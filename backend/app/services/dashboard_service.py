"""Dashboard service -- real-time KPIs and live operations."""

import uuid
from datetime import timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floor import Table
from app.models.order import Order
from app.services import report_service
from app.services.report_service import comparison_periods
from app.utils.tenant_time import local_day_bounds_utc, local_today, tenant_timezone


async def get_dashboard_kpis(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Get today's dashboard KPI data.

    "Today" is the restaurant's own day. A UTC date cast showed a Pakistani
    owner the previous afternoon's takings as today's until 5 am (D-30).
    """
    tz_name = await tenant_timezone(db, tenant_id)
    today = local_today(tz_name)

    # Same query and same "real order" rule as the Reports page, so the two
    # screens cannot show different takings for the same day.
    periods = comparison_periods(tz_name, today, today)
    row = await report_service.sales_totals(db, tenant_id, *periods["current"])
    today_revenue = row.revenue
    today_orders = row.orders
    avg_order_value = today_revenue // today_orders if today_orders > 0 else 0

    # D-55: yesterday up to the same clock time, not all of yesterday, so at
    # 2 am the card does not read "down 100%".
    same = await report_service.sales_totals(db, tenant_id, *periods["previous"])
    yest_start, yest_end = local_day_bounds_utc(tz_name, today - timedelta(days=1))
    yesterday_revenue = (await report_service.sales_totals(db, tenant_id, yest_start, yest_end)).revenue

    # Table utilization
    table_counts = await db.execute(
        select(
            func.count(Table.id).label("total"),
            func.count(case((Table.status == "occupied", Table.id))).label("occupied"),
        ).where(
            Table.tenant_id == tenant_id,
            Table.is_active == True,  # noqa: E712
        )
    )
    t_row = table_counts.one()
    utilization = t_row.occupied / t_row.total if t_row.total > 0 else 0.0

    # Active and kitchen counts
    active_result = await db.execute(
        select(
            func.count(Order.id).label("active"),
            func.count(case((Order.status == "in_kitchen", Order.id))).label("kitchen"),
        ).where(
            Order.tenant_id == tenant_id,
            Order.status.in_(["confirmed", "in_kitchen", "ready", "served"]),
        )
    )
    a_row = active_result.one()

    return {
        "today_revenue": today_revenue,
        "yesterday_revenue": yesterday_revenue,
        "today_orders": today_orders,
        "avg_order_value": avg_order_value,
        "yesterday_same_time_revenue": same.revenue,
        "yesterday_same_time_orders": same.orders,
        "yesterday_same_time_avg_order_value": same.revenue // same.orders if same.orders else 0,
        "compared_until": periods["previous_cut_at"],
        "table_utilization": round(utilization, 2),
        "active_orders": a_row.active,
        "pending_kitchen": a_row.kitchen,
    }


async def get_live_operations(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Get active orders grouped by channel for live operations view."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.table))
        .where(
            Order.tenant_id == tenant_id,
            Order.status.in_(["confirmed", "in_kitchen", "ready", "served"]),
        )
        .order_by(Order.created_at.asc())
    )
    orders = result.scalars().unique().all()

    def to_live_item(o: Order) -> dict:
        return {
            "id": str(o.id),
            "order_number": o.order_number,
            "order_type": o.order_type,
            "status": o.status,
            "table_id": str(o.table_id) if o.table_id else None,
            "table_number": o.table.number if o.table else None,
            "customer_name": o.customer_name,
            "customer_phone": o.customer_phone,
            "item_count": sum(i.quantity for i in o.items),
            "total": o.total,
            "created_at": o.created_at.isoformat(),
        }

    return {
        "dine_in": [to_live_item(o) for o in orders if o.order_type == "dine_in"],
        "takeaway": [to_live_item(o) for o in orders if o.order_type == "takeaway"],
        "call_center": [
            to_live_item(o) for o in orders if o.order_type == "call_center"
        ],
        "online": [to_live_item(o) for o in orders if o.order_type == "online"],
    }
