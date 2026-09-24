"""A restaurant's "today" is its own day, not the server's UTC day.

Danny's UAT, 2026-09-25 (D-18, D-30): at 01:59 in Faisalabad (20:59 UTC the
day before) an order was numbered with yesterday's date, and the dashboard
counted the previous afternoon as today's takings. Every test here stands the
clock at 01:30 Pakistan time, which is 20:30 UTC the previous day.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.models.user import User
from app.services import dashboard_service, order_service, report_service, zreport_service
from app.utils import tenant_time

# 25 Sep 2026 01:30 in Pakistan (UTC+5) == 24 Sep 2026 20:30 UTC.
NOW_UTC = datetime(2026, 9, 24, 20, 30, tzinfo=timezone.utc)
PK_TODAY = date(2026, 9, 25)


@pytest.fixture(autouse=True)
def pakistan_after_midnight(monkeypatch):
    monkeypatch.setattr(tenant_time, "_utcnow", lambda: NOW_UTC)


@pytest_asyncio.fixture
async def karachi(db: AsyncSession, tenant: Tenant) -> None:
    db.add(RestaurantConfig(tenant_id=tenant.id, currency="PKR", timezone="Asia/Karachi"))
    await db.commit()


def _order(tenant: Tenant, user: User, number: str, at_utc: datetime, total: int) -> Order:
    return Order(
        tenant_id=tenant.id, order_number=number, order_type="dine_in", status="completed",
        payment_status="paid", subtotal=total, tax_amount=0, discount_amount=0, total=total,
        created_by=user.id, created_at=at_utc,
    )


async def test_order_number_carries_the_restaurants_date(db, tenant, karachi):
    number = await order_service.generate_order_number(db, tenant.id)
    assert number.startswith("260925-"), number


async def test_dashboard_today_is_the_restaurants_day(db, tenant, admin_user, karachi):
    # Yesterday afternoon in Pakistan (the D-30 case) and just after midnight.
    db.add(_order(tenant, admin_user, "A", datetime(2026, 9, 24, 9, 15, tzinfo=timezone.utc), 5000))
    db.add(_order(tenant, admin_user, "B", datetime(2026, 9, 24, 20, 5, tzinfo=timezone.utc), 7000))
    await db.commit()

    kpis = await dashboard_service.get_dashboard_kpis(db, tenant.id)
    assert kpis["today_orders"] == 1
    assert kpis["today_revenue"] == 7000
    assert kpis["yesterday_revenue"] == 5000


async def test_hourly_uses_the_restaurants_hours(db, tenant, admin_user, karachi):
    # 08:15 UTC is 13:15 in Faisalabad: the lunch bar, not the breakfast one.
    db.add(_order(tenant, admin_user, "L", datetime(2026, 9, 24, 8, 15, tzinfo=timezone.utc), 4000))
    await db.commit()

    report = await report_service.get_hourly_breakdown(db, tenant.id, date(2026, 9, 24))
    by_hour = {b["hour"]: b for b in report["buckets"]}
    assert by_hour[13]["order_count"] == 1
    assert by_hour[8]["order_count"] == 0


async def test_zreport_day_is_the_restaurants_day(db, tenant, admin_user, karachi):
    # 01:59 on the 25th in Pakistan belongs to the 25th's settlement.
    db.add(_order(tenant, admin_user, "N", datetime(2026, 9, 24, 20, 59, tzinfo=timezone.utc), 6894))
    await db.commit()

    z25 = await zreport_service.generate_zreport(db, tenant.id, PK_TODAY, "test")
    z24 = await zreport_service.generate_zreport(db, tenant.id, date(2026, 9, 24), "test")
    assert z25["total_orders"] == 1
    assert z25["total_revenue"] == 6894
    assert z24["total_orders"] == 0


async def test_tenant_without_a_timezone_keeps_utc(db, tenant):
    number = await order_service.generate_order_number(db, tenant.id)
    assert number.startswith("260924-"), number
