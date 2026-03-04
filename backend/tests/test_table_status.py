"""Tests for PATCH /api/v1/floors/tables/{table_id}/status.

Covers: auth, role access, valid/invalid status values, tenant isolation,
DB persistence, and edge cases.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floor import Table
from app.models.order import Order
from app.models.table_session import TableSession

URL = "/api/v1/floors/tables/{table_id}/status"


def _url(table_id: uuid.UUID) -> str:
    return URL.format(table_id=table_id)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Auth: no token → 401
# ---------------------------------------------------------------------------
class TestAuth:
    async def test_no_token_returns_401(self, client: AsyncClient, table: Table):
        resp = await client.patch(_url(table.id), json={"status": "reserved"})
        assert resp.status_code == 401

    async def test_invalid_token_returns_401(self, client: AsyncClient, table: Table):
        resp = await client.patch(
            _url(table.id),
            json={"status": "reserved"},
            headers={"Authorization": "Bearer garbage.token.here"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. Role access: admin, cashier, kitchen all allowed
# ---------------------------------------------------------------------------
class TestRoleAccess:
    async def test_admin_can_update_status(
        self, client: AsyncClient, table: Table, admin_token: str
    ):
        resp = await client.patch(
            _url(table.id), json={"status": "reserved"}, headers=_auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "reserved"

    async def test_cashier_can_update_status(
        self, client: AsyncClient, table: Table, cashier_token: str
    ):
        resp = await client.patch(
            _url(table.id), json={"status": "cleaning"}, headers=_auth(cashier_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cleaning"

    async def test_kitchen_can_update_status(
        self, client: AsyncClient, table: Table, kitchen_token: str
    ):
        resp = await client.patch(
            _url(table.id), json={"status": "occupied"}, headers=_auth(kitchen_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "occupied"


# ---------------------------------------------------------------------------
# 3. Valid status values
# ---------------------------------------------------------------------------
class TestValidStatus:
    @pytest.mark.parametrize("new_status", ["available", "occupied", "reserved", "cleaning"])
    async def test_all_valid_statuses_accepted(
        self, client: AsyncClient, table: Table, admin_token: str, new_status: str
    ):
        resp = await client.patch(
            _url(table.id), json={"status": new_status}, headers=_auth(admin_token)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == new_status
        assert body["id"] == str(table.id)


# ---------------------------------------------------------------------------
# 4. Invalid status values → 422
# ---------------------------------------------------------------------------
class TestInvalidStatus:
    @pytest.mark.parametrize(
        "bad_status",
        ["deleted", "AVAILABLE", "Reserved", "closed", "", "foo", "occupied "],
    )
    async def test_invalid_status_returns_422(
        self, client: AsyncClient, table: Table, admin_token: str, bad_status: str
    ):
        resp = await client.patch(
            _url(table.id), json={"status": bad_status}, headers=_auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_missing_status_field_returns_422(
        self, client: AsyncClient, table: Table, admin_token: str
    ):
        """TableStatusUpdate requires status — omitting it must fail."""
        resp = await client.patch(
            _url(table.id), json={}, headers=_auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_null_status_returns_422(
        self, client: AsyncClient, table: Table, admin_token: str
    ):
        resp = await client.patch(
            _url(table.id), json={"status": None}, headers=_auth(admin_token)
        )
        assert resp.status_code == 422

    async def test_extra_fields_ignored(
        self, client: AsyncClient, table: Table, admin_token: str
    ):
        """Extra fields in the body should not affect the table (only status applied)."""
        resp = await client.patch(
            _url(table.id),
            json={"status": "reserved", "capacity": 99, "number": 999},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "reserved"
        # capacity and number must NOT have changed
        assert body["capacity"] == 4
        assert body["number"] == 1


# ---------------------------------------------------------------------------
# 5. Tenant isolation
# ---------------------------------------------------------------------------
class TestTenantIsolation:
    async def test_cross_tenant_returns_404(
        self, client: AsyncClient, table: Table, other_tenant_token: str
    ):
        """User from tenant B must NOT see or update tenant A's table."""
        resp = await client.patch(
            _url(table.id),
            json={"status": "reserved"},
            headers=_auth(other_tenant_token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 6. DB persistence
# ---------------------------------------------------------------------------
class TestPersistence:
    async def test_status_persisted_across_requests(
        self, client: AsyncClient, table: Table, admin_token: str
    ):
        """Update status, then fetch via status-board to confirm persistence."""
        resp = await client.patch(
            _url(table.id), json={"status": "reserved"}, headers=_auth(admin_token)
        )
        assert resp.status_code == 200

        # Verify via independent GET (separate DB session)
        board = await client.get(
            "/api/v1/floors/status-board", headers=_auth(admin_token)
        )
        assert board.status_code == 200
        floors = board.json()["floors"]
        tables = [t for f in floors for t in f["tables"]]
        match = [t for t in tables if t["id"] == str(table.id)]
        assert len(match) == 1
        assert match[0]["status"] == "reserved"

    async def test_sequential_status_changes(
        self, client: AsyncClient, table: Table, admin_token: str
    ):
        """Status should update correctly through multiple transitions."""
        for new_status in ["reserved", "occupied", "cleaning", "available"]:
            resp = await client.patch(
                _url(table.id), json={"status": new_status}, headers=_auth(admin_token)
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == new_status

    async def test_status_board_releases_table_for_paid_completed_open_session(
        self,
        client: AsyncClient,
        db: AsyncSession,
        table: Table,
        admin_user,
        admin_token: str,
        tenant,
    ):
        """Paid+completed dine-in activity must not keep table occupied."""
        table.status = "occupied"
        session = TableSession(
            tenant_id=tenant.id,
            table_id=table.id,
            status="open",
            opened_by=admin_user.id,
        )
        db.add(session)
        await db.flush()

        db.add(Order(
            tenant_id=tenant.id,
            order_number="D260304-001",
            order_type="dine_in",
            status="completed",
            payment_status="paid",
            table_id=table.id,
            table_session_id=session.id,
            subtotal=1000,
            tax_amount=160,
            discount_amount=0,
            total=1160,
            created_by=admin_user.id,
        ))
        await db.flush()
        await db.commit()

        board = await client.get("/api/v1/floors/status-board", headers=_auth(admin_token))
        assert board.status_code == 200
        tables = [t for f in board.json()["floors"] for t in f["tables"]]
        current = next(t for t in tables if t["id"] == str(table.id))
        assert current["status"] == "available"

    async def test_status_board_releases_table_for_empty_open_session(
        self,
        client: AsyncClient,
        db: AsyncSession,
        table: Table,
        admin_user,
        admin_token: str,
        tenant,
    ):
        """Empty stale open sessions must not keep table occupied."""
        table.status = "occupied"
        db.add(TableSession(
            tenant_id=tenant.id,
            table_id=table.id,
            status="open",
            opened_by=admin_user.id,
        ))
        await db.flush()
        await db.commit()

        board = await client.get("/api/v1/floors/status-board", headers=_auth(admin_token))
        assert board.status_code == 200
        tables = [t for f in board.json()["floors"] for t in f["tables"]]
        current = next(t for t in tables if t["id"] == str(table.id))
        assert current["status"] == "available"


# ---------------------------------------------------------------------------
# 7. 404 for non-existent table
# ---------------------------------------------------------------------------
class TestNotFound:
    async def test_nonexistent_table_returns_404(
        self, client: AsyncClient, admin_token: str
    ):
        fake_id = uuid.uuid4()
        resp = await client.patch(
            _url(fake_id), json={"status": "reserved"}, headers=_auth(admin_token)
        )
        assert resp.status_code == 404
