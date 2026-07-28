"""Tenant routing on the public storefront routes, and the merchant queue.

Why this file exists
--------------------
`public.py` used to resolve the storefront's tenant with

    SELECT id FROM tenants WHERE is_active LIMIT 1

There is no ORDER BY in that query, so with more than one active tenant it
returns an arbitrary row. This deployment already carries several
(`demo-restaurant`, `yk-online`, `yk-desktop`, `chick-shack`), which meant a UK
storefront could have been served a Pakistani menu priced in rupees -- or worse,
had a customer's order written against another restaurant's books.

Every test below that involves two tenants exists to keep that from coming back.
The single-tenant tests would all have passed against the broken version, so they
are not the point; the cross-tenant ones are.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu import Category, MenuItem
from app.models.order import Order
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.models.user import Role, User

pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


QUEUE_URL = "/api/v1/public/manage/orders"


# ---------------------------------------------------------------------------
# Fixtures -- a menu for each of the two tenants, with distinguishable items
# ---------------------------------------------------------------------------


async def _make_menu(
    db: AsyncSession, tenant_id: uuid.UUID, item_name: str, price: int
) -> MenuItem:
    category = Category(
        tenant_id=tenant_id, name=f"{item_name} Category", display_order=1
    )
    db.add(category)
    await db.flush()

    item = MenuItem(
        tenant_id=tenant_id,
        category_id=category.id,
        name=item_name,
        price=price,
        is_available=True,
    )
    db.add(item)
    await db.commit()
    return item


@pytest_asyncio.fixture
async def uk_menu(db: AsyncSession, tenant: Tenant, admin_role: Role) -> MenuItem:
    """A fully orderable tenant: config, at least one role, and an item.

    `admin_role` is not incidental. `create_public_order` attaches its orders to
    a dedicated non-login user, and creating that user needs some active role to
    hang it on -- without one every order fails with "Restaurant is not
    configured to take online orders". A cross-tenant test asserting 409 would
    then pass whether or not cross-tenant ordering was actually blocked.
    """
    db.add(RestaurantConfig(tenant_id=tenant.id, currency="GBP"))
    await db.flush()
    return await _make_menu(db, tenant.id, "Peri Peri Half Chicken", 850)


@pytest_asyncio.fixture
async def pk_menu(db: AsyncSession, other_tenant: Tenant) -> MenuItem:
    db.add(RestaurantConfig(tenant_id=other_tenant.id, currency="PKR"))
    await db.flush()
    return await _make_menu(db, other_tenant.id, "Chicken Karahi", 145000)


# ---------------------------------------------------------------------------
# Slug resolution
# ---------------------------------------------------------------------------


async def test_menu_is_served_for_a_known_slug(
    client: AsyncClient, uk_menu: MenuItem
):
    resp = await client.get("/api/v1/public/test-restaurant/menu")
    assert resp.status_code == 200
    names = [i["name"] for c in resp.json()["categories"] for i in c["items"]]
    assert "Peri Peri Half Chicken" in names


async def test_unknown_slug_is_404(client: AsyncClient, uk_menu: MenuItem):
    resp = await client.get("/api/v1/public/no-such-restaurant/menu")
    assert resp.status_code == 404


@pytest.mark.parametrize("slug", ["manage", "orders", "menu", "health"])
async def test_reserved_slugs_are_refused(
    client: AsyncClient, uk_menu: MenuItem, slug: str
):
    """A tenant slugged `manage` would make /public/manage/orders ambiguous."""
    resp = await client.get(f"/api/v1/public/{slug}/menu")
    assert resp.status_code == 404


async def test_inactive_tenant_is_404(
    client: AsyncClient, db: AsyncSession, tenant: Tenant, uk_menu: MenuItem
):
    tenant.is_active = False
    await db.commit()

    resp = await client.get("/api/v1/public/test-restaurant/menu")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# The cross-tenant tests -- the actual reason this file exists
# ---------------------------------------------------------------------------


async def test_each_slug_gets_only_its_own_menu(
    client: AsyncClient, uk_menu: MenuItem, pk_menu: MenuItem
):
    """Two active tenants, two menus, no bleed in either direction.

    Against the old `LIMIT 1` resolver one of these two assertions was a coin
    toss decided by Postgres' physical row order.
    """
    uk = await client.get("/api/v1/public/test-restaurant/menu")
    pk = await client.get("/api/v1/public/other-restaurant/menu")
    assert uk.status_code == 200 and pk.status_code == 200

    uk_names = [i["name"] for c in uk.json()["categories"] for i in c["items"]]
    pk_names = [i["name"] for c in pk.json()["categories"] for i in c["items"]]

    assert "Peri Peri Half Chicken" in uk_names
    assert "Chicken Karahi" not in uk_names
    assert "Chicken Karahi" in pk_names
    assert "Peri Peri Half Chicken" not in pk_names


async def test_currency_follows_the_slug_not_the_first_row(
    client: AsyncClient, uk_menu: MenuItem, pk_menu: MenuItem
):
    """The failure this guards is a UK customer shown prices in rupees."""
    uk = await client.get("/api/v1/public/test-restaurant/menu")
    pk = await client.get("/api/v1/public/other-restaurant/menu")

    assert uk.json()["currency"] == "GBP"
    assert pk.json()["currency"] == "PKR"


async def test_order_is_written_to_the_tenant_named_in_the_path(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    uk_menu: MenuItem,
    pk_menu: MenuItem,
):
    """An order placed on one storefront must never land on another's books."""
    resp = await client.post(
        "/api/v1/public/test-restaurant/orders",
        json={
            "service_type": "collection",
            "customer_name": "Imran R",
            "customer_phone": "07909313456",
            "items": [{"menu_item_id": str(uk_menu.id), "quantity": 1}],
        },
    )
    assert resp.status_code == 201, resp.text

    order = await db.get(Order, uuid.UUID(resp.json()["id"]))
    assert order is not None
    assert order.tenant_id == tenant.id


async def test_cannot_order_another_tenants_item_through_your_slug(
    client: AsyncClient, uk_menu: MenuItem, pk_menu: MenuItem
):
    """Posting a valid item ID belonging to a different tenant must fail.

    Menu item IDs are UUIDs and the public menu exposes them, so this is a
    reachable request, not a theoretical one.
    """
    resp = await client.post(
        "/api/v1/public/test-restaurant/orders",
        json={
            "service_type": "collection",
            "customer_name": "Imran R",
            "customer_phone": "07909313456",
            "items": [{"menu_item_id": str(pk_menu.id), "quantity": 1}],
        },
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# The merchant queue -- what the shop's tablet polls
# ---------------------------------------------------------------------------


async def _online_order(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    number: str,
    *,
    minutes_ago: int = 0,
    accepted: bool = False,
    rejected: bool = False,
) -> Order:
    now = datetime.now(timezone.utc)
    order = Order(
        tenant_id=tenant_id,
        order_number=number,
        order_type="online",
        status="voided" if rejected else ("in_kitchen" if accepted else "confirmed"),
        payment_status="unpaid",
        customer_name="Imran R",
        customer_phone="07909313456",
        subtotal=850,
        tax_amount=0,
        discount_amount=0,
        delivery_fee=300,
        total=1150,
        service_type="delivery",
        delivery_address="12 Feorlin Way",
        delivery_area="Garelochhead",
        created_by=user_id,
        created_at=now - timedelta(minutes=minutes_ago),
        accepted_at=now if accepted else None,
        rejected_at=now if rejected else None,
        eta_minutes=30 if accepted else None,
    )
    db.add(order)
    await db.commit()
    return order


async def test_queue_requires_authentication(client: AsyncClient):
    """It is a list of names, phone numbers and home addresses."""
    resp = await client.get(QUEUE_URL)
    assert resp.status_code in (401, 403)


async def test_queue_returns_only_the_callers_tenant(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    other_tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    await _online_order(db, tenant.id, admin_user.id, "260728-001")
    await _online_order(db, other_tenant.id, admin_user.id, "260728-999")

    resp = await client.get(QUEUE_URL, headers=_auth(admin_token))
    assert resp.status_code == 200

    numbers = [o["order_number"] for o in resp.json()["orders"]]
    assert numbers == ["260728-001"]


async def test_pending_excludes_accepted_and_rejected(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    await _online_order(db, tenant.id, admin_user.id, "260728-001")
    await _online_order(db, tenant.id, admin_user.id, "260728-002", accepted=True)
    await _online_order(db, tenant.id, admin_user.id, "260728-003", rejected=True)

    resp = await client.get(QUEUE_URL, headers=_auth(admin_token))
    numbers = [o["order_number"] for o in resp.json()["orders"]]
    assert numbers == ["260728-001"]


async def test_active_is_accepted_and_still_working(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    await _online_order(db, tenant.id, admin_user.id, "260728-001")
    await _online_order(db, tenant.id, admin_user.id, "260728-002", accepted=True)
    await _online_order(db, tenant.id, admin_user.id, "260728-003", rejected=True)

    resp = await client.get(
        QUEUE_URL, params={"state": "active"}, headers=_auth(admin_token)
    )
    numbers = [o["order_number"] for o in resp.json()["orders"]]
    assert numbers == ["260728-002"]


async def test_pending_is_oldest_first(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    """A work queue, not a log.

    The customer who has been waiting longest is the one who needs answering,
    so pending ascends by placement time while the other views descend.
    """
    await _online_order(db, tenant.id, admin_user.id, "260728-new", minutes_ago=1)
    await _online_order(db, tenant.id, admin_user.id, "260728-old", minutes_ago=20)

    resp = await client.get(QUEUE_URL, headers=_auth(admin_token))
    numbers = [o["order_number"] for o in resp.json()["orders"]]
    assert numbers == ["260728-old", "260728-new"]


async def test_queue_card_carries_what_the_shop_needs_to_work_the_order(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    """Phone, address and area -- the three fields the customer-facing
    response deliberately withholds and the shop cannot operate without."""
    await _online_order(db, tenant.id, admin_user.id, "260728-001")

    resp = await client.get(QUEUE_URL, headers=_auth(admin_token))
    card = resp.json()["orders"][0]

    assert card["customer_phone"] == "07909313456"
    assert card["delivery_address"] == "12 Feorlin Way"
    assert card["delivery_area"] == "Garelochhead"
    assert card["currency"] == "GBP"
