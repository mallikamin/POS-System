"""OI-58a: online orders must not be silently dropped from reports/dashboard.

`get_sales_summary` already computed an `"online"` bucket internally but only
read out dine_in/takeaway/call_center; `get_live_operations` filtered active
orders into the same three buckets and dropped anything else on the floor.
Both bugs meant an online-ordering tenant's totals looked right (the
unfiltered top-level sum already included online) but every breakdown lied
about where the money came from.

⚠️ `test_sales_summary_*` below are deliberately structural (zero orders),
not "create an order, assert the number comes back right" -- this suite's
in-memory SQLite DB cannot exercise that path at all. `get_sales_summary`'s
date filter does `func.cast(Order.created_at, Date) >= date_from`, and SQLite
casts a "2026-08-01 00:36:50" TEXT value to NUMERIC affinity by taking its
leading digit run -- i.e. the CAST returns the integer `2026`, not a date.
Comparing that INTEGER against a TEXT date bound always evaluates false under
SQLite's storage-class ordering (NUMERIC sorts below TEXT unconditionally),
so *every* date-ranged report query returns zero rows in this test harness,
regardless of the actual dates involved -- confirmed directly: even a
2000-01-01..2100-01-01 range on a real order still came back empty. This is
a pre-existing gap in the whole report_service.py/dashboard_service.py CAST
pattern (see the many other `func.cast(..., Date)` call sites), not
something introduced here, and it does not affect production, which runs
real Postgres (its CAST genuinely truncates to a date) -- verified directly
against the live local dev Postgres DB as part of this same session's OI-57
work. Fixing the CAST mechanism for every existing report is out of scope
for OI-58; logged in ERROR_LOG.md instead. The new report queries OI-58c
adds are written with plain datetime-range comparisons (no CAST) specifically
so they don't inherit this landmine and stay meaningfully testable here.

`get_live_operations` has no date filter at all, so its online-bucket test
below exercises the real fix end to end, not just the response shape.
"""

from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.tenant import Tenant
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def _make_order(
    db: AsyncSession,
    tenant_id,
    user_id,
    *,
    number: str,
    order_type: str,
    total: int,
    status: str = "confirmed",
) -> Order:
    o = Order(
        tenant_id=tenant_id,
        order_number=number,
        order_type=order_type,
        status=status,
        payment_status="unpaid",
        subtotal=total,
        tax_amount=0,
        discount_amount=0,
        total=total,
        created_by=user_id,
    )
    db.add(o)
    await db.commit()
    return o


async def test_sales_summary_response_includes_online_fields(
    client: AsyncClient,
    admin_token: str,
    tenant: Tenant,
):
    today = date.today().isoformat()
    resp = await client.get(
        "/api/v1/reports/sales-summary",
        params={"date_from": today, "date_to": today},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "online_revenue" in data
    assert "online_orders" in data
    assert data["online_revenue"] == 0
    assert data["online_orders"] == 0


async def test_sales_summary_csv_includes_online_rows(
    client: AsyncClient,
    admin_token: str,
    tenant: Tenant,
):
    today = date.today().isoformat()
    resp = await client.get(
        "/api/v1/reports/sales-summary/csv",
        params={"date_from": today, "date_to": today},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "Online Revenue" in resp.text
    assert "Online Orders" in resp.text


async def test_live_operations_includes_an_online_bucket(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
):
    online_order = await _make_order(
        db,
        tenant.id,
        admin_user.id,
        number="O-1",
        order_type="online",
        total=2000,
        status="in_kitchen",
    )

    resp = await client.get(
        "/api/v1/dashboard/live",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "online" in data
    online_ids = [o["id"] for o in data["online"]]
    assert str(online_order.id) in online_ids
    # And it must not have also leaked into an unrelated bucket.
    for other in ("dine_in", "takeaway", "call_center"):
        assert str(online_order.id) not in [o["id"] for o in data[other]]
