"""BOM & Inventory API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
from app.services import recipe_service

router = APIRouter(prefix="/inventory", tags=["inventory"])


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
        await db.refresh(recipe, ["recipe_items", "menu_item"])

        # Build response with enriched data
        response = RecipeResponse.model_validate(recipe)
        if recipe.menu_item:
            response.menu_item_name = recipe.menu_item.name
            response.menu_item_price = recipe.menu_item.price

            # Calculate food cost percentage
            if recipe.menu_item.price > 0:
                # menu price is in paisa, cost is also in paisa
                response.food_cost_percentage = (
                    recipe.cost_per_serving / recipe.menu_item.price * 100
                )

        return response

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

    return [
        RecipeResponse.model_validate(r) for r in recipes
    ]


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

    await db.refresh(recipe, ["menu_item"])
    response = RecipeResponse.model_validate(recipe)

    if recipe.menu_item:
        response.menu_item_name = recipe.menu_item.name
        response.menu_item_price = recipe.menu_item.price
        if recipe.menu_item.price > 0:
            response.food_cost_percentage = (
                recipe.cost_per_serving / recipe.menu_item.price * 100
            )

    return response


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

    await db.refresh(recipe, ["menu_item"])
    response = RecipeResponse.model_validate(recipe)

    if recipe.menu_item:
        response.menu_item_name = recipe.menu_item.name
        response.menu_item_price = recipe.menu_item.price
        if recipe.menu_item.price > 0:
            response.food_cost_percentage = (
                recipe.cost_per_serving / recipe.menu_item.price * 100
            )

    return response


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
        await db.refresh(updated, ["recipe_items", "menu_item"])

        response = RecipeResponse.model_validate(updated)
        if updated.menu_item:
            response.menu_item_name = updated.menu_item.name
            response.menu_item_price = updated.menu_item.price
            if updated.menu_item.price > 0:
                response.food_cost_percentage = (
                    updated.cost_per_serving / updated.menu_item.price * 100
                )

        return response

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
