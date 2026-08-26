"""The ordering suggestion: recipe explosion, shortfall, pack rounding.

The invariants:

  * a produced ingredient is MADE, never bought -- the recursion orders its raw
    inputs instead, which is the entire point of the sub-recipe chain
  * waste factors are applied, at every layer
  * shortfall = required - on hand - already on order, so running it twice in a
    morning does not order everything twice
  * an order is rounded UP to whole packs and up to the minimum, never down
  * a circular recipe is refused by name rather than recursed forever

⚠️ A regression net, not the verification. `app/scripts/verify_suggestion.py`
checks the same arithmetic against the real API using quantities worked out by
hand from the seed, because a test written by whoever wrote the code will
happily agree with its own mistake.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Ingredient, Recipe, RecipeItem
from app.models.location import Location
from app.models.menu import Category, MenuItem
from app.models.tenant import Tenant
from app.services import (
    purchase_order_service,
    purchase_suggestion_service,
    stock_service,
    supplier_service,
)
from app.services.purchase_suggestion_service import SuggestionError

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# A three-layer bakery: flour + butter -> dough -> croissant
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def site(db: AsyncSession, tenant: Tenant) -> Location:
    loc = Location(
        tenant_id=tenant.id, name="Bakery", code="BAK", is_default=True
    )
    db.add(loc)
    await db.flush()
    return loc


async def _ingredient(
    db: AsyncSession,
    tenant: Tenant,
    name: str,
    unit: str = "kg",
    cost_minor: str = "400",
    produced: bool = False,
) -> Ingredient:
    ing = Ingredient(
        tenant_id=tenant.id,
        name=name,
        unit=unit,
        cost_per_unit=Decimal(cost_minor),
        is_produced=produced,
    )
    db.add(ing)
    await db.flush()
    return ing


@pytest_asyncio.fixture
async def flour(db, tenant) -> Ingredient:
    return await _ingredient(db, tenant, "Flour", cost_minor="400")


@pytest_asyncio.fixture
async def butter(db, tenant) -> Ingredient:
    return await _ingredient(db, tenant, "Butter", cost_minor="1800")


@pytest_asyncio.fixture
async def dough(db, tenant) -> Ingredient:
    return await _ingredient(db, tenant, "Croissant Dough", produced=True)


@pytest_asyncio.fixture
async def croissant(db: AsyncSession, tenant: Tenant) -> MenuItem:
    category = Category(tenant_id=tenant.id, name="Pastry", display_order=1)
    db.add(category)
    await db.flush()
    item = MenuItem(
        tenant_id=tenant.id, category_id=category.id, name="Butter Croissant", price=800
    )
    db.add(item)
    await db.flush()
    return item


@pytest_asyncio.fixture
async def dough_recipe(
    db: AsyncSession, tenant: Tenant, dough: Ingredient, flour: Ingredient, butter: Ingredient
) -> Recipe:
    """One batch yields 5 kg of dough from 2.5 kg flour (2% waste) + 1.2 kg butter."""
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
                tenant_id=tenant.id,
                recipe_id=recipe.id,
                ingredient_id=flour.id,
                quantity=Decimal("2.5"),
                unit="kg",
                waste_factor=Decimal("2"),
            ),
            RecipeItem(
                tenant_id=tenant.id,
                recipe_id=recipe.id,
                ingredient_id=butter.id,
                quantity=Decimal("1.2"),
                unit="kg",
                waste_factor=Decimal("0"),
            ),
        ]
    )
    await db.flush()
    return recipe


@pytest_asyncio.fixture
async def croissant_recipe(
    db: AsyncSession, tenant: Tenant, croissant: MenuItem, dough: Ingredient
) -> Recipe:
    """One croissant takes 0.12 kg of dough."""
    recipe = Recipe(
        tenant_id=tenant.id, menu_item_id=croissant.id, yield_servings=Decimal("1")
    )
    db.add(recipe)
    await db.flush()
    db.add(
        RecipeItem(
            tenant_id=tenant.id,
            recipe_id=recipe.id,
            ingredient_id=dough.id,
            quantity=Decimal("0.12"),
            unit="kg",
            waste_factor=Decimal("0"),
        )
    )
    await db.flush()
    return recipe


async def _plan(db, tenant, site, recipe, batches="500"):
    return await purchase_suggestion_service.build_suggestion(
        db,
        tenant_id=tenant.id,
        location_id=site.id,
        targets=[{"recipe_id": recipe.id, "batches": Decimal(batches)}],
    )


def _line(plan: dict, name: str) -> dict | None:
    return next((r for r in plan["lines"] if r["ingredient_name"] == name), None)


# ---------------------------------------------------------------------------
# EXPLOSION
# ---------------------------------------------------------------------------


async def test_a_sub_recipe_is_made_not_bought(
    db, tenant, site, croissant_recipe, dough_recipe, flour, butter, dough
):
    """500 croissants -> 60 kg of dough to MAKE -> flour and butter to BUY."""
    plan = await _plan(db, tenant, site, croissant_recipe, "500")

    made = {r["ingredient_name"]: r["quantity_to_make"] for r in plan["production_plan"]}
    assert made["Croissant Dough"] == Decimal("60.000")

    # The dough itself must never appear as something to order.
    assert _line(plan, "Croissant Dough") is None

    # 60 kg / 5 kg per batch = 12 batches.
    #   flour  2.5 x 1.02 waste x 12 = 30.6
    #   butter 1.2            x 12   = 14.4
    assert _line(plan, "Flour")["required"] == Decimal("30.600")
    assert _line(plan, "Butter")["required"] == Decimal("14.400")


async def test_waste_is_applied_at_every_layer(
    db, tenant, site, croissant_recipe, dough_recipe, flour
):
    """30.6, not 30. A 2% loss on every sack is a real cost, not a rounding."""
    plan = await _plan(db, tenant, site, croissant_recipe, "500")
    assert _line(plan, "Flour")["required"] == Decimal("30.600")


async def test_two_products_sharing_a_sub_recipe_add_up(
    db: AsyncSession,
    tenant: Tenant,
    site: Location,
    croissant: MenuItem,
    croissant_recipe: Recipe,
    dough_recipe: Recipe,
    dough: Ingredient,
    flour: Ingredient,
):
    """Two lines using the same dough order one combined quantity of flour."""
    category_id = croissant.category_id
    second = MenuItem(
        tenant_id=tenant.id,
        category_id=category_id,
        name="Pain au Chocolat",
        price=900,
    )
    db.add(second)
    await db.flush()
    second_recipe = Recipe(
        tenant_id=tenant.id, menu_item_id=second.id, yield_servings=Decimal("1")
    )
    db.add(second_recipe)
    await db.flush()
    db.add(
        RecipeItem(
            tenant_id=tenant.id,
            recipe_id=second_recipe.id,
            ingredient_id=dough.id,
            quantity=Decimal("0.12"),
            unit="kg",
        )
    )
    await db.flush()

    plan = await purchase_suggestion_service.build_suggestion(
        db,
        tenant_id=tenant.id,
        location_id=site.id,
        targets=[
            {"recipe_id": croissant_recipe.id, "batches": Decimal("250")},
            {"recipe_id": second_recipe.id, "batches": Decimal("250")},
        ],
    )
    # Same 500 units of dough-consuming product, so the same 30.6 kg of flour.
    assert _line(plan, "Flour")["required"] == Decimal("30.600")


async def test_a_circular_recipe_is_refused_by_name(
    db: AsyncSession,
    tenant: Tenant,
    site: Location,
    dough: Ingredient,
    dough_recipe: Recipe,
    flour: Ingredient,
):
    """A bill of materials that consumes itself is not orderable. Say so."""
    loop_ingredient = await _ingredient(db, tenant, "Starter", produced=True)
    loop_recipe = Recipe(
        tenant_id=tenant.id,
        produces_ingredient_id=loop_ingredient.id,
        yield_servings=Decimal("1"),
    )
    db.add(loop_recipe)
    await db.flush()
    # Starter is made from dough...
    db.add(
        RecipeItem(
            tenant_id=tenant.id,
            recipe_id=loop_recipe.id,
            ingredient_id=dough.id,
            quantity=Decimal("1"),
            unit="kg",
        )
    )
    # ...and dough is now also made from starter.
    db.add(
        RecipeItem(
            tenant_id=tenant.id,
            recipe_id=dough_recipe.id,
            ingredient_id=loop_ingredient.id,
            quantity=Decimal("1"),
            unit="kg",
        )
    )
    await db.flush()

    with pytest.raises(SuggestionError, match="circular"):
        await _plan(db, tenant, site, loop_recipe, "1")


async def test_a_produced_ingredient_with_no_recipe_is_surfaced_not_dropped(
    db: AsyncSession,
    tenant: Tenant,
    site: Location,
    croissant_recipe: Recipe,
    dough: Ingredient,
):
    """Flagged as produced but nothing makes it: a data problem, not a zero.

    Silently dropping the requirement would under-order the whole run and give
    no clue why.
    """
    plan = await _plan(db, tenant, site, croissant_recipe, "500")
    row = _line(plan, "Croissant Dough")
    assert row is not None
    assert row["required"] == Decimal("60.000")


# ---------------------------------------------------------------------------
# SHORTFALL
# ---------------------------------------------------------------------------


async def test_stock_on_hand_reduces_the_shortfall(
    db, tenant, site, croissant_recipe, dough_recipe, flour
):
    await stock_service.move_stock(
        db,
        tenant_id=tenant.id,
        ingredient_id=flour.id,
        quantity_delta=Decimal("20"),
        transaction_type="purchase",
        location_id=site.id,
    )
    plan = await _plan(db, tenant, site, croissant_recipe, "500")
    row = _line(plan, "Flour")
    assert row["required"] == Decimal("30.600")
    assert row["on_hand"] == Decimal("20.000")
    assert row["shortfall"] == Decimal("10.600")


async def test_stock_at_another_location_does_not_count(
    db: AsyncSession,
    tenant: Tenant,
    site: Location,
    croissant_recipe: Recipe,
    dough_recipe: Recipe,
    flour: Ingredient,
):
    """Flour in the other kitchen cannot be baked with here."""
    other = Location(tenant_id=tenant.id, name="Delivery", code="DEL")
    db.add(other)
    await db.flush()
    await stock_service.move_stock(
        db,
        tenant_id=tenant.id,
        ingredient_id=flour.id,
        quantity_delta=Decimal("999"),
        transaction_type="purchase",
        location_id=other.id,
    )
    plan = await _plan(db, tenant, site, croissant_recipe, "500")
    assert _line(plan, "Flour")["on_hand"] == Decimal("0.000")
    assert _line(plan, "Flour")["shortfall"] == Decimal("30.600")


async def test_an_open_purchase_order_is_not_ordered_again(
    db: AsyncSession,
    tenant: Tenant,
    site: Location,
    croissant_recipe: Recipe,
    dough_recipe: Recipe,
    flour: Ingredient,
):
    """Running the suggestion twice in a morning must not order twice."""
    supplier = await supplier_service.create_supplier(
        db, tenant.id, {"name": "Mills", "code": "MILLS"}
    )
    po = await purchase_order_service.create_purchase_order(
        db,
        tenant_id=tenant.id,
        supplier_id=supplier.id,
        location_id=site.id,
        lines=[{"ingredient_id": flour.id, "quantity_ordered": Decimal("25")}],
    )
    await purchase_order_service.mark_sent(db, tenant_id=tenant.id, po_id=po.id)

    plan = await _plan(db, tenant, site, croissant_recipe, "500")
    row = _line(plan, "Flour")
    assert row["on_order"] == Decimal("25.000")
    assert row["shortfall"] == Decimal("5.600")


# ---------------------------------------------------------------------------
# PACK ROUNDING AND BASKETS
# ---------------------------------------------------------------------------


async def test_orders_round_up_to_whole_packs_never_down(
    db, tenant, site, croissant_recipe, dough_recipe, flour
):
    supplier = await supplier_service.create_supplier(
        db, tenant.id, {"name": "Mills", "code": "MILLS"}
    )
    await supplier_service.upsert_supplier_item(
        db,
        tenant.id,
        supplier.id,
        {
            "ingredient_id": flour.id,
            "last_price_minor": Decimal("300"),
            "pack_size": Decimal("25"),
            "is_preferred": True,
        },
    )
    plan = await _plan(db, tenant, site, croissant_recipe, "500")
    row = _line(plan, "Flour")
    # 30.6 kg needed -> two 25 kg sacks, not one and a bit.
    assert row["shortfall"] == Decimal("30.600")
    assert row["suggested_quantity"] == Decimal("50.000")
    assert row["suggested_quantity"] > row["shortfall"]
    # Priced from the supplier's price, not the ingredient master's.
    assert row["unit_price_minor"] == Decimal("300.00")
    assert row["estimated_cost_minor"] == Decimal("15000.00")


async def test_a_minimum_order_quantity_is_respected(
    db, tenant, site, croissant_recipe, dough_recipe, butter
):
    supplier = await supplier_service.create_supplier(
        db, tenant.id, {"name": "Dairy", "code": "DAIRY"}
    )
    await supplier_service.upsert_supplier_item(
        db,
        tenant.id,
        supplier.id,
        {
            "ingredient_id": butter.id,
            "last_price_minor": Decimal("1800"),
            "minimum_order_quantity": Decimal("50"),
            "is_preferred": True,
        },
    )
    plan = await _plan(db, tenant, site, croissant_recipe, "500")
    # 14.4 kg needed, but they will not sell less than 50.
    assert _line(plan, "Butter")["suggested_quantity"] == Decimal("50.000")


async def test_lines_group_into_one_basket_per_supplier(
    db, tenant, site, croissant_recipe, dough_recipe, flour, butter
):
    mills = await supplier_service.create_supplier(
        db, tenant.id, {"name": "Mills", "code": "MILLS"}
    )
    dairy = await supplier_service.create_supplier(
        db, tenant.id, {"name": "Dairy", "code": "DAIRY"}
    )
    await supplier_service.upsert_supplier_item(
        db, tenant.id, mills.id, {"ingredient_id": flour.id, "last_price_minor": Decimal("300")}
    )
    await supplier_service.upsert_supplier_item(
        db, tenant.id, dairy.id, {"ingredient_id": butter.id, "last_price_minor": Decimal("1800")}
    )

    plan = await _plan(db, tenant, site, croissant_recipe, "500")
    assert [b["supplier_name"] for b in plan["baskets"]] == ["Dairy", "Mills"]
    assert all(len(b["lines"]) == 1 for b in plan["baskets"])
    assert plan["unsourced"] == []


async def test_an_ingredient_nobody_supplies_is_flagged(
    db, tenant, site, croissant_recipe, dough_recipe, flour, butter
):
    """Not silently dropped, and not silently priced as if someone sold it."""
    plan = await _plan(db, tenant, site, croissant_recipe, "500")
    assert {r["ingredient_name"] for r in plan["unsourced"]} == {"Flour", "Butter"}
    assert plan["baskets"] == []
    assert all(r["has_supplier"] is False for r in plan["unsourced"])


async def test_the_total_is_the_sum_of_what_is_actually_ordered(
    db, tenant, site, croissant_recipe, dough_recipe, flour, butter
):
    plan = await _plan(db, tenant, site, croissant_recipe, "500")
    expected = sum(
        (r["estimated_cost_minor"] for r in plan["lines"] if r["suggested_quantity"] > 0),
        Decimal("0"),
    )
    assert plan["estimated_total_minor"] == expected
    # Magnitude: ~45 kg of flour and butter, not thousands of currency units.
    assert Decimal("1") < plan["estimated_total_minor"] / 100 < Decimal("10000")


# ---------------------------------------------------------------------------
# REFUSALS
# ---------------------------------------------------------------------------


async def test_an_empty_target_is_refused(db, tenant, site):
    with pytest.raises(SuggestionError, match="production target"):
        await purchase_suggestion_service.build_suggestion(
            db, tenant_id=tenant.id, location_id=site.id, targets=[]
        )


async def test_a_zero_batch_target_is_refused(db, tenant, site, croissant_recipe):
    with pytest.raises(SuggestionError, match="greater than zero"):
        await purchase_suggestion_service.build_suggestion(
            db,
            tenant_id=tenant.id,
            location_id=site.id,
            targets=[{"recipe_id": croissant_recipe.id, "batches": Decimal("0")}],
        )


async def test_an_unknown_recipe_is_refused(db, tenant, site):
    with pytest.raises(SuggestionError, match="No such active recipe"):
        await purchase_suggestion_service.build_suggestion(
            db,
            tenant_id=tenant.id,
            location_id=site.id,
            targets=[{"recipe_id": uuid.uuid4(), "batches": Decimal("1")}],
        )
