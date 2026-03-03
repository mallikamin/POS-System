"""Report service -- sales summaries, item performance, hourly breakdown."""

import uuid
from datetime import date

from sqlalchemy import Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discount import OrderDiscount
from app.models.order import Order, OrderItem


async def get_sales_summary(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    date_from: date,
    date_to: date,
) -> dict:
    """Aggregate sales data for a date range."""
    base = select(
        func.coalesce(func.sum(Order.total), 0).label("revenue"),
        func.count(Order.id).label("orders"),
        func.coalesce(func.sum(Order.tax_amount), 0).label("tax"),
        func.coalesce(func.sum(Order.discount_amount), 0).label("discount"),
    ).where(
        Order.tenant_id == tenant_id,
        func.cast(Order.created_at, Date) >= date_from,
        func.cast(Order.created_at, Date) <= date_to,
        Order.status != "voided",
    )

    total_row = (await db.execute(base)).one()

    # Per-channel breakdown
    channel_result = await db.execute(
        select(
            Order.order_type,
            func.coalesce(func.sum(Order.total), 0).label("revenue"),
            func.count(Order.id).label("orders"),
        ).where(
            Order.tenant_id == tenant_id,
            func.cast(Order.created_at, Date) >= date_from,
            func.cast(Order.created_at, Date) <= date_to,
            Order.status != "voided",
        ).group_by(Order.order_type)
    )
    channels = {r.order_type: {"revenue": r.revenue, "orders": r.orders} for r in channel_result.all()}

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
            func.cast(Order.created_at, Date) >= date_from,
            func.cast(Order.created_at, Date) <= date_to,
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

    total_orders = total_row.orders
    total_revenue = total_row.revenue
    total_discount = total_row.discount
    return {
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "avg_order_value": total_revenue // total_orders if total_orders > 0 else 0,
        "total_tax": total_row.tax,
        "total_discount": total_discount,
        "net_revenue": total_revenue - total_discount,
        "dine_in_revenue": channels.get("dine_in", {}).get("revenue", 0),
        "dine_in_orders": channels.get("dine_in", {}).get("orders", 0),
        "takeaway_revenue": channels.get("takeaway", {}).get("revenue", 0),
        "takeaway_orders": channels.get("takeaway", {}).get("orders", 0),
        "call_center_revenue": channels.get("call_center", {}).get("revenue", 0),
        "call_center_orders": channels.get("call_center", {}).get("orders", 0),
        "discount_breakdown": discount_breakdown,
    }


async def get_item_performance(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    date_from: date,
    date_to: date,
) -> dict:
    """Get top/bottom items and category breakdown."""
    # Top items by revenue
    item_stats = await db.execute(
        select(
            OrderItem.menu_item_id,
            OrderItem.name,
            func.sum(OrderItem.quantity).label("qty"),
            func.sum(OrderItem.total).label("revenue"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .where(
            Order.tenant_id == tenant_id,
            func.cast(Order.created_at, Date) >= date_from,
            func.cast(Order.created_at, Date) <= date_to,
            Order.status != "voided",
        )
        .group_by(OrderItem.menu_item_id, OrderItem.name)
        .order_by(func.sum(OrderItem.total).desc())
    )
    all_items = [
        {
            "menu_item_id": str(r.menu_item_id),
            "name": r.name,
            "quantity_sold": r.qty,
            "revenue": r.revenue,
        }
        for r in item_stats.all()
    ]

    top_items = all_items[:10]
    bottom_items = list(reversed(all_items[-5:])) if len(all_items) > 5 else []

    # Category breakdown (using denormalized item names won't work for categories,
    # so we join through menu_items → categories)
    from app.models.menu import Category, MenuItem

    cat_stats = await db.execute(
        select(
            Category.name.label("category_name"),
            func.sum(OrderItem.total).label("revenue"),
            func.count(OrderItem.id).label("order_count"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .join(MenuItem, OrderItem.menu_item_id == MenuItem.id)
        .join(Category, MenuItem.category_id == Category.id)
        .where(
            Order.tenant_id == tenant_id,
            func.cast(Order.created_at, Date) >= date_from,
            func.cast(Order.created_at, Date) <= date_to,
            Order.status != "voided",
        )
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
    target_date: date,
) -> dict:
    """Get order count and revenue per hour for a given date."""
    result = await db.execute(
        select(
            func.extract("hour", Order.created_at).label("hour"),
            func.count(Order.id).label("order_count"),
            func.coalesce(func.sum(Order.total), 0).label("revenue"),
        ).where(
            Order.tenant_id == tenant_id,
            func.cast(Order.created_at, Date) == target_date,
            Order.status != "voided",
        ).group_by(func.extract("hour", Order.created_at))
        .order_by(func.extract("hour", Order.created_at))
    )

    hour_data = {int(r.hour): {"order_count": r.order_count, "revenue": r.revenue} for r in result.all()}

    buckets = [
        {
            "hour": h,
            "order_count": hour_data.get(h, {}).get("order_count", 0),
            "revenue": hour_data.get(h, {}).get("revenue", 0),
        }
        for h in range(24)
    ]

    return {"date": target_date.isoformat(), "buckets": buckets}
