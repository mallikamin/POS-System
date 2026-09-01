"""BOM & Inventory API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.inventory import (
    IngredientCreate,
    IngredientResponse,
    IngredientUpdate,
    RecipeCostSimulation,
    RecipeCostSimulationResult,
    RecipeCreate,
    RecipeResponse,
    RecipeUpdate,
)
from app.services import order_service, recipe_service
from app.services.order_service import net_of_tax

router = APIRouter(prefix="/inventory", tags=["inventory"])


def _enrich_recipe(recipe, tax_settings: tuple[int, bool]) -> RecipeResponse:
    """Label a recipe by whatever it produces, and cost it against its price.

    A recipe has no name column of its own: it is identified by its target. A
    normal recipe is named after its menu item; a sub-recipe after the
    ingredient it makes (dough, sauce, stuffing); an add-on recipe after its
    modifier. The list endpoint previously did none of this, so sub-recipes and
    menu-item recipes alike arrived at the UI with nothing to display.

    `tax_settings` is the tenant's `(rate_bps, prices_include_tax)` from
    `order_service._get_tax_settings`. Food cost is a share of what the business
    keeps, so the divisor is the price NET of any tax it contains (F13); the
    same helper the order path uses backs it out, so the two cannot drift. An
    add-on is costed against its own `price_adjustment` on the same basis, so a
    modifier's food cost % means the same thing as an item's.

    Requires `menu_item`, `produces_ingredient` and `modifier` to be
    eager-loaded.
    """
    response = RecipeResponse.model_validate(recipe)
    rate_bps, prices_include_tax = tax_settings

    if recipe.menu_item is not None:
        response.menu_item_name = recipe.menu_item.name
        response.menu_item_price = recipe.menu_item.price
        net_price = net_of_tax(recipe.menu_item.price, rate_bps, prices_include_tax)
        response.menu_item_net_price = net_price
        if net_price > 0:
            # Net price and recipe cost are both in minor units.
            response.food_cost_percentage = recipe.cost_per_serving / net_price * 100
    elif recipe.modifier is not None:
        response.modifier_name = recipe.modifier.name
        response.modifier_price = recipe.modifier.price_adjustment
        # The list/get paths eager-load `.group`; the refresh-after-write paths
        # do not, and touching an unloaded relationship on an async session
        # raises MissingGreenlet. Asked, not assumed: the group name is a label,
        # never worth a failed write response.
        if "group" not in sa_inspect(recipe.modifier).unloaded:
            response.modifier_group_name = recipe.modifier.group.name
        # A free add-on (or one that discounts the line) has no price to divide
        # by, so it gets a cost with no percentage rather than a misleading one.
        if recipe.modifier.price_adjustment > 0:
            net_price = net_of_tax(
                recipe.modifier.price_adjustment, rate_bps, prices_include_tax
            )
            if net_price > 0:
                response.food_cost_percentage = (
                    recipe.cost_per_serving / net_price * 100
                )
    elif recipe.produces_ingredient is not None:
        response.produces_ingredient_name = recipe.produces_ingredient.name

    return response


# ---------------------------------------------------------------------------
# INGREDIENT ENDPOINTS
# ---------------------------------------------------------------------------


@router.post(
    "/ingredients",
    response_model=IngredientResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin"))],
)
async def create_ingredient(
    data: IngredientCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IngredientResponse:
    """Create a new ingredient."""
    ingredient = await recipe_service.create_ingredient(
        db, current_user.tenant_id, data
    )
    await db.commit()
    return IngredientResponse.model_validate(ingredient)


@router.get("/ingredients", response_model=list[IngredientResponse])
async def list_ingredients(
    category: str | None = Query(None),
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[IngredientResponse]:
    """List all ingredients with optional filters."""
    ingredients = await recipe_service.list_ingredients(
        db,
        current_user.tenant_id,
        category=category,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return [IngredientResponse.model_validate(i) for i in ingredients]


@router.get("/ingredients/{ingredient_id}", response_model=IngredientResponse)
async def get_ingredient(
    ingredient_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IngredientResponse:
    """Get ingredient by ID."""
    ingredient = await recipe_service.get_ingredient(
        db, current_user.tenant_id, ingredient_id
    )
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found",
        )
    return IngredientResponse.model_validate(ingredient)


@router.patch(
    "/ingredients/{ingredient_id}",
    response_model=IngredientResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def update_ingredient(
    ingredient_id: uuid.UUID,
    data: IngredientUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IngredientResponse:
    """Update ingredient fields."""
    ingredient = await recipe_service.get_ingredient(
        db, current_user.tenant_id, ingredient_id
    )
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found",
        )

    updated = await recipe_service.update_ingredient(db, ingredient, data)
    await db.commit()
    return IngredientResponse.model_validate(updated)


@router.delete(
    "/ingredients/{ingredient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("admin"))],
    response_model=None,
)
async def delete_ingredient(
    ingredient_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete ingredient (sets is_active=False)."""
    ingredient = await recipe_service.get_ingredient(
        db, current_user.tenant_id, ingredient_id
    )
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found",
        )

    await recipe_service.delete_ingredient(db, ingredient)
    await db.commit()


# ---------------------------------------------------------------------------
# RECIPE ENDPOINTS
# ---------------------------------------------------------------------------


@router.post(
    "/recipes",
    response_model=RecipeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin"))],
)
async def create_recipe(
    data: RecipeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecipeResponse:
    """Create a new recipe.

    Automatically deactivates any existing active recipe for the menu item (versioning).
    Calculates total cost and cost per serving based on current ingredient prices.
    """
    try:
        recipe = await recipe_service.create_recipe(
            db, current_user.tenant_id, data, current_user.id
        )
        await db.commit()
        # Re-fetched, NOT partially refreshed. `db.refresh(obj, [names])` left
        # every column outside that list unloaded, so building the response
        # touched `updated_at` and raised MissingGreenlet -- a 400 on every
        # recipe save, for every tenant, through this endpoint. Found on
        # 2026-09-01 by walking the client's own UAT path over HTTP; the
        # service-level tests never saw it because they never came through the
        # route. `get_recipe` eager-loads every label this response needs.
        saved = await recipe_service.get_recipe(db, current_user.tenant_id, recipe.id)
        tax_settings = await order_service._get_tax_settings(db, current_user.tenant_id)
        return _enrich_recipe(saved, tax_settings)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/recipes", response_model=list[RecipeResponse])
async def list_recipes(
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RecipeResponse]:
    """List all recipes with optional filters."""
    recipes = await recipe_service.list_recipes(
        db,
        current_user.tenant_id,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )

    tax_settings = await order_service._get_tax_settings(db, current_user.tenant_id)
    return [_enrich_recipe(r, tax_settings) for r in recipes]


@router.get("/recipes/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(
    recipe_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecipeResponse:
    """Get recipe by ID with all recipe items."""
    recipe = await recipe_service.get_recipe(
        db, current_user.tenant_id, recipe_id
    )
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found",
        )

    await db.refresh(recipe, ["menu_item", "produces_ingredient", "modifier"])
    tax_settings = await order_service._get_tax_settings(db, current_user.tenant_id)
    return _enrich_recipe(recipe, tax_settings)


@router.get(
    "/recipes/by-menu-item/{menu_item_id}",
    response_model=RecipeResponse,
)
async def get_recipe_by_menu_item(
    menu_item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecipeResponse:
    """Get active recipe for a menu item."""
    recipe = await recipe_service.get_recipe_by_menu_item(
        db, current_user.tenant_id, menu_item_id
    )
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active recipe found for this menu item",
        )

    await db.refresh(recipe, ["menu_item", "produces_ingredient", "modifier"])
    tax_settings = await order_service._get_tax_settings(db, current_user.tenant_id)
    return _enrich_recipe(recipe, tax_settings)


@router.patch(
    "/recipes/{recipe_id}",
    response_model=RecipeResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def update_recipe(
    recipe_id: uuid.UUID,
    data: RecipeUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecipeResponse:
    """Update recipe.

    If recipe_items are provided, creates a new version.
    Otherwise, updates metadata only (prep time, notes, etc.).
    """
    recipe = await recipe_service.get_recipe(
        db, current_user.tenant_id, recipe_id
    )
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found",
        )

    try:
        updated = await recipe_service.update_recipe(
            db, recipe, data, current_user.id
        )
        await db.commit()
        # Re-fetched rather than partially refreshed, same reason as the create
        # route above: a partial refresh left `updated_at` unloaded and every
        # save that cut a new version came back as a 400.
        saved = await recipe_service.get_recipe(db, current_user.tenant_id, updated.id)
        tax_settings = await order_service._get_tax_settings(db, current_user.tenant_id)
        return _enrich_recipe(saved, tax_settings)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/recipes/{recipe_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("admin"))],
    response_model=None,
)
async def delete_recipe(
    recipe_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete recipe (sets is_active=False)."""
    recipe = await recipe_service.get_recipe(
        db, current_user.tenant_id, recipe_id
    )
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found",
        )

    await recipe_service.delete_recipe(db, recipe)
    await db.commit()


# ---------------------------------------------------------------------------
# COST SIMULATION
# ---------------------------------------------------------------------------


@router.post(
    "/recipes/{recipe_id}/simulate-cost",
    response_model=RecipeCostSimulationResult,
)
async def simulate_recipe_cost(
    recipe_id: uuid.UUID,
    data: RecipeCostSimulation,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecipeCostSimulationResult:
    """Simulate cost impact of ingredient price changes.

    Useful for "what-if" analysis when suppliers change prices.
    """
    recipe = await recipe_service.get_recipe(
        db, current_user.tenant_id, recipe_id
    )
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found",
        )

    result = await recipe_service.simulate_recipe_cost(
        db, recipe, data.ingredient_price_changes
    )

    return RecipeCostSimulationResult(**result)
