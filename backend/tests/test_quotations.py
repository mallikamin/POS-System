"""Back-office quotations: pricing, expiry, and the one-way trip to an order.

The invariants:

  * prices INCLUDE VAT, so the tax is backed OUT and the total equals the sum
    of the lines -- the exact opposite of a purchase order, and getting the two
    the wrong way round misstates tax on every document
  * a line's price is SNAPSHOTTED; the offer does not move when the menu does
  * expiry is DERIVED from the date, never written, so it is right in the
    window between the date passing and any job running
  * an accepted quotation is a record of an agreement and cannot be edited
  * conversion happens once, produces a real order at the QUOTED prices, and
    refuses to silently drop a line it cannot represent

⚠️ A regression net. `app/scripts/verify_quotations.py` is the verification,
against the real API.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu import Category, MenuItem
from app.models.tenant import Tenant
from app.services import quotation_service
from app.services.quotation_service import QuotationError

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def croissant(db: AsyncSession, tenant: Tenant) -> MenuItem:
    category = Category(tenant_id=tenant.id, name="Pastry", display_order=1)
    db.add(category)
    await db.flush()
    item = MenuItem(
        tenant_id=tenant.id,
        category_id=category.id,
        name="Butter Croissant",
        price=900,  # 9.00, VAT-inclusive
    )
    db.add(item)
    await db.flush()
    return item


async def _quote(db, tenant, croissant, **overrides):
    data = {
        "customer_name": "Emirates Catering",
        "customer_email": "buyer@example.invalid",
        "tax_rate_bps": 500,
        "lines": [{"menu_item_id": croissant.id, "quantity": 400}],
    }
    data.update(overrides)
    return await quotation_service.create_quotation(
        db, tenant_id=tenant.id, data=data, created_by=None
    )


# ---------------------------------------------------------------------------
# PRICING
# ---------------------------------------------------------------------------


async def test_vat_is_backed_out_not_added(db, tenant, croissant):
    """400 x 9.00 = 3,600.00. The VAT is INSIDE that, not on top of it."""
    quote = await _quote(db, tenant, croissant)
    assert quote.subtotal_minor == 360000
    assert quote.total_minor == 360000  # NOT 378000
    # 360000 * 10000 // 10500 = 342857 net, so 17143 of VAT.
    assert quote.tax_minor == 360000 - (360000 * 10000) // 10500
    assert quote.tax_minor == 17143


async def test_a_discount_reduces_the_total_and_the_vat_with_it(
    db, tenant, croissant
):
    quote = await _quote(db, tenant, croissant, discount_minor=60000)
    assert quote.subtotal_minor == 360000
    assert quote.total_minor == 300000
    assert quote.tax_minor == 300000 - (300000 * 10000) // 10500


async def test_no_vat_rate_means_no_vat(db, tenant, croissant):
    quote = await _quote(db, tenant, croissant, tax_rate_bps=0)
    assert quote.tax_minor == 0
    assert quote.total_minor == quote.subtotal_minor


async def test_a_menu_line_snapshots_the_price(db, tenant, croissant):
    """The offer must not move when the menu does."""
    quote = await _quote(db, tenant, croissant)
    assert quote.items[0].unit_price_minor == 900

    croissant.price = 1200
    await db.flush()

    reread = await quotation_service.get_quotation(db, tenant.id, quote.id)
    assert reread.items[0].unit_price_minor == 900
    assert reread.total_minor == 360000


async def test_a_free_text_line_needs_its_own_name_and_price(
    db, tenant, croissant
):
    with pytest.raises(QuotationError, match="needs a price"):
        await _quote(
            db,
            tenant,
            croissant,
            lines=[{"name": "Delivery to Abu Dhabi", "quantity": 1}],
        )
    with pytest.raises(QuotationError, match="needs a description"):
        await _quote(
            db,
            tenant,
            croissant,
            lines=[{"quantity": 1, "unit_price_minor": 15000}],
        )


async def test_an_empty_quotation_is_refused(db, tenant, croissant):
    with pytest.raises(QuotationError, match="at least one line"):
        await _quote(db, tenant, croissant, lines=[])


async def test_it_cannot_expire_before_it_is_issued(db, tenant, croissant):
    with pytest.raises(QuotationError, match="expire before"):
        await _quote(
            db, tenant, croissant, valid_until=date.today() - timedelta(days=1)
        )


async def test_totals_follow_an_edit(db, tenant, croissant):
    quote = await _quote(db, tenant, croissant)
    updated = await quotation_service.update_quotation(
        db,
        tenant_id=tenant.id,
        quotation_id=quote.id,
        data={"lines": [{"menu_item_id": croissant.id, "quantity": 10}]},
    )
    assert updated.subtotal_minor == 9000
    assert updated.total_minor == 9000


# ---------------------------------------------------------------------------
# EXPIRY
# ---------------------------------------------------------------------------


async def test_expiry_is_derived_from_the_date(db, tenant, croissant):
    quote = await _quote(db, tenant, croissant)
    quote.status = "sent"

    quote.valid_until = date.today()
    # Valid THROUGH its last day, not up to the morning of it.
    assert quotation_service.is_expired(quote) is False
    assert quotation_service.display_status(quote) == "sent"

    quote.valid_until = date.today() - timedelta(days=1)
    assert quotation_service.is_expired(quote) is True
    assert quotation_service.display_status(quote) == "expired"
    # Derived, never written.
    assert quote.status == "sent"


async def test_a_decided_quotation_never_reads_as_expired(db, tenant, croissant):
    """The offer was taken up while it stood; the calendar cannot undo that."""
    quote = await _quote(db, tenant, croissant)
    quote.valid_until = date.today() - timedelta(days=30)
    for status in ("accepted", "converted", "declined"):
        quote.status = status
        assert quotation_service.is_expired(quote) is False
        assert quotation_service.display_status(quote) == status


# ---------------------------------------------------------------------------
# LIFECYCLE
# ---------------------------------------------------------------------------


async def test_a_draft_cannot_be_accepted(db, tenant, croissant):
    quote = await _quote(db, tenant, croissant)
    with pytest.raises(QuotationError, match="not been sent"):
        await quotation_service.decide(
            db, tenant_id=tenant.id, quotation_id=quote.id, accepted=True
        )


async def test_a_failed_email_does_not_undo_the_send(db, tenant, croissant):
    quote = await _quote(db, tenant, croissant)
    quote = await quotation_service.mark_sent(
        db,
        tenant_id=tenant.id,
        quotation_id=quote.id,
        sent_to_email="buyer@example.invalid",
        email_delivered=False,
        email_error="SMTPConnectError: refused",
    )
    assert quote.status == "sent"
    assert quote.email_send_count == 0
    assert "refused" in quote.last_email_error


async def test_an_accepted_quotation_cannot_be_edited(db, tenant, croissant):
    quote = await _quote(db, tenant, croissant)
    await quotation_service.mark_sent(
        db, tenant_id=tenant.id, quotation_id=quote.id
    )
    await quotation_service.decide(
        db, tenant_id=tenant.id, quotation_id=quote.id, accepted=True
    )
    with pytest.raises(QuotationError, match="cannot be changed"):
        await quotation_service.update_quotation(
            db,
            tenant_id=tenant.id,
            quotation_id=quote.id,
            data={"notes": "too late"},
        )


async def test_a_declined_quotation_keeps_the_reason(db, tenant, croissant):
    quote = await _quote(db, tenant, croissant)
    await quotation_service.mark_sent(
        db, tenant_id=tenant.id, quotation_id=quote.id
    )
    quote = await quotation_service.decide(
        db,
        tenant_id=tenant.id,
        quotation_id=quote.id,
        accepted=False,
        reason="Went with another supplier on price",
    )
    assert quote.status == "declined"
    assert "another supplier" in quote.decline_reason
    assert quote.decided_at is not None


async def test_an_expired_offer_can_still_be_honoured(db, tenant, croissant):
    """The system should not be the thing that refuses a sale the seller wants."""
    quote = await _quote(db, tenant, croissant)
    await quotation_service.mark_sent(
        db, tenant_id=tenant.id, quotation_id=quote.id
    )
    quote.valid_until = date.today() - timedelta(days=3)
    await db.flush()

    quote = await quotation_service.decide(
        db, tenant_id=tenant.id, quotation_id=quote.id, accepted=True
    )
    assert quote.status == "accepted"
    # And the original validity date is not rewritten to cover it up.
    assert quote.valid_until == date.today() - timedelta(days=3)


# ---------------------------------------------------------------------------
# CONVERSION
# ---------------------------------------------------------------------------


async def test_only_an_accepted_quotation_converts(db, tenant, croissant, admin_user):
    quote = await _quote(db, tenant, croissant)
    with pytest.raises(QuotationError, match="Only an accepted"):
        await quotation_service.convert_to_order(
            db,
            tenant_id=tenant.id,
            quotation_id=quote.id,
            created_by=admin_user.id,
        )


async def test_a_free_text_line_blocks_conversion(db, tenant, croissant, admin_user):
    """Dropping it would quietly change the price the customer agreed to."""
    quote = await _quote(
        db,
        tenant,
        croissant,
        lines=[
            {"menu_item_id": croissant.id, "quantity": 400},
            {
                "name": "Delivery to Abu Dhabi",
                "quantity": 1,
                "unit_price_minor": 15000,
            },
        ],
    )
    await quotation_service.mark_sent(
        db, tenant_id=tenant.id, quotation_id=quote.id
    )
    await quotation_service.decide(
        db, tenant_id=tenant.id, quotation_id=quote.id, accepted=True
    )
    with pytest.raises(QuotationError, match="Delivery to Abu Dhabi"):
        await quotation_service.convert_to_order(
            db,
            tenant_id=tenant.id,
            quotation_id=quote.id,
            created_by=admin_user.id,
        )


async def test_conversion_creates_an_order_at_the_quoted_price(
    db, tenant, croissant, admin_user
):
    quote = await _quote(db, tenant, croissant, lines=[
        {"menu_item_id": croissant.id, "quantity": 20}
    ])
    await quotation_service.mark_sent(
        db, tenant_id=tenant.id, quotation_id=quote.id
    )
    await quotation_service.decide(
        db, tenant_id=tenant.id, quotation_id=quote.id, accepted=True
    )

    # The menu moves AFTER the offer was accepted. The order must not follow.
    croissant.price = 1500
    await db.flush()

    quote, order = await quotation_service.convert_to_order(
        db, tenant_id=tenant.id, quotation_id=quote.id, created_by=admin_user.id
    )
    assert quote.status == "converted"
    assert quote.converted_order_id == order.id
    assert quote.converted_at is not None
    assert order.subtotal == 18000  # 20 x 900, the QUOTED price
    assert quote.quote_number in (order.notes or "")


async def test_a_quotation_converts_only_once(db, tenant, croissant, admin_user):
    quote = await _quote(db, tenant, croissant, lines=[
        {"menu_item_id": croissant.id, "quantity": 5}
    ])
    await quotation_service.mark_sent(
        db, tenant_id=tenant.id, quotation_id=quote.id
    )
    await quotation_service.decide(
        db, tenant_id=tenant.id, quotation_id=quote.id, accepted=True
    )
    await quotation_service.convert_to_order(
        db, tenant_id=tenant.id, quotation_id=quote.id, created_by=admin_user.id
    )
    with pytest.raises(QuotationError, match="already become an order"):
        await quotation_service.convert_to_order(
            db,
            tenant_id=tenant.id,
            quotation_id=quote.id,
            created_by=admin_user.id,
        )


async def test_a_converted_quotation_cannot_be_re_decided(
    db, tenant, croissant, admin_user
):
    quote = await _quote(db, tenant, croissant, lines=[
        {"menu_item_id": croissant.id, "quantity": 5}
    ])
    await quotation_service.mark_sent(
        db, tenant_id=tenant.id, quotation_id=quote.id
    )
    await quotation_service.decide(
        db, tenant_id=tenant.id, quotation_id=quote.id, accepted=True
    )
    await quotation_service.convert_to_order(
        db, tenant_id=tenant.id, quotation_id=quote.id, created_by=admin_user.id
    )
    with pytest.raises(QuotationError, match="already become an order"):
        await quotation_service.decide(
            db, tenant_id=tenant.id, quotation_id=quote.id, accepted=False
        )


async def test_tenant_isolation(db, tenant, croissant):
    quote = await _quote(db, tenant, croissant)
    other_id = uuid.uuid4()
    other = Tenant(
        id=other_id,
        tenant_id=other_id,
        name="Someone Else",
        slug="someone-else",
        is_active=True,
    )
    db.add(other)
    await db.flush()
    with pytest.raises(QuotationError, match="No such quotation"):
        await quotation_service.get_quotation(db, other.id, quote.id)
