"""One-time fix: detach obsolete modifier groups from Chick Shack items, 2026-07-31.

Why this exists
----------------
`seed_chick_shack.py` matches modifier groups by `(tenant, name)` and only
ever ADDS a `menu_item_modifier_groups` link -- it never removes one. Two
renames in this session's OI-45 build therefore left stale links behind:

* `HEAT.name` changed from "Mild or Hot" to "Peri-Peri Heat" in
  `storefront/src/data/menu.ts`. The seeder found no existing group named
  "Peri-Peri Heat", so it created a NEW group row and linked it -- the OLD
  "Mild or Hot" row and its 10 links to peri items were left in place.
* The flat "Make it a meal" tick was removed from every item's
  `modifierGroups` in code (replaced by real Meal sibling products), but the
  25 existing links to that group were never removed by a reseed that only
  adds.

This detaches those two groups from every item they are still linked to.
It deliberately does NOT delete the `modifier_groups` / `modifiers` rows
themselves: a past real order may reference one of their modifiers via
`order_item_modifiers`, and that FK must stay valid. Only the *current*
menu-item association -- which controls what a NEW order can pick -- is
removed. The orphaned groups are also marked inactive so they cannot appear
anywhere new.

Safe to run more than once: deleting links that no longer exist is a no-op.

Usage
-----
    python -m app.scripts.fix_chick_shack_stale_groups_2026_07_31 --tenant-slug chick-shack
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import delete, select, update

from app.database import async_session_factory
from app.models.menu import MenuItemModifierGroup, ModifierGroup
from app.models.tenant import Tenant

OBSOLETE_GROUP_NAMES = ["Mild or Hot", "Make it a meal"]


async def run(slug: str) -> None:
    async with async_session_factory() as db:
        tenant = (
            await db.execute(select(Tenant).where(Tenant.slug == slug))
        ).scalar_one_or_none()
        if tenant is None:
            print(f"No tenant with slug '{slug}' -- nothing to do.")
            return

        for name in OBSOLETE_GROUP_NAMES:
            group = (
                await db.execute(
                    select(ModifierGroup).where(
                        ModifierGroup.tenant_id == tenant.id,
                        ModifierGroup.name == name,
                    )
                )
            ).scalar_one_or_none()
            if group is None:
                print(f"  '{name}' -- no such group, already cleaned up")
                continue

            result = await db.execute(
                delete(MenuItemModifierGroup).where(
                    MenuItemModifierGroup.modifier_group_id == group.id
                )
            )
            group.is_active = False
            print(f"  '{name}': removed {result.rowcount} stale item link(s), "
                  f"marked inactive")

        await db.commit()
        print("Committed.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-slug", default="chick-shack")
    args = parser.parse_args()
    asyncio.run(run(args.tenant_slug))


if __name__ == "__main__":
    main()
