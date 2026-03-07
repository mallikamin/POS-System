"""Order service -- business logic for order lifecycle.

Handles order creation, state machine transitions, price calculation,
and table status synchronization.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import Date, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.customer import Customer
from app.models.floor import Table
from app.models.order import Order, OrderItem, OrderItemModifier, OrderStatusLog
from app.models.restaurant_config import RestaurantConfig
from app.models.table_session import TableSession
from app.schemas.order import OrderCreate, PaymentPreviewResponse
from app.services import customer_service, kitchen_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State Machine
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["confirmed", "voided"],
    "confirmed": ["in_kitchen", "voided"],
    "in_kitchen": ["ready", "voided"],
    "ready": ["served", "voided"],
    "served": ["completed", "voided"],
    "completed": [],
    "voided": [],
}


# ---------------------------------------------------------------------------
# Order Number Generation
# ---------------------------------------------------------------------------


async def generate_order_number(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    """Generate a daily sequential order number: YYMMDD-NNN."""
    now = datetime.now(timezone.utc)
    date_prefix = now.strftime("%y%m%d")

    result = await db.execute(
        select(func.count(Order.id)).where(
            Order.tenant_id == tenant_id,
            func.cast(Order.created_at, Date) == now.date(),
        )
    )
    count = result.scalar_one()
    return f"{date_prefix}-{count + 1:03d}"


# ---------------------------------------------------------------------------
# Tax Calculation
# ---------------------------------------------------------------------------


async def _get_tax_rate(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    """Get the default tax rate in basis points from restaurant config."""
    result = await db.execute(
        select(RestaurantConfig.default_tax_rate).where(
            RestaurantConfig.tenant_id == tenant_id
        )
    )
    rate = result.scalar_one_or_none()
    return rate if rate is not None else 1600  # Default 16%


# ---------------------------------------------------------------------------
# Create Order
# ---------------------------------------------------------------------------


async def create_order(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    data: OrderCreate,
) -> Order:
    """Create an order from cart data.

    Server-side re-calculates subtotal/tax/total for integrity.
    Creates the order with status 'confirmed' and auto-transitions
    to 'in_kitchen'. For dine-in orders, marks the table as occupied.
    """
    tax_rate_bps = await _get_tax_rate(db, tenant_id)

    # Normalize customer_phone to digits-only
    customer_phone = data.customer_phone
    if customer_phone:
        customer_phone = "".join(c for c in customer_phone if c.isdigit()) or None

    # Build order items and compute subtotal server-side
    order_items_data: list[dict] = []
    subtotal = 0

    for item_data in data.items:
        item_total = item_data.unit_price * item_data.quantity
        subtotal += item_total

        item_dict: dict = {
            "menu_item_id": item_data.menu_item_id,
            "name": item_data.name,
            "quantity": item_data.quantity,
            "unit_price": item_data.unit_price,
            "total": item_total,
            "notes": item_data.notes,
            "modifiers": [
                {
                    "modifier_id": mod_data.modifier_id,
                    "name": mod_data.name,
                    "price_adjustment": mod_data.price_adjustment,
                }
                for mod_data in item_data.modifiers
            ],
        }
        order_items_data.append(item_dict)

    tax_amount = round(subtotal * tax_rate_bps / 10_000)
    total = subtotal + tax_amount

    # Retry loop to handle order number race condition under concurrency.
    # The uq_order_tenant_number constraint catches collisions; we regenerate
    # the number and retry within a SAVEPOINT so the outer transaction survives.
    max_retries = 3
    for attempt in range(max_retries):
        order_number = await generate_order_number(db, tenant_id)

        order_items: list[OrderItem] = []
        for item_dict in order_items_data:
            order_item = OrderItem(
                tenant_id=tenant_id,
                menu_item_id=item_dict["menu_item_id"],
                name=item_dict["name"],
                quantity=item_dict["quantity"],
                unit_price=item_dict["unit_price"],
                total=item_dict["total"],
                notes=item_dict["notes"],
                status="pending",
            )
            for mod in item_dict["modifiers"]:
                modifier = OrderItemModifier(
                    tenant_id=tenant_id,
                    modifier_id=mod["modifier_id"],
                    name=mod["name"],
                    price_adjustment=mod["price_adjustment"],
                )
                order_item.modifiers.append(modifier)
            order_items.append(order_item)

        # For dine-in: find or create table session
        table_session_id = None
        waiter_id = None
        if data.order_type == "dine_in" and data.table_id:
            table_session_id = await _resolve_table_session(
                db,
                tenant_id,
                user_id,
                data.table_id,
                waiter_id=data.waiter_id,
            )
            # Inherit waiter from session
            if table_session_id:
                session_result = await db.execute(
                    select(TableSession.assigned_waiter_id).where(
                        TableSession.id == table_session_id
                    )
                )
                waiter_id = session_result.scalar_one_or_none()

        # Resolve customer_id: walk-in default for dine-in/takeaway, lookup for call-center
        customer_id = None
        customer_name = data.customer_name
        if data.order_type in ("dine_in", "takeaway") and not data.customer_name:
            walkin = await db.execute(
                select(Customer).where(
                    Customer.tenant_id == tenant_id,
                    Customer.phone == "0000000000",
                )
            )
            walkin_cust = walkin.scalar_one_or_none()
            if walkin_cust:
                customer_id = walkin_cust.id
                customer_name = "Walk-in Customer"
        elif customer_phone:
            cust_result = await db.execute(
                select(Customer).where(
                    Customer.tenant_id == tenant_id,
                    Customer.phone == customer_phone,
                )
            )
            found_cust = cust_result.scalar_one_or_none()
            if found_cust:
                customer_id = found_cust.id

        order = Order(
            tenant_id=tenant_id,
            order_number=order_number,
            order_type=data.order_type,
            status="confirmed",
            payment_status="unpaid",
            table_id=data.table_id,
            table_session_id=table_session_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_id=customer_id,
            waiter_id=waiter_id,
            subtotal=subtotal,
            tax_amount=tax_amount,
            discount_amount=0,
            total=total,
            notes=data.notes,
            created_by=user_id,
            items=order_items,
        )

        try:
            async with db.begin_nested():
                db.add(order)
                await db.flush()
            break  # Success — exit retry loop
        except IntegrityError:
            if attempt == max_retries - 1:
                raise ValueError("Failed to generate unique order number after retries")
            logger.warning(
                "Order number collision on '%s', retrying (%d/%d)",
                order_number,
                attempt + 1,
                max_retries,
            )
            continue

    # Status log: creation
    log_entry = OrderStatusLog(
        tenant_id=tenant_id,
        order_id=order.id,
        from_status=None,
        to_status="confirmed",
        changed_by=user_id,
    )
    db.add(log_entry)

    # Check payment_flow config
    payment_flow = await _get_payment_flow(db, tenant_id)

    if payment_flow == "pay_first":
        # Pay-before-eat: keep order as confirmed, do NOT send to kitchen
        # Kitchen tickets created after payment in payment_service
        pass
    else:
        # Order-first (default): auto-transition to in_kitchen
        order.status = "in_kitchen"
        for item in order.items:
            item.status = "sent"

        kitchen_log = OrderStatusLog(
            tenant_id=tenant_id,
            order_id=order.id,
            from_status="confirmed",
            to_status="in_kitchen",
            changed_by=user_id,
        )
        db.add(kitchen_log)

    # For dine-in: mark table as occupied
    if data.order_type == "dine_in" and data.table_id:
        table = await _get_table(db, data.table_id, tenant_id)
        if table:
            table.status = "occupied"

    await db.flush()

    if payment_flow != "pay_first":
        # Auto-create kitchen ticket: route all items to the first active station
        await _auto_create_kitchen_ticket(db, tenant_id, order)

    await _sync_customer_stats_for_order(db, tenant_id, order)

    return await get_order(db, order.id, tenant_id)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Read Orders
# ---------------------------------------------------------------------------


async def list_orders(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    status_filter: str | None = None,
    type_filter: str | None = None,
    active_only: bool = False,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Order], int]:
    """List orders with optional filtering and pagination.

    Returns (orders, total_count).
    """
    base = select(Order).where(Order.tenant_id == tenant_id)

    if status_filter:
        base = base.where(Order.status == status_filter)
    if type_filter:
        base = base.where(Order.order_type == type_filter)
    if active_only:
        base = base.where(Order.status.notin_(["completed", "voided"]))

    # Count
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Fetch with items for item_count
    stmt = (
        base.options(
            selectinload(Order.items),
            selectinload(Order.table),
        )
        .order_by(Order.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    orders = list(result.scalars().unique().all())
    return orders, total


async def get_order(
    db: AsyncSession, order_id: uuid.UUID, tenant_id: uuid.UUID
) -> Order | None:
    """Get a single order with all relationships loaded."""
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.modifiers),
            selectinload(Order.table),
            selectinload(Order.creator),
        )
        .where(Order.id == order_id, Order.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# State Transitions
# ---------------------------------------------------------------------------


async def transition_order(
    db: AsyncSession,
    order_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    new_status: str,
) -> Order:
    """Transition an order to a new status.

    Validates against the state machine. On completion of dine-in orders,
    resets the table to available.
    """
    order = await get_order(db, order_id, tenant_id)
    if order is None:
        raise ValueError("Order not found")

    current = order.status
    allowed = VALID_TRANSITIONS.get(current, [])
    if new_status not in allowed:
        raise ValueError(
            f"Cannot transition from '{current}' to '{new_status}'. Allowed: {allowed}"
        )

    # Pay-first guard: block confirmed→in_kitchen without payment
    if current == "confirmed" and new_status == "in_kitchen":
        payment_flow = await _get_payment_flow(db, tenant_id)
        if payment_flow == "pay_first":
            from app.models.payment import Payment

            paid_result = await db.execute(
                select(func.count(Payment.id)).where(
                    Payment.order_id == order_id,
                    Payment.tenant_id == tenant_id,
                    Payment.kind == "payment",
                    Payment.status == "completed",
                )
            )
            if paid_result.scalar_one() == 0:
                raise ValueError(
                    "This order is pending payment. Please complete payment first — "
                    "go to the order and click Pay to proceed."
                )

    order.status = new_status

    log_entry = OrderStatusLog(
        tenant_id=tenant_id,
        order_id=order.id,
        from_status=current,
        to_status=new_status,
        changed_by=user_id,
    )
    db.add(log_entry)

    # On completion: free the table
    if new_status == "completed" and order.order_type == "dine_in" and order.table_id:
        table = await _get_table(db, order.table_id, tenant_id)
        if table:
            table.status = "available"

    await db.flush()
    await _sync_customer_stats_for_order(db, tenant_id, order)
    # Force fresh load with all relationships by fetching anew
    order_id = order.id
    db.expunge(order)
    return await get_order(db, order_id, tenant_id)  # type: ignore[return-value]


async def void_order(
    db: AsyncSession,
    order_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    reason: str | None = None,
) -> Order:
    """Void an order (admin only — role check at route level).

    Any non-terminal status can be voided. Frees the table if dine-in.
    """
    order = await get_order(db, order_id, tenant_id)
    if order is None:
        raise ValueError("Order not found")

    if order.status in ("completed", "voided"):
        raise ValueError(f"Cannot void an order with status '{order.status}'")

    old_status = order.status
    order.status = "voided"

    log_entry = OrderStatusLog(
        tenant_id=tenant_id,
        order_id=order.id,
        from_status=old_status,
        to_status="voided",
        changed_by=user_id,
        note=reason,
    )
    db.add(log_entry)

    # Free the table if dine-in
    if order.order_type == "dine_in" and order.table_id:
        table = await _get_table(db, order.table_id, tenant_id)
        if table:
            table.status = "available"

    await db.flush()
    await _sync_customer_stats_for_order(db, tenant_id, order)
    order_id = order.id
    db.expunge(order)
    return await get_order(db, order_id, tenant_id)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _auto_create_kitchen_ticket(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order: Order,
) -> None:
    """Create a kitchen ticket for an order, routing all items to the first active station."""
    stations = await kitchen_service.list_stations(db, tenant_id, active_only=True)
    if not stations:
        logger.warning(
            "No active kitchen stations — skipping ticket creation for order %s",
            order.id,
        )
        return

    station = stations[0]  # Route to first active station (Main Kitchen)
    item_quantities = [(item.id, item.quantity) for item in order.items]
    if not item_quantities:
        return

    await kitchen_service.create_ticket_for_order(
        db,
        tenant_id,
        order.id,
        station.id,
        item_quantities,
    )


async def _get_payment_flow(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    """Get the payment_flow setting from restaurant config."""
    result = await db.execute(
        select(RestaurantConfig.payment_flow).where(
            RestaurantConfig.tenant_id == tenant_id
        )
    )
    flow = result.scalar_one_or_none()
    return flow if flow else "order_first"


async def _get_table(
    db: AsyncSession, table_id: uuid.UUID, tenant_id: uuid.UUID
) -> Table | None:
    result = await db.execute(
        select(Table).where(Table.id == table_id, Table.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def _sync_customer_stats_for_order(
    db: AsyncSession, tenant_id: uuid.UUID, order: Order
) -> None:
    if order.customer_id is None:
        return

    customer = await customer_service.get_customer(db, order.customer_id, tenant_id)
    if customer is None:
        return

    await customer_service.update_customer_stats(db, tenant_id, customer)


async def _resolve_table_session(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    table_id: uuid.UUID,
    waiter_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Find an open session for this table, or create one. Returns session id."""
    result = await db.execute(
        select(TableSession)
        .where(
            TableSession.tenant_id == tenant_id,
            TableSession.table_id == table_id,
            TableSession.status == "open",
        )
        .limit(1)
    )
    session = result.scalar_one_or_none()
    if session is not None:
        return session.id

    session = TableSession(
        tenant_id=tenant_id,
        table_id=table_id,
        status="open",
        opened_by=user_id,
        assigned_waiter_id=waiter_id,
    )
    db.add(session)
    await db.flush()
    return session.id


# ---------------------------------------------------------------------------
# Payment Preview (dual totals by method-specific tax)
# ---------------------------------------------------------------------------


async def get_payment_preview(
    db: AsyncSession, order_id: uuid.UUID, tenant_id: uuid.UUID
) -> PaymentPreviewResponse | None:
    """Compute cash and card totals for an order using method-specific tax rates."""
    order = await get_order(db, order_id, tenant_id)
    if order is None:
        return None

    # Fetch per-method tax rates from config
    result = await db.execute(
        select(
            RestaurantConfig.cash_tax_rate_bps,
            RestaurantConfig.card_tax_rate_bps,
        ).where(RestaurantConfig.tenant_id == tenant_id)
    )
    row = result.one_or_none()
    cash_rate = row.cash_tax_rate_bps if row else 1600
    card_rate = row.card_tax_rate_bps if row else 500

    subtotal = order.subtotal
    cash_tax = round(subtotal * cash_rate / 10_000)
    card_tax = round(subtotal * card_rate / 10_000)

    return PaymentPreviewResponse(
        order_id=order.id,
        subtotal=subtotal,
        cash_tax_rate_bps=cash_rate,
        cash_tax_amount=cash_tax,
        cash_total=subtotal + cash_tax,
        card_tax_rate_bps=card_rate,
        card_tax_amount=card_tax,
        card_total=subtotal + card_tax,
    )
