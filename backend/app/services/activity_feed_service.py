"""The owner's live feed (Danny's D-57): what just happened, where, for how much.

    "Tree House, Table 1 settled the bill: Rs 14,300 cash"
    "Hall 1, Table 4 placed an order: 3 items, Rs 4,200"
    "Hall 2, Table 3 order went to the kitchen"

Built only from what the system already records: every order status change
writes an `OrderStatusLog` row, every payment a `Payment` row. The sentences are
fixed templates filled with those facts; nothing is generated or guessed. The
feed covers the restaurant's own day, newest first.

Two pieces of noise are dropped on purpose:
  * an order-first POS order is written as `confirmed` and moved to `in_kitchen`
    in the same request, so "went to the kitchen" a second after "placed an
    order" says nothing new;
  * a dine-in order that completes because its bill was paid would repeat the
    payment line, so `completed` is shown only for orders nobody paid at the
    table (takeaway, call centre, online).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floor import Floor, Table
from app.models.order import Order, OrderItem, OrderStatusLog
from app.models.payment import Payment, PaymentMethod
from app.utils.tenant_time import local_day_bounds_utc, local_today, tenant_timezone

# The same-request kitchen hop is well under this; a real later hop is not.
_SAME_REQUEST = timedelta(seconds=5)

_STATUS_TEXT = {
    "in_kitchen": "order went to the kitchen",
    "ready": "order is ready to serve",
    "served": "order served",
    "completed": "order completed",
    "voided": "order voided",
}

_CHANNEL = {
    "takeaway": "Takeaway",
    "call_center": "Call centre",
    "online": "Online",
}


def _aware(at: datetime) -> datetime:
    """SQLite hands back naive UTC."""
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def _where(order: Order, table: Table | None, floor_name: str | None) -> str:
    if order.order_type == "dine_in" and table is not None:
        name = table.label or f"Table {table.number}"
        return f"{floor_name}, {name}" if floor_name else name
    channel = _CHANNEL.get(order.order_type, order.order_type.replace("_", " ").title())
    who = order.customer_name
    return f"{channel} #{order.order_number}" + (f" ({who})" if who else "")


async def get_activity_feed(
    db: AsyncSession, tenant_id: uuid.UUID, limit: int = 40
) -> dict:
    tz_name = await tenant_timezone(db, tenant_id)
    today = local_today(tz_name)
    start, end = local_day_bounds_utc(tz_name, today)

    # --- status changes -----------------------------------------------------
    logs = (
        await db.execute(
            select(OrderStatusLog, Order, Table, Floor.name)
            .join(Order, OrderStatusLog.order_id == Order.id)
            .outerjoin(Table, Order.table_id == Table.id)
            .outerjoin(Floor, Table.floor_id == Floor.id)
            .where(
                OrderStatusLog.tenant_id == tenant_id,
                OrderStatusLog.created_at >= start,
                OrderStatusLog.created_at < end,
            )
            .order_by(OrderStatusLog.created_at.desc())
            .limit(limit * 3)
        )
    ).all()

    order_ids = {order.id for _, order, _, _ in logs}
    item_counts = (
        dict(
            (
                await db.execute(
                    select(OrderItem.order_id, func.sum(OrderItem.quantity))
                    .where(OrderItem.order_id.in_(order_ids))
                    .group_by(OrderItem.order_id)
                )
            ).all()
        )
        if order_ids
        else {}
    )

    events: list[dict] = []
    for log, order, table, floor_name in logs:
        at = _aware(log.created_at)
        kind = log.to_status
        amount = None
        if log.from_status is None:
            kind = "placed"
            count = int(item_counts.get(order.id) or 0)
            text = f"placed an order: {count} item{'s' if count != 1 else ''}"
            amount = order.total
        elif kind == "in_kitchen" and at - _aware(order.created_at) < _SAME_REQUEST:
            continue
        elif kind == "completed" and order.order_type == "dine_in":
            continue
        elif kind in _STATUS_TEXT:
            text = _STATUS_TEXT[kind]
            if kind == "voided":
                amount = order.total
                if log.note:
                    text += f" ({log.note})"
        else:
            continue
        events.append(
            {
                "id": f"s-{log.id}",
                "at": at.isoformat(),
                "kind": kind,
                "where": _where(order, table, floor_name),
                "text": text,
                "amount": amount,
                "order_number": order.order_number,
            }
        )

    # --- money in -------------------------------------------------------------
    payments = (
        await db.execute(
            select(Payment, Order, Table, Floor.name, PaymentMethod.display_name)
            .join(Order, Payment.order_id == Order.id)
            .join(PaymentMethod, Payment.method_id == PaymentMethod.id)
            .outerjoin(Table, Order.table_id == Table.id)
            .outerjoin(Floor, Table.floor_id == Floor.id)
            .where(
                Payment.tenant_id == tenant_id,
                Payment.status == "completed",
                Payment.created_at >= start,
                Payment.created_at < end,
            )
            .order_by(Payment.created_at.desc())
        )
    ).all()

    # One settlement of a table writes one Payment row per order in the
    # session; the owner sees one bill. Group by visit, method, kind, second.
    groups: dict[tuple, dict] = {}
    for pay, order, table, floor_name, method_name in payments:
        at = _aware(pay.created_at)
        visit = order.table_session_id or order.id
        key = (visit, pay.method_id, pay.kind, at.replace(microsecond=0))
        g = groups.setdefault(
            key,
            {
                "at": at,
                "id": f"p-{pay.id}",
                "kind": pay.kind,
                "method": method_name,
                "amount": 0,
                "orders": [],
                "where": _where(order, table, floor_name),
                "order_number": order.order_number,
            },
        )
        g["amount"] += pay.amount
        g["orders"].append(order)

    # "Settled" only when this was the last money in and nothing is owed now.
    latest_by_visit: dict = {}
    for (visit, _, kind, _), g in groups.items():
        if kind == "payment":
            latest_by_visit[visit] = max(latest_by_visit.get(visit, g["at"]), g["at"])

    for (visit, _, kind, _), g in groups.items():
        if kind == "refund":
            text, event_kind = f"refund given, {g['method']}", "refund"
        else:
            settled = g["at"] == latest_by_visit.get(visit) and all(
                o.payment_status == "paid" for o in g["orders"]
            )
            event_kind = "settled" if settled else "paid"
            text = (
                f"settled the bill, {g['method']}"
                if settled
                else f"paid part of the bill, {g['method']}"
            )
        events.append(
            {
                "id": g["id"],
                "at": g["at"].isoformat(),
                "kind": event_kind,
                "where": g["where"],
                "text": text,
                "amount": g["amount"],
                "order_number": g["order_number"],
            }
        )

    events.sort(key=lambda e: e["at"], reverse=True)
    return {"date": today.isoformat(), "events": events[:limit]}
