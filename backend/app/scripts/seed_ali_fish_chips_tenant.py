"""Create the Ali Fish & Chips tenant: config, roles, users and delivery areas.

The menu is seeded separately by `seed_ali_fish_chips.py`, which expects this
tenant to exist already. Run this first.

Ali Fish & Chips & Curry House, 281 Main Road, Garelochhead G84 0AH. Takes
orders only from its website (alifishandchips.uk), like Chick Shack. Client
folder: `_context/clients/ali-fish-chips-uk/`.

Safety
------
* Idempotent. Re-running updates config and delivery fees in place; it never
  duplicates. It DOES reset the two users' passwords and PINs (same as the
  Chick Shack seeder), so only re-run when a new login sheet is wanted.
* Never guesses a tenant: the slug is fixed below and every query is scoped.
* Per `memory/data-integrity.md`: `pg_dump` before running this on production.

Usage
-----
    python -m app.scripts.seed_ali_fish_chips_tenant --login-sheet /tmp/ali_logins.txt
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib

from sqlalchemy import select

from app.database import async_session_factory
from app.models.delivery import DeliveryArea
from app.models.restaurant_config import RestaurantConfig
from app.scripts.seed import seed_permissions, seed_roles
from app.scripts.seed_chick_shack import _get_or_create_tenant, _get_or_create_user

SLUG = "ali-fish-chips"
NAME = "Ali Fish & Chips"

# The printed menu (March 2025) gives no delivery minimum. 0 until the client
# says otherwise. Server-enforced, so it must match the storefront's SHOP block.
DELIVERY_MINIMUM = 0

# (code, name, fee in pence), from the printed menu, spellings corrected. The
# codes MUST match the storefront's SHOP.deliveryAreas ids: the server looks the
# fee up by code and refuses anything it cannot find. Priced by village, not
# postcode (most of these share G84).
DELIVERY_AREAS: list[tuple[str, str, int]] = [
    ("garelochhead", "Garelochhead", 295),
    ("greenfields", "Greenfields Camp", 295),
    ("southgate", "Southgate & Shanden", 395),
    ("mambeg", "Mambeg, Clynder & Rahane", 395),
    ("portincaple", "Portincaple", 395),
    ("rhu", "Rhu", 450),
    ("rosneath", "Rosneath", 450),
    ("caravan-park", "Caravan Park", 595),
    ("kilcreggan", "Kilcreggan & Cove", 695),
    ("helensburgh", "Helensburgh", 995),
]

OWNER_EMAIL = "shop@alifishandchips.uk"
OWNER_NAME = "Ali Fish & Chips"
SUPPORT_EMAIL = "malik@sitaratech.info"
SUPPORT_NAME = "Malik Amin"


async def _config(db, tenant) -> None:
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
    # Same reasoning as Chick Shack: prices are what the printed menu says the
    # customer pays; no VAT registration has been confirmed, so no rate.
    config.tax_inclusive = True
    config.default_tax_rate = 0
    config.service_fee = 0
    config.delivery_minimum = DELIVERY_MINIMUM
    config.receipt_header = "ALI FISH & CHIPS"
    config.receipt_footer = "Thank you for your order!"
    config.online_ordering_only = True
    await db.flush()
    print("  Config: GBP, Europe/London, tax 0, no service fee, online-only.")


async def _delivery(db, tenant) -> None:
    existing = {
        a.code: a
        for a in (
            await db.execute(select(DeliveryArea).where(DeliveryArea.tenant_id == tenant.id))
        )
        .scalars()
        .all()
    }
    for position, (code, name, fee) in enumerate(DELIVERY_AREAS):
        area = existing.get(code)
        if area is None:
            db.add(
                DeliveryArea(
                    tenant_id=tenant.id,
                    code=code,
                    name=name,
                    fee=fee,
                    display_order=position,
                    is_active=True,
                )
            )
        else:
            area.name, area.fee, area.display_order, area.is_active = name, fee, position, True
    seeded = {code for code, _, _ in DELIVERY_AREAS}
    for code, area in existing.items():
        if code not in seeded:
            area.is_active = False
    await db.flush()
    print(f"  Delivery areas: {len(DELIVERY_AREAS)}, minimum {DELIVERY_MINIMUM}.")


async def seed(login_sheet: pathlib.Path | None) -> None:
    async with async_session_factory() as db:
        print(f"Seeding tenant '{SLUG}'")
        tenant = await _get_or_create_tenant(db, SLUG, NAME)
        await _config(db, tenant)
        await _delivery(db, tenant)

        perms = await seed_permissions(db, tenant)
        roles = await seed_roles(db, tenant, perms)
        owner, owner_creds = await _get_or_create_user(
            db, tenant, roles["admin"], OWNER_EMAIL, OWNER_NAME
        )
        support, support_creds = await _get_or_create_user(
            db, tenant, roles["admin"], SUPPORT_EMAIL, SUPPORT_NAME
        )

        await db.commit()
        print("Committed.")

    if login_sheet is not None:
        login_sheet.parent.mkdir(parents=True, exist_ok=True)
        login_sheet.write_text(
            "ALI FISH & CHIPS -- LOGIN DETAILS\n"
            "================================\n\n"
            f"SHOP (order tablet)\n  Email     {owner_creds['email']}\n"
            f"  Password  {owner_creds['password']}\n  PIN       {owner_creds['pin']}\n\n"
            f"SITARA SUPPORT\n  Email     {support_creds['email']}\n"
            f"  Password  {support_creds['password']}\n  PIN       {support_creds['pin']}\n\n"
            f"Tenant slug: {SLUG}\n"
            f"Tablet login: https://eats.sitaratech.info/login?shop={SLUG}\n\n"
            "Treat this file as a password. Do not commit it.\n",
            encoding="utf-8",
        )
        # The values are deliberately not printed. Reference by path only.
        print(f"Login sheet written to {login_sheet}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--login-sheet", type=pathlib.Path, default=None)
    args = parser.parse_args()
    asyncio.run(seed(args.login_sheet))


if __name__ == "__main__":
    main()
