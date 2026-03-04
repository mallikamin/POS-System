"""Payment service -- payment posting, split payments, refunds, cash drawer sessions."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order
from app.models.payment import CashDrawerSession, Payment, PaymentMethod
from app.schemas.payment import (
    CashDrawerCloseRequest,
    CashDrawerOpenRequest,
    PaymentCreate,
    PaymentSummary,
    RefundCreate,
    SessionPaymentCreate,
    SessionPaymentOrderDue,
    SessionPaymentPreview,
    SessionPaymentSummary,
    SessionSplitPaymentCreate,
    SplitPaymentCreate,
)

DEFAULT_PAYMENT_METHODS: list[tuple[str, str, bool, int]] = [
    ("cash", "Cash", False, 1),
    ("card", "Card", True, 2),
    ("mobile_wallet", "Mobile Wallet", True, 3),
    ("bank_transfer", "Bank Transfer", True, 4),
]


async def ensure_default_payment_methods(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    result = await db.execute(
        select(PaymentMethod).where(PaymentMethod.tenant_id == tenant_id)
    )
    existing_codes = {m.code for m in result.scalars().all()}

    for code, display_name, requires_reference, sort_order in DEFAULT_PAYMENT_METHODS:
        if code in existing_codes:
            continue
        db.add(
            PaymentMethod(
                tenant_id=tenant_id,
                code=code,
                display_name=display_name,
                requires_reference=requires_reference,
                sort_order=sort_order,
                is_active=True,
            )
        )
    await db.flush()


async def list_payment_methods(db: AsyncSession, tenant_id: uuid.UUID) -> list[PaymentMethod]:
    await ensure_default_payment_methods(db, tenant_id)
    result = await db.execute(
        select(PaymentMethod)
        .where(PaymentMethod.tenant_id == tenant_id, PaymentMethod.is_active == True)  # noqa: E712
        .order_by(PaymentMethod.sort_order, PaymentMethod.display_name)
    )
    return list(result.scalars().all())


async def create_payment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    data: PaymentCreate,
) -> PaymentSummary:
    order = await _get_order_or_raise(db, data.order_id, tenant_id)
    method = await _get_method_or_raise(db, tenant_id, data.method_code)
    paid_amount, refunded_amount = await _get_order_payment_totals(db, tenant_id, order.id)
    due_amount = max(order.total - paid_amount + refunded_amount, 0)
    if due_amount <= 0:
        raise ValueError("Order is already fully paid")
    if data.amount > due_amount:
        raise ValueError("Payment amount exceeds due amount")

    payment = Payment(
        tenant_id=tenant_id,
        order_id=order.id,
        method_id=method.id,
        kind="payment",
        status="completed",
        amount=data.amount,
        tendered_amount=data.tendered_amount,
        change_amount=max((data.tendered_amount or data.amount) - data.amount, 0)
        if data.method_code == "cash"
        else 0,
        reference=data.reference,
        note=data.note,
        processed_by=user_id,
    )
    db.add(payment)
    await db.flush()

    await _sync_order_payment_status(db, order, tenant_id)

    # Pay-first auto-send: after payment, send confirmed order to kitchen
    await _maybe_send_to_kitchen_after_payment(db, tenant_id, order, user_id)

    return await get_order_payment_summary(db, order.id, tenant_id)


async def split_payment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    data: SplitPaymentCreate,
) -> PaymentSummary:
    order = await _get_order_or_raise(db, data.order_id, tenant_id)
    paid_amount, refunded_amount = await _get_order_payment_totals(db, tenant_id, order.id)
    await _retax_unpaid_order_for_split_allocations(
        db, tenant_id, order, data.allocations, paid_amount, refunded_amount
    )
    paid_amount, refunded_amount = await _get_order_payment_totals(db, tenant_id, order.id)
    due_amount = max(order.total - paid_amount + refunded_amount, 0)
    split_total = sum(a.amount for a in data.allocations)
    if split_total <= 0:
        raise ValueError("Split payment total must be > 0")
    if split_total > due_amount:
        raise ValueError("Split payment exceeds due amount")

    methods = {
        method.code: method
        for method in await list_payment_methods(db, tenant_id)
    }

    for allocation in data.allocations:
        method = methods.get(allocation.method_code)
        if method is None:
            raise ValueError(f"Payment method '{allocation.method_code}' is not available")
        change_amount = 0
        if allocation.method_code == "cash":
            if allocation.tendered_amount is not None and allocation.tendered_amount < allocation.amount:
                raise ValueError("Cash split tendered_amount must be >= amount")
            change_amount = max((allocation.tendered_amount or allocation.amount) - allocation.amount, 0)

        db.add(
            Payment(
                tenant_id=tenant_id,
                order_id=order.id,
                method_id=method.id,
                kind="payment",
                status="completed",
                amount=allocation.amount,
                tendered_amount=allocation.tendered_amount,
                change_amount=change_amount,
                reference=allocation.reference,
                note=data.note,
                processed_by=user_id,
            )
        )

    await db.flush()
    await _sync_order_payment_status(db, order, tenant_id)

    # Pay-first auto-send: after payment, send confirmed order to kitchen
    await _maybe_send_to_kitchen_after_payment(db, tenant_id, order, user_id)

    return await get_order_payment_summary(db, order.id, tenant_id)


async def create_refund(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    data: RefundCreate,
) -> PaymentSummary:
    source_payment = await _get_payment_or_raise(db, data.payment_id, tenant_id)
    if source_payment.kind != "payment":
        raise ValueError("Refund can only target a payment transaction")

    result = await db.execute(
        select(Payment).where(
            Payment.parent_payment_id == source_payment.id,
            Payment.kind == "refund",
            Payment.status == "completed",
            Payment.tenant_id == tenant_id,
        )
    )
    already_refunded = sum(p.amount for p in result.scalars().all())
    refundable = source_payment.amount - already_refunded
    if data.amount > refundable:
        raise ValueError("Refund amount exceeds refundable amount")

    refund = Payment(
        tenant_id=tenant_id,
        order_id=source_payment.order_id,
        method_id=source_payment.method_id,
        parent_payment_id=source_payment.id,
        kind="refund",
        status="completed",
        amount=data.amount,
        tendered_amount=None,
        change_amount=0,
        reference=source_payment.reference,
        note=data.note,
        processed_by=user_id,
    )
    db.add(refund)
    await db.flush()

    order = await _get_order_or_raise(db, source_payment.order_id, tenant_id)
    await _sync_order_payment_status(db, order, tenant_id)
    return await get_order_payment_summary(db, source_payment.order_id, tenant_id)


async def get_order_payment_summary(
    db: AsyncSession,
    order_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> PaymentSummary:
    order = await _get_order_or_raise(db, order_id, tenant_id)
    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.method))
        .where(Payment.tenant_id == tenant_id, Payment.order_id == order_id)
        .order_by(Payment.created_at.asc())
    )
    payments = list(result.scalars().all())
    paid_amount = sum(p.amount for p in payments if p.kind == "payment" and p.status == "completed")
    refunded_amount = sum(p.amount for p in payments if p.kind == "refund" and p.status == "completed")
    due_amount = max(order.total - paid_amount + refunded_amount, 0)
    return PaymentSummary(
        order_id=order.id,
        order_number=order.order_number,
        order_total=order.total,
        paid_amount=paid_amount,
        refunded_amount=refunded_amount,
        due_amount=due_amount,
        payment_status=order.payment_status,
        payments=payments,
    )


async def get_active_drawer_session(
    db: AsyncSession, tenant_id: uuid.UUID
) -> CashDrawerSession | None:
    result = await db.execute(
        select(CashDrawerSession)
        .where(
            CashDrawerSession.tenant_id == tenant_id,
            CashDrawerSession.status == "open",
        )
        .order_by(CashDrawerSession.opened_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def open_drawer_session(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    data: CashDrawerOpenRequest,
) -> CashDrawerSession:
    existing = await get_active_drawer_session(db, tenant_id)
    if existing is not None:
        raise ValueError("An active cash drawer session already exists")

    session = CashDrawerSession(
        tenant_id=tenant_id,
        status="open",
        opened_by=user_id,
        opening_float=data.opening_float,
        note=data.note,
    )
    db.add(session)
    await db.flush()
    return session


async def close_drawer_session(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    data: CashDrawerCloseRequest,
) -> CashDrawerSession:
    session = await get_active_drawer_session(db, tenant_id)
    if session is None:
        raise ValueError("No active cash drawer session")

    expected = await _calculate_expected_drawer_balance(
        db, tenant_id, session.opened_at, session.opening_float
    )
    session.status = "closed"
    session.closed_by = user_id
    session.closed_at = datetime.now(timezone.utc)
    session.closing_balance_expected = expected
    session.closing_balance_counted = data.closing_balance_counted
    session.note = data.note or session.note
    await db.flush()
    return session


async def _calculate_expected_drawer_balance(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    opened_at: datetime,
    opening_float: int,
) -> int:
    result = await db.execute(
        select(Payment)
        .join(PaymentMethod, Payment.method_id == PaymentMethod.id)
        .where(
            Payment.tenant_id == tenant_id,
            PaymentMethod.code == "cash",
            Payment.status == "completed",
            Payment.created_at >= opened_at,
            Payment.kind.in_(["payment", "refund"]),
        )
    )
    payments = list(result.scalars().all())
    incoming = sum(p.amount for p in payments if p.kind == "payment")
    outgoing_change = sum(p.change_amount for p in payments if p.kind == "payment")
    outgoing_refund = sum(p.amount for p in payments if p.kind == "refund")
    return opening_float + incoming - outgoing_change - outgoing_refund


# ---------------------------------------------------------------------------
# Session Payment (P2)
# ---------------------------------------------------------------------------


async def get_session_payment_summary(
    db: AsyncSession, session_id: uuid.UUID, tenant_id: uuid.UUID
) -> SessionPaymentSummary:
    """Get consolidated payment summary for a table session."""
    from app.models.table_session import TableSession
    from app.models.discount import OrderDiscount

    result = await db.execute(
        select(TableSession)
        .options(
            selectinload(TableSession.table),
            selectinload(TableSession.orders),
        )
        .where(TableSession.id == session_id, TableSession.tenant_id == tenant_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise ValueError("Table session not found")

    billable_orders = sorted(
        [o for o in session.orders if o.status != "voided"],
        key=lambda o: o.created_at,
    )

    subtotal = sum(o.subtotal for o in billable_orders)
    tax_amount = sum(o.tax_amount for o in billable_orders)
    discount_amount = sum(o.discount_amount for o in billable_orders)
    total = sum(o.total for o in billable_orders)

    # Per-order payment breakdown
    order_dues: list[SessionPaymentOrderDue] = []
    total_paid = 0
    for o in billable_orders:
        paid, refunded = await _get_order_payment_totals(db, tenant_id, o.id)
        net_paid = paid - refunded
        due = max(o.total - net_paid, 0)
        total_paid += net_paid
        order_dues.append(SessionPaymentOrderDue(
            order_id=o.id,
            order_number=o.order_number,
            order_total=o.total,
            paid_amount=net_paid,
            due_amount=due,
            payment_status=o.payment_status,
        ))

    # Session-level discounts
    session_disc_result = await db.execute(
        select(OrderDiscount.amount).where(
            OrderDiscount.tenant_id == tenant_id,
            OrderDiscount.table_session_id == session_id,
        )
    )
    session_discount = sum(row[0] for row in session_disc_result.all())
    discount_amount += session_discount

    session_due = max(total - session_discount - total_paid, 0)

    if total_paid <= 0:
        payment_status = "unpaid"
    elif session_due > 0:
        payment_status = "partial"
    else:
        payment_status = "paid"

    return SessionPaymentSummary(
        session_id=session.id,
        table_id=session.table_id,
        table_label=(
            (session.table.label or str(session.table.number))
            if session.table else None
        ),
        order_count=len(billable_orders),
        subtotal=subtotal,
        tax_amount=tax_amount,
        discount_amount=discount_amount,
        total=total,
        paid_amount=total_paid,
        due_amount=session_due,
        payment_status=payment_status,
        orders=order_dues,
    )


async def get_session_payment_preview(
    db: AsyncSession, session_id: uuid.UUID, tenant_id: uuid.UUID
) -> SessionPaymentPreview:
    """Compute cash and card totals for a table session using method-specific tax rates."""
    from app.models.table_session import TableSession
    from app.models.restaurant_config import RestaurantConfig

    result = await db.execute(
        select(TableSession)
        .options(selectinload(TableSession.orders))
        .where(TableSession.id == session_id, TableSession.tenant_id == tenant_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise ValueError("Table session not found")

    billable_orders = [o for o in session.orders if o.status != "voided"]
    subtotal = sum(o.subtotal for o in billable_orders)

    # Fetch per-method tax rates from config
    cfg_result = await db.execute(
        select(
            RestaurantConfig.cash_tax_rate_bps,
            RestaurantConfig.card_tax_rate_bps,
        ).where(RestaurantConfig.tenant_id == tenant_id)
    )
    row = cfg_result.one_or_none()
    cash_rate = row.cash_tax_rate_bps if row else 1600
    card_rate = row.card_tax_rate_bps if row else 500

    cash_tax = round(subtotal * cash_rate / 10_000)
    card_tax = round(subtotal * card_rate / 10_000)

    return SessionPaymentPreview(
        session_id=session.id,
        subtotal=subtotal,
        cash_tax_rate_bps=cash_rate,
        cash_tax_amount=cash_tax,
        cash_total=subtotal + cash_tax,
        card_tax_rate_bps=card_rate,
        card_tax_amount=card_tax,
        card_total=subtotal + card_tax,
    )


async def create_session_payment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    data: SessionPaymentCreate,
) -> SessionPaymentSummary:
    """Pay a table session bill with a single method.

    Allocates payment across unpaid orders deterministically (oldest first).
    """
    from app.models.table_session import TableSession

    result = await db.execute(
        select(TableSession)
        .options(selectinload(TableSession.orders))
        .where(TableSession.id == session_id, TableSession.tenant_id == tenant_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise ValueError("Table session not found")
    if session.status == "closed":
        raise ValueError("Session is already closed")

    method = await _get_method_or_raise(db, tenant_id, data.method_code)

    billable_orders = sorted(
        [o for o in session.orders if o.status != "voided"],
        key=lambda o: o.created_at,
    )

    # Align taxable totals with selected settlement mode (cash/card) before
    # computing dues so card settlement can close at card-total preview.
    if data.method_code in {"cash", "card"}:
        await _retax_unpaid_session_orders_for_method(
            db, tenant_id, billable_orders, data.method_code
        )

    # Build per-order due list
    order_dues: list[tuple[Order, int]] = []
    total_session_due = 0
    for o in billable_orders:
        paid, refunded = await _get_order_payment_totals(db, tenant_id, o.id)
        due = max(o.total - (paid - refunded), 0)
        total_session_due += due
        if due > 0:
            order_dues.append((o, due))

    if total_session_due <= 0:
        raise ValueError("Session is already fully paid")
    if data.amount > total_session_due:
        raise ValueError("Payment amount exceeds session due amount")

    # Allocate across orders (oldest first)
    remaining = data.amount
    is_first = True
    for order, order_due in order_dues:
        if remaining <= 0:
            break
        alloc = min(remaining, order_due)

        tendered = None
        change = 0
        if data.method_code == "cash" and is_first:
            tendered = data.tendered_amount
            change = max((data.tendered_amount or data.amount) - data.amount, 0)
            is_first = False

        db.add(Payment(
            tenant_id=tenant_id,
            order_id=order.id,
            method_id=method.id,
            kind="payment",
            status="completed",
            amount=alloc,
            tendered_amount=tendered,
            change_amount=change,
            reference=data.reference,
            note=data.note,
            processed_by=user_id,
        ))
        remaining -= alloc

    await db.flush()

    # Sync payment status for all affected orders
    # (_sync_order_payment_status auto-closes session when all orders paid)
    for order, _ in order_dues:
        await _sync_order_payment_status(db, order, tenant_id)

    return await get_session_payment_summary(db, session_id, tenant_id)


async def _retax_unpaid_session_orders_for_method(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    billable_orders: list[Order],
    method_code: str,
) -> None:
    """Recalculate tax/total for fully-unpaid session orders by payment mode.

    This keeps preview totals and settlement totals consistent for cash/card.
    If any order has net paid > 0, we skip retaxing to avoid mutating totals
    after payment has started.
    """
    if method_code not in {"cash", "card"} or not billable_orders:
        return

    # Do not retax once any payment is already posted on the session orders.
    for order in billable_orders:
        paid, refunded = await _get_order_payment_totals(db, tenant_id, order.id)
        if (paid - refunded) > 0:
            return

    from app.models.restaurant_config import RestaurantConfig

    cfg_result = await db.execute(
        select(
            RestaurantConfig.cash_tax_rate_bps,
            RestaurantConfig.card_tax_rate_bps,
        ).where(RestaurantConfig.tenant_id == tenant_id)
    )
    row = cfg_result.one_or_none()
    cash_rate = row.cash_tax_rate_bps if row else 1600
    card_rate = row.card_tax_rate_bps if row else 500
    rate_bps = cash_rate if method_code == "cash" else card_rate

    subtotal = sum(o.subtotal for o in billable_orders)
    target_tax = round(subtotal * rate_bps / 10_000)
    remaining_tax = target_tax

    for idx, order in enumerate(billable_orders):
        if idx == len(billable_orders) - 1:
            tax_amount = remaining_tax
        else:
            tax_amount = round(order.subtotal * rate_bps / 10_000)
            remaining_tax -= tax_amount

        order.tax_amount = tax_amount
        order.total = order.subtotal + order.tax_amount - order.discount_amount

    await db.flush()


async def split_session_payment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    data: SessionSplitPaymentCreate,
) -> SessionPaymentSummary:
    """Split-pay a table session bill across multiple methods.

    Allocates method amounts across unpaid orders deterministically (oldest first).
    """
    from app.models.table_session import TableSession

    result = await db.execute(
        select(TableSession)
        .options(selectinload(TableSession.orders))
        .where(TableSession.id == session_id, TableSession.tenant_id == tenant_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise ValueError("Table session not found")
    if session.status == "closed":
        raise ValueError("Session is already closed")

    methods = {m.code: m for m in await list_payment_methods(db, tenant_id)}

    for alloc in data.allocations:
        if alloc.method_code not in methods:
            raise ValueError(f"Payment method '{alloc.method_code}' is not available")

    billable_orders = sorted(
        [o for o in session.orders if o.status != "voided"],
        key=lambda o: o.created_at,
    )
    await _retax_unpaid_session_orders_for_split_allocations(
        db, tenant_id, billable_orders, data.allocations
    )

    order_dues: list[tuple[Order, int]] = []
    total_session_due = 0
    for o in billable_orders:
        paid, refunded = await _get_order_payment_totals(db, tenant_id, o.id)
        due = max(o.total - (paid - refunded), 0)
        total_session_due += due
        if due > 0:
            order_dues.append((o, due))

    split_total = sum(a.amount for a in data.allocations)
    if split_total <= 0:
        raise ValueError("Split payment total must be > 0")
    if split_total > total_session_due:
        raise ValueError("Split payment total exceeds session due amount")

    # Track remaining per allocation
    alloc_remaining = [[a, a.amount] for a in data.allocations]

    for order, order_due in order_dues:
        order_remaining = order_due
        for entry in alloc_remaining:
            alloc, alloc_rem = entry[0], entry[1]
            if order_remaining <= 0 or alloc_rem <= 0:
                continue

            method = methods[alloc.method_code]
            pay_amount = min(order_remaining, alloc_rem)

            tendered = None
            change = 0
            if alloc.method_code == "cash" and alloc_rem == alloc.amount:
                tendered = alloc.tendered_amount
                if tendered is not None:
                    change = max(tendered - alloc.amount, 0)

            db.add(Payment(
                tenant_id=tenant_id,
                order_id=order.id,
                method_id=method.id,
                kind="payment",
                status="completed",
                amount=pay_amount,
                tendered_amount=tendered,
                change_amount=change,
                reference=alloc.reference,
                note=data.note,
                processed_by=user_id,
            ))

            order_remaining -= pay_amount
            entry[1] = alloc_rem - pay_amount

    await db.flush()

    for order, _ in order_dues:
        await _sync_order_payment_status(db, order, tenant_id)

    return await get_session_payment_summary(db, session_id, tenant_id)


async def _retax_unpaid_order_for_split_allocations(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order: Order,
    allocations,
    paid_amount: int,
    refunded_amount: int,
) -> None:
    """Retax an unpaid order for cash/card mixed split allocations."""
    if (paid_amount - refunded_amount) > 0:
        return

    inferred = await _infer_split_subtotal_and_tax(db, tenant_id, allocations)
    if inferred is None:
        return
    inferred_subtotal, inferred_tax = inferred
    if abs(inferred_subtotal - order.subtotal) > 1:
        return

    order.tax_amount = inferred_tax
    order.total = order.subtotal + order.tax_amount - order.discount_amount
    await db.flush()


async def _retax_unpaid_session_orders_for_split_allocations(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    billable_orders: list[Order],
    allocations,
) -> None:
    """Retax fully-unpaid session orders for cash/card mixed split allocations."""
    if not billable_orders:
        return

    for order in billable_orders:
        paid, refunded = await _get_order_payment_totals(db, tenant_id, order.id)
        if (paid - refunded) > 0:
            return

    inferred = await _infer_split_subtotal_and_tax(db, tenant_id, allocations)
    if inferred is None:
        return
    inferred_subtotal, inferred_tax = inferred

    subtotal = sum(o.subtotal for o in billable_orders)
    if abs(inferred_subtotal - subtotal) > max(1, len(billable_orders)):
        return

    remaining_tax = inferred_tax
    for idx, order in enumerate(billable_orders):
        if idx == len(billable_orders) - 1:
            tax_amount = remaining_tax
        else:
            tax_amount = round(order.subtotal * inferred_tax / subtotal) if subtotal > 0 else 0
            remaining_tax -= tax_amount

        order.tax_amount = tax_amount
        order.total = order.subtotal + order.tax_amount - order.discount_amount

    await db.flush()


async def _infer_split_subtotal_and_tax(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    allocations,
) -> tuple[int, int] | None:
    """Infer pre-tax subtotal and tax from mixed cash/card tax-inclusive allocations.

    Returns None if any allocation method is outside cash/card.
    """
    if not allocations:
        return None

    from app.models.restaurant_config import RestaurantConfig

    cfg_result = await db.execute(
        select(
            RestaurantConfig.cash_tax_rate_bps,
            RestaurantConfig.card_tax_rate_bps,
        ).where(RestaurantConfig.tenant_id == tenant_id)
    )
    row = cfg_result.one_or_none()
    cash_rate = row.cash_tax_rate_bps if row else 1600
    card_rate = row.card_tax_rate_bps if row else 500

    inferred_subtotal = 0
    inferred_tax = 0
    for alloc in allocations:
        if alloc.method_code == "cash":
            rate = cash_rate
        elif alloc.method_code == "card":
            rate = card_rate
        else:
            return None

        divisor = 10_000 + rate
        base = round(alloc.amount * 10_000 / divisor) if divisor > 0 else alloc.amount
        tax = alloc.amount - base
        inferred_subtotal += base
        inferred_tax += tax

    return inferred_subtotal, inferred_tax


async def _sync_order_payment_status(
    db: AsyncSession, order: Order, tenant_id: uuid.UUID
) -> None:
    paid_amount, refunded_amount = await _get_order_payment_totals(db, tenant_id, order.id)
    net_paid = paid_amount - refunded_amount
    if net_paid <= 0 and refunded_amount > 0:
        order.payment_status = "refunded"
    elif net_paid <= 0:
        order.payment_status = "unpaid"
    elif net_paid < order.total:
        order.payment_status = "partial"
    else:
        order.payment_status = "paid"

    # Auto-complete: a dine-in order that is "served" and fully paid is done.
    # This ensures the table is released without waiting for a manual transition.
    if (
        order.payment_status == "paid"
        and order.status == "served"
        and order.order_type == "dine_in"
    ):
        order.status = "completed"

    await db.flush()

    # Auto-close table session when all its orders are fully settled.
    # This covers the per-order payment path (session payment endpoints
    # handle their own auto-close separately).
    if order.payment_status == "paid" and order.table_session_id:
        await _maybe_close_session(db, order.table_session_id, tenant_id)


async def _maybe_close_session(
    db: AsyncSession, session_id: uuid.UUID, tenant_id: uuid.UUID
) -> None:
    """Close a table session if every order in it is paid or completed/voided."""
    from app.models.table_session import TableSession

    result = await db.execute(
        select(TableSession)
        .options(selectinload(TableSession.orders))
        .where(TableSession.id == session_id, TableSession.tenant_id == tenant_id)
    )
    session = result.scalar_one_or_none()
    if session is None or session.status == "closed":
        return

    for o in session.orders:
        if o.status == "voided":
            continue
        if o.payment_status != "paid":
            return  # at least one unpaid order — don't close

    # All orders paid or voided — close the session
    from app.services import table_session_service
    await table_session_service.close_session(
        db, session_id, tenant_id, session.opened_by
    )


async def _get_order_payment_totals(
    db: AsyncSession, tenant_id: uuid.UUID, order_id: uuid.UUID
) -> tuple[int, int]:
    result = await db.execute(
        select(Payment).where(
            Payment.tenant_id == tenant_id,
            Payment.order_id == order_id,
            Payment.status == "completed",
        )
    )
    payments = list(result.scalars().all())
    paid_amount = sum(p.amount for p in payments if p.kind == "payment")
    refunded_amount = sum(p.amount for p in payments if p.kind == "refund")
    return paid_amount, refunded_amount


async def _get_order_or_raise(
    db: AsyncSession, order_id: uuid.UUID, tenant_id: uuid.UUID
) -> Order:
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.tenant_id == tenant_id)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise ValueError("Order not found")
    return order


async def _get_method_or_raise(
    db: AsyncSession, tenant_id: uuid.UUID, method_code: str
) -> PaymentMethod:
    await ensure_default_payment_methods(db, tenant_id)
    result = await db.execute(
        select(PaymentMethod).where(
            PaymentMethod.tenant_id == tenant_id,
            PaymentMethod.code == method_code,
            PaymentMethod.is_active == True,  # noqa: E712
        )
    )
    method = result.scalar_one_or_none()
    if method is None:
        raise ValueError(f"Payment method '{method_code}' is not available")
    return method


async def _maybe_send_to_kitchen_after_payment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order: Order,
    user_id: uuid.UUID,
) -> None:
    """In pay_first mode, auto-send a confirmed order to kitchen after payment."""
    from app.services.order_service import (
        _auto_create_kitchen_ticket,
        _get_payment_flow,
    )
    from app.models.order import OrderStatusLog

    if order.status != "confirmed":
        return

    payment_flow = await _get_payment_flow(db, tenant_id)
    if payment_flow != "pay_first":
        return

    # Transition to in_kitchen
    order.status = "in_kitchen"
    for item in order.items:
        item.status = "sent"

    db.add(OrderStatusLog(
        tenant_id=tenant_id,
        order_id=order.id,
        from_status="confirmed",
        to_status="in_kitchen",
        changed_by=user_id,
    ))
    await db.flush()

    # Reload order with items for kitchen ticket creation
    from app.services.order_service import get_order as _get_order_full
    full_order = await _get_order_full(db, order.id, tenant_id)
    if full_order:
        await _auto_create_kitchen_ticket(db, tenant_id, full_order)


async def _get_payment_or_raise(
    db: AsyncSession, payment_id: uuid.UUID, tenant_id: uuid.UUID
) -> Payment:
    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.method))
        .where(Payment.id == payment_id, Payment.tenant_id == tenant_id)
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        raise ValueError("Payment not found")
    return payment
