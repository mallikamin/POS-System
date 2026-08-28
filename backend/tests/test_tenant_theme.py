"""Per-tenant visual theme, and the property that makes it safe to ship.

The whole safety argument for theming one restaurant on a shared production
server is that `theme` is NULL for everybody else. NULL means the frontend
stamps no attribute on the root element, the `:root` defaults in `index.css`
apply, and the screens render exactly as they did before theming existed.

⚠️ PRESENTATION ONLY, like `hidden_ui_modules` beside it. A theme must never
gate behaviour, and an unrecognised name must fall back to the standard look
rather than erroring, so a typo in one tenant's config cannot take its screens
down.
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


async def test_default_is_no_theme(
    db: AsyncSession, tenant: Tenant, admin_token: str, client
):
    """🔴 The property that makes this safe to ship to a live shared server.

    A tenant that never asked for a theme has none, so every existing
    restaurant keeps the look it has today. Adding the column changes nobody's
    appearance until a name is deliberately written into it.
    """
    await _config(db, tenant)

    resp = await client.get(
        "/api/v1/config/restaurant",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert "theme" in body, (
        "the field must be present in the response; a response field with no "
        "matching client type is silent in both directions until it breaks"
    )
    assert body["theme"] is None


async def test_a_theme_is_reported_when_set(
    db: AsyncSession, tenant: Tenant, admin_token: str, client
):
    """Setting a theme on a tenant surfaces it on that tenant's config."""
    cfg = await _config(db, tenant)
    cfg.theme = "desert-salt"
    await db.commit()

    resp = await client.get(
        "/api/v1/config/restaurant",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["theme"] == "desert-salt"


async def test_theming_one_tenant_leaves_the_others_alone(
    db: AsyncSession, tenant: Tenant, other_tenant: Tenant, admin_token: str, client
):
    """🔴 Cross-tenant isolation, stated as a test rather than as an intention.

    This is the Chick Shack question: giving one restaurant a palette must not
    reach any other row. If this ever fails, a themed client has restyled
    somebody else's live shop.
    """
    cfg = await _config(db, tenant)
    other = RestaurantConfig(tenant_id=other_tenant.id)
    db.add(other)
    await db.commit()

    cfg.theme = "desert-salt"
    await db.commit()

    rows = (
        await db.execute(
            select(RestaurantConfig).where(
                RestaurantConfig.tenant_id != tenant.id
            )
        )
    ).scalars().all()

    assert rows, "expected at least one other tenant's config to exist"
    assert all(r.theme is None for r in rows), (
        "theming one tenant changed another tenant's configuration"
    )


async def test_a_theme_can_be_cleared(db: AsyncSession, tenant: Tenant):
    """Clearing returns the tenant to the standard look, with no residue."""
    cfg = await _config(db, tenant)
    cfg.theme = "desert-salt"
    await db.commit()

    cfg.theme = None
    await db.commit()
    await db.refresh(cfg)

    assert cfg.theme is None
