"""Business logic for the public storefront: menu read + order placement.

⚠️ EVERY PRICE ON THE RESULTING ORDER IS COMPUTED HERE, FROM THE DATABASE. ⚠️

The request carries menu item IDs, modifier IDs and quantities. Nothing else is
trusted. In particular the browser never supplies a unit price, a line total, a
delivery fee or a tax amount, because anyone on the internet can POST to this
endpoint. Contrast `order_service.create_order`, which accepts `unit_price` from
the caller -- acceptable for an authenticated till, not for this.

Validation is deliberately strict and fails the whole order rather than
silently dropping a bad line. A basket that references an unavailable item is a
stale browser tab, and the customer needs to see that before they pay, not
after.
"""

import logging
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.customer import Customer
from app.models.delivery import DeliveryArea
from app.models.menu import Category, MenuItem, Modifier
from app.models.order import Order, OrderItem, OrderItemModifier, OrderStatusLog
from app.models.restaurant_config import RestaurantConfig
from app.models.user import Role, User
from app.models.tenant import Tenant
from app.schemas.public_order import PublicOrderCreate
from app.services import email_service, order_service
from app.utils.security import hash_password

logger = logging.getLogger(__name__)

ONLINE_SYSTEM_EMAIL = "online-orders@system.local"


class PublicOrderError(Exception):
    """Rejected for a reason the customer should see. Maps to HTTP 409."""


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------


async def get_public_menu(db: AsyncSession, tenant_id: uuid.UUID) -> tuple[str, list[Category]]:
    """Active categories with available items only.

    Unavailable items and modifiers are OMITTED rather than flagged, so a stale
    tab cannot offer something the kitchen has turned off.
    """
    result = await db.execute(
        select(Category)
        .where(Category.tenant_id == tenant_id, Category.is_active.is_(True))
        .options(
            selectinload(Category.items).selectinload(MenuItem.modifier_groups)
        )
        .order_by(Category.display_order, Category.name)
    )
    categories = list(result.scalars().unique())

    for cat in categories:
        cat.items = sorted(
            (i for i in cat.items if i.is_available),
            key=lambda i: (i.display_order, i.name),
        )
        for item in cat.items:
            item.modifier_groups = [g for g in item.modifier_groups if g.is_active]
            for group in item.modifier_groups:
                group.modifiers = [m for m in group.modifiers if m.is_available]

    categories = [c for c in categories if c.items]

    currency = await get_currency(db, tenant_id)
    return currency, categories


async def get_currency(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    result = await db.execute(
        select(RestaurantConfig.currency).where(
            RestaurantConfig.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none() or "PKR"


async def get_shop_name(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    """Display name for customer-facing email. The tenant's own name."""
    result = await db.execute(select(Tenant.name).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none() or "Your restaurant"


async def notify_customer(
    db: AsyncSession, tenant_id: uuid.UUID, order: Order, event: str
) -> bool:
    """Email the customer about their order. Never raises.

    ⚠️ **Call this AFTER `db.commit()`, never before.** An email announcing an
    order that then failed to commit cannot be recalled, and the customer would
    be holding a confirmation for something that does not exist.
    """
    currency = await get_currency(db, tenant_id)
    shop_name = await get_shop_name(db, tenant_id)
    return await email_service.send_order_email(
        order, event, shop_name=shop_name, currency=currency
    )


# ---------------------------------------------------------------------------
# The system user that owns online orders
# ---------------------------------------------------------------------------


async def _get_or_create_online_user(db: AsyncSession, tenant_id: uuid.UUID) -> User:
    """Resolve the non-login user that public orders are attributed to.

    `Order.created_by` is NOT NULL and FKs to users, and it is relied on by
    reports, the audit trail and the status log. Making it nullable would ripple
    through all of those, so online orders get a dedicated owner instead. That
    also reads better on a report than a blank column: the channel is visible.

    The account is created `is_active=False` with a random unusable password and
    no PIN. That matters for more than tidiness -- `authenticate_by_pin` loops
    ACTIVE users and returns the first bcrypt match, so an inactive account with
    no PIN cannot participate in a PIN collision.
    """
    result = await db.execute(
        select(User).where(
            User.tenant_id == tenant_id, User.email == ONLINE_SYSTEM_EMAIL
        )
    )
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    role_result = await db.execute(
        select(Role)
        .where(Role.tenant_id == tenant_id, Role.is_active.is_(True))
        .order_by(Role.name)
        .limit(1)
    )
    role = role_result.scalar_one_or_none()
    if role is None:
        raise PublicOrderError("Restaurant is not configured to take online orders.")

    user = User(
        tenant_id=tenant_id,
        email=ONLINE_SYSTEM_EMAIL,
        full_name="Online Orders",
        # Random and discarded: this account must never be logged into.
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        pin_code=None,
        is_active=False,
        role_id=role.id,
    )
    db.add(user)
    await db.flush()
    logger.info("Created online-orders system user for tenant %s", tenant_id)
    return user


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------


async def _price_basket(
    db: AsyncSession, tenant_id: uuid.UUID, data: PublicOrderCreate
) -> tuple[list[dict], int]:
    """Re-derive every line from the database. Returns (lines, subtotal).

    Raises PublicOrderError on anything that does not add up.
    """
    requested_item_ids = {line.menu_item_id for line in data.items}

    item_result = await db.execute(
        select(MenuItem)
        .where(
            MenuItem.tenant_id == tenant_id,
            MenuItem.id.in_(requested_item_ids),
            MenuItem.is_available.is_(True),
        )
        .options(selectinload(MenuItem.modifier_groups))
    )
    items_by_id = {i.id: i for i in item_result.scalars().unique()}

    missing = requested_item_ids - items_by_id.keys()
    if missing:
        raise PublicOrderError(
            "Some items are no longer available. Please refresh the menu and try again."
        )

    # Every modifier referenced anywhere in the basket, fetched once.
    requested_modifier_ids = {
        mid for line in data.items for mid in line.modifier_ids
    }
    modifiers_by_id: dict[uuid.UUID, Modifier] = {}
    if requested_modifier_ids:
        mod_result = await db.execute(
            select(Modifier).where(
                Modifier.tenant_id == tenant_id,
                Modifier.id.in_(requested_modifier_ids),
                Modifier.is_available.is_(True),
            )
        )
        modifiers_by_id = {m.id: m for m in mod_result.scalars()}

        missing_mods = requested_modifier_ids - modifiers_by_id.keys()
        if missing_mods:
            raise PublicOrderError(
                "Some options are no longer available. "
                "Please refresh the menu and try again."
            )

    lines: list[dict] = []
    subtotal = 0

    for line in data.items:
        item = items_by_id[line.menu_item_id]
        allowed_group_ids = {g.id: g for g in item.modifier_groups if g.is_active}

        chosen: list[Modifier] = []
        per_group_count: dict[uuid.UUID, int] = {}

        for mid in line.modifier_ids:
            modifier = modifiers_by_id[mid]
            # A modifier is only valid if its group is actually attached to THIS
            # item. Without this check a caller could apply the -400 "Half
            # serving" discount from one item to any other item on the menu.
            if modifier.group_id not in allowed_group_ids:
                raise PublicOrderError(
                    f"'{modifier.name}' is not a valid option for '{item.name}'."
                )
            chosen.append(modifier)
            per_group_count[modifier.group_id] = (
                per_group_count.get(modifier.group_id, 0) + 1
            )

        for group_id, group in allowed_group_ids.items():
            count = per_group_count.get(group_id, 0)
            if count < group.min_selections:
                raise PublicOrderError(
                    f"'{item.name}' needs at least {group.min_selections} "
                    f"choice(s) from {group.name}."
                )
            # max_selections == 0 means unlimited, per the menu engine's convention.
            if group.max_selections and count > group.max_selections:
                raise PublicOrderError(
                    f"'{item.name}' allows at most {group.max_selections} "
                    f"choice(s) from {group.name}."
                )

        unit_price = item.price + sum(m.price_adjustment for m in chosen)
        if unit_price < 0:
            # Negative-priced modifiers are legitimate (a "Half serving"
            # discount exists in the seed menu), but a line that costs less
            # than nothing is a menu misconfiguration, not a valid order.
            raise PublicOrderError(
                f"'{item.name}' is misconfigured and cannot be ordered online."
            )

        line_total = unit_price * line.quantity
        subtotal += line_total

        lines.append(
            {
                "menu_item_id": item.id,
                "name": item.name,
                "quantity": line.quantity,
                "unit_price": unit_price,
                "total": line_total,
                "notes": line.notes,
                "modifiers": [
                    {
                        "modifier_id": m.id,
                        "name": m.name,
                        "price_adjustment": m.price_adjustment,
                    }
                    for m in chosen
                ],
            }
        )

    return lines, subtotal


async def _resolve_delivery(
    db: AsyncSession, tenant_id: uuid.UUID, data: PublicOrderCreate, subtotal: int
) -> tuple[int, str | None]:
    """Look the delivery fee up server-side. Returns (fee, area_name)."""
    if data.service_type != "delivery":
        return 0, None

    result = await db.execute(
        select(DeliveryArea).where(
            DeliveryArea.tenant_id == tenant_id,
            DeliveryArea.code == data.delivery_area_id,
            DeliveryArea.is_active.is_(True),
        )
    )
    area = result.scalar_one_or_none()
    if area is None:
        raise PublicOrderError("We do not deliver to that area.")

    config_result = await db.execute(
        select(RestaurantConfig.delivery_minimum).where(
            RestaurantConfig.tenant_id == tenant_id
        )
    )
    minimum = config_result.scalar_one_or_none() or 0
    # Checked against the goods subtotal, excluding the delivery fee -- charging
    # the fee then counting it towards the minimum would be circular.
    if minimum and subtotal < minimum:
        raise PublicOrderError(
            f"Minimum order for delivery is {minimum / 100:.2f}."
        )

    return area.fee, area.name


# ---------------------------------------------------------------------------
# Order creation
# ---------------------------------------------------------------------------


async def create_public_order(
    db: AsyncSession, tenant_id: uuid.UUID, data: PublicOrderCreate
) -> Order:
    """Place an order from the public storefront.

    The order lands as `confirmed` + `unpaid` and does NOT go to the kitchen.
    An online order is a request until the shop accepts it -- see
    `accept_order` / `reject_order`. This is the merchant accept/reject gate the
    client asked for, and it is also why no kitchen ticket is created here.
    """
    lines, subtotal = await _price_basket(db, tenant_id, data)
    delivery_fee, area_name = await _resolve_delivery(db, tenant_id, data, subtotal)

    tax_rate_bps = await order_service._get_tax_rate(db, tenant_id)
    # Tax is charged on goods, not on the delivery fee.
    tax_amount = round(subtotal * tax_rate_bps / 10_000)
    total = subtotal + tax_amount + delivery_fee

    system_user = await _get_or_create_online_user(db, tenant_id)

    phone = "".join(c for c in data.customer_phone if c.isdigit()) or None
    email = (data.customer_email or "").strip() or None
    customer_id = await _link_customer(db, tenant_id, data.customer_name, phone, email)

    order_items: list[OrderItem] = []
    for line in lines:
        order_item = OrderItem(
            tenant_id=tenant_id,
            menu_item_id=line["menu_item_id"],
            name=line["name"],
            quantity=line["quantity"],
            unit_price=line["unit_price"],
            total=line["total"],
            notes=line["notes"],
            status="pending",
        )
        for mod in line["modifiers"]:
            order_item.modifiers.append(
                OrderItemModifier(
                    tenant_id=tenant_id,
                    modifier_id=mod["modifier_id"],
                    name=mod["name"],
                    price_adjustment=mod["price_adjustment"],
                )
            )
        order_items.append(order_item)

    order = Order(
        tenant_id=tenant_id,
        order_number=await order_service.generate_order_number(db, tenant_id),
        order_type="online",
        status="confirmed",
        payment_status="unpaid",
        customer_name=data.customer_name,
        customer_phone=phone,
        customer_email=email,
        customer_id=customer_id,
        subtotal=subtotal,
        tax_amount=tax_amount,
        discount_amount=0,
        total=total,
        notes=data.notes,
        service_type=data.service_type,
        delivery_address=data.delivery_address,
        delivery_area=area_name,
        delivery_fee=delivery_fee,
        created_by=system_user.id,
        items=order_items,
    )
    db.add(order)
    await db.flush()

    db.add(
        OrderStatusLog(
            tenant_id=tenant_id,
            order_id=order.id,
            from_status=None,
            to_status="confirmed",
            changed_by=system_user.id,
        )
    )
    await db.flush()

    return await order_service.get_order(db, order.id, tenant_id)  # type: ignore[return-value]


async def _link_customer(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    name: str,
    phone: str | None,
    email: str | None = None,
) -> uuid.UUID | None:
    """Attach to an existing customer by phone, or create one.

    Phone is normalised to digits here because `create_customer` and
    `update_customer` both do the same -- a mismatch would silently break order
    history joins, which has happened before on this codebase.

    An email supplied at checkout fills a BLANK customer email but never
    overwrites one that is already there: a shared household phone number would
    otherwise let one person's order quietly rewrite another's contact details.
    The order keeps its own copy regardless, which is what confirmations use.
    """
    if not phone:
        return None

    result = await db.execute(
        select(Customer).where(
            Customer.tenant_id == tenant_id, Customer.phone == phone
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        if email and not existing.email:
            existing.email = email
            await db.flush()
        return existing.id

    customer = Customer(tenant_id=tenant_id, name=name, phone=phone, email=email)
    db.add(customer)
    await db.flush()
    return customer.id


# ---------------------------------------------------------------------------
# Merchant accept / reject
# ---------------------------------------------------------------------------


async def accept_order(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    user_id: uuid.UUID,
    eta_minutes: int,
) -> Order:
    """Accept an online order and send it to the kitchen."""
    order = await _get_pending_online_order(db, tenant_id, order_id)

    order.accepted_at = datetime.now(timezone.utc)
    order.eta_minutes = eta_minutes
    order.status = "in_kitchen"
    for item in order.items:
        item.status = "sent"

    db.add(
        OrderStatusLog(
            tenant_id=tenant_id,
            order_id=order.id,
            from_status="confirmed",
            to_status="in_kitchen",
            changed_by=user_id,
        )
    )
    await db.flush()

    await order_service._auto_create_kitchen_ticket(db, tenant_id, order)
    return await order_service.get_order(db, order.id, tenant_id)  # type: ignore[return-value]


async def advance_order(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    user_id: uuid.UUID,
    to_status: str,
) -> Order:
    """Move an accepted online order along the rest of its life.

    This is the half that was missing. Accept moved an order to `in_kitchen`
    and nothing moved it again, so the shop's Active tab grew forever and a
    day's takings never settled. The client raised it independently
    ("a button ... that would say out for delivery").

    No new state machine: `ready -> served -> completed` already exists and is
    what the dine-in floor uses. Only two steps are exposed here, because only
    two mean anything to a takeaway:

      `ready`      food is made. Out for delivery, or ready on the counter.
      `completed`  handed over. The order is done and leaves the queue.

    `served` is passed through on the way to `completed` rather than being a
    button of its own -- for a delivery there is no moment between "handed to
    the driver" and "done" that the shop would ever tap.
    """
    if to_status not in ("ready", "completed"):
        raise PublicOrderError(f"Cannot move an online order to '{to_status}'.")

    order = await order_service.get_order(db, order_id, tenant_id)
    if order is None or order.order_type != "online":
        raise PublicOrderError("Order not found.")
    if order.accepted_at is None:
        raise PublicOrderError("Accept the order before moving it along.")
    if order.rejected_at is not None:
        raise PublicOrderError("This order was rejected.")
    if order.status == to_status:
        raise PublicOrderError(f"Order is already {to_status}.")

    # `completed` is two hops from `in_kitchen`. Walk them rather than jumping,
    # so the status log tells the truth and every guard in transition_order runs.
    path = {
        ("in_kitchen", "ready"): ["ready"],
        ("in_kitchen", "completed"): ["ready", "served", "completed"],
        ("ready", "completed"): ["served", "completed"],
        ("served", "completed"): ["completed"],
    }.get((order.status, to_status))

    if path is None:
        raise PublicOrderError(
            f"Cannot move an order from '{order.status}' to '{to_status}'."
        )

    for step in path:
        try:
            order = await order_service.transition_order(
                db, order_id, tenant_id, user_id, step
            )
        except ValueError as exc:
            raise PublicOrderError(str(exc)) from exc

    return order


async def mark_order_paid(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    user_id: uuid.UUID,
    method_code: str = "cash",
) -> Order:
    """Record that a cash-on-handover order has been settled.

    Online orders are created `unpaid` and there is no Stripe yet, so the money
    arrives at the door or the counter. Without this the order stays unpaid
    forever, the Z-report understates the day's takings, and the tablet keeps
    showing the unpaid banner on an order that was paid in full.

    A real `Payment` row is written through the normal payment service rather
    than by flipping `payment_status` directly -- reports, the drawer session
    and the Z-report all read payments, so a status flag alone would show money
    that no report could find.
    """
    order = await order_service.get_order(db, order_id, tenant_id)
    if order is None or order.order_type != "online":
        raise PublicOrderError("Order not found.")
    if order.payment_status == "paid":
        raise PublicOrderError("Order is already paid.")
    if order.rejected_at is not None:
        raise PublicOrderError("This order was rejected.")

    from app.schemas.payment import PaymentCreate
    from app.services import payment_service

    # A tenant seeded purely for online ordering has no payment methods at all
    # -- `seed_chick_shack.py` creates the menu and users but never touches the
    # payments domain, so `chick-shack` had zero rows and this would have failed
    # with "payment method not found" the first time anyone tapped Paid.
    # Idempotent, so it costs one indexed read on every later call.
    await payment_service.ensure_default_payment_methods(db, tenant_id)

    paid, refunded = await payment_service._get_order_payment_totals(
        db, tenant_id, order.id
    )
    due = max(order.total - paid + refunded, 0)
    if due <= 0:
        raise PublicOrderError("Order is already paid.")

    try:
        await payment_service.create_payment(
            db,
            tenant_id,
            user_id,
            PaymentCreate(
                order_id=order.id,
                method_code=method_code,
                amount=due,
                tendered_amount=due if method_code == "cash" else None,
                note="Online order settled on handover",
            ),
        )
    except ValueError as exc:
        raise PublicOrderError(str(exc)) from exc

    refreshed = await order_service.get_order(db, order_id, tenant_id)
    if refreshed is None:
        raise PublicOrderError("Order not found.")
    return refreshed


async def reject_order(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    user_id: uuid.UUID,
    reason: str,
) -> Order:
    """Reject an online order. Terminal -- it becomes `voided`."""
    order = await _get_pending_online_order(db, tenant_id, order_id)

    order.rejected_at = datetime.now(timezone.utc)
    order.rejection_reason = reason
    order.status = "voided"

    db.add(
        OrderStatusLog(
            tenant_id=tenant_id,
            order_id=order.id,
            from_status="confirmed",
            to_status="voided",
            changed_by=user_id,
        )
    )
    await db.flush()
    return await order_service.get_order(db, order.id, tenant_id)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# The merchant queue -- what the shop's tablet polls
# ---------------------------------------------------------------------------


async def list_merchant_orders(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    state: str = "pending",
    limit: int = 50,
) -> list[Order]:
    """Online orders for the shop's order-queue tablet.

    `state`:
      `pending` -- placed, awaiting the shop's accept or reject. The decision queue.
      `active`  -- accepted and still being worked: cooking, or out for delivery.
      `all`     -- everything online including rejected, for looking something up.

    **Pending is ordered oldest-first and everything else newest-first**, which
    is deliberate rather than an inconsistency. Pending is a work queue, and the
    customer who has been waiting four minutes needs answering before the one
    who ordered ten seconds ago. The other views are a log, where the most
    recent thing is the thing you came to look at.

    Modifiers are eagerly loaded two levels deep on purpose. `item.modifiers` on
    a lazily loaded item raises `MissingGreenlet` under async SQLAlchemy, and
    the tablet renders every modifier on every line of every card.
    """
    stmt = (
        select(Order)
        .where(Order.tenant_id == tenant_id, Order.order_type == "online")
        .options(selectinload(Order.items).selectinload(OrderItem.modifiers))
    )

    if state == "pending":
        stmt = stmt.where(
            Order.accepted_at.is_(None), Order.rejected_at.is_(None)
        ).order_by(Order.created_at.asc())
    elif state == "active":
        stmt = stmt.where(
            Order.accepted_at.is_not(None),
            Order.status.not_in(("completed", "voided")),
        ).order_by(Order.created_at.desc())
    else:
        stmt = stmt.order_by(Order.created_at.desc())

    result = await db.execute(stmt.limit(limit))
    return list(result.scalars().all())


async def _get_pending_online_order(
    db: AsyncSession, tenant_id: uuid.UUID, order_id: uuid.UUID
) -> Order:
    result = await db.execute(
        select(Order)
        .where(
            Order.id == order_id,
            Order.tenant_id == tenant_id,
            Order.order_type == "online",
        )
        .options(selectinload(Order.items))
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise PublicOrderError("Order not found.")
    if order.accepted_at is not None:
        raise PublicOrderError("Order has already been accepted.")
    if order.rejected_at is not None:
        raise PublicOrderError("Order has already been rejected.")
    return order
