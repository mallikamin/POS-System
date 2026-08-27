"""F31: a sale must know which site made it and which channel it came through.

The defect these tests pin: `OrderCreate` accepted neither field, nothing in
`order_service` ever wrote `Order.location_id`, and so every order the POS had
ever taken was written with both columns NULL. Two consequences, both on a
document a client actually receives:

  * `tax_invoice_service` read `order.location_id` raw, found None, and issued a
    UAE A4 tax invoice with **no TRN on it**. Measured on production before the
    fix: all nine seeded `FZ-000x` orders carried the TRN, all three orders
    actually rung up on the POS carried `trn: null`.
  * The sale landed as "Unassigned" in the per-channel profitability report,
    which is the single report the client asked for by name.

Written the way the F19 post-mortem said to write them: every test here drives
`order_service.create_order`, the real write path, rather than hand-building an
ORM row with the answer already in it.

The first test is the one that matters most operationally. It is chick-shack's
shape -- a live trading tenant with no locations configured at all -- and it
asserts that attribution stays entirely optional.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import Location, SalesChannel
from app.models.menu import Category, MenuItem
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.order import OrderCreate, OrderItemCreate
from app.services import order_service, tax_invoice_service

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures built by hand, so each test states its own world
# ---------------------------------------------------------------------------


async def _tenant(db: AsyncSession, *, slug: str, rate_bps: int = 500) -> Tenant:
    tenant_id = uuid.uuid4()
    tenant = Tenant(
        id=tenant_id,
        tenant_id=tenant_id,
        name=f"Test {slug}",
        slug=slug,
        is_active=True,
    )
    db.add(tenant)
    await db.flush()
    db.add(
        RestaurantConfig(
            tenant_id=tenant.id,
            currency="AED",
            timezone="Asia/Dubai",
            payment_flow="order_first",
            tax_inclusive=True,
            default_tax_rate=rate_bps,
        )
    )
    await db.flush()
    return tenant


async def _location(
    db: AsyncSession,
    tenant: Tenant,
    *,
    name: str,
    code: str,
    default: bool,
    trn: str | None = None,
) -> Location:
    location = Location(
        tenant_id=tenant.id,
        name=name,
        code=code,
        location_type="production",
        legal_name=f"{name} Legal Entity",
        tax_registration_number=trn,
        invoice_format="a4_tax_invoice",
        # Give each site its own document series, so a test that checks
        # numbering is checking that site's run and not the shared INV default.
        invoice_prefix=code,
        is_active=True,
        is_default=default,
    )
    db.add(location)
    await db.flush()
    return location


async def _channel(
    db: AsyncSession, tenant: Tenant, *, name: str, code: str, bps: int
) -> SalesChannel:
    channel = SalesChannel(
        tenant_id=tenant.id, name=name, code=code, commission_bps=bps, is_active=True
    )
    db.add(channel)
    await db.flush()
    return channel


async def _item(db: AsyncSession, tenant: Tenant, price: int = 1000) -> MenuItem:
    category = Category(tenant_id=tenant.id, name="Bakery", display_order=1)
    db.add(category)
    await db.flush()
    item = MenuItem(
        tenant_id=tenant.id,
        category_id=category.id,
        name="Butter Croissant",
        price=price,
        is_available=True,
    )
    db.add(item)
    await db.flush()
    return item


async def _order(
    db: AsyncSession,
    tenant: Tenant,
    user: User,
    item: MenuItem,
    **attribution,
):
    return await order_service.create_order(
        db,
        tenant_id=tenant.id,
        user_id=user.id,
        data=OrderCreate(
            order_type="takeaway",
            items=[
                OrderItemCreate(
                    menu_item_id=item.id,
                    name=item.name,
                    quantity=1,
                    unit_price=item.price,
                )
            ],
            **attribution,
        ),
    )


# ---------------------------------------------------------------------------
# The one that protects the live shop
# ---------------------------------------------------------------------------


async def test_tenant_with_no_locations_still_takes_orders(
    db: AsyncSession, admin_user: User
):
    """chick-shack's shape. No locations, no channels, nothing configured.

    Attribution is an optional capability on the same contract that
    `_apply_inventory_and_commission` already honours at completion. If this
    test ever fails, a live restaurant cannot ring up a sale.
    """
    tenant = await _tenant(db, slug="attr-no-locations")
    item = await _item(db, tenant)

    order = await _order(db, tenant, admin_user, item)

    assert order.location_id is None
    assert order.sales_channel_id is None
    assert order.total == 1000, "the sale itself must be untouched by attribution"


async def test_tenant_with_no_locations_gets_the_pre_locations_invoice(
    db: AsyncSession, admin_user: User
):
    """No locations means no TRN and the tenant's own name. Unchanged behaviour."""
    tenant = await _tenant(db, slug="attr-no-loc-invoice")
    item = await _item(db, tenant)
    order = await _order(db, tenant, admin_user, item)

    invoice = await tax_invoice_service.get_tax_invoice(db, tenant.id, order.id)

    assert invoice.supplier.trn is None
    assert invoice.supplier.name == tenant.name


# ---------------------------------------------------------------------------
# The default site
# ---------------------------------------------------------------------------


async def test_sale_falls_back_to_the_default_location(
    db: AsyncSession, admin_user: User
):
    """The POS names no location, so the sale lands at the default site.

    This is what `Location.is_default` has always claimed to do in its own
    docstring: "Where a sale lands when the caller names no location."
    """
    tenant = await _tenant(db, slug="attr-default-loc")
    default = await _location(
        db, tenant, name="Production", code="PROD", default=True, trn="100123456700003"
    )
    await _location(db, tenant, name="Delivery", code="DEL", default=False, trn="999")
    item = await _item(db, tenant)

    order = await _order(db, tenant, admin_user, item)

    assert order.location_id == default.id


async def test_tax_invoice_carries_a_trn_for_a_pos_sale(
    db: AsyncSession, admin_user: User
):
    """F31 itself. Before the fix this invoice went out with `trn: null`."""
    tenant = await _tenant(db, slug="attr-trn")
    await _location(
        db, tenant, name="Production", code="PROD", default=True, trn="100123456700003"
    )
    item = await _item(db, tenant)
    order = await _order(db, tenant, admin_user, item)

    invoice = await tax_invoice_service.get_tax_invoice(db, tenant.id, order.id)

    assert invoice.supplier.trn == "100123456700003", (
        "a UAE A4 tax invoice without a TRN is not a valid tax invoice"
    )
    assert invoice.supplier.name == "Production Legal Entity"


async def test_tax_invoice_recovers_a_trn_for_an_order_written_before_the_fix(
    db: AsyncSession, admin_user: User
):
    """Historical rows have location_id NULL and cannot be back-filled by hand.

    The invoice resolves the default site at render time, so the nine orders
    already sitting on production stop issuing without a TRN too.
    """
    tenant = await _tenant(db, slug="attr-trn-historic")
    await _location(
        db, tenant, name="Production", code="PROD", default=True, trn="100123456700003"
    )
    item = await _item(db, tenant)
    order = await _order(db, tenant, admin_user, item)

    order.location_id = None  # exactly how every pre-fix row is stored
    await db.flush()

    invoice = await tax_invoice_service.get_tax_invoice(db, tenant.id, order.id)

    assert invoice.supplier.trn == "100123456700003"


# ---------------------------------------------------------------------------
# Explicit attribution, and refusing to guess
# ---------------------------------------------------------------------------


async def test_an_explicitly_named_location_is_used(
    db: AsyncSession, admin_user: User
):
    tenant = await _tenant(db, slug="attr-explicit-loc")
    await _location(db, tenant, name="Production", code="PROD", default=True, trn="1")
    delivery = await _location(
        db, tenant, name="Delivery", code="DEL", default=False, trn="2"
    )
    item = await _item(db, tenant)

    order = await _order(db, tenant, admin_user, item, location_id=delivery.id)

    assert order.location_id == delivery.id, "the named site must win over the default"


async def test_a_location_from_another_tenant_is_refused(
    db: AsyncSession, admin_user: User
):
    """Never substitute the default for a bad id.

    Quietly falling back would attribute a sale, and its VAT, to a different
    registered legal entity than the caller asked for.
    """
    mine = await _tenant(db, slug="attr-mine")
    theirs = await _tenant(db, slug="attr-theirs")
    await _location(db, mine, name="Production", code="PROD", default=True, trn="1")
    stranger = await _location(
        db, theirs, name="Theirs", code="PROD", default=True, trn="2"
    )
    item = await _item(db, mine)

    with pytest.raises(ValueError):
        await _order(db, mine, admin_user, item, location_id=stranger.id)


async def test_a_channel_from_another_tenant_is_refused(
    db: AsyncSession, admin_user: User
):
    mine = await _tenant(db, slug="attr-chan-mine")
    theirs = await _tenant(db, slug="attr-chan-theirs")
    stranger = await _channel(db, theirs, name="Talabat", code="TLB", bps=1500)
    item = await _item(db, mine)

    with pytest.raises(ValueError):
        await _order(db, mine, admin_user, item, sales_channel_id=stranger.id)


# ---------------------------------------------------------------------------
# The report the client asked for, end to end
# ---------------------------------------------------------------------------


async def test_channel_commission_is_frozen_when_the_order_completes(
    db: AsyncSession, admin_user: User
):
    """`snapshot_commission` has always been wired into completion.

    It only ever produced zero because nothing put a channel on the order in
    the first place. AED 100.00 through a 15% channel owes 15.00.
    """
    tenant = await _tenant(db, slug="attr-commission", rate_bps=0)
    await _location(db, tenant, name="Production", code="PROD", default=True, trn="1")
    talabat = await _channel(db, tenant, name="Talabat", code="TLB", bps=1500)
    item = await _item(db, tenant, price=10000)

    order = await _order(db, tenant, admin_user, item, sales_channel_id=talabat.id)
    assert order.sales_channel_id == talabat.id

    for status in ("ready", "served", "completed"):
        order = await order_service.transition_order(
            db,
            order_id=order.id,
            tenant_id=tenant.id,
            new_status=status,
            user_id=admin_user.id,
        )

    assert order.channel_commission_minor == 1500, (
        "15% of AED 100.00 is AED 15.00, frozen at the rate in force on the day"
    )


async def test_the_profitability_report_separates_direct_from_platform(
    db: AsyncSession, admin_user: User
):
    """The claim the playbook makes to the client in Exercise 10.

    A direct channel must show a visibly better margin than a platform one,
    and both must appear as their own rows rather than collapsing into
    "Direct / unassigned".
    """
    from app.services import location_service

    tenant = await _tenant(db, slug="attr-report", rate_bps=0)
    await _location(db, tenant, name="Production", code="PROD", default=True, trn="1")
    talabat = await _channel(db, tenant, name="Talabat", code="TLB", bps=1500)
    whatsapp = await _channel(db, tenant, name="WhatsApp", code="WA", bps=0)
    item = await _item(db, tenant, price=10000)

    for channel in (talabat, whatsapp):
        order = await _order(db, tenant, admin_user, item, sales_channel_id=channel.id)
        for status in ("ready", "served", "completed"):
            order = await order_service.transition_order(
                db,
                order_id=order.id,
                tenant_id=tenant.id,
                new_status=status,
                user_id=admin_user.id,
            )

    report = await location_service.profitability_report(db, tenant.id)

    names = {row["name"]: row for row in report["by_channel"]}
    assert "Talabat" in names and "WhatsApp" in names, (
        f"channels must be attributed, got {sorted(names)}"
    )
    assert "Direct / unassigned" not in names
    assert names["Talabat"]["commission_minor"] == 1500
    assert names["WhatsApp"]["commission_minor"] == 0
    assert names["WhatsApp"]["net_margin_pct"] > names["Talabat"]["net_margin_pct"], (
        "the direct channel must show the better margin, which is the whole "
        "point of the report"
    )
    assert report["by_location"][0]["name"] == "Production"


# ---------------------------------------------------------------------------
# F33: the number on the document must identify the document
# ---------------------------------------------------------------------------


async def test_two_orders_never_share_an_invoice_number(
    db: AsyncSession, admin_user: User
):
    """The measured defect: seven separate sales all read `FZD-00007`.

    The old test asserted only `invoice_number.startswith("INV-")`, which is
    true of every duplicate, so it could not fail on the thing that was broken.
    """
    tenant = await _tenant(db, slug="inv-unique")
    await _location(db, tenant, name="Production", code="PROD", default=True, trn="1")
    item = await _item(db, tenant)

    numbers = []
    for _ in range(5):
        order = await _order(db, tenant, admin_user, item)
        invoice = await tax_invoice_service.get_tax_invoice(db, tenant.id, order.id)
        numbers.append(invoice.invoice_number)

    assert len(set(numbers)) == 5, f"duplicate invoice numbers issued: {numbers}"


async def test_an_invoice_number_does_not_move_when_later_sales_happen(
    db: AsyncSession, admin_user: User
):
    """Re-open yesterday's invoice after fifty more sales and it must be identical.

    Under the count-based scheme the number tracked the order total, so a
    document silently renumbered itself every time the shop sold something.
    """
    tenant = await _tenant(db, slug="inv-stable")
    await _location(db, tenant, name="Production", code="PROD", default=True, trn="1")
    item = await _item(db, tenant)

    first = await _order(db, tenant, admin_user, item)
    issued = (
        await tax_invoice_service.get_tax_invoice(db, tenant.id, first.id)
    ).invoice_number

    for _ in range(4):
        later = await _order(db, tenant, admin_user, item)
        await tax_invoice_service.get_tax_invoice(db, tenant.id, later.id)

    reissued = (
        await tax_invoice_service.get_tax_invoice(db, tenant.id, first.id)
    ).invoice_number

    assert reissued == issued, (
        f"the same order issued {issued} and then {reissued}; a tax invoice "
        "number must identify one document permanently"
    )


async def test_the_sequence_starts_at_one_and_runs_consecutively(
    db: AsyncSession, admin_user: User
):
    """A first invoice numbered 00012 because the shop had taken 12 orders is
    not a sequence, it is a coincidence."""
    tenant = await _tenant(db, slug="inv-seq")
    await _location(db, tenant, name="Production", code="PROD", default=True, trn="1")
    item = await _item(db, tenant)

    issued = []
    for _ in range(3):
        order = await _order(db, tenant, admin_user, item)
        issued.append(
            (await tax_invoice_service.get_tax_invoice(db, tenant.id, order.id)).invoice_number
        )

    assert issued == ["PROD-00001", "PROD-00002", "PROD-00003"], issued


async def test_each_prefix_keeps_its_own_run_of_numbers(
    db: AsyncSession, admin_user: User
):
    """Two sites with different prefixes are two document series."""
    tenant = await _tenant(db, slug="inv-two-series")
    production = await _location(
        db, tenant, name="Production", code="PROD", default=True, trn="1"
    )
    delivery = await _location(
        db, tenant, name="Delivery", code="DEL", default=False, trn="2"
    )
    production.invoice_prefix = "FZW"
    delivery.invoice_prefix = "FZD"
    await db.flush()
    item = await _item(db, tenant)

    a = await _order(db, tenant, admin_user, item, location_id=production.id)
    b = await _order(db, tenant, admin_user, item, location_id=delivery.id)
    c = await _order(db, tenant, admin_user, item, location_id=production.id)

    numbers = [
        (await tax_invoice_service.get_tax_invoice(db, tenant.id, o.id)).invoice_number
        for o in (a, b, c)
    ]

    assert numbers == ["FZW-00001", "FZD-00001", "FZW-00002"], numbers


async def test_a_tenant_with_no_locations_still_gets_a_unique_sequence(
    db: AsyncSession, admin_user: User
):
    """chick-shack's shape again. No locations means the default INV series."""
    tenant = await _tenant(db, slug="inv-no-locations")
    item = await _item(db, tenant)

    numbers = []
    for _ in range(3):
        order = await _order(db, tenant, admin_user, item)
        numbers.append(
            (await tax_invoice_service.get_tax_invoice(db, tenant.id, order.id)).invoice_number
        )

    assert numbers == ["INV-00001", "INV-00002", "INV-00003"], numbers
