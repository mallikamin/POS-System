"""One-time fix: rename existing Chick Shack drink items in place, 2026-07-31.

Why this exists
----------------
Imran (via Malik): append a serving-size/container label to every drink name so
customers know what they're getting -- "(Can)" on the canned soft drinks, "(500ml)"
on Water, "(330ml)" on Fruit Shoot.

`seed_chick_shack.py` matches `MenuItem` rows by `(tenant, name)`. Renaming these in
`storefront/src/data/menu.ts` and reseeding blind would create 10 duplicate rows
rather than renaming them -- the same additive-only-seeder class of bug already
documented in `ERROR_LOG.md` for the Burger/Wrap suffix renames and the dip modifier
renames. This renames the 10 existing rows **in place** (same primary key), so:
* No duplicate item appears on the storefront.
* Any historical `order_items` FK referencing an old row's id stays valid.
* Running `seed_chick_shack.py` afterwards then matches and updates these same rows.

Safe to run more than once: an `UPDATE ... WHERE name = <old>` against a name that
no longer exists is a no-op.

Usage
-----
    python -m app.scripts.rename_chick_shack_drinks_2026_07_31 --tenant-slug chick-shack
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select, update

from app.database import async_session_factory
from app.models.menu import MenuItem
from app.models.tenant import Tenant

RENAMES = {
    "Pepsi": "Pepsi (Can)",
    "Pepsi Max": "Pepsi Max (Can)",
    "Fanta Orange": "Fanta Orange (Can)",
    "7up": "7up (Can)",
    "Rubicon Passionfruit": "Rubicon Passionfruit (Can)",
    "Levi Roots Caribbean Crush": "Levi Roots Caribbean Crush (Can)",
    "Irn Bru": "Irn Bru (Can)",
    "Diet Irn Bru": "Diet Irn Bru (Can)",
    "Water": "Water (500ml)",
    "Fruit Shoot": "Fruit Shoot (330ml)",
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
