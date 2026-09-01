"""A recipe can be attached to a modifier, and that add-on then behaves like
everything else in the inventory module (OI-99).

Martin Zubeldia found the gap in his own UAT: a paid add-on could not be told
what it was made of, so it moved no stock and carried no cost. The three
invariants these tests hold down:

  * an add-on the customer paid for DEDUCTS what it is made of, at the line's
    quantity, from the location that sold it;
  * an add-on's cost reaches the profitability report, so the margin on a
    modified line is the real one and not a flattering one;
  * a tenant with no modifier recipes -- which is every tenant that existed
    before this -- behaves exactly as it did before.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Ingredient, InventoryTransaction, Recipe, RecipeItem
from app.models.location import Location
from app.models.menu import Category, MenuItem, Modifier, ModifierGroup
from app.models.order import Order, OrderItem, OrderItemModifier
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.inventory import RecipeCreate, RecipeItemCreate
from app.services import location_service, production_service, recipe_service, stock_service
from app.services.stock_service import StockError

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def site(db: AsyncSession, tenant: Tenant) -> Location:
    loc = Location(
        tenant_id=tenant.id,
        name="Delivery Kitchen",
        code="DEL",
        location_type="delivery",
        is_default=True,
    )
    db.add(loc)
    await db.flush()
    return loc


@pytest_asyncio.fixture
async def cheese(db: AsyncSession, tenant: Tenant) -> Ingredient:
    ing = Ingredient(
        tenant_id=tenant.id,
        name="Cheese Sauce",
        unit="kg",
        cost_per_unit=Decimal("13.90"),
    )
    db.add(ing)
    await db.flush()
    return ing


@pytest_asyncio.fixture
async def croissant(db: AsyncSession, tenant: Tenant) -> MenuItem:
    category = Category(tenant_id=tenant.id, name="Pastries", display_order=1)
    db.add(category)
    await db.flush()
    item = MenuItem(
        tenant_id=tenant.id, category_id=category.id, name="Croissant", price=1600
    )
    db.add(item)
    await db.flush()
    return item


@pytest_asyncio.fixture
async def extra_cheese(db: AsyncSession, tenant: Tenant) -> Modifier:
    group = ModifierGroup(tenant_id=tenant.id, name="Extras", display_order=1)
    db.add(group)
    await db.flush()
    modifier = Modifier(
        tenant_id=tenant.id,
        group_id=group.id,
        name="Extra Cheese Sauce",
        price_adjustment=200,
    )
    db.add(modifier)
    await db.flush()
    return modifier


async def _stock(db: AsyncSession, tenant: Tenant, ingredient: Ingredient,
                 site: Location, qty: str) -> None:
    await stock_service.move_stock(
        db,
        tenant_id=tenant.id,
        ingredient_id=ingredient.id,
        quantity_delta=Decimal(qty),
        transaction_type="purchase",
        location_id=site.id,
    )


async def _order_with_addon(
    db: AsyncSession, tenant: Tenant, admin_user: User, site: Location,
    item: MenuItem, modifier: Modifier | None, quantity: int = 1,
    number: str = "A-001",
) -> Order:
    order = Order(
        tenant_id=tenant.id, order_number=number, order_type="takeaway",
        status="completed", subtotal=1600, tax_amount=0, discount_amount=0,
        total=1600 + (200 if modifier else 0), created_by=admin_user.id,
        location_id=site.id,
    )
    db.add(order)
    await db.flush()
    line = OrderItem(
        tenant_id=tenant.id, order_id=order.id, menu_item_id=item.id,
        name=item.name, quantity=quantity, unit_price=1600,
        total=1600 * quantity,
    )
    db.add(line)
    await db.flush()
    if modifier is not None:
        db.add(
            OrderItemModifier(
                tenant_id=tenant.id,
                order_item_id=line.id,
                modifier_id=modifier.id,
                name=modifier.name,
                price_adjustment=modifier.price_adjustment,
            )
        )
    await db.flush()
    return order


async def _addon_recipe(
    db: AsyncSession, tenant: Tenant, admin_user: User,
    modifier: Modifier, ingredient: Ingredient, quantity: str = "0.03",
) -> Recipe:
    return await recipe_service.create_recipe(
        db,
        tenant.id,
        RecipeCreate(
            modifier_id=modifier.id,
            yield_servings=Decimal("1"),
            recipe_items=[
                RecipeItemCreate(
                    ingredient_id=ingredient.id,
                    quantity=Decimal(quantity),
                    unit=ingredient.unit,
                    waste_factor=Decimal("0"),
                )
            ],
        ),
        admin_user.id,
    )


# ---------------------------------------------------------------------------
# THE TARGET RULE
# ---------------------------------------------------------------------------


class TestExactlyOneTarget:
    def test_a_modifier_alone_is_a_valid_target(self):
        payload = RecipeCreate(modifier_id="11111111-1111-1111-1111-111111111111")
        assert payload.modifier_id is not None
        assert payload.menu_item_id is None

    def test_no_target_at_all_is_refused(self):
        with pytest.raises(ValidationError):
            RecipeCreate()

    def test_two_targets_are_refused(self):
        with pytest.raises(ValidationError):
            RecipeCreate(
                menu_item_id="11111111-1111-1111-1111-111111111111",
                modifier_id="22222222-2222-2222-2222-222222222222",
            )

    def test_all_three_targets_are_refused(self):
        with pytest.raises(ValidationError):
            RecipeCreate(
                menu_item_id="11111111-1111-1111-1111-111111111111",
                produces_ingredient_id="22222222-2222-2222-2222-222222222222",
                modifier_id="33333333-3333-3333-3333-333333333333",
            )


class TestAddonRecipeCrud:
    async def test_an_addon_recipe_is_created_and_costed(
        self, db: AsyncSession, tenant: Tenant, admin_user: User,
        extra_cheese: Modifier, cheese: Ingredient,
    ):
        recipe = await _addon_recipe(db, tenant, admin_user, extra_cheese, cheese)

        assert recipe.modifier_id == extra_cheese.id
        assert recipe.menu_item_id is None
        # 0.03 kg x 13.90 = 0.417. Quantized before comparing because Postgres
        # rounds to the column's 2dp on write and SQLite does not, and this
        # suite runs on SQLite: asserting the raw value would pass here and
        # mean nothing about production.
        assert recipe.cost_per_serving.quantize(Decimal("0.01")) == Decimal("0.42")

    async def test_a_modifier_from_another_tenant_is_refused(
        self, db: AsyncSession, tenant: Tenant, admin_user: User,
        cheese: Ingredient,
    ):
        # A tenant carries its own id in tenant_id, as the seed script does.
        other_id = uuid.uuid4()
        other = Tenant(
            id=other_id, tenant_id=other_id, name="Someone Else",
            slug="someone-else",
        )
        db.add(other)
        await db.flush()
        group = ModifierGroup(tenant_id=other.id, name="Extras", display_order=1)
        db.add(group)
        await db.flush()
        theirs = Modifier(
            tenant_id=other.id, group_id=group.id, name="Extra Cheese",
            price_adjustment=200,
        )
        db.add(theirs)
        await db.flush()

        with pytest.raises(ValueError, match="Modifier not found"):
            await _addon_recipe(db, tenant, admin_user, theirs, cheese)

    async def test_editing_an_addon_recipe_keeps_it_on_its_modifier(
        self, db: AsyncSession, tenant: Tenant, admin_user: User,
        extra_cheese: Modifier, cheese: Ingredient,
    ):
        """The new version must carry the target across.

        Rebuilding a version from `menu_item_id` and `produces_ingredient_id`
        alone would leave a modifier recipe with no target at all, which the
        exactly-one-target rule then refuses -- an add-on recipe that could be
        created and never edited.
        """
        first = await _addon_recipe(db, tenant, admin_user, extra_cheese, cheese)

        second = await _addon_recipe(
            db, tenant, admin_user, extra_cheese, cheese, quantity="0.06"
        )

        assert second.id != first.id
        assert second.modifier_id == extra_cheese.id
        assert second.version == 2
        assert second.cost_per_serving.quantize(Decimal("0.01")) == Decimal("0.83")
        await db.refresh(first)
        assert first.is_active is False

    async def test_an_addon_recipe_cannot_be_produced_into_stock(
        self, db: AsyncSession, tenant: Tenant, admin_user: User,
        extra_cheese: Modifier, cheese: Ingredient, site: Location,
    ):
        recipe = await _addon_recipe(db, tenant, admin_user, extra_cheese, cheese)

        with pytest.raises(StockError, match="is for an add-on"):
            await production_service.run_production(
                db, tenant_id=tenant.id, recipe_id=recipe.id,
                batches=Decimal("1"), location_id=site.id,
            )


# ---------------------------------------------------------------------------
# THE POINT OF THE WHOLE THING: STOCK MOVES
# ---------------------------------------------------------------------------


class TestAddonConsumption:
    async def test_a_paid_addon_deducts_what_it_is_made_of(
        self, db: AsyncSession, tenant: Tenant, admin_user: User, site: Location,
        croissant: MenuItem, extra_cheese: Modifier, cheese: Ingredient,
    ):
        await _stock(db, tenant, cheese, site, "5")
        await _addon_recipe(db, tenant, admin_user, extra_cheese, cheese)
        order = await _order_with_addon(
            db, tenant, admin_user, site, croissant, extra_cheese
        )

        await production_service.consume_for_order(
            db, tenant_id=tenant.id, order_id=order.id
        )

        moves = (
            await db.execute(
                select(InventoryTransaction).where(
                    InventoryTransaction.order_id == order.id,
                    InventoryTransaction.ingredient_id == cheese.id,
                )
            )
        ).scalars().all()
        assert len(moves) == 1
        assert moves[0].quantity == Decimal("-0.030")
        assert "add-on" in (moves[0].notes or "")

    async def test_the_addon_scales_with_the_line_quantity(
        self, db: AsyncSession, tenant: Tenant, admin_user: User, site: Location,
        croissant: MenuItem, extra_cheese: Modifier, cheese: Ingredient,
    ):
        """Two croissants with extra cheese is ONE modifier row and TWO portions.

        `order_item_modifiers` holds one row per chosen modifier per line, not
        one per unit, so the line quantity is the multiplier.
        """
        await _stock(db, tenant, cheese, site, "5")
        await _addon_recipe(db, tenant, admin_user, extra_cheese, cheese)
        order = await _order_with_addon(
            db, tenant, admin_user, site, croissant, extra_cheese, quantity=2
        )

        await production_service.consume_for_order(
            db, tenant_id=tenant.id, order_id=order.id
        )

        move = (
            await db.execute(
                select(InventoryTransaction).where(
                    InventoryTransaction.order_id == order.id,
                    InventoryTransaction.ingredient_id == cheese.id,
                )
            )
        ).scalar_one()
        assert move.quantity == Decimal("-0.060")

    async def test_an_addon_is_deducted_even_when_its_item_has_no_recipe(
        self, db: AsyncSession, tenant: Tenant, admin_user: User, site: Location,
        croissant: MenuItem, extra_cheese: Modifier, cheese: Ingredient,
    ):
        """A bought-in item can still carry an add-on that is made in-house.

        Skipping the modifiers whenever the line's own recipe was missing was
        the first version of this fix, and it silently lost the deduction on
        exactly the lines most likely to have one.
        """
        await _stock(db, tenant, cheese, site, "5")
        await _addon_recipe(db, tenant, admin_user, extra_cheese, cheese)
        # croissant deliberately has NO recipe of its own
        order = await _order_with_addon(
            db, tenant, admin_user, site, croissant, extra_cheese
        )

        result = await production_service.consume_for_order(
            db, tenant_id=tenant.id, order_id=order.id
        )

        assert croissant.id in result["menu_items_without_recipe"]
        move = (
            await db.execute(
                select(InventoryTransaction).where(
                    InventoryTransaction.order_id == order.id,
                    InventoryTransaction.ingredient_id == cheese.id,
                )
            )
        ).scalar_one()
        assert move.quantity == Decimal("-0.030")

    async def test_a_modifier_with_no_recipe_deducts_nothing_and_is_not_an_error(
        self, db: AsyncSession, tenant: Tenant, admin_user: User, site: Location,
        croissant: MenuItem, extra_cheese: Modifier, cheese: Ingredient,
    ):
        """Most modifiers (Mild/Medium/Hot) change no ingredients at all."""
        await _stock(db, tenant, cheese, site, "5")
        order = await _order_with_addon(
            db, tenant, admin_user, site, croissant, extra_cheese
        )

        result = await production_service.consume_for_order(
            db, tenant_id=tenant.id, order_id=order.id
        )

        assert result["lines_deducted"] == 0
        moves = (
            await db.execute(
                select(InventoryTransaction).where(
                    InventoryTransaction.order_id == order.id
                )
            )
        ).scalars().all()
        assert moves == []

    async def test_an_order_with_no_modifiers_is_unchanged(
        self, db: AsyncSession, tenant: Tenant, admin_user: User, site: Location,
        croissant: MenuItem, cheese: Ingredient,
    ):
        """The no-regression guard. Every tenant that existed before OI-99 is
        this case, Chick Shack included."""
        await _stock(db, tenant, cheese, site, "5")
        recipe = Recipe(
            tenant_id=tenant.id, menu_item_id=croissant.id,
            yield_servings=Decimal("1"),
        )
        db.add(recipe)
        await db.flush()
        db.add(
            RecipeItem(
                tenant_id=tenant.id, recipe_id=recipe.id, ingredient_id=cheese.id,
                quantity=Decimal("0.1"), unit="kg",
            )
        )
        order = await _order_with_addon(
            db, tenant, admin_user, site, croissant, None
        )

        await production_service.consume_for_order(
            db, tenant_id=tenant.id, order_id=order.id
        )

        move = (
            await db.execute(
                select(InventoryTransaction).where(
                    InventoryTransaction.order_id == order.id
                )
            )
        ).scalar_one()
        assert move.quantity == Decimal("-0.100")

    async def test_deducting_twice_is_still_refused_with_addons_present(
        self, db: AsyncSession, tenant: Tenant, admin_user: User, site: Location,
        croissant: MenuItem, extra_cheese: Modifier, cheese: Ingredient,
    ):
        await _stock(db, tenant, cheese, site, "5")
        await _addon_recipe(db, tenant, admin_user, extra_cheese, cheese)
        order = await _order_with_addon(
            db, tenant, admin_user, site, croissant, extra_cheese
        )

        await production_service.consume_for_order(
            db, tenant_id=tenant.id, order_id=order.id
        )
        again = await production_service.consume_for_order(
            db, tenant_id=tenant.id, order_id=order.id
        )

        assert again["skipped"] is True
        moves = (
            await db.execute(
                select(InventoryTransaction).where(
                    InventoryTransaction.order_id == order.id
                )
            )
        ).scalars().all()
        assert len(moves) == 1


# ---------------------------------------------------------------------------
# AND THE MARGIN STOPS LYING
# ---------------------------------------------------------------------------


class TestAddonCosting:
    async def test_the_addon_cost_reaches_the_profitability_report(
        self, db: AsyncSession, tenant: Tenant, admin_user: User, site: Location,
        croissant: MenuItem, extra_cheese: Modifier, cheese: Ingredient,
    ):
        """Revenue 1800 against a cost of 346 + 42, not 346.

        Before OI-99 the add-on's 200 of revenue carried no cost at all, which
        reported a better margin than the business actually made, and the error
        grew with how hard the counter upsold.
        """
        item_recipe = Recipe(
            tenant_id=tenant.id, menu_item_id=croissant.id,
            yield_servings=Decimal("1"), cost_per_serving=Decimal("346"),
        )
        db.add(item_recipe)
        await db.flush()
        addon = Recipe(
            tenant_id=tenant.id, modifier_id=extra_cheese.id,
            yield_servings=Decimal("1"), cost_per_serving=Decimal("42"),
        )
        db.add(addon)
        await db.flush()
        order = await _order_with_addon(
            db, tenant, admin_user, site, croissant, extra_cheese
        )
        order.subtotal = 1800
        order.total = 1800
        await db.flush()

        report = await location_service.profitability_report(db, tenant.id)

        assert report["totals"]["revenue_minor"] == 1800
        assert report["totals"]["product_cost_minor"] == 388

    async def test_an_addon_cost_scales_with_the_line_quantity(
        self, db: AsyncSession, tenant: Tenant, admin_user: User, site: Location,
        croissant: MenuItem, extra_cheese: Modifier,
    ):
        addon = Recipe(
            tenant_id=tenant.id, modifier_id=extra_cheese.id,
            yield_servings=Decimal("1"), cost_per_serving=Decimal("42"),
        )
        db.add(addon)
        await db.flush()
        await _order_with_addon(
            db, tenant, admin_user, site, croissant, extra_cheese, quantity=3
        )

        report = await location_service.profitability_report(db, tenant.id)

        assert report["totals"]["product_cost_minor"] == 126

    async def test_costs_are_unchanged_for_an_order_with_no_addons(
        self, db: AsyncSession, tenant: Tenant, admin_user: User, site: Location,
        croissant: MenuItem,
    ):
        db.add(
            Recipe(
                tenant_id=tenant.id, menu_item_id=croissant.id,
                yield_servings=Decimal("1"), cost_per_serving=Decimal("346"),
            )
        )
        await db.flush()
        await _order_with_addon(db, tenant, admin_user, site, croissant, None)

        report = await location_service.profitability_report(db, tenant.id)

        assert report["totals"]["product_cost_minor"] == 346
