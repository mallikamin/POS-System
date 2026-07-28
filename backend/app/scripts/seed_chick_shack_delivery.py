"""Seed Chick Shack UK delivery areas and the delivery minimum.

Why this exists
---------------
`delivery_areas` starts empty. `public_order_service` looks the fee up in that
table and rejects anything it cannot find, so until this runs **every delivery
order is refused** with "We do not deliver to that area." The storefront looks
fine while this is broken, because the storefront carries its own copy of the
list in `storefront/src/data/menu.ts` -- which is exactly why the two must be
kept in step.

Source of truth
---------------
The client's print-ready A4 menu (artwork dated 05/2026), transcribed to
`_context/clients/chick-shack-uk/refs/` and cross-checked item by item against
`storefront/src/data/menu.ts`. Fees are integer pence.

Priced BY VILLAGE, not by postcode. Nearly all of these villages share the same
G84 outward code, so a postcode-prefix rule quotes 3.00 for a 15.00 Arrochar
run. Do not "simplify" this into a postcode lookup.

Usage
-----
    docker exec pos-system-backend-1 python -m app.scripts.seed_chick_shack_delivery
    # optionally target a specific tenant
    ... python -m app.scripts.seed_chick_shack_delivery --tenant-slug chick-shack

Idempotent. Re-running updates names, fees and ordering in place and reactivates
anything previously deactivated; it never deletes and never duplicates, so it is
safe to re-run on the server after a price change.
"""

import argparse
import asyncio
import uuid

from sqlalchemy import select

from app.database import async_session_factory
from app.models.delivery import DeliveryArea
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant

# (code, name, fee in pence). Order here is the order shown in the picker.
DELIVERY_AREAS: list[tuple[str, str, int]] = [
    ("garelochhead", "Garelochhead", 300),
    ("greenfields", "Greenfields Camp", 300),
    ("southgate", "Southgate & Shanden", 400),
    ("mambeg", "Mambeg, Clynder & Rahane", 400),
    ("portincaple", "Portincaple", 400),
    ("rhu", "Rhu", 450),
    ("rosneath", "Rosneath", 450),
    ("caravan-park", "Caravan Park", 600),
    ("kilcreggan", "Kilcreggan & Cove", 700),
    ("helensburgh", "Helensburgh", 1000),
    ("arrochar", "Arrochar", 1500),
]

# £5.00. Enforced server-side, not just as a storefront check.
DELIVERY_MINIMUM = 500


async def _resolve_tenant_id(db, slug: str | None) -> uuid.UUID:
    """Find the target tenant.

    Mirrors `_resolve_tenant_id` in the auth service: with a single active
    tenant, do not make the caller name it. With several, refuse to guess --
    seeding the wrong tenant's delivery table is a silent pricing bug.
    """
    if slug:
        tenant = (
            await db.execute(select(Tenant).where(Tenant.slug == slug))
        ).scalar_one_or_none()
        if tenant is None:
            raise SystemExit(f"No tenant with slug {slug!r}.")
        return tenant.id

    tenants = (
        (await db.execute(select(Tenant).where(Tenant.is_active.is_(True))))
        .scalars()
        .all()
    )
    if not tenants:
        raise SystemExit("No active tenants.")
    if len(tenants) > 1:
        names = ", ".join(f"{t.slug}" for t in tenants)
        raise SystemExit(
            f"{len(tenants)} active tenants ({names}). "
            "Pass --tenant-slug; refusing to guess."
        )
    return tenants[0].id


async def seed(slug: str | None) -> None:
    async with async_session_factory() as db:
        tenant_id = await _resolve_tenant_id(db, slug)

        existing = {
            area.code: area
            for area in (
                await db.execute(
                    select(DeliveryArea).where(DeliveryArea.tenant_id == tenant_id)
                )
            )
            .scalars()
            .all()
        }

        created = updated = unchanged = 0
        for position, (code, name, fee) in enumerate(DELIVERY_AREAS):
            area = existing.get(code)
            if area is None:
                db.add(
                    DeliveryArea(
                        tenant_id=tenant_id,
                        code=code,
                        name=name,
                        fee=fee,
                        display_order=position,
                        is_active=True,
                    )
                )
                created += 1
                continue

            # Update in place rather than delete-and-recreate: orders reference
            # the area by name, and churning ids for no reason loses history.
            if (
                area.name == name
                and area.fee == fee
                and area.display_order == position
                and area.is_active
            ):
                unchanged += 1
                continue

            area.name = name
            area.fee = fee
            area.display_order = position
            area.is_active = True
            updated += 1

        config = (
            await db.execute(
                select(RestaurantConfig).where(RestaurantConfig.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()

        if config is None:
            print("  ! No restaurant_config row -- delivery minimum NOT set.")
        elif config.delivery_minimum != DELIVERY_MINIMUM:
            config.delivery_minimum = DELIVERY_MINIMUM
            print(f"  delivery_minimum -> {DELIVERY_MINIMUM} ({DELIVERY_MINIMUM / 100:.2f})")
        else:
            print(f"  delivery_minimum already {DELIVERY_MINIMUM}")

        # Anything in the table that is no longer on the menu is deactivated
        # rather than deleted, so historic orders keep resolving their area.
        seeded_codes = {code for code, _, _ in DELIVERY_AREAS}
        retired = 0
        for code, area in existing.items():
            if code not in seeded_codes and area.is_active:
                area.is_active = False
                retired += 1

        await db.commit()

        print(
            f"Delivery areas for tenant {tenant_id}: "
            f"{created} created, {updated} updated, {unchanged} unchanged, "
            f"{retired} retired."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tenant-slug",
        default=None,
        help="Tenant to seed. Omit when there is exactly one active tenant.",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.tenant_slug))


if __name__ == "__main__":
    main()
