"""Danny's D-99: visit-based loyalty.

The rules, in one place:

* A visit is a PAID bill. Unpaid, voided or walk-in bills never count.
* One visit per bill (UNIQUE order_id), whoever claims it first: the cashier
  (customer phone on the order), or the customer scanning the bill's QR on the
  receipt or the counter display.
* At most `max_visits_per_day` visits per customer per local day, set by the
  owner (0 = no limit). The customer row is locked while counting, so two
  claims racing each other cannot pass the limit together.
* A bill that carries a customer phone belongs to that customer. Only the
  cashier route can count it; its QR cannot be claimed by anyone else, even
  when its own customer was over the daily limit.
* A QR claim is accepted for CLAIM_WINDOW after the bill was created.
* Rewards: every `visits_required` visits earns one. Available = earned -
  redeemed. Redeeming puts a discount line equal to the reward item's price on
  a bill that carries that item.

Recording a visit never blocks a payment: it runs in a SAVEPOINT and a
failure is logged, the same isolation the audit log uses.
"""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.integrations import google_wallet
from app.models.customer import Customer
from app.models.discount import OrderDiscount
from app.models.loyalty import LoyaltyRedemption, LoyaltyVisit, LoyaltyWalletPass
from app.models.menu import MenuItem
from app.models.order import Order
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.utils.tenant_time import zone

logger = logging.getLogger(__name__)

WALK_IN_PHONE = "0000000000"
CLAIM_WINDOW = timedelta(days=3)
DISPLAY_WINDOW = timedelta(minutes=10)
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I, read aloud safely


class LoyaltyError(ValueError):
    """A loyalty action that cannot be done as asked. Never a 500."""


@dataclass
class LoyaltySettings:
    enabled: bool
    visits_required: int
    reward_menu_item_id: uuid.UUID | None
    reward_label: str
    max_visits_per_day: int  # 0 = no limit


@dataclass
class Progress:
    customer_id: uuid.UUID
    customer_name: str
    phone: str
    total_visits: int
    visits_required: int
    toward_next: int
    rewards_earned: int
    rewards_redeemed: int
    rewards_available: int
    reward_label: str
    last_visit: str | None


def normalize_phone(raw: str | None) -> str | None:
    """Digits only; a Pakistani 92xxxxxxxxxx becomes 0xxxxxxxxxx. None if unusable."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0092"):
        digits = "0" + digits[4:]
    elif digits.startswith("92") and len(digits) == 12:
        digits = "0" + digits[2:]
    if len(digits) < 10 or len(digits) > 15 or digits == WALK_IN_PHONE:
        return None
    return digits


def new_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(10))


async def get_settings(db: AsyncSession, tenant_id: uuid.UUID) -> LoyaltySettings:
    row = (await db.execute(
        select(RestaurantConfig).where(RestaurantConfig.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if row is None or not row.loyalty_enabled:
        return LoyaltySettings(False, 5, None, "", 1)
    label = row.loyalty_reward_label
    if not label and row.loyalty_reward_menu_item_id:
        name = (await db.execute(
            select(MenuItem.name).where(MenuItem.id == row.loyalty_reward_menu_item_id,
                                        MenuItem.tenant_id == tenant_id)
        )).scalar_one_or_none()
        label = f"Free {name}" if name else None
    return LoyaltySettings(
        True,
        max(int(row.loyalty_visits_required or 5), 1),
        row.loyalty_reward_menu_item_id,
        label or "A free reward",
        max(int(row.loyalty_max_visits_per_day or 0), 0),
    )


async def _tz_name(db: AsyncSession, tenant_id: uuid.UUID) -> str | None:
    return (await db.execute(
        select(RestaurantConfig.timezone).where(RestaurantConfig.tenant_id == tenant_id)
    )).scalar_one_or_none()


async def progress_for(
    db: AsyncSession, tenant_id: uuid.UUID, customer: Customer, settings: LoyaltySettings
) -> Progress:
    visits = (await db.execute(
        select(func.count(LoyaltyVisit.id), func.max(LoyaltyVisit.visit_date)).where(
            LoyaltyVisit.tenant_id == tenant_id, LoyaltyVisit.customer_id == customer.id)
    )).one()
    redeemed = (await db.execute(
        select(func.count(LoyaltyRedemption.id)).where(
            LoyaltyRedemption.tenant_id == tenant_id,
            LoyaltyRedemption.customer_id == customer.id)
    )).scalar_one()
    total = int(visits[0] or 0)
    n = settings.visits_required
    earned = total // n
    return Progress(
        customer_id=customer.id,
        customer_name=customer.name,
        phone=customer.phone,
        total_visits=total,
        visits_required=n,
        toward_next=total - earned * n,
        rewards_earned=earned,
        rewards_redeemed=int(redeemed or 0),
        rewards_available=max(earned - int(redeemed or 0), 0),
        reward_label=settings.reward_label,
        last_visit=visits[1].isoformat() if visits[1] else None,
    )


async def _find_or_create_customer(
    db: AsyncSession, tenant_id: uuid.UUID, phone: str, name: str | None
) -> Customer:
    customer = (await db.execute(
        select(Customer).where(Customer.tenant_id == tenant_id, Customer.phone == phone)
    )).scalar_one_or_none()
    if customer is not None:
        return customer
    customer = Customer(tenant_id=tenant_id, phone=phone,
                        name=(name or "").strip()[:255] or "Loyalty member")
    db.add(customer)
    await db.flush()
    return customer


async def _record_visit(
    db: AsyncSession, tenant_id: uuid.UUID, order: Order, customer: Customer, source: str,
    max_per_day: int,
) -> str:
    """Insert the visit. Returns 'counted', 'already_counted' or 'daily_limit'."""
    existing = (await db.execute(
        select(LoyaltyVisit.customer_id).where(LoyaltyVisit.order_id == order.id)
    )).scalar_one_or_none()
    if existing is not None:
        return "already_counted"
    created = order.created_at or datetime.now(timezone.utc)
    if created.tzinfo is None:  # SQLite hands back naive UTC
        created = created.replace(tzinfo=timezone.utc)
    visit_date = created.astimezone(zone(await _tz_name(db, tenant_id))).date()
    if max_per_day > 0:
        # Serialise this customer's claims so two racing bills cannot both
        # pass the count below (Postgres row lock; SQLite has no FOR UPDATE).
        await db.execute(select(Customer.id).where(Customer.id == customer.id).with_for_update())
        today = (await db.execute(
            select(func.count(LoyaltyVisit.id)).where(LoyaltyVisit.tenant_id == tenant_id,
                                                      LoyaltyVisit.customer_id == customer.id,
                                                      LoyaltyVisit.visit_date == visit_date)
        )).scalar_one()
        if today >= max_per_day:
            return "daily_limit"
    try:
        async with db.begin_nested():
            db.add(LoyaltyVisit(tenant_id=tenant_id, customer_id=customer.id,
                                order_id=order.id, visit_date=visit_date, source=source))
            await db.flush()
    except IntegrityError:
        # Lost a race to the other route (cashier vs scan): the constraint held.
        return "already_counted"
    _queue_wallet_push(db, tenant_id, customer.id, notify=True)
    return "counted"


async def ensure_code(db: AsyncSession, tenant_id: uuid.UUID, order: Order) -> None:
    """Give a new order its loyalty code when the tenant has loyalty on."""
    if order.loyalty_code or order.order_type not in ("dine_in", "takeaway", "call_center"):
        return
    if not (await get_settings(db, tenant_id)).enabled:
        return
    order.loyalty_code = new_code()


async def on_order_paid(db: AsyncSession, tenant_id: uuid.UUID, order: Order) -> None:
    """Cashier route: the bill is paid and carries a customer phone. Never raises."""
    try:
        if order.payment_status != "paid" or order.status == "voided":
            return
        # Read the number from the database, not the copy loaded at the start of
        # the payment: a guest may have scanned the bill at the table meanwhile.
        row = (await db.execute(
            select(Order.customer_phone, Order.customer_name).where(Order.id == order.id)
        )).one()
        phone = normalize_phone(row.customer_phone)
        if phone is None:
            return
        settings = await get_settings(db, tenant_id)
        if not settings.enabled:
            return
        async with db.begin_nested():
            customer = await _find_or_create_customer(db, tenant_id, phone, row.customer_name)
            await _record_visit(db, tenant_id, order, customer, "cashier",
                                settings.max_visits_per_day)
    except Exception:  # noqa: BLE001 - loyalty must never block taking money
        logger.exception("Loyalty visit not recorded for order %s", order.id)


# --- Public QR claim -------------------------------------------------------

@dataclass
class ClaimInfo:
    status: str  # open | counted | linked | pending | expired | disabled
    restaurant_name: str
    visits_required: int
    reward_label: str
    order_number: str
    tenant_slug: str  # D-106: the claim page shows the shop's own logo
    progress: Progress | None = None


async def _order_by_code(db: AsyncSession, code: str) -> Order:
    order = (await db.execute(
        select(Order).where(Order.loyalty_code == code.strip().upper())
    )).scalar_one_or_none()
    if order is None:
        raise LoyaltyError("This code is not valid.")
    return order


async def claim_info(db: AsyncSession, code: str) -> ClaimInfo:
    order = await _order_by_code(db, code)
    tenant_id = order.tenant_id
    name, slug = (await db.execute(
        select(Tenant.name, Tenant.slug).where(Tenant.id == tenant_id))).one()
    settings = await get_settings(db, tenant_id)
    info = ClaimInfo("open", name, settings.visits_required, settings.reward_label,
                     order.order_number, slug)
    if not settings.enabled:
        info.status = "disabled"
    elif order.status == "voided":
        info.status = "expired"
    elif order.created_at and datetime.now(timezone.utc) - (
        order.created_at if order.created_at.tzinfo else order.created_at.replace(tzinfo=timezone.utc)
    ) > CLAIM_WINDOW:
        info.status = "expired"
    elif (await db.execute(select(LoyaltyVisit.id).where(LoyaltyVisit.order_id == order.id))
          ).scalar_one_or_none() is not None:
        info.status = "counted"
    elif normalize_phone(order.customer_phone) is not None:
        # A number is on the bill. Unpaid: the guest scanned it at the table and
        # the visit counts at payment. Paid: the cashier route owns it.
        info.status = "pending" if order.payment_status != "paid" else "linked"
    # An unpaid bill with no number stays "open": in dine-in the bill reaches
    # the table before payment, and that is when guests scan it.
    return info


async def claim(db: AsyncSession, code: str, phone_raw: str, name: str | None) -> tuple[str, Progress]:
    """Customer route. Returns (result, progress); result is counted | daily_limit | pending.

    `pending`: the bill is not paid yet (dine-in: the bill comes to the table
    first). The number goes on the bill, and the visit is counted by
    `on_order_paid` when it is paid, under the same rules as a number the
    cashier typed.
    """
    phone = normalize_phone(phone_raw)
    info = await claim_info(db, code)
    if info.status == "counted":
        raise LoyaltyError("This bill has already been counted.")
    if info.status in ("linked", "pending"):
        raise LoyaltyError("This bill is already linked to a customer's loyalty card.")
    if info.status in ("expired", "disabled"):
        raise LoyaltyError("This code can no longer be used.")
    if phone is None:
        raise LoyaltyError("Please enter a valid mobile number.")
    # Lock the bill: a payment landing at the same moment must either see the
    # number (and count the visit) or have finished first (and we count it here).
    order = (await db.execute(
        select(Order).where(Order.loyalty_code == code.strip().upper())
        .with_for_update().execution_options(populate_existing=True)
    )).scalar_one()
    settings = await get_settings(db, order.tenant_id)
    customer = await _find_or_create_customer(db, order.tenant_id, phone, name)
    if order.payment_status != "paid":
        if normalize_phone(order.customer_phone) is not None:
            raise LoyaltyError("This bill is already linked to a customer's loyalty card.")
        order.customer_phone = phone
        if not order.customer_name and (name or "").strip():
            order.customer_name = name.strip()[:255]
        await db.flush()
        return "pending", await progress_for(db, order.tenant_id, customer, settings)
    result = await _record_visit(db, order.tenant_id, order, customer, "qr",
                                 settings.max_visits_per_day)
    if result == "already_counted":
        raise LoyaltyError("This bill has already been counted.")
    return result, await progress_for(db, order.tenant_id, customer, settings)


# --- Staff side -----------------------------------------------------------

async def progress_by_phone(db: AsyncSession, tenant_id: uuid.UUID, phone_raw: str) -> Progress | None:
    settings = await get_settings(db, tenant_id)
    phone = normalize_phone(phone_raw)
    if not settings.enabled or phone is None:
        return None
    customer = (await db.execute(
        select(Customer).where(Customer.tenant_id == tenant_id, Customer.phone == phone)
    )).scalar_one_or_none()
    if customer is None:
        return None
    return await progress_for(db, tenant_id, customer, settings)


async def order_status(db: AsyncSession, tenant_id: uuid.UUID, order_id: uuid.UUID) -> dict:
    """What the payment screen needs: progress, and whether a reward can go on this bill."""
    order = (await db.execute(
        select(Order).where(Order.id == order_id, Order.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if order is None:
        raise LoyaltyError("Order not found")
    settings = await get_settings(db, tenant_id)
    out: dict = {"enabled": settings.enabled, "loyalty_code": order.loyalty_code,
                 "reward_label": settings.reward_label, "progress": None,
                 "reward_on_bill": False, "redeemed_on_this_bill": False,
                 "can_redeem": False}
    if not settings.enabled:
        return out
    out["redeemed_on_this_bill"] = (await db.execute(
        select(LoyaltyRedemption.id).where(LoyaltyRedemption.order_id == order.id)
    )).scalar_one_or_none() is not None
    out["reward_on_bill"] = settings.reward_menu_item_id is not None and any(
        i.menu_item_id == settings.reward_menu_item_id for i in await _items(db, order))
    phone = normalize_phone(order.customer_phone)
    if phone:
        p = await progress_by_phone(db, tenant_id, phone)
        if p is not None:
            out["progress"] = p.__dict__ | {"customer_id": str(p.customer_id)}
            out["can_redeem"] = (p.rewards_available > 0 and out["reward_on_bill"]
                                 and not out["redeemed_on_this_bill"]
                                 and order.payment_status != "paid")
    return out


async def _items(db: AsyncSession, order: Order) -> list:
    from app.models.order import OrderItem

    return list((await db.execute(
        select(OrderItem).where(OrderItem.order_id == order.id)
    )).scalars().all())


async def redeem(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID,
                 order_id: uuid.UUID) -> Progress:
    """Put one reward on an unpaid bill that carries the reward item."""
    settings = await get_settings(db, tenant_id)
    if not settings.enabled or settings.reward_menu_item_id is None:
        raise LoyaltyError("Loyalty rewards are not set up. Choose a reward item in Settings.")
    order = (await db.execute(
        select(Order).where(Order.id == order_id, Order.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if order is None:
        raise LoyaltyError("Order not found")
    if order.payment_status == "paid" or order.status == "voided":
        raise LoyaltyError("A reward can only go on an unpaid bill.")
    phone = normalize_phone(order.customer_phone)
    if phone is None:
        raise LoyaltyError("Add the customer's phone number to the order first.")
    customer = (await db.execute(
        select(Customer).where(Customer.tenant_id == tenant_id, Customer.phone == phone)
    )).scalar_one_or_none()
    if customer is None:
        raise LoyaltyError("This customer has no visits yet.")
    p = await progress_for(db, tenant_id, customer, settings)
    if p.rewards_available < 1:
        raise LoyaltyError(f"No reward available yet ({p.toward_next} of {p.visits_required} visits).")
    item = next((i for i in await _items(db, order)
                 if i.menu_item_id == settings.reward_menu_item_id), None)
    if item is None:
        raise LoyaltyError(f"Add the reward item to the bill first ({settings.reward_label}).")
    if (await db.execute(select(LoyaltyRedemption.id).where(
            LoyaltyRedemption.order_id == order.id))).scalar_one_or_none() is not None:
        raise LoyaltyError("A reward is already on this bill.")

    od = OrderDiscount(tenant_id=tenant_id, order_id=order.id, label=f"Loyalty: {settings.reward_label}",
                       source_type="loyalty", amount=item.unit_price, percent_bps=0,
                       note=f"{p.visits_required} visits reward", applied_by=user_id)
    db.add(od)
    await db.flush()
    db.add(LoyaltyRedemption(tenant_id=tenant_id, customer_id=customer.id, order_id=order.id,
                             order_discount_id=od.id, amount=item.unit_price,
                             redeemed_by=user_id))
    await db.flush()
    from app.services import discount_service

    await discount_service._sync_order_discount(db, tenant_id, order.id)
    _queue_wallet_push(db, tenant_id, customer.id, notify=False)
    return await progress_for(db, tenant_id, customer, settings)


async def display_current(
    db: AsyncSession, tenant_id: uuid.UUID, with_idle: bool = False
) -> dict | None:
    """Counter screen: the QR of the bill paid most recently, while it can still be claimed.

    Only the newest paid bill is ever shown. Once it is claimed, or it carries
    a customer phone (the cashier route owns it), the screen goes blank; it
    never falls back to an older unclaimed bill, whose customer has left and
    whose visit the next person in the queue must not be able to take.
    "Newest" is by the time of the bill's last payment, not `updated_at`,
    which a later kitchen or status change also moves.
    """
    from app.models.payment import Payment

    settings = await get_settings(db, tenant_id)
    if not settings.enabled:
        return None
    since = datetime.now(timezone.utc) - DISPLAY_WINDOW
    order = (await db.execute(
        select(Order)
        .join(Payment, Payment.order_id == Order.id)
        .where(
            Order.tenant_id == tenant_id,
            Order.payment_status == "paid",
            Order.loyalty_code.is_not(None),
            Payment.tenant_id == tenant_id,
            Payment.kind == "payment",
            Payment.status == "completed",
            Payment.created_at >= since,
        )
        .order_by(Payment.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    # D-106: the idle screen explains the card, so with `with_idle` the rule goes
    # out with null QR fields when no bill is waiting. Opt-in: a counter page
    # still running the old bundle reads any object as a bill to scan.
    idle = ({"loyalty_code": None, "order_number": None, "total": None,
             "reward_label": settings.reward_label, "visits_required": settings.visits_required}
            if with_idle else None)
    if order is None or normalize_phone(order.customer_phone) is not None:
        return idle
    if (await db.execute(select(LoyaltyVisit.id).where(LoyaltyVisit.order_id == order.id))
            ).scalar_one_or_none() is not None:
        return idle
    return {"loyalty_code": order.loyalty_code, "order_number": order.order_number,
            "total": order.total, "reward_label": settings.reward_label,
            "visits_required": settings.visits_required}


async def members(db: AsyncSession, tenant_id: uuid.UUID) -> list[Progress]:
    settings = await get_settings(db, tenant_id)
    ids = (await db.execute(
        select(LoyaltyVisit.customer_id).where(LoyaltyVisit.tenant_id == tenant_id).distinct()
    )).scalars().all()
    if not ids:
        return []
    customers = (await db.execute(
        select(Customer).where(Customer.tenant_id == tenant_id, Customer.id.in_(ids))
    )).scalars().all()
    if not settings.enabled:
        settings = LoyaltySettings(False, settings.visits_required, None, "",
                                   settings.max_visits_per_day)
    rows = [await progress_for(db, tenant_id, c, settings) for c in customers]
    return sorted(rows, key=lambda r: (r.last_visit or ""), reverse=True)


# --- Google Wallet card ---------------------------------------------------
#
# A guest who collected a visit can add the card to Google Wallet. From then
# on each counted visit (and each reward used) updates the card on their
# phone, with a notification for visits. The push to Google runs only AFTER
# the payment's transaction commits, in its own task: a slow or failing Google
# never holds up taking money, and a rolled-back payment never notifies.

_WALLET_KEY = "loyalty_wallet_push"
_wallet_tasks: set[asyncio.Task] = set()


def _queue_wallet_push(db: AsyncSession, tenant_id: uuid.UUID, customer_id: uuid.UUID,
                       notify: bool) -> None:
    if not google_wallet.enabled():
        return
    queued = db.sync_session.info.setdefault(_WALLET_KEY, {})
    queued[customer_id] = (tenant_id, notify or queued.get(customer_id, (None, False))[1])


@event.listens_for(Session, "after_commit")
def _after_commit(session: Session) -> None:
    # SQLAlchemy also fires this when a SAVEPOINT is released, and the visit is
    # written inside one: pushing then would read the count before the payment
    # commits (the card said "0 of 5"). Only the real commit sends.
    if session.in_nested_transaction():
        return
    queued = session.info.pop(_WALLET_KEY, None)
    if not queued:
        return
    for customer_id, (tenant_id, notify) in queued.items():
        _schedule(_push_wallet(tenant_id, customer_id, notify))


def _schedule(coro) -> None:
    """Run the push in the background (tests replace this to run it in step)."""
    try:
        task = asyncio.get_running_loop().create_task(coro)
    except RuntimeError:
        coro.close()
        return
    _wallet_tasks.add(task)
    task.add_done_callback(_wallet_tasks.discard)


@event.listens_for(Session, "after_rollback")
def _after_rollback(session: Session) -> None:
    if session.in_nested_transaction():
        return  # a savepoint: the outer transaction decides (the push re-reads the count)
    session.info.pop(_WALLET_KEY, None)


async def _wallet_card(db: AsyncSession, tenant_id: uuid.UUID, customer: Customer
                       ) -> google_wallet.Card | None:
    name, slug = (await db.execute(
        select(Tenant.name, Tenant.slug).where(Tenant.id == tenant_id))).one()
    if not google_wallet.available_for(slug):
        return None
    settings = await get_settings(db, tenant_id)
    if not settings.enabled:
        return None
    p = await progress_for(db, tenant_id, customer, settings)
    member = customer.name if customer.name and customer.name != "Loyalty member" else "Member"
    return google_wallet.Card(
        slug=slug, restaurant_name=name, customer_id=customer.id, member_name=member,
        phone=customer.phone, masked_phone=mask_phone(customer.phone),
        toward_next=p.toward_next, visits_required=p.visits_required,
        rewards_available=p.rewards_available, reward_label=p.reward_label)


async def _push_wallet(tenant_id: uuid.UUID, customer_id: uuid.UUID, notify: bool) -> None:
    from app.database import async_session_factory

    try:
        async with async_session_factory() as db:
            has_card = (await db.execute(select(LoyaltyWalletPass.id).where(
                LoyaltyWalletPass.tenant_id == tenant_id,
                LoyaltyWalletPass.customer_id == customer_id,
                LoyaltyWalletPass.platform == "google"))).scalar_one_or_none()
            if has_card is None:
                return
            customer = (await db.execute(select(Customer).where(
                Customer.id == customer_id, Customer.tenant_id == tenant_id))).scalar_one()
            card = await _wallet_card(db, tenant_id, customer)
        if card is not None:
            result = await google_wallet.push_update(card, notify)
            logger.info("Wallet card %s: %s", customer_id, result)
    except Exception:  # noqa: BLE001 - a card update must never surface as an error
        logger.exception("Wallet card not updated for customer %s", customer_id)


def mask_phone(phone: str) -> str:
    return phone[:4] + "*" * max(len(phone) - 7, 0) + phone[-3:] if len(phone) > 7 else phone


async def wallet_link(db: AsyncSession, code: str, phone_raw: str) -> str:
    """The "Add to Google Wallet" link for the guest who claimed this bill.

    The caller must give the same number that is on the bill, so a bill's QR
    alone never opens someone else's card (the card's barcode is the number).
    """
    order = await _order_by_code(db, code)
    phone = normalize_phone(phone_raw)
    on_bill = normalize_phone(order.customer_phone)
    if on_bill is None:
        visit_customer = (await db.execute(
            select(Customer.phone).join(LoyaltyVisit, LoyaltyVisit.customer_id == Customer.id)
            .where(LoyaltyVisit.order_id == order.id))).scalar_one_or_none()
        on_bill = normalize_phone(visit_customer)
    if phone is None or phone != on_bill:
        raise LoyaltyError("Collect your visit first, then add the card.")
    customer = (await db.execute(select(Customer).where(
        Customer.tenant_id == order.tenant_id, Customer.phone == phone))).scalar_one_or_none()
    if customer is None:
        raise LoyaltyError("Collect your visit first, then add the card.")
    card = await _wallet_card(db, order.tenant_id, customer)
    if card is None:
        raise LoyaltyError("Google Wallet cards are not available here yet.")
    try:
        await google_wallet.upsert(card)
    except google_wallet.WalletError as exc:
        logger.error("Wallet card not created for %s: %s", customer.id, exc)
        raise LoyaltyError("Google Wallet is not reachable right now. Please try again.") from exc
    exists = (await db.execute(select(LoyaltyWalletPass.id).where(
        LoyaltyWalletPass.customer_id == customer.id,
        LoyaltyWalletPass.platform == "google"))).scalar_one_or_none()
    if exists is None:
        try:
            async with db.begin_nested():
                db.add(LoyaltyWalletPass(tenant_id=order.tenant_id, customer_id=customer.id,
                                         platform="google",
                                         object_id=google_wallet.object_id(customer.id)))
                await db.flush()
        except IntegrityError:
            pass  # the same guest tapped twice at once; the row is there
    return google_wallet.save_url(card)
