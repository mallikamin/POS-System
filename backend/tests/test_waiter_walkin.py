"""Tests for Slice 2: waiter assignment + walk-in customer default.

Covers:
- Open table session with waiter_id → session has waiter
- Create dine-in order → inherits waiter from session
- Create dine-in order without customer → gets walk-in customer_id + name
- Create call-center order with phone → links to existing customer_id
- GET /staff/waiters returns non-kitchen staff
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.menu import Category, MenuItem
from app.models.user import User
from tests.conftest import make_token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# Fixtures
# =========================================================================

@pytest_asyncio.fixture
async def menu_item(db: AsyncSession, tenant) -> MenuItem:
    cat = Category(tenant_id=tenant.id, name="BBQ", display_order=1, is_active=True)
    db.add(cat)
    await db.flush()
    item = MenuItem(
        tenant_id=tenant.id, category_id=cat.id,
        name="Chicken Tikka", price=35000, is_available=True,
    )
    db.add(item)
    await db.flush()
    await db.commit()
    return item


@pytest_asyncio.fixture
async def walkin_customer(db: AsyncSession, tenant) -> Customer:
    """Walk-in customer seeded per tenant."""
    c = Customer(
        tenant_id=tenant.id, name="Walk-in Customer", phone="0000000000",
    )
    db.add(c)
    await db.flush()
    await db.commit()
    return c


@pytest_asyncio.fixture
async def known_customer(db: AsyncSession, tenant) -> Customer:
    """A known customer with a phone number."""
    c = Customer(
        tenant_id=tenant.id, name="Ahmad Khan", phone="03001234567",
    )
    db.add(c)
    await db.flush()
    await db.commit()
    return c


def _dine_in_payload(menu_item_id: uuid.UUID, table_id: uuid.UUID, **overrides) -> dict:
    base = {
        "order_type": "dine_in",
        "table_id": str(table_id),
        "items": [
            {
                "menu_item_id": str(menu_item_id),
                "name": "Chicken Tikka",
                "quantity": 2,
                "unit_price": 35000,
            }
        ],
    }
    base.update(overrides)
    return base


# =========================================================================
# 1. Open table session with waiter
# =========================================================================
class TestTableSessionWaiter:
    """POST /api/v1/table-sessions/open with waiter_id."""

    async def test_open_session_with_waiter(
        self, client: AsyncClient, admin_token: str, table, cashier_user: User,
    ):
        resp = await client.post(
            "/api/v1/table-sessions/open",
            json={"table_id": str(table.id), "waiter_id": str(cashier_user.id)},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200 or resp.status_code == 201
        body = resp.json()
        assert body["assigned_waiter_id"] == str(cashier_user.id)
        assert body["assigned_waiter_name"] == cashier_user.full_name

    async def test_open_session_without_waiter(
        self, client: AsyncClient, admin_token: str, table,
    ):
        resp = await client.post(
            "/api/v1/table-sessions/open",
            json={"table_id": str(table.id)},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200 or resp.status_code == 201
        body = resp.json()
        assert body.get("assigned_waiter_id") is None


# =========================================================================
# 2. Dine-in order inherits waiter from session
# =========================================================================
class TestOrderInheritsWaiter:
    """Create a dine-in order where the session has a waiter assigned."""

    async def test_order_inherits_waiter_via_session(
        self, client: AsyncClient, admin_token: str, table,
        cashier_user: User, menu_item: MenuItem, walkin_customer: Customer,
    ):
        # Open session with waiter
        await client.post(
            "/api/v1/table-sessions/open",
            json={"table_id": str(table.id), "waiter_id": str(cashier_user.id)},
            headers=_auth(admin_token),
        )
        # Create dine-in order
        payload = _dine_in_payload(menu_item.id, table.id)
        resp = await client.post(
            "/api/v1/orders", json=payload, headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["waiter_id"] == str(cashier_user.id)
        assert body["waiter_name"] == cashier_user.full_name

    async def test_order_passes_waiter_to_auto_session(
        self, client: AsyncClient, admin_token: str, table,
        cashier_user: User, menu_item: MenuItem, walkin_customer: Customer,
    ):
        """When no session exists, waiter_id in order payload creates session with waiter."""
        payload = _dine_in_payload(
            menu_item.id, table.id, waiter_id=str(cashier_user.id)
        )
        resp = await client.post(
            "/api/v1/orders", json=payload, headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["waiter_id"] == str(cashier_user.id)

        # Verify session was created with waiter
        sess_resp = await client.get(
            f"/api/v1/table-sessions/table/{table.id}/active",
            headers=_auth(admin_token),
        )
        assert sess_resp.status_code == 200
        sess = sess_resp.json()
        assert sess["assigned_waiter_id"] == str(cashier_user.id)


# =========================================================================
# 3. Walk-in customer default
# =========================================================================
class TestWalkInCustomerDefault:
    """Dine-in/takeaway orders without customer name get walk-in default."""

    async def test_dine_in_gets_walkin_customer(
        self, client: AsyncClient, admin_token: str, table,
        menu_item: MenuItem, walkin_customer: Customer,
    ):
        payload = _dine_in_payload(menu_item.id, table.id)
        resp = await client.post(
            "/api/v1/orders", json=payload, headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["customer_name"] == "Walk-in Customer"
        assert body["customer_id"] == str(walkin_customer.id)

    async def test_takeaway_gets_walkin_customer(
        self, client: AsyncClient, cashier_token: str,
        menu_item: MenuItem, walkin_customer: Customer,
    ):
        payload = {
            "order_type": "takeaway",
            "items": [
                {
                    "menu_item_id": str(menu_item.id),
                    "name": "Chicken Tikka",
                    "quantity": 1,
                    "unit_price": 35000,
                }
            ],
        }
        resp = await client.post(
            "/api/v1/orders", json=payload, headers=_auth(cashier_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["customer_name"] == "Walk-in Customer"
        assert body["customer_id"] == str(walkin_customer.id)


# =========================================================================
# 4. Call-center links to existing customer
# =========================================================================
class TestCallCenterCustomerLinking:
    """Call-center order with phone matches existing customer."""

    async def test_call_center_links_customer_by_phone(
        self, client: AsyncClient, cashier_token: str,
        menu_item: MenuItem, known_customer: Customer,
    ):
        payload = {
            "order_type": "call_center",
            "customer_name": "Ahmad Khan",
            "customer_phone": "03001234567",
            "items": [
                {
                    "menu_item_id": str(menu_item.id),
                    "name": "Chicken Tikka",
                    "quantity": 1,
                    "unit_price": 35000,
                }
            ],
        }
        resp = await client.post(
            "/api/v1/orders", json=payload, headers=_auth(cashier_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["customer_id"] == str(known_customer.id)


# =========================================================================
# 5. GET /staff/waiters
# =========================================================================
class TestWaitersEndpoint:
    """GET /api/v1/staff/waiters returns non-kitchen staff."""

    async def test_waiters_excludes_kitchen_role(
        self, client: AsyncClient, cashier_token: str,
        admin_user: User, cashier_user: User, kitchen_user: User,
    ):
        resp = await client.get(
            "/api/v1/staff/waiters", headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        ids = {w["id"] for w in data}
        # Admin and cashier are eligible
        assert str(admin_user.id) in ids
        assert str(cashier_user.id) in ids
        # Kitchen is excluded
        assert str(kitchen_user.id) not in ids

    async def test_waiters_returns_name_and_role(
        self, client: AsyncClient, admin_token: str,
        admin_user: User,
    ):
        resp = await client.get(
            "/api/v1/staff/waiters", headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        entry = data[0]
        assert "id" in entry
        assert "name" in entry
        assert "role" in entry
