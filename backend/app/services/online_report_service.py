"""OI-58: report queries specific to online-ordering tenants.

Deliberately a new module rather than an addition to `report_service.py`:
these date filters use plain `Order.created_at >= / <` datetime-range
comparisons, never `func.cast(Order.created_at, Date)`. See `ERROR_LOG.md`
2026-08-01 -- that CAST pattern is silently unverifiable by this project's
SQLite test DB (it truncates to an integer year and can never compare true
against a date bound), and while production Postgres handles it correctly,
there's no reason for new code to inherit a landmine that's already caused
one blind spot. A plain range comparison is correct and testable on both.

Daily Orders/Sales intentionally has no function here -- OI-58a already
fixed `report_service.get_sales_summary` to expose `online_revenue` /
`online_orders`, so the frontend calls that existing endpoint directly
rather than this module duplicating it.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.services import stripe_service
from app.services.order_visibility import is_real_order, money_actually_taken


def _range_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    """[start, end) UTC bounds spanning `date_from` through `date_to` inclusive."""
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to, time.min, tzinfo=timezone.utc) + timedelta(days=1)
    return start, end


async def get_prepaid_vs_cod(
    db: AsyncSession, tenant_id: uuid.UUID, date_from: date, date_to: date
) -> dict:
    """Online orders bucketed by whether the money was actually taken up front.

    Prepaid = `payment_captured_at IS NOT NULL`, i.e. the shop has the money.
    Everything else real is cash on delivery. Voided orders are excluded, and
    so is any card order Stripe never approved -- it is not an order at all
    (see `is_real_order`), so it must not appear in revenue any more than it
    appears on the tablet.
    """
    start, end = _range_bounds(date_from, date_to)
    # Prepaid means the money is IN, not that the customer opened a card page.
    # The old definition (`stripe_checkout_session_id IS NOT NULL`) counted a
    # session created the instant the customer was sent to Stripe -- so an
    # abandoned checkout was reported as prepaid revenue. That is exactly what
    # overstated the client's own reports screen on 2026-08-04 (order
    # 260804-002, £62.92 never taken, shown as prepaid).
    is_prepaid = money_actually_taken()

    stmt = select(
        func.coalesce(func.sum(case((is_prepaid, Order.total), else_=0)), 0).label(
            "prepaid_revenue"
        ),
        func.count(case((is_prepaid, Order.id))).label("prepaid_orders"),
        func.coalesce(func.sum(case((~is_prepaid, Order.total), else_=0)), 0).label(
            "cod_revenue"
        ),
        func.count(case((~is_prepaid, Order.id))).label("cod_orders"),
    ).where(
        Order.tenant_id == tenant_id,
        Order.order_type == "online",
        Order.status != "voided",
        is_real_order(),
        Order.created_at >= start,
        Order.created_at < end,
    )
    row = (await db.execute(stmt)).one()

    return {
        "date_from": date_from,
        "date_to": date_to,
        "prepaid_revenue": row.prepaid_revenue,
        "prepaid_orders": row.prepaid_orders,
        "cod_revenue": row.cod_revenue,
        "cod_orders": row.cod_orders,
    }


async def get_rejected_orders(
    db: AsyncSession, tenant_id: uuid.UUID, date_from: date, date_to: date
) -> dict:
    """Online orders the shop explicitly rejected, scoped by when they were
    rejected (not when they were placed) -- "rejected orders this week"
    means rejected this week, regardless of how old the order was.

    A dedicated query on `Order.rejected_at`/`rejection_reason`, not a
    retrofit of the general void report: that report's `by_reason` breakdown
    reads `OrderStatusLog.note`, which `reject_order` never sets, so it would
    show "No reason provided" for every row. The real reason already sits on
    `Order.rejection_reason`, unread.
    """
    start, end = _range_bounds(date_from, date_to)
    stmt = (
        select(Order)
        .where(
            Order.tenant_id == tenant_id,
            Order.order_type == "online",
            Order.rejected_at.is_not(None),
            Order.rejected_at >= start,
            Order.rejected_at < end,
        )
        .order_by(Order.rejected_at.desc())
    )
    orders = (await db.execute(stmt)).scalars().all()

    return {
        "date_from": date_from,
        "date_to": date_to,
        "count": len(orders),
        "total_value": sum(o.total for o in orders),
        "orders": [
            {
                "order_number": o.order_number,
                "customer_name": o.customer_name,
                "rejected_at": o.rejected_at,
                "rejection_reason": o.rejection_reason or "No reason provided",
                "total": o.total,
            }
            for o in orders
        ],
    }


async def get_stripe_reconciliation(
    db: AsyncSession, tenant_id: uuid.UUID, date_from: date, date_to: date
) -> dict:
    """Diff our own DB against Stripe's own record, order by order.

    Deliberately `PaymentIntent.retrieve` per order rather than a blind
    account-wide `PaymentIntent.list` -- the latter isn't tenant-scoped and
    would mix in any other Stripe account activity. This is the same manual
    check already done by hand for OI-41, made repeatable. Read-only: it
    never captures, cancels, or otherwise mutates anything in Stripe.

    A single order's Stripe lookup failing (network blip, deleted intent)
    is reported as an error row rather than failing the whole report -- one
    bad row shouldn't hide the reconciliation status of every other order.
    """
    start, end = _range_bounds(date_from, date_to)
    stmt = (
        select(Order)
        .where(
            Order.tenant_id == tenant_id,
            Order.order_type == "online",
            Order.stripe_payment_intent_id.is_not(None),
            Order.created_at >= start,
            Order.created_at < end,
        )
        .order_by(Order.created_at.asc())
    )
    orders = (await db.execute(stmt)).scalars().all()

    rows = []
    mismatches = 0
    for o in orders:
        db_captured_amount = o.total if o.payment_captured_at else 0
        row = {
            "order_number": o.order_number,
            "db_payment_status": o.payment_status,
            "db_captured_amount": db_captured_amount,
            "stripe_status": None,
            "stripe_amount_received": None,
            "matches": False,
            "error": None,
        }
        try:
            intent = await stripe_service.retrieve_payment_intent(
                o.stripe_payment_intent_id  # type: ignore[arg-type]
            )
        except stripe_service.StripeError as exc:
            row["error"] = str(exc)
            mismatches += 1
            rows.append(row)
            continue

        row["stripe_status"] = intent["status"]
        row["stripe_amount_received"] = intent["amount_received"]
        row["matches"] = intent["amount_received"] == db_captured_amount
        if not row["matches"]:
            mismatches += 1
        rows.append(row)

    return {
        "date_from": date_from,
        "date_to": date_to,
        "checked": len(rows),
        "mismatches": mismatches,
        "rows": rows,
    }
