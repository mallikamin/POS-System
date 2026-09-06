"""The list of categories an ingredient can be filed under.

Martin's M11. See `IngredientCategory` in `app/models/inventory.py` for why the
category on the ingredient stays a string while this table is the master list,
and for the two rules that stop the two drifting apart.

Both rules live here:

  * `ensure_category` is called on every ingredient write, so saving an
    ingredient under a category nobody created yet creates it;
  * `list_categories` returns the union of the master rows and any category
    string actually in use, so a value that arrived before this table existed
    (or through a direct SQL fix) still appears in the dropdown rather than
    silently vanishing from it.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Ingredient, IngredientCategory


class CategoryError(ValueError):
    """A category action that cannot be performed as asked. Never a 500."""


async def ensure_category(
    db: AsyncSession, tenant_id: uuid.UUID, name: str | None
) -> IngredientCategory | None:
    """Make sure `name` exists in the master list. Idempotent.

    Matched case-insensitively, and the STORED spelling wins: typing "dairy"
    when "Dairy" exists files the ingredient under "Dairy" rather than creating
    a second category that differs only in case. That is the whole point of the
    table, and doing it anywhere other than the write path would let the first
    typo through.

    Returns the row, or None when there is nothing to file.
    """
    clean = (name or "").strip()
    if not clean:
        return None

    existing = (
        await db.execute(
            select(IngredientCategory).where(
                IngredientCategory.tenant_id == tenant_id,
                func.lower(IngredientCategory.name) == clean.lower(),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        # Filing something under a category that was deactivated brings it back:
        # the operator has just said they still use it.
        if not existing.is_active:
            existing.is_active = True
            await db.flush()
        return existing

    highest = (
        await db.execute(
            select(func.coalesce(func.max(IngredientCategory.sort_order), 0)).where(
                IngredientCategory.tenant_id == tenant_id
            )
        )
    ).scalar_one()
    row = IngredientCategory(
        tenant_id=tenant_id, name=clean, sort_order=int(highest) + 1
    )
    db.add(row)
    await db.flush()
    return row


async def canonical_name(
    db: AsyncSession, tenant_id: uuid.UUID, name: str | None
) -> str | None:
    """The spelling to store on the ingredient, creating the category if new."""
    row = await ensure_category(db, tenant_id, name)
    return row.name if row is not None else None


async def list_categories(
    db: AsyncSession, tenant_id: uuid.UUID, include_inactive: bool = False
) -> list[dict]:
    """Every category, with how many ingredients carry it.

    The count is what makes the screen honest: a category with 12 ingredients
    behind it must not look like a free thing to delete, and one with zero is
    safe to remove.
    """
    counts = {
        (name or "").lower(): count
        for name, count in (
            await db.execute(
                select(Ingredient.category, func.count(Ingredient.id))
                .where(Ingredient.tenant_id == tenant_id)
                .group_by(Ingredient.category)
            )
        ).all()
    }

    stmt = select(IngredientCategory).where(IngredientCategory.tenant_id == tenant_id)
    if not include_inactive:
        stmt = stmt.where(IngredientCategory.is_active == True)  # noqa: E712
    rows = list(
        (
            await db.execute(
                stmt.order_by(IngredientCategory.sort_order, IngredientCategory.name)
            )
        )
        .scalars()
        .all()
    )

    out = [
        {
            "id": row.id,
            "name": row.name,
            "sort_order": row.sort_order,
            "is_active": row.is_active,
            "ingredient_count": counts.get(row.name.lower(), 0),
        }
        for row in rows
    ]

    # The self-healing half. A category string in use with no master row behind
    # it gets one on the wire (id None) so the dropdown is never missing a value
    # the data already contains.
    known = {row["name"].lower() for row in out}
    orphans = sorted(
        name
        for name in {
            (n or "").strip() for n in counts.keys() if (n or "").strip()
        }
        if name.lower() not in known
    )
    for name in orphans:
        out.append(
            {
                "id": None,
                "name": name,
                "sort_order": 9999,
                "is_active": True,
                "ingredient_count": counts.get(name.lower(), 0),
            }
        )
    return out


async def get_category(
    db: AsyncSession, tenant_id: uuid.UUID, category_id: uuid.UUID
) -> IngredientCategory:
    row = (
        await db.execute(
            select(IngredientCategory).where(
                IngredientCategory.id == category_id,
                IngredientCategory.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise CategoryError("No such ingredient category for this restaurant.")
    return row


async def create_category(
    db: AsyncSession, tenant_id: uuid.UUID, name: str
) -> IngredientCategory:
    clean = (name or "").strip()
    if not clean:
        raise CategoryError("A category needs a name.")
    existing = (
        await db.execute(
            select(IngredientCategory).where(
                IngredientCategory.tenant_id == tenant_id,
                func.lower(IngredientCategory.name) == clean.lower(),
            )
        )
    ).scalar_one_or_none()
    if existing is not None and existing.is_active:
        raise CategoryError(f"A category called {existing.name!r} already exists.")
    row = await ensure_category(db, tenant_id, clean)
    assert row is not None  # `clean` is non-empty, so ensure_category returns a row
    return row


async def rename_category(
    db: AsyncSession, tenant_id: uuid.UUID, category_id: uuid.UUID, new_name: str
) -> tuple[IngredientCategory, int]:
    """Rename the master row AND every ingredient carrying the old string.

    🔴 Both halves or neither. The caller commits once, so a failure between
    them rolls the whole rename back; renaming only the master row would leave
    every ingredient filed under a category that no longer exists, which is
    exactly the drift this table was added to prevent.

    Returns the row and how many ingredients moved.
    """
    clean = (new_name or "").strip()
    if not clean:
        raise CategoryError("A category needs a name.")

    row = await get_category(db, tenant_id, category_id)
    if clean.lower() == row.name.lower():
        row.name = clean
        await db.flush()
        return row, 0

    clash = (
        await db.execute(
            select(IngredientCategory).where(
                IngredientCategory.tenant_id == tenant_id,
                IngredientCategory.id != category_id,
                func.lower(IngredientCategory.name) == clean.lower(),
            )
        )
    ).scalar_one_or_none()
    if clash is not None:
        raise CategoryError(
            f"A category called {clash.name!r} already exists. Move the "
            "ingredients across instead of renaming onto it."
        )

    old = row.name
    affected = list(
        (
            await db.execute(
                select(Ingredient).where(
                    Ingredient.tenant_id == tenant_id,
                    func.lower(Ingredient.category) == old.lower(),
                )
            )
        )
        .scalars()
        .all()
    )
    for ingredient in affected:
        ingredient.category = clean
    row.name = clean
    await db.flush()
    return row, len(affected)


async def delete_category(
    db: AsyncSession, tenant_id: uuid.UUID, category_id: uuid.UUID
) -> IngredientCategory:
    """Deactivate, and refuse while ingredients are still filed under it.

    Refusing rather than reassigning is deliberate: silently moving 12
    ingredients to "General" because someone tidied a dropdown is a data change
    nobody asked for. The error names the count so the operator can decide.
    """
    row = await get_category(db, tenant_id, category_id)
    in_use = (
        await db.execute(
            select(func.count(Ingredient.id)).where(
                Ingredient.tenant_id == tenant_id,
                func.lower(Ingredient.category) == row.name.lower(),
            )
        )
    ).scalar_one()
    if int(in_use) > 0:
        raise CategoryError(
            f"{row.name} still has {int(in_use)} ingredient(s) in it. Move them "
            "to another category first."
        )
    row.is_active = False
    await db.flush()
    return row
