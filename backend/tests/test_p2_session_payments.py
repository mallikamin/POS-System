"""P2-Slice 1: Consolidated session payment tests."""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floor import Floor, Table
from app.models.order import Order
from app.models.table_session import TableSession
from app.models.payment import PaymentMethod
from tests.conftest import TENANT_ID, make_token


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def session_floor(db: AsyncSession, tenant) -> Floor:
    f = Floor(tenant_id=tenant.id, name="Session Floor", display_order=1, is_active=True)
    db.add(f)
    await db.flush()
    return f


@pytest_asyncio.fixture
async def session_table(db: AsyncSession, tenant, session_floor) -> Table:
    t = Table(
        tenant_id=tenant.id, floor_id=session_floor.id, number=99,
        capacity=4, shape="square", status="available",
    )
    db.add(t)
    await db.flush()
    return t


@pytest_asyncio.fixture
async def table_session(db: AsyncSession, tenant, admin_user, session_table) -> TableSession:
    ts = TableSession(
        tenant_id=tenant.id,
        table_id=session_table.id,
        status="open",
        opened_by=admin_user.id,
    )
    db.add(ts)
    await db.flush()
    return ts


@pytest_asyncio.fixture
async def session_order_a(db: AsyncSession, tenant, admin_user, table_session) -> Order:
    """First order in session, total=5000 paisa (Rs 50)."""
    o = Order(
        tenant_id=tenant.id,
        order_number="D260301-001",
        order_type="dine_in",
        status="confirmed",
        payment_status="unpaid",
        subtotal=4310,
        tax_amount=690,
        discount_amount=0,
        total=5000,
        table_id=table_session.table_id,
        table_session_id=table_session.id,
        created_by=admin_user.id,
    )
    db.add(o)
    await db.flush()
    await db.commit()
    return o


@pytest_asyncio.fixture
async def session_order_b(db: AsyncSession, tenant, admin_user, table_session) -> Order:
    """Second order in session, total=3000 paisa (Rs 30)."""
    o = Order(
        tenant_id=tenant.id,
        order_number="D260301-002",
        order_type="dine_in",
        status="confirmed",
        payment_status="unpaid",
        subtotal=2586,
        tax_amount=414,
        discount_amount=0,
        total=3000,
        table_id=table_session.table_id,
        table_session_id=table_session.id,
        created_by=admin_user.id,
    )
    db.add(o)
    await db.flush()
    await db.commit()
    return o


@pytest_asyncio.fixture
async def cash_method(db: AsyncSession, tenant) -> PaymentMethod:
    pm = PaymentMethod(
        tenant_id=tenant.id, code="cash", display_name="Cash",
        is_active=True, sort_order=1, requires_reference=False,
    )
    db.add(pm)
    await db.flush()
    await db.commit()
    return pm


@pytest_asyncio.fixture
async def card_method(db: AsyncSession, tenant) -> PaymentMethod:
    pm = PaymentMethod(
        tenant_id=tenant.id, code="card", display_name="Card",
        is_active=True, sort_order=2, requires_reference=True,
    )
    db.add(pm)
    await db.flush()
    await db.commit()
    return pm


# ---------------------------------------------------------------------------
# Tests: Session Payment Summary
# ---------------------------------------------------------------------------

class TestSessionPaymentSummary:
    @pytest.mark.asyncio
    async def test_summary_with_orders(
        self, client: AsyncClient, admin_token: str,
        table_session, session_order_a, session_order_b,
    ):
        resp = await client.get(
            f"/api/v1/payments/table-sessions/{table_session.id}/summary",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == str(table_session.id)
        assert data["order_count"] == 2
        assert data["total"] == 8000
        assert data["due_amount"] == 8000
        assert data["payment_status"] == "unpaid"
        assert len(data["orders"]) == 2

    @pytest.mark.asyncio
    async def test_summary_not_found(
        self, client: AsyncClient, admin_token: str,
    ):
        resp = await client.get(
            f"/api/v1/payments/table-sessions/{uuid.uuid4()}/summary",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Session Full Pay
# ---------------------------------------------------------------------------

class TestSessionFullPay:
    @pytest.mark.asyncio
    async def test_full_pay_cash(
        self, client: AsyncClient, admin_token: str,
        table_session, session_order_a, session_order_b,
        cash_method,
    ):
        preview = await client.get(
            f"/api/v1/payments/table-sessions/{table_session.id}/payment-preview",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert preview.status_code == 200
        cash_total = preview.json()["cash_total"]

        resp = await client.post(
            f"/api/v1/payments/table-sessions/{table_session.id}/pay",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"method_code": "cash", "amount": cash_total, "tendered_amount": 10000},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["due_amount"] == 0
        assert data["payment_status"] == "paid"
        assert data["paid_amount"] == cash_total
        # Both orders should be paid
        for order in data["orders"]:
            assert order["due_amount"] == 0
            assert order["payment_status"] == "paid"

    @pytest.mark.asyncio
    async def test_full_pay_card_uses_card_tax_total(
        self, client: AsyncClient, admin_token: str,
        table_session, session_order_a, session_order_b,
        card_method,
    ):
        """Card settlement should close session at card-tax total, not cash/default total."""
        preview = await client.get(
            f"/api/v1/payments/table-sessions/{table_session.id}/payment-preview",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert preview.status_code == 200
        card_total = preview.json()["card_total"]

        resp = await client.post(
            f"/api/v1/payments/table-sessions/{table_session.id}/pay",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"method_code": "card", "amount": card_total, "reference": "UAT-CARD"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["due_amount"] == 0
        assert data["payment_status"] == "paid"
        assert data["paid_amount"] == card_total

    @pytest.mark.asyncio
    async def test_partial_pay(
        self, client: AsyncClient, admin_token: str,
        table_session, session_order_a, session_order_b,
        cash_method,
    ):
        """Pay Rs 50 (5000 paisa) of Rs 80 session."""
        preview = await client.get(
            f"/api/v1/payments/table-sessions/{table_session.id}/payment-preview",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert preview.status_code == 200
        cash_total = preview.json()["cash_total"]

        resp = await client.post(
            f"/api/v1/payments/table-sessions/{table_session.id}/pay",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"method_code": "cash", "amount": 5000},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["payment_status"] == "partial"
        assert data["due_amount"] == cash_total - 5000
        assert data["paid_amount"] == 5000
        # First order should be fully paid, second remains due
        order_a = next(o for o in data["orders"] if o["order_number"] == "D260301-001")
        order_b = next(o for o in data["orders"] if o["order_number"] == "D260301-002")
        assert order_a["due_amount"] == 0
        assert order_b["due_amount"] == cash_total - 5000

    @pytest.mark.asyncio
    async def test_overpay_rejected(
        self, client: AsyncClient, admin_token: str,
        table_session, session_order_a, session_order_b,
        cash_method,
    ):
        resp = await client.post(
            f"/api/v1/payments/table-sessions/{table_session.id}/pay",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"method_code": "cash", "amount": 9000},
        )
        assert resp.status_code == 400
        assert "exceeds" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_closed_session_rejected(
        self, client: AsyncClient, admin_token: str, db: AsyncSession,
        table_session, session_order_a, cash_method,
    ):
        table_session.status = "closed"
        await db.flush()
        await db.commit()
        resp = await client.post(
            f"/api/v1/payments/table-sessions/{table_session.id}/pay",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"method_code": "cash", "amount": 5000},
        )
        assert resp.status_code == 400
        assert "closed" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Tests: Session Split Pay
# ---------------------------------------------------------------------------

class TestSessionSplitPay:
    @pytest.mark.asyncio
    async def test_split_pay_full(
        self, client: AsyncClient, admin_token: str,
        table_session, session_order_a, session_order_b,
        cash_method, card_method,
    ):
        resp = await client.post(
            f"/api/v1/payments/table-sessions/{table_session.id}/split",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "allocations": [
                    {"method_code": "cash", "amount": 5000},
                    {"method_code": "card", "amount": 3000, "reference": "1234"},
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["due_amount"] == 0
        assert data["payment_status"] == "paid"

    @pytest.mark.asyncio
    async def test_split_mixed_tax_base_settles_to_zero_due(
        self, client: AsyncClient, admin_token: str,
        table_session, session_order_a, session_order_b,
        cash_method, card_method,
    ):
        preview = await client.get(
            f"/api/v1/payments/table-sessions/{table_session.id}/payment-preview",
            headers={"Authorization": f"Bearer {admin_token}"},
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
            f"/api/v1/payments/table-sessions/{table_session.id}/split",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "allocations": [
                    {"method_code": "cash", "amount": cash_payable, "tendered_amount": cash_payable},
                    {"method_code": "card", "amount": card_payable, "reference": "SPLIT-MIX"},
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["due_amount"] == 0
        assert data["payment_status"] == "paid"
        assert data["paid_amount"] == cash_payable + card_payable

    @pytest.mark.asyncio
    async def test_split_overpay_rejected(
        self, client: AsyncClient, admin_token: str,
        table_session, session_order_a, session_order_b,
        cash_method, card_method,
    ):
        resp = await client.post(
            f"/api/v1/payments/table-sessions/{table_session.id}/split",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "allocations": [
                    {"method_code": "cash", "amount": 5000},
                    {"method_code": "card", "amount": 5000},
                ],
            },
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests: Tenant Isolation
# ---------------------------------------------------------------------------

class TestSessionPaymentTenantIsolation:
    @pytest.mark.asyncio
    async def test_cannot_access_other_tenant_session(
        self, client: AsyncClient, table_session, session_order_a,
        other_tenant, other_tenant_token: str,
    ):
        resp = await client.get(
            f"/api/v1/payments/table-sessions/{table_session.id}/summary",
            headers={"Authorization": f"Bearer {other_tenant_token}"},
        )
        assert resp.status_code == 404
