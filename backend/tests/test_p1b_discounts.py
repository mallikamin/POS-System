"""Tests for P1-B Phase 2: Discount engine."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# 1. Discount Type CRUD
# =========================================================================

class TestDiscountTypeCRUD:
    """CRUD for /api/v1/discounts/types"""

    async def test_create_discount_type(
        self, client: AsyncClient, admin_token: str
    ):
        resp = await client.post(
            "/api/v1/discounts/types",
            json={
                "code": "bank_promo",
                "name": "Bank Promotion",
                "kind": "percent",
                "value": 1000,
            },
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["code"] == "bank_promo"
        assert body["kind"] == "percent"
        assert body["value"] == 1000
        assert body["is_active"] is True

    async def test_list_discount_types(
        self, client: AsyncClient, admin_token: str
    ):
        # Create two
        await client.post(
            "/api/v1/discounts/types",
            json={"code": "esr", "name": "ESR Discount", "kind": "percent", "value": 500},
            headers=_auth(admin_token),
        )
        await client.post(
            "/api/v1/discounts/types",
            json={"code": "manual", "name": "Manual Discount", "kind": "fixed", "value": 10000},
            headers=_auth(admin_token),
        )
        resp = await client.get(
            "/api/v1/discounts/types",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    async def test_update_discount_type(
        self, client: AsyncClient, admin_token: str
    ):
        create_resp = await client.post(
            "/api/v1/discounts/types",
            json={"code": "test_update", "name": "Test", "kind": "fixed", "value": 500},
            headers=_auth(admin_token),
        )
        type_id = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/v1/discounts/types/{type_id}",
            json={"name": "Updated Name", "is_active": False},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"
        assert resp.json()["is_active"] is False

    async def test_delete_discount_type(
        self, client: AsyncClient, admin_token: str
    ):
        create_resp = await client.post(
            "/api/v1/discounts/types",
            json={"code": "to_delete", "name": "Delete Me", "kind": "fixed", "value": 100},
            headers=_auth(admin_token),
        )
        type_id = create_resp.json()["id"]
        resp = await client.delete(
            f"/api/v1/discounts/types/{type_id}",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 204

    async def test_create_requires_admin(
        self, client: AsyncClient, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/discounts/types",
            json={"code": "noauth", "name": "No Auth", "kind": "fixed", "value": 100},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 403


# =========================================================================
# 2. Apply Discount
# =========================================================================

class TestApplyDiscount:
    """POST /api/v1/discounts/apply"""

    async def test_apply_manual_discount(
        self, client: AsyncClient, admin_token: str, order: Order
    ):
        resp = await client.post(
            "/api/v1/discounts/apply",
            json={
                "order_id": str(order.id),
                "label": "Special Discount",
                "source_type": "manual",
                "amount": 1000,  # Rs 10
            },
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["amount"] == 1000
        assert body["label"] == "Special Discount"

    async def test_apply_typed_percent_discount(
        self, client: AsyncClient, admin_token: str, order: Order
    ):
        # Create a 10% discount type
        type_resp = await client.post(
            "/api/v1/discounts/types",
            json={"code": "bank_10", "name": "Bank 10%", "kind": "percent", "value": 1000},
            headers=_auth(admin_token),
        )
        type_id = type_resp.json()["id"]

        resp = await client.post(
            "/api/v1/discounts/apply",
            json={
                "order_id": str(order.id),
                "discount_type_id": type_id,
            },
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        # 10% of subtotal 8621 = 862 (rounded)
        expected = round(order.subtotal * 1000 / 10_000)
        assert body["amount"] == expected
        assert body["percent_bps"] == 1000

    async def test_discount_cannot_exceed_subtotal(
        self, client: AsyncClient, admin_token: str, order: Order
    ):
        resp = await client.post(
            "/api/v1/discounts/apply",
            json={
                "order_id": str(order.id),
                "label": "Excessive",
                "source_type": "manual",
                "amount": 999999,
            },
            headers=_auth(admin_token),
        )
        assert resp.status_code == 400
        assert "exceeds" in resp.json()["detail"].lower()

    async def test_apply_updates_order_discount_amount(
        self, client: AsyncClient, admin_token: str, order: Order
    ):
        """Applying discount should update order.discount_amount and total."""
        await client.post(
            "/api/v1/discounts/apply",
            json={
                "order_id": str(order.id),
                "label": "Test",
                "source_type": "manual",
                "amount": 500,
            },
            headers=_auth(admin_token),
        )
        # Check order detail
        order_resp = await client.get(
            f"/api/v1/orders/{order.id}",
            headers=_auth(admin_token),
        )
        assert order_resp.status_code == 200
        body = order_resp.json()
        assert body["discount_amount"] == 500
        # total = subtotal + tax - discount
        assert body["total"] == order.subtotal + order.tax_amount - 500


# =========================================================================
# 3. Remove Discount
# =========================================================================

class TestRemoveDiscount:
    """DELETE /api/v1/discounts/{id}"""

    async def test_remove_discount(
        self, client: AsyncClient, admin_token: str, order: Order
    ):
        apply_resp = await client.post(
            "/api/v1/discounts/apply",
            json={
                "order_id": str(order.id),
                "label": "To Remove",
                "source_type": "manual",
                "amount": 200,
            },
            headers=_auth(admin_token),
        )
        discount_id = apply_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/discounts/{discount_id}",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 204

    async def test_remove_restores_order_total(
        self, client: AsyncClient, admin_token: str, order: Order
    ):
        apply_resp = await client.post(
            "/api/v1/discounts/apply",
            json={
                "order_id": str(order.id),
                "label": "Temp",
                "source_type": "manual",
                "amount": 300,
            },
            headers=_auth(admin_token),
        )
        discount_id = apply_resp.json()["id"]

        await client.delete(
            f"/api/v1/discounts/{discount_id}",
            headers=_auth(admin_token),
        )

        order_resp = await client.get(
            f"/api/v1/orders/{order.id}",
            headers=_auth(admin_token),
        )
        body = order_resp.json()
        assert body["discount_amount"] == 0
        assert body["total"] == order.subtotal + order.tax_amount


# =========================================================================
# 4. List Order Discounts
# =========================================================================

class TestListDiscounts:
    """GET /api/v1/discounts/orders/{order_id}"""

    async def test_list_order_discounts(
        self, client: AsyncClient, admin_token: str, order: Order
    ):
        # Apply two discounts
        await client.post(
            "/api/v1/discounts/apply",
            json={"order_id": str(order.id), "label": "D1", "source_type": "manual", "amount": 100},
            headers=_auth(admin_token),
        )
        await client.post(
            "/api/v1/discounts/apply",
            json={"order_id": str(order.id), "label": "D2", "source_type": "manual", "amount": 200},
            headers=_auth(admin_token),
        )
        resp = await client.get(
            f"/api/v1/discounts/orders/{order.id}",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["order_id"] == str(order.id)
        assert len(body["discounts"]) == 2
        assert body["total_discount"] == 300


# =========================================================================
# 5. Multiple discounts stack correctly
# =========================================================================

class TestMultipleDiscounts:

    async def test_multiple_discounts_stack(
        self, client: AsyncClient, admin_token: str, order: Order
    ):
        """Multiple discounts should stack and not exceed subtotal."""
        await client.post(
            "/api/v1/discounts/apply",
            json={"order_id": str(order.id), "label": "D1", "source_type": "manual", "amount": 2000},
            headers=_auth(admin_token),
        )
        await client.post(
            "/api/v1/discounts/apply",
            json={"order_id": str(order.id), "label": "D2", "source_type": "manual", "amount": 3000},
            headers=_auth(admin_token),
        )
        # Third discount should fail if it would exceed subtotal
        resp = await client.post(
            "/api/v1/discounts/apply",
            json={"order_id": str(order.id), "label": "D3", "source_type": "manual", "amount": 999999},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 400

        # Order should have 5000 discount
        order_resp = await client.get(
            f"/api/v1/orders/{order.id}",
            headers=_auth(admin_token),
        )
        assert order_resp.json()["discount_amount"] == 5000
