"""Report service -- sales summaries, item performance, hourly breakdown."""

import calendar
import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discount import OrderDiscount
from app.models.floor import Table
from app.models.menu import MenuItem
from app.models.order import Order, OrderItem, OrderStatusLog
from app.models.payment import Payment, PaymentMethod
from app.models.user import User
from app.services.order_visibility import is_real_order
from app.utils.tenant_time import (
    local_now,
    local_range_bounds_utc,
    tenant_range_utc,
    tenant_timezone,
    zone,
)


def _sold(tenant_id: uuid.UUID, start: datetime, end: datetime) -> list:
    """The orders every sales figure counts: this tenant, this window, not
    voided, and real (a card order Stripe never approved is not revenue; counting
    it overstated the client's own reports screen on 2026-08-04, £98.96 shown,
    £36.04 taken). One definition so the cards, the item tables and the hourly
    chart cannot disagree; item performance and the hourly chart used to skip
    `is_real_order()`."""
    return [
        Order.tenant_id == tenant_id,
        Order.created_at >= start,
        Order.created_at < end,
        Order.status != "voided",
        is_real_order(),
    ]


# ---------------------------------------------------------------------------
# PERIOD COMPARISON (Danny's D-55)
# ---------------------------------------------------------------------------


def _is_whole_month_view(date_from: date, date_to: date, today: date) -> bool:
    """1st of a month to its last day, or to today (month to date)."""
    if date_from.day != 1 or (date_from.year, date_from.month) != (date_to.year, date_to.month):
        return False
    last = calendar.monthrange(date_to.year, date_to.month)[1]
    return date_to.day == last or date_to == today


def comparison_periods(
    tz_name: str | None, date_from: date, date_to: date, now: datetime | None = None
) -> dict:
    """The range asked for, and the one to compare it with, as UTC bounds.

    The previous period is the one just before, of the same shape: yesterday
    for a day, the same weekdays a week earlier for a week so far, the month
    before for a month, and for any other range the same number of days
    immediately before it.

    Like for like: when the range runs to today, the day is not over, so the
    previous period is cut at the same clock time on its own last day. Without
    that, 2 am today against all of yesterday reads "down 100%", and a Monday
    against all of last week reads "down 85%".

    `now` is the restaurant's local time (tests pass it; callers leave it out).
    """
    tz = zone(tz_name)
    now = now or local_now(tz_name)
    today = now.date()

    cur_start, cur_end = local_range_bounds_utc(tz_name, date_from, date_to)

    if _is_whole_month_view(date_from, date_to, today):
        prev_month_end = date_from - timedelta(days=1)
        prev_from = prev_month_end.replace(day=1)
        prev_to = prev_month_end.replace(
            day=min(date_to.day, prev_month_end.day)
            if date_to == today
            else prev_month_end.day
        )
    else:
        span = (date_to - date_from).days + 1
        # A week so far (2 to 7 days ending today) goes back a whole week, to
        # the same weekdays: Sun-Sat so far against last Sun-Sat, not against
        # the six days just before it, which would pair Saturday with Friday.
        shift = 7 if 1 < span <= 7 and date_to >= today else span
        prev_from = date_from - timedelta(days=shift)
        prev_to = date_to - timedelta(days=shift)

    prev_start, prev_end = local_range_bounds_utc(tz_name, prev_from, prev_to)
    cut_at = None
    if date_to >= today:
        # Same clock time on the previous period's last day.
        elapsed = now.replace(tzinfo=None) - datetime.combine(today, time.min)
        cut = datetime.combine(prev_to, time.min, tzinfo=tz) + elapsed
        prev_end = min(prev_end, cut.astimezone(timezone.utc))
        cut_at = cut.replace(tzinfo=None).isoformat(timespec="minutes")

    return {
        "current": (cur_start, cur_end),
        "previous": (prev_start, prev_end),
        "previous_from": prev_from,
        "previous_to": prev_to,
        "previous_cut_at": cut_at,
    }


async def sales_totals(db: AsyncSession, tenant_id: uuid.UUID, start: datetime, end: datetime):
    """Revenue, orders, tax, discount for a window. The one query both the
    range and its comparison use, so they are measured the same way."""
    return (
        await db.execute(
            select(
                func.coalesce(func.sum(Order.total), 0).label("revenue"),
                func.count(Order.id).label("orders"),
                func.coalesce(func.sum(Order.tax_amount), 0).label("tax"),
                func.coalesce(func.sum(Order.discount_amount), 0).label("discount"),
            ).where(*_sold(tenant_id, start, end))
        )
    ).one()


def _headline(row) -> dict:
    return {
        "total_revenue": row.revenue,
        "total_orders": row.orders,
        "avg_order_value": row.revenue // row.orders if row.orders > 0 else 0,
        "total_tax": row.tax,
        "total_discount": row.discount,
        "net_revenue": row.revenue - row.discount,
    }


async def get_sales_summary(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    date_from: date,
    date_to: date,
    compare: bool = False,
) -> dict:
    """Aggregate sales data for a date range.

    With `compare`, `previous` carries the same headline figures for the
    comparison period (see `comparison_periods`); otherwise it is None.
    """
    tz_name = await tenant_timezone(db, tenant_id)
    range_start, range_end = local_range_bounds_utc(tz_name, date_from, date_to)
    total_row = await sales_totals(db, tenant_id, range_start, range_end)

    previous = None
    if compare:
        periods = comparison_periods(tz_name, date_from, date_to)
        prev_row = await sales_totals(db, tenant_id, *periods["previous"])
        previous = {
            **_headline(prev_row),
            "date_from": periods["previous_from"].isoformat(),
            "date_to": periods["previous_to"].isoformat(),
            "cut_at": periods["previous_cut_at"],
        }

    # Per-channel breakdown
    channel_result = await db.execute(
        select(
            Order.order_type,
            func.coalesce(func.sum(Order.total), 0).label("revenue"),
            func.count(Order.id).label("orders"),
        )
        .where(*_sold(tenant_id, range_start, range_end))
        .group_by(Order.order_type)
    )
    channels = {
        r.order_type: {"revenue": r.revenue, "orders": r.orders}
        for r in channel_result.all()
    }

    # Discount breakdown by source_type
    disc_result = await db.execute(
        select(
            OrderDiscount.source_type,
            func.count(OrderDiscount.id).label("count"),
            func.coalesce(func.sum(OrderDiscount.amount), 0).label("total"),
        )
        .join(Order, OrderDiscount.order_id == Order.id)
        .where(
            OrderDiscount.tenant_id == tenant_id,
            Order.created_at >= range_start,
            Order.created_at < range_end,
            Order.status != "voided",
        )
        .group_by(OrderDiscount.source_type)
        .order_by(func.sum(OrderDiscount.amount).desc())
    )
    discount_breakdown = [
        {
            "source_type": r.source_type,
            "label": r.source_type.replace("_", " ").title(),
            "count": r.count,
            "total": r.total,
        }
        for r in disc_result.all()
    ]

    # Payment method revenue breakdown (cash vs card vs other)
    pm_revenue = await db.execute(
        select(
            PaymentMethod.code,
            func.coalesce(func.sum(Payment.amount), 0).label("total"),
        )
        .join(PaymentMethod, Payment.method_id == PaymentMethod.id)
        .where(
            Payment.tenant_id == tenant_id,
            Payment.kind == "payment",
            Payment.status == "completed",
            Payment.created_at >= range_start,
            Payment.created_at < range_end,
        )
        .group_by(PaymentMethod.code)
    )
    pm_map = {r.code: r.total for r in pm_revenue.all()}
    cash_revenue = pm_map.get("cash", 0)
    card_revenue = pm_map.get("card", 0)
    other_revenue = sum(v for k, v in pm_map.items() if k not in ("cash", "card"))

    return {
        **_headline(total_row),
        "previous": previous,
        "cash_revenue": cash_revenue,
        "card_revenue": card_revenue,
        "other_revenue": other_revenue,
        "dine_in_revenue": channels.get("dine_in", {}).get("revenue", 0),
        "dine_in_orders": channels.get("dine_in", {}).get("orders", 0),
        "takeaway_revenue": channels.get("takeaway", {}).get("revenue", 0),
        "takeaway_orders": channels.get("takeaway", {}).get("orders", 0),
        "call_center_revenue": channels.get("call_center", {}).get("revenue", 0),
        "call_center_orders": channels.get("call_center", {}).get("orders", 0),
        "online_revenue": channels.get("online", {}).get("revenue", 0),
        "online_orders": channels.get("online", {}).get("orders", 0),
        "discount_breakdown": discount_breakdown,
    }


async def get_item_performance(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    date_from: date,
    date_to: date,
    compare: bool = False,
) -> dict:
    """Get top/bottom items and category breakdown.

    Each item carries its menu photo (D-52) and, with `compare`, what it sold
    in the comparison period (D-55; None without `compare`, 0 when it sold
    nothing then).

    Bottom 5 is drawn only from items OUTSIDE the top 10 (D-54): on a quiet day
    with 13 items sold, Hot & Sour Soup was listed as a top AND a bottom
    performer. With 10 items or fewer there is no bottom list at all.
    """
    tz_name = await tenant_timezone(db, tenant_id)
    range_start, range_end = local_range_bounds_utc(tz_name, date_from, date_to)

    async def per_item(start: datetime, end: datetime) -> list:
        return (
            await db.execute(
                select(
                    OrderItem.menu_item_id,
                    OrderItem.name,
                    func.sum(OrderItem.quantity).label("qty"),
                    func.sum(OrderItem.total).label("revenue"),
                )
                .join(Order, OrderItem.order_id == Order.id)
                .where(*_sold(tenant_id, start, end))
                .group_by(OrderItem.menu_item_id, OrderItem.name)
                # Name breaks ties so the order is the same on every load.
                .order_by(func.sum(OrderItem.total).desc(), OrderItem.name)
            )
        ).all()

    rows = await per_item(range_start, range_end)

    previous: dict[str, tuple[int, int]] | None = None
    if compare:
        periods = comparison_periods(tz_name, date_from, date_to)
        previous = {}
        for r in await per_item(*periods["previous"]):
            qty, rev = previous.get(str(r.menu_item_id), (0, 0))
            previous[str(r.menu_item_id)] = (qty + r.qty, rev + r.revenue)

    ids = {r.menu_item_id for r in rows if r.menu_item_id is not None}
    images = (
        dict(
            (
                await db.execute(
                    select(MenuItem.id, MenuItem.image_url).where(
                        MenuItem.tenant_id == tenant_id, MenuItem.id.in_(ids)
                    )
                )
            ).all()
        )
        if ids
        else {}
    )

    def entry(r) -> dict:
        key = str(r.menu_item_id)
        prev = None if previous is None else previous.get(key, (0, 0))
        return {
            "menu_item_id": key,
            "name": r.name,
            "image_url": images.get(r.menu_item_id),
            "quantity_sold": r.qty,
            "revenue": r.revenue,
            "previous_quantity": None if prev is None else prev[0],
            "previous_revenue": None if prev is None else prev[1],
        }

    all_items = [entry(r) for r in rows]
    top_items = all_items[:10]
    bottom_items = list(reversed(all_items[10:][-5:]))

    # Category breakdown (using denormalized item names won't work for categories,
    # so we join through menu_items → categories)
    from app.models.menu import Category

    cat_stats = await db.execute(
        select(
            Category.name.label("category_name"),
            func.sum(OrderItem.total).label("revenue"),
            func.count(OrderItem.id).label("order_count"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .join(MenuItem, OrderItem.menu_item_id == MenuItem.id)
        .join(Category, MenuItem.category_id == Category.id)
        .where(*_sold(tenant_id, range_start, range_end))
        .group_by(Category.name)
        .order_by(func.sum(OrderItem.total).desc())
    )

    categories = [
        {
            "category_name": r.category_name,
            "revenue": r.revenue,
            "order_count": r.order_count,
        }
        for r in cat_stats.all()
    ]

    return {
        "top_items": top_items,
        "bottom_items": bottom_items,
        "categories": categories,
    }


async def get_hourly_breakdown(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    date_from: date,
    date_to: date | None = None,
) -> dict:
    """Order count and revenue per hour of the day, summed over a date range.

    The day and the hours are the restaurant's own. A UTC date cast and UTC
    `extract(hour)` put a 1 pm Faisalabad lunch in the 8 am bar, on the wrong
    day after midnight (Danny's UAT D-30).

    The range used to be one day only: the Reports page passed the start date
    alone, so "This Week" charted Monday and titled it as the week (D-53).
    """
    date_to = date_to or date_from
    tz_name = await tenant_timezone(db, tenant_id)
    day_start, day_end = local_range_bounds_utc(tz_name, date_from, date_to)
    result = await db.execute(
        select(Order.created_at, Order.total).where(*_sold(tenant_id, day_start, day_end))
    )

    tz = zone(tz_name)
    hour_data: dict[int, dict[str, int]] = {}
    for created_at, total in result.all():
        if created_at.tzinfo is None:  # SQLite hands back naive UTC
            created_at = created_at.replace(tzinfo=timezone.utc)
        hour = created_at.astimezone(tz).hour
        bucket = hour_data.setdefault(hour, {"order_count": 0, "revenue": 0})
        bucket["order_count"] += 1
        bucket["revenue"] += total or 0

    buckets = [
        {
            "hour": h,
            "order_count": hour_data.get(h, {}).get("order_count", 0),
            "revenue": hour_data.get(h, {}).get("revenue", 0),
        }
        for h in range(24)
    ]

    return {
        "date": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "buckets": buckets,
    }


# Below this many visits a size's "what they order" is noise, not a pattern.
TABLE_SIZE_MIN_VISITS = 5


async def get_table_size_report(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    date_from: date,
    date_to: date,
) -> dict:
    """Dine-in by table size (Danny's D-56): 4-seaters against 6-seaters.

    The unit is a VISIT (one table session), not an order: a table that orders
    starters, then mains, then dessert is one party spending one bill, and
    counting it as three orders would make every big table look cheap. An order
    with no session counts as its own visit.

    "What they order" is the share of visits that included each dish, with the
    counts behind it. Real figures only: below TABLE_SIZE_MIN_VISITS visits a
    size gets no item list (`enough_data` false), because two visits cannot
    show what 4-seaters "tend to" order.
    """
    tz_name = await tenant_timezone(db, tenant_id)
    start, end = local_range_bounds_utc(tz_name, date_from, date_to)
    visit_key = func.coalesce(Order.table_session_id, Order.id)
    where = [*_sold(tenant_id, start, end), Order.order_type == "dine_in", Order.table_id.is_not(None)]

    visits = (
        await db.execute(
            select(
                Table.capacity,
                func.count(func.distinct(visit_key)).label("visits"),
                func.count(Order.id).label("orders"),
                func.coalesce(func.sum(Order.total), 0).label("revenue"),
            )
            .join(Table, Order.table_id == Table.id)
            .where(*where)
            .group_by(Table.capacity)
            .order_by(Table.capacity)
        )
    ).all()

    dishes = (
        await db.execute(
            select(
                Table.capacity,
                OrderItem.name,
                func.count(func.distinct(visit_key)).label("visits_with"),
                func.sum(OrderItem.quantity).label("qty"),
            )
            .join(Order, OrderItem.order_id == Order.id)
            .join(Table, Order.table_id == Table.id)
            .where(*where)
            .group_by(Table.capacity, OrderItem.name)
        )
    ).all()

    by_size: dict[int, list] = {}
    for d in dishes:
        by_size.setdefault(d.capacity, []).append(d)

    sizes = []
    for v in visits:
        enough = v.visits >= TABLE_SIZE_MIN_VISITS
        top = sorted(
            by_size.get(v.capacity, []), key=lambda d: (-d.visits_with, -d.qty, d.name)
        )[:5]
        sizes.append(
            {
                "capacity": v.capacity,
                "visits": v.visits,
                "orders": v.orders,
                "revenue": v.revenue,
                "avg_per_visit": v.revenue // v.visits if v.visits else 0,
                "enough_data": enough,
                "top_items": [
                    {
                        "name": d.name,
                        "visits_with": d.visits_with,
                        "quantity": d.qty,
                        "share_pct": round(d.visits_with * 100 / v.visits),
                    }
                    for d in top
                ]
                if enough
                else [],
            }
        )

    return {"min_visits": TABLE_SIZE_MIN_VISITS, "sizes": sizes}


async def get_void_report(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    date_from: date,
    date_to: date,
) -> dict:
    """Aggregate void data: counts, values, breakdown by reason and user."""
    range_start, range_end = await tenant_range_utc(db, tenant_id, date_from, date_to)
    # Base: all voided orders in date range
    voided_orders = (
        select(
            Order.id,
            Order.total,
        ).where(
            Order.tenant_id == tenant_id,
            Order.status == "voided",
            Order.created_at >= range_start,
            Order.created_at < range_end,
        )
    ).subquery()

    # Totals
    totals_result = await db.execute(
        select(
            func.count(voided_orders.c.id).label("count"),
            func.coalesce(func.sum(voided_orders.c.total), 0).label("value"),
        )
    )
    totals = totals_result.one()

    # By reason (from status log)
    reason_label = func.coalesce(OrderStatusLog.note, "No reason provided")
    reason_result = await db.execute(
        select(
            reason_label.label("reason"),
            func.count(OrderStatusLog.id).label("count"),
            func.coalesce(func.sum(Order.total), 0).label("total_value"),
        )
        .join(Order, OrderStatusLog.order_id == Order.id)
        .where(
            OrderStatusLog.tenant_id == tenant_id,
            OrderStatusLog.to_status == "voided",
            Order.created_at >= range_start,
            Order.created_at < range_end,
        )
        .group_by(reason_label)
        .order_by(func.count(OrderStatusLog.id).desc())
    )
    by_reason = [
        {"reason": r.reason, "count": r.count, "total_value": r.total_value}
        for r in reason_result.all()
    ]

    # By user who voided
    user_result = await db.execute(
        select(
            User.id.label("user_id"),
            User.full_name.label("user_name"),
            func.count(OrderStatusLog.id).label("count"),
            func.coalesce(func.sum(Order.total), 0).label("total_value"),
        )
        .join(Order, OrderStatusLog.order_id == Order.id)
        .join(User, OrderStatusLog.changed_by == User.id)
        .where(
            OrderStatusLog.tenant_id == tenant_id,
            OrderStatusLog.to_status == "voided",
            Order.created_at >= range_start,
            Order.created_at < range_end,
        )
        .group_by(User.id, User.full_name)
        .order_by(func.count(OrderStatusLog.id).desc())
    )
    by_user = [
        {
            "user_id": str(r.user_id),
            "user_name": r.user_name,
            "count": r.count,
            "total_value": r.total_value,
        }
        for r in user_result.all()
    ]

    return {
        "total_voids": totals.count,
        "total_voided_value": totals.value,
        "by_reason": by_reason,
        "by_user": by_user,
    }


async def get_payment_method_report(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    date_from: date,
    date_to: date,
) -> dict:
    """Payment-mode daily sales: breakdown by payment method for a date range."""
    range_start, range_end = await tenant_range_utc(db, tenant_id, date_from, date_to)
    result = await db.execute(
        select(
            PaymentMethod.display_name.label("method"),
            PaymentMethod.code.label("method_code"),
            func.count(Payment.id).label("count"),
            func.coalesce(func.sum(Payment.amount), 0).label("total"),
        )
        .join(PaymentMethod, Payment.method_id == PaymentMethod.id)
        .where(
            Payment.tenant_id == tenant_id,
            Payment.kind == "payment",
            Payment.status == "completed",
            Payment.created_at >= range_start,
            Payment.created_at < range_end,
        )
        .group_by(PaymentMethod.display_name, PaymentMethod.code)
        .order_by(func.sum(Payment.amount).desc())
    )
    rows = result.all()
    entries = [
        {
            "method": r.method,
            "method_code": r.method_code,
            "count": r.count,
            "total": r.total,
        }
        for r in rows
    ]
    total_collected = sum(e["total"] for e in entries)

    return {"entries": entries, "total_collected": total_collected}


async def get_waiter_performance(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    date_from: date,
    date_to: date,
) -> dict:
    """Waiter performance: orders, revenue, avg order value per waiter."""
    range_start, range_end = await tenant_range_utc(db, tenant_id, date_from, date_to)
    # Orders with a waiter assigned
    result = await db.execute(
        select(
            User.id.label("waiter_id"),
            User.full_name.label("waiter_name"),
            func.count(Order.id).label("order_count"),
            func.coalesce(func.sum(Order.total), 0).label("total_revenue"),
        )
        .join(User, Order.waiter_id == User.id)
        .where(
            Order.tenant_id == tenant_id,
            Order.status != "voided",
            Order.created_at >= range_start,
            Order.created_at < range_end,
        )
        .group_by(User.id, User.full_name)
        .order_by(func.sum(Order.total).desc())
    )
    rows = result.all()

    entries = [
        {
            "waiter_id": str(r.waiter_id),
            "waiter_name": r.waiter_name,
            "order_count": r.order_count,
            "total_revenue": r.total_revenue,
            "avg_order_value": r.total_revenue // r.order_count if r.order_count else 0,
        }
        for r in rows
    ]

    # Count orders without waiter
    no_waiter_result = await db.execute(
        select(func.count(Order.id)).where(
            Order.tenant_id == tenant_id,
            Order.status != "voided",
            Order.waiter_id.is_(None),
            Order.created_at >= range_start,
            Order.created_at < range_end,
        )
    )
    total_without = no_waiter_result.scalar_one()
    total_with = sum(e["order_count"] for e in entries)

    return {
        "entries": entries,
        "total_orders_with_waiter": total_with,
        "total_orders_without_waiter": total_without,
    }
