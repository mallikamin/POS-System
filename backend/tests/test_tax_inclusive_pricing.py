"""Tax-inclusive pricing: the total a customer is actually charged.

UAT finding F19, 2026-08-28.

`restaurant_configs.tax_inclusive` has existed since Phase 2, defaults to True,
and was read by exactly ONE service (`tax_invoice_service`). The order path never
consulted it and unconditionally did:

    tax_amount = round(subtotal * rate_bps / 10_000)
    total      = subtotal + tax_amount

which is correct only when prices EXCLUDE tax. For a tenant whose menu prices
already contain VAT, the VAT was charged a second time: three croissants on a
AED 9.00 board rang up at AED 28.35 instead of AED 27.00, while the A4 tax
invoice — which DID back the VAT out — reported a different figure for the same
sale.

Why 765 passing tests did not catch it, which is the part worth remembering:

  1. **No test created an order.** Not through `order_service.create_order`,
     not through `POST /api/v1/orders`. Verified by grep across `backend/tests`
     before writing this file. Every order in the suite was hand-built as an ORM
     row with a literal `tax_amount=800` / `=1379` / `=0`, so the calculation was
     never executed once.
  2. Where a total was asserted, the expectation encoded the bug —
     `test_p1b_discounts.py` carries the comment
     `# total = subtotal + tax - discount`. A test written from the code, after
     the code, asserts whatever the code does.
  3. No tenant had ever combined `tax_inclusive=True` with a NON-ZERO rate.
     Chick Shack runs rate 0; the Pakistan demo tenant is priced exclusive-style.
     FZ LLC is the first, so FZ LLC is where it surfaced.

So this file does two things: it pins the arithmetic, and it creates a real order
through the real service — the test that was missing.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu import Category, MenuItem
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.order import OrderCreate, OrderItemCreate
from app.services import order_service
from app.services.order_service import compute_tax


# ---------------------------------------------------------------------------
# The arithmetic
# ---------------------------------------------------------------------------


class TestComputeTax:
    def test_inclusive_backs_the_tax_out_of_the_price(self):
        """Three items at AED 9.00 with 5% VAT already in the price."""
        tax, total = compute_tax(2700, 500, prices_include_tax=True)
        assert total == 2700, "the customer pays the price on the board"
        assert tax == 129, "129 fils of VAT sits inside 2700, it is not added"

    def test_exclusive_adds_the_tax_on_top(self):
        tax, total = compute_tax(2700, 500, prices_include_tax=False)
        assert tax == 135
        assert total == 2835

    def test_the_two_conventions_actually_differ(self):
        """Guards against a 'fix' that quietly makes the flag a no-op."""
        assert compute_tax(2700, 500, True) != compute_tax(2700, 500, False)

    def test_matches_the_figure_promised_to_the_client(self):
        """The UAT playbook tells Martin, in writing, that on 100.00 dirhams at
        5% the VAT shown should be **4.76, not 5.00**. Before this fix the
        system said 5.00. The document and the software now agree."""
        tax, total = compute_tax(10_000, 500, prices_include_tax=True)
        assert tax == 476
        assert total == 10_000

    @pytest.mark.parametrize(
        "subtotal", [0, 1, 7, 99, 100, 333, 2700, 10_000, 123_456, 999_999]
    )
    @pytest.mark.parametrize("rate_bps", [500, 1600, 2000])
    def test_inclusive_never_loses_or_invents_a_fil(self, subtotal, rate_bps):
        """`net + tax == subtotal` exactly, at every value and rate.

        This is why the tax is derived by SUBTRACTION rather than as
        `net * rate`: two independent roundings would leave a remainder that
        either vanishes or appears from nowhere, and on a tax document a
        stray minor unit is a reconciliation failure.
        """
        tax, total = compute_tax(subtotal, rate_bps, prices_include_tax=True)
        assert total == subtotal
        assert 0 <= tax <= subtotal
        assert (subtotal - tax) + tax == subtotal

    @pytest.mark.parametrize("prices_include_tax", [True, False])
    @pytest.mark.parametrize("subtotal", [0, 1, 500, 233_00, 642_087])
    def test_zero_rate_is_identical_under_both_conventions(
        self, subtotal, prices_include_tax
    ):
        """🔴 THE CHICK SHACK SAFETY PROOF. Do not delete this test.

        Chick Shack is live, takes real money, and runs `default_tax_rate = 0`
        (deliberately — nobody has confirmed a VAT registration). At rate 0 both
        branches must return `(0, subtotal)`, which is what makes it safe to ship
        this change to a trading shop: their totals are provably unchanged.

        `642_087` is their actual recorded payments total, used here so the
        assertion is anchored to a real number rather than a toy one.
        """
        assert compute_tax(subtotal, 0, prices_include_tax) == (0, subtotal)

    def test_negative_rate_is_treated_as_no_tax(self):
        """Defensive: a bad config must not produce a negative total."""
        assert compute_tax(1000, -100, True) == (0, 1000)


# ---------------------------------------------------------------------------
# The test that was missing: an order, created by the real service
# ---------------------------------------------------------------------------


async def _tenant_with_config(
    db: AsyncSession, *, slug: str, rate_bps: int, inclusive: bool
) -> Tenant:
    # `id` is supplied rather than left to the default: `tenant_id` is NOT NULL
    # and self-referential on this table, so both have to be known before flush.
    tenant_id = uuid.uuid4()
    tenant = Tenant(
        id=tenant_id, tenant_id=tenant_id, name=f"Test {slug}", slug=slug, is_active=True
    )
    db.add(tenant)
    await db.flush()

    db.add(
        RestaurantConfig(
            tenant_id=tenant.id,
            currency="AED",
            timezone="Asia/Dubai",
            payment_flow="order_first",
            tax_inclusive=inclusive,
            default_tax_rate=rate_bps,
        )
    )
    await db.flush()
    return tenant


async def _menu_item(db: AsyncSession, tenant: Tenant, price: int) -> MenuItem:
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


@pytest.mark.asyncio
async def test_order_total_equals_the_shelf_price_when_prices_include_tax(
    db: AsyncSession, admin_user: User
):
    """The exact scenario from UAT: 3 x AED 9.00, 5% VAT, prices inclusive.

    Before the fix this order totalled 2835. The menu board says 2700.
    """
    tenant = await _tenant_with_config(
        db, slug="incl-vat-test", rate_bps=500, inclusive=True
    )
    item = await _menu_item(db, tenant, price=900)

    order = await order_service.create_order(
        db,
        tenant_id=tenant.id,
        user_id=admin_user.id,
        data=OrderCreate(
            order_type="takeaway",
            items=[
                OrderItemCreate(
                    menu_item_id=item.id,
                    name="Butter Croissant",
                    quantity=3,
                    unit_price=900,
                )
            ],
        ),
    )

    assert order.subtotal == 2700
    assert order.total == 2700, (
        "a tax-inclusive tenant must charge the price on the board; "
        f"got {order.total}"
    )
    assert order.tax_amount == 129, "the VAT is reported, but from inside the price"
    assert order.subtotal - order.tax_amount + order.tax_amount == order.total


@pytest.mark.asyncio
async def test_order_total_adds_tax_when_prices_exclude_it(
    db: AsyncSession, admin_user: User
):
    """The other convention still works — the fix is a branch, not a rewrite."""
    tenant = await _tenant_with_config(
        db, slug="excl-vat-test", rate_bps=500, inclusive=False
    )
    item = await _menu_item(db, tenant, price=900)

    order = await order_service.create_order(
        db,
        tenant_id=tenant.id,
        user_id=admin_user.id,
        data=OrderCreate(
            order_type="takeaway",
            items=[
                OrderItemCreate(
                    menu_item_id=item.id,
                    name="Butter Croissant",
                    quantity=3,
                    unit_price=900,
                )
            ],
        ),
    )

    assert order.subtotal == 2700
    assert order.tax_amount == 135
    assert order.total == 2835


@pytest.mark.asyncio
async def test_zero_rate_tenant_order_total_is_the_subtotal(
    db: AsyncSession, admin_user: User
):
    """Chick Shack's shape, end to end rather than only at the pure function."""
    tenant = await _tenant_with_config(
        db, slug="zero-rate-test", rate_bps=0, inclusive=True
    )
    item = await _menu_item(db, tenant, price=650)

    order = await order_service.create_order(
        db,
        tenant_id=tenant.id,
        user_id=admin_user.id,
        data=OrderCreate(
            order_type="takeaway",
            items=[
                OrderItemCreate(
                    menu_item_id=item.id,
                    name="Wings",
                    quantity=2,
                    unit_price=650,
                )
            ],
        ),
    )

    assert order.subtotal == 1300
    assert order.tax_amount == 0
    assert order.total == 1300
