"""Seed the menu for Ali Fish & Chips & Curry House (UK, GBP, pence).

What this does, and what it does not
------------------------------------
Reads `data/ali_fish_chips_menu.json` (typed off the March 2025 printed menu)
and writes categories, menu items, modifier groups and modifiers for a tenant
that ALREADY EXISTS. It does not create the tenant, users, roles, restaurant
config or delivery areas. Another step owns those.

Modelled on `seed_chick_shack.py`, with the same conventions, because the
storefront's `menuAdapter.ts` depends on them:

* An item with more than one entry in `variants` gets a required single-choice
  group named "<item name> -- Choice" (two ASCII hyphens). The item price is the
  cheapest variant; the others become positive price adjustments. The storefront
  shows that group as sizes with absolute prices.
* Every other group in `modifierGroups` is shared by exact name across items
  (`modifier_groups` is unique on (tenant, name)). Two JSON groups with the same
  name and different options would silently merge, so validation refuses that.
* The printed item number has no column in `menu_items`; it is the name prefix
  ("12. King Rib"). `number`, `notes` and `spice` in the JSON are reference only.

Safety
------
* **Additive and idempotent**, like the Chick Shack seeder: re-running matches on
  (tenant, name) and updates prices in place, never inserting duplicates.
  Options removed from the JSON are NOT deleted from the database.
* **Never guesses a tenant.** `--tenant-slug` is required and must exist.
* **Refuses a tenant that already holds items not in this JSON**, which is what
  pointing it at another restaurant by mistake looks like. `--allow-other-items`
  overrides that once the shop has added its own items.
* Every query is tenant-scoped.
* Per `memory/data-integrity.md`: `pg_dump` before running this against any
  database you care about.

Usage
-----
    python -m app.scripts.seed_ali_fish_chips --tenant-slug ali-fish-chips
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu import (
    Category,
    MenuItem,
    MenuItemModifierGroup,
    Modifier,
    ModifierGroup,
)
from app.models.tenant import Tenant

DATA_FILE = pathlib.Path(__file__).parent / "data" / "ali_fish_chips_menu.json"

# Must match `VARIANT_GROUP_SUFFIX` in storefront/src/lib/menuAdapter.ts and
# `VARIANT_GROUP_NAME` in seed_chick_shack.py.
VARIANT_GROUP_NAME = "Choice"

# Column limits from app/models/menu.py.
_MAX_ITEM_NAME = 200
_MAX_GROUP_NAME = 100
_MAX_MODIFIER_NAME = 100
_MAX_CATEGORY_NAME = 100


class MenuDataError(ValueError):
    """The JSON would produce a wrong or unorderable menu. Nothing was written."""


def variant_group_name(item_name: str) -> str:
    return f"{item_name} -- {VARIANT_GROUP_NAME}"


def load_menu(path: pathlib.Path = DATA_FILE) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_int(value: Any) -> bool:
    # bool is a subclass of int; a price of True is a bug, not a penny.
    return isinstance(value, int) and not isinstance(value, bool)


def validate_menu(payload: dict[str, Any]) -> None:
    """Raise MenuDataError listing every problem, before any row is touched."""
    errors: list[str] = []
    category_ids = set()
    for cat in payload.get("categories", []):
        if cat["id"] in category_ids:
            errors.append(f"duplicate category id {cat['id']}")
        category_ids.add(cat["id"])
        if len(cat["name"]) > _MAX_CATEGORY_NAME:
            errors.append(f"category name too long: {cat['name']}")

    item_names: set[str] = set()
    groups_by_name: dict[str, dict[str, Any]] = {}

    for entry in payload.get("items", []):
        name = entry["name"]
        if name in item_names:
            errors.append(f"duplicate item name {name!r}")
        item_names.add(name)
        if len(name) > _MAX_ITEM_NAME:
            errors.append(f"item name too long: {name!r}")
        if entry.get("categoryId") not in category_ids:
            errors.append(f"{name!r}: unknown category {entry.get('categoryId')!r}")

        variants = entry.get("variants") or []
        if not variants:
            errors.append(f"{name!r}: no variants, so no price")
        for var in variants:
            if not _is_int(var.get("price")) or var["price"] <= 0:
                errors.append(f"{name!r}: variant {var.get('name')!r} price "
                              f"{var.get('price')!r} is not a positive integer")
        if len(variants) > 1:
            vnames = [var["name"] for var in variants]
            if len(set(vnames)) != len(vnames) or any(not n for n in vnames):
                errors.append(f"{name!r}: variant names must be unique and non-empty")
            if len(variant_group_name(name)) > _MAX_GROUP_NAME:
                errors.append(f"{name!r}: variant group name over {_MAX_GROUP_NAME} chars")

        for group in entry.get("modifierGroups") or []:
            gname = group["name"]
            mn, mx = group.get("min", 0), group.get("max", 0)
            opts = group.get("options", [])
            if len(gname) > _MAX_GROUP_NAME:
                errors.append(f"group name too long: {gname!r}")
            if gname.endswith(f" -- {VARIANT_GROUP_NAME}"):
                errors.append(f"{gname!r}: the ' -- Choice' suffix is reserved for variants")
            if not (_is_int(mn) and _is_int(mx)) or mn < 0 or mx < 0:
                errors.append(f"{gname!r}: min/max must be non-negative integers")
            elif mx and mn > mx:
                errors.append(f"{gname!r}: min {mn} > max {mx}")
            if mn > len(opts):
                errors.append(f"{gname!r}: min {mn} but only {len(opts)} options")
            onames = [o["name"] for o in opts]
            if len(set(onames)) != len(onames):
                errors.append(f"{gname!r}: duplicate option names")
            for opt in opts:
                if len(opt["name"]) > _MAX_MODIFIER_NAME:
                    errors.append(f"option name too long: {opt['name']!r}")
                delta = opt.get("priceDelta", 0)
                if not _is_int(delta) or delta < 0:
                    errors.append(f"{gname!r}/{opt['name']!r}: priceDelta {delta!r} "
                                  "must be a non-negative integer")

            signature = {
                "min": mn,
                "max": mx,
                "options": [(o["name"], o.get("priceDelta", 0)) for o in opts],
            }
            seen = groups_by_name.get(gname)
            if seen is None:
                groups_by_name[gname] = signature
            elif seen != signature:
                errors.append(f"group {gname!r} is defined twice with different "
                              "options; groups are shared by name, so one would "
                              "silently overwrite the other")

    if errors:
        raise MenuDataError("Menu data refused:\n  - " + "\n  - ".join(errors))


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------


async def _seed_categories(
    db: AsyncSession, tenant: Tenant, categories: list[dict[str, Any]]
) -> dict[str, Category]:
    by_id: dict[str, Category] = {}
    for entry in categories:
        row = (
            await db.execute(
                select(Category).where(
                    Category.tenant_id == tenant.id, Category.name == entry["name"]
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = Category(tenant_id=tenant.id, name=entry["name"])
            db.add(row)
        row.display_order = entry.get("sort", 0)
        row.is_active = True
        await db.flush()
        by_id[entry["id"]] = row
    return by_id


async def _upsert_group(
    db: AsyncSession,
    tenant: Tenant,
    name: str,
    *,
    min_selections: int,
    max_selections: int,
    options: list[tuple[str, int]],
) -> ModifierGroup:
    group = (
        await db.execute(
            select(ModifierGroup).where(
                ModifierGroup.tenant_id == tenant.id, ModifierGroup.name == name
            )
        )
    ).scalar_one_or_none()
    if group is None:
        group = ModifierGroup(tenant_id=tenant.id, name=name)
        db.add(group)

    group.required = min_selections > 0
    group.min_selections = min_selections
    group.max_selections = max_selections
    group.is_active = True
    await db.flush()

    for order, (opt_name, delta) in enumerate(options):
        modifier = (
            await db.execute(
                select(Modifier).where(
                    Modifier.tenant_id == tenant.id,
                    Modifier.group_id == group.id,
                    Modifier.name == opt_name,
                )
            )
        ).scalar_one_or_none()
        if modifier is None:
            modifier = Modifier(tenant_id=tenant.id, group_id=group.id, name=opt_name)
            db.add(modifier)
        modifier.price_adjustment = delta
        modifier.display_order = order
        modifier.is_available = True
        await db.flush()

    return group


async def _seed_items(
    db: AsyncSession,
    tenant: Tenant,
    items: list[dict[str, Any]],
    categories: dict[str, Category],
) -> dict[str, int]:
    shared: dict[str, ModifierGroup] = {}
    variant_groups = 0

    for order, entry in enumerate(items):
        category = categories[entry["categoryId"]]
        variants = entry["variants"]
        base_price = min(var["price"] for var in variants)

        item = (
            await db.execute(
                select(MenuItem).where(
                    MenuItem.tenant_id == tenant.id, MenuItem.name == entry["name"]
                )
            )
        ).scalar_one_or_none()
        if item is None:
            item = MenuItem(tenant_id=tenant.id, name=entry["name"])
            db.add(item)

        item.category_id = category.id
        item.description = entry.get("description")
        item.price = base_price
        item.is_available = True
        item.display_order = order
        await db.flush()

        # All links for this item are built in ONE list and recreated in one
        # delete + insert. See the 2026-07-31 note in seed_chick_shack.py for
        # the bug that splitting this caused there.
        group_ids: list[uuid.UUID] = []

        if len(variants) > 1:
            vgroup = await _upsert_group(
                db,
                tenant,
                variant_group_name(entry["name"]),
                min_selections=1,
                max_selections=1,
                options=[(var["name"], var["price"] - base_price) for var in variants],
            )
            group_ids.append(vgroup.id)
            variant_groups += 1

        for gdef in entry.get("modifierGroups") or []:
            gname = gdef["name"]
            if gname not in shared:
                shared[gname] = await _upsert_group(
                    db,
                    tenant,
                    gname,
                    min_selections=gdef.get("min", 0),
                    max_selections=gdef.get("max", 0),
                    options=[(o["name"], o.get("priceDelta", 0)) for o in gdef["options"]],
                )
            group_ids.append(shared[gname].id)

        await db.execute(
            delete(MenuItemModifierGroup).where(
                MenuItemModifierGroup.menu_item_id == item.id,
                MenuItemModifierGroup.tenant_id == tenant.id,
            )
        )
        for gid in group_ids:
            db.add(
                MenuItemModifierGroup(
                    tenant_id=tenant.id, menu_item_id=item.id, modifier_group_id=gid
                )
            )
        await db.flush()

    return {
        "items": len(items),
        "variant_groups": variant_groups,
        "shared_groups": len(shared),
    }


async def seed_menu(
    db: AsyncSession,
    tenant: Tenant,
    payload: dict[str, Any],
    *,
    allow_other_items: bool = False,
) -> dict[str, int]:
    """Validate, then write the menu for `tenant`. Flushes; does not commit."""
    validate_menu(payload)

    json_names = {entry["name"] for entry in payload["items"]}
    existing = (
        await db.execute(select(MenuItem.name).where(MenuItem.tenant_id == tenant.id))
    ).scalars().all()
    foreign = sorted(set(existing) - json_names)
    if foreign and not allow_other_items:
        raise MenuDataError(
            f"Tenant '{tenant.slug}' already has {len(foreign)} menu item(s) that are "
            f"not in {DATA_FILE.name} (e.g. {foreign[:3]}). Wrong tenant? Pass "
            "--allow-other-items only if those are the shop's own additions."
        )

    categories = await _seed_categories(db, tenant, payload["categories"])
    counts = await _seed_items(db, tenant, payload["items"], categories)
    counts["categories"] = len(categories)
    return counts


async def seed(slug: str, allow_other_items: bool) -> None:
    from app.database import async_session_factory

    payload = load_menu()
    async with async_session_factory() as db:
        tenant = (
            await db.execute(select(Tenant).where(Tenant.slug == slug))
        ).scalar_one_or_none()
        if tenant is None:
            raise SystemExit(
                f"Tenant '{slug}' does not exist. This script only seeds the menu; "
                "create the tenant first."
            )

        print(f"Seeding menu for tenant '{slug}' from {DATA_FILE.name}")
        counts = await seed_menu(db, tenant, payload, allow_other_items=allow_other_items)
        await db.commit()

    print(f"  Categories:            {counts['categories']}")
    print(f"  Menu items:            {counts['items']}")
    print(f"  Size/choice groups:    {counts['variant_groups']}")
    print(f"  Shared modifier groups:{counts['shared_groups']:>3}")
    print("Committed.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tenant-slug", required=True,
                        help="Existing tenant to seed. Never guessed.")
    parser.add_argument("--allow-other-items", action="store_true",
                        help="Proceed even if the tenant has items not in the JSON.")
    args = parser.parse_args()
    try:
        asyncio.run(seed(args.tenant_slug, args.allow_other_items))
    except MenuDataError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
