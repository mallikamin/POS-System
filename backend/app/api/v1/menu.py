"""Menu endpoints -- categories, items, modifier groups, modifiers, full menu tree."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.database import get_db
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.menu import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    FullMenuResponse,
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate,
    ModifierCreate,
    ModifierGroupCreate,
    ModifierGroupResponse,
    ModifierGroupUpdate,
    ModifierResponse,
    ModifierUpdate,
)
from app.services import menu_service

router = APIRouter(prefix="/menu", tags=["menu"])

# Shared admin dependency — avoids double auth execution
_admin_dep = require_role("admin")


# ---------------------------------------------------------------------------
# Full Menu Tree (POS frontend uses this)
# ---------------------------------------------------------------------------

@router.get("/full", response_model=FullMenuResponse)
async def get_full_menu(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FullMenuResponse:
    """Return the complete menu tree for the POS frontend."""
    categories = await menu_service.get_full_menu(db, current_user.tenant_id)
    return FullMenuResponse(categories=categories)


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(
    active_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CategoryResponse]:
    cats = await menu_service.list_categories(db, current_user.tenant_id, active_only)
    return [CategoryResponse.model_validate(c) for c in cats]


@router.get("/categories/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    cat = await menu_service.get_category(db, category_id, current_user.tenant_id)
    if cat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return CategoryResponse.model_validate(cat)


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    body: CategoryCreate,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    cat = await menu_service.create_category(db, current_user.tenant_id, body)
    return CategoryResponse.model_validate(cat)


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    cat = await menu_service.get_category(db, category_id, current_user.tenant_id)
    if cat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    updated = await menu_service.update_category(db, cat, body)
    return CategoryResponse.model_validate(updated)


@router.delete("/categories/{category_id}", response_model=MessageResponse)
async def delete_category(
    category_id: uuid.UUID,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    cat = await menu_service.get_category(db, category_id, current_user.tenant_id)
    if cat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    await menu_service.delete_category(db, cat)
    return MessageResponse(message="Category deleted")


# ---------------------------------------------------------------------------
# Menu Items
# ---------------------------------------------------------------------------

@router.get("/items", response_model=list[MenuItemResponse])
async def list_menu_items(
    category_id: uuid.UUID | None = Query(None),
    available_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MenuItemResponse]:
    items = await menu_service.list_menu_items(
        db, current_user.tenant_id, category_id, available_only
    )
    return [MenuItemResponse.model_validate(i) for i in items]


@router.get("/items/{item_id}", response_model=MenuItemResponse)
async def get_menu_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    item = await menu_service.get_menu_item(db, item_id, current_user.tenant_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")
    return MenuItemResponse.model_validate(item)


@router.post(
    "/items",
    response_model=MenuItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_menu_item(
    body: MenuItemCreate,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    item = await menu_service.create_menu_item(db, current_user.tenant_id, body)
    return MenuItemResponse.model_validate(item)


@router.patch("/items/{item_id}", response_model=MenuItemResponse)
async def update_menu_item(
    item_id: uuid.UUID,
    body: MenuItemUpdate,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    item = await menu_service.get_menu_item(db, item_id, current_user.tenant_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")
    updated = await menu_service.update_menu_item(db, current_user.tenant_id, item, body)
    return MenuItemResponse.model_validate(updated)


@router.delete("/items/{item_id}", response_model=MessageResponse)
async def delete_menu_item(
    item_id: uuid.UUID,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    item = await menu_service.get_menu_item(db, item_id, current_user.tenant_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")
    await menu_service.delete_menu_item(db, item)
    return MessageResponse(message="Menu item deleted")


# ---------------------------------------------------------------------------
# Modifier Groups
# ---------------------------------------------------------------------------

@router.get("/modifier-groups", response_model=list[ModifierGroupResponse])
async def list_modifier_groups(
    active_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ModifierGroupResponse]:
    groups = await menu_service.list_modifier_groups(
        db, current_user.tenant_id, active_only
    )
    return [ModifierGroupResponse.model_validate(g) for g in groups]


@router.get("/modifier-groups/{group_id}", response_model=ModifierGroupResponse)
async def get_modifier_group(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ModifierGroupResponse:
    group = await menu_service.get_modifier_group(db, group_id, current_user.tenant_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Modifier group not found")
    return ModifierGroupResponse.model_validate(group)


@router.post(
    "/modifier-groups",
    response_model=ModifierGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_modifier_group(
    body: ModifierGroupCreate,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> ModifierGroupResponse:
    group = await menu_service.create_modifier_group(db, current_user.tenant_id, body)
    return ModifierGroupResponse.model_validate(group)


@router.patch("/modifier-groups/{group_id}", response_model=ModifierGroupResponse)
async def update_modifier_group(
    group_id: uuid.UUID,
    body: ModifierGroupUpdate,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> ModifierGroupResponse:
    group = await menu_service.get_modifier_group(db, group_id, current_user.tenant_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Modifier group not found")
    updated = await menu_service.update_modifier_group(
        db, current_user.tenant_id, group, body
    )
    return ModifierGroupResponse.model_validate(updated)


@router.delete("/modifier-groups/{group_id}", response_model=MessageResponse)
async def delete_modifier_group(
    group_id: uuid.UUID,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    group = await menu_service.get_modifier_group(db, group_id, current_user.tenant_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Modifier group not found")
    await menu_service.delete_modifier_group(db, group)
    return MessageResponse(message="Modifier group deleted")


# ---------------------------------------------------------------------------
# Modifiers (within a group)
# ---------------------------------------------------------------------------

@router.post(
    "/modifier-groups/{group_id}/modifiers",
    response_model=ModifierResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_modifier(
    group_id: uuid.UUID,
    body: ModifierCreate,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> ModifierResponse:
    group = await menu_service.get_modifier_group(db, group_id, current_user.tenant_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Modifier group not found")
    mod = await menu_service.create_modifier(db, current_user.tenant_id, group_id, body)
    return ModifierResponse.model_validate(mod)


@router.patch("/modifiers/{modifier_id}", response_model=ModifierResponse)
async def update_modifier(
    modifier_id: uuid.UUID,
    body: ModifierUpdate,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> ModifierResponse:
    mod = await menu_service.get_modifier(db, modifier_id, current_user.tenant_id)
    if mod is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Modifier not found")
    updated = await menu_service.update_modifier(db, mod, body)
    return ModifierResponse.model_validate(updated)


@router.delete("/modifiers/{modifier_id}", response_model=MessageResponse)
async def delete_modifier(
    modifier_id: uuid.UUID,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    mod = await menu_service.get_modifier(db, modifier_id, current_user.tenant_id)
    if mod is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Modifier not found")
    await menu_service.delete_modifier(db, mod)
    return MessageResponse(message="Modifier deleted")
