"""Reading the public menu must never write to the database.

The bug these defend against, found on prod 2026-10-02:

    `GET /public/dannys/menu` -> 500, NotNullViolation on menu_items.category_id.

`get_public_menu` filtered for display by REASSIGNING relationship collections
on the loaded ORM objects (`cat.items = [...]`, `group.modifiers = [...]`).
SQLAlchemy reads that as "these children were removed from their parent" and,
on the next autoflush, tries to NULL their foreign key. The route runs a second
query straight after (`is_online_ordering_paused`), which is the autoflush.

The NOT NULL constraint turned it into a 500 instead of silent data damage, but
either way one hidden item took the whole storefront menu down.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu import Category, MenuItem, Modifier, MenuItemModifierGroup, ModifierGroup
from app.models.tenant import Tenant
from app.services.public_order_service import get_public_menu, is_online_ordering_paused


async def _seed(db: AsyncSession, tenant: Tenant) -> dict[str, uuid.UUID]:
    """An active category holding one live item and one hidden item.

    The live item carries a group with one live and one hidden modifier, so
    both reassignments that drop children are exercised.
    """
    category = Category(tenant_id=tenant.id, name="Burgers", is_active=True)
    db.add(category)
    await db.flush()

    live = MenuItem(
        tenant_id=tenant.id, category_id=category.id, name="Live Burger",
        price=999, is_available=True,
    )
    hidden = MenuItem(
        tenant_id=tenant.id, category_id=category.id, name="Sold Out Burger",
        price=999, is_available=False,
    )
    group = ModifierGroup(
        tenant_id=tenant.id, name="Sauce", display_order=0, is_active=True,
        required=False, min_selections=0, max_selections=1,
    )
    db.add_all([live, hidden, group])
    await db.flush()

    on = Modifier(tenant_id=tenant.id, group_id=group.id, name="Garlic", price_adjustment=0, is_available=True)
    off = Modifier(tenant_id=tenant.id, group_id=group.id, name="Ketchup", price_adjustment=0, is_available=False)
    db.add_all([
        on, off,
        MenuItemModifierGroup(tenant_id=tenant.id, menu_item_id=live.id, modifier_group_id=group.id),
    ])
    await db.flush()

    ids = {
        "category": category.id, "live": live.id, "hidden": hidden.id,
        "group": group.id, "off_modifier": off.id,
    }
    db.expunge_all()
    return ids


@pytest.mark.asyncio
async def test_menu_then_next_query_does_not_flush(db: AsyncSession, tenant: Tenant) -> None:
    """The exact prod sequence: build the menu, then the route's next query."""
    ids = await _seed(db, tenant)

    _, categories = await get_public_menu(db, tenant.id)
    await is_online_ordering_paused(db, tenant.id)  # the autoflush that 500'd on prod

    assert not db.dirty, "reading the menu left ORM objects marked for UPDATE"

    [cat] = [c for c in categories if c.id == ids["category"]]
    assert [i.name for i in cat.items] == ["Live Burger"]
    [group] = cat.items[0].modifier_groups
    assert [m.name for m in group.modifiers] == ["Garlic"]


@pytest.mark.asyncio
async def test_hidden_rows_keep_their_parents(db: AsyncSession, tenant: Tenant) -> None:
    """Even if something flushes or commits, hidden rows stay attached."""
    ids = await _seed(db, tenant)

    await get_public_menu(db, tenant.id)
    await db.flush()
    db.expunge_all()

    hidden = (await db.execute(select(MenuItem).where(MenuItem.id == ids["hidden"]))).scalar_one()
    assert hidden.category_id == ids["category"]
    off = (await db.execute(select(Modifier).where(Modifier.id == ids["off_modifier"]))).scalar_one()
    assert off.group_id == ids["group"]
