"""One-time fix: reorder each Meal item's modifier-group tabs, 2026-07-31 (session K).

Why this exists
----------------
`menu_item_modifier_groups` has no ordering column, so the API's `selectin`
relationship returns an item's modifier groups in whatever order Postgres
happens to return them for that join -- in practice, insertion order.

`withMeal()` in `storefront/src/data/menu.ts` originally appended the meal
groups (drink, chips upgrade) AFTER whatever the solo item already carried,
so Dips -- an optional garnish -- ended up linked (and therefore rendered)
BEFORE the meal's required drink choice. Malik caught this in UAT: "ur
showing optional sauce options ahead of the compulsory drink and fries
option."

`withMeal()` now builds the array in the right order (Heat, if present ->
Drink -> Meal Deal Upgrade -> Dips, if present), and `chick_shack_menu.json`
has been regenerated to match. But `seed_chick_shack.py`'s `_link()` is
additive-only -- it skips a link that already exists rather than fixing its
position -- so a plain reseed does not change anything already live. Same
failure shape as the two 2026-07-31 rename bugs, one script over: rewiring
what's already there needs its own explicit fix, not another seed run.

This script deletes and re-inserts each Meal item's modifier-group links, in
the exact order `chick_shack_menu.json` now specifies for that item, so a
fresh SELECT returns them correctly. It changes nothing about which groups
are linked -- only their order -- and reads the desired order from the same
JSON file `seed_chick_shack.py` uses, so it can never drift from menu.ts.

Idempotent: safe to run more than once. Only touches
`menu_item_modifier_groups` rows (no `order_items`/`order_item_modifiers`
FK depends on this table), so no historical order data is at risk.

Usage
-----
    python -m app.scripts.reorder_chick_shack_meal_modifiers_2026_07_31 --tenant-slug chick-shack
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib

from sqlalchemy import delete, select

from app.database import async_session_factory
from app.models.menu import MenuItem, MenuItemModifierGroup, ModifierGroup
from app.models.tenant import Tenant

DATA_FILE = pathlib.Path(__file__).parent / "data" / "chick_shack_menu.json"


async def run(slug: str) -> None:
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    meal_entries = [e for e in payload["items"] if e["name"].endswith(" Meal")]

    async with async_session_factory() as db:
        tenant = (
            await db.execute(select(Tenant).where(Tenant.slug == slug))
        ).scalar_one_or_none()
        if tenant is None:
            print(f"No tenant with slug '{slug}' -- nothing to do.")
            return

        group_id_by_name: dict[str, object] = {
            row.name: row.id
            for row in (
                await db.execute(
                    select(ModifierGroup).where(ModifierGroup.tenant_id == tenant.id)
                )
            ).scalars()
        }

        fixed = 0
        for entry in meal_entries:
            item = (
                await db.execute(
                    select(MenuItem).where(
                        MenuItem.tenant_id == tenant.id, MenuItem.name == entry["name"]
                    )
                )
            ).scalar_one_or_none()
            if item is None:
                print(f"  '{entry['name']}' -- no such item, skipping")
                continue

            wanted_order = [g["name"] for g in entry["modifierGroups"]]
            group_ids = []
            for name in wanted_order:
                gid = group_id_by_name.get(name)
                if gid is None:
                    print(f"  '{entry['name']}': group '{name}' not found in DB, skipping item")
                    group_ids = None
                    break
                group_ids.append(gid)
            if group_ids is None:
                continue

            await db.execute(
                delete(MenuItemModifierGroup).where(
                    MenuItemModifierGroup.menu_item_id == item.id
                )
            )
            for gid in group_ids:
                db.add(
                    MenuItemModifierGroup(
                        tenant_id=tenant.id, menu_item_id=item.id, modifier_group_id=gid
                    )
                )
            await db.flush()
            fixed += 1
            print(f"  '{entry['name']}': reordered to {wanted_order}")

        await db.commit()
        print(f"Committed. {fixed} meal item(s) reordered.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-slug", default="chick-shack")
    args = parser.parse_args()
    asyncio.run(run(args.tenant_slug))


if __name__ == "__main__":
    main()
