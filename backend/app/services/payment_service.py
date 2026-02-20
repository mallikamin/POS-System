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
    return await get_order_payment_summary(db, order.id, tenant_id)


async def split_payment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    data: SplitPaymentCreate,
) -> PaymentSummary:
    order = await _get_order_or_raise(db, data.order_id, tenant_id)
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
    await db.flush()


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
