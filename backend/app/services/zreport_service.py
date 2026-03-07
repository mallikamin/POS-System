"""Z-Report / Daily Settlement service -- assembles end-of-day report data."""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discount import OrderDiscount
from app.models.order import Order, OrderItem
from app.models.payment import CashDrawerSession, Payment, PaymentMethod


async def generate_zreport(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    target_date: date,
    generated_by: str,
) -> dict:
    """Assemble a complete Z-Report for a given date."""
    date_filter = func.cast(Order.created_at, Date) == target_date

    # --- Sales totals ---
    totals = (
        await db.execute(
            select(
                func.count(Order.id).label("orders"),
                func.coalesce(func.sum(Order.total), 0).label("revenue"),
                func.coalesce(func.sum(Order.tax_amount), 0).label("tax"),
                func.coalesce(func.sum(Order.discount_amount), 0).label("discount"),
            ).where(
                Order.tenant_id == tenant_id,
                date_filter,
                Order.status.notin_(["draft", "voided"]),
            )
        )
    ).one()

    # --- By channel ---
    channel_rows = (
        await db.execute(
            select(
                Order.order_type,
                func.count(Order.id).label("orders"),
                func.coalesce(func.sum(Order.total), 0).label("revenue"),
            )
            .where(
                Order.tenant_id == tenant_id,
                date_filter,
                Order.status.notin_(["draft", "voided"]),
            )
            .group_by(Order.order_type)
        )
    ).all()

    # --- By status ---
    status_rows = (
        await db.execute(
            select(
                Order.status,
                func.count(Order.id).label("count"),
            )
            .where(Order.tenant_id == tenant_id, date_filter)
            .group_by(Order.status)
        )
    ).all()

    # --- By payment method ---
    pm_rows = (
        await db.execute(
            select(
                PaymentMethod.display_name,
                func.coalesce(
                    func.sum(case((Payment.kind == "payment", 1), else_=0)), 0
                ).label("payment_count"),
                func.coalesce(
                    func.sum(case((Payment.kind == "refund", 1), else_=0)), 0
                ).label("refund_count"),
                func.coalesce(
                    func.sum(
                        case((Payment.kind == "payment", Payment.amount), else_=0)
                    ),
                    0,
                ).label("gross_total"),
                func.coalesce(
                    func.sum(
                        case((Payment.kind == "refund", Payment.amount), else_=0)
                    ),
                    0,
                ).label("refund_total"),
            )
            .join(PaymentMethod, Payment.method_id == PaymentMethod.id)
            .where(
                Payment.tenant_id == tenant_id,
                Payment.kind.in_(["payment", "refund"]),
                Payment.status == "completed",
                func.cast(Payment.created_at, Date) == target_date,
            )
            .group_by(PaymentMethod.display_name)
            .order_by(PaymentMethod.display_name)
        )
    ).all()

    # --- Settlement summary (transaction-date based) ---
    settlement_rows = (
        await db.execute(
            select(
                Payment.order_id,
                Order.payment_status,
                Order.total,
                Order.tax_amount,
                Payment.kind,
                Payment.amount,
            )
            .join(Order, Payment.order_id == Order.id)
            .where(
                Payment.tenant_id == tenant_id,
                Payment.status == "completed",
                Payment.kind.in_(["payment", "refund"]),
                func.cast(Payment.created_at, Date) == target_date,
                Order.tenant_id == tenant_id,
                Order.status.notin_(["draft", "voided"]),
            )
        )
    ).all()

    settlement_by_order: dict[uuid.UUID, dict[str, int | str]] = {}
    for row in settlement_rows:
        entry = settlement_by_order.setdefault(
            row.order_id,
            {
                "payment_status": row.payment_status,
                "order_total": row.total,
                "tax_amount": row.tax_amount,
                "payments": 0,
                "refunds": 0,
            },
        )
        entry["payment_status"] = row.payment_status
        if row.kind == "payment":
            entry["payments"] = int(entry["payments"]) + row.amount
        else:
            entry["refunds"] = int(entry["refunds"]) + row.amount

    settled_orders = 0
    fully_refunded_orders = 0
    net_revenue = 0
    net_tax = 0
    for entry in settlement_by_order.values():
        payment_status = str(entry["payment_status"])
        if payment_status == "paid":
            settled_orders += 1
        elif payment_status == "refunded":
            fully_refunded_orders += 1

        net_amount = int(entry["payments"]) - int(entry["refunds"])
        net_revenue += net_amount
        net_tax += _proportional_amount(
            int(entry["tax_amount"]),
            net_amount,
            int(entry["order_total"]),
        )

    # --- Top 10 items ---
    item_rows = (
        await db.execute(
            select(
                OrderItem.name,
                func.sum(OrderItem.quantity).label("qty"),
                func.sum(OrderItem.total).label("revenue"),
            )
            .join(Order, OrderItem.order_id == Order.id)
            .where(
                Order.tenant_id == tenant_id,
                date_filter,
                Order.status.notin_(["draft", "voided"]),
            )
            .group_by(OrderItem.name)
            .order_by(func.sum(OrderItem.total).desc())
            .limit(10)
        )
    ).all()

    # --- Cash drawer session for the date ---
    drawer_result = await db.execute(
        select(CashDrawerSession)
        .where(
            CashDrawerSession.tenant_id == tenant_id,
            func.cast(CashDrawerSession.opened_at, Date) == target_date,
        )
        .order_by(CashDrawerSession.opened_at.desc())
        .limit(1)
    )
    drawer_session = drawer_result.scalar_one_or_none()

    drawer_data = None
    if drawer_session:
        # Calculate cash movements for this session
        cash_payments = (
            (
                await db.execute(
                    select(Payment)
                    .join(PaymentMethod, Payment.method_id == PaymentMethod.id)
                    .where(
                        Payment.tenant_id == tenant_id,
                        PaymentMethod.code == "cash",
                        Payment.status == "completed",
                        Payment.created_at >= drawer_session.opened_at,
                        Payment.created_at
                        <= (
                            drawer_session.closed_at
                            if drawer_session.closed_at
                            else func.now()
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )

        cash_in = sum(p.amount for p in cash_payments if p.kind == "payment")
        cash_out_change = sum(
            (p.change_amount or 0) for p in cash_payments if p.kind == "payment"
        )
        cash_out_refund = sum(p.amount for p in cash_payments if p.kind == "refund")
        expected = (
            drawer_session.opening_float + cash_in - cash_out_change - cash_out_refund
        )

        drawer_data = {
            "opening_float": drawer_session.opening_float,
            "cash_in": cash_in,
            "cash_out_change": cash_out_change,
            "cash_out_refund": cash_out_refund,
            "expected_balance": expected,
            "counted_balance": drawer_session.closing_balance_counted,
            "variance": (
                (drawer_session.closing_balance_counted - expected)
                if drawer_session.closing_balance_counted is not None
                else None
            ),
            "session_status": drawer_session.status,
        }

    # --- Discount breakdown by source_type ---
    disc_rows = (
        await db.execute(
            select(
                OrderDiscount.source_type,
                func.count(OrderDiscount.id).label("count"),
                func.coalesce(func.sum(OrderDiscount.amount), 0).label("total"),
            )
            .join(Order, OrderDiscount.order_id == Order.id)
            .where(
                OrderDiscount.tenant_id == tenant_id,
                date_filter,
                Order.status.notin_(["draft", "voided"]),
            )
            .group_by(OrderDiscount.source_type)
            .order_by(func.sum(OrderDiscount.amount).desc())
        )
    ).all()

    return {
        "date": target_date,
        "generated_at": datetime.now(timezone.utc),
        "generated_by": generated_by,
        "drawer": drawer_data,
        "total_orders": totals.orders,
        "total_revenue": totals.revenue,
        "total_tax": totals.tax,
        "total_discount": totals.discount,
        "net_revenue": net_revenue,
        "settled_orders": settled_orders,
        "fully_refunded_orders": fully_refunded_orders,
        "net_tax": net_tax,
        "by_channel": [
            {"channel": r.order_type, "orders": r.orders, "revenue": r.revenue}
            for r in channel_rows
        ],
        "by_payment_method": [
            {
                "method": r.display_name,
                "count": r.payment_count,
                "total": r.gross_total - r.refund_total,
                "payment_count": r.payment_count,
                "refund_count": r.refund_count,
                "gross_total": r.gross_total,
                "refund_total": r.refund_total,
                "net_total": r.gross_total - r.refund_total,
            }
            for r in pm_rows
        ],
        "by_status": [{"status": r.status, "count": r.count} for r in status_rows],
        "top_items": [
            {"name": r.name, "quantity": r.qty, "revenue": r.revenue} for r in item_rows
        ],
        "discount_breakdown": [
            {
                "source_type": r.source_type,
                "label": r.source_type.replace("_", " ").title(),
                "count": r.count,
                "total": r.total,
            }
            for r in disc_rows
        ],
    }


def _proportional_amount(base_amount: int, partial_amount: int, total_amount: int) -> int:
    if base_amount == 0 or partial_amount == 0 or total_amount <= 0:
        return 0

    sign = -1 if partial_amount < 0 else 1
    scaled = base_amount * abs(partial_amount)
    return sign * ((scaled + (total_amount // 2)) // total_amount)
