"""One-time fix: rename existing Chick Shack menu rows in place, 2026-07-31.

Why this exists
----------------
`seed_chick_shack.py` matches rows by `(tenant, name)`. Renaming an item in
`storefront/src/data/menu.ts` (e.g. "Chicken Fillet" -> "Chicken Fillet
Burger" -- OI-45 item naming ask) therefore does NOT rename the existing row
on the next seed run: the seeder no longer finds anything named "Chicken
Fillet" and creates a brand new "Chicken Fillet Burger" row instead, leaving
the old one sitting active in the database as an orphaned duplicate.

This renames the row **in place** (same primary key), so:
* No duplicate appears on the storefront.
* Any historical `order_items` FK referencing the old row's id stays valid.
* Running `seed_chick_shack.py` afterwards then matches and updates this same
  row rather than creating a new one.

Safe to run more than once: an `UPDATE ... WHERE name = <old>` against a name
that no longer exists is a no-op.

Usage
-----
    python -m app.scripts.rename_chick_shack_items_2026_07_31 --tenant-slug chick-shack
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select, update

from app.database import async_session_factory
from app.models.menu import MenuItem
from app.models.tenant import Tenant

RENAMES = {
    "Chicken Fillet": "Chicken Fillet Burger",
    "Double Chicken": "Double Chicken Burger",
    "Chick Shack Fillet Tower": "Chick Shack Fillet Tower Burger",
    "Peri Peri": "Peri Peri Burger",
    "Double Peri Peri": "Double Peri Peri Burger",
    "The Big Shack": "The Big Shack Burger",
    "The Hot Chick": "The Hot Chick Wrap",
}


async def run(slug: str) -> None:
    async with async_session_factory() as db:
        tenant = (
            await db.execute(select(Tenant).where(Tenant.slug == slug))
        ).scalar_one_or_none()
        if tenant is None:
            print(f"No tenant with slug '{slug}' -- nothing to do.")
            return

        for old_name, new_name in RENAMES.items():
            result = await db.execute(
                update(MenuItem)
                .where(MenuItem.tenant_id == tenant.id, MenuItem.name == old_name)
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
