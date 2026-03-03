"""Tests for P1-B Phase 1: Table session consolidation."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floor import Floor, Table
from app.models.order import Order
from app.models.table_session import TableSession
from app.models.user import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# 1. Open session
# =========================================================================

class TestOpenSession:
    """POST /api/v1/table-sessions/open"""

    async def test_open_session_creates_new(
        self, client: AsyncClient, admin_token: str, table: Table
    ):
        resp = await client.post(
            "/api/v1/table-sessions/open",
            json={"table_id": str(table.id)},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["table_id"] == str(table.id)
        assert body["status"] == "open"
        assert body["order_count"] == 0

    async def test_open_session_idempotent(
        self, client: AsyncClient, admin_token: str, table: Table
    ):
        """Opening twice for the same table returns the same session."""
        resp1 = await client.post(
            "/api/v1/table-sessions/open",
            json={"table_id": str(table.id)},
            headers=_auth(admin_token),
        )
        resp2 = await client.post(
            "/api/v1/table-sessions/open",
            json={"table_id": str(table.id)},
            headers=_auth(admin_token),
        )
        assert resp1.json()["id"] == resp2.json()["id"]

    async def test_open_session_requires_auth(
        self, client: AsyncClient, table: Table
    ):
        resp = await client.post(
            "/api/v1/table-sessions/open",
            json={"table_id": str(table.id)},
        )
        assert resp.status_code in (401, 403)


# =========================================================================
# 2. Get session
# =========================================================================

class TestGetSession:
    """GET /api/v1/table-sessions/{id}"""

    async def test_get_session(
        self, client: AsyncClient, admin_token: str, table: Table
    ):
        # Create session first
        open_resp = await client.post(
            "/api/v1/table-sessions/open",
            json={"table_id": str(table.id)},
            headers=_auth(admin_token),
        )
        session_id = open_resp.json()["id"]

        resp = await client.get(
            f"/api/v1/table-sessions/{session_id}",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == session_id
        assert resp.json()["status"] == "open"

    async def test_get_session_not_found(
        self, client: AsyncClient, admin_token: str
    ):
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/v1/table-sessions/{fake_id}",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 404


# =========================================================================
# 3. Active session by table
# =========================================================================

class TestActiveSessionByTable:
    """GET /api/v1/table-sessions/table/{table_id}/active"""

    async def test_active_session_returns_open(
        self, client: AsyncClient, admin_token: str, table: Table
    ):
        # Open session
        await client.post(
            "/api/v1/table-sessions/open",
            json={"table_id": str(table.id)},
            headers=_auth(admin_token),
        )
        resp = await client.get(
            f"/api/v1/table-sessions/table/{table.id}/active",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body is not None
        assert body["status"] == "open"

    async def test_no_active_session_returns_null(
        self, client: AsyncClient, admin_token: str, table: Table
    ):
        resp = await client.get(
            f"/api/v1/table-sessions/table/{table.id}/active",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json() is None


# =========================================================================
# 4. Close session
# =========================================================================

class TestCloseSession:
    """POST /api/v1/table-sessions/{id}/close"""

    async def test_close_session(
        self, client: AsyncClient, admin_token: str, table: Table
    ):
        open_resp = await client.post(
            "/api/v1/table-sessions/open",
            json={"table_id": str(table.id)},
            headers=_auth(admin_token),
        )
        session_id = open_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/table-sessions/{session_id}/close",
            json={},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"

    async def test_close_already_closed_fails(
        self, client: AsyncClient, admin_token: str, table: Table
    ):
        open_resp = await client.post(
            "/api/v1/table-sessions/open",
            json={"table_id": str(table.id)},
            headers=_auth(admin_token),
        )
        session_id = open_resp.json()["id"]

        # Close once
        await client.post(
            f"/api/v1/table-sessions/{session_id}/close",
            json={},
            headers=_auth(admin_token),
        )
        # Close again should fail
        resp = await client.post(
            f"/api/v1/table-sessions/{session_id}/close",
            json={},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 400


# =========================================================================
# 5. Bill summary
# =========================================================================

class TestBillSummary:
    """GET /api/v1/table-sessions/{id}/bill-summary"""

    async def test_bill_summary_empty_session(
        self, client: AsyncClient, admin_token: str, table: Table
    ):
        open_resp = await client.post(
            "/api/v1/table-sessions/open",
            json={"table_id": str(table.id)},
            headers=_auth(admin_token),
        )
        session_id = open_resp.json()["id"]

        resp = await client.get(
            f"/api/v1/table-sessions/{session_id}/bill-summary",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == session_id
        assert body["total"] == 0
        assert body["due_amount"] == 0
        assert body["order_count"] == 0

    async def test_bill_summary_with_orders(
        self, client: AsyncClient, admin_token: str, table: Table, db: AsyncSession, tenant
    ):
        """Add orders to session and verify consolidated total."""
        open_resp = await client.post(
            "/api/v1/table-sessions/open",
            json={"table_id": str(table.id)},
            headers=_auth(admin_token),
        )
        session_id = open_resp.json()["id"]

        # Create two orders attached to this session
        from tests.conftest import TENANT_ID
        from app.models.user import User
        from sqlalchemy import select

        result = await db.execute(select(User).where(User.email == "admin@test.com"))
        admin = result.scalar_one()

        order1 = Order(
            tenant_id=TENANT_ID,
            order_number="S250301-001",
            order_type="dine_in",
            status="confirmed",
            payment_status="unpaid",
            table_id=table.id,
            table_session_id=uuid.UUID(session_id),
            subtotal=5000,
            tax_amount=800,
            discount_amount=0,
            total=5800,
            created_by=admin.id,
        )
        order2 = Order(
            tenant_id=TENANT_ID,
            order_number="S250301-002",
            order_type="dine_in",
            status="confirmed",
            payment_status="unpaid",
            table_id=table.id,
            table_session_id=uuid.UUID(session_id),
            subtotal=3000,
            tax_amount=480,
            discount_amount=0,
            total=3480,
            created_by=admin.id,
        )
        db.add_all([order1, order2])
        await db.commit()

        resp = await client.get(
            f"/api/v1/table-sessions/{session_id}/bill-summary",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["order_count"] == 2
        assert body["subtotal"] == 8000
        assert body["tax_amount"] == 1280
        assert body["total"] == 9280
        assert body["due_amount"] == 9280


# =========================================================================
# 6. Tenant isolation
# =========================================================================

class TestSessionTenantIsolation:
    """Ensure sessions from one tenant are not visible to another."""

    async def test_cross_tenant_session_not_visible(
        self, client: AsyncClient, admin_token: str, other_tenant_token: str,
        table: Table, other_tenant
    ):
        # Tenant A opens a session
        open_resp = await client.post(
            "/api/v1/table-sessions/open",
            json={"table_id": str(table.id)},
            headers=_auth(admin_token),
        )
        session_id = open_resp.json()["id"]

        # Tenant B cannot see it
        resp = await client.get(
            f"/api/v1/table-sessions/{session_id}",
            headers=_auth(other_tenant_token),
        )
        assert resp.status_code == 404
