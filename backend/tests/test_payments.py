"""Tests for payment endpoints (POST /payments, /payments/split, /payments/refund)
and cash drawer session endpoints (/drawer/open, /drawer/close, /drawer/session).

Covers: create payment, split payment, refund, drawer open/close/status,
tenant isolation, and validation errors.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.payment import Payment
from app.models.tenant import Tenant
from app.models.user import Permission, Role, RolePermission


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(autouse=True)
async def grant_admin_refund_permission(
    db: AsyncSession,
    tenant: Tenant,
    admin_role: Role,
) -> None:
    """Grant admin role payment.refund permission for refund tests."""
    perm = Permission(
        tenant_id=tenant.id,
        code="payment.refund",
        description="Issue refunds",
    )
    db.add(perm)
    await db.flush()
    db.add(RolePermission(
        tenant_id=tenant.id,
        role_id=admin_role.id,
        permission_id=perm.id,
    ))
    await db.flush()
    await db.commit()


# =========================================================================
# 1. Create Payment
# =========================================================================
class TestCreatePayment:
    """POST /api/v1/payments"""

    async def test_create_cash_payment_success(
        self, client: AsyncClient, order: Order, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/payments",
            json={
                "order_id": str(order.id),
                "method_code": "cash",
                "amount": 10000,
                "tendered_amount": 10000,
            },
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["order_id"] == str(order.id)
        assert body["paid_amount"] == 10000
        assert body["due_amount"] == 0
        assert body["payment_status"] == "paid"
        assert len(body["payments"]) == 1

    async def test_create_card_payment_success(
        self, client: AsyncClient, order: Order, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/payments",
            json={
                "order_id": str(order.id),
                "method_code": "card",
                "amount": 10000,
                "reference": "TXN-12345",
            },
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 201
        assert resp.json()["payment_status"] == "paid"

    async def test_partial_payment(
        self, client: AsyncClient, order: Order, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/payments",
            json={
                "order_id": str(order.id),
                "method_code": "cash",
                "amount": 5000,
                "tendered_amount": 5000,
            },
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["paid_amount"] == 5000
        assert body["due_amount"] == 5000
        assert body["payment_status"] == "partial"

    async def test_cash_change_calculated(
        self, client: AsyncClient, order: Order, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/payments",
            json={
                "order_id": str(order.id),
                "method_code": "cash",
                "amount": 10000,
                "tendered_amount": 15000,
            },
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 201
        payment = resp.json()["payments"][0]
        assert payment["change_amount"] == 5000

    async def test_exceeds_due_amount_rejected(
        self, client: AsyncClient, order: Order, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/payments",
            json={
                "order_id": str(order.id),
                "method_code": "cash",
                "amount": 20000,
                "tendered_amount": 20000,
            },
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 400
        assert "exceeds" in resp.json()["detail"].lower()

    async def test_already_paid_rejected(
        self, client: AsyncClient, order: Order, cashier_token: str
    ):
        # Pay in full
        await client.post(
            "/api/v1/payments",
            json={"order_id": str(order.id), "method_code": "cash", "amount": 10000, "tendered_amount": 10000},
            headers=_auth(cashier_token),
        )
        # Try again
        resp = await client.post(
            "/api/v1/payments",
            json={"order_id": str(order.id), "method_code": "cash", "amount": 1000, "tendered_amount": 1000},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 400
        assert "already fully paid" in resp.json()["detail"].lower()

    async def test_cash_tendered_less_than_amount_rejected(
        self, client: AsyncClient, order: Order, cashier_token: str
    ):
        """Pydantic validator: tendered_amount < amount for cash → 422."""
        resp = await client.post(
            "/api/v1/payments",
            json={
                "order_id": str(order.id),
                "method_code": "cash",
                "amount": 10000,
                "tendered_amount": 5000,
            },
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 422

    async def test_invalid_method_code_422(
        self, client: AsyncClient, order: Order, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/payments",
            json={"order_id": str(order.id), "method_code": "bitcoin", "amount": 10000},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 422

    async def test_zero_amount_422(
        self, client: AsyncClient, order: Order, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/payments",
            json={"order_id": str(order.id), "method_code": "cash", "amount": 0},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 422

    async def test_negative_amount_422(
        self, client: AsyncClient, order: Order, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/payments",
            json={"order_id": str(order.id), "method_code": "cash", "amount": -100},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 422

    async def test_no_auth_401(self, client: AsyncClient, order: Order):
        resp = await client.post(
            "/api/v1/payments",
            json={"order_id": str(order.id), "method_code": "cash", "amount": 10000},
        )
        assert resp.status_code == 401

    async def test_nonexistent_order_400(
        self, client: AsyncClient, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/payments",
            json={"order_id": str(uuid.uuid4()), "method_code": "cash", "amount": 5000, "tendered_amount": 5000},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"].lower()


# =========================================================================
# 2. Split Payment
# =========================================================================
class TestSplitPayment:
    """POST /api/v1/payments/split"""

    async def test_split_payment_success(
        self, client: AsyncClient, order: Order, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/payments/split",
            json={
                "order_id": str(order.id),
                "allocations": [
                    {"method_code": "cash", "amount": 6000, "tendered_amount": 6000},
                    {"method_code": "card", "amount": 4000, "reference": "CARD-001"},
                ],
            },
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["paid_amount"] == 10000
        assert body["due_amount"] == 0
        assert body["payment_status"] == "paid"
        assert len(body["payments"]) == 2

    async def test_split_mixed_tax_base_settles_to_zero_due(
        self, client: AsyncClient, order: Order, cashier_token: str
    ):
        """Split computed from pre-tax base (cash+card) should fully settle order."""
        preview = await client.get(
            f"/api/v1/orders/{order.id}/payment-preview",
            headers=_auth(cashier_token),
        )
        assert preview.status_code == 200
        p = preview.json()
        subtotal = p["subtotal"]
        cash_rate = p["cash_tax_rate_bps"]
        card_rate = p["card_tax_rate_bps"]

        cash_base = subtotal // 2
        card_base = subtotal - cash_base
        cash_payable = cash_base + round(cash_base * cash_rate / 10_000)
        card_payable = card_base + round(card_base * card_rate / 10_000)

        resp = await client.post(
            "/api/v1/payments/split",
            json={
                "order_id": str(order.id),
                "allocations": [
                    {"method_code": "cash", "amount": cash_payable, "tendered_amount": cash_payable},
                    {"method_code": "card", "amount": card_payable, "reference": "SPLIT-MIX"},
                ],
            },
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["due_amount"] == 0
        assert body["payment_status"] == "paid"
        assert body["paid_amount"] == cash_payable + card_payable

    async def test_split_exceeds_due_rejected(
        self, client: AsyncClient, order: Order, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/payments/split",
            json={
                "order_id": str(order.id),
                "allocations": [
                    {"method_code": "cash", "amount": 8000, "tendered_amount": 8000},
                    {"method_code": "card", "amount": 8000},
                ],
            },
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 400
        assert "exceeds" in resp.json()["detail"].lower()

    async def test_split_needs_at_least_two_allocations(
        self, client: AsyncClient, order: Order, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/payments/split",
            json={
                "order_id": str(order.id),
                "allocations": [
                    {"method_code": "cash", "amount": 10000, "tendered_amount": 10000},
                ],
            },
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 422

    async def test_split_partial(
        self, client: AsyncClient, order: Order, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/payments/split",
            json={
                "order_id": str(order.id),
                "allocations": [
                    {"method_code": "cash", "amount": 3000, "tendered_amount": 3000},
                    {"method_code": "card", "amount": 2000},
                ],
            },
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["paid_amount"] == 5000
        assert body["due_amount"] == 5000
        assert body["payment_status"] == "partial"

    async def test_split_no_auth_401(self, client: AsyncClient, order: Order):
        resp = await client.post(
            "/api/v1/payments/split",
            json={
                "order_id": str(order.id),
                "allocations": [
                    {"method_code": "cash", "amount": 5000, "tendered_amount": 5000},
                    {"method_code": "card", "amount": 5000},
                ],
            },
        )
        assert resp.status_code == 401


# =========================================================================
# 3. Refund
# =========================================================================
class TestRefund:
    """POST /api/v1/payments/refund"""

    async def _pay_order(self, client: AsyncClient, order: Order, token: str) -> str:
        """Helper: pay an order in full, return the payment ID."""
        resp = await client.post(
            "/api/v1/payments",
            json={"order_id": str(order.id), "method_code": "cash", "amount": order.total, "tendered_amount": order.total},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        return resp.json()["payments"][0]["id"]

    async def test_full_refund(
        self, client: AsyncClient, order: Order, admin_token: str, cashier_token: str
    ):
        payment_id = await self._pay_order(client, order, cashier_token)
        resp = await client.post(
            "/api/v1/payments/refund",
            json={"payment_id": payment_id, "amount": 10000, "note": "Customer complaint"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["refunded_amount"] == 10000
        assert body["payment_status"] == "refunded"

    async def test_partial_refund(
        self, client: AsyncClient, order: Order, admin_token: str, cashier_token: str
    ):
        payment_id = await self._pay_order(client, order, cashier_token)
        resp = await client.post(
            "/api/v1/payments/refund",
            json={"payment_id": payment_id, "amount": 3000},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["refunded_amount"] == 3000
        assert body["due_amount"] == 3000
        assert body["payment_status"] == "partial"

    async def test_refund_exceeds_refundable_rejected(
        self, client: AsyncClient, order: Order, admin_token: str, cashier_token: str
    ):
        payment_id = await self._pay_order(client, order, cashier_token)
        resp = await client.post(
            "/api/v1/payments/refund",
            json={"payment_id": payment_id, "amount": 20000},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 400
        assert "exceeds" in resp.json()["detail"].lower()

    async def test_double_full_refund_rejected(
        self, client: AsyncClient, order: Order, admin_token: str, cashier_token: str
    ):
        payment_id = await self._pay_order(client, order, cashier_token)
        # First refund: full
        await client.post(
            "/api/v1/payments/refund",
            json={"payment_id": payment_id, "amount": 10000},
            headers=_auth(admin_token),
        )
        # Second refund: rejected
        resp = await client.post(
            "/api/v1/payments/refund",
            json={"payment_id": payment_id, "amount": 1},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 400
        assert "exceeds" in resp.json()["detail"].lower()

    async def test_refund_nonexistent_payment_400(
        self, client: AsyncClient, admin_token: str
    ):
        resp = await client.post(
            "/api/v1/payments/refund",
            json={"payment_id": str(uuid.uuid4()), "amount": 1000},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"].lower()

    async def test_refund_zero_amount_422(
        self, client: AsyncClient, admin_token: str
    ):
        resp = await client.post(
            "/api/v1/payments/refund",
            json={"payment_id": str(uuid.uuid4()), "amount": 0},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 422

    async def test_refund_no_auth_401(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/payments/refund",
            json={"payment_id": str(uuid.uuid4()), "amount": 1000},
        )
        assert resp.status_code == 401


# =========================================================================
# 4. Payment Summary
# =========================================================================
class TestPaymentSummary:
    """GET /api/v1/payments/orders/{order_id}/summary"""

    async def test_get_summary_unpaid(
        self, client: AsyncClient, order: Order, cashier_token: str
    ):
        resp = await client.get(
            f"/api/v1/payments/orders/{order.id}/summary",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["order_total"] == 10000
        assert body["paid_amount"] == 0
        assert body["due_amount"] == 10000
        assert body["payments"] == []

    async def test_get_summary_nonexistent_order_404(
        self, client: AsyncClient, cashier_token: str
    ):
        resp = await client.get(
            f"/api/v1/payments/orders/{uuid.uuid4()}/summary",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 404


# =========================================================================
# 5. Cash Drawer: Open / Close / Status
# =========================================================================
class TestCashDrawer:
    """POST /drawer/open, /drawer/close, GET /drawer/session"""

    async def test_open_drawer_success(
        self, client: AsyncClient, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/payments/drawer/open",
            json={"opening_float": 500000, "note": "Morning shift"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "open"
        assert body["opening_float"] == 500000
        assert body["note"] == "Morning shift"

    async def test_get_active_drawer_session(
        self, client: AsyncClient, cashier_token: str
    ):
        # Open a drawer first
        await client.post(
            "/api/v1/payments/drawer/open",
            json={"opening_float": 500000},
            headers=_auth(cashier_token),
        )
        resp = await client.get(
            "/api/v1/payments/drawer/session",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "open"
        assert body["opening_float"] == 500000

    async def test_get_no_active_drawer_returns_null(
        self, client: AsyncClient, cashier_token: str
    ):
        resp = await client.get(
            "/api/v1/payments/drawer/session",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        assert resp.json() is None

    async def test_close_drawer_success(
        self, client: AsyncClient, cashier_token: str
    ):
        # Open
        await client.post(
            "/api/v1/payments/drawer/open",
            json={"opening_float": 500000},
            headers=_auth(cashier_token),
        )
        # Close
        resp = await client.post(
            "/api/v1/payments/drawer/close",
            json={"closing_balance_counted": 480000, "note": "Evening count"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "closed"
        assert body["closing_balance_counted"] == 480000
        assert body["closing_balance_expected"] is not None

    async def test_double_open_rejected(
        self, client: AsyncClient, cashier_token: str
    ):
        await client.post(
            "/api/v1/payments/drawer/open",
            json={"opening_float": 500000},
            headers=_auth(cashier_token),
        )
        resp = await client.post(
            "/api/v1/payments/drawer/open",
            json={"opening_float": 300000},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"].lower()

    async def test_close_when_none_open_rejected(
        self, client: AsyncClient, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/payments/drawer/close",
            json={"closing_balance_counted": 500000},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 400
        assert "no active" in resp.json()["detail"].lower()

    async def test_reopen_after_close(
        self, client: AsyncClient, cashier_token: str
    ):
        # Open → Close → Reopen
        await client.post(
            "/api/v1/payments/drawer/open", json={"opening_float": 500000},
            headers=_auth(cashier_token),
        )
        await client.post(
            "/api/v1/payments/drawer/close", json={"closing_balance_counted": 480000},
            headers=_auth(cashier_token),
        )
        resp = await client.post(
            "/api/v1/payments/drawer/open", json={"opening_float": 480000},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 201
        assert resp.json()["opening_float"] == 480000

    async def test_drawer_no_auth_401(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/payments/drawer/open", json={"opening_float": 0},
        )
        assert resp.status_code == 401

    async def test_negative_float_422(
        self, client: AsyncClient, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/payments/drawer/open",
            json={"opening_float": -100},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 422


# =========================================================================
# 6. Payment Methods
# =========================================================================
class TestPaymentMethods:
    """GET /api/v1/payments/methods"""

    async def test_list_payment_methods(
        self, client: AsyncClient, cashier_token: str
    ):
        resp = await client.get(
            "/api/v1/payments/methods",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        methods = resp.json()
        codes = {m["code"] for m in methods}
        assert codes == {"cash", "card", "mobile_wallet", "bank_transfer"}

    async def test_methods_no_auth_401(self, client: AsyncClient):
        resp = await client.get("/api/v1/payments/methods")
        assert resp.status_code == 401


# =========================================================================
# 7. Tenant Isolation
# =========================================================================
class TestTenantIsolation:
    """Cross-tenant access must be blocked."""

    async def test_pay_other_tenants_order_rejected(
        self, client: AsyncClient, other_tenant_order: Order, cashier_token: str
    ):
        """Tenant A's cashier must NOT pay tenant B's order."""
        resp = await client.post(
            "/api/v1/payments",
            json={
                "order_id": str(other_tenant_order.id),
                "method_code": "cash",
                "amount": 5000,
                "tendered_amount": 5000,
            },
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"].lower()

    async def test_view_other_tenants_summary_rejected(
        self, client: AsyncClient, other_tenant_order: Order, cashier_token: str
    ):
        resp = await client.get(
            f"/api/v1/payments/orders/{other_tenant_order.id}/summary",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 404

    async def test_other_tenant_drawer_isolated(
        self, client: AsyncClient, cashier_token: str, other_tenant_token: str
    ):
        """Drawer opened by tenant A is not visible to tenant B."""
        await client.post(
            "/api/v1/payments/drawer/open",
            json={"opening_float": 500000},
            headers=_auth(cashier_token),
        )
        resp = await client.get(
            "/api/v1/payments/drawer/session",
            headers=_auth(other_tenant_token),
        )
        assert resp.status_code == 200
        assert resp.json() is None  # Tenant B sees no active drawer
