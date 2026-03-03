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
            target_subtotal = await _get_target_subtotal(db, tenant_id, order_id, table_session_id)
            resolved_amount = round(target_subtotal * dt.value / 10_000)
            percent_bps = dt.value
            if label is None:
                resolved_label = f"{dt.name} ({dt.value / 100:.1f}%)"
        else:
            # fixed discount
            resolved_amount = amount if amount is not None else dt.value

    if resolved_amount <= 0:
        raise ValueError("Discount amount must be > 0")

    # Validate: discount cannot exceed remaining applicable amount
    target_subtotal = await _get_target_subtotal(db, tenant_id, order_id, table_session_id)
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
        db, tenant_id, resolved_amount, percent_bps, target_subtotal,
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
    await db.delete(od)
    await db.flush()

    # Re-sync rollup
    if order_id:
        await _sync_order_discount(db, tenant_id, order_id)


# ---------------------------------------------------------------------------
# List Discounts on Order
# ---------------------------------------------------------------------------

async def list_order_discounts(
    db: AsyncSession, tenant_id: uuid.UUID, order_id: uuid.UUID
) -> list[OrderDiscount]:
    result = await db.execute(
        select(OrderDiscount).where(
            OrderDiscount.tenant_id == tenant_id,
            OrderDiscount.order_id == order_id,
        ).order_by(OrderDiscount.created_at)
    )
    return list(result.scalars().all())


async def list_session_discounts(
    db: AsyncSession, tenant_id: uuid.UUID, session_id: uuid.UUID
) -> list[OrderDiscount]:
    result = await db.execute(
        select(OrderDiscount).where(
            OrderDiscount.tenant_id == tenant_id,
            OrderDiscount.table_session_id == session_id,
        ).order_by(OrderDiscount.created_at)
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
        from app.models.table_session import TableSession
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
    stmt = select(OrderDiscount.amount).where(
        OrderDiscount.tenant_id == tenant_id
    )
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
    """Update the order.discount_amount and order.total to reflect applied discounts."""
    total_discount = await _get_existing_discount_total(db, tenant_id, order_id, None)
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.tenant_id == tenant_id)
    )
    order = result.scalar_one_or_none()
    if order:
        order.discount_amount = total_discount
        order.total = order.subtotal + order.tax_amount - total_discount
        await db.flush()
