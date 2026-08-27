"""A4 VAT tax invoice, and the arithmetic underneath it.

The VAT split is the part worth testing hardest. This POS stores VAT-INCLUSIVE
prices, so a tax invoice has to back the VAT out of the gross rather than add it
on top. Getting that backwards overstates the tax on every document by roughly
0.24% of the invoice, which is exactly the kind of error that survives a demo
and surfaces in an audit.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import Location
from app.models.menu import Category, MenuItem
from app.models.order import Order, OrderItem
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.models.user import User
from app.services import tax_invoice_service
from app.services.tax_invoice_service import (
    TaxInvoiceError,
    add_vat_exclusive,
    split_vat_inclusive,
)

class TestVatArithmetic:
    """Pure functions, no database. The maths must be exact."""

    def test_five_percent_backed_out_of_an_inclusive_price(self):
        # 105.00 gross at 5% inclusive is 100.00 net + 5.00 VAT.
        net, vat = split_vat_inclusive(10500, 500)
        assert (net, vat) == (10000, 500)

    def test_net_and_vat_always_sum_back_to_the_gross(self):
        """The invariant that matters: lines must sum to what was charged."""
        for gross in (1, 7, 99, 100, 333, 1234, 99999, 100000):
            net, vat = split_vat_inclusive(gross, 500)
            assert net + vat == gross, f"lost a fils at {gross}"

    def test_zero_rate_adds_nothing(self):
        assert split_vat_inclusive(5000, 0) == (5000, 0)

    def test_exclusive_adds_on_top(self):
        assert add_vat_exclusive(10000, 500) == (10000, 500)

    def test_inclusive_and_exclusive_are_not_the_same(self):
        """Guards the actual bug: treating an inclusive price as exclusive."""
        gross = 10500
        inclusive_net, inclusive_vat = split_vat_inclusive(gross, 500)
        _, wrong_vat = add_vat_exclusive(gross, 500)
        assert inclusive_vat == 500
        assert wrong_vat == 525  # what you get by adding 5% to a 5%-inclusive price
        assert inclusive_net == 10000


@pytest_asyncio.fixture
async def vat_config(db: AsyncSession, tenant: Tenant) -> RestaurantConfig:
    config = RestaurantConfig(
        tenant_id=tenant.id,
        currency="AED",
        tax_inclusive=True,
        default_tax_rate=500,  # 5% in basis points
    )
    db.add(config)
    await db.flush()
    return config


@pytest_asyncio.fixture
async def wholesale_site(db: AsyncSession, tenant: Tenant) -> Location:
    loc = Location(
        tenant_id=tenant.id,
        name="Production & Wholesale",
        code="PROD",
        location_type="production",
        legal_name="FZ LLC",
        tax_registration_number="100123456700003",
        address_line1="Warehouse 12, Al Quoz",
        city="Dubai",
        country="United Arab Emirates",
        invoice_format="a4_tax_invoice",
        invoice_prefix="FZW",
        is_default=True,
    )
    db.add(loc)
    await db.flush()
    return loc


async def _make_order(
    db: AsyncSession, tenant: Tenant, admin_user: User, location: Location,
    *, quantity: int = 2, price: int = 10500, status: str = "completed",
) -> Order:
    category = Category(tenant_id=tenant.id, name="Wholesale", display_order=1)
    db.add(category)
    await db.flush()
    item = MenuItem(
        tenant_id=tenant.id, category_id=category.id, name="Croissant Box", price=price
    )
    db.add(item)
    await db.flush()

    order = Order(
        tenant_id=tenant.id,
        order_number="W-0001",
        order_type="takeaway",
        status=status,
        payment_status="paid",
        subtotal=price * quantity,
        tax_amount=0,
        discount_amount=0,
        total=price * quantity,
        created_by=admin_user.id,
        location_id=location.id,
        customer_name="Gulf Hotels LLC",
        customer_phone="+971500000000",
    )
    db.add(order)
    await db.flush()
    db.add(
        OrderItem(
            tenant_id=tenant.id, order_id=order.id, menu_item_id=item.id,
            name="Croissant Box", quantity=quantity, unit_price=price,
            total=price * quantity,
        )
    )
    await db.flush()
    return order


@pytest.mark.asyncio
class TestTaxInvoiceDocument:
    async def test_carries_the_legal_identity_from_the_location(
        self, db: AsyncSession, tenant: Tenant, admin_user: User,
        wholesale_site: Location, vat_config: RestaurantConfig,
    ):
        order = await _make_order(db, tenant, admin_user, wholesale_site)
        invoice = await tax_invoice_service.get_tax_invoice(db, tenant.id, order.id)

        assert invoice.document_title == "TAX INVOICE"
        assert invoice.supplier.name == "FZ LLC"
        assert invoice.supplier.trn == "100123456700003"
        assert invoice.supplier.city == "Dubai"
        assert invoice.currency == "AED"
        assert invoice.invoice_number.startswith("FZW-")

    async def test_vat_is_split_out_not_added_on(
        self, db: AsyncSession, tenant: Tenant, admin_user: User,
        wholesale_site: Location, vat_config: RestaurantConfig,
    ):
        # 2 x 105.00 inclusive = 210.00 gross -> 200.00 net + 10.00 VAT
        order = await _make_order(db, tenant, admin_user, wholesale_site)
        invoice = await tax_invoice_service.get_tax_invoice(db, tenant.id, order.id)

        assert invoice.prices_include_vat is True
        assert invoice.subtotal_net_minor == 20000
        assert invoice.vat_total_minor == 1000
        assert invoice.total_gross_minor == 21000
        assert invoice.total_gross_minor == order.total

    async def test_line_totals_reconcile_to_the_invoice_total(
        self, db: AsyncSession, tenant: Tenant, admin_user: User,
        wholesale_site: Location, vat_config: RestaurantConfig,
    ):
        order = await _make_order(db, tenant, admin_user, wholesale_site, quantity=3,
                                  price=3333)
        invoice = await tax_invoice_service.get_tax_invoice(db, tenant.id, order.id)

        assert sum(line.line_net_minor for line in invoice.lines) == invoice.subtotal_net_minor
        assert sum(line.vat_amount_minor for line in invoice.lines) == invoice.vat_total_minor
        assert sum(line.line_gross_minor for line in invoice.lines) == order.total

    async def test_recipient_is_captured_for_a_b2b_sale(
        self, db: AsyncSession, tenant: Tenant, admin_user: User,
        wholesale_site: Location, vat_config: RestaurantConfig,
    ):
        order = await _make_order(db, tenant, admin_user, wholesale_site)
        invoice = await tax_invoice_service.get_tax_invoice(db, tenant.id, order.id)
        assert invoice.recipient is not None
        assert invoice.recipient.name == "Gulf Hotels LLC"

    async def test_a_voided_order_is_refused(
        self, db: AsyncSession, tenant: Tenant, admin_user: User,
        wholesale_site: Location, vat_config: RestaurantConfig,
    ):
        order = await _make_order(
            db, tenant, admin_user, wholesale_site, status="voided"
        )
        with pytest.raises(TaxInvoiceError, match="voided"):
            await tax_invoice_service.get_tax_invoice(db, tenant.id, order.id)

    async def test_another_tenant_cannot_read_the_invoice(
        self, db: AsyncSession, tenant: Tenant, admin_user: User,
        wholesale_site: Location, vat_config: RestaurantConfig,
    ):
        import uuid as _uuid

        order = await _make_order(db, tenant, admin_user, wholesale_site)
        other_id = _uuid.uuid4()
        other = Tenant(
            id=other_id, tenant_id=other_id, name="Other", slug="other-tax",
            is_active=True,
        )
        db.add(other)
        await db.flush()
        with pytest.raises(TaxInvoiceError, match="not found"):
            await tax_invoice_service.get_tax_invoice(db, other_id, order.id)

    async def test_falls_back_to_the_tenant_name_without_a_location(
        self, db: AsyncSession, tenant: Tenant, admin_user: User,
        wholesale_site: Location, vat_config: RestaurantConfig,
    ):
        """CORRECTED 2026-08-27. This test used to assert the F31 defect.

        It asserted that a tenant which HAS a registered site with a TRN
        (`wholesale_site`, `is_default=True`) issues a tax invoice carrying
        neither the site's legal name nor its TRN, merely because the order row
        had no `location_id`. That is not a fallback, it is an invalid UAE tax
        invoice, and it was the state of every sale the POS had ever taken.

        Same shape as `test_p1a_features` in the F19 post-mortem: a test written
        from the code, after the code, asserting whatever the code happened to
        do.

        The genuine "nothing configured at all" case -- no locations, so no TRN
        exists anywhere to put on the document -- is a different scenario and is
        covered by `test_tenant_with_no_locations_gets_the_pre_locations_invoice`
        in `test_sale_attribution.py`.
        """
        order = await _make_order(db, tenant, admin_user, wholesale_site)
        order.location_id = None
        await db.flush()

        invoice = await tax_invoice_service.get_tax_invoice(db, tenant.id, order.id)
        assert invoice.supplier.name == "FZ LLC", (
            "the registered legal name of the default site, not the tenant's "
            "display name"
        )
        assert invoice.supplier.trn == "100123456700003", (
            "a business that holds a TRN must show it on its tax invoices"
        )
        assert invoice.invoice_number.startswith("FZW-")
