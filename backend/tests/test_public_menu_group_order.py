"""Modifier groups must reach the storefront in `display_order` (OI-79).

The bug these defend against, found 2026-08-12:

    `get_public_menu` FILTERED the groups but never SORTED them.

Items directly above them in the same loop were sorted by
`(display_order, name)`, and the modifiers *inside* each group are ordered by
the relationship itself. Only the groups were left to whatever order the
`menu_item_modifier_groups` association table happened to return, which is not
guaranteed by Postgres and in practice was insertion order. So `display_order`
was inert on the storefront: setting it in the admin changed nothing a customer
could see.

That mattered because Imran asked for the meal options to read
Peri-Peri Heat -> Chips -> Drink -> Add a dip, and the obvious fix (set
`display_order`) would silently have done nothing at all.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu import (
    Category,
    MenuItem,
    MenuItemModifierGroup,
    ModifierGroup,
)
from app.models.tenant import Tenant
from app.services.public_order_service import get_public_menu


async def _item_with_groups(
    db: AsyncSession, tenant: Tenant, groups: list[tuple[str, int, bool]]
) -> uuid.UUID:
    """One category, one item, and the given (name, display_order, active) groups.

    Groups are added in the order given, so the insertion order is under the
    test's control and can be made to disagree with `display_order`.

    Returns the item id, not the object, and expunges first so `get_public_menu`
    genuinely re-reads through its own eager loads instead of being handed the
    identity-mapped objects this helper just built.
    """
    category = Category(
        tenant_id=tenant.id, name=f"Cat {uuid.uuid4().hex[:8]}", is_active=True
    )
    db.add(category)
    await db.flush()

    rows = [
        ModifierGroup(
            tenant_id=tenant.id,
            name=name,
            display_order=order,
            is_active=active,
            required=False,
            min_selections=0,
            max_selections=1,
        )
        for name, order, active in groups
    ]
    db.add_all(rows)
    await db.flush()

    item = MenuItem(
        tenant_id=tenant.id,
        category_id=category.id,
        name=f"Item {uuid.uuid4().hex[:8]}",
        price=999,
        is_available=True,
    )
    db.add(item)
    await db.flush()

    # Link rows written directly rather than through `item.modifier_groups`.
    # Two reasons, both learned the hard way here: assigning that collection on
    # an already-flushed object makes SQLAlchemy read the old collection to
    # compute history, which is sync IO in an async session (MissingGreenlet);
    # and the association is a real model carrying its own NOT NULL
    # `tenant_id`, which the plain relationship does not populate.
    db.add_all(
        [
            MenuItemModifierGroup(
                tenant_id=tenant.id, menu_item_id=item.id, modifier_group_id=g.id
            )
            for g in rows
        ]
    )
    await db.flush()

    item_id = item.id
    db.expunge_all()
    return item_id


def _names(categories: list[Category], item_id: uuid.UUID) -> list[str]:
    for cat in categories:
        for item in cat.items:
            if item.id == item_id:
                return [g.name for g in item.modifier_groups]
    raise AssertionError("seeded item missing from the public menu")


@pytest.mark.asyncio
async def test_groups_come_back_in_display_order(
    db: AsyncSession, tenant: Tenant
) -> None:
    """Neither insertion order nor alphabetical order — `display_order` wins.

    The names are chosen so all three orderings disagree. Alphabetical would
    give Aaa/Bbb/Ccc and insertion order would give the same, so a test using
    tidy names would pass against the unsorted code and prove nothing.
    """
    item_id = await _item_with_groups(
        db,
        tenant,
        [("Aaa Heat", 3, True), ("Bbb Chips", 1, True), ("Ccc Drink", 2, True)],
    )

    _, categories = await get_public_menu(db, tenant.id)

    assert _names(categories, item_id) == ["Bbb Chips", "Ccc Drink", "Aaa Heat"]


@pytest.mark.asyncio
async def test_equal_display_order_falls_back_to_name(
    db: AsyncSession, tenant: Tenant
) -> None:
    """Same key as the item sort directly above it: `(display_order, name)`.

    Every group starts life at the column default of 0, so before anyone sets
    an order the tie-break is the only thing standing between the customer and
    an arbitrary shuffle.
    """
    item_id = await _item_with_groups(
        db,
        tenant,
        [("Zulu", 0, True), ("Alpha", 0, True), ("Mike", 0, True)],
    )

    _, categories = await get_public_menu(db, tenant.id)

    assert _names(categories, item_id) == ["Alpha", "Mike", "Zulu"]


@pytest.mark.asyncio
async def test_sorting_did_not_cost_the_inactive_filter(
    db: AsyncSession, tenant: Tenant
) -> None:
    """The line that gained the sort is the same line that hides dead groups.

    Worth its own test: replacing a list comprehension with `sorted()` is
    exactly the kind of edit that quietly drops a predicate.
    """
    item_id = await _item_with_groups(
        db,
        tenant,
        [("Live One", 2, True), ("Switched Off", 1, False), ("Live Two", 3, True)],
    )

    _, categories = await get_public_menu(db, tenant.id)

    assert _names(categories, item_id) == ["Live One", "Live Two"]
