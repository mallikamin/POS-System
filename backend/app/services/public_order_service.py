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

import asyncio
import logging
import secrets
import uuid
from datetime import date as date_
from datetime import datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select, update
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
from app.services import audit_service, email_service, order_service, stripe_service
from app.services.order_visibility import is_card_order, is_real_order
from app.utils.security import hash_password

logger = logging.getLogger(__name__)

ONLINE_SYSTEM_EMAIL = "online-orders@system.local"

# A card order becomes visible to the shop when Stripe confirms the money, and
# at no other time. There is deliberately NO timeout, grace period or
# show-it-anyway fallback here -- the payment event is the only thing that
# publishes the order, exactly as Uber Eats and Foodpanda behave.
#
# OI-61 (2026-08-03) originally shipped a 5-minute grace window so an abandoned
# checkout would still surface. That was the wrong trade twice over, and
# production proved it the next day (OI-65):
#
#   * It was calibrated on one day's sample -- the worst gap on 2026-08-02 was
#     179s, so 5 minutes "left real margin". On 2026-08-03 order 260803-003 took
#     366s, the window expired, and the order was publishable while unpaid.
#   * An abandoned checkout SHOULD be lost. Nobody paid, so there is no order to
#     cook. Surfacing it buys nothing and costs the money guarantee.
#
# The cost of removing the timeout is that publication now depends entirely on
# learning about the authorisation -- so it must never depend on a single
# webhook delivery. `publish_authorized_card_orders` re-derives it straight from
# Stripe on every queue poll; the webhook is only the fast path.
CARD_ORDER_UNPUBLISHED_MAX_AGE = timedelta(hours=24)

#: Most unpublished card orders to re-check against Stripe on one queue poll.
#: Bounded so a burst of abandoned checkouts can never turn the tablet's
#: 10-second poll into a long serial walk of the Stripe API.
CARD_ORDER_RECONCILE_BATCH = 8


class PublicOrderError(Exception):
    """Rejected for a reason the customer should see. Maps to HTTP 409."""


#: Shown to the customer when the shop has paused online ordering. Imran's own
#: wording (via Malik, 2026-08-04) -- kept verbatim, including the phone number,
#: because the whole purpose of the pause is to move the customer to the phone.
ONLINE_ORDERING_PAUSED_MESSAGE = (
    "We are facing high demand at the moment, please directly call the "
    "restaurant 07719 566 889 to place your order. We appreciate your "
    "patience in this regard."
)


class OnlineOrderingPaused(PublicOrderError):
    """The shop has stopped taking online orders during a rush.

    Its own type so the storefront can render the "please phone us" message
    rather than a generic basket error -- this is not a fault, it is the shop
    deliberately closing the channel for a while.
    """


class CardPaymentNotConfirmed(PublicOrderError):
    """Accept was attempted on a card order whose money Stripe has not confirmed.

    Its own type because this one is not a fault to be reported as an error:
    it is the system correctly refusing, and the tablet should say "waiting for
    the customer's card payment", not "something went wrong".
    """


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
            # Sorted, not just filtered. The association table returns groups in
            # no particular order, so without this `display_order` is inert on
            # the storefront and customers get whatever order the rows were
            # inserted in. Same key as the item sort directly above.
            item.modifier_groups = sorted(
                (g for g in item.modifier_groups if g.is_active),
                key=lambda g: (g.display_order, g.name),
            )
            for group in item.modifier_groups:
                group.modifiers = [m for m in group.modifiers if m.is_available]

    categories = [c for c in categories if c.items]

    currency = await get_currency(db, tenant_id)
    return currency, categories


async def is_online_ordering_paused(db: AsyncSession, tenant_id: uuid.UUID) -> bool:
    """Has the shop pressed the "we're slammed, stop taking orders" button?

    Read by the menu endpoint so the storefront can explain itself, and by
    `create_public_order` so it is actually enforced. Both, deliberately: a
    check that only exists in the browser is a suggestion.
    """
    result = await db.execute(
        select(RestaurantConfig.online_ordering_paused).where(
            RestaurantConfig.tenant_id == tenant_id
        )
    )
    return bool(result.scalar_one_or_none())


async def set_online_ordering_paused(
    db: AsyncSession, tenant_id: uuid.UUID, paused: bool
) -> bool:
    """Flip the switch. Returns the value now in force."""
    result = await db.execute(
        select(RestaurantConfig).where(RestaurantConfig.tenant_id == tenant_id)
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise PublicOrderError("This shop has no configuration record.")
    config.online_ordering_paused = paused
    await db.commit()
    return paused


async def get_currency(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    result = await db.execute(
        select(RestaurantConfig.currency).where(
            RestaurantConfig.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none() or "PKR"


async def get_timezone(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    result = await db.execute(
        select(RestaurantConfig.timezone).where(
            RestaurantConfig.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none() or "UTC"


async def get_service_fee(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    """Flat per-order fee in minor units. 0 for every tenant that doesn't charge one."""
    result = await db.execute(
        select(RestaurantConfig.service_fee).where(
            RestaurantConfig.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none() or 0


def _zone(tz_name: str) -> ZoneInfo | timezone:
    """Same fallback-to-UTC-on-bad-name behaviour as `print_service._offset_minutes`."""
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


def _today_in_timezone(tz_name: str) -> date_:
    return datetime.now(timezone.utc).astimezone(_zone(tz_name)).date()


def _local_day_bounds_utc(tz_name: str, local_date: date_) -> tuple[datetime, datetime]:
    """[start, end) of one calendar day in the shop's own timezone, in UTC.

    Computed from the shop's local wall-clock day rather than a raw UTC date
    cast, so "today" for a UK shop actually means its own midnight-to-midnight,
    not whatever the server's UTC clock happens to be at the boundary.
    """
    tz = _zone(tz_name)
    start_local = datetime.combine(local_date, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


async def get_shop_name(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    """Display name for customer-facing email. The tenant's own name."""
    result = await db.execute(select(Tenant.name).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none() or "Your restaurant"


# Strong references to in-flight email tasks. asyncio keeps only a weak ref to
# tasks, so without this set a send could be garbage-collected mid-flight.
_email_tasks: set[asyncio.Task] = set()


async def notify_customer(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order: Order,
    event: str,
    *,
    intends_card_payment: bool = False,
    review_url: str = "",
) -> None:
    """Schedule the customer's email without making anyone wait for it.

    ⚠️ **Call this AFTER `db.commit()`, never before.** An email announcing an
    order that then failed to commit cannot be recalled, and the customer would
    be holding a confirmation for something that does not exist.

    The send itself is fire-and-forget, and that is load-bearing: an
    unreachable provider burns its full transport timeout, and while this was
    awaited inline that put ~15 silent seconds inside every checkout and every
    Accept tap on production (2026-07-29, the dead-SMTP period). An email must
    never fail an order — nor delay one. `send_order_email` never raises, so a
    finished task has nothing to hand back; the order object's fields are
    eager-loaded before this is called, so the task outliving the request's
    DB session is safe.
    """
    currency = await get_currency(db, tenant_id)
    shop_name = await get_shop_name(db, tenant_id)
    task = asyncio.create_task(
        email_service.send_order_email(
            order,
            event,
            shop_name=shop_name,
            currency=currency,
            intends_card_payment=intends_card_payment,
            review_url=review_url,
        )
    )
    _email_tasks.add(task)
    task.add_done_callback(_email_tasks.discard)


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
    # Checked here, not only in the storefront. The shop presses this button
    # when the kitchen is drowning; a stale browser tab must not be able to
    # push one more order through, and a client-side check is a suggestion.
    if await is_online_ordering_paused(db, tenant_id):
        raise OnlineOrderingPaused(ONLINE_ORDERING_PAUSED_MESSAGE)

    lines, subtotal = await _price_basket(db, tenant_id, data)
    delivery_fee, area_name = await _resolve_delivery(db, tenant_id, data, subtotal)
    service_fee = await get_service_fee(db, tenant_id)

    tax_rate_bps, prices_include_tax = await order_service._get_tax_settings(
        db, tenant_id
    )
    # Tax is charged on goods, not on the delivery fee, the service fee or
    # the tip. The tip is the one client-sent amount on the order (OI-81);
    # the schema has already bounded it to 0..2000.
    #
    # F19: when menu prices already include tax, the tax is backed OUT of the
    # goods subtotal rather than added to it, so `goods_total == subtotal` and
    # the customer pays the price on the board. `compute_tax` owns that rule so
    # the online channel and the POS cannot drift apart.
    #
    # Chick Shack, the only live user of this path, runs `default_tax_rate = 0`,
    # for which both branches return `(0, subtotal)` -- their totals are
    # unchanged by this, and `test_tax_inclusive_pricing.py` pins that.
    tax_amount, goods_total = order_service.compute_tax(
        subtotal, tax_rate_bps, prices_include_tax
    )
    total = goods_total + delivery_fee + service_fee + data.tip

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
        # Carries the C/D marker for collection vs delivery, so the printed
        # receipt says which it is in the number itself (Imran, 2026-08-04).
        order_number=await order_service.generate_order_number(
            db, tenant_id, service_type=data.service_type
        ),
        order_type="online",
        status="confirmed",
        payment_status="unpaid",
        # Written in the same INSERT as the order itself, so the "card or cash?"
        # question is answerable from the instant the row exists. The Stripe
        # session id is set by a later request and must never be used for this
        # (OI-84).
        intends_card_payment=(data.payment_method == "card"),
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
        service_fee=service_fee,
        tip=data.tip,
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


async def _log_stripe_event(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order: Order,
    *,
    action: str,
    detail: str,
    changes: dict,
    user_id: uuid.UUID | None = None,
) -> None:
    """Durable, per-order record of every Stripe transaction and event.

    Money moved through Stripe is exactly the kind of thing a chargeback or a
    "did I actually pay?" query asks about weeks later, by which point an
    ephemeral application log has usually rotated away. `audit_logs` already
    exists, is tenant-scoped, is queryable by `entity_id`, and is isolated in
    its own SAVEPOINT (see `audit_service.log_action`) so a logging failure
    can never take a payment down with it -- so Stripe events are recorded
    through it rather than inventing a second logging path.

    `user_id=None` marks an event nobody at the shop triggered: a webhook
    delivery. A staff Accept/Reject passes its own `user_id` instead, so the
    trail shows who took the action, not just that Stripe reported it.
    """
    await audit_service.log_action(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        user_name=None if user_id else "Stripe webhook",
        entity_type="order",
        entity_id=order.id,
        action=action,
        changes=changes,
        detail=detail,
    )


async def log_stripe_checkout_session_created(
    db: AsyncSession,
    order: Order,
    *,
    session_id: str,
    intent_id: str | None,
) -> None:
    """Record that the customer was sent to Stripe to pay -- the start of the
    money trail for this order, called from the public checkout-session route.
    """
    await _log_stripe_event(
        db,
        order.tenant_id,
        order,
        action="stripe_checkout_created",
        detail=f"Checkout session started for {order.order_number}.",
        changes={"session_id": session_id, "intent_id": intent_id},
    )


async def log_stripe_webhook_event(
    db: AsyncSession,
    order: Order,
    *,
    event_type: str,
    event_id: str | None,
    intent_id: str | None,
) -> None:
    """Record every Stripe webhook delivery for this order, whether or not we
    acted on it -- including `payment_intent.canceled`/`payment_intent.
    payment_failed`, which deliberately change nothing on the order but are
    still real events on the money side that a dispute conversation may need.
    """
    await _log_stripe_event(
        db,
        order.tenant_id,
        order,
        action=f"stripe_webhook_{event_type}",
        detail=f"Stripe reported {event_type} for {order.order_number}.",
        changes={"event_id": event_id, "event_type": event_type, "intent_id": intent_id},
    )


async def _record_card_payment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order: Order,
    user_id: uuid.UUID,
) -> None:
    """Write the Payment row for a card capture.

    Money that Stripe has but this system has no row for is money the shop
    cannot reconcile: the Z-report, the dashboard and the drawer session all
    read `payments`, never `orders.payment_status`.

    Failure here must NOT undo the capture -- the money is already taken and
    the customer is owed their food. So it is isolated in a SAVEPOINT, the same
    pattern audit logging uses, and a failure is logged loudly rather than
    poisoning the acceptance. The webhook is the backstop that reconciles it.
    """
    from app.schemas.payment import PaymentCreate
    from app.services import payment_service

    try:
        async with db.begin_nested():
            # A tenant seeded only for online ordering has no payment methods.
            await payment_service.ensure_default_payment_methods(db, tenant_id)

            paid, refunded = await payment_service._get_order_payment_totals(
                db, tenant_id, order.id
            )
            due = max(order.total - paid + refunded, 0)
            if due <= 0:
                return

            await payment_service.create_payment(
                db,
                tenant_id,
                user_id,
                PaymentCreate(
                    order_id=order.id,
                    method_code="card",
                    amount=due,
                    reference=order.stripe_payment_intent_id,
                    note="Online card payment captured on acceptance",
                ),
            )
    except Exception:
        logger.exception(
            "Captured %s for order %s but could not write the Payment row. "
            "The money IS taken; reports will understate until reconciled.",
            order.stripe_payment_intent_id,
            order.order_number,
        )


async def accept_order(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    user_id: uuid.UUID,
    eta_minutes: int,
) -> Order:
    """Accept an online order, take the money if a card is held, fire the kitchen.

    Order of operations matters and is deliberate: **the card is captured before
    anything else changes.** The client's rule is "charge once accepted", so
    acceptance is the moment money moves, and if it cannot move the shop must
    not be told the order is accepted -- the very next thing that happens is a
    ticket printing in the kitchen and food being made.

    A capture failure therefore raises and leaves the order pending, which is
    recoverable. Cooking food for a payment that failed is not.
    """
    order = await _get_pending_online_order(db, tenant_id, order_id)

    # A checkout session, not the payment intent id, is what reliably marks
    # this as a card order -- it is written the instant the session is
    # created, whereas `stripe_payment_intent_id` is often still unresolved at
    # this point (see `resolve_payment_intent_id`). Guarding on the intent id
    # instead is exactly the bug that let a real, successfully-authorised
    # order (260731-001, 2026-07-31) sail through Accept without ever being
    # captured: the field was still `None` and this whole block silently
    # never ran, with no error and nothing logged.
    # ⚠️ Keyed on the customer's INTENT, not on the Stripe session id (OI-84).
    # The session id is set by a second request ~0.3s after the order commits,
    # and while it was null this entire block was skipped -- so a card order
    # caught in that window could be accepted as though it were cash on
    # delivery, committing the kitchen with no money held and no capture ever
    # attempted. `intends_card_payment` is written in the order's own INSERT, so
    # there is no window in which a card order looks like a cash one.
    if is_card_order(order) and order.payment_captured_at is None:
        # No session id yet means the customer never reached Stripe, so there is
        # nothing to confirm and nothing to capture. Refuse for the same reason
        # an unauthorised session is refused: no money is held.
        if not order.stripe_checkout_session_id:
            raise CardPaymentNotConfirmed(
                "The customer's card payment has not gone through yet, so "
                "this order has not been accepted. It will appear by itself "
                "the moment Stripe confirms the payment -- and if the "
                "customer never completes it, there is nothing to make."
            )

        intent_id = order.stripe_payment_intent_id

        # ⚠️ THE INVARIANT (OI-65). An unconfirmed card order cannot be
        # accepted, by any route, ever. `list_merchant_orders` also hides it,
        # but a query filter only protects the query it is written on: OI-61
        # shipped exactly that filter, and it was bypassed within a day from
        # the tablet's "All" tab, which renders Accept for any unanswered
        # order and is not gated (order 260803-003, 2026-08-03 -- accepted
        # 2m34s in, authorised 3m36s later). A stale render or a direct API
        # call would do the same. This check is what actually makes the rule
        # true, because it sits on the one path that commits food.
        if order.payment_authorized_at is None or intent_id is None:
            try:
                resolved_id, authorized = await stripe_service.authorization_for_session(
                    order.stripe_checkout_session_id
                )
            except stripe_service.StripeError as exc:
                # Cannot confirm the money, so cannot commit the kitchen.
                # Refusing is recoverable -- staff retry in a moment. Cooking
                # against a payment we could not verify is not.
                raise PublicOrderError(
                    "Could not check the card payment with Stripe, so the order "
                    f"has not been accepted. Try again in a moment. ({exc})"
                ) from exc

            if not authorized:
                raise CardPaymentNotConfirmed(
                    "The customer's card payment has not gone through yet, so "
                    "this order has not been accepted. It will appear by itself "
                    "the moment Stripe confirms the payment -- and if the "
                    "customer never completes it, there is nothing to make."
                )

            intent_id = resolved_id
            await mark_card_order_authorized(db, order, intent_id)

        if intent_id:
            try:
                # Bounded by what the order is worth NOW, not by what was
                # authorised when the customer paid. If the shop struck an
                # item in between, the customer must not be charged the
                # original figure.
                status = await stripe_service.capture_for_order(intent_id, order.total)
            except stripe_service.StripeError as exc:
                raise PublicOrderError(
                    f"Could not take the payment, so the order has not been accepted. {exc}"
                ) from exc

            if status != "succeeded":
                raise PublicOrderError(
                    f"The payment did not complete (status: {status}). "
                    "The order has not been accepted."
                )
            order.payment_captured_at = datetime.now(timezone.utc)
            # Stripe holding the money is not the same as this system knowing
            # about it. Reports, the drawer session and the Z-report all read
            # the payments table, so a capture that writes no Payment row is
            # money the shop cannot see -- the same trap `mark_order_paid`
            # exists to avoid.
            await _record_card_payment(db, tenant_id, order, user_id)
            await _log_stripe_event(
                db,
                tenant_id,
                order,
                action="stripe_captured",
                detail=f"Captured {order.total} for {order.order_number} on accept.",
                changes={"intent_id": intent_id, "amount": order.total, "status": status},
                user_id=user_id,
            )

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
    """Reject an online order. Terminal -- it becomes `voided`.

    If a card was authorised, the hold is released here. Nothing was ever
    captured, so there is no refund and the customer's "nothing has been
    charged" line stays literally true.

    Releasing is best-effort **on purpose**: a Stripe outage must not trap the
    shop with an order it has already declined, and an uncaptured authorisation
    expires by itself within days either way. Compare `accept_order`, where a
    Stripe failure *does* block -- there the shop would otherwise cook food it
    had not been paid for.
    """
    order = await _get_pending_online_order(db, tenant_id, order_id)

    if order.stripe_payment_intent_id and order.payment_captured_at is None:
        released = await stripe_service.cancel(order.stripe_payment_intent_id)
        await _log_stripe_event(
            db,
            tenant_id,
            order,
            action="stripe_canceled",
            detail=f"Released hold on {order.order_number} at reject.",
            changes={"intent_id": order.stripe_payment_intent_id, "released": released},
            user_id=user_id,
        )

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


async def reconcile_late_authorization(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order: Order,
    intent_id: str,
) -> bool:
    """Close the race between the shop answering an order and the customer's
    card actually finishing authorisation, whichever happens first.

    `accept_order` resolves and captures a PaymentIntent that already exists;
    `reject_order` cancels one that already exists. Neither can act on an
    authorisation that shows up *after* the order was already answered --
    e.g. staff tap Accept while the customer is still entering card details,
    and the hold only lands a few seconds later. Triggered by the webhook's
    `payment_intent.amount_capturable_updated` event, which fires exactly
    when that authorisation completes.

    Since OI-65 (2026-08-04) the "already accepted" branch below is unreachable
    for any NEW order: `accept_order` refuses outright until Stripe confirms the
    money, and the queue never shows an unconfirmed card order in the first
    place, with no grace window to release one. It is kept deliberately, for two
    reasons that are still live: orders answered under the older behaviour (or
    in flight across the deploy) can still have a late authorisation arrive, and
    the `rejected` branch remains genuinely reachable -- a customer can complete
    a payment after the shop has rejected the order, and that hold must be
    released rather than left to expire on its own days later.

    A no-op, returning `False`, if the order is still awaiting an answer --
    Accept/Reject handle it themselves when they happen -- or if the money is
    already captured. Returns `True` only when THIS call is the one that
    performed a genuine late capture, so the caller knows to re-notify the
    customer: the "accepted" email already sent (if any) was built from the
    payment state at Accept time, which was still unpaid.
    """
    if order.payment_captured_at is not None:
        return False

    if order.rejected_at is not None:
        released = await stripe_service.cancel(intent_id)
        await _log_stripe_event(
            db,
            tenant_id,
            order,
            action="stripe_canceled",
            detail=(
                f"Released a late authorisation on already-rejected order "
                f"{order.order_number}."
            ),
            changes={"intent_id": intent_id, "released": released},
        )
        return False

    if order.accepted_at is None:
        # Still pending. Accept will resolve and capture this live when it
        # happens, exactly as it does today -- nothing to do yet.
        return False

    # Already accepted: the kitchen has committed to the food. Take the
    # payment now, same capture call accept_order makes.
    try:
        capture_status = await stripe_service.capture_for_order(intent_id, order.total)
    except stripe_service.StripeError:
        logger.exception(
            "Late capture failed for already-accepted order %s (%s). Food may already "
            "be in the kitchen with payment still uncaptured -- needs manual follow-up.",
            order.order_number,
            intent_id,
        )
        await _log_stripe_event(
            db,
            tenant_id,
            order,
            action="stripe_capture_failed",
            detail=(
                f"Late capture failed on already-accepted order {order.order_number}. "
                "Needs manual follow-up -- food may already be made."
            ),
            changes={"intent_id": intent_id, "amount": order.total},
        )
        return False

    if capture_status != "succeeded":
        logger.warning(
            "Late capture for accepted order %s did not succeed (status=%s)",
            order.order_number,
            capture_status,
        )
        await _log_stripe_event(
            db,
            tenant_id,
            order,
            action="stripe_capture_failed",
            detail=(
                f"Late capture on already-accepted order {order.order_number} returned "
                f"status {capture_status}, not succeeded. Needs manual follow-up."
            ),
            changes={"intent_id": intent_id, "status": capture_status},
        )
        return False

    order.payment_captured_at = datetime.now(timezone.utc)
    system_user = await _get_or_create_online_user(db, tenant_id)
    await _record_card_payment(db, tenant_id, order, system_user.id)
    await _log_stripe_event(
        db,
        tenant_id,
        order,
        action="stripe_captured",
        detail=(
            f"Captured {order.total} for {order.order_number} via a late-arriving "
            "authorisation (order was already accepted)."
        ),
        changes={"intent_id": intent_id, "amount": order.total, "status": capture_status},
    )
    return True


async def mark_card_order_authorized(
    db: AsyncSession, order: Order, intent_id: str | None
) -> bool:
    """Record that Stripe has confirmed the money for a card order.

    This is the single moment a card order becomes real to the shop, so both
    routes that can learn it -- the `amount_capturable_updated` webhook and
    `publish_authorized_card_orders`'s poll-time check -- go through here
    rather than each setting the fields their own way.

    Returns `True` only when THIS call published the order, so the caller knows
    to send the customer's "we've got your order" email exactly once.

    ⚠️ The claim is a conditional UPDATE rather than a read-then-write, and that
    matters: there are now three independent things that can publish the same
    order within a few hundred milliseconds of each other -- the webhook and the
    tablet's two separate 10-second polls (`refresh` and `checkForNewOrders`).
    Testing `order.payment_authorized_at is None` in Python reads a value loaded
    before the others committed, so two callers would both believe they won and
    the customer would get two "order received" emails. `WHERE
    payment_authorized_at IS NULL` makes the database pick exactly one winner.
    """
    if intent_id and order.stripe_payment_intent_id is None:
        order.stripe_payment_intent_id = intent_id

    authorized_at = stripe_service.authorization_timestamp()
    result = await db.execute(
        update(Order)
        .where(Order.id == order.id, Order.payment_authorized_at.is_(None))
        .values(payment_authorized_at=authorized_at)
        .execution_options(synchronize_session=False)
    )
    if not result.rowcount:
        return False

    # Keep the in-session object consistent with the row we just wrote, using
    # the same timestamp so a later flush cannot rewrite it to a different one.
    order.payment_authorized_at = authorized_at
    return True


async def publish_authorized_card_orders(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[Order]:
    """Re-derive card authorisations straight from Stripe. Returns newly published orders.

    Since OI-65 a card order has no timeout: it appears when Stripe confirms the
    money and never before. That guarantee is only as good as our knowledge of
    the authorisation -- and `payment_authorized_at` was previously written in
    exactly one place, the `payment_intent.amount_capturable_updated` webhook.
    A single dropped or delayed delivery would therefore mean a customer whose
    card is authorised, whose order the shop never sees, and no expiry to save
    it. That is a worse failure than the double-charge this all started with.

    So the queue does not wait to be told. Every poll, any card order still
    unpublished is checked against Stripe directly and published if the money is
    there. The webhook stays as the fast path (typically 1-2s); this is what
    makes the guarantee hold without it.

    Deliberately defensive: bounded to `CARD_ORDER_RECONCILE_BATCH` orders and
    to those younger than `CARD_ORDER_UNPUBLISHED_MAX_AGE`, run concurrently,
    and every Stripe failure is swallowed after logging. A Stripe outage must
    slow or degrade this backstop, never take the shop's order queue down with
    it -- cash orders and every already-published card order must keep flowing.
    """
    result = await db.execute(
        select(Order)
        .where(
            Order.tenant_id == tenant_id,
            Order.order_type == "online",
            Order.stripe_checkout_session_id.is_not(None),
            Order.payment_authorized_at.is_(None),
            Order.accepted_at.is_(None),
            Order.rejected_at.is_(None),
            Order.created_at >= datetime.now(timezone.utc) - CARD_ORDER_UNPUBLISHED_MAX_AGE,
        )
        .order_by(Order.created_at.desc())
        .limit(CARD_ORDER_RECONCILE_BATCH)
    )
    waiting = list(result.scalars().all())
    if not waiting:
        return []

    async def _check(order: Order) -> tuple[Order, str | None, bool]:
        try:
            intent_id, authorized = await stripe_service.authorization_for_session(
                order.stripe_checkout_session_id  # type: ignore[arg-type]
            )
        except stripe_service.StripeNotConfigured:
            return order, None, False
        except Exception:
            # Deliberately broad. This is a backstop on the tablet's polling
            # path: whatever goes wrong reaching Stripe, the order simply stays
            # unpublished and is retried on the next poll ten seconds later.
            # Letting anything escape here would take the whole order queue
            # down -- including the cash orders that have nothing to do with
            # Stripe -- which is far worse than a delayed card order.
            logger.warning(
                "Could not re-check the Stripe authorisation for %s; it stays "
                "unpublished and will be retried on the next poll.",
                order.order_number,
                exc_info=True,
            )
            return order, None, False
        return order, intent_id, authorized

    published: list[Order] = []
    for order, intent_id, authorized in await asyncio.gather(
        *(_check(order) for order in waiting)
    ):
        if not authorized:
            continue
        if await mark_card_order_authorized(db, order, intent_id):
            published.append(order)
            await _log_stripe_event(
                db,
                tenant_id,
                order,
                action="stripe_authorized",
                detail=(
                    f"Stripe confirmed the authorisation for {order.order_number} "
                    "on a queue re-check; the order is now visible to the shop."
                ),
                changes={"intent_id": intent_id, "source": "queue_reconcile"},
            )

    if not published:
        return []

    await db.commit()

    # Re-fetch through the same eager-loaded getter the webhook uses. The query
    # above loads columns only, and the customer's email template walks
    # `order.items[*].modifiers` -- a lazy load there raises `MissingGreenlet`
    # under async SQLAlchemy. `db.refresh()` would not fix it either: it
    # restores column state, not the relationship loader options.
    reloaded = []
    for order in published:
        full = await order_service.get_order(db, order.id, tenant_id)
        if full is not None:
            reloaded.append(full)
    return reloaded


# ---------------------------------------------------------------------------
# The merchant queue -- what the shop's tablet polls
# ---------------------------------------------------------------------------


def default_sort_for_state(state: str) -> Literal["asc", "desc"]:
    """The sort `list_merchant_orders` applies when the caller doesn't override it."""
    return "asc" if state == "pending" else "desc"


async def list_merchant_orders(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    state: str = "pending",
    limit: int = 50,
    offset: int = 0,
    date: date_ | None = None,
    date_from: date_ | None = None,
    date_to: date_ | None = None,
    sort: Literal["asc", "desc"] | None = None,
) -> tuple[list[Order], int]:
    """Online orders for the shop's order-queue tablet.

    `state`:
      `pending` -- placed, awaiting the shop's accept or reject. The decision queue.
      `active`  -- accepted and still being worked: cooking, or out for delivery.
      `all`     -- everything online including rejected, for looking something up.

    **Pending is ordered oldest-first and everything else newest-first by
    default**, which is deliberate rather than an inconsistency. Pending is a
    work queue, and the customer who has been waiting four minutes needs
    answering before the one who ordered ten seconds ago. The other views are a
    log, where the most recent thing is the thing you came to look at. `sort`
    overrides the default when the caller (Active/All's sort toggle) asks for
    it explicitly; nothing sends it for Pending today, so its default holds.

    `pending`/`active` scope to a single calendar day in the shop's own
    timezone -- `date` if given, else today -- so a multi-day-old test order
    doesn't sit in the live queue forever. `all` is a browsable log instead:
    it stays unscoped unless `date_from`/`date_to` narrow it, matching its own
    "everything, for looking something up" purpose.

    Modifiers are eagerly loaded two levels deep on purpose. `item.modifiers` on
    a lazily loaded item raises `MissingGreenlet` under async SQLAlchemy, and
    the tablet renders every modifier on every line of every card.

    Returns `(orders, total_count)` -- `total_count` is the full match count
    before `limit`/`offset`, for the tablet to render real page controls.
    """
    conditions = [Order.tenant_id == tenant_id, Order.order_type == "online"]

    # ⚠️ A card order whose money Stripe has not confirmed is NOT IN THE POS.
    # Not in Pending, not in Active, not in All -- nowhere, in any view, until
    # the payment is approved. Applied to EVERY state on purpose, and defined
    # once in `order_visibility` so reports and the tablet can never disagree
    # about what counts as a real order (they did, on 2026-08-04).
    conditions += [is_real_order()]

    if state == "pending":
        conditions += [Order.accepted_at.is_(None), Order.rejected_at.is_(None)]
    elif state == "active":
        conditions += [
            Order.accepted_at.is_not(None),
            Order.status.not_in(("completed", "voided")),
        ]
    default_sort = default_sort_for_state(state)

    if state in ("pending", "active"):
        tz_name = await get_timezone(db, tenant_id)
        start_utc, end_utc = _local_day_bounds_utc(
            tz_name, date or _today_in_timezone(tz_name)
        )
        conditions += [Order.created_at >= start_utc, Order.created_at < end_utc]
    elif date_from or date_to:
        tz_name = await get_timezone(db, tenant_id)
        start_utc, _ = _local_day_bounds_utc(tz_name, date_from or date_to)  # type: ignore[arg-type]
        _, end_utc = _local_day_bounds_utc(tz_name, date_to or date_from)  # type: ignore[arg-type]
        conditions += [Order.created_at >= start_utc, Order.created_at < end_utc]

    count_result = await db.execute(
        select(func.count()).select_from(Order).where(*conditions)
    )
    total_count = count_result.scalar_one()

    order_by = (
        Order.created_at.asc()
        if (sort or default_sort) == "asc"
        else Order.created_at.desc()
    )
    stmt = (
        select(Order)
        .where(*conditions)
        .options(selectinload(Order.items).selectinload(OrderItem.modifiers))
        .order_by(order_by)
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all()), total_count


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


# ---------------------------------------------------------------------------
# Review-request emails
# ---------------------------------------------------------------------------
#
# Malik, 2026-08-10: ask every online customer for a Google review a few hours
# after their order. His own framing of why it is time-based rather than tied
# to the shop tapping "Complete": *"instead of waiting on someone to tap
# complete - lets just send email after 2-3 hours of order acceptance"*. Staff
# behaviour is then irrelevant to whether the email goes.

#: How long after the shop ACCEPTS before we ask. Acceptance, not placement:
#: a pre-order placed at 14:00 is not accepted until the shop opens at 16:00,
#: and the food only exists after acceptance.
REVIEW_EMAIL_DELAY = timedelta(hours=3)

#: Orders older than this are never asked about, however they got missed. This
#: is what stops a burst of emails about stale orders the first time the
#: feature is switched on, and what stops a backend outage ending in a mailshot
#: about food eaten days ago.
#:
#: ⚠️ **It must be wide enough to survive the overnight wait, or it silently
#: eats the busiest part of the night.** This was 12h and that was wrong. Work
#: it through with the shop's real hours (16:00-22:00):
#:
#:   accepted 16:00-19:00 -> due 19:00-22:00 -> inside the window, sent that
#:                           evening.
#:   accepted 19:00-22:00 -> due 22:00-01:00 -> window shut, deferred to 09:00,
#:                           by which time the order is 11-14h old.
#:
#: At 12h everything accepted after ~19:00 aged out overnight and was dropped
#: without a trace -- peak dinner, and the failure was invisible because no
#: email is not an error. Caught on 2026-08-10 by dry-running the real query
#: against production the moment the feature was switched on: 260809-D002,
#: accepted 19:06, was due and would have been binned at 09:00.
#:
#: 18h covers acceptance back to 15:00 the previous day at the 09:00 sweep,
#: i.e. the whole of the last service, with margin.
REVIEW_EMAIL_MAX_AGE = timedelta(hours=18)

#: Shop-local hours during which a review email may go out. An order accepted
#: at 22:00 falls due at 01:00, and a restaurant emailing a customer at 1am
#: reads as spam and can buzz a phone in the night. Anything due outside this
#: window simply stays unclaimed until the next morning's sweep.
REVIEW_SEND_FROM = time(9, 0)
REVIEW_SEND_UNTIL = time(22, 0)


async def send_due_review_emails(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[Order]:
    """Send the "how did we do" email for every order that has come due.

    Returns the orders actually claimed by THIS call, which is what makes the
    function testable: a second call must return an empty list.

    Three guards, each earning its place:

    * **The tenant's `google_review_url` is the feature switch.** It is NULL
      everywhere on deploy, so this ships inert and turns on for exactly the
      restaurant whose link is filled in. A review link belongs to one Google
      Business Profile; hardcoding Chick Shack's would send Cosa Nostra's
      customers to a chicken shop in Garelochhead (the OI-73 lesson).
    * **The send window**, in the tenant's own timezone, not the server's.
    * **The claim is a conditional UPDATE**, not a read-then-write. The backend
      runs `--workers 4` and every worker sweeps on the same timer, so
      `WHERE review_email_sent_at IS NULL` is what makes the database pick one
      winner. Checking the field in Python would let all four believe they won
      and send one customer four emails. Same reasoning as
      `mark_card_order_authorized`.

    Never raises. This runs on a background timer with no user waiting on it,
    and a failure here must not be able to take down the loop.
    """
    config = (
        await db.execute(
            select(
                RestaurantConfig.google_review_url,
                RestaurantConfig.timezone,
            ).where(RestaurantConfig.tenant_id == tenant_id)
        )
    ).first()

    if config is None:
        return []
    review_url = (config.google_review_url or "").strip()
    if not review_url:
        return []

    try:
        shop_zone = ZoneInfo(config.timezone or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        # A bad timezone string must not silently move every customer's email
        # to the wrong hour. Refuse the sweep and say so.
        logger.warning(
            "Tenant %s has an unusable timezone %r; skipping review emails",
            tenant_id,
            config.timezone,
        )
        return []

    now = datetime.now(timezone.utc)
    local_now = now.astimezone(shop_zone).time()
    if not (REVIEW_SEND_FROM <= local_now < REVIEW_SEND_UNTIL):
        return []

    due_orders = (
        (
            await db.execute(
                select(Order)
                .where(
                    Order.tenant_id == tenant_id,
                    Order.order_type == "online",
                    Order.review_email_sent_at.is_(None),
                    Order.accepted_at.is_not(None),
                    Order.accepted_at <= now - REVIEW_EMAIL_DELAY,
                    Order.accepted_at >= now - REVIEW_EMAIL_MAX_AGE,
                    Order.rejected_at.is_(None),
                    Order.status != "voided",
                    Order.customer_email.is_not(None),
                    Order.customer_email != "",
                    is_real_order(),
                )
                # The builders read `order.items` after the request's session is
                # gone, so they must be loaded now, not lazily later.
                .options(selectinload(Order.items))
                .order_by(Order.accepted_at)
                # Bounds the BURST, not the backlog. `notify_customer` fires
                # each send as its own task, so this number is exactly how many
                # emails can hit the provider's API at once -- and the 09:00
                # sweep is the spike, because it carries everything that fell
                # due overnight. Anything over the limit is not lost, it simply
                # goes on the next sweep 15 minutes later. 25 is far above this
                # shop's ~11 orders a day while still being a real ceiling.
                .limit(25)
            )
        )
        .scalars()
        .all()
    )

    claimed: list[Order] = []
    for order in due_orders:
        result = await db.execute(
            update(Order)
            .where(Order.id == order.id, Order.review_email_sent_at.is_(None))
            .values(review_email_sent_at=now)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount:
            order.review_email_sent_at = now
            claimed.append(order)

    if not claimed:
        return []

    # Commit the claim BEFORE sending. If the process dies between the two, the
    # customer misses one review request -- which is nothing. Committing after
    # sending would risk the opposite: mail out, claim lost, and everyone asked
    # again on the next sweep.
    await db.commit()

    for order in claimed:
        await notify_customer(db, tenant_id, order, "review", review_url=review_url)

    return claimed
