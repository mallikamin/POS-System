"""PIN login must never authenticate across tenants.

The bug this file exists to prevent
-----------------------------------
`POST /auth/login/pin` used to loop every active tenant and return the first
user whose PIN matched:

    for tid in tenant_ids:
        try:
            user = await authenticate_by_pin(db, body.pin, tid)
            break
        except ValueError:
            continue

That is not a failed login, it is the *wrong* login. Four digits is a space of
10,000 and real POS PINs cluster on memorable numbers -- the demo tenant ships
1234 / 5678 / 9012 -- so a new restaurant issued 1234 would have been dropped
inside another restaurant's data holding a valid token for it.

`authenticate_by_pin` itself was never at fault; it has always scoped to
`User.tenant_id`. The flaw was entirely in the route deciding which tenants to
try.

Password login keeps its cross-tenant search on purpose: a collision there
needs the same email *and* the same password, not four matching digits.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.models.user import Role, User
from app.utils.security import hash_password

pytestmark = pytest.mark.asyncio

PIN_URL = "/api/v1/auth/login/pin"
PASSWORD_URL = "/api/v1/auth/login"

# The same PIN, deliberately issued in two different restaurants.
SHARED_PIN = "1234"


@pytest_asyncio.fixture
async def user_in_home_tenant(
    db: AsyncSession, tenant: Tenant, admin_role: Role
) -> User:
    user = User(
        tenant_id=tenant.id,
        email="home@example.com",
        full_name="Home Tenant User",
        hashed_password=hash_password("home-password"),
        pin_code=hash_password(SHARED_PIN),
        role_id=admin_role.id,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    return user


@pytest_asyncio.fixture
async def user_in_other_tenant(
    db: AsyncSession, other_tenant: Tenant, other_tenant_role: Role
) -> User:
    """A different person, in a different restaurant, with the same PIN."""
    user = User(
        tenant_id=other_tenant.id,
        email="other@example.com",
        full_name="Other Tenant User",
        hashed_password=hash_password("other-password"),
        pin_code=hash_password(SHARED_PIN),
        role_id=other_tenant_role.id,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    return user


# ---------------------------------------------------------------------------
# The regression
# ---------------------------------------------------------------------------


async def test_pin_login_returns_the_user_from_the_named_tenant(
    client: AsyncClient,
    user_in_home_tenant: User,
    user_in_other_tenant: User,
):
    """Two restaurants, one PIN, and the slug decides which person you are.

    Against the old route this was a coin toss decided by row order.
    """
    home = await client.post(
        PIN_URL, json={"pin": SHARED_PIN, "tenant_slug": "test-restaurant"}
    )
    other = await client.post(
        PIN_URL, json={"pin": SHARED_PIN, "tenant_slug": "other-restaurant"}
    )

    assert home.status_code == 200, home.text
    assert other.status_code == 200, other.text

    assert home.json()["user"]["email"] == "home@example.com"
    assert other.json()["user"]["email"] == "other@example.com"


async def test_pin_login_refuses_when_the_pin_is_genuinely_ambiguous(
    client: AsyncClient,
    user_in_home_tenant: User,
    user_in_other_tenant: User,
):
    """No slug, and the PIN matches a real person in TWO restaurants.

    Refusing is the whole fix. Returning the first match is what put someone
    in the wrong restaurant's data.
    """
    resp = await client.post(PIN_URL, json={"pin": SHARED_PIN})
    assert resp.status_code == 400
    assert "more than one restaurant" in resp.json()["detail"].lower()


async def test_pin_login_still_works_across_tenants_when_unambiguous(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    other_tenant: Tenant,
    admin_role: Role,
    other_tenant_role: Role,
):
    """Two restaurants, DIFFERENT PINs, no slug -- log the right person in.

    This is the case that must not regress. The live server already hosts more
    than one restaurant behind a single frontend that sends no tenant, so
    demanding a slug outright would have broken every existing PIN login on
    deploy. Only a real collision is refused.
    """
    db.add(
        User(
            tenant_id=tenant.id,
            email="a@example.com",
            full_name="Restaurant A Staff",
            hashed_password=hash_password("pw-a"),
            pin_code=hash_password("4455"),
            role_id=admin_role.id,
            is_active=True,
        )
    )
    db.add(
        User(
            tenant_id=other_tenant.id,
            email="b@example.com",
            full_name="Restaurant B Staff",
            hashed_password=hash_password("pw-b"),
            pin_code=hash_password("7788"),
            role_id=other_tenant_role.id,
            is_active=True,
        )
    )
    await db.commit()

    a = await client.post(PIN_URL, json={"pin": "4455"})
    b = await client.post(PIN_URL, json={"pin": "7788"})

    assert a.status_code == 200, a.text
    assert b.status_code == 200, b.text
    assert a.json()["user"]["email"] == "a@example.com"
    assert b.json()["user"]["email"] == "b@example.com"


async def test_pin_login_still_works_with_one_tenant_and_no_slug(
    client: AsyncClient, user_in_home_tenant: User
):
    """Backward compatibility for the existing POS demo.

    Its frontend sends no tenant at all. With exactly one active tenant there
    is nothing to be ambiguous about, so that must keep working.
    """
    resp = await client.post(PIN_URL, json={"pin": SHARED_PIN})
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["email"] == "home@example.com"


async def test_pin_from_another_tenant_is_rejected_not_redirected(
    client: AsyncClient,
    db: AsyncSession,
    user_in_other_tenant: User,
    tenant: Tenant,
):
    """A PIN that exists only in another restaurant must simply fail here."""
    resp = await client.post(
        PIN_URL, json={"pin": SHARED_PIN, "tenant_slug": "test-restaurant"}
    )
    assert resp.status_code == 401


async def test_unknown_slug_does_not_reveal_that_it_is_unknown(
    client: AsyncClient, user_in_home_tenant: User
):
    """401, not 404. A 404 would let anyone enumerate the tenants on the box."""
    resp = await client.post(
        PIN_URL, json={"pin": SHARED_PIN, "tenant_slug": "no-such-restaurant"}
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Password login keeps its cross-tenant search, and honours an explicit slug
# ---------------------------------------------------------------------------


async def test_password_login_still_finds_the_user_without_a_slug(
    client: AsyncClient,
    user_in_home_tenant: User,
    user_in_other_tenant: User,
):
    resp = await client.post(
        PASSWORD_URL, json={"email": "home@example.com", "password": "home-password"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["email"] == "home@example.com"


async def test_password_login_scoped_by_slug_rejects_the_wrong_tenant(
    client: AsyncClient,
    user_in_home_tenant: User,
    user_in_other_tenant: User,
):
    """Right credentials, wrong restaurant named -- must fail."""
    resp = await client.post(
        PASSWORD_URL,
        json={
            "email": "home@example.com",
            "password": "home-password",
            "tenant_slug": "other-restaurant",
        },
    )
    assert resp.status_code == 401
