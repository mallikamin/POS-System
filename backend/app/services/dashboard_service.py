"""Dashboard service -- real-time KPIs and live operations."""

import uuid
from datetime import date, timedelta

from sqlalchemy import Date, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floor import Table
from app.models.order import Order


async def get_dashboard_kpis(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Get today's dashboard KPI data."""
    today = date.today()
    yesterday = today - timedelta(days=1)

    # Today's revenue and order count (non-voided)
    today_stats = await db.execute(
        select(
            func.coalesce(func.sum(Order.total), 0).label("revenue"),
            func.count(Order.id).label("orders"),
        ).where(
            Order.tenant_id == tenant_id,
            func.cast(Order.created_at, Date) == today,
            Order.status != "voided",
        )
    )
    row = today_stats.one()
    today_revenue = row.revenue
    today_orders = row.orders

    # Yesterday's revenue
    yest_stats = await db.execute(
        select(
            func.coalesce(func.sum(Order.total), 0),
        ).where(
            Order.tenant_id == tenant_id,
            func.cast(Order.created_at, Date) == yesterday,
            Order.status != "voided",
        )
    )
    yesterday_revenue = yest_stats.scalar_one()

    avg_order_value = today_revenue // today_orders if today_orders > 0 else 0

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
            "item_count": len(o.items),
            "total": o.total,
            "created_at": o.created_at.isoformat(),
        }

    return {
        "dine_in": [to_live_item(o) for o in orders if o.order_type == "dine_in"],
        "takeaway": [to_live_item(o) for o in orders if o.order_type == "takeaway"],
        "call_center": [
            to_live_item(o) for o in orders if o.order_type == "call_center"
        ],
    }
