"""P2-Slice 2: Discount Reporting tests.

Tests discount aggregation logic and API response structure.

NOTE: SQLite CAST(ts AS DATE) doesn't truncate timestamps, so report
endpoints that use func.cast(created_at, Date) return 0 results in
SQLite.  We test the aggregation logic directly via SQL queries and
verify the API response *structure* (new fields present + correct types).
Full date-range integration tests require PostgreSQL.
"""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discount import OrderDiscount
from app.models.order import Order, OrderItem
from app.models.user import User
from app.models.tenant import Tenant


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def menu_item_id():
    return uuid.uuid4()


@pytest_asyncio.fixture
async def orders_with_discounts(
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    menu_item_id: uuid.UUID,
):
    """Create orders with varying discounts.

    Order A: total=10000, discount=1500 (bank_promo 1000 + manual 500), status=completed
    Order B: total=5000,  discount=500  (bank_promo 500), status=completed
    Order C: total=3000,  discount=0    (no discount), status=confirmed
    Voided:  total=9000,  discount=900  (manual 900), status=voided — excluded from reports
    """
    # Order A
    order_a = Order(
        tenant_id=tenant.id,
        order_number="T260303-001",
        order_type="dine_in",
        status="completed",
        payment_status="paid",
        subtotal=8621,
        tax_amount=1379,
        discount_amount=1500,
        total=10000,
        created_by=admin_user.id,
    )
    db.add(order_a)
    await db.flush()

    db.add(OrderItem(
        tenant_id=tenant.id, order_id=order_a.id,
        menu_item_id=menu_item_id, name="Chicken Biryani",
        quantity=2, unit_price=5000, total=10000,
    ))
    db.add(OrderDiscount(
        tenant_id=tenant.id, order_id=order_a.id,
        label="Bank Promo 10%", source_type="bank_promo",
        amount=1000, percent_bps=1000, applied_by=admin_user.id,
    ))
    db.add(OrderDiscount(
        tenant_id=tenant.id, order_id=order_a.id,
        label="Manual Discount", source_type="manual",
        amount=500, percent_bps=0, applied_by=admin_user.id,
    ))
    await db.flush()

    # Order B
    order_b = Order(
        tenant_id=tenant.id,
        order_number="T260303-002",
        order_type="takeaway",
        status="completed",
        payment_status="paid",
        subtotal=4310,
        tax_amount=690,
        discount_amount=500,
        total=5000,
        created_by=admin_user.id,
    )
    db.add(order_b)
    await db.flush()

    db.add(OrderItem(
        tenant_id=tenant.id, order_id=order_b.id,
        menu_item_id=menu_item_id, name="Chicken Biryani",
        quantity=1, unit_price=5000, total=5000,
    ))
    db.add(OrderDiscount(
        tenant_id=tenant.id, order_id=order_b.id,
        label="Bank Promo 5%", source_type="bank_promo",
        amount=500, percent_bps=500, applied_by=admin_user.id,
    ))
    await db.flush()

    # Order C (no discounts)
    order_c = Order(
        tenant_id=tenant.id,
        order_number="T260303-003",
        order_type="call_center",
        status="confirmed",
        payment_status="unpaid",
        subtotal=2586,
        tax_amount=414,
        discount_amount=0,
        total=3000,
        created_by=admin_user.id,
    )
    db.add(order_c)
    await db.flush()

    # Voided order
    order_voided = Order(
        tenant_id=tenant.id,
        order_number="T260303-004",
        order_type="dine_in",
        status="voided",
        payment_status="unpaid",
        subtotal=7759,
        tax_amount=1241,
        discount_amount=900,
        total=9000,
        created_by=admin_user.id,
    )
    db.add(order_voided)
    await db.flush()

    db.add(OrderDiscount(
        tenant_id=tenant.id, order_id=order_voided.id,
        label="Voided discount", source_type="manual",
        amount=900, percent_bps=0, applied_by=admin_user.id,
    ))
    await db.flush()
    await db.commit()

    return {"a": order_a, "b": order_b, "c": order_c, "voided": order_voided}


# ── Discount Aggregation Logic (direct SQL) ──────────────────────────
# These tests verify the exact SQL pattern used in report_service and
# zreport_service, but without the date-cast filter (SQLite limitation).


class TestDiscountAggregation:
    """Core discount GROUP BY logic — same pattern as report_service."""

    @pytest.mark.asyncio
    async def test_discount_breakdown_by_source_type(
        self, db: AsyncSession, orders_with_discounts,
    ):
        """GROUP BY source_type aggregates correctly, excluding voided orders."""
        tenant_id = orders_with_discounts["a"].tenant_id
        result = await db.execute(
            select(
                OrderDiscount.source_type,
                func.count(OrderDiscount.id).label("count"),
                func.coalesce(func.sum(OrderDiscount.amount), 0).label("total"),
            )
            .join(Order, OrderDiscount.order_id == Order.id)
            .where(
                OrderDiscount.tenant_id == tenant_id,
                Order.status != "voided",
            )
            .group_by(OrderDiscount.source_type)
            .order_by(func.sum(OrderDiscount.amount).desc())
        )
        rows = {r.source_type: {"count": r.count, "total": r.total} for r in result.all()}

        # bank_promo: disc_a1(1000) + disc_b1(500) = 1500, count=2
        assert rows["bank_promo"]["total"] == 1500
        assert rows["bank_promo"]["count"] == 2
        # manual: disc_a2(500) only — voided order's disc_voided(900) excluded
        assert rows["manual"]["total"] == 500
        assert rows["manual"]["count"] == 1

    @pytest.mark.asyncio
    async def test_total_discount_from_orders(
        self, db: AsyncSession, orders_with_discounts,
    ):
        """Sum of Order.discount_amount excludes voided orders."""
        tenant_id = orders_with_discounts["a"].tenant_id
        result = await db.execute(
            select(
                func.coalesce(func.sum(Order.discount_amount), 0).label("discount"),
                func.coalesce(func.sum(Order.total), 0).label("revenue"),
            ).where(
                Order.tenant_id == tenant_id,
                Order.status != "voided",
            )
        )
        row = result.one()
        # A(1500) + B(500) + C(0) = 2000
        assert row.discount == 2000
        # A(10000) + B(5000) + C(3000) = 18000
        assert row.revenue == 18000
        # net_revenue = revenue - discount
        assert row.revenue - row.discount == 16000

    @pytest.mark.asyncio
    async def test_no_discounts_returns_zero(
        self, db: AsyncSession, tenant: Tenant, admin_user: User,
    ):
        """When no discounts exist, aggregation returns 0 / empty."""
        order_plain = Order(
            tenant_id=tenant.id,
            order_number="T260303-010",
            order_type="takeaway",
            status="completed",
            payment_status="paid",
            subtotal=8621, tax_amount=1379,
            discount_amount=0, total=10000,
            created_by=admin_user.id,
        )
        db.add(order_plain)
        await db.flush()

        result = await db.execute(
            select(
                func.coalesce(func.sum(Order.discount_amount), 0).label("discount"),
            ).where(
                Order.tenant_id == tenant.id,
                Order.status != "voided",
            )
        )
        assert result.scalar_one() == 0

        disc_result = await db.execute(
            select(
                OrderDiscount.source_type,
                func.count(OrderDiscount.id).label("count"),
            )
            .join(Order, OrderDiscount.order_id == Order.id)
            .where(
                OrderDiscount.tenant_id == tenant.id,
                Order.status != "voided",
            )
            .group_by(OrderDiscount.source_type)
        )
        assert disc_result.all() == []

    @pytest.mark.asyncio
    async def test_tenant_isolation(
        self,
        db: AsyncSession,
        orders_with_discounts,
        other_tenant: Tenant,
        other_tenant_user: User,
    ):
        """Discount aggregation is scoped to tenant_id."""
        # Other tenant has no orders/discounts
        result = await db.execute(
            select(
                func.coalesce(func.sum(Order.discount_amount), 0).label("discount"),
            ).where(
                Order.tenant_id == other_tenant.id,
                Order.status != "voided",
            )
        )
        assert result.scalar_one() == 0


# ── API Response Structure Tests ──────────────────────────────────────
# Verify the new discount fields exist in API responses.


class TestSalesSummaryStructure:
    """Sales summary endpoint returns the new discount fields."""

    @pytest.mark.asyncio
    async def test_response_has_discount_fields(
        self,
        client: AsyncClient,
        admin_token: str,
        tenant: Tenant,
    ):
        """Response includes total_discount, net_revenue, discount_breakdown."""
        today = date.today().isoformat()
        resp = await client.get(
            "/api/v1/reports/sales-summary",
            params={"date_from": today, "date_to": today},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_discount" in data
        assert "net_revenue" in data
        assert "discount_breakdown" in data
        assert isinstance(data["discount_breakdown"], list)
        # Invariant: net_revenue = total_revenue - total_discount
        assert data["net_revenue"] == data["total_revenue"] - data["total_discount"]


class TestZReportStructure:
    """Z-report endpoint returns the new discount fields."""

    @pytest.mark.asyncio
    async def test_response_has_discount_fields(
        self,
        client: AsyncClient,
        admin_token: str,
        tenant: Tenant,
    ):
        """Response includes net_revenue and discount_breakdown."""
        today = date.today().isoformat()
        resp = await client.get(
            "/api/v1/reports/z-report",
            params={"date": today},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "net_revenue" in data
        assert "discount_breakdown" in data
        assert isinstance(data["discount_breakdown"], list)
        assert data["net_revenue"] == data["total_revenue"] - data["total_discount"]


class TestCsvStructure:
    """CSV export includes discount-related lines."""

    @pytest.mark.asyncio
    async def test_csv_has_discount_headers(
        self,
        client: AsyncClient,
        admin_token: str,
        tenant: Tenant,
    ):
        """CSV output includes Total Discount and Net Revenue rows."""
        today = date.today().isoformat()
        resp = await client.get(
            "/api/v1/reports/sales-summary/csv",
            params={"date_from": today, "date_to": today},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.text
        assert "Total Discount (PKR)" in body
        assert "Net Revenue (PKR)" in body
