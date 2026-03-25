"""Recipe and ingredient business logic."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import Ingredient, Recipe, RecipeItem
from app.models.menu import MenuItem
from app.schemas.inventory import (
    IngredientCreate,
    IngredientUpdate,
    RecipeCreate,
    RecipeItemCreate,
    RecipeUpdate,
)


# ---------------------------------------------------------------------------
# INGREDIENT CRUD
# ---------------------------------------------------------------------------


async def create_ingredient(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: IngredientCreate,
) -> Ingredient:
    """Create a new ingredient."""
    ingredient = Ingredient(
        tenant_id=tenant_id,
        **data.model_dump(),
    )
    db.add(ingredient)
    await db.flush()
    await db.refresh(ingredient)
    return ingredient


async def get_ingredient(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    ingredient_id: uuid.UUID,
) -> Ingredient | None:
    """Get ingredient by ID."""
    result = await db.execute(
        select(Ingredient).where(
            Ingredient.id == ingredient_id,
            Ingredient.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def list_ingredients(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    category: str | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Ingredient]:
    """List ingredients with optional filters."""
    query = select(Ingredient).where(Ingredient.tenant_id == tenant_id)

    if category is not None:
        query = query.where(Ingredient.category == category)
    if is_active is not None:
        query = query.where(Ingredient.is_active == is_active)

    query = query.order_by(Ingredient.category, Ingredient.name)
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


async def update_ingredient(
    db: AsyncSession,
    ingredient: Ingredient,
    data: IngredientUpdate,
) -> Ingredient:
    """Update ingredient fields."""
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(ingredient, field, value)

    await db.flush()
    await db.refresh(ingredient)
    return ingredient


async def delete_ingredient(
    db: AsyncSession,
    ingredient: Ingredient,
) -> None:
    """Soft-delete ingredient (set is_active=False)."""
    ingredient.is_active = False
    await db.flush()


# ---------------------------------------------------------------------------
# RECIPE CRUD
# ---------------------------------------------------------------------------


async def create_recipe(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: RecipeCreate,
    user_id: uuid.UUID,
) -> Recipe:
    """Create a new recipe with recipe items.

    Automatically calculates total cost and cost per serving.
    """
    # Verify menu item exists and belongs to tenant
    menu_item_result = await db.execute(
        select(MenuItem).where(
            MenuItem.id == data.menu_item_id,
            MenuItem.tenant_id == tenant_id,
        )
    )
    menu_item = menu_item_result.scalar_one_or_none()
    if not menu_item:
        raise ValueError("Menu item not found")

    # Check if an active recipe already exists for this menu item
    existing_recipe_result = await db.execute(
        select(Recipe).where(
            Recipe.menu_item_id == data.menu_item_id,
            Recipe.tenant_id == tenant_id,
            Recipe.is_active == True,
        )
    )
    existing_recipe = existing_recipe_result.scalar_one_or_none()

    # If exists, deactivate it (new version)
    version = 1
    if existing_recipe:
        existing_recipe.is_active = False
        version = existing_recipe.version + 1

    # Create recipe
    recipe = Recipe(
        tenant_id=tenant_id,
        menu_item_id=data.menu_item_id,
        version=version,
        yield_servings=data.yield_servings,
        prep_time_minutes=data.prep_time_minutes,
        cook_time_minutes=data.cook_time_minutes,
        instructions=data.instructions,
        notes=data.notes,
        is_active=True,
        effective_date=datetime.now(timezone.utc),
        created_by=user_id,
    )
    db.add(recipe)
    await db.flush()

    # Create recipe items and calculate cost
    total_cost = Decimal(0)
    for item_data in data.recipe_items:
        # Get ingredient with current cost
        ingredient_result = await db.execute(
            select(Ingredient).where(
                Ingredient.id == item_data.ingredient_id,
                Ingredient.tenant_id == tenant_id,
            )
        )
        ingredient = ingredient_result.scalar_one_or_none()
        if not ingredient:
            raise ValueError(f"Ingredient {item_data.ingredient_id} not found")

        # Calculate cost including waste
        cost_per_unit = ingredient.cost_per_unit
        waste_multiplier = Decimal(1) + (item_data.waste_factor / Decimal(100))
        item_total_cost = (
            item_data.quantity * cost_per_unit * waste_multiplier
        )

        recipe_item = RecipeItem(
            tenant_id=tenant_id,
            recipe_id=recipe.id,
            ingredient_id=item_data.ingredient_id,
            quantity=item_data.quantity,
            unit=item_data.unit,
            waste_factor=item_data.waste_factor,
            cost_per_unit_snapshot=cost_per_unit,
            total_cost=item_total_cost,
            notes=item_data.notes,
        )
        db.add(recipe_item)
        total_cost += item_total_cost

    # Update recipe totals
    recipe.total_ingredient_cost = total_cost
    recipe.cost_per_serving = total_cost / data.yield_servings

    await db.flush()
    await db.refresh(recipe, ["recipe_items"])
    return recipe


async def get_recipe(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    recipe_id: uuid.UUID,
) -> Recipe | None:
    """Get recipe with items."""
    result = await db.execute(
        select(Recipe)
        .options(selectinload(Recipe.recipe_items))
        .where(
            Recipe.id == recipe_id,
            Recipe.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def get_recipe_by_menu_item(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    menu_item_id: uuid.UUID,
) -> Recipe | None:
    """Get active recipe for a menu item."""
    result = await db.execute(
        select(Recipe)
        .options(selectinload(Recipe.recipe_items))
        .where(
            Recipe.menu_item_id == menu_item_id,
            Recipe.tenant_id == tenant_id,
            Recipe.is_active == True,
        )
    )
    return result.scalar_one_or_none()


async def list_recipes(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Recipe]:
    """List recipes."""
    query = (
        select(Recipe)
        .options(selectinload(Recipe.recipe_items))
        .where(Recipe.tenant_id == tenant_id)
    )

    if is_active is not None:
        query = query.where(Recipe.is_active == is_active)

    query = query.order_by(Recipe.created_at.desc())
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


async def update_recipe(
    db: AsyncSession,
    recipe: Recipe,
    data: RecipeUpdate,
    user_id: uuid.UUID,
) -> Recipe:
    """Update recipe.

    If recipe_items are provided, creates a new version.
    Otherwise, updates metadata only.
    """
    if data.recipe_items is not None:
        # Creating new version - deactivate current and create new
        recipe.is_active = False
        await db.flush()

        # Build new recipe data
        new_recipe_data = RecipeCreate(
            menu_item_id=recipe.menu_item_id,
            yield_servings=data.yield_servings or recipe.yield_servings,
            prep_time_minutes=data.prep_time_minutes or recipe.prep_time_minutes,
            cook_time_minutes=data.cook_time_minutes or recipe.cook_time_minutes,
            instructions=data.instructions or recipe.instructions,
            notes=data.notes or recipe.notes,
            recipe_items=data.recipe_items,
        )

        return await create_recipe(
            db, recipe.tenant_id, new_recipe_data, user_id
        )
    else:
        # Just update metadata
        update_data = data.model_dump(exclude_unset=True, exclude={"recipe_items"})
        for field, value in update_data.items():
            setattr(recipe, field, value)

        await db.flush()
        await db.refresh(recipe)
        return recipe


async def delete_recipe(
    db: AsyncSession,
    recipe: Recipe,
) -> None:
    """Soft-delete recipe (set is_active=False)."""
    recipe.is_active = False
    await db.flush()


# ---------------------------------------------------------------------------
# COST SIMULATION
# ---------------------------------------------------------------------------


async def simulate_recipe_cost(
    db: AsyncSession,
    recipe: Recipe,
    ingredient_price_changes: dict[str, Decimal],
) -> dict:
    """Simulate cost impact of ingredient price changes.

    Args:
        recipe: Recipe to simulate
        ingredient_price_changes: Map of ingredient_id -> new cost_per_unit

    Returns:
        Dict with original vs new costs and breakdown
    """
    affected = []
    new_total_cost = Decimal(0)

    for item in recipe.recipe_items:
        ingredient_id_str = str(item.ingredient_id)
        new_cost_per_unit = ingredient_price_changes.get(
            ingredient_id_str, item.cost_per_unit_snapshot
        )

        # Recalculate item cost with new price
        waste_multiplier = Decimal(1) + (item.waste_factor / Decimal(100))
        new_item_cost = item.quantity * new_cost_per_unit * waste_multiplier

        new_total_cost += new_item_cost

        if ingredient_id_str in ingredient_price_changes:
            # This ingredient's price changed
            cost_change = new_item_cost - item.total_cost
            affected.append(
                {
                    "ingredient_id": ingredient_id_str,
                    "quantity": float(item.quantity),
                    "old_cost_per_unit": float(item.cost_per_unit_snapshot),
                    "new_cost_per_unit": float(new_cost_per_unit),
                    "old_item_cost": float(item.total_cost),
                    "new_item_cost": float(new_item_cost),
                    "cost_change": float(cost_change),
                }
            )

    original_total = recipe.total_ingredient_cost
    cost_difference = new_total_cost - original_total
    percentage_change = (
        (cost_difference / original_total * Decimal(100))
        if original_total > 0
        else Decimal(0)
    )

    return {
        "original_total_cost": float(original_total),
        "new_total_cost": float(new_total_cost),
        "cost_difference": float(cost_difference),
        "percentage_change": float(percentage_change),
        "original_cost_per_serving": float(recipe.cost_per_serving),
        "new_cost_per_serving": float(new_total_cost / recipe.yield_servings),
        "affected_ingredients": affected,
    }
