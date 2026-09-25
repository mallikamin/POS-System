"""Danny's UAT round 3 on Reports and the Dashboard (2026-09-26).

  D-52 each top/bottom item carries its menu photo
  D-53 the hourly chart covers the whole date range, not its first day
  D-54 an item is never both a top-10 and a bottom-5 performer
  D-55 figures compare with the previous period, like for like
  D-56 dine-in by table size, counted in visits, no pattern from a tiny sample
  D-57 the owner's live feed, built from recorded events only

The clock stands at 14:00 in Faisalabad on Sat 26 Sep 2026 (09:00 UTC).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floor import Floor, Table
from app.models.menu import Category, MenuItem
from app.models.order import Order, OrderItem, OrderStatusLog
from app.models.payment import Payment, PaymentMethod
from app.models.restaurant_config import RestaurantConfig
from app.models.table_session import TableSession
from app.models.tenant import Tenant
from app.models.user import User
from app.services import activity_feed_service, dashboard_service, report_service
from app.utils import tenant_time

pytestmark = pytest.mark.asyncio

NOW_UTC = datetime(2026, 9, 26, 9, 0, tzinfo=timezone.utc)  # 14:00 PKT
TODAY = date(2026, 9, 26)
KHI = "Asia/Karachi"


def utc(d: int, h: int, m: int = 0) -> datetime:
    """Pakistan local 2026-09-<d> h:m, as UTC."""
    return datetime(2026, 9, d, h, m, tzinfo=ZoneInfo(KHI)).astimezone(timezone.utc)


@pytest.fixture(autouse=True)
def afternoon_in_faisalabad(monkeypatch):
    monkeypatch.setattr(tenant_time, "_utcnow", lambda: NOW_UTC)


@pytest_asyncio.fixture
async def karachi(db: AsyncSession, tenant: Tenant) -> None:
    db.add(RestaurantConfig(tenant_id=tenant.id, currency="PKR", timezone=KHI))
    await db.commit()


@pytest_asyncio.fixture
async def menu(db: AsyncSession, tenant: Tenant) -> dict[str, MenuItem]:
    cat = Category(tenant_id=tenant.id, name="Mains", display_order=1)
    db.add(cat)
    await db.flush()
    items = {}
    for i, name in enumerate(
        ["Karahi", "Mutton", "Naan", "Raita", "Soup", "Coffee", "Rice", "Kebab",
         "Tikka", "Brownie", "Lassi", "Salad", "Roti"]
    ):
        m = MenuItem(
            tenant_id=tenant.id, category_id=cat.id, name=name, price=1000,
            image_url=f"/photos/{name.lower()}.jpg" if name != "Roti" else None,
        )
        db.add(m)
        items[name] = m
    await db.flush()
    return items


def _order(tenant, user, number, at, lines, *, order_type="dine_in", table=None,
           session=None, status="completed", payment_status="paid"):
    total = sum(q * p for _, q, p in lines)
    o = Order(
        tenant_id=tenant.id, order_number=number, order_type=order_type, status=status,
        payment_status=payment_status, subtotal=total, tax_amount=0, discount_amount=0,
        total=total, created_by=user.id, created_at=at,
        table_id=table.id if table else None,
        table_session_id=session.id if session else None,
    )
    o.items = [
        OrderItem(tenant_id=tenant.id, menu_item_id=m.id, name=m.name, quantity=q,
                  unit_price=p, total=q * p)
        for m, q, p in lines
    ]
    return o


# ---------------------------------------------------------------------------
# D-55 comparison periods: pure date logic
# ---------------------------------------------------------------------------


def _local(d: date, h: int, m: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, h, m, tzinfo=ZoneInfo(KHI))


class TestComparisonPeriods:
    def test_today_is_compared_with_yesterday_up_to_the_same_time(self):
        p = report_service.comparison_periods(KHI, TODAY, TODAY, _local(TODAY, 2, 27))
        assert (p["previous_from"], p["previous_to"]) == (date(2026, 9, 25), date(2026, 9, 25))
        start, end = p["previous"]
        assert start == datetime(2026, 9, 24, 19, 0, tzinfo=timezone.utc)  # 25th 00:00 PKT
        assert end == datetime(2026, 9, 24, 21, 27, tzinfo=timezone.utc)  # 25th 02:27 PKT
        assert p["previous_cut_at"] == "2026-09-25T02:27"

    def test_a_past_day_is_compared_with_the_whole_day_before(self):
        p = report_service.comparison_periods(KHI, date(2026, 9, 25), date(2026, 9, 25), _local(TODAY, 14))
        start, end = p["previous"]
        assert end - start == (datetime(2026, 9, 25) - datetime(2026, 9, 24))
        assert p["previous_cut_at"] is None

    def test_this_week_so_far_is_compared_with_the_same_days_last_week(self):
        # The page's week starts Sunday. Sun 20 to Sat 26 (today, 14:00) vs
        # Sun 13 to Sat 19 up to 14:00.
        p = report_service.comparison_periods(KHI, date(2026, 9, 20), TODAY, _local(TODAY, 14))
        assert (p["previous_from"], p["previous_to"]) == (date(2026, 9, 13), date(2026, 9, 19))
        assert p["previous"][1] == datetime(2026, 9, 19, 9, 0, tzinfo=timezone.utc)

    def test_a_short_week_so_far_still_goes_back_a_whole_week(self):
        # Mon 21 to Sat 26 must pair Saturday with Saturday, not with Sunday 20.
        p = report_service.comparison_periods(KHI, date(2026, 9, 21), TODAY, _local(TODAY, 14))
        assert (p["previous_from"], p["previous_to"]) == (date(2026, 9, 14), date(2026, 9, 19))

    def test_this_month_so_far_is_compared_with_last_month_to_the_same_date(self):
        p = report_service.comparison_periods(KHI, date(2026, 9, 1), TODAY, _local(TODAY, 14))
        assert (p["previous_from"], p["previous_to"]) == (date(2026, 8, 1), date(2026, 8, 26))

    def test_a_whole_past_month_is_compared_with_the_whole_month_before(self):
        p = report_service.comparison_periods(KHI, date(2026, 3, 1), date(2026, 3, 31), _local(TODAY, 14))
        assert (p["previous_from"], p["previous_to"]) == (date(2026, 2, 1), date(2026, 2, 28))

    def test_a_custom_range_is_compared_with_the_same_length_before_it(self):
        p = report_service.comparison_periods(KHI, date(2026, 9, 10), date(2026, 9, 12), _local(TODAY, 14))
        assert (p["previous_from"], p["previous_to"]) == (date(2026, 9, 7), date(2026, 9, 9))


# ---------------------------------------------------------------------------
# D-55 in the summary and the dashboard
# ---------------------------------------------------------------------------


async def test_summary_carries_the_previous_period(db, tenant, admin_user, karachi, menu):
    k = menu["Karahi"]
    db.add(_order(tenant, admin_user, "T1", utc(26, 13), [(k, 1, 9000)]))
    db.add(_order(tenant, admin_user, "Y1", utc(25, 12), [(k, 1, 10000)]))  # before 14:00
    db.add(_order(tenant, admin_user, "Y2", utc(25, 20), [(k, 1, 50000)]))  # after 14:00
    await db.commit()

    s = await report_service.get_sales_summary(db, tenant.id, TODAY, TODAY, compare=True)
    assert s["total_revenue"] == 9000
    assert s["previous"]["total_revenue"] == 10000  # Y2 is later in the day than now
    assert s["previous"]["cut_at"] == "2026-09-25T14:00"

    plain = await report_service.get_sales_summary(db, tenant.id, TODAY, TODAY)
    assert plain["previous"] is None


async def test_dashboard_compares_with_yesterday_so_far(db, tenant, admin_user, karachi, menu):
    k = menu["Karahi"]
    db.add(_order(tenant, admin_user, "T1", utc(26, 13), [(k, 1, 9000)]))
    db.add(_order(tenant, admin_user, "Y1", utc(25, 12), [(k, 1, 10000)]))
    db.add(_order(tenant, admin_user, "Y2", utc(25, 20), [(k, 1, 50000)]))
    await db.commit()

    kpis = await dashboard_service.get_dashboard_kpis(db, tenant.id)
    assert kpis["today_revenue"] == 9000
    assert kpis["yesterday_revenue"] == 60000
    assert kpis["yesterday_same_time_revenue"] == 10000
    assert kpis["yesterday_same_time_orders"] == 1


# ---------------------------------------------------------------------------
# D-52, D-54: item tables
# ---------------------------------------------------------------------------


async def test_items_carry_photos_and_never_appear_twice(db, tenant, admin_user, karachi, menu):
    # 13 dishes, revenue 13000 down to 1000: the 25 Sep shape.
    names = list(menu)
    lines = [(menu[n], 1, (13 - i) * 1000) for i, n in enumerate(names)]
    db.add(_order(tenant, admin_user, "A", utc(26, 12), lines))
    db.add(_order(tenant, admin_user, "P", utc(25, 12), [(menu["Karahi"], 2, 4000)]))
    await db.commit()

    perf = await report_service.get_item_performance(db, tenant.id, TODAY, TODAY, compare=True)
    top = [i["name"] for i in perf["top_items"]]
    bottom = [i["name"] for i in perf["bottom_items"]]
    assert top == names[:10]
    assert bottom == ["Roti", "Salad", "Lassi"]  # lowest first, none from the top 10
    assert not set(top) & set(bottom)

    karahi = perf["top_items"][0]
    assert karahi["image_url"] == "/photos/karahi.jpg"
    assert (karahi["previous_quantity"], karahi["previous_revenue"]) == (2, 8000)
    assert perf["top_items"][1]["previous_revenue"] == 0  # sold nothing then
    assert perf["bottom_items"][0]["image_url"] is None  # Roti has no photo


async def test_ten_items_or_fewer_have_no_bottom_list(db, tenant, admin_user, karachi, menu):
    lines = [(menu[n], 1, 1000) for n in list(menu)[:8]]
    db.add(_order(tenant, admin_user, "A", utc(26, 12), lines))
    await db.commit()
    perf = await report_service.get_item_performance(db, tenant.id, TODAY, TODAY)
    assert perf["bottom_items"] == []
    assert perf["top_items"][0]["previous_revenue"] is None  # not asked


# ---------------------------------------------------------------------------
# D-53: hourly over a range
# ---------------------------------------------------------------------------


async def test_hourly_covers_every_day_of_the_range(db, tenant, admin_user, karachi, menu):
    k = menu["Karahi"]
    db.add(_order(tenant, admin_user, "M", utc(21, 13), [(k, 1, 1000)]))  # Monday lunch
    db.add(_order(tenant, admin_user, "S", utc(26, 13), [(k, 1, 2000)]))  # Saturday lunch
    db.add(_order(tenant, admin_user, "D", utc(24, 20), [(k, 1, 4000)]))  # Thursday dinner
    await db.commit()

    week = await report_service.get_hourly_breakdown(db, tenant.id, date(2026, 9, 21), TODAY)
    by_hour = {b["hour"]: b for b in week["buckets"]}
    assert by_hour[13] == {"hour": 13, "order_count": 2, "revenue": 3000}
    assert by_hour[20]["revenue"] == 4000
    assert (week["date"], week["date_to"]) == ("2026-09-21", "2026-09-26")


# ---------------------------------------------------------------------------
# D-56: table size
# ---------------------------------------------------------------------------


async def test_table_size_counts_visits_and_hides_thin_patterns(
    db, tenant, admin_user, karachi, menu
):
    floor = Floor(tenant_id=tenant.id, name="Hall 1")
    db.add(floor)
    await db.flush()
    four = Table(tenant_id=tenant.id, floor_id=floor.id, number=1, capacity=4)
    six = Table(tenant_id=tenant.id, floor_id=floor.id, number=2, capacity=6)
    db.add_all([four, six])
    await db.flush()

    k, m, n = menu["Karahi"], menu["Mutton"], menu["Naan"]
    # Five 4-seater visits, each two orders in one session (mains, then naan).
    for v in range(5):
        s = TableSession(tenant_id=tenant.id, table_id=four.id, status="closed",
                         opened_by=admin_user.id, opened_at=utc(26, 12))
        db.add(s)
        await db.flush()
        lines = [(k, 1, 3000)] if v < 4 else [(m, 1, 5000)]
        db.add(_order(tenant, admin_user, f"F{v}a", utc(26, 12, v), lines, table=four, session=s))
        db.add(_order(tenant, admin_user, f"F{v}b", utc(26, 12, 30 + v), [(n, 2, 200)], table=four, session=s))
    # Two 6-seater visits: too few to read a pattern.
    for v in range(2):
        db.add(_order(tenant, admin_user, f"S{v}", utc(26, 13, v), [(m, 2, 5000)], table=six))
    # A takeaway never counts.
    db.add(_order(tenant, admin_user, "TK", utc(26, 13), [(k, 1, 3000)], order_type="takeaway"))
    await db.commit()

    report = await report_service.get_table_size_report(db, tenant.id, TODAY, TODAY)
    sizes = {s["capacity"]: s for s in report["sizes"]}

    four_s = sizes[4]
    assert (four_s["visits"], four_s["orders"]) == (5, 10)
    assert four_s["revenue"] == 4 * 3000 + 5000 + 5 * 400
    assert four_s["avg_per_visit"] == four_s["revenue"] // 5
    assert four_s["enough_data"] is True
    first, second = four_s["top_items"][:2]
    assert (first["name"], first["visits_with"], first["share_pct"]) == ("Naan", 5, 100)
    assert (second["name"], second["visits_with"], second["share_pct"]) == ("Karahi", 4, 80)

    six_s = sizes[6]
    assert (six_s["visits"], six_s["enough_data"], six_s["top_items"]) == (2, False, [])


# ---------------------------------------------------------------------------
# D-57: live feed
# ---------------------------------------------------------------------------


async def test_feed_tells_the_owner_what_happened_where(db, tenant, admin_user, karachi, menu):
    floor = Floor(tenant_id=tenant.id, name="Tree House")
    db.add(floor)
    await db.flush()
    t1 = Table(tenant_id=tenant.id, floor_id=floor.id, number=1, capacity=4)
    db.add(t1)
    cash = PaymentMethod(tenant_id=tenant.id, code="cash", display_name="Cash")
    db.add(cash)
    await db.flush()
    s = TableSession(tenant_id=tenant.id, table_id=t1.id, status="closed",
                     opened_by=admin_user.id, opened_at=utc(26, 12))
    db.add(s)
    await db.flush()

    k = menu["Karahi"]
    placed = utc(26, 12, 0)
    o1 = _order(tenant, admin_user, "260926-001", placed, [(k, 2, 3000)], table=t1, session=s)
    o2 = _order(tenant, admin_user, "260926-002", utc(26, 12, 20), [(menu["Naan"], 3, 200)], table=t1, session=s)
    db.add_all([o1, o2])
    await db.flush()
    for o in (o1, o2):
        db.add(OrderStatusLog(tenant_id=tenant.id, order_id=o.id, from_status=None,
                              to_status="confirmed", changed_by=admin_user.id, created_at=o.created_at))
        # Same request: must not show as a separate line.
        db.add(OrderStatusLog(tenant_id=tenant.id, order_id=o.id, from_status="confirmed",
                              to_status="in_kitchen", changed_by=admin_user.id, created_at=o.created_at))
    db.add(OrderStatusLog(tenant_id=tenant.id, order_id=o1.id, from_status="in_kitchen",
                          to_status="ready", changed_by=admin_user.id, created_at=utc(26, 12, 25)))
    settle = utc(26, 13, 5)
    for o in (o1, o2):  # one settlement writes one row per order
        db.add(Payment(tenant_id=tenant.id, order_id=o.id, method_id=cash.id, kind="payment",
                       status="completed", amount=o.total, change_amount=0,
                       processed_by=admin_user.id, created_at=settle))
        db.add(OrderStatusLog(tenant_id=tenant.id, order_id=o.id, from_status="served",
                              to_status="completed", changed_by=admin_user.id, created_at=settle))
    await db.commit()

    feed = await activity_feed_service.get_activity_feed(db, tenant.id)
    lines = [(e["where"], e["kind"], e["text"], e["amount"]) for e in feed["events"]]
    assert lines == [
        ("Tree House, Table 1", "settled", "settled the bill, Cash", 6600),
        ("Tree House, Table 1", "ready", "order is ready to serve", None),
        ("Tree House, Table 1", "placed", "placed an order: 3 items", 600),
        ("Tree House, Table 1", "placed", "placed an order: 2 items", 6000),
    ]
    assert feed["date"] == "2026-09-26"


async def test_feed_route_is_owner_only(client, admin_token, cashier_token, karachi):
    ok = await client.get("/api/v1/dashboard/activity", headers={"Authorization": "Bearer " + admin_token})
    assert ok.status_code == 200, ok.text
    assert ok.json()["events"] == []
    denied = await client.get("/api/v1/dashboard/activity", headers={"Authorization": "Bearer " + cashier_token})
    assert denied.status_code == 403


async def test_report_routes_answer_with_the_new_fields(client, admin_token, karachi):
    auth = {"Authorization": "Bearer " + admin_token}
    q = {"date_from": "2026-09-21", "date_to": "2026-09-26"}
    s = await client.get("/api/v1/reports/sales-summary", headers=auth, params={**q, "compare": "true"})
    assert s.status_code == 200, s.text
    assert s.json()["previous"]["date_from"] == "2026-09-14"
    h = await client.get("/api/v1/reports/hourly-breakdown", headers=auth, params=q)
    assert h.status_code == 200, h.text
    assert h.json()["date_to"] == "2026-09-26"
    legacy = await client.get("/api/v1/reports/hourly-breakdown", headers=auth, params={"date": "2026-09-25"})
    assert legacy.json()["date_to"] == "2026-09-25"
    t = await client.get("/api/v1/reports/table-size", headers=auth, params=q)
    assert t.status_code == 200, t.text
    assert t.json() == {"min_visits": 5, "sizes": []}
