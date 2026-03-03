"""Tests for P1-A features: payment preview, verify-password, void hardening."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.restaurant_config import RestaurantConfig


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# 1. Payment Preview
# =========================================================================
class TestPaymentPreview:
    """GET /api/v1/orders/{id}/payment-preview"""

    async def test_payment_preview_returns_dual_totals(
        self,
        client: AsyncClient,
        order: Order,
        tenant,
        db: AsyncSession,
        admin_token: str,
    ):
        # Set up config with cash 16% / card 5%
        config = RestaurantConfig(
            tenant_id=tenant.id,
            payment_flow="order_first",
            currency="PKR",
            timezone="Asia/Karachi",
            tax_inclusive=True,
            default_tax_rate=1600,
            cash_tax_rate_bps=1600,
            card_tax_rate_bps=500,
        )
        db.add(config)
        await db.commit()

        resp = await client.get(
            f"/api/v1/orders/{order.id}/payment-preview",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["order_id"] == str(order.id)
        assert body["subtotal"] == order.subtotal

        # Cash: subtotal * 16% = 8621 * 0.16 = 1379 (rounded)
        expected_cash_tax = round(order.subtotal * 1600 / 10_000)
        assert body["cash_tax_rate_bps"] == 1600
        assert body["cash_tax_amount"] == expected_cash_tax
        assert body["cash_total"] == order.subtotal + expected_cash_tax

        # Card: subtotal * 5% = 8621 * 0.05 = 431 (rounded)
        expected_card_tax = round(order.subtotal * 500 / 10_000)
        assert body["card_tax_rate_bps"] == 500
        assert body["card_tax_amount"] == expected_card_tax
        assert body["card_total"] == order.subtotal + expected_card_tax

    async def test_payment_preview_order_not_found(
        self, client: AsyncClient, admin_token: str
    ):
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/v1/orders/{fake_id}/payment-preview",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 404

    async def test_payment_preview_requires_auth(
        self, client: AsyncClient, order: Order
    ):
        resp = await client.get(
            f"/api/v1/orders/{order.id}/payment-preview",
        )
        assert resp.status_code in (401, 403)


# =========================================================================
# 2. Verify Password
# =========================================================================
class TestVerifyPassword:
    """POST /api/v1/auth/verify-password"""

    async def test_verify_password_success(
        self, client: AsyncClient, admin_token: str
    ):
        resp = await client.post(
            "/api/v1/auth/verify-password",
            json={"password": "admin123"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "auth_token" in body
        assert body["expires_in"] == 300

    async def test_verify_password_wrong_password(
        self, client: AsyncClient, admin_token: str
    ):
        resp = await client.post(
            "/api/v1/auth/verify-password",
            json={"password": "wrongpassword"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 401
        assert "Invalid password" in resp.json()["detail"]

    async def test_verify_password_requires_auth(
        self, client: AsyncClient
    ):
        resp = await client.post(
            "/api/v1/auth/verify-password",
            json={"password": "admin123"},
        )
        assert resp.status_code in (401, 403)


# =========================================================================
# 3. Void Hardening
# =========================================================================
class TestVoidHardening:
    """POST /api/v1/orders/{id}/void - mandatory reason + optional auth token"""

    async def test_void_requires_reason(
        self, client: AsyncClient, order: Order, admin_token: str
    ):
        """Void without reason should fail validation."""
        resp = await client.post(
            f"/api/v1/orders/{order.id}/void",
            json={},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 422  # Pydantic validation error

    async def test_void_with_reason_succeeds(
        self, client: AsyncClient, order: Order, admin_token: str
    ):
        resp = await client.post(
            f"/api/v1/orders/{order.id}/void",
            json={"reason": "Customer changed mind"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "voided"

    async def test_void_with_valid_auth_token(
        self, client: AsyncClient, order: Order, admin_token: str
    ):
        # First get auth token
        verify_resp = await client.post(
            "/api/v1/auth/verify-password",
            json={"password": "admin123"},
            headers=_auth(admin_token),
        )
        auth_token = verify_resp.json()["auth_token"]

        # Void with auth token
        resp = await client.post(
            f"/api/v1/orders/{order.id}/void",
            json={"reason": "Test void", "auth_token": auth_token},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "voided"

    async def test_void_with_invalid_auth_token(
        self, client: AsyncClient, order: Order, admin_token: str
    ):
        resp = await client.post(
            f"/api/v1/orders/{order.id}/void",
            json={"reason": "Test void", "auth_token": "invalid-token"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 401

    async def test_void_still_requires_admin_role(
        self, client: AsyncClient, order: Order, cashier_token: str
    ):
        resp = await client.post(
            f"/api/v1/orders/{order.id}/void",
            json={"reason": "Cashier trying to void"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 403

    async def test_void_empty_reason_fails(
        self, client: AsyncClient, order: Order, admin_token: str
    ):
        """Empty string reason should fail min_length=1 validation."""
        resp = await client.post(
            f"/api/v1/orders/{order.id}/void",
            json={"reason": ""},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 422
