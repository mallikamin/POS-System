"""Per-tenant UI module visibility, and the session knowing its own tenant.

Both came out of UAT on 2026-08-27.

⚠️ `hidden_ui_modules` is PRESENTATION ONLY. It hides navigation entries and
dashboard cards so a client is not shown modules they do not use. It does not
gate the endpoints behind them, because every admin route in this system is
gated by role and nothing else. The real per-tenant module gate is OI-93 and is
not built. There is a test below that pins that distinction, so nobody later
reads the feature as access control.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant

pytestmark = pytest.mark.asyncio


async def _config(db: AsyncSession, tenant: Tenant) -> RestaurantConfig:
    cfg = RestaurantConfig(tenant_id=tenant.id)
    db.add(cfg)
    await db.commit()
    return cfg


async def test_default_is_hide_nothing(
    db: AsyncSession, tenant: Tenant, admin_token: str, client
):
    """🔴 The property that makes this safe to ship to a live shared server.

    Every existing tenant must come out of this change with exactly the screens
    they had before. An empty string means hide nothing, so adding the column
    changes nobody's interface until a slug is deliberately written into it.
    """
    await _config(db, tenant)

    resp = await client.get(
        "/api/v1/config/restaurant",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["hidden_ui_modules"] == ""


async def test_the_response_carries_the_tenant_slug(
    db: AsyncSession, tenant: Tenant, admin_token: str, client
):
    """The session must be able to say which shop it belongs to.

    Without this the frontend inferred it from a localStorage value that any URL
    could overwrite, which is how the switch-account screen ended up showing one
    tenant's slug inside another tenant's session.
    """
    await _config(db, tenant)

    resp = await client.get(
        "/api/v1/config/restaurant",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    body = resp.json()
    assert body["tenant_slug"] == tenant.slug
    assert body["restaurant_name"] == tenant.name


async def test_hidden_modules_are_normalised_on_the_way_in(
    db: AsyncSession, tenant: Tenant, admin_token: str, client
):
    """It is hand-edited, so it will arrive untidy.

    Normalising on write means every reader can do a plain set membership test
    instead of each one reinventing trim-and-lowercase, which is exactly how two
    call sites end up disagreeing about whether "Dine-In" matches "dine-in".
    """
    await _config(db, tenant)

    resp = await client.patch(
        "/api/v1/config/restaurant",
        json={"hidden_ui_modules": " Dine-In , QuickBooks-Online ,, "},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["hidden_ui_modules"] == "dine-in,quickbooks-online"


async def test_patch_still_returns_the_restaurant_name(
    db: AsyncSession, tenant: Tenant, admin_token: str, client
):
    """PATCH used to answer without it, and a client re-reading config from that
    response lost the shop's name until the next full reload. That is one of the
    two things that put "Restaurant not loaded" on screen."""
    await _config(db, tenant)

    resp = await client.patch(
        "/api/v1/config/restaurant",
        json={"hidden_ui_modules": "dine-in"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    body = resp.json()
    assert body["restaurant_name"] == tenant.name
    assert body["tenant_slug"] == tenant.slug


async def test_hiding_a_module_does_NOT_close_its_endpoint(
    db: AsyncSession, tenant: Tenant, admin_token: str, client
):
    """🔴 Pins the honest limitation, deliberately.

    This is not a bug and this test must not be "fixed" by making it pass the
    other way without building OI-93 properly. Hiding a nav entry is cosmetic.
    The route behind it stays open because authorisation in this system is by
    ROLE. If someone later reads `hidden_ui_modules` as access control, this test
    is what tells them otherwise.
    """
    await _config(db, tenant)

    await client.patch(
        "/api/v1/config/restaurant",
        json={"hidden_ui_modules": "dine-in,quickbooks-online"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Still reachable, and that is the documented behaviour today.
    resp = await client.get(
        "/api/v1/locations",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200


async def test_clearing_it_restores_everything(
    db: AsyncSession, tenant: Tenant, admin_token: str, client
):
    """An empty string must clear, not be ignored as "no value supplied"."""
    await _config(db, tenant)

    await client.patch(
        "/api/v1/config/restaurant",
        json={"hidden_ui_modules": "dine-in"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.patch(
        "/api/v1/config/restaurant",
        json={"hidden_ui_modules": ""},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.json()["hidden_ui_modules"] == ""

    stored = (
        await db.execute(
            select(RestaurantConfig.hidden_ui_modules).where(
                RestaurantConfig.tenant_id == tenant.id
            )
        )
    ).scalar_one()
    assert stored == ""
