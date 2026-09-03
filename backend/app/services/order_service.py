"""Order service -- business logic for order lifecycle.

Handles order creation, state machine transitions, price calculation,
and table status synchronization.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
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


#: Letter stamped into an online order's number so the fulfilment type is
#: readable at a glance on the printed receipt (Imran, 2026-08-04), and since
#: 2026-09-03 the key to its OWN daily sequence (Imran, matching what EposNow
#: gave him): `260903-C001` first collection, `260903-D001` first delivery.
SERVICE_TYPE_MARKERS = {"collection": "C", "delivery": "D"}


async def generate_order_number(
    db: AsyncSession, tenant_id: uuid.UUID, service_type: str | None = None
) -> str:
    """Generate a daily sequential order number: `YYMMDD-NNN`, or `YYMMDD-XNNN`.

    **One counter per fulfilment type per tenant per day** (Imran, 2026-09-03).
    Collection and delivery each run their own sequence, so a delivery order
    followed by a collection order reads `260903-D001` then `260903-C001`, and
    a third order that is a collection reads `260903-C002`.

    This REPLACES the shared counter shipped on 2026-08-04, where the letter
    was only a category marker on one sequence (`260903-D001`, `260903-C002`).
    What it costs: the highest number on the pass is no longer "how many orders
    today", it is how many of that type. Imran asked for the numbering his till
    gives him, and that one is per type.

    `service_type` is only set on online orders. Every other channel (dine-in,
    takeaway, call centre) passes `None`, keeps the plain `YYMMDD-NNN`, and now
    runs its own sequence too.
    """
    now = datetime.now(timezone.utc)
    date_prefix = now.strftime("%y%m%d")
    marker = SERVICE_TYPE_MARKERS.get((service_type or "").lower(), "")

    # Serialise allocation on the tenant's own config row. Reading the highest
    # issued number and then inserting is a read-modify-write, so without this
    # two customers checking out in the same instant both read the same value
    # and both take it. The lock is held only until the caller commits, which
    # for an order is milliseconds, and it is per-tenant so one restaurant's
    # traffic cannot block another's.
    #
    # SQLite (tests) does not support FOR UPDATE and SQLAlchemy omits it there;
    # the tests are single-threaded, so nothing is lost.
    await db.execute(
        select(RestaurantConfig.id)
        .where(RestaurantConfig.tenant_id == tenant_id)
        .with_for_update()
    )

    # ⚠️ Allocated from the highest number ALREADY ISSUED today CARRYING THE
    # SAME LETTER, not from `count(*)`.
    #
    # `count(*) + 1` was wrong in two ways. It collides whenever two customers
    # check out in the same instant -- both count N and both take N+1 -- and
    # while the `uq_order_tenant_number` constraint used to reject the loser,
    # the C/D marker broke even that accidental safety net: a collection and a
    # delivery order colliding produce `-C006` and `-D006`, which are different
    # strings, so both save and the counter silently forks.
    #
    # Reading the max issued value is also self-healing: a deleted or voided
    # row no longer rewinds the counter onto a number that has already been
    # printed on a receipt.
    #
    # Scoping the read to one letter is what makes the sequences independent,
    # and it is why switching over mid-day is safe: each letter continues from
    # its own high-water mark, so no number issued under the old shared counter
    # can ever be handed out a second time.
    result = await db.execute(
        select(Order.order_number).where(
            Order.tenant_id == tenant_id,
            Order.order_number.like(f"{date_prefix}-{marker}%"),
        )
    )
    highest = 0
    for issued in result.scalars():
        tail = issued.split("-", 1)[1] if "-" in issued else ""
        if marker:
            if not tail.startswith(marker):
                continue
            digits = tail[len(marker) :]
        else:
            # No letter asked for: the plain sequence. A lettered number is not
            # all digits, so it drops out here and cannot bump this counter.
            digits = tail
        if digits.isdigit():
            highest = max(highest, int(digits))

    return f"{date_prefix}-{marker}{highest + 1:03d}"


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


async def _get_tax_settings(
    db: AsyncSession, tenant_id: uuid.UUID
) -> tuple[int, bool]:
    """Return `(rate_bps, prices_include_tax)` for the tenant.

    `tax_inclusive` defaults to True, matching the column default and
    `tax_invoice_service`, so a tenant with no config row is treated the same
    way in both places rather than two subsystems disagreeing by default.
    """
    result = await db.execute(
        select(
            RestaurantConfig.default_tax_rate,
            RestaurantConfig.tax_inclusive,
        ).where(RestaurantConfig.tenant_id == tenant_id)
    )
    row = result.one_or_none()
    if row is None:
        return 1600, True
    return (
        row.default_tax_rate if row.default_tax_rate is not None else 1600,
        True if row.tax_inclusive is None else bool(row.tax_inclusive),
    )


def compute_tax(subtotal: int, rate_bps: int, prices_include_tax: bool) -> tuple[int, int]:
    """Split a subtotal into `(tax_amount, total)`, both integer minor units.

    🔴 UAT finding F19, 2026-08-28. This used to be two unconditional lines:

        tax_amount = round(subtotal * rate_bps / 10_000)
        total = subtotal + tax_amount

    which is only correct when prices EXCLUDE tax. `restaurant_configs.tax_inclusive`
    existed, defaulted to True, and was read by exactly one service
    (`tax_invoice_service`) -- the order path never consulted it. So a tenant whose
    menu prices already contain VAT had that VAT charged a second time: three
    croissants on a AED 9.00 board came to AED 28.35 instead of AED 27.00, and the
    A4 tax invoice (which DID back the VAT out) disagreed with the amount actually
    taken.

    When prices include tax, the tax is the part already inside the price:

        net = round(subtotal / (1 + rate))      total  = subtotal
        tax = subtotal - net                    invoice shows `tax` within `total`

    Derived by subtraction, never as `net * rate`, so `net + tax == subtotal`
    exactly and no rounding remainder can appear or vanish.

    ⚠️ At `rate_bps == 0` both branches return `(0, subtotal)`. That is not a
    coincidence to rely on silently, it is the reason this change is safe to ship
    to a live tenant: Chick Shack runs `default_tax_rate = 0`, so their totals are
    provably byte-identical before and after. There is a test pinning it.
    """
    if rate_bps <= 0:
        return 0, subtotal

    if prices_include_tax:
        net = round(subtotal * 10_000 / (10_000 + rate_bps))
        return subtotal - net, subtotal

    tax_amount = round(subtotal * rate_bps / 10_000)
    return tax_amount, subtotal + tax_amount


def net_of_tax(amount: int, rate_bps: int, prices_include_tax: bool) -> int:
    """The part of `amount` that is the business's own revenue, in minor units.

    UAT finding F13. Food Cost % was `cost / menu_price`, and for a tax-inclusive
    tenant the menu price contains VAT that is collected for the tax authority,
    not earned. Dividing by it understates food cost on every costed item (AED
    1.22 on a 9.00 croissant read 13.58% instead of 14.26% at 5%), and the error
    grows with the rate. Derived from `compute_tax` so there is exactly one place
    that knows how a price and its tax relate; when prices exclude tax the price
    already is the net figure and comes back unchanged.
    """
    tax_amount, _ = compute_tax(amount, rate_bps, prices_include_tax)
    return amount - tax_amount if prices_include_tax else amount


def order_total(order: Order, prices_include_tax: bool) -> int:
    """What the customer pays for an order, from its stored parts.

    One rule, used everywhere an order is re-totalled (payment-mode retax,
    discount sync, split allocations), because every place that wrote its own
    version got at least one of these wrong:

        goods  = subtotal                (prices include tax, F19)
               = subtotal + tax_amount   (prices exclude tax)
        total  = goods + delivery_fee + service_fee + tip - discount_amount

    Fees and the tip ride OUTSIDE the tax, exactly as `public_order_service`
    has always charged them on the online channel; the POS charges added for
    Martin (FZ LLC, 2026-09-02) follow the same rule so the two channels cannot
    quote different totals for the same basket and fee.
    """
    goods_total = (
        order.subtotal if prices_include_tax else order.subtotal + order.tax_amount
    )
    extras = (order.delivery_fee or 0) + (order.service_fee or 0) + (order.tip or 0)
    return goods_total + extras - (order.discount_amount or 0)


# ---------------------------------------------------------------------------
# Create Order
# ---------------------------------------------------------------------------


async def _resolve_sale_attribution(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    location_id: uuid.UUID | None,
    sales_channel_id: uuid.UUID | None,
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """Which site made this sale, and which channel it came through.

    Both are OPTIONAL capabilities, on exactly the contract
    `_apply_inventory_and_commission` already uses at the other end of the
    lifecycle: a tenant that has never configured locations -- which is every
    tenant except martin-fz, chick-shack included -- must create orders exactly
    as it always has. So a tenant with no locations gets NULL and no error.

    The two failure modes are deliberately NOT symmetric:

    * An id the caller **passed explicitly** that does not belong to this
      tenant is a client error and raises. Silently substituting the default
      site would attribute a sale, and its VAT, to the wrong registered entity.
    * An id **omitted** falls back to the tenant's default location, because
      the alternative is the tax invoice this system already shipped: no TRN
      at all on a legal document (F31).
    """
    from app.models.location import Location, SalesChannel
    from app.services.stock_service import StockError, resolve_location

    resolved_location: uuid.UUID | None = None
    if location_id is not None:
        try:
            resolved_location = (
                await resolve_location(db, tenant_id, location_id)
            ).id
        except StockError as exc:
            raise ValueError(str(exc)) from exc
    else:
        has_locations = (
            await db.execute(
                select(Location.id).where(Location.tenant_id == tenant_id).limit(1)
            )
        ).scalar_one_or_none()
        if has_locations is not None:
            try:
                resolved_location = (await resolve_location(db, tenant_id, None)).id
            except StockError as exc:
                # Several sites and none flagged default: refusing to guess is
                # correct, but it must not refuse the sale.
                logger.warning(
                    "Sale not attributed to a location for tenant %s: %s",
                    tenant_id,
                    exc,
                )

    resolved_channel: uuid.UUID | None = None
    if sales_channel_id is not None:
        channel = (
            await db.execute(
                select(SalesChannel.id).where(
                    SalesChannel.id == sales_channel_id,
                    SalesChannel.tenant_id == tenant_id,
                    SalesChannel.is_active == True,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if channel is None:
            raise ValueError("No such sales channel for this restaurant.")
        resolved_channel = channel

    return resolved_location, resolved_channel


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
    tax_rate_bps, prices_include_tax = await _get_tax_settings(db, tenant_id)

    # Attribute the sale before anything is written, so an unknown location or
    # channel is rejected before an order number is burned.
    sale_location_id, sale_channel_id = await _resolve_sale_attribution(
        db, tenant_id, data.location_id, data.sales_channel_id
    )

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

    tax_amount, goods_total = compute_tax(subtotal, tax_rate_bps, prices_include_tax)
    # Charges added at the till (Martin, FZ LLC 2026-09-02: "option to add
    # charges such as delivery fees"). Outside the tax, same as the online
    # channel; see `order_total` for the one rule.
    delivery_fee = data.delivery_fee or 0
    service_fee = data.service_fee or 0
    total = goods_total + delivery_fee + service_fee

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
            location_id=sale_location_id,
            sales_channel_id=sale_channel_id,
            subtotal=subtotal,
            tax_amount=tax_amount,
            discount_amount=0,
            delivery_fee=delivery_fee,
            service_fee=service_fee,
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

    # Online-order guard: a placed online order is ACCEPTED, never merely
    # "sent to kitchen". Accepting (public_order_service.accept_order) is what
    # gives the customer their ETA, captures a card authorisation, notifies
    # them and prints the kitchen ticket. This generic transition does none of
    # that, so allowing it here would cook food that was never charged for.
    if (
        order.order_type == "online"
        and current == "confirmed"
        and new_status == "in_kitchen"
    ):
        raise ValueError(
            "This is an online order awaiting acceptance. Accept it from the "
            "Online Orders queue so the customer is notified and any card "
            "payment is captured."
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

    if new_status == "completed":
        await _apply_inventory_and_commission(db, tenant_id, order)
    await _sync_customer_stats_for_order(db, tenant_id, order)
    # Force fresh load with all relationships by fetching anew
    order_id = order.id
    db.expunge(order)
    return await get_order(db, order_id, tenant_id)  # type: ignore[return-value]


async def _apply_inventory_and_commission(
    db: AsyncSession, tenant_id: uuid.UUID, order: Order
) -> None:
    """On completion: deduct the recipe ingredients and freeze the commission.

    Both are OPTIONAL capabilities. A tenant that has never configured locations
    or recipes -- which is every existing tenant, chick-shack included -- must
    complete orders exactly as it always has. Stock tracking must never be able
    to block a sale from closing: an inventory problem is a bookkeeping problem,
    and a till that refuses to finish an order because of one is a worse
    outcome than a stock figure that needs correcting.
    """
    from app.models.location import Location
    from app.services import location_service, production_service
    from app.services.stock_service import StockError

    has_locations = (
        await db.execute(
            select(Location.id).where(Location.tenant_id == tenant_id).limit(1)
        )
    ).scalar_one_or_none()
    if has_locations is None:
        return  # Single-site tenant, nothing to do. The pre-locations behaviour.

    try:
        await production_service.consume_for_order(
            db, tenant_id=tenant_id, order_id=order.id
        )
    except StockError as exc:
        # Recorded, never raised. See the docstring.
        logger.warning(
            "Stock deduction skipped for order %s: %s", order.order_number, exc
        )

    try:
        await location_service.snapshot_commission(db, tenant_id, order)
    except StockError as exc:
        logger.warning(
            "Commission snapshot skipped for order %s: %s", order.order_number, exc
        )


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
            RestaurantConfig.tax_inclusive,
        ).where(RestaurantConfig.tenant_id == tenant_id)
    )
    row = result.one_or_none()
    cash_rate = row.cash_tax_rate_bps if row else 1600
    card_rate = row.card_tax_rate_bps if row else 500
    # Same default as `_get_tax_settings` and `tax_invoice_service`, so a tenant
    # with no config row is treated identically everywhere (F19).
    prices_include_tax = True if row is None else bool(row.tax_inclusive)

    subtotal = order.subtotal
    cash_tax, cash_goods = compute_tax(subtotal, cash_rate, prices_include_tax)
    card_tax, card_goods = compute_tax(subtotal, card_rate, prices_include_tax)
    # Fees and tip are outside the tax, so they are the same under either
    # method and simply ride on top (see `order_total`).
    extras = (order.delivery_fee or 0) + (order.service_fee or 0) + (order.tip or 0)

    return PaymentPreviewResponse(
        order_id=order.id,
        subtotal=subtotal,
        cash_tax_rate_bps=cash_rate,
        cash_tax_amount=cash_tax,
        cash_total=cash_goods + extras,
        card_tax_rate_bps=card_rate,
        card_tax_amount=card_tax,
        card_total=card_goods + extras,
        delivery_fee=order.delivery_fee or 0,
        service_fee=order.service_fee or 0,
        tip=order.tip or 0,
    )
