"""OI-58c/d: prepaid-vs-COD, rejected orders, and Stripe reconciliation.

Unlike `report_service.get_sales_summary` (see ERROR_LOG.md 2026-08-01),
`online_report_service` filters dates with plain `Order.created_at >= / <`
comparisons, not `func.cast(..., Date)` -- so these tests genuinely exercise
real aggregation against this suite's SQLite DB, not just response shape.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.tenant import Tenant
from app.models.user import User
from app.services import stripe_service

pytestmark = pytest.mark.asyncio


async def _make_order(
    db: AsyncSession,
    tenant_id,
    user_id,
    *,
    number: str,
    total: int,
    order_type: str = "online",
    status: str = "confirmed",
    stripe_checkout_session_id: str | None = None,
    stripe_payment_intent_id: str | None = None,
    payment_captured_at: datetime | None = None,
    payment_status: str = "unpaid",
    rejected_at: datetime | None = None,
    rejection_reason: str | None = None,
) -> Order:
    o = Order(
        tenant_id=tenant_id,
        order_number=number,
        order_type=order_type,
        status=status,
        payment_status=payment_status,
        subtotal=total,
        tax_amount=0,
        discount_amount=0,
        total=total,
        created_by=user_id,
        stripe_checkout_session_id=stripe_checkout_session_id,
        stripe_payment_intent_id=stripe_payment_intent_id,
        payment_captured_at=payment_captured_at,
        rejected_at=rejected_at,
        rejection_reason=rejection_reason,
    )
    db.add(o)
    await db.commit()
    return o


def _today_range() -> tuple[str, str]:
    today = date.today().isoformat()
    return today, today


# ---------------------------------------------------------------------------
# Prepaid vs Cash-on-Delivery
# ---------------------------------------------------------------------------


async def test_prepaid_vs_cod_buckets_correctly(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
):
    await _make_order(
        db,
        tenant.id,
        admin_user.id,
        number="O-card",
        total=2000,
        stripe_checkout_session_id="cs_test_1",
    )
    await _make_order(db, tenant.id, admin_user.id, number="O-cash", total=1500)
    # Voided orders must not count either way.
    await _make_order(
        db, tenant.id, admin_user.id, number="O-voided", total=9999, status="voided"
    )

    date_from, date_to = _today_range()
    resp = await client.get(
        "/api/v1/reports/online/prepaid-vs-cod",
        params={"date_from": date_from, "date_to": date_to},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["prepaid_revenue"] == 2000
    assert data["prepaid_orders"] == 1
    assert data["cod_revenue"] == 1500
    assert data["cod_orders"] == 1


async def test_prepaid_vs_cod_csv_has_both_rows(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
):
    await _make_order(
        db,
        tenant.id,
        admin_user.id,
        number="O-card",
        total=2000,
        stripe_checkout_session_id="cs_test_1",
    )
    date_from, date_to = _today_range()
    resp = await client.get(
        "/api/v1/reports/online/prepaid-vs-cod/csv",
        params={"date_from": date_from, "date_to": date_to},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "Prepaid Revenue" in resp.text
    assert "Cash on Delivery Revenue" in resp.text
    assert "20.0" in resp.text  # 2000 paisa/pence -> 20.0


# ---------------------------------------------------------------------------
# Rejected orders
# ---------------------------------------------------------------------------


async def test_rejected_orders_lists_only_rejected_online_orders(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
):
    now = datetime.now(timezone.utc)
    await _make_order(
        db,
        tenant.id,
        admin_user.id,
        number="O-rejected",
        total=1200,
        status="voided",
        rejected_at=now,
        rejection_reason="Outside delivery area",
    )
    await _make_order(db, tenant.id, admin_user.id, number="O-live", total=800)

    date_from, date_to = _today_range()
    resp = await client.get(
        "/api/v1/reports/online/rejected-orders",
        params={"date_from": date_from, "date_to": date_to},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["total_value"] == 1200
    assert data["orders"][0]["order_number"] == "O-rejected"
    assert data["orders"][0]["rejection_reason"] == "Outside delivery area"


async def test_rejected_orders_falls_back_when_reason_missing(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
):
    """`reject_order` always sets a reason today, but the report must not
    break if a future caller (or old data) leaves it null."""
    await _make_order(
        db,
        tenant.id,
        admin_user.id,
        number="O-no-reason",
        total=500,
        status="voided",
        rejected_at=datetime.now(timezone.utc),
        rejection_reason=None,
    )
    date_from, date_to = _today_range()
    resp = await client.get(
        "/api/v1/reports/online/rejected-orders",
        params={"date_from": date_from, "date_to": date_to},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    data = resp.json()
    assert data["orders"][0]["rejection_reason"] == "No reason provided"


async def test_rejected_orders_scopes_by_rejection_date_not_placement_date(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
):
    """An old order rejected today belongs in today's report."""
    long_ago = datetime.now(timezone.utc) - timedelta(days=30)
    o = await _make_order(
        db,
        tenant.id,
        admin_user.id,
        number="O-old-placed",
        total=700,
        status="voided",
        rejected_at=datetime.now(timezone.utc),
        rejection_reason="Closing soon",
    )
    # Backdate only created_at, leaving rejected_at as "now".
    o.created_at = long_ago
    await db.commit()

    date_from, date_to = _today_range()
    resp = await client.get(
        "/api/v1/reports/online/rejected-orders",
        params={"date_from": date_from, "date_to": date_to},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    numbers = [o["order_number"] for o in resp.json()["orders"]]
    assert "O-old-placed" in numbers


# ---------------------------------------------------------------------------
# Stripe reconciliation
# ---------------------------------------------------------------------------


async def test_stripe_reconciliation_flags_a_match(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
):
    await _make_order(
        db,
        tenant.id,
        admin_user.id,
        number="O-match",
        total=2500,
        stripe_payment_intent_id="pi_match",
        payment_captured_at=datetime.now(timezone.utc),
        payment_status="paid",
    )

    async def fake_retrieve(payment_intent_id: str) -> dict:
        assert payment_intent_id == "pi_match"
        return {"status": "succeeded", "amount_received": 2500, "amount_capturable": 0}

    date_from, date_to = _today_range()
    with patch.object(
        stripe_service, "retrieve_payment_intent", side_effect=fake_retrieve
    ):
        resp = await client.get(
            "/api/v1/reports/online/stripe-reconciliation",
            params={"date_from": date_from, "date_to": date_to},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["checked"] == 1
    assert data["mismatches"] == 0
    assert data["rows"][0]["matches"] is True


async def test_stripe_reconciliation_flags_a_mismatch(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
):
    """DB thinks it was captured for 2500; Stripe says only 2000 landed."""
    await _make_order(
        db,
        tenant.id,
        admin_user.id,
        number="O-mismatch",
        total=2500,
        stripe_payment_intent_id="pi_mismatch",
        payment_captured_at=datetime.now(timezone.utc),
        payment_status="paid",
    )

    async def fake_retrieve(payment_intent_id: str) -> dict:
        return {"status": "succeeded", "amount_received": 2000, "amount_capturable": 0}

    date_from, date_to = _today_range()
    with patch.object(
        stripe_service, "retrieve_payment_intent", side_effect=fake_retrieve
    ):
        resp = await client.get(
            "/api/v1/reports/online/stripe-reconciliation",
            params={"date_from": date_from, "date_to": date_to},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    data = resp.json()
    assert data["mismatches"] == 1
    assert data["rows"][0]["matches"] is False


async def test_stripe_reconciliation_reports_a_lookup_failure_without_crashing(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
):
    await _make_order(
        db,
        tenant.id,
        admin_user.id,
        number="O-error",
        total=1000,
        stripe_payment_intent_id="pi_gone",
    )

    async def fake_retrieve(payment_intent_id: str) -> dict:
        raise stripe_service.StripeError("No such payment_intent: 'pi_gone'")

    date_from, date_to = _today_range()
    with patch.object(
        stripe_service, "retrieve_payment_intent", side_effect=fake_retrieve
    ):
        resp = await client.get(
            "/api/v1/reports/online/stripe-reconciliation",
            params={"date_from": date_from, "date_to": date_to},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mismatches"] == 1
    assert "No such payment_intent" in data["rows"][0]["error"]


async def test_stripe_reconciliation_csv_downloads(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
):
    await _make_order(
        db,
        tenant.id,
        admin_user.id,
        number="O-csv",
        total=1000,
        stripe_payment_intent_id="pi_csv",
        payment_captured_at=datetime.now(timezone.utc),
        payment_status="paid",
    )

    async def fake_retrieve(payment_intent_id: str) -> dict:
        return {"status": "succeeded", "amount_received": 1000, "amount_capturable": 0}

    date_from, date_to = _today_range()
    with patch.object(
        stripe_service, "retrieve_payment_intent", side_effect=fake_retrieve
    ):
        resp = await client.get(
            "/api/v1/reports/online/stripe-reconciliation/csv",
            params={"date_from": date_from, "date_to": date_to},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 200
    assert "O-csv" in resp.text
    assert "Mismatches" in resp.text
