"""Z-Report / Daily Settlement service -- assembles end-of-day report data."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discount import OrderDiscount
from app.models.expense import Expense
from app.models.inventory import Ingredient, InventoryTransaction
from app.models.order import Order, OrderItem
from app.models.payment import CashDrawerSession, Payment, PaymentMethod
from app.services import other_income_service, stock_service
from app.utils.tenant_time import tenant_range_utc


async def generate_zreport(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    target_date: date,
    generated_by: str,
) -> dict:
    """Assemble a complete Z-Report for a given date.

    The date is the restaurant's own day, midnight to midnight where it
    stands. A UTC date cast put everything after local midnight on the
    previous day's settlement (Danny's UAT D-30).
    """
    day_start, day_end = await tenant_range_utc(db, tenant_id, target_date, target_date)
    date_filter = and_(Order.created_at >= day_start, Order.created_at < day_end)

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
                Payment.created_at >= day_start,
                Payment.created_at < day_end,
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
                Payment.created_at >= day_start,
                Payment.created_at < day_end,
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
            CashDrawerSession.opened_at >= day_start,
            CashDrawerSession.opened_at < day_end,
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
        # `amount` is already net of change; `cash_out_change` is reported for
        # information only. Subtracting it too counted change twice (D-67).
        expected = drawer_session.opening_float + cash_in - cash_out_refund

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
        "inventory_used": await _inventory_used(db, tenant_id, day_start, day_end),
        "stock_left": await _stock_left(db, tenant_id, day_end),
        "cash_position": await _cash_position(
            db, tenant_id, target_date, day_start, day_end
        ),
    }


# ---------------------------------------------------------------------------
# D-60 daily summary: inventory used, stock left, cash position
# ---------------------------------------------------------------------------
#
# Danny's owner asked for one daily page: what we sold, cash vs card, how much
# stock was used, what is left, and the cash position. The first two were
# already here, so the rest is added to this report rather than to a second
# screen whose numbers could drift from these.

_QTY = Decimal("0.001")
_MONEY = Decimal("0.01")
_ZERO = Decimal("0")


def _dec(value) -> Decimal:
    return Decimal(str(value if value is not None else 0))


async def _inventory_used(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    day_start: datetime,
    day_end: datetime,
) -> dict:
    """What left the shelves during the day, per ingredient, from the movement log.

    Source is `inventory_transactions`, which `stock_service.move_stock` writes
    for every stock change. Classification:

    * `consumption` WITH an order_id: a sale (`consume_for_order`).
    * `consumption` WITHOUT an order_id: an input to a production run
      (`production_service.produce`), shown separately.
    * `waste`: waste. The type exists but no screen writes it today; a waste
      recorded through the adjust screen arrives as an adjustment.
    * `adjustment`: manual corrections, kept SIGNED and separate.
    Purchases, production output and transfers add or move stock and are not
    usage, so they are left out.

    A sale is deducted when the order completes, so its movement lands on the
    day it completed, which is the day it is counted here.

    Cost of a movement = |quantity| x the unit_cost recorded ON THE MOVEMENT
    (move_stock stores the ingredient's cost_per_unit at that moment, or the
    explicit cost it was given). Only when the movement recorded a cost of zero
    do we fall back to the ingredient's CURRENT cost_per_unit, and the row is
    flagged `costed_at_current_price` so the page can say so.

    The day's total cost of goods used is sold + waste. Production inputs are
    excluded because the in-house item they became carries their cost when it
    is itself sold or wasted; adding both would count the same flour twice.
    """
    rows = (
        await db.execute(
            select(
                InventoryTransaction.ingredient_id,
                InventoryTransaction.transaction_type,
                InventoryTransaction.order_id,
                InventoryTransaction.quantity,
                InventoryTransaction.unit_cost,
                Ingredient.name,
                Ingredient.unit,
                Ingredient.cost_per_unit,
            )
            .join(Ingredient, Ingredient.id == InventoryTransaction.ingredient_id)
            .where(
                InventoryTransaction.tenant_id == tenant_id,
                Ingredient.tenant_id == tenant_id,
                InventoryTransaction.transaction_type.in_(
                    ["consumption", "waste", "adjustment"]
                ),
                InventoryTransaction.transaction_date >= day_start,
                InventoryTransaction.transaction_date < day_end,
            )
        )
    ).all()

    by_ingredient: dict[uuid.UUID, dict] = {}
    for r in rows:
        entry = by_ingredient.setdefault(
            r.ingredient_id,
            {
                "ingredient_id": r.ingredient_id,
                "ingredient_name": r.name,
                "unit": r.unit,
                "sold_quantity": _ZERO,
                "sold_cost": _ZERO,
                "production_quantity": _ZERO,
                "production_cost": _ZERO,
                "waste_quantity": _ZERO,
                "waste_cost": _ZERO,
                "adjustment_quantity": _ZERO,
                "adjustment_cost": _ZERO,
                "costed_at_current_price": False,
            },
        )
        qty = _dec(r.quantity)
        unit_cost = _dec(r.unit_cost)
        if unit_cost == 0:
            unit_cost = _dec(r.cost_per_unit)
            if unit_cost != 0:
                entry["costed_at_current_price"] = True

        if r.transaction_type == "adjustment":
            entry["adjustment_quantity"] += qty
            entry["adjustment_cost"] += qty * unit_cost
            continue

        # Consumption and waste are stored negative (they left the shelf) and
        # reported positive. abs() rather than negation so a stray positive
        # row cannot turn into negative usage.
        used = abs(qty)
        if r.transaction_type == "waste":
            key = "waste"
        elif r.order_id is not None:
            key = "sold"
        else:
            key = "production"
        entry[f"{key}_quantity"] += used
        entry[f"{key}_cost"] += used * unit_cost

    out_rows = []
    for entry in by_ingredient.values():
        for k in ("sold", "production", "waste", "adjustment"):
            entry[f"{k}_quantity"] = entry[f"{k}_quantity"].quantize(_QTY)
            entry[f"{k}_cost"] = entry[f"{k}_cost"].quantize(_MONEY)
        entry["used_cost"] = (
            entry["sold_cost"] + entry["production_cost"] + entry["waste_cost"]
        )
        out_rows.append(entry)
    out_rows.sort(key=lambda e: (-e["used_cost"], e["ingredient_name"].lower()))

    total_sold = sum((e["sold_cost"] for e in out_rows), _ZERO)
    total_production = sum((e["production_cost"] for e in out_rows), _ZERO)
    total_waste = sum((e["waste_cost"] for e in out_rows), _ZERO)
    total_adjustment = sum((e["adjustment_cost"] for e in out_rows), _ZERO)
    return {
        "rows": out_rows,
        "total_sold_cost": total_sold,
        "total_production_cost": total_production,
        "total_waste_cost": total_waste,
        "total_adjustment_cost": total_adjustment,
        "total_cost_of_goods_used": total_sold + total_waste,
    }


async def _stock_left(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    day_end: datetime,
) -> dict:
    """Closing stock per location and ingredient at the end of the day.

    Closing = the balance now minus every movement recorded after the day
    ended. For today (or a future date) nothing is after the end yet, so this
    is simply the current balance.

    This is only true because every stock change goes through
    `stock_service.move_stock`, which writes the balance and the movement
    together (checked 2026-09-26: no other runtime code writes
    `location_stock.quantity`, `Ingredient.current_stock` or an
    `InventoryTransaction`; only seed scripts do). Movements with no
    location_id predate locations and cannot be placed on a row; they are not
    backed out.

    The rows come from `stock_service.get_location_stock`, the same query as
    the Stock screen, so retired ingredients are skipped the same way. The
    reorder point is today's setting; history of reorder points is not kept.
    """
    current = await stock_service.get_location_stock(db, tenant_id)

    later = (
        await db.execute(
            select(
                InventoryTransaction.ingredient_id,
                InventoryTransaction.location_id,
                func.coalesce(func.sum(InventoryTransaction.quantity), 0),
            )
            .where(
                InventoryTransaction.tenant_id == tenant_id,
                InventoryTransaction.transaction_date >= day_end,
                InventoryTransaction.location_id.is_not(None),
            )
            .group_by(
                InventoryTransaction.ingredient_id, InventoryTransaction.location_id
            )
        )
    ).all()
    after_end = {(ing, loc): _dec(total) for ing, loc, total in later}
    rows = []
    for r in current:
        closing = (
            _dec(r["quantity"])
            - after_end.get((r["ingredient_id"], r["location_id"]), _ZERO)
        ).quantize(_QTY)
        reorder_point = _dec(r["reorder_point"])
        rows.append(
            {
                "location_id": r["location_id"],
                "location_name": r["location_name"],
                "ingredient_id": r["ingredient_id"],
                "ingredient_name": r["ingredient_name"],
                "unit": r["unit"],
                "closing_quantity": closing,
                "reorder_point": reorder_point,
                # Same rule as the Stock screen's is_low, applied to the
                # closing quantity instead of the live one.
                "is_low": reorder_point > 0 and closing <= reorder_point,
            }
        )

    return {
        "as_of": day_end,
        "multiple_locations": len({r["location_id"] for r in rows}) > 1,
        "low_count": sum(1 for r in rows if r["is_low"]),
        "rows": rows,
    }


async def _cash_sums(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    start: datetime,
    end: datetime | None,
) -> tuple[int, int]:
    """(cash taken, cash refunded) between start and end, in minor units.

    `Payment.amount` is what was applied to the bill; change handed back is
    the part of `tendered_amount` above it and never entered `amount`. So cash
    taken is the sum of `amount`, with nothing subtracted for change.
    """
    conditions = [
        Payment.tenant_id == tenant_id,
        PaymentMethod.code == "cash",
        Payment.status == "completed",
        Payment.kind.in_(["payment", "refund"]),
        Payment.created_at >= start,
    ]
    if end is not None:
        conditions.append(Payment.created_at < end)
    rows = (
        await db.execute(
            select(Payment.kind, func.coalesce(func.sum(Payment.amount), 0))
            .join(PaymentMethod, Payment.method_id == PaymentMethod.id)
            .where(*conditions)
            .group_by(Payment.kind)
        )
    ).all()
    sums = {kind: int(total) for kind, total in rows}
    return sums.get("payment", 0), sums.get("refund", 0)


async def _cash_expenses(
    db: AsyncSession, tenant_id: uuid.UUID, date_from: date, date_to: date
) -> list[dict]:
    """Paid cash expenses with `paid_on` in [date_from, date_to]; see
    `_cash_position` for why "cash" is a substring match. Each amount is
    rounded to whole minor units here, once, so the day figure and the
    rolled-forward cash in hand (D-62) round the same way."""
    if date_to < date_from:
        return []
    rows = (
        await db.execute(
            select(Expense.payee, Expense.payment_method, Expense.amount_minor)
            .where(
                Expense.tenant_id == tenant_id,
                Expense.status == "paid",
                Expense.paid_on >= date_from,
                Expense.paid_on <= date_to,
                func.lower(Expense.payment_method).contains("cash"),
            )
            .order_by(Expense.payee)
        )
    ).all()
    return [
        {
            "payee": r.payee,
            "payment_method": r.payment_method,
            "amount": int(_dec(r.amount_minor).quantize(Decimal("1"), ROUND_HALF_UP)),
        }
        for r in rows
    ]


async def _cash_in_hand(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    target_date: date,
    day_start: datetime,
    net_cash_today: int,
) -> dict | None:
    """Expected cash in hand at the start and end of the day (D-62).

    Start = the opening cash balance plus every day's net cash from its
    `as_of` date up to the day before, by the same formula as `net_cash`.
    None when no opening balance is recorded or the day is before it: no
    figure is invented. Drawer floats are not added: a float is cash in hand
    moved into the till, not new money. "Expected" because counted shortages
    at drawer close are not booked anywhere and so cannot be subtracted.
    """
    opening = await other_income_service.get_opening_balance(db, tenant_id)
    if opening is None or target_date < opening.as_of:
        return None

    range_start, _ = await tenant_range_utc(db, tenant_id, opening.as_of, opening.as_of)
    before = target_date - timedelta(days=1)
    taken, refunds = await _cash_sums(db, tenant_id, range_start, day_start)
    paid_out = sum(
        e["amount"] for e in await _cash_expenses(db, tenant_id, opening.as_of, before)
    )
    other_in = await other_income_service.cash_received_total(
        db, tenant_id, opening.as_of, before
    )
    start = opening.cash_minor + taken - refunds - paid_out + other_in
    return {
        "opening_as_of": opening.as_of,
        "opening_cash": opening.cash_minor,
        "start_of_day": start,
        "end_of_day": start + net_cash_today,
    }


async def _cash_position(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    target_date: date,
    day_start: datetime,
    day_end: datetime,
) -> dict:
    """Cash in and out for the day, and each drawer opened that day.

    Cash paid out = expenses marked paid, paid on this date, whose payment
    method mentions cash. `Expense.payment_method` is FREE TEXT on the
    Expenses screen (placeholder "Bank transfer, cash, cheque"), and on
    2026-09-26 no stored rows existed to learn the real spellings from, so any
    value containing "cash" in any case counts ("Cash", "petty cash"). Every
    expense counted is returned in `cash_expenses`, so the page shows exactly
    what was deducted and a mis-typed method is visible, not silent.

    An expense has a date and no time, so the day's cash expenses are charged
    to the LAST drawer opened that day. Expense amounts are Numeric minor
    units; each is rounded to whole minor units to sit beside the integer
    payment figures.

    No drawer opened that day means `drawers` is empty: no float is invented.
    """
    cash_taken, cash_refunds = await _cash_sums(db, tenant_id, day_start, day_end)

    cash_expenses = await _cash_expenses(db, tenant_id, target_date, target_date)
    cash_paid_out = sum(e["amount"] for e in cash_expenses)

    sessions = (
        (
            await db.execute(
                select(CashDrawerSession)
                .where(
                    CashDrawerSession.tenant_id == tenant_id,
                    CashDrawerSession.opened_at >= day_start,
                    CashDrawerSession.opened_at < day_end,
                )
                .order_by(CashDrawerSession.opened_at)
            )
        )
        .scalars()
        .all()
    )

    # Cash income that is not a sale (D-63). Like an expense it has a date and
    # no time, so it is charged to the LAST drawer opened that day.
    other_cash_income = await other_income_service.cash_received(
        db, tenant_id, target_date
    )
    other_cash_in = sum(line["amount"] for line in other_cash_income)

    # THE CASH FORMULA, in one place:
    #     day:    net_cash = cash_taken - cash_refunds - cash_paid_out + other_cash_in
    #     drawer: expected = opening_float + taken - refunds - paid_out + other_in
    #     in hand: start = opening cash + the same net cash for every earlier
    #              day since the opening balance (D-62, `_cash_in_hand`)
    net_cash = cash_taken - cash_refunds - cash_paid_out + other_cash_in
    cash_in_hand = await _cash_in_hand(db, tenant_id, target_date, day_start, net_cash)

    drawers = []
    for i, s in enumerate(sessions):
        taken, refunds = await _cash_sums(db, tenant_id, s.opened_at, s.closed_at)
        last = i == len(sessions) - 1
        paid_out = cash_paid_out if last else 0
        other_in = other_cash_in if last else 0
        expected = s.opening_float + taken - refunds - paid_out + other_in
        counted = s.closing_balance_counted
        drawers.append(
            {
                "session_status": s.status,
                "opened_at": s.opened_at,
                "closed_at": s.closed_at,
                "opening_float": s.opening_float,
                "cash_taken": taken,
                "cash_refunds": refunds,
                "cash_paid_out": paid_out,
                "other_cash_in": other_in,
                "expected_in_drawer": expected,
                "counted_closing": counted,
                "over_short": (counted - expected) if counted is not None else None,
            }
        )

    return {
        "cash_taken": cash_taken,
        "cash_refunds": cash_refunds,
        "cash_paid_out": cash_paid_out,
        "cash_expenses": cash_expenses,
        "other_cash_in": other_cash_in,
        "other_cash_income": other_cash_income,
        "net_cash": net_cash,
        "cash_in_hand": cash_in_hand,
        "drawer_opened": bool(drawers),
        "drawers": drawers,
    }


def _proportional_amount(base_amount: int, partial_amount: int, total_amount: int) -> int:
    if base_amount == 0 or partial_amount == 0 or total_amount <= 0:
        return 0

    sign = -1 if partial_amount < 0 else 1
    scaled = base_amount * abs(partial_amount)
    return sign * ((scaled + (total_amount // 2)) // total_amount)
