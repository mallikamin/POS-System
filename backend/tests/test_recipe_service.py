"""Tests for recipe_service, including the new sub-recipe (multi-layer
production chain) capability added for the FZ LLC UAE lead.

No test coverage existed for this module before this file (BOM_IMPLEMENTATION_
STATUS.md marks it "100% Complete" but nothing here was ever exercised in CI) --
this is the first pass, focused on the new produces_ingredient_id code path
and a regression check that plain menu-item recipes still work.
"""

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Ingredient
from app.models.menu import Category, MenuItem
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.inventory import RecipeCreate, RecipeItemCreate
from app.services import recipe_service


@pytest_asyncio.fixture
async def category(db: AsyncSession, tenant: Tenant) -> Category:
    cat = Category(tenant_id=tenant.id, name="Pastries", display_order=0, is_active=True)
    db.add(cat)
    await db.flush()
    return cat


@pytest_asyncio.fixture
async def menu_item(db: AsyncSession, tenant: Tenant, category: Category) -> MenuItem:
    item = MenuItem(
        tenant_id=tenant.id,
        category_id=category.id,
        name="Chicken Croissant",
        price=1600,
        is_available=True,
    )
    db.add(item)
    await db.flush()
    return item


@pytest_asyncio.fixture
async def flour(db: AsyncSession, tenant: Tenant) -> Ingredient:
    ing = Ingredient(
        tenant_id=tenant.id, name="Flour", category="Bakery", unit="kg",
        cost_per_unit=Decimal("3.50"), is_active=True, is_produced=False,
    )
    db.add(ing)
    await db.flush()
    return ing


@pytest_asyncio.fixture
async def butter(db: AsyncSession, tenant: Tenant) -> Ingredient:
    ing = Ingredient(
        tenant_id=tenant.id, name="Butter", category="Dairy", unit="kg",
        cost_per_unit=Decimal("28.00"), is_active=True, is_produced=False,
    )
    db.add(ing)
    await db.flush()
    return ing


async def test_create_recipe_for_menu_item_still_works(
    db: AsyncSession, tenant: Tenant, admin_user: User, menu_item: MenuItem, flour: Ingredient
) -> None:
    """Regression: plain single-layer recipes (the only kind before this
    change) must keep working unmodified."""
    recipe = await recipe_service.create_recipe(
        db,
        tenant.id,
        RecipeCreate(
            menu_item_id=menu_item.id,
            yield_servings=Decimal("1"),
            recipe_items=[
                RecipeItemCreate(ingredient_id=flour.id, quantity=Decimal("0.2"), unit="kg", waste_factor=Decimal("0"))
            ],
        ),
        admin_user.id,
    )
    assert recipe.menu_item_id == menu_item.id
    assert recipe.produces_ingredient_id is None
    assert recipe.total_ingredient_cost == Decimal("0.70")  # 0.2kg * 3.50


async def test_recipe_target_validation_rejects_both_and_neither() -> None:
    """Schema-level guard: a recipe must target exactly one of menu_item_id
    or produces_ingredient_id."""
    import uuid

    with pytest.raises(ValueError):
        RecipeCreate(menu_item_id=uuid.uuid4(), produces_ingredient_id=uuid.uuid4())

    with pytest.raises(ValueError):
        RecipeCreate()


async def test_sub_recipe_produces_ingredient_and_syncs_cost(
    db: AsyncSession, tenant: Tenant, admin_user: User, flour: Ingredient, butter: Ingredient
) -> None:
    """A recipe targeting produces_ingredient_id creates the multi-layer
    production chain: it marks the target ingredient is_produced and rolls
    its cost_per_unit up from the sub-recipe's own cost_per_serving."""
    dough = Ingredient(
        tenant_id=tenant.id, name="Croissant Dough", category="Produced", unit="kg",
        cost_per_unit=0, is_active=True, is_produced=False,
    )
    db.add(dough)
    await db.flush()

    recipe = await recipe_service.create_recipe(
        db,
        tenant.id,
        RecipeCreate(
            produces_ingredient_id=dough.id,
            yield_servings=Decimal("5"),  # batch yields 5 kg of dough
            recipe_items=[
                RecipeItemCreate(ingredient_id=flour.id, quantity=Decimal("2.5"), unit="kg", waste_factor=Decimal("0")),
                RecipeItemCreate(ingredient_id=butter.id, quantity=Decimal("1.0"), unit="kg", waste_factor=Decimal("0")),
            ],
        ),
        admin_user.id,
    )

    await db.refresh(dough)
    assert dough.is_produced is True
    # total batch cost = 2.5*3.50 + 1.0*28.00 = 8.75 + 28.00 = 36.75, / 5kg yield = 7.35/kg
    assert recipe.cost_per_serving == Decimal("7.35")
    assert dough.cost_per_unit == Decimal("7.35")


async def test_final_recipe_rolls_up_sub_recipe_cost(
    db: AsyncSession, tenant: Tenant, admin_user: User, menu_item: MenuItem,
    flour: Ingredient, butter: Ingredient,
) -> None:
    """The full chain: raw ingredients -> sub-recipe (produced ingredient)
    -> final menu-item recipe, cost rolls up automatically because the
    consuming recipe just reads the produced ingredient's cost_per_unit."""
    dough = Ingredient(
        tenant_id=tenant.id, name="Croissant Dough", category="Produced", unit="kg",
        cost_per_unit=0, is_active=True, is_produced=False,
    )
    db.add(dough)
    await db.flush()

    await recipe_service.create_recipe(
        db,
        tenant.id,
        RecipeCreate(
            produces_ingredient_id=dough.id,
            yield_servings=Decimal("5"),
            recipe_items=[
                RecipeItemCreate(ingredient_id=flour.id, quantity=Decimal("2.5"), unit="kg", waste_factor=Decimal("0")),
                RecipeItemCreate(ingredient_id=butter.id, quantity=Decimal("1.0"), unit="kg", waste_factor=Decimal("0")),
            ],
        ),
        admin_user.id,
    )
    await db.refresh(dough)  # dough.cost_per_unit is now 7.35/kg

    final = await recipe_service.create_recipe(
        db,
        tenant.id,
        RecipeCreate(
            menu_item_id=menu_item.id,
            yield_servings=Decimal("1"),
            recipe_items=[
                RecipeItemCreate(ingredient_id=dough.id, quantity=Decimal("0.15"), unit="kg", waste_factor=Decimal("0")),
            ],
        ),
        admin_user.id,
    )

    # 0.15kg of dough at 7.35 AED/kg = 1.1025, matching what the recipe
    # engine would compute for ANY ingredient -- the multi-layer rollup is
    # transparent, no special-case cost logic needed for produced inputs.
    assert final.cost_per_serving == Decimal("1.1025")
