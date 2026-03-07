"""Report service -- sales summaries, item performance, hourly breakdown."""

import uuid
from datetime import date

from sqlalchemy import Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discount import OrderDiscount
from app.models.order import Order, OrderItem, OrderStatusLog
from app.models.payment import Payment, PaymentMethod
from app.models.user import User


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
            func.cast(Payment.created_at, Date) >= date_from,
            func.cast(Payment.created_at, Date) <= date_to,
        )
        .group_by(PaymentMethod.code)
    )
    pm_map = {r.code: r.total for r in pm_revenue.all()}
    cash_revenue = pm_map.get("cash", 0)
    card_revenue = pm_map.get("card", 0)
    other_revenue = sum(v for k, v in pm_map.items() if k not in ("cash", "card"))

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
        "cash_revenue": cash_revenue,
        "card_revenue": card_revenue,
        "other_revenue": other_revenue,
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


async def get_void_report(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    date_from: date,
    date_to: date,
) -> dict:
    """Aggregate void data: counts, values, breakdown by reason and user."""
    # Base: all voided orders in date range
    voided_orders = (
        select(
            Order.id,
            Order.total,
        )
        .where(
            Order.tenant_id == tenant_id,
            Order.status == "voided",
            func.cast(Order.created_at, Date) >= date_from,
            func.cast(Order.created_at, Date) <= date_to,
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
            func.cast(Order.created_at, Date) >= date_from,
            func.cast(Order.created_at, Date) <= date_to,
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
            func.cast(Order.created_at, Date) >= date_from,
            func.cast(Order.created_at, Date) <= date_to,
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
            func.cast(Payment.created_at, Date) >= date_from,
            func.cast(Payment.created_at, Date) <= date_to,
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
            func.cast(Order.created_at, Date) >= date_from,
            func.cast(Order.created_at, Date) <= date_to,
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
            func.cast(Order.created_at, Date) >= date_from,
            func.cast(Order.created_at, Date) <= date_to,
        )
    )
    total_without = no_waiter_result.scalar_one()
    total_with = sum(e["order_count"] for e in entries)

    return {
        "entries": entries,
        "total_orders_with_waiter": total_with,
        "total_orders_without_waiter": total_without,
    }
