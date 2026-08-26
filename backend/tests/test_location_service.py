"""Multi-location: stock, production, transfers, channel commission, profit.

These are the invariants that have to hold or the module is not trustworthy:

  * a balance can never change without a movement that explains it
  * stock leaves a location when sent and arrives only when received
  * a sale deducts from the location that sold it, and never twice
  * a tenant with no locations behaves exactly as it did before this existed
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Ingredient, InventoryTransaction, Recipe, RecipeItem
from app.models.location import Location, LocationStock, SalesChannel
from app.models.menu import Category, MenuItem
from app.models.order import Order, OrderItem
from app.models.tenant import Tenant
from app.models.user import User
from app.services import (
    location_service,
    production_service,
    stock_service,
    transfer_service,
)
from app.services.stock_service import StockError

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def production_site(db: AsyncSession, tenant: Tenant) -> Location:
    loc = Location(
        tenant_id=tenant.id,
        name="Production Kitchen",
        code="PROD",
        location_type="production",
        legal_name="FZ LLC",
        tax_registration_number="100123456700003",
        invoice_format="a4_tax_invoice",
        is_default=True,
    )
    db.add(loc)
    await db.flush()
    return loc


@pytest_asyncio.fixture
async def delivery_site(db: AsyncSession, tenant: Tenant) -> Location:
    loc = Location(
        tenant_id=tenant.id,
        name="Delivery Hub",
        code="DEL",
        location_type="delivery",
        invoice_format="thermal_ticket",
    )
    db.add(loc)
    await db.flush()
    return loc


@pytest_asyncio.fixture
async def flour(db: AsyncSession, tenant: Tenant) -> Ingredient:
    ing = Ingredient(
        tenant_id=tenant.id, name="Flour", unit="kg", cost_per_unit=Decimal("4.00")
    )
    db.add(ing)
    await db.flush()
    return ing


@pytest_asyncio.fixture
async def butter(db: AsyncSession, tenant: Tenant) -> Ingredient:
    ing = Ingredient(
        tenant_id=tenant.id, name="Butter", unit="kg", cost_per_unit=Decimal("20.00")
    )
    db.add(ing)
    await db.flush()
    return ing


@pytest_asyncio.fixture
async def dough(db: AsyncSession, tenant: Tenant) -> Ingredient:
    ing = Ingredient(
        tenant_id=tenant.id,
        name="Croissant Dough",
        unit="kg",
        cost_per_unit=Decimal("0"),
        is_produced=True,
    )
    db.add(ing)
    await db.flush()
    return ing


@pytest_asyncio.fixture
async def dough_recipe(
    db: AsyncSession, tenant: Tenant, flour: Ingredient, butter: Ingredient,
    dough: Ingredient,
) -> Recipe:
    """5 kg of dough from 4 kg flour (10% waste) + 1 kg butter."""
    recipe = Recipe(
        tenant_id=tenant.id,
        produces_ingredient_id=dough.id,
        yield_servings=Decimal("5"),
    )
    db.add(recipe)
    await db.flush()
    db.add_all(
        [
            RecipeItem(
                tenant_id=tenant.id, recipe_id=recipe.id, ingredient_id=flour.id,
                quantity=Decimal("4"), unit="kg", waste_factor=Decimal("10"),
            ),
            RecipeItem(
                tenant_id=tenant.id, recipe_id=recipe.id, ingredient_id=butter.id,
                quantity=Decimal("1"), unit="kg", waste_factor=Decimal("0"),
            ),
        ]
    )
    await db.flush()
    return recipe


# ---------------------------------------------------------------------------
# LOCATION RESOLUTION
# ---------------------------------------------------------------------------


class TestLocationResolution:
    async def test_default_location_is_used_when_none_given(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        delivery_site: Location,
    ):
        resolved = await stock_service.resolve_location(db, tenant.id, None)
        assert resolved.id == production_site.id

    async def test_ambiguous_without_a_default_is_refused_not_guessed(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        delivery_site: Location,
    ):
        production_site.is_default = False
        await db.flush()
        with pytest.raises(StockError, match="must be specified"):
            await stock_service.resolve_location(db, tenant.id, None)

    async def test_single_location_needs_no_default_flag(
        self, db: AsyncSession, tenant: Tenant, delivery_site: Location
    ):
        resolved = await stock_service.resolve_location(db, tenant.id, None)
        assert resolved.id == delivery_site.id

    async def test_another_tenants_location_is_invisible(
        self, db: AsyncSession, tenant: Tenant, production_site: Location
    ):
        # Tenant inherits BaseMixin, so it carries its own NOT NULL tenant_id
        # pointing at itself -- same shape as the conftest fixture.
        other_id = uuid.uuid4()
        other = Tenant(
            id=other_id, tenant_id=other_id, name="Other", slug="other-tenant",
            is_active=True,
        )
        db.add(other)
        await db.flush()
        with pytest.raises(StockError, match="No such location"):
            await stock_service.resolve_location(db, other.id, production_site.id)

    async def test_setting_a_new_default_clears_the_old_one(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        delivery_site: Location,
    ):
        await location_service.update_location(
            db, tenant.id, delivery_site.id, {"is_default": True}
        )
        await db.refresh(production_site)
        assert delivery_site.is_default is True
        assert production_site.is_default is False


# ---------------------------------------------------------------------------
# STOCK MOVEMENT
# ---------------------------------------------------------------------------


class TestStockMovement:
    async def test_movement_creates_row_and_logs_transaction(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        flour: Ingredient,
    ):
        await stock_service.move_stock(
            db, tenant_id=tenant.id, ingredient_id=flour.id,
            quantity_delta=Decimal("25"), transaction_type="purchase",
            location_id=production_site.id,
        )
        row = (
            await db.execute(
                select(LocationStock).where(
                    LocationStock.location_id == production_site.id,
                    LocationStock.ingredient_id == flour.id,
                )
            )
        ).scalar_one()
        assert row.quantity == Decimal("25.000")

        txn = (
            await db.execute(
                select(InventoryTransaction).where(
                    InventoryTransaction.ingredient_id == flour.id
                )
            )
        ).scalar_one()
        assert txn.location_id == production_site.id
        assert txn.balance_after == Decimal("25.000")

    async def test_balance_after_is_per_location_not_tenant_wide(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        delivery_site: Location, flour: Ingredient,
    ):
        await stock_service.move_stock(
            db, tenant_id=tenant.id, ingredient_id=flour.id,
            quantity_delta=Decimal("10"), transaction_type="purchase",
            location_id=production_site.id,
        )
        txn = await stock_service.move_stock(
            db, tenant_id=tenant.id, ingredient_id=flour.id,
            quantity_delta=Decimal("3"), transaction_type="purchase",
            location_id=delivery_site.id,
        )
        # The delivery site holds 3, even though the tenant now holds 13.
        assert txn.balance_after == Decimal("3.000")
        await db.refresh(flour)
        assert flour.current_stock == Decimal("13.000")

    async def test_stock_is_isolated_between_locations(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        delivery_site: Location, flour: Ingredient,
    ):
        await stock_service.move_stock(
            db, tenant_id=tenant.id, ingredient_id=flour.id,
            quantity_delta=Decimal("10"), transaction_type="purchase",
            location_id=production_site.id,
        )
        rows = await stock_service.get_location_stock(db, tenant.id, delivery_site.id)
        assert rows == []

    async def test_negative_is_allowed_and_recorded(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        flour: Ingredient,
    ):
        """A till must not refuse to sell because the books say zero."""
        txn = await stock_service.move_stock(
            db, tenant_id=tenant.id, ingredient_id=flour.id,
            quantity_delta=Decimal("-2"), transaction_type="consumption",
            location_id=production_site.id,
        )
        assert txn.balance_after == Decimal("-2.000")

    async def test_zero_movement_is_rejected(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        flour: Ingredient,
    ):
        with pytest.raises(StockError, match="not a movement"):
            await stock_service.move_stock(
                db, tenant_id=tenant.id, ingredient_id=flour.id,
                quantity_delta=Decimal("0"), transaction_type="adjustment",
                location_id=production_site.id,
            )

    async def test_unknown_transaction_type_is_rejected(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        flour: Ingredient,
    ):
        with pytest.raises(StockError, match="Unknown transaction type"):
            await stock_service.move_stock(
                db, tenant_id=tenant.id, ingredient_id=flour.id,
                quantity_delta=Decimal("1"), transaction_type="teleport",
                location_id=production_site.id,
            )

    async def test_low_stock_filter(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        flour: Ingredient, butter: Ingredient,
    ):
        for ing, qty in ((flour, Decimal("2")), (butter, Decimal("50"))):
            await stock_service.move_stock(
                db, tenant_id=tenant.id, ingredient_id=ing.id,
                quantity_delta=qty, transaction_type="purchase",
                location_id=production_site.id,
            )
        row = await stock_service.get_or_create_stock_row(
            db, tenant.id, production_site.id, flour.id
        )
        row.reorder_point = Decimal("5")
        await db.flush()

        low = await stock_service.get_location_stock(
            db, tenant.id, production_site.id, low_only=True
        )
        assert [r["ingredient_name"] for r in low] == ["Flour"]
        assert low[0]["is_low"] is True


# ---------------------------------------------------------------------------
# PRODUCTION
# ---------------------------------------------------------------------------


class TestProduction:
    async def test_production_consumes_inputs_and_adds_output(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        flour: Ingredient, butter: Ingredient, dough: Ingredient,
        dough_recipe: Recipe,
    ):
        for ing in (flour, butter):
            await stock_service.move_stock(
                db, tenant_id=tenant.id, ingredient_id=ing.id,
                quantity_delta=Decimal("100"), transaction_type="purchase",
                location_id=production_site.id,
            )

        result = await production_service.run_production(
            db, tenant_id=tenant.id, recipe_id=dough_recipe.id,
            batches=Decimal("2"), location_id=production_site.id,
        )

        assert result["produced_quantity"] == Decimal("10.000")  # 5 x 2

        rows = {
            r["ingredient_name"]: r["quantity"]
            for r in await stock_service.get_location_stock(
                db, tenant.id, production_site.id
            )
        }
        # Flour: 4kg x 1.10 waste x 2 batches = 8.8 consumed
        assert rows["Flour"] == Decimal("91.200")
        assert rows["Butter"] == Decimal("98.000")
        assert rows["Croissant Dough"] == Decimal("10.000")

    async def test_waste_factor_is_actually_applied(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        flour: Ingredient, butter: Ingredient, dough_recipe: Recipe,
    ):
        await stock_service.move_stock(
            db, tenant_id=tenant.id, ingredient_id=flour.id,
            quantity_delta=Decimal("100"), transaction_type="purchase",
            location_id=production_site.id,
        )
        await stock_service.move_stock(
            db, tenant_id=tenant.id, ingredient_id=butter.id,
            quantity_delta=Decimal("100"), transaction_type="purchase",
            location_id=production_site.id,
        )
        await production_service.run_production(
            db, tenant_id=tenant.id, recipe_id=dough_recipe.id,
            batches=Decimal("1"), location_id=production_site.id,
        )
        rows = {
            r["ingredient_name"]: r["quantity"]
            for r in await stock_service.get_location_stock(
                db, tenant.id, production_site.id
            )
        }
        assert rows["Flour"] == Decimal("95.600")  # 100 - 4.4, not 100 - 4

    async def test_producing_a_menu_item_recipe_is_refused(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
    ):
        category = Category(tenant_id=tenant.id, name="Pastry", display_order=1)
        db.add(category)
        await db.flush()
        item = MenuItem(
            tenant_id=tenant.id, category_id=category.id, name="Croissant", price=900
        )
        db.add(item)
        await db.flush()
        recipe = Recipe(
            tenant_id=tenant.id, menu_item_id=item.id,
            yield_servings=Decimal("1"),
        )
        db.add(recipe)
        await db.flush()

        with pytest.raises(StockError, match="produces a menu item"):
            await production_service.run_production(
                db, tenant_id=tenant.id, recipe_id=recipe.id,
                batches=Decimal("1"), location_id=production_site.id,
            )

    async def test_zero_batches_is_refused(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        dough_recipe: Recipe,
    ):
        with pytest.raises(StockError, match="greater than zero"):
            await production_service.run_production(
                db, tenant_id=tenant.id, recipe_id=dough_recipe.id,
                batches=Decimal("0"), location_id=production_site.id,
            )

    async def test_production_at_one_site_does_not_touch_the_other(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        delivery_site: Location, flour: Ingredient, butter: Ingredient,
        dough_recipe: Recipe,
    ):
        for site in (production_site, delivery_site):
            for ing in (flour, butter):
                await stock_service.move_stock(
                    db, tenant_id=tenant.id, ingredient_id=ing.id,
                    quantity_delta=Decimal("50"), transaction_type="purchase",
                    location_id=site.id,
                )
        await production_service.run_production(
            db, tenant_id=tenant.id, recipe_id=dough_recipe.id,
            batches=Decimal("1"), location_id=production_site.id,
        )
        delivery = {
            r["ingredient_name"]: r["quantity"]
            for r in await stock_service.get_location_stock(
                db, tenant.id, delivery_site.id
            )
        }
        assert delivery["Flour"] == Decimal("50.000")
        assert delivery["Butter"] == Decimal("50.000")


# ---------------------------------------------------------------------------
# TRANSFERS
# ---------------------------------------------------------------------------


class TestTransfers:
    @pytest_asyncio.fixture
    async def stocked(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        flour: Ingredient,
    ):
        await stock_service.move_stock(
            db, tenant_id=tenant.id, ingredient_id=flour.id,
            quantity_delta=Decimal("100"), transaction_type="purchase",
            location_id=production_site.id,
        )

    async def _qty(self, db, tenant, location, name) -> Decimal:
        rows = await stock_service.get_location_stock(db, tenant.id, location.id)
        return next((r["quantity"] for r in rows if r["ingredient_name"] == name), Decimal("0"))

    async def test_draft_moves_nothing(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        delivery_site: Location, flour: Ingredient, stocked,
    ):
        await transfer_service.create_transfer(
            db, tenant_id=tenant.id, from_location_id=production_site.id,
            to_location_id=delivery_site.id,
            lines=[{"ingredient_id": flour.id, "quantity": Decimal("10")}],
        )
        assert await self._qty(db, tenant, production_site, "Flour") == Decimal("100.000")

    async def test_send_then_receive_moves_the_stock(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        delivery_site: Location, flour: Ingredient, stocked,
    ):
        transfer = await transfer_service.create_transfer(
            db, tenant_id=tenant.id, from_location_id=production_site.id,
            to_location_id=delivery_site.id,
            lines=[{"ingredient_id": flour.id, "quantity": Decimal("10")}],
        )
        await transfer_service.send_transfer(
            db, tenant_id=tenant.id, transfer_id=transfer.id
        )
        # In transit: gone from source, NOT yet at destination.
        assert await self._qty(db, tenant, production_site, "Flour") == Decimal("90.000")
        assert await self._qty(db, tenant, delivery_site, "Flour") == Decimal("0")

        await transfer_service.receive_transfer(
            db, tenant_id=tenant.id, transfer_id=transfer.id
        )
        assert await self._qty(db, tenant, delivery_site, "Flour") == Decimal("10.000")

    async def test_short_delivery_is_visible_not_absorbed(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        delivery_site: Location, flour: Ingredient, stocked,
    ):
        transfer = await transfer_service.create_transfer(
            db, tenant_id=tenant.id, from_location_id=production_site.id,
            to_location_id=delivery_site.id,
            lines=[{"ingredient_id": flour.id, "quantity": Decimal("10")}],
        )
        await transfer_service.send_transfer(
            db, tenant_id=tenant.id, transfer_id=transfer.id
        )
        item_id = transfer.items[0].id
        received = await transfer_service.receive_transfer(
            db, tenant_id=tenant.id, transfer_id=transfer.id,
            received={item_id: Decimal("8")},
        )
        line = received.items[0]
        assert line.quantity_sent == Decimal("10.000")
        assert line.quantity_received == Decimal("8.000")
        # The 2 missing units are at neither site. That is the truth.
        assert await self._qty(db, tenant, delivery_site, "Flour") == Decimal("8.000")
        assert await self._qty(db, tenant, production_site, "Flour") == Decimal("90.000")

    async def test_cannot_receive_more_than_sent(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        delivery_site: Location, flour: Ingredient, stocked,
    ):
        transfer = await transfer_service.create_transfer(
            db, tenant_id=tenant.id, from_location_id=production_site.id,
            to_location_id=delivery_site.id,
            lines=[{"ingredient_id": flour.id, "quantity": Decimal("10")}],
        )
        await transfer_service.send_transfer(
            db, tenant_id=tenant.id, transfer_id=transfer.id
        )
        with pytest.raises(StockError, match="cannot exceed"):
            await transfer_service.receive_transfer(
                db, tenant_id=tenant.id, transfer_id=transfer.id,
                received={transfer.items[0].id: Decimal("11")},
            )

    async def test_cannot_receive_twice(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        delivery_site: Location, flour: Ingredient, stocked,
    ):
        transfer = await transfer_service.create_transfer(
            db, tenant_id=tenant.id, from_location_id=production_site.id,
            to_location_id=delivery_site.id,
            lines=[{"ingredient_id": flour.id, "quantity": Decimal("10")}],
        )
        await transfer_service.send_transfer(
            db, tenant_id=tenant.id, transfer_id=transfer.id
        )
        await transfer_service.receive_transfer(
            db, tenant_id=tenant.id, transfer_id=transfer.id
        )
        with pytest.raises(StockError, match="in transit"):
            await transfer_service.receive_transfer(
                db, tenant_id=tenant.id, transfer_id=transfer.id
            )

    async def test_cancelling_in_transit_returns_the_stock(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        delivery_site: Location, flour: Ingredient, stocked,
    ):
        transfer = await transfer_service.create_transfer(
            db, tenant_id=tenant.id, from_location_id=production_site.id,
            to_location_id=delivery_site.id,
            lines=[{"ingredient_id": flour.id, "quantity": Decimal("10")}],
        )
        await transfer_service.send_transfer(
            db, tenant_id=tenant.id, transfer_id=transfer.id
        )
        await transfer_service.cancel_transfer(
            db, tenant_id=tenant.id, transfer_id=transfer.id
        )
        assert await self._qty(db, tenant, production_site, "Flour") == Decimal("100.000")
        assert await self._qty(db, tenant, delivery_site, "Flour") == Decimal("0")

    async def test_received_transfer_cannot_be_cancelled(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        delivery_site: Location, flour: Ingredient, stocked,
    ):
        transfer = await transfer_service.create_transfer(
            db, tenant_id=tenant.id, from_location_id=production_site.id,
            to_location_id=delivery_site.id,
            lines=[{"ingredient_id": flour.id, "quantity": Decimal("10")}],
        )
        await transfer_service.send_transfer(db, tenant_id=tenant.id, transfer_id=transfer.id)
        await transfer_service.receive_transfer(db, tenant_id=tenant.id, transfer_id=transfer.id)
        with pytest.raises(StockError, match="cannot be cancelled"):
            await transfer_service.cancel_transfer(
                db, tenant_id=tenant.id, transfer_id=transfer.id
            )

    async def test_transfer_to_the_same_location_is_refused(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        flour: Ingredient,
    ):
        with pytest.raises(StockError, match="two different locations"):
            await transfer_service.create_transfer(
                db, tenant_id=tenant.id, from_location_id=production_site.id,
                to_location_id=production_site.id,
                lines=[{"ingredient_id": flour.id, "quantity": Decimal("1")}],
            )

    async def test_an_unsent_transfer_cannot_be_received(
        self, db: AsyncSession, tenant: Tenant, production_site: Location,
        delivery_site: Location, flour: Ingredient, stocked,
    ):
        transfer = await transfer_service.create_transfer(
            db, tenant_id=tenant.id, from_location_id=production_site.id,
            to_location_id=delivery_site.id,
            lines=[{"ingredient_id": flour.id, "quantity": Decimal("5")}],
        )
        with pytest.raises(StockError, match="in transit"):
            await transfer_service.receive_transfer(
                db, tenant_id=tenant.id, transfer_id=transfer.id
            )


# ---------------------------------------------------------------------------
# CHANNEL COMMISSION AND PROFITABILITY
# ---------------------------------------------------------------------------


class TestCommission:
    async def test_commission_is_integer_maths(self, db: AsyncSession, tenant: Tenant):
        channel = SalesChannel(
            tenant_id=tenant.id, name="Talabat", code="talabat",
            commission_bps=1500,
        )
        assert location_service.commission_for(channel, 10000) == 1500  # 15%

    async def test_fixed_fee_is_added(self, db: AsyncSession, tenant: Tenant):
        channel = SalesChannel(
            tenant_id=tenant.id, name="Card", code="card",
            commission_bps=250, fixed_fee_minor=30,
        )
        assert location_service.commission_for(channel, 10000) == 280

    async def test_no_channel_costs_nothing(self):
        assert location_service.commission_for(None, 99999) == 0

    async def test_snapshot_freezes_the_rate(
        self, db: AsyncSession, tenant: Tenant, admin_user: User, order: Order,
    ):
        channel = SalesChannel(
            tenant_id=tenant.id, name="Talabat", code="talabat", commission_bps=1500
        )
        db.add(channel)
        await db.flush()

        order.sales_channel_id = channel.id
        await db.flush()
        frozen = await location_service.snapshot_commission(db, tenant.id, order)

        # Renegotiate. The order must not move.
        channel.commission_bps = 500
        await db.flush()
        assert order.channel_commission_minor == frozen


class TestProfitability:
    async def test_net_profit_subtracts_cost_and_commission(
        self, db: AsyncSession, tenant: Tenant, admin_user: User,
        production_site: Location,
    ):
        category = Category(tenant_id=tenant.id, name="Pastry", display_order=1)
        db.add(category)
        await db.flush()
        item = MenuItem(
            tenant_id=tenant.id, category_id=category.id, name="Croissant", price=1000
        )
        db.add(item)
        await db.flush()
        # cost_per_serving is stored in MINOR units, the same unit as
        # Order.total. 200 here means 2.00 AED, not 200 AED. Asserting the
        # wrong convention here is exactly what let a 100x cost overstatement
        # reach the live API on 2026-08-26.
        recipe = Recipe(
            tenant_id=tenant.id, menu_item_id=item.id,
            yield_servings=Decimal("1"), cost_per_serving=Decimal("200"),
        )
        db.add(recipe)
        channel = SalesChannel(
            tenant_id=tenant.id, name="Talabat", code="talabat", commission_bps=1500
        )
        db.add(channel)
        await db.flush()

        order = Order(
            tenant_id=tenant.id, order_number="T-001", order_type="online",
            status="completed", subtotal=1000, tax_amount=0, discount_amount=0,
            total=1000, created_by=admin_user.id,
            location_id=production_site.id, sales_channel_id=channel.id,
            channel_commission_minor=150,
        )
        db.add(order)
        await db.flush()
        db.add(
            OrderItem(
                tenant_id=tenant.id, order_id=order.id, menu_item_id=item.id,
                name="Croissant", quantity=1, unit_price=1000, total=1000,
            )
        )
        await db.flush()

        report = await location_service.profitability_report(db, tenant.id)
        totals = report["totals"]
        assert totals["revenue_minor"] == 1000
        assert totals["product_cost_minor"] == 200
        assert totals["commission_minor"] == 150
        assert totals["net_profit_minor"] == 650

        assert report["by_channel"][0]["name"] == "Talabat"
        assert report["by_location"][0]["name"] == "Production Kitchen"


# ---------------------------------------------------------------------------
# SALE DEDUCTS STOCK -- AND THE NO-REGRESSION GUARD
# ---------------------------------------------------------------------------


class TestSaleDeduction:
    async def test_completing_an_order_deducts_from_its_own_location(
        self, db: AsyncSession, tenant: Tenant, admin_user: User,
        production_site: Location, delivery_site: Location, flour: Ingredient,
    ):
        for site in (production_site, delivery_site):
            await stock_service.move_stock(
                db, tenant_id=tenant.id, ingredient_id=flour.id,
                quantity_delta=Decimal("50"), transaction_type="purchase",
                location_id=site.id,
            )

        category = Category(tenant_id=tenant.id, name="Pastry", display_order=1)
        db.add(category)
        await db.flush()
        item = MenuItem(
            tenant_id=tenant.id, category_id=category.id, name="Bread", price=500
        )
        db.add(item)
        await db.flush()
        recipe = Recipe(
            tenant_id=tenant.id, menu_item_id=item.id,
            yield_servings=Decimal("1"),
        )
        db.add(recipe)
        await db.flush()
        db.add(
            RecipeItem(
                tenant_id=tenant.id, recipe_id=recipe.id, ingredient_id=flour.id,
                quantity=Decimal("2"), unit="kg",
            )
        )
        order = Order(
            tenant_id=tenant.id, order_number="D-001", order_type="takeaway",
            status="served", subtotal=500, tax_amount=0, discount_amount=0,
            total=500, created_by=admin_user.id, location_id=delivery_site.id,
        )
        db.add(order)
        await db.flush()
        db.add(
            OrderItem(
                tenant_id=tenant.id, order_id=order.id, menu_item_id=item.id,
                name="Bread", quantity=3, unit_price=500, total=1500,
            )
        )
        await db.flush()

        await production_service.consume_for_order(
            db, tenant_id=tenant.id, order_id=order.id
        )

        delivery_rows = await stock_service.get_location_stock(
            db, tenant.id, delivery_site.id
        )
        production_rows = await stock_service.get_location_stock(
            db, tenant.id, production_site.id
        )
        assert delivery_rows[0]["quantity"] == Decimal("44.000")  # 50 - (2 x 3)
        assert production_rows[0]["quantity"] == Decimal("50.000")  # untouched

    async def test_deduction_is_idempotent(
        self, db: AsyncSession, tenant: Tenant, admin_user: User,
        delivery_site: Location, flour: Ingredient,
    ):
        await stock_service.move_stock(
            db, tenant_id=tenant.id, ingredient_id=flour.id,
            quantity_delta=Decimal("50"), transaction_type="purchase",
            location_id=delivery_site.id,
        )
        category = Category(tenant_id=tenant.id, name="Pastry", display_order=1)
        db.add(category)
        await db.flush()
        item = MenuItem(
            tenant_id=tenant.id, category_id=category.id, name="Bread", price=500
        )
        db.add(item)
        await db.flush()
        recipe = Recipe(
            tenant_id=tenant.id, menu_item_id=item.id,
            yield_servings=Decimal("1"),
        )
        db.add(recipe)
        await db.flush()
        db.add(
            RecipeItem(
                tenant_id=tenant.id, recipe_id=recipe.id, ingredient_id=flour.id,
                quantity=Decimal("2"), unit="kg",
            )
        )
        order = Order(
            tenant_id=tenant.id, order_number="D-002", order_type="takeaway",
            status="served", subtotal=500, tax_amount=0, discount_amount=0,
            total=500, created_by=admin_user.id, location_id=delivery_site.id,
        )
        db.add(order)
        await db.flush()
        db.add(
            OrderItem(
                tenant_id=tenant.id, order_id=order.id, menu_item_id=item.id,
                name="Bread", quantity=1, unit_price=500, total=500,
            )
        )
        await db.flush()

        first = await production_service.consume_for_order(
            db, tenant_id=tenant.id, order_id=order.id
        )
        second = await production_service.consume_for_order(
            db, tenant_id=tenant.id, order_id=order.id
        )
        assert first["skipped"] is False
        assert second["skipped"] is True

        rows = await stock_service.get_location_stock(db, tenant.id, delivery_site.id)
        assert rows[0]["quantity"] == Decimal("48.000")  # deducted once, not twice

    async def test_item_without_a_recipe_is_noted_not_an_error(
        self, db: AsyncSession, tenant: Tenant, admin_user: User,
        delivery_site: Location,
    ):
        """A canned drink is bought and sold, not made. That is normal."""
        category = Category(tenant_id=tenant.id, name="Drinks", display_order=1)
        db.add(category)
        await db.flush()
        item = MenuItem(
            tenant_id=tenant.id, category_id=category.id, name="Cola", price=300
        )
        db.add(item)
        await db.flush()
        order = Order(
            tenant_id=tenant.id, order_number="D-003", order_type="takeaway",
            status="served", subtotal=300, tax_amount=0, discount_amount=0,
            total=300, created_by=admin_user.id, location_id=delivery_site.id,
        )
        db.add(order)
        await db.flush()
        db.add(
            OrderItem(
                tenant_id=tenant.id, order_id=order.id, menu_item_id=item.id,
                name="Cola", quantity=1, unit_price=300, total=300,
            )
        )
        await db.flush()

        result = await production_service.consume_for_order(
            db, tenant_id=tenant.id, order_id=order.id
        )
        assert result["lines_deducted"] == 0
        assert item.id in result["menu_items_without_recipe"]


class TestNoRegressionForSingleSiteTenants:
    """The guard that matters most: chick-shack has no locations at all."""

    async def test_resolve_location_raises_for_a_tenant_with_no_locations(
        self, db: AsyncSession, tenant: Tenant
    ):
        with pytest.raises(StockError, match="no active location"):
            await stock_service.resolve_location(db, tenant.id, None)

    async def test_completing_an_order_is_unaffected_when_no_locations_exist(
        self, db: AsyncSession, tenant: Tenant, admin_user: User, order: Order,
    ):
        """The order-completion hook must be a no-op, never an exception."""
        from app.services.order_service import _apply_inventory_and_commission

        await _apply_inventory_and_commission(db, tenant.id, order)
        assert order.channel_commission_minor == 0

    async def test_profitability_reports_cleanly_with_no_locations(
        self, db: AsyncSession, tenant: Tenant
    ):
        report = await location_service.profitability_report(db, tenant.id)
        assert report["totals"]["orders"] == 0
        assert report["by_channel"] == []
