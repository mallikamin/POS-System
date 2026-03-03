"""Tests for Slice 3: pay-before-eat hard block.

Covers:
- pay_first config → order created as confirmed (not in_kitchen)
- Manual confirmed→in_kitchen blocked without payment
- After payment, order auto-transitions to in_kitchen
- order_first flow unchanged (existing behavior)
"""

import uuid

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu import Category, MenuItem
from app.models.restaurant_config import RestaurantConfig
from app.models.user import User
from tests.conftest import make_token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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
async def pay_first_config(db: AsyncSession, tenant) -> RestaurantConfig:
    """Set restaurant to pay_first mode."""
    config = RestaurantConfig(
        tenant_id=tenant.id, payment_flow="pay_first",
        default_tax_rate=1600, cash_tax_rate_bps=1600, card_tax_rate_bps=500,
    )
    db.add(config)
    await db.flush()
    await db.commit()
    return config


@pytest_asyncio.fixture
async def order_first_config(db: AsyncSession, tenant) -> RestaurantConfig:
    """Set restaurant to order_first mode (default)."""
    config = RestaurantConfig(
        tenant_id=tenant.id, payment_flow="order_first",
        default_tax_rate=1600, cash_tax_rate_bps=1600, card_tax_rate_bps=500,
    )
    db.add(config)
    await db.flush()
    await db.commit()
    return config


def _order_payload(menu_item_id: uuid.UUID) -> dict:
    return {
        "order_type": "takeaway",
        "items": [
            {
                "menu_item_id": str(menu_item_id),
                "name": "Chicken Tikka",
                "quantity": 2,
                "unit_price": 35000,
            }
        ],
    }


class TestPayFirstOrderCreation:
    """In pay_first mode, orders stay as confirmed (not in_kitchen)."""

    async def test_pay_first_order_stays_confirmed(
        self, client: AsyncClient, cashier_token: str,
        menu_item: MenuItem, pay_first_config: RestaurantConfig,
    ):
        resp = await client.post(
            "/api/v1/orders",
            json=_order_payload(menu_item.id),
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "confirmed"

    async def test_order_first_auto_sends_to_kitchen(
        self, client: AsyncClient, cashier_token: str,
        menu_item: MenuItem, order_first_config: RestaurantConfig,
    ):
        resp = await client.post(
            "/api/v1/orders",
            json=_order_payload(menu_item.id),
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "in_kitchen"


class TestPayFirstTransitionBlock:
    """confirmed→in_kitchen blocked without payment in pay_first mode."""

    async def test_transition_blocked_without_payment(
        self, client: AsyncClient, cashier_token: str,
        menu_item: MenuItem, pay_first_config: RestaurantConfig,
    ):
        # Create order (stays confirmed)
        resp = await client.post(
            "/api/v1/orders",
            json=_order_payload(menu_item.id),
            headers=_auth(cashier_token),
        )
        order_id = resp.json()["id"]

        # Try to transition to in_kitchen without payment
        resp = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "in_kitchen"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 400
        assert "Payment required" in resp.json()["detail"]


class TestPayFirstAutoSendAfterPayment:
    """After payment in pay_first mode, order auto-transitions to in_kitchen."""

    async def test_payment_triggers_kitchen_send(
        self, client: AsyncClient, cashier_token: str,
        menu_item: MenuItem, pay_first_config: RestaurantConfig,
    ):
        # Create order (stays confirmed)
        resp = await client.post(
            "/api/v1/orders",
            json=_order_payload(menu_item.id),
            headers=_auth(cashier_token),
        )
        order_id = resp.json()["id"]
        order_total = resp.json()["total"]
        assert resp.json()["status"] == "confirmed"

        # Pay for the order
        pay_resp = await client.post(
            "/api/v1/payments",
            json={
                "order_id": order_id,
                "method_code": "cash",
                "amount": order_total,
                "tendered_amount": order_total,
            },
            headers=_auth(cashier_token),
        )
        assert pay_resp.status_code in (200, 201)

        # Verify order is now in_kitchen
        order_resp = await client.get(
            f"/api/v1/orders/{order_id}",
            headers=_auth(cashier_token),
        )
        assert order_resp.status_code == 200
        assert order_resp.json()["status"] == "in_kitchen"
