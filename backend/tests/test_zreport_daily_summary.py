"""The Z-Report as the owner's one daily summary (Danny's UAT D-60).

Beside sales and cash vs card, the Z-Report now says how much stock the day
used, what was left at the end of it, and where the cash stands. Every date
here is a Faisalabad day (Asia/Karachi, UTC+5), so a movement at 01:05 local
belongs to that local day even though it is the previous day in UTC.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Expense
from app.models.inventory import Ingredient, InventoryTransaction, Recipe, RecipeItem
from app.models.location import Location, LocationStock
from app.models.menu import Category, MenuItem
from app.models.order import Order, OrderItem
from app.models.payment import CashDrawerSession, Payment, PaymentMethod
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.models.user import User
from app.services import production_service, stock_service, zreport_service

pytestmark = pytest.mark.asyncio

DAY_24 = date(2026, 9, 24)
DAY_25 = date(2026, 9, 25)


def utc(y, mo, d, h, mi=0) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def karachi(db: AsyncSession, tenant: Tenant) -> None:
    db.add(RestaurantConfig(tenant_id=tenant.id, currency="PKR", timezone="Asia/Karachi"))
    await db.flush()


@pytest_asyncio.fixture
async def site(db: AsyncSession, tenant: Tenant) -> Location:
    loc = Location(
        tenant_id=tenant.id, name="Restaurant", code="MAIN", location_type="retail",
        invoice_format="thermal_ticket", is_default=True,
    )
    db.add(loc)
    await db.flush()
    return loc


@pytest_asyncio.fixture
async def chicken(db: AsyncSession, tenant: Tenant) -> Ingredient:
    ing = Ingredient(tenant_id=tenant.id, name="Chicken", unit="kg", cost_per_unit=Decimal("1200"))
    db.add(ing)
    await db.flush()
    return ing


async def _dated_move(db, tenant, ingredient, delta, kind, at, site, **kw) -> InventoryTransaction:
    txn = await stock_service.move_stock(
        db, tenant_id=tenant.id, ingredient_id=ingredient.id, quantity_delta=Decimal(delta),
        transaction_type=kind, location_id=site.id, **kw,
    )
    txn.transaction_date = at
    await db.flush()
    return txn


async def _sell_karahi(db, tenant, user, chicken, *, portions: int, at: datetime) -> Order:
    """A real sale: menu item + recipe + order, deducted by consume_for_order."""
    category = Category(tenant_id=tenant.id, name="Karahi", display_order=1)
    db.add(category)
    await db.flush()
    item = MenuItem(tenant_id=tenant.id, category_id=category.id, name="Chicken Karahi", price=180000)
    db.add(item)
    await db.flush()
    recipe = Recipe(tenant_id=tenant.id, menu_item_id=item.id, yield_servings=Decimal("1"))
    db.add(recipe)
    await db.flush()
    # 0.25 kg plus 10% waste = 0.275 kg a portion.
    db.add(RecipeItem(
        tenant_id=tenant.id, recipe_id=recipe.id, ingredient_id=chicken.id,
        quantity=Decimal("0.25"), unit="kg", waste_factor=Decimal("10"),
    ))
    order = Order(
        tenant_id=tenant.id, order_number="260925-001", order_type="dine_in", status="completed",
        payment_status="paid", subtotal=180000 * portions, tax_amount=0, discount_amount=0,
        total=180000 * portions, created_by=user.id, created_at=at,
    )
    db.add(order)
    await db.flush()
    db.add(OrderItem(
        tenant_id=tenant.id, order_id=order.id, menu_item_id=item.id, name="Chicken Karahi",
        quantity=portions, unit_price=180000, total=180000 * portions,
    ))
    await db.flush()
    await production_service.consume_for_order(db, tenant_id=tenant.id, order_id=order.id)
    await db.execute(
        update(InventoryTransaction)
        .where(InventoryTransaction.order_id == order.id)
        .values(transaction_date=at)
    )
    await db.flush()
    return order


# ---------------------------------------------------------------------------
# Inventory used
# ---------------------------------------------------------------------------


async def test_a_sale_shows_in_inventory_used_at_the_movement_cost(
    db, tenant, admin_user, karachi, site, chicken,
):
    await _dated_move(db, tenant, chicken, "10", "purchase", utc(2026, 9, 24, 5), site)
    # 01:05 on the 25th in Faisalabad, 20:05 on the 24th in UTC.
    await _sell_karahi(db, tenant, admin_user, chicken, portions=2, at=utc(2026, 9, 24, 20, 5))
    await _dated_move(
        db, tenant, chicken, "-1", "adjustment", utc(2026, 9, 25, 10), site,
        notes="dropped tray",
    )
    # The price moves AFTER the sale; the report must keep the sale's cost.
    chicken.cost_per_unit = Decimal("9999")
    await db.flush()

    z25 = await zreport_service.generate_zreport(db, tenant.id, DAY_25, "test")
    used = z25["inventory_used"]
    assert len(used["rows"]) == 1
    row = used["rows"][0]
    assert row["ingredient_name"] == "Chicken"
    assert row["unit"] == "kg"
    assert row["sold_quantity"] == Decimal("0.550")  # 2 x 0.25 x 1.10
    assert row["sold_cost"] == Decimal("660.00")  # 0.55 x 1200 minor units
    assert row["adjustment_quantity"] == Decimal("-1.000")
    assert row["adjustment_cost"] == Decimal("-1200.00")
    assert row["production_quantity"] == Decimal("0.000")
    assert row["waste_quantity"] == Decimal("0.000")
    assert row["costed_at_current_price"] is False
    assert used["total_sold_cost"] == Decimal("660.00")
    assert used["total_cost_of_goods_used"] == Decimal("660.00")

    # The purchase on the 24th is not usage, and the sale is not on the 24th.
    z24 = await zreport_service.generate_zreport(db, tenant.id, DAY_24, "test")
    assert z24["inventory_used"]["rows"] == []


async def test_inventory_used_is_sorted_by_cost_and_falls_back_to_current_price(
    db, tenant, karachi, site, chicken,
):
    salt = Ingredient(tenant_id=tenant.id, name="Salt", unit="kg", cost_per_unit=Decimal("0"))
    db.add(salt)
    await db.flush()
    await _dated_move(db, tenant, salt, "5", "purchase", utc(2026, 9, 25, 5), site)
    await _dated_move(db, tenant, chicken, "5", "purchase", utc(2026, 9, 25, 5), site)
    await _dated_move(db, tenant, salt, "-2", "waste", utc(2026, 9, 25, 6), site)
    await _dated_move(db, tenant, chicken, "-1", "waste", utc(2026, 9, 25, 6), site)
    # Salt's waste was recorded at cost 0; it is priced at today's 50.
    salt.cost_per_unit = Decimal("50")
    await db.flush()

    used = (await zreport_service.generate_zreport(db, tenant.id, DAY_25, "t"))["inventory_used"]
    assert [r["ingredient_name"] for r in used["rows"]] == ["Chicken", "Salt"]
    salt_row = used["rows"][1]
    assert salt_row["waste_cost"] == Decimal("100.00")
    assert salt_row["costed_at_current_price"] is True
    assert used["total_waste_cost"] == Decimal("1300.00")
    assert used["total_cost_of_goods_used"] == Decimal("1300.00")


# ---------------------------------------------------------------------------
# Stock left
# ---------------------------------------------------------------------------


async def test_closing_stock_for_a_past_day_backs_out_later_movements(
    db, tenant, admin_user, karachi, site, chicken,
):
    retired = Ingredient(tenant_id=tenant.id, name="Karahi Base", unit="kg",
                         cost_per_unit=Decimal("400"), is_active=True)
    db.add(retired)
    await db.flush()
    await _dated_move(db, tenant, retired, "3", "purchase", utc(2026, 9, 24, 5), site)
    retired.is_active = False

    await _dated_move(db, tenant, chicken, "10", "purchase", utc(2026, 9, 24, 10), site)
    # Sold at 11:00 local on the 25th.
    await _sell_karahi(db, tenant, admin_user, chicken, portions=2, at=utc(2026, 9, 25, 6))
    stock_row = (await db.execute(
        select(LocationStock).where(LocationStock.ingredient_id == chicken.id)
    )).scalar_one()
    stock_row.reorder_point = Decimal("9.5")
    await db.flush()

    z24 = await zreport_service.generate_zreport(db, tenant.id, DAY_24, "t")
    z25 = await zreport_service.generate_zreport(db, tenant.id, DAY_25, "t")

    # The retired ingredient is skipped, as on the Stock screen.
    assert [r["ingredient_name"] for r in z24["stock_left"]["rows"]] == ["Chicken"]
    assert z24["stock_left"]["rows"][0]["closing_quantity"] == Decimal("10.000")
    assert z24["stock_left"]["rows"][0]["is_low"] is False
    assert z25["stock_left"]["rows"][0]["closing_quantity"] == Decimal("9.450")
    assert z25["stock_left"]["rows"][0]["is_low"] is True
    assert z25["stock_left"]["low_count"] == 1
    assert z25["stock_left"]["multiple_locations"] is False
    # Today is the live balance.
    assert Decimal(str(stock_row.quantity)) == Decimal("9.450")


async def test_stock_left_is_per_location_when_there_are_several(
    db, tenant, karachi, site, chicken,
):
    hub = Location(
        tenant_id=tenant.id, name="Delivery Hub", code="DEL", location_type="delivery",
        invoice_format="thermal_ticket",
    )
    db.add(hub)
    await db.flush()
    await _dated_move(db, tenant, chicken, "4", "purchase", utc(2026, 9, 24, 5), site)
    await _dated_move(db, tenant, chicken, "6", "purchase", utc(2026, 9, 24, 5), hub)
    await _dated_move(db, tenant, chicken, "-2", "transfer_out", utc(2026, 9, 25, 5), hub)

    left = (await zreport_service.generate_zreport(db, tenant.id, DAY_24, "t"))["stock_left"]
    assert left["multiple_locations"] is True
    by_site = {r["location_name"]: r["closing_quantity"] for r in left["rows"]}
    assert by_site == {"Delivery Hub": Decimal("6.000"), "Restaurant": Decimal("4.000")}


# ---------------------------------------------------------------------------
# Cash position
# ---------------------------------------------------------------------------


async def _cash_day(db, tenant, user) -> None:
    """One order paid 900 cash (1000 handed over, 100 change), 500 card,
    200 cash refunded; 300 of expenses paid in cash that day."""
    cash = PaymentMethod(tenant_id=tenant.id, code="cash", display_name="Cash")
    card = PaymentMethod(tenant_id=tenant.id, code="card", display_name="Card")
    db.add_all([cash, card])
    order = Order(
        tenant_id=tenant.id, order_number="260925-009", order_type="takeaway", status="completed",
        payment_status="paid", subtotal=1400, tax_amount=0, discount_amount=0, total=1400,
        created_by=user.id, created_at=utc(2026, 9, 25, 7),
    )
    db.add(order)
    await db.flush()
    paid = Payment(
        tenant_id=tenant.id, order_id=order.id, method_id=cash.id, kind="payment",
        status="completed", amount=900, tendered_amount=1000, change_amount=100,
        processed_by=user.id, created_at=utc(2026, 9, 25, 7, 5),
    )
    db.add(paid)
    await db.flush()
    db.add_all([
        Payment(
            tenant_id=tenant.id, order_id=order.id, method_id=card.id, kind="payment",
            status="completed", amount=500, change_amount=0, processed_by=user.id,
            created_at=utc(2026, 9, 25, 7, 6),
        ),
        Payment(
            tenant_id=tenant.id, order_id=order.id, method_id=cash.id, kind="refund",
            parent_payment_id=paid.id, status="completed", amount=200, change_amount=0,
            processed_by=user.id, created_at=utc(2026, 9, 25, 9),
        ),
        # Yesterday in Faisalabad (23:00 local on the 24th): not today's cash.
        Payment(
            tenant_id=tenant.id, order_id=order.id, method_id=cash.id, kind="payment",
            status="completed", amount=4444, change_amount=0, processed_by=user.id,
            created_at=utc(2026, 9, 24, 18),
        ),
        # Payment method is free text: both spellings are cash.
        Expense(
            tenant_id=tenant.id, expense_date=DAY_25, payee="Gas cylinder",
            amount_minor=Decimal("200"), status="paid", payment_method="Cash", paid_on=DAY_25,
        ),
        Expense(
            tenant_id=tenant.id, expense_date=DAY_25, payee="Ice",
            amount_minor=Decimal("100"), status="paid", payment_method="petty cash",
            paid_on=DAY_25,
        ),
        # Not cash, not paid, or paid another day: none of these count.
        Expense(
            tenant_id=tenant.id, expense_date=DAY_25, payee="Landlord",
            amount_minor=Decimal("700"), status="paid", payment_method="Bank transfer",
            paid_on=DAY_25,
        ),
        Expense(
            tenant_id=tenant.id, expense_date=DAY_25, payee="Plumber",
            amount_minor=Decimal("900"), status="unpaid", payment_method="cash",
        ),
        Expense(
            tenant_id=tenant.id, expense_date=DAY_24, payee="Milk",
            amount_minor=Decimal("50"), status="paid", payment_method="cash", paid_on=DAY_24,
        ),
    ])
    await db.flush()


async def test_cash_position_without_a_drawer_invents_no_float(db, tenant, admin_user, karachi):
    await _cash_day(db, tenant, admin_user)

    z = await zreport_service.generate_zreport(db, tenant.id, DAY_25, "t")
    cash = z["cash_position"]
    # Change was never part of `amount`, so nothing is subtracted for it.
    assert cash["cash_taken"] == 900
    assert cash["cash_refunds"] == 200
    assert cash["cash_paid_out"] == 300
    assert cash["cash_expenses"] == [
        {"payee": "Gas cylinder", "payment_method": "Cash", "amount": 200},
        {"payee": "Ice", "payment_method": "petty cash", "amount": 100},
    ]
    assert cash["net_cash"] == 400
    assert cash["drawer_opened"] is False
    assert cash["drawers"] == []
    # The same number as the report's own cash-vs-card breakdown.
    cash_method = next(pm for pm in z["by_payment_method"] if pm["method"] == "Cash")
    assert cash_method["gross_total"] == cash["cash_taken"]
    assert cash_method["refund_total"] == cash["cash_refunds"]


async def test_cash_position_with_a_drawer_shows_over_short(db, tenant, admin_user, karachi):
    await _cash_day(db, tenant, admin_user)
    db.add(CashDrawerSession(
        tenant_id=tenant.id, status="closed", opened_by=admin_user.id,
        opened_at=utc(2026, 9, 25, 4), opening_float=5000,
        closed_by=admin_user.id, closed_at=utc(2026, 9, 25, 17),
        closing_balance_counted=5350,
    ))
    await db.flush()

    cash = (await zreport_service.generate_zreport(db, tenant.id, DAY_25, "t"))["cash_position"]
    assert cash["drawer_opened"] is True
    [drawer] = cash["drawers"]
    assert drawer["opening_float"] == 5000
    assert drawer["cash_taken"] == 900
    assert drawer["cash_refunds"] == 200
    assert drawer["cash_paid_out"] == 300
    assert drawer["expected_in_drawer"] == 5400  # 5000 + 900 - 200 - 300
    assert drawer["counted_closing"] == 5350
    assert drawer["over_short"] == -50


# ---------------------------------------------------------------------------
# Through the route
# ---------------------------------------------------------------------------


class TestThroughTheApi:
    async def test_z_report_route_returns_the_daily_summary(
        self, client, admin_token, db, tenant, admin_user, karachi, site, chicken,
    ):
        await _dated_move(db, tenant, chicken, "10", "purchase", utc(2026, 9, 24, 5), site)
        await _sell_karahi(db, tenant, admin_user, chicken, portions=2, at=utc(2026, 9, 24, 20, 5))
        await _cash_day(db, tenant, admin_user)
        await db.commit()

        resp = await client.get(
            "/api/v1/reports/z-report?date=2026-09-25",
            headers={"Authorization": "Bearer " + admin_token},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        [row] = body["inventory_used"]["rows"]
        assert row["ingredient_name"] == "Chicken"
        assert row["sold_quantity"] == 0.55  # a JSON number, not a string
        assert row["sold_cost"] == 660.0
        assert body["inventory_used"]["total_cost_of_goods_used"] == 660.0

        [left] = body["stock_left"]["rows"]
        assert left["closing_quantity"] == 9.45
        assert left["location_name"] == "Restaurant"

        cash = body["cash_position"]
        assert cash["cash_taken"] == 900
        assert cash["net_cash"] == 400
        assert cash["drawer_opened"] is False
        assert cash["drawers"] == []
