"""Menu service -- business logic for categories, items, modifier groups, modifiers."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.menu import (
    Category,
    MenuItem,
    MenuItemModifierGroup,
    Modifier,
    ModifierGroup,
)
from app.schemas.menu import (
    CategoryCreate,
    CategoryUpdate,
    MenuItemCreate,
    MenuItemUpdate,
    ModifierCreate,
    ModifierGroupCreate,
    ModifierGroupUpdate,
    ModifierUpdate,
)


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


async def list_categories(
    db: AsyncSession, tenant_id: uuid.UUID, active_only: bool = False
) -> list[Category]:
    stmt = (
        select(Category)
        .where(Category.tenant_id == tenant_id)
        .order_by(Category.display_order, Category.name)
    )
    if active_only:
        stmt = stmt.where(Category.is_active == True)  # noqa: E712
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_category(
    db: AsyncSession, category_id: uuid.UUID, tenant_id: uuid.UUID
) -> Category | None:
    result = await db.execute(
        select(Category).where(
            Category.id == category_id,
            Category.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_category(
    db: AsyncSession, tenant_id: uuid.UUID, data: CategoryCreate
) -> Category:
    cat = Category(
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        display_order=data.display_order,
        is_active=data.is_active,
        icon=data.icon,
    )
    db.add(cat)
    await db.flush()
    return cat


async def update_category(
    db: AsyncSession,
    category: Category,
    data: CategoryUpdate,
) -> Category:
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)
    await db.flush()
    return category


async def delete_category(db: AsyncSession, category: Category) -> None:
    await db.delete(category)
    await db.flush()


# ---------------------------------------------------------------------------
# Menu Items
# ---------------------------------------------------------------------------


async def list_menu_items(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    category_id: uuid.UUID | None = None,
    available_only: bool = False,
) -> list[MenuItem]:
    stmt = (
        select(MenuItem)
        .options(
            selectinload(MenuItem.modifier_groups).selectinload(ModifierGroup.modifiers)
        )
        .where(MenuItem.tenant_id == tenant_id)
        .order_by(MenuItem.display_order, MenuItem.name)
    )
    if category_id is not None:
        stmt = stmt.where(MenuItem.category_id == category_id)
    if available_only:
        stmt = stmt.where(MenuItem.is_available == True)  # noqa: E712
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def get_menu_item(
    db: AsyncSession, item_id: uuid.UUID, tenant_id: uuid.UUID
) -> MenuItem | None:
    result = await db.execute(
        select(MenuItem)
        .options(
            selectinload(MenuItem.modifier_groups).selectinload(ModifierGroup.modifiers)
        )
        .where(MenuItem.id == item_id, MenuItem.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def create_menu_item(
    db: AsyncSession, tenant_id: uuid.UUID, data: MenuItemCreate
) -> MenuItem:
    item = MenuItem(
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        price=data.price,
        category_id=data.category_id,
        image_url=data.image_url,
        is_available=data.is_available,
        display_order=data.display_order,
        preparation_time_minutes=data.preparation_time_minutes,
    )
    db.add(item)
    await db.flush()

    # Link modifier groups
    if data.modifier_group_ids:
        await _sync_item_modifier_groups(
            db, tenant_id, item.id, data.modifier_group_ids
        )

    # Re-fetch with relationships
    return await get_menu_item(db, item.id, tenant_id)  # type: ignore[return-value]


async def update_menu_item(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    item: MenuItem,
    data: MenuItemUpdate,
) -> MenuItem:
    update_data = data.model_dump(exclude_unset=True)
    modifier_group_ids = update_data.pop("modifier_group_ids", None)

    for field, value in update_data.items():
        setattr(item, field, value)
    await db.flush()

    if modifier_group_ids is not None:
        await _sync_item_modifier_groups(db, tenant_id, item.id, modifier_group_ids)

    return await get_menu_item(db, item.id, tenant_id)  # type: ignore[return-value]


async def delete_menu_item(db: AsyncSession, item: MenuItem) -> None:
    await db.delete(item)
    await db.flush()


async def _sync_item_modifier_groups(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    item_id: uuid.UUID,
    group_ids: list[uuid.UUID],
) -> None:
    """Replace all modifier group links for a menu item."""
    await db.execute(
        delete(MenuItemModifierGroup).where(
            MenuItemModifierGroup.menu_item_id == item_id
        )
    )
    for gid in group_ids:
        link = MenuItemModifierGroup(
            tenant_id=tenant_id,
            menu_item_id=item_id,
            modifier_group_id=gid,
        )
        db.add(link)
    await db.flush()


# ---------------------------------------------------------------------------
# Modifier Groups
# ---------------------------------------------------------------------------


async def list_modifier_groups(
    db: AsyncSession, tenant_id: uuid.UUID, active_only: bool = False
) -> list[ModifierGroup]:
    stmt = (
        select(ModifierGroup)
        .options(selectinload(ModifierGroup.modifiers))
        .where(ModifierGroup.tenant_id == tenant_id)
        .order_by(ModifierGroup.display_order, ModifierGroup.name)
    )
    if active_only:
        stmt = stmt.where(ModifierGroup.is_active == True)  # noqa: E712
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def get_modifier_group(
    db: AsyncSession, group_id: uuid.UUID, tenant_id: uuid.UUID
) -> ModifierGroup | None:
    result = await db.execute(
        select(ModifierGroup)
        .options(selectinload(ModifierGroup.modifiers))
        .where(ModifierGroup.id == group_id, ModifierGroup.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def create_modifier_group(
    db: AsyncSession, tenant_id: uuid.UUID, data: ModifierGroupCreate
) -> ModifierGroup:
    group = ModifierGroup(
        tenant_id=tenant_id,
        name=data.name,
        display_order=data.display_order,
        required=data.required,
        min_selections=data.min_selections,
        max_selections=data.max_selections,
        is_active=data.is_active,
    )
    db.add(group)
    await db.flush()

    # Create inline modifiers if provided
    for mod_data in data.modifiers:
        mod = Modifier(
            tenant_id=tenant_id,
            group_id=group.id,
            name=mod_data.name,
            price_adjustment=mod_data.price_adjustment,
            display_order=mod_data.display_order,
            is_available=mod_data.is_available,
        )
        db.add(mod)
    await db.flush()

    return await get_modifier_group(db, group.id, tenant_id)  # type: ignore[return-value]


async def update_modifier_group(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    group: ModifierGroup,
    data: ModifierGroupUpdate,
) -> ModifierGroup:
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(group, field, value)
    await db.flush()
    return await get_modifier_group(db, group.id, tenant_id)  # type: ignore[return-value]


async def delete_modifier_group(db: AsyncSession, group: ModifierGroup) -> None:
    await db.delete(group)
    await db.flush()


# ---------------------------------------------------------------------------
# Modifiers
# ---------------------------------------------------------------------------


async def create_modifier(
    db: AsyncSession, tenant_id: uuid.UUID, group_id: uuid.UUID, data: ModifierCreate
) -> Modifier:
    mod = Modifier(
        tenant_id=tenant_id,
        group_id=group_id,
        name=data.name,
        price_adjustment=data.price_adjustment,
        display_order=data.display_order,
        is_available=data.is_available,
    )
    db.add(mod)
    await db.flush()
    return mod


async def update_modifier(
    db: AsyncSession,
    modifier: Modifier,
    data: ModifierUpdate,
) -> Modifier:
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(modifier, field, value)
    await db.flush()
    return modifier


async def delete_modifier(db: AsyncSession, modifier: Modifier) -> None:
    await db.delete(modifier)
    await db.flush()


async def get_modifier(
    db: AsyncSession, modifier_id: uuid.UUID, tenant_id: uuid.UUID
) -> Modifier | None:
    result = await db.execute(
        select(Modifier).where(
            Modifier.id == modifier_id,
            Modifier.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Full Menu Tree
# ---------------------------------------------------------------------------


async def get_full_menu(db: AsyncSession, tenant_id: uuid.UUID) -> list[Category]:
    """Fetch the complete menu tree: active categories -> available items -> modifier groups -> modifiers."""
    result = await db.execute(
        select(Category)
        .options(
            selectinload(Category.items)
            .selectinload(MenuItem.modifier_groups)
            .selectinload(ModifierGroup.modifiers)
        )
        .where(
            Category.tenant_id == tenant_id,
            Category.is_active == True,  # noqa: E712
        )
        .order_by(Category.display_order, Category.name)
    )
    categories = list(result.scalars().unique().all())

    # Filter to available items only (in-memory to avoid complex subquery)
    for cat in categories:
        cat.items = [item for item in cat.items if item.is_available]
        cat.items.sort(key=lambda i: (i.display_order, i.name))

    return categories
