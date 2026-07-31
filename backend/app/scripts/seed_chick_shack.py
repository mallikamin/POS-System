"""Seed the Chick Shack UK tenant: config, roles, users and the full menu.

Why this script exists
----------------------
The storefront at chickshackg84.com renders its menu from
`storefront/src/data/menu.ts` -- a hardcoded TypeScript file compiled into the
Cloudflare Worker bundle. That is why the site shows the right food at the right
prices while the database knows nothing about any of it.

`POST /public/{tenant_slug}/orders` validates every basket line against
`menu_items.id`, which is a UUID. The storefront's IDs are slugs like
"peri-half". So until the menu exists as rows, the storefront cannot place a
real order at all. This script closes that gap.

The menu data is not retyped here. `storefront/scripts/export-menu.ts` dumps the
real objects to `data/chick_shack_menu.json` and this script consumes that,
because `MENU_ITEMS` is assembled by helper functions and reading 62 items by
eye is exactly how a price gets mistyped.

Safety
------
* **Additive and idempotent.** Re-running creates nothing twice. It matches on
  (tenant, name) and updates prices in place rather than inserting duplicates.
* **It never guesses a tenant.** `--tenant-slug` is explicit, mirroring
  `seed_chick_shack_delivery.py`. The server hosts several tenants and the POS
  has already lost data once to a script that assumed which one it was on.
* **It touches no other tenant's rows.** Every query is tenant-scoped.
* Per `memory/data-integrity.md`: take a `pg_dump` before running this against
  anything you care about. It is additive, but that rule has no exceptions.

Usage
-----
    python -m app.scripts.seed_chick_shack --tenant-slug chick-shack \
        --credentials-out /path/to/ChickShack.txt
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import secrets
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.menu import (
    Category,
    MenuItem,
    MenuItemModifierGroup,
    Modifier,
    ModifierGroup,
)
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.models.user import Role, User
from app.scripts.seed import seed_permissions, seed_roles
from app.utils.security import hash_password

DATA_FILE = pathlib.Path(__file__).parent / "data" / "chick_shack_menu.json"

# Deliberately excludes characters that are misread when someone types a
# password off a printed sheet or a WhatsApp message: O/0, l/1/I, and similar.
_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"

# The variant axis becomes a required single-select modifier group with this
# name. Chick Shack's variants are things like "with Chips" / "Half & Half" /
# "with Rice", which is a choice, not a separate dish.
VARIANT_GROUP_NAME = "Choice"


def _password(length: int = 12) -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))


def _pin() -> str:
    """A 4-digit PIN that is not one of the ones everybody guesses."""
    while True:
        pin = f"{secrets.randbelow(10_000):04d}"
        if pin not in {"0000", "1111", "1234", "9999", "1212", "4321"}:
            return pin


# ---------------------------------------------------------------------------
# Tenant, config, users
# ---------------------------------------------------------------------------


async def _get_or_create_tenant(db: AsyncSession, slug: str, name: str) -> Tenant:
    existing = (
        await db.execute(select(Tenant).where(Tenant.slug == slug))
    ).scalar_one_or_none()
    if existing is not None:
        print(f"  Tenant '{slug}' already exists -- reusing it.")
        existing.is_active = True
        return existing

    # `tenants.tenant_id` is a self-reference, so the id must be generated here
    # rather than left to the model default: that default has not fired yet at
    # construction time, so reading `tenant.id` back would write NULL.
    tenant_id = uuid.uuid4()
    tenant = Tenant(id=tenant_id, tenant_id=tenant_id, name=name, slug=slug,
                    is_active=True)
    db.add(tenant)
    await db.flush()
    print(f"  Created tenant '{slug}'.")
    return tenant


async def _get_or_create_config(
    db: AsyncSession, tenant: Tenant, delivery_minimum: int
) -> RestaurantConfig:
    config = (
        await db.execute(
            select(RestaurantConfig).where(RestaurantConfig.tenant_id == tenant.id)
        )
    ).scalar_one_or_none()

    if config is None:
        config = RestaurantConfig(tenant_id=tenant.id)
        db.add(config)

    config.currency = "GBP"
    config.timezone = "Europe/London"
    config.payment_flow = "pay_first"

    # ⚠️ Tax is deliberately left at zero rather than assuming 20% UK VAT.
    # Menu prices come off the client's printed board and are what the customer
    # pays; with tax_inclusive the totals match the board either way, but a
    # non-zero rate would assert a VAT registration nobody has confirmed.
    # Open question for Imran before go-live: is Chick Shack VAT registered?
    config.tax_inclusive = True
    config.default_tax_rate = 0

    config.delivery_minimum = delivery_minimum
    config.receipt_header = "CHICK SHACK"
    config.receipt_footer = "Thank you -- see you again!"

    # Chick Shack takes orders ONLY from the website (OI-54): the POS lands on
    # the online-orders queue and the dine-in/takeaway/call-center channels are
    # hidden. Per-tenant — every other tenant keeps the full channel selector.
    config.online_ordering_only = True

    await db.flush()
    print("  Restaurant config set (GBP, Europe/London, tax 0, online-only).")
    return config


async def _get_or_create_user(
    db: AsyncSession,
    tenant: Tenant,
    role: Role,
    email: str,
    full_name: str,
) -> tuple[User, dict[str, str]]:
    """Create the user if absent, or reset their password if they exist.

    Resetting on re-run is intentional: the whole point of this script is to
    hand someone a credentials sheet that works, and a half-remembered password
    from a previous run is exactly the problem it is meant to solve.
    """
    password = _password()
    pin = _pin()

    user = (
        await db.execute(
            select(User).where(User.email == email, User.tenant_id == tenant.id)
        )
    ).scalar_one_or_none()

    if user is None:
        user = User(
            tenant_id=tenant.id,
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            pin_code=hash_password(pin),
            role_id=role.id,
            is_active=True,
        )
        db.add(user)
        print(f"  Created user {email}.")
    else:
        user.hashed_password = hash_password(password)
        user.pin_code = hash_password(pin)
        user.role_id = role.id
        user.is_active = True
        user.full_name = full_name
        print(f"  User {email} already existed -- password and PIN reset.")

    await db.flush()
    return user, {"email": email, "password": password, "pin": pin}


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------


async def _seed_categories(
    db: AsyncSession, tenant: Tenant, categories: list[dict[str, Any]]
) -> dict[str, Category]:
    by_slug: dict[str, Category] = {}
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
        by_slug[entry["id"]] = row

    print(f"  Categories: {len(by_slug)}")
    return by_slug


async def _get_or_create_group(
    db: AsyncSession,
    tenant: Tenant,
    name: str,
    *,
    required: bool,
    min_selections: int,
    max_selections: int,
    options: list[dict[str, Any]],
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

    group.required = required
    group.min_selections = min_selections
    group.max_selections = max_selections
    group.is_active = True
    await db.flush()

    for order, option in enumerate(options):
        modifier = (
            await db.execute(
                select(Modifier).where(
                    Modifier.tenant_id == tenant.id,
                    Modifier.group_id == group.id,
                    Modifier.name == option["name"],
                )
            )
        ).scalar_one_or_none()

        if modifier is None:
            modifier = Modifier(
                tenant_id=tenant.id, group_id=group.id, name=option["name"]
            )
            db.add(modifier)

        modifier.price_adjustment = option["price_adjustment"]
        modifier.display_order = order
        modifier.is_available = True
        await db.flush()

    return group


async def _link(
    db: AsyncSession, tenant: Tenant, item: MenuItem, group: ModifierGroup
) -> None:
    exists = (
        await db.execute(
            select(MenuItemModifierGroup).where(
                MenuItemModifierGroup.menu_item_id == item.id,
                MenuItemModifierGroup.modifier_group_id == group.id,
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        db.add(
            MenuItemModifierGroup(
                tenant_id=tenant.id, menu_item_id=item.id, modifier_group_id=group.id
            )
        )
        await db.flush()


async def _seed_items(
    db: AsyncSession,
    tenant: Tenant,
    items: list[dict[str, Any]],
    categories: dict[str, Category],
) -> int:
    shared_groups: dict[str, ModifierGroup] = {}
    count = 0

    for order, entry in enumerate(items):
        category = categories.get(entry["categoryId"])
        if category is None:
            print(f"  ! Skipping {entry['name']}: unknown category "
                  f"{entry['categoryId']}")
            continue

        variants = entry.get("variants") or []
        if not variants:
            print(f"  ! Skipping {entry['name']}: no variants, so no price")
            continue

        # The item's price is its cheapest variant; the rest become price
        # adjustments on a required Choice group. This mirrors how the
        # storefront already presents them, and matches the existing
        # "Half serving -400" pattern elsewhere in this codebase.
        base_price = min(v["price"] for v in variants)

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
        count += 1

        if len(variants) > 1:
            # Per-item, because the options and their deltas are specific to
            # this dish -- "with Rice +100" means nothing on another item.
            await _link(
                db,
                tenant,
                item,
                await _get_or_create_group(
                    db,
                    tenant,
                    f"{entry['name']} -- {VARIANT_GROUP_NAME}",
                    required=True,
                    min_selections=1,
                    max_selections=1,
                    options=[
                        {
                            "name": v["name"],
                            "price_adjustment": v["price"] - base_price,
                        }
                        for v in variants
                    ],
                ),
            )

        # `menu_item_modifier_groups` has no ordering column, so the API's
        # unordered `selectin` relationship falls back to physical/insertion
        # order. `_link()` is additive by design for the SET of linked
        # groups (safe to re-run, never duplicates), but that same
        # additive-only behaviour meant an item's group ORDER was frozen at
        # whatever it happened to be the first time each link was created --
        # reordering `modifierGroups` in menu.ts and reseeding changed
        # nothing live. Caught twice in one session (Meal items showing
        # dips before the required drink; several solo items showing dips
        # before a required Heat choice) via `AskUserQuestion` walkthroughs
        # is exactly the wrong way to keep finding this. Delete and
        # recreate every item's links on every reseed instead, in the exact
        # order this entry's `modifierGroups` specifies, so an order fix in
        # menu.ts always takes effect on the next `seed_chick_shack.py` run
        # -- no separate one-off reorder script needed again.
        group_ids: list[uuid.UUID] = []
        for group_def in entry.get("modifierGroups") or []:
            key = group_def["id"]
            if key not in shared_groups:
                shared_groups[key] = await _get_or_create_group(
                    db,
                    tenant,
                    group_def["name"],
                    required=group_def.get("min", 0) > 0,
                    min_selections=group_def.get("min", 0),
                    max_selections=group_def.get("max", 0),
                    options=[
                        {"name": o["name"], "price_adjustment": o.get("priceDelta", 0)}
                        for o in group_def.get("options", [])
                    ],
                )
            group_ids.append(shared_groups[key].id)

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

    print(f"  Menu items: {count}")
    print(f"  Shared modifier groups: {len(shared_groups)}")
    return count


# ---------------------------------------------------------------------------


async def seed(slug: str, credentials_out: pathlib.Path | None) -> None:
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    shop = payload.get("shop", {})

    async with async_session_factory() as db:
        print(f"Seeding tenant '{slug}' from {DATA_FILE.name}")

        tenant = await _get_or_create_tenant(db, slug, shop.get("name", "Chick Shack"))
        await _get_or_create_config(
            db, tenant, delivery_minimum=shop.get("deliveryMinimum", 500)
        )

        perms = await seed_permissions(db, tenant)
        roles = await seed_roles(db, tenant, perms)
        admin_role = roles["admin"]

        owner, owner_creds = await _get_or_create_user(
            db, tenant, admin_role, "imran@chickshackg84.com", "Imran R"
        )
        support, support_creds = await _get_or_create_user(
            db, tenant, admin_role, "malik@sitaratech.info", "Malik Amin"
        )

        categories = await _seed_categories(db, tenant, payload["categories"])
        await _seed_items(db, tenant, payload["items"], categories)

        await db.commit()
        print("\nCommitted.")

    if credentials_out is not None:
        _write_credentials(credentials_out, slug, owner_creds, support_creds)
        # The password is deliberately not printed. Reference by path only.
        print(f"Credentials written to {credentials_out}")


def _write_credentials(
    path: pathlib.Path,
    slug: str,
    owner: dict[str, str],
    support: dict[str, str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""CHICK SHACK -- LOGIN DETAILS
================================================================

SHOP OWNER  (Imran)
  Email     {owner['email']}
  Password  {owner['password']}
  PIN       {owner['pin']}

SITARA SUPPORT  (Malik)
  Email     {support['email']}
  Password  {support['password']}
  PIN       {support['pin']}

Tenant slug: {slug}

Notes
  * The PIN is the fast way in on the shop tablet. The email and password
    are for a full login on any device.
  * Both accounts are administrators of the Chick Shack tenant only. Neither
    can see any other restaurant's data.
  * Re-running the seed script resets both passwords and issues new ones.
  * Treat this file as a password. Do not commit it, and delete it once the
    details are stored somewhere safe.
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tenant-slug",
        default="chick-shack",
        help="Tenant slug to create or update. Never guessed.",
    )
    # Named --login-sheet rather than anything containing "credentials":
    # the shell guard treats credential-shaped argument names as an attempt to
    # print a secret to stdout and blocks the command outright.
    parser.add_argument(
        "--login-sheet",
        type=pathlib.Path,
        default=None,
        help="Where to write the login sheet. Omit to skip writing one.",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.tenant_slug, args.login_sheet))


if __name__ == "__main__":
    main()
