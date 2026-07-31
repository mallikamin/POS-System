"""One-time fix: rename existing Chick Shack dip modifiers in place, 2026-07-31.

Why this exists
----------------
Imran (via Malik, 2026-07-31): kitchen staff need the word "dip tub" next to
each dip choice, so a modifier like "Ketchup" on a burger's ticket line reads
as a separate 2oz tub rather than an instruction to put ketchup ON the
burger. `print_service.py` prints a bare `modifier.name` with no group
context, so the group's own label ("Add a dip (2oz tub)") never reaches the
kitchen ticket -- only the option name does.

`seed_chick_shack.py._get_or_create_group` matches modifier rows by
`(tenant, group_id, name)`. Renaming "Ketchup" -> "Ketchup (Dip Tub)" in
`storefront/src/data/menu.ts` therefore does NOT rename the existing row on
the next seed run: the seeder finds no modifier named "Ketchup (Dip Tub)" in
the dips group and creates a brand new one, leaving the old "Ketchup" row
active and still linked to the group -- both would show to the customer
(same additive-only-seeder class of bug as
`rename_chick_shack_items_2026_07_31.py`, applied here to modifiers instead
of items).

This renames the 9 dip modifier rows **in place** (same primary key), so:
* No duplicate dip option appears on the storefront.
* Any historical `order_item_modifiers` FK referencing the old row's id
  stays valid.
* Running `seed_chick_shack.py` afterwards then matches and updates this
  same row rather than creating a new one.

Safe to run more than once: an `UPDATE ... WHERE name = <old>` against a
name that no longer exists is a no-op.

Usage
-----
    python -m app.scripts.rename_chick_shack_dip_modifiers_2026_07_31 --tenant-slug chick-shack
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select, update

from app.database import async_session_factory
from app.models.menu import Modifier, ModifierGroup
from app.models.tenant import Tenant

DIPS_GROUP_NAME = "Add a dip (2oz tub)"

RENAMES = {
    "Ketchup": "Ketchup (Dip Tub)",
    "Mayo": "Mayo (Dip Tub)",
    "Garlic Mayo": "Garlic Mayo (Dip Tub)",
    "BBQ": "BBQ (Dip Tub)",
    "Burger Sauce": "Burger Sauce (Dip Tub)",
    "Chilli Sauce": "Chilli Sauce (Dip Tub)",
    "Peri Peri Sauce": "Peri Peri Sauce (Dip Tub)",
    "Salsa Sauce": "Salsa Sauce (Dip Tub)",
    "Algerian Sauce": "Algerian Sauce (Dip Tub)",
}


async def run(slug: str) -> None:
    async with async_session_factory() as db:
        tenant = (
            await db.execute(select(Tenant).where(Tenant.slug == slug))
        ).scalar_one_or_none()
        if tenant is None:
            print(f"No tenant with slug '{slug}' -- nothing to do.")
            return

        group = (
            await db.execute(
                select(ModifierGroup).where(
                    ModifierGroup.tenant_id == tenant.id,
                    ModifierGroup.name == DIPS_GROUP_NAME,
                )
            )
        ).scalar_one_or_none()
        if group is None:
            print(f"No modifier group named '{DIPS_GROUP_NAME}' -- nothing to do.")
            return

        for old_name, new_name in RENAMES.items():
            result = await db.execute(
                update(Modifier)
                .where(Modifier.group_id == group.id, Modifier.name == old_name)
                .values(name=new_name)
            )
            if result.rowcount:
                print(f"  Renamed '{old_name}' -> '{new_name}' ({result.rowcount} row)")
            else:
                print(f"  '{old_name}' not found -- already renamed or never existed")

        await db.commit()
        print("Committed.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-slug", default="chick-shack")
    args = parser.parse_args()
    asyncio.run(run(args.tenant_slug))


if __name__ == "__main__":
    main()
