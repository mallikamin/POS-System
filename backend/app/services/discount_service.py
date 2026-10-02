"""Discount service — CRUD for discount types, apply/remove discounts on orders."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discount import DiscountType, OrderDiscount
from app.models.order import Order
from app.schemas.discount import DiscountTypeCreate, DiscountTypeUpdate


# ---------------------------------------------------------------------------
# Discount Type CRUD
# ---------------------------------------------------------------------------


async def list_discount_types(
    db: AsyncSession, tenant_id: uuid.UUID, active_only: bool = False
) -> list[DiscountType]:
    stmt = select(DiscountType).where(DiscountType.tenant_id == tenant_id)
    if active_only:
        stmt = stmt.where(DiscountType.is_active == True)  # noqa: E712
    stmt = stmt.order_by(DiscountType.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_discount_type(
    db: AsyncSession, type_id: uuid.UUID, tenant_id: uuid.UUID
) -> DiscountType | None:
    result = await db.execute(
        select(DiscountType).where(
            DiscountType.id == type_id,
            DiscountType.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_discount_type(
    db: AsyncSession, tenant_id: uuid.UUID, data: DiscountTypeCreate
) -> DiscountType:
    dt = DiscountType(
        tenant_id=tenant_id,
        code=data.code,
        name=data.name,
        kind=data.kind,
        value=data.value,
        is_active=data.is_active,
    )
    db.add(dt)
    await db.flush()
    return dt


async def update_discount_type(
    db: AsyncSession, dt: DiscountType, data: DiscountTypeUpdate
) -> DiscountType:
    for field in ("name", "kind", "value", "is_active"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(dt, field, val)
    await db.flush()
    return dt


async def delete_discount_type(db: AsyncSession, dt: DiscountType) -> None:
    await db.delete(dt)
    await db.flush()


# ---------------------------------------------------------------------------
# Apply Discount
# ---------------------------------------------------------------------------


async def apply_discount(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    order_id: uuid.UUID | None,
    table_session_id: uuid.UUID | None,
    discount_type_id: uuid.UUID | None,
    label: str | None,
    source_type: str | None,
    amount: int | None,
    note: str | None,
    manager_verify_token: str | None = None,
) -> OrderDiscount:
    """Apply a discount to an order or session.

    If discount_type_id is provided, auto-derive label/source_type/amount.
    Validates that discount does not exceed the order/session subtotal.
    """
    if not order_id and not table_session_id:
        raise ValueError("Either order_id or table_session_id is required")

    resolved_label = label or "Discount"
    resolved_source = source_type or "manual"
    resolved_amount = amount or 0
    percent_bps = 0

    # If using a catalog type, derive fields
    if discount_type_id:
        dt = await get_discount_type(db, discount_type_id, tenant_id)
        if dt is None:
            raise ValueError("Discount type not found")
        if not dt.is_active:
            raise ValueError("Discount type is not active")
        resolved_label = label or f"{dt.name}"
        resolved_source = source_type or dt.code

        if dt.kind == "percent":
            # Need the order subtotal to compute amount
            target_subtotal = await _get_target_subtotal(
                db, tenant_id, order_id, table_session_id
            )
            resolved_amount = round(target_subtotal * dt.value / 10_000)
            percent_bps = dt.value
            if label is None:
                resolved_label = f"{dt.name} ({dt.value / 100:.1f}%)"
        else:
            # fixed discount
            resolved_amount = amount if amount is not None else dt.value

    if resolved_amount <= 0:
        raise ValueError("Discount amount must be > 0")

    # D-104: a table discount has to land on a bill that can still change.
    if table_session_id and not order_id and not await _session_has_unpaid_bill(
        db, tenant_id, table_session_id
    ):
        raise ValueError(
            "Every bill on this table already has a payment. Discount a single bill instead."
        )

    # Validate: discount cannot exceed remaining applicable amount
    target_subtotal = await _get_target_subtotal(
        db, tenant_id, order_id, table_session_id
    )
    existing_discounts = await _get_existing_discount_total(
        db, tenant_id, order_id, table_session_id
    )
    max_discount = target_subtotal - existing_discounts
    if resolved_amount > max_discount:
        raise ValueError(
            f"Discount ({resolved_amount}) exceeds available amount ({max_discount})"
        )

    # --- Threshold check: require manager approval if exceeded ---
    await _check_approval_threshold(
        db,
        tenant_id,
        resolved_amount,
        percent_bps,
        target_subtotal,
        manager_verify_token,
    )

    od = OrderDiscount(
        tenant_id=tenant_id,
        order_id=order_id,
        table_session_id=table_session_id,
        discount_type_id=discount_type_id,
        label=resolved_label,
        source_type=resolved_source,
        amount=resolved_amount,
        percent_bps=percent_bps,
        note=note,
        applied_by=user_id,
    )
    db.add(od)
    await db.flush()

    # Update order's discount_amount rollup for backward compatibility
    if order_id:
        await _sync_order_discount(db, tenant_id, order_id)
    elif table_session_id:
        await allocate_session_discounts(db, tenant_id, table_session_id)

    return od


# ---------------------------------------------------------------------------
# Remove Discount
# ---------------------------------------------------------------------------


async def remove_discount(
    db: AsyncSession, discount_id: uuid.UUID, tenant_id: uuid.UUID
) -> None:
    result = await db.execute(
        select(OrderDiscount).where(
            OrderDiscount.id == discount_id,
            OrderDiscount.tenant_id == tenant_id,
        )
    )
    od = result.scalar_one_or_none()
    if od is None:
        raise ValueError("Discount not found")

    order_id = od.order_id
    session_id = od.table_session_id
    await db.delete(od)
    await db.flush()

    # Re-sync rollup
    if order_id:
        await _sync_order_discount(db, tenant_id, order_id)
    elif session_id:
        await allocate_session_discounts(db, tenant_id, session_id)


# ---------------------------------------------------------------------------
# List Discounts on Order
# ---------------------------------------------------------------------------


async def list_order_discounts(
    db: AsyncSession, tenant_id: uuid.UUID, order_id: uuid.UUID
) -> list[OrderDiscount]:
    result = await db.execute(
        select(OrderDiscount)
        .where(
            OrderDiscount.tenant_id == tenant_id,
            OrderDiscount.order_id == order_id,
        )
        .order_by(OrderDiscount.created_at)
    )
    return list(result.scalars().all())


async def list_session_discounts(
    db: AsyncSession, tenant_id: uuid.UUID, session_id: uuid.UUID
) -> list[OrderDiscount]:
    result = await db.execute(
        select(OrderDiscount)
        .where(
            OrderDiscount.tenant_id == tenant_id,
            OrderDiscount.table_session_id == session_id,
        )
        .order_by(OrderDiscount.created_at)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_target_subtotal(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order_id: uuid.UUID | None,
    table_session_id: uuid.UUID | None,
) -> int:
    """Get the subtotal that discounts are applied against."""
    if order_id:
        result = await db.execute(
            select(Order.subtotal).where(
                Order.id == order_id, Order.tenant_id == tenant_id
            )
        )
        subtotal = result.scalar_one_or_none()
        if subtotal is None:
            raise ValueError("Order not found")
        return subtotal

    if table_session_id:
        # Sum subtotals of non-voided orders in session
        result = await db.execute(
            select(Order.subtotal).where(
                Order.table_session_id == table_session_id,
                Order.tenant_id == tenant_id,
                Order.status != "voided",
            )
        )
        return sum(row[0] for row in result.all())

    return 0


async def _get_existing_discount_total(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order_id: uuid.UUID | None,
    table_session_id: uuid.UUID | None,
) -> int:
    stmt = select(OrderDiscount.amount).where(OrderDiscount.tenant_id == tenant_id)
    if order_id:
        stmt = stmt.where(OrderDiscount.order_id == order_id)
    elif table_session_id:
        stmt = stmt.where(OrderDiscount.table_session_id == table_session_id)
    else:
        return 0

    result = await db.execute(stmt)
    return sum(row[0] for row in result.all())


async def _check_approval_threshold(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    discount_amount: int,
    percent_bps: int,
    target_subtotal: int,
    manager_verify_token: str | None,
) -> None:
    """Raise ValueError if discount exceeds threshold and no valid manager token."""
    from app.models.restaurant_config import RestaurantConfig
    from app.services.auth_service import validate_verify_token

    result = await db.execute(
        select(RestaurantConfig).where(RestaurantConfig.tenant_id == tenant_id)
    )
    config = result.scalar_one_or_none()
    if config is None:
        return  # no config = no threshold enforcement

    threshold_bps = config.discount_approval_threshold_bps
    threshold_fixed = config.discount_approval_threshold_fixed

    # Both 0 = disabled
    if threshold_bps == 0 and threshold_fixed == 0:
        return

    # Compute effective percent of this discount
    if percent_bps > 0:
        effective_bps = percent_bps
    elif target_subtotal > 0:
        effective_bps = round(discount_amount * 10_000 / target_subtotal)
    else:
        effective_bps = 0

    exceeds = False
    if threshold_bps > 0 and effective_bps > threshold_bps:
        exceeds = True
    if threshold_fixed > 0 and discount_amount > threshold_fixed:
        exceeds = True

    if not exceeds:
        return

    # Threshold exceeded — require valid manager token
    if not manager_verify_token:
        raise ValueError("approval_required")

    user_id = validate_verify_token(manager_verify_token)
    if user_id is None:
        raise ValueError("Invalid or expired manager approval token")


async def _sync_order_discount(
    db: AsyncSession, tenant_id: uuid.UUID, order_id: uuid.UUID
) -> None:
    """Update the order.discount_amount and order.total to reflect applied discounts.

    discount_amount = the order's own discount lines + its share of any
    table-level (session) discount (D-104, see `allocate_session_discounts`).
    """
    total_discount = await _get_existing_discount_total(db, tenant_id, order_id, None)
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.tenant_id == tenant_id)
    )
    order = result.scalar_one_or_none()
    if order:
        # `order_total` is the one rule for an order's payable amount. The
        # inline `subtotal + tax_amount - discount` this replaces double-charged
        # tax-inclusive tenants (F19) and would have dropped any delivery or
        # service charge the moment a discount was applied.
        from app.services import order_service

        _, prices_include_tax = await order_service._get_tax_settings(db, tenant_id)
        order.discount_amount = total_discount + (order.session_discount_share or 0)
        order.total = order_service.order_total(order, prices_include_tax)
        await db.flush()


# ---------------------------------------------------------------------------
# Table-level (session) discounts (D-104)
# ---------------------------------------------------------------------------


async def session_discount_total(
    db: AsyncSession, tenant_id: uuid.UUID, session_id: uuid.UUID
) -> int:
    """Sum of the table-level discount lines (no order attached) on a session."""
    result = await db.execute(
        select(OrderDiscount.amount).where(
            OrderDiscount.tenant_id == tenant_id,
            OrderDiscount.table_session_id == session_id,
            OrderDiscount.order_id.is_(None),
        )
    )
    return sum(row[0] for row in result.all())


async def unallocated_session_discount(
    db: AsyncSession, tenant_id: uuid.UUID, session_id: uuid.UUID, billable_orders: list[Order]
) -> int:
    """The part of the table discount not yet inside any billable order's total.

    Readers (session summary, preview, bill, receipt) subtract only this, since
    the allocated part already sits in each order's discount_amount and total.
    Normally 0; non-zero only between a change to the table's bills and the
    next allocation (which every table payment runs first).
    """
    total = await session_discount_total(db, tenant_id, session_id)
    allocated = sum(o.session_discount_share or 0 for o in billable_orders)
    return max(total - allocated, 0)


async def allocate_session_discounts(
    db: AsyncSession, tenant_id: uuid.UUID, session_id: uuid.UUID
) -> None:
    """Spread the table-level discount over the table's bills (D-104).

    A table discount used to live only on the session, so each order's total
    stayed full: the table paid the discounted amount, the order stayed
    'partial', the session never closed and stock was never deducted.

    Bills with a payment on them keep their share (like the tax, nothing is
    re-priced once money is taken). The rest is spread over the unpaid bills
    in proportion to their food subtotal; the last bill takes the rounding
    remainder, so the shares always add up to the discount exactly.
    """
    from app.services.payment_service import _get_order_payment_totals

    result = await db.execute(
        select(Order)
        .where(Order.tenant_id == tenant_id, Order.table_session_id == session_id)
        .order_by(Order.created_at, Order.id)
    )
    orders = list(result.scalars().all())
    billable = [o for o in orders if o.status != "voided"]

    open_orders: list[Order] = []
    frozen = 0
    for o in billable:
        paid, refunded = await _get_order_payment_totals(db, tenant_id, o.id)
        if paid - refunded > 0:
            frozen += o.session_discount_share or 0
        else:
            open_orders.append(o)

    to_allocate = max(await session_discount_total(db, tenant_id, session_id) - frozen, 0)
    base = sum(o.subtotal for o in open_orders)
    remaining = to_allocate
    changed: list[Order] = []
    for idx, o in enumerate(open_orders):
        if idx == len(open_orders) - 1:
            share = remaining
        else:
            share = round(to_allocate * o.subtotal / base) if base > 0 else 0
            remaining -= share
        if share != (o.session_discount_share or 0):
            o.session_discount_share = share
            changed.append(o)
    # A voided bill never carries a share.
    for o in orders:
        if o.status == "voided" and o.session_discount_share:
            o.session_discount_share = 0
    await db.flush()
    # Only a bill whose share moved is re-totalled. A table with no table
    # discount is never touched, so paying it cannot re-price any bill.
    for o in changed:
        await _sync_order_discount(db, tenant_id, o.id)


async def _session_has_unpaid_bill(
    db: AsyncSession, tenant_id: uuid.UUID, session_id: uuid.UUID
) -> bool:
    from app.services.payment_service import _get_order_payment_totals

    result = await db.execute(
        select(Order.id).where(
            Order.tenant_id == tenant_id,
            Order.table_session_id == session_id,
            Order.status != "voided",
        )
    )
    for (order_id,) in result.all():
        paid, refunded = await _get_order_payment_totals(db, tenant_id, order_id)
        if paid - refunded <= 0:
            return True
    return False
