"""Suppliers, purchase orders, goods receiving.

The invariants that have to hold or the module is not trustworthy:

  * a purchase-order total is always the sum of its lines plus VAT on top,
    and no value is ever multiplied or divided by 100 on the way through
  * received goods land at the order's OWN location, never anywhere else
  * status is derived from the quantities, so it can never claim "received"
    while something is still owed
  * every receipt writes a stock movement; a balance never changes silently
  * an in-house produced ingredient can never be bought from a supplier, and
    its cost is never overwritten by a purchase price

⚠️ These tests are a regression net, NOT the verification. They run on SQLite
and they were written by whoever wrote the code, which is exactly how a 100x
unit error survived a green suite on 2026-08-26. The real check is
`app/scripts/verify_procurement.py`, which runs against the live API and
sanity-checks magnitudes.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Ingredient, InventoryTransaction, Recipe
from app.models.location import Location, LocationStock
from app.models.procurement import Supplier
from app.models.tenant import Tenant
from app.services import purchase_order_service, stock_service, supplier_service
from app.services.supplier_service import ProcurementError

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def store(db: AsyncSession, tenant: Tenant) -> Location:
    loc = Location(
        tenant_id=tenant.id,
        name="Production Kitchen",
        code="PROD",
        location_type="production",
        is_default=True,
    )
    db.add(loc)
    await db.flush()
    return loc


@pytest_asyncio.fixture
async def second_store(db: AsyncSession, tenant: Tenant) -> Location:
    loc = Location(
        tenant_id=tenant.id,
        name="Delivery Kitchen",
        code="DEL",
        location_type="delivery",
    )
    db.add(loc)
    await db.flush()
    return loc


@pytest_asyncio.fixture
async def flour(db: AsyncSession, tenant: Tenant) -> Ingredient:
    # 400 = 4.00 AED per kg. MINOR UNITS, matching the module's convention.
    ing = Ingredient(
        tenant_id=tenant.id, name="Flour", unit="kg", cost_per_unit=Decimal("400")
    )
    db.add(ing)
    await db.flush()
    return ing


@pytest_asyncio.fixture
async def butter(db: AsyncSession, tenant: Tenant) -> Ingredient:
    ing = Ingredient(
        tenant_id=tenant.id, name="Butter", unit="kg", cost_per_unit=Decimal("1800")
    )
    db.add(ing)
    await db.flush()
    return ing


@pytest_asyncio.fixture
async def dough(db: AsyncSession, tenant: Tenant) -> Ingredient:
    """An in-house sub-recipe output, not something anyone sells us."""
    ing = Ingredient(
        tenant_id=tenant.id,
        name="Croissant Dough",
        unit="kg",
        cost_per_unit=Decimal("735"),
        is_produced=True,
    )
    db.add(ing)
    await db.flush()
    return ing


@pytest_asyncio.fixture
async def supplier(db: AsyncSession, tenant: Tenant) -> Supplier:
    return await supplier_service.create_supplier(
        db,
        tenant.id,
        {
            "name": "Al Maya Trading",
            "code": "almaya",
            "email": "orders@almaya.example",
            "lead_time_days": 2,
        },
    )


async def _order(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    lines: list[dict],
    tax_bps: int = 500,
):
    return await purchase_order_service.create_purchase_order(
        db,
        tenant_id=tenant.id,
        supplier_id=supplier.id,
        location_id=store.id,
        lines=lines,
        tax_bps=tax_bps,
    )


# ---------------------------------------------------------------------------
# SUPPLIERS
# ---------------------------------------------------------------------------


async def test_supplier_code_is_uppercased_and_unique(
    db: AsyncSession, tenant: Tenant, supplier: Supplier
):
    assert supplier.code == "ALMAYA"
    with pytest.raises(ProcurementError, match="already exists"):
        await supplier_service.create_supplier(
            db, tenant.id, {"name": "Someone else", "code": "almaya"}
        )


async def test_supplier_without_a_code_is_refused(db: AsyncSession, tenant: Tenant):
    with pytest.raises(ProcurementError, match="short code"):
        await supplier_service.create_supplier(db, tenant.id, {"name": "X", "code": " "})


async def test_deactivating_keeps_the_supplier_and_its_history(
    db: AsyncSession, tenant: Tenant, supplier: Supplier
):
    await supplier_service.deactivate_supplier(db, tenant.id, supplier.id)
    assert supplier.is_active is False
    # Still findable, because the purchase history hangs off it.
    assert (await supplier_service.get_supplier(db, tenant.id, supplier.id)) is supplier
    assert supplier not in await supplier_service.list_suppliers(db, tenant.id)


async def test_a_produced_ingredient_cannot_be_bought(
    db: AsyncSession, tenant: Tenant, supplier: Supplier, dough: Ingredient
):
    with pytest.raises(ProcurementError, match="made in-house"):
        await supplier_service.upsert_supplier_item(
            db, tenant.id, supplier.id, {"ingredient_id": dough.id}
        )


async def test_catalogue_upserts_instead_of_erroring(
    db: AsyncSession, tenant: Tenant, supplier: Supplier, flour: Ingredient
):
    first = await supplier_service.upsert_supplier_item(
        db,
        tenant.id,
        supplier.id,
        {"ingredient_id": flour.id, "last_price_minor": Decimal("450")},
    )
    second = await supplier_service.upsert_supplier_item(
        db,
        tenant.id,
        supplier.id,
        {"ingredient_id": flour.id, "last_price_minor": Decimal("470")},
    )
    assert first.id == second.id
    assert Decimal(str(second.last_price_minor)) == Decimal("470")


async def test_only_one_preferred_supplier_per_ingredient(
    db: AsyncSession, tenant: Tenant, supplier: Supplier, flour: Ingredient
):
    other = await supplier_service.create_supplier(
        db, tenant.id, {"name": "Second Source", "code": "SEC"}
    )
    first = await supplier_service.upsert_supplier_item(
        db,
        tenant.id,
        supplier.id,
        {"ingredient_id": flour.id, "last_price_minor": Decimal("450"), "is_preferred": True},
    )
    second = await supplier_service.upsert_supplier_item(
        db,
        tenant.id,
        other.id,
        {"ingredient_id": flour.id, "last_price_minor": Decimal("900"), "is_preferred": True},
    )
    await db.refresh(first)
    assert second.is_preferred is True
    assert first.is_preferred is False

    # The preferred flag wins over the cheaper price -- a human settled it.
    chosen = await supplier_service.preferred_supplier_for(db, tenant.id, flour.id)
    assert chosen is not None and chosen.id == second.id


async def test_cheapest_wins_when_nobody_is_preferred(
    db: AsyncSession, tenant: Tenant, supplier: Supplier, flour: Ingredient
):
    other = await supplier_service.create_supplier(
        db, tenant.id, {"name": "Second Source", "code": "SEC"}
    )
    await supplier_service.upsert_supplier_item(
        db, tenant.id, supplier.id, {"ingredient_id": flour.id, "last_price_minor": Decimal("900")}
    )
    cheap = await supplier_service.upsert_supplier_item(
        db, tenant.id, other.id, {"ingredient_id": flour.id, "last_price_minor": Decimal("450")}
    )
    chosen = await supplier_service.preferred_supplier_for(db, tenant.id, flour.id)
    assert chosen is not None and chosen.id == cheap.id


# ---------------------------------------------------------------------------
# PURCHASE ORDER ARITHMETIC
# ---------------------------------------------------------------------------


async def test_totals_are_the_sum_of_the_lines_with_vat_added_on_top(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    flour: Ingredient,
    butter: Ingredient,
):
    po = await _order(
        db,
        tenant,
        supplier,
        store,
        [
            {"ingredient_id": flour.id, "quantity_ordered": Decimal("10")},
            {
                "ingredient_id": butter.id,
                "quantity_ordered": Decimal("2"),
                "unit_price_minor": Decimal("2000"),
            },
        ],
    )
    # 10 x 400 = 4000, 2 x 2000 = 4000, subtotal 8000 minor = 80.00 AED.
    assert Decimal(str(po.subtotal_minor)) == Decimal("8000.00")
    # 5% ADDED, because a supplier quotes net. Not backed out.
    assert Decimal(str(po.tax_minor)) == Decimal("400.00")
    assert Decimal(str(po.total_minor)) == Decimal("8400.00")
    # Magnitude: 12 units of flour and butter costs 84 AED, not 8,400.
    assert Decimal("10") < Decimal(str(po.total_minor)) / 100 < Decimal("1000")


async def test_price_falls_back_to_the_last_paid_price_then_the_ingredient_cost(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    flour: Ingredient,
    butter: Ingredient,
):
    await supplier_service.upsert_supplier_item(
        db,
        tenant.id,
        supplier.id,
        {"ingredient_id": flour.id, "last_price_minor": Decimal("450")},
    )
    po = await _order(
        db,
        tenant,
        supplier,
        store,
        [
            {"ingredient_id": flour.id, "quantity_ordered": Decimal("1")},
            {"ingredient_id": butter.id, "quantity_ordered": Decimal("1")},
        ],
        tax_bps=0,
    )
    prices = {i.ingredient_id: Decimal(str(i.unit_price_minor)) for i in po.items}
    assert prices[flour.id] == Decimal("450.00")  # the supplier's price
    assert prices[butter.id] == Decimal("1800.00")  # the ingredient master's


async def test_an_ingredient_cannot_appear_twice_on_one_order(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    flour: Ingredient,
):
    with pytest.raises(ProcurementError, match="twice"):
        await _order(
            db,
            tenant,
            supplier,
            store,
            [
                {"ingredient_id": flour.id, "quantity_ordered": Decimal("1")},
                {"ingredient_id": flour.id, "quantity_ordered": Decimal("2")},
            ],
        )


async def test_a_produced_ingredient_cannot_be_ordered(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    dough: Ingredient,
):
    with pytest.raises(ProcurementError, match="produced in-house"):
        await _order(
            db, tenant, supplier, store, [{"ingredient_id": dough.id, "quantity_ordered": Decimal("1")}]
        )


async def test_an_empty_order_is_refused(
    db: AsyncSession, tenant: Tenant, supplier: Supplier, store: Location
):
    with pytest.raises(ProcurementError, match="at least one item"):
        await _order(db, tenant, supplier, store, [])


# ---------------------------------------------------------------------------
# LIFECYCLE
# ---------------------------------------------------------------------------


async def test_a_sent_order_cannot_be_edited(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    flour: Ingredient,
):
    po = await _order(
        db, tenant, supplier, store, [{"ingredient_id": flour.id, "quantity_ordered": Decimal("5")}]
    )
    await purchase_order_service.update_purchase_order(
        db, tenant_id=tenant.id, po_id=po.id, data={"notes": "fine while draft"}
    )
    await purchase_order_service.mark_sent(db, tenant_id=tenant.id, po_id=po.id)
    with pytest.raises(ProcurementError, match="Only a draft"):
        await purchase_order_service.update_purchase_order(
            db, tenant_id=tenant.id, po_id=po.id, data={"notes": "too late"}
        )


async def test_goods_cannot_be_received_before_the_order_is_sent(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    flour: Ingredient,
):
    po = await _order(
        db, tenant, supplier, store, [{"ingredient_id": flour.id, "quantity_ordered": Decimal("5")}]
    )
    with pytest.raises(ProcurementError, match="only be received against a sent order"):
        await purchase_order_service.receive_goods(
            db,
            tenant_id=tenant.id,
            po_id=po.id,
            lines=[
                {
                    "purchase_order_item_id": po.items[0].id,
                    "quantity_received": Decimal("1"),
                }
            ],
        )


async def test_a_failed_email_does_not_undo_the_send(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    flour: Ingredient,
):
    """The buyer's intent survives a dead mail server; the failure is recorded."""
    po = await _order(
        db, tenant, supplier, store, [{"ingredient_id": flour.id, "quantity_ordered": Decimal("5")}]
    )
    po = await purchase_order_service.mark_sent(
        db,
        tenant_id=tenant.id,
        po_id=po.id,
        sent_to_email="orders@almaya.example",
        email_delivered=False,
        email_error="SMTPConnectError: connection refused",
    )
    assert po.status == "sent"
    assert po.email_send_count == 0
    assert "connection refused" in po.last_email_error


# ---------------------------------------------------------------------------
# RECEIVING
# ---------------------------------------------------------------------------


async def _sent_order(db, tenant, supplier, store, ingredient, quantity="10"):
    po = await _order(
        db,
        tenant,
        supplier,
        store,
        [{"ingredient_id": ingredient.id, "quantity_ordered": Decimal(quantity)}],
        tax_bps=0,
    )
    return await purchase_order_service.mark_sent(db, tenant_id=tenant.id, po_id=po.id)


async def test_partial_receipt_leaves_the_order_partially_received(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    flour: Ingredient,
):
    po = await _sent_order(db, tenant, supplier, store, flour)
    po, receipt = await purchase_order_service.receive_goods(
        db,
        tenant_id=tenant.id,
        po_id=po.id,
        lines=[
            {"purchase_order_item_id": po.items[0].id, "quantity_received": Decimal("6")}
        ],
        document_reference="DN-1",
    )
    assert po.status == "partially_received"
    assert Decimal(str(po.items[0].quantity_received)) == Decimal("6.000")
    assert po.fully_received_at is None
    assert receipt.receipt_number.startswith("GRN-")

    po, _ = await purchase_order_service.receive_goods(
        db,
        tenant_id=tenant.id,
        po_id=po.id,
        lines=[
            {"purchase_order_item_id": po.items[0].id, "quantity_received": Decimal("4")}
        ],
    )
    assert po.status == "received"
    assert po.fully_received_at is not None
    assert len(po.receipts) == 2


async def test_received_stock_lands_only_at_the_orders_own_location(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    second_store: Location,
    flour: Ingredient,
):
    po = await _sent_order(db, tenant, supplier, store, flour)
    await purchase_order_service.receive_goods(
        db,
        tenant_id=tenant.id,
        po_id=po.id,
        lines=[
            {"purchase_order_item_id": po.items[0].id, "quantity_received": Decimal("10")}
        ],
    )

    here = (
        await db.execute(
            select(LocationStock).where(
                LocationStock.location_id == store.id,
                LocationStock.ingredient_id == flour.id,
            )
        )
    ).scalar_one()
    assert Decimal(str(here.quantity)) == Decimal("10.000")

    there = (
        await db.execute(
            select(LocationStock).where(
                LocationStock.location_id == second_store.id,
                LocationStock.ingredient_id == flour.id,
            )
        )
    ).scalar_one_or_none()
    assert there is None


async def test_every_receipt_writes_a_stock_movement(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    flour: Ingredient,
):
    """A balance must never change without a movement that explains it."""
    po = await _sent_order(db, tenant, supplier, store, flour)
    await purchase_order_service.receive_goods(
        db,
        tenant_id=tenant.id,
        po_id=po.id,
        lines=[
            {"purchase_order_item_id": po.items[0].id, "quantity_received": Decimal("7")}
        ],
    )
    movements = list(
        (
            await db.execute(
                select(InventoryTransaction).where(
                    InventoryTransaction.ingredient_id == flour.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(movements) == 1
    movement = movements[0]
    assert movement.transaction_type == "purchase"
    assert movement.location_id == store.id
    assert Decimal(str(movement.quantity)) == Decimal("7.000")
    assert Decimal(str(movement.balance_after)) == Decimal("7.000")
    assert movement.reference_number == po.po_number


async def test_over_delivery_is_accepted_and_stays_visible(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    flour: Ingredient,
):
    """Stock that physically arrived must be booked, or the stock figure lies."""
    po = await _sent_order(db, tenant, supplier, store, flour, quantity="10")
    po, _ = await purchase_order_service.receive_goods(
        db,
        tenant_id=tenant.id,
        po_id=po.id,
        lines=[
            {"purchase_order_item_id": po.items[0].id, "quantity_received": Decimal("12")}
        ],
    )
    assert po.status == "received"
    assert Decimal(str(po.items[0].quantity_received)) == Decimal("12.000")
    assert Decimal(str(po.items[0].quantity_ordered)) == Decimal("10.000")


async def test_a_zero_quantity_receipt_is_refused(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    flour: Ingredient,
):
    po = await _sent_order(db, tenant, supplier, store, flour)
    with pytest.raises(ProcurementError, match="greater than zero"):
        await purchase_order_service.receive_goods(
            db,
            tenant_id=tenant.id,
            po_id=po.id,
            lines=[
                {
                    "purchase_order_item_id": po.items[0].id,
                    "quantity_received": Decimal("0"),
                }
            ],
        )


async def test_a_line_from_another_order_is_refused(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    flour: Ingredient,
    butter: Ingredient,
):
    first = await _sent_order(db, tenant, supplier, store, flour)
    second = await _sent_order(db, tenant, supplier, store, butter)
    with pytest.raises(ProcurementError, match="does not belong"):
        await purchase_order_service.receive_goods(
            db,
            tenant_id=tenant.id,
            po_id=first.id,
            lines=[
                {
                    "purchase_order_item_id": second.items[0].id,
                    "quantity_received": Decimal("1"),
                }
            ],
        )


async def test_receiving_updates_the_ingredient_cost_to_what_was_actually_paid(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    flour: Ingredient,
):
    po = await _sent_order(db, tenant, supplier, store, flour)
    await purchase_order_service.receive_goods(
        db,
        tenant_id=tenant.id,
        po_id=po.id,
        lines=[
            {
                "purchase_order_item_id": po.items[0].id,
                "quantity_received": Decimal("10"),
                "unit_price_minor": Decimal("520"),
            }
        ],
    )
    await db.refresh(flour)
    assert Decimal(str(flour.cost_per_unit)) == Decimal("520.00")

    catalogue = await supplier_service.preferred_supplier_for(db, tenant.id, flour.id)
    assert catalogue is not None
    assert Decimal(str(catalogue.last_price_minor)) == Decimal("520.00")
    assert catalogue.last_purchased_at is not None


async def test_a_purchase_never_overwrites_a_produced_ingredients_rolled_up_cost(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    dough: Ingredient,
):
    """The guard that stops a purchase corrupting every recipe that uses it.

    A produced ingredient's cost is owned by
    `recipe_service.sync_produced_ingredient_cost`. Nothing on the buying side
    may touch it. Ordering one is blocked outright, so the guard is reached
    only through a direct call -- which is exactly why it is tested directly.
    """
    before = Decimal(str(dough.cost_per_unit))
    await purchase_order_service._apply_purchase_price(
        db, tenant.id, supplier.id, dough.id, Decimal("9999")
    )
    await db.refresh(dough)
    assert Decimal(str(dough.cost_per_unit)) == before


async def test_a_received_order_refuses_further_receipts_and_cancellation(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    flour: Ingredient,
):
    po = await _sent_order(db, tenant, supplier, store, flour)
    po, _ = await purchase_order_service.receive_goods(
        db,
        tenant_id=tenant.id,
        po_id=po.id,
        lines=[
            {"purchase_order_item_id": po.items[0].id, "quantity_received": Decimal("10")}
        ],
    )
    with pytest.raises(ProcurementError, match="only be received against a sent order"):
        await purchase_order_service.receive_goods(
            db,
            tenant_id=tenant.id,
            po_id=po.id,
            lines=[
                {
                    "purchase_order_item_id": po.items[0].id,
                    "quantity_received": Decimal("1"),
                }
            ],
        )
    with pytest.raises(ProcurementError, match="cannot be cancelled"):
        await purchase_order_service.cancel_purchase_order(
            db, tenant_id=tenant.id, po_id=po.id
        )


async def test_cancelling_a_partially_received_order_keeps_the_stock(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    flour: Ingredient,
):
    """Cancelling paperwork does not un-deliver goods that arrived."""
    po = await _sent_order(db, tenant, supplier, store, flour)
    await purchase_order_service.receive_goods(
        db,
        tenant_id=tenant.id,
        po_id=po.id,
        lines=[
            {"purchase_order_item_id": po.items[0].id, "quantity_received": Decimal("3")}
        ],
    )
    po = await purchase_order_service.cancel_purchase_order(
        db, tenant_id=tenant.id, po_id=po.id
    )
    assert po.status == "cancelled"

    row = (
        await db.execute(
            select(LocationStock).where(
                LocationStock.location_id == store.id,
                LocationStock.ingredient_id == flour.id,
            )
        )
    ).scalar_one()
    assert Decimal(str(row.quantity)) == Decimal("3.000")


# ---------------------------------------------------------------------------
# REPORTING
# ---------------------------------------------------------------------------


async def test_outstanding_quantities_ignore_what_has_already_arrived(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    flour: Ingredient,
):
    po = await _sent_order(db, tenant, supplier, store, flour, quantity="10")
    outstanding = await purchase_order_service.outstanding_quantities(db, tenant.id)
    assert outstanding[flour.id] == Decimal("10.000")

    await purchase_order_service.receive_goods(
        db,
        tenant_id=tenant.id,
        po_id=po.id,
        lines=[
            {"purchase_order_item_id": po.items[0].id, "quantity_received": Decimal("4")}
        ],
    )
    outstanding = await purchase_order_service.outstanding_quantities(db, tenant.id)
    assert outstanding[flour.id] == Decimal("6.000")


async def test_a_draft_order_is_not_counted_as_spend(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    flour: Ingredient,
):
    await _order(
        db, tenant, supplier, store, [{"ingredient_id": flour.id, "quantity_ordered": Decimal("5")}]
    )
    totals = await supplier_service.supplier_spend_totals(db, tenant.id)
    assert supplier.id not in totals

    po = await _sent_order(db, tenant, supplier, store, flour, quantity="5")
    totals = await supplier_service.supplier_spend_totals(db, tenant.id)
    assert totals[supplier.id]["order_count"] == 1
    assert totals[supplier.id]["total_spend_minor"] == Decimal(str(po.total_minor))


async def test_purchase_history_lists_the_orders_placed_with_a_supplier(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    flour: Ingredient,
):
    po = await _sent_order(db, tenant, supplier, store, flour)
    history = await supplier_service.supplier_purchase_history(db, tenant.id, supplier.id)
    assert [row["po_number"] for row in history] == [po.po_number]
    assert history[0]["location_name"] == store.name


async def test_receiving_history_records_each_delivery_separately(
    db: AsyncSession,
    tenant: Tenant,
    supplier: Supplier,
    store: Location,
    flour: Ingredient,
):
    po = await _sent_order(db, tenant, supplier, store, flour)
    for quantity, reference in ((Decimal("4"), "DN-1"), (Decimal("6"), "DN-2")):
        await purchase_order_service.receive_goods(
            db,
            tenant_id=tenant.id,
            po_id=po.id,
            lines=[
                {
                    "purchase_order_item_id": po.items[0].id,
                    "quantity_received": quantity,
                }
            ],
            document_reference=reference,
        )
    history = await purchase_order_service.receiving_history(db, tenant.id)
    assert {row["document_reference"] for row in history} == {"DN-1", "DN-2"}
    assert all(row["po_number"] == po.po_number for row in history)


async def test_tenant_isolation(db: AsyncSession, tenant: Tenant, supplier: Supplier):
    # `Tenant.tenant_id` points at itself -- see conftest's own tenant fixture.
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
    with pytest.raises(ProcurementError, match="No such supplier"):
        await supplier_service.get_supplier(db, other.id, supplier.id)
