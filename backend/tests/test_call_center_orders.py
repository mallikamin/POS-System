"""Tests for call-center order integrity (Phase 8 contract).

Covers: call_center order creation with customer fields, missing phone rejection,
non-call-center orders unaffected, phone normalization, and customer
order-history consistency with newly created call-center orders.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu import Category, MenuItem
from app.models.user import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# Fixtures
# =========================================================================

@pytest_asyncio.fixture
async def menu_item(db: AsyncSession, tenant) -> MenuItem:
    """A single menu item for building order payloads."""
    cat = Category(tenant_id=tenant.id, name="BBQ", display_order=1, is_active=True)
    db.add(cat)
    await db.flush()
    item = MenuItem(
        tenant_id=tenant.id,
        category_id=cat.id,
        name="Chicken Tikka",
        price=35000,
        is_available=True,
    )
    db.add(item)
    await db.flush()
    await db.commit()
    return item


def _order_payload(menu_item_id: uuid.UUID, **overrides) -> dict:
    """Build a minimal order creation payload."""
    base = {
        "order_type": "call_center",
        "customer_name": "Ahmad Khan",
        "customer_phone": "03001234567",
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
# 1. Call-Center Order Creation with Customer Fields
# =========================================================================
class TestCallCenterOrderCreation:
    """POST /api/v1/orders with order_type=call_center"""

    async def test_create_with_customer_fields(
        self, client: AsyncClient, cashier_token: str, menu_item: MenuItem
    ):
        payload = _order_payload(menu_item.id)
        resp = await client.post(
            "/api/v1/orders", json=payload, headers=_auth(cashier_token)
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["order_type"] == "call_center"
        assert body["customer_name"] == "Ahmad Khan"
        assert body["customer_phone"] == "03001234567"
        assert body["status"] == "in_kitchen"
        assert body["payment_status"] == "unpaid"
        assert len(body["items"]) == 1

    async def test_create_phone_only(
        self, client: AsyncClient, cashier_token: str, menu_item: MenuItem
    ):
        """Call-center order with phone but no name is valid."""
        payload = _order_payload(menu_item.id, customer_name=None)
        resp = await client.post(
            "/api/v1/orders", json=payload, headers=_auth(cashier_token)
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["customer_phone"] == "03001234567"
        assert body["customer_name"] is None

    async def test_phone_normalized_to_digits(
        self, client: AsyncClient, cashier_token: str, menu_item: MenuItem
    ):
        """Phone with dashes/spaces is normalized to digits on the server."""
        payload = _order_payload(menu_item.id, customer_phone="0300-123-4567")
        resp = await client.post(
            "/api/v1/orders", json=payload, headers=_auth(cashier_token)
        )
        assert resp.status_code == 201
        assert resp.json()["customer_phone"] == "03001234567"


# =========================================================================
# 2. Missing Customer Info Rejection for call_center
# =========================================================================
class TestCallCenterValidation:

    async def test_missing_phone_422(
        self, client: AsyncClient, cashier_token: str, menu_item: MenuItem
    ):
        """call_center orders MUST have customer_phone."""
        payload = _order_payload(menu_item.id, customer_phone=None)
        resp = await client.post(
            "/api/v1/orders", json=payload, headers=_auth(cashier_token)
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        # Pydantic model_validator error should mention customer_phone
        errors_text = str(detail).lower()
        assert "customer_phone" in errors_text

    async def test_empty_phone_422(
        self, client: AsyncClient, cashier_token: str, menu_item: MenuItem
    ):
        """Empty string phone is treated as falsy → rejected."""
        payload = _order_payload(menu_item.id, customer_phone="")
        resp = await client.post(
            "/api/v1/orders", json=payload, headers=_auth(cashier_token)
        )
        assert resp.status_code == 422


# =========================================================================
# 3. Non-Call-Center Orders Unaffected
# =========================================================================
class TestNonCallCenterUnaffected:

    async def test_takeaway_no_phone_ok(
        self, client: AsyncClient, cashier_token: str, menu_item: MenuItem
    ):
        """Takeaway orders don't require customer_phone."""
        payload = _order_payload(
            menu_item.id,
            order_type="takeaway",
            customer_phone=None,
            customer_name=None,
        )
        resp = await client.post(
            "/api/v1/orders", json=payload, headers=_auth(cashier_token)
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["order_type"] == "takeaway"
        assert body["customer_phone"] is None

    async def test_dine_in_no_phone_ok(
        self, client: AsyncClient, cashier_token: str, menu_item: MenuItem
    ):
        """Dine-in orders don't require customer_phone."""
        payload = _order_payload(
            menu_item.id,
            order_type="dine_in",
            customer_phone=None,
            customer_name=None,
        )
        resp = await client.post(
            "/api/v1/orders", json=payload, headers=_auth(cashier_token)
        )
        assert resp.status_code == 201
        assert resp.json()["order_type"] == "dine_in"

    async def test_takeaway_with_phone_preserved(
        self, client: AsyncClient, cashier_token: str, menu_item: MenuItem
    ):
        """Takeaway orders CAN have customer_phone — it's just optional."""
        payload = _order_payload(
            menu_item.id,
            order_type="takeaway",
            customer_phone="03009876543",
            customer_name="Bilal",
        )
        resp = await client.post(
            "/api/v1/orders", json=payload, headers=_auth(cashier_token)
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["customer_phone"] == "03009876543"
        assert body["customer_name"] == "Bilal"


# =========================================================================
# 4. Customer Order-History Consistency
# =========================================================================
class TestOrderHistoryConsistency:
    """Verify that call-center orders appear in customer order history."""

    async def test_new_order_appears_in_history(
        self, client: AsyncClient, cashier_token: str, menu_item: MenuItem
    ):
        """Create customer, create call-center order with same phone,
        then verify order appears in customer's history endpoint."""
        # Create customer
        cust_resp = await client.post(
            "/api/v1/customers",
            json={"name": "History Check", "phone": "03005559999"},
            headers=_auth(cashier_token),
        )
        assert cust_resp.status_code == 201
        cid = cust_resp.json()["id"]

        # Create call-center order with same phone
        payload = _order_payload(
            menu_item.id,
            customer_phone="03005559999",
            customer_name="History Check",
        )
        order_resp = await client.post(
            "/api/v1/orders", json=payload, headers=_auth(cashier_token)
        )
        assert order_resp.status_code == 201
        order_id = order_resp.json()["id"]

        # Check history
        hist_resp = await client.get(
            f"/api/v1/customers/{cid}/orders",
            headers=_auth(cashier_token),
        )
        assert hist_resp.status_code == 200
        orders = hist_resp.json()
        assert len(orders) == 1
        assert orders[0]["id"] == order_id
        assert orders[0]["order_type"] == "call_center"

    async def test_multiple_orders_in_history(
        self, client: AsyncClient, cashier_token: str,
        db: AsyncSession, tenant, admin_user: User,
    ):
        """Multiple orders for same phone appear in history."""
        from app.models.order import Order

        cust_resp = await client.post(
            "/api/v1/customers",
            json={"name": "Multi Order", "phone": "03005558888"},
            headers=_auth(cashier_token),
        )
        cid = cust_resp.json()["id"]

        # Seed orders directly to avoid order-number collision in SQLite
        for i in range(3):
            o = Order(
                tenant_id=tenant.id,
                order_number=f"M250101-{i+1:03d}",
                order_type="call_center",
                status="completed",
                payment_status="paid",
                subtotal=5000,
                tax_amount=800,
                discount_amount=0,
                total=5800,
                created_by=admin_user.id,
                customer_phone="03005558888",
                customer_name="Multi Order",
            )
            db.add(o)
        await db.flush()
        await db.commit()

        hist_resp = await client.get(
            f"/api/v1/customers/{cid}/orders",
            headers=_auth(cashier_token),
        )
        assert hist_resp.status_code == 200
        assert len(hist_resp.json()) == 3

    async def test_different_phone_not_in_history(
        self, client: AsyncClient, cashier_token: str, menu_item: MenuItem
    ):
        """Orders with different phone don't show in customer history."""
        cust_resp = await client.post(
            "/api/v1/customers",
            json={"name": "Isolated", "phone": "03005557777"},
            headers=_auth(cashier_token),
        )
        cid = cust_resp.json()["id"]

        # Order with different phone
        payload = _order_payload(
            menu_item.id,
            customer_phone="03001110000",
            customer_name="Someone Else",
        )
        await client.post(
            "/api/v1/orders", json=payload, headers=_auth(cashier_token)
        )

        hist_resp = await client.get(
            f"/api/v1/customers/{cid}/orders",
            headers=_auth(cashier_token),
        )
        assert hist_resp.status_code == 200
        assert len(hist_resp.json()) == 0
