"""Turn an online order into a printable kitchen ticket.

Where this sits in the chain
----------------------------
    customer orders on the website
      -> POST /public/orders            (order lands in Postgres)
      -> tablet in the shop is notified (WebSocket, already exists)
      -> shop taps ACCEPT               (he does this by hand for every order)
      -> THIS builds the ticket bytes
      -> tablet hands them to RawBT     (rawbt: URL scheme)
      -> RawBT opens TCP:9100           (printer is on the shop LAN)
      -> ticket prints

The print is triggered by the Accept tap, not by a background service. That
matters: it is the reason no daemon has to survive Android's battery killer,
and therefore the reason no Raspberry Pi or mini PC is needed in the shop.

Confirmed by the client 2026-07-27: the kitchen printer is on an Ethernet
switch which is on the broadband router, so it is on the shop LAN and reachable
from the tablet's Wi-Fi. See `_state/printing.md`.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.services import escpos, order_service
from app.services.escpos import Ticket

# Symbols for the currencies this product actually ships in. Anything else
# falls back to the ISO code plus a space, which is ugly but never wrong.
_CURRENCY_SYMBOLS = {
    "GBP": "£",
    "PKR": "Rs.",
    "USD": "$",
    "EUR": "EUR ",
    "AED": "AED ",
}

DIP_TUB_SUFFIX = " (Dip Tub)"


def money(minor_units: int, currency: str) -> str:
    """Format integer minor units for print.

    Everything in this system is integer pence/paisa on purpose, so this is the
    only place the decimal point is introduced.
    """
    symbol = _CURRENCY_SYMBOLS.get(currency.upper(), f"{currency.upper()} ")
    return f"{symbol}{minor_units / 100:,.2f}"


def _local(dt: datetime | None, offset_minutes: int) -> datetime | None:
    """Shift a UTC timestamp to the shop's wall clock.

    Timestamps are stored UTC. A kitchen ticket showing 17:42 when the clock on
    the wall says 18:42 is worse than useless during a rush, and the server is
    in Singapore while the shop is in Scotland.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(minutes=offset_minutes)))


def _daily_number(order_number: str | None) -> str:
    """The day's running number — the `NNN` of `YYMMDD-NNN` that staff shout out.

    The numbering itself already exists and already resets at 001 each day
    (order numbers are generated as `YYMMDD-NNN`); this only extracts it for
    display. Do not add a counter here.
    """
    if not order_number:
        return ""
    return order_number.rsplit("-", 1)[-1]


def build_online_order_ticket(
    order: Order,
    *,
    shop_name: str,
    currency: str = "GBP",
    width: int = 48,
    utc_offset_minutes: int = 60,
    copies: int = 1,
) -> bytes:
    """Render one accepted online order as ESC/POS bytes.

    This is a KITCHEN ticket, not a customer receipt: it leads with what has to
    be cooked and how it leaves the building. Money is included because for a
    delivery the driver needs to know whether to collect cash, and that is the
    single most expensive thing to get wrong on a ticket.

    `copies` repeats the whole ticket inside ONE payload, each copy cut into
    its own slip -- identical, unlabelled: all three go to separate stations,
    none of them is "the extra one" (Imran, 2026-08-01). The repeat lives here
    and not in the tablet because every `rawbt:` navigation is a separate
    chance for Chrome to drop or coalesce the handoff (see ERROR_LOG
    2026-07-29): one payload, one navigation, N slips.
    """
    t = Ticket(width=width)
    copies = max(1, copies)
    for _ in range(copies):
        _render_copy(
            t,
            order,
            shop_name=shop_name,
            currency=currency,
            utc_offset_minutes=utc_offset_minutes,
        )
    return t.bytes()


def _render_copy(
    t: Ticket,
    order: Order,
    *,
    shop_name: str,
    currency: str,
    utc_offset_minutes: int,
) -> None:
    """One complete slip, ending in its own cut."""
    is_delivery = (order.service_type or "").lower() == "delivery"
    heading = "DELIVERY" if is_delivery else "COLLECTION"

    # The day's number, first and unmissable. The kitchen works by this, not
    # by the full order number. Double size is the largest this exact printer
    # has proven on paper (photographed 2026-07-29) — do not go bigger untested.
    daily = _daily_number(order.order_number)
    if daily:
        t.center(f"#{daily}", bold=True, big=True)
    t.rule()

    t.center(shop_name, bold=True, big=True)
    t.center("ONLINE ORDER")
    t.feed()
    t.center(heading, bold=True, big=True)
    t.rule("=")

    placed = _local(order.created_at, utc_offset_minutes)
    accepted = _local(order.accepted_at, utc_offset_minutes)

    t.bold(f"ORDER {order.order_number}")
    if placed:
        t.field("Placed", f"{placed:%H:%M}, {placed:%d %b}")

    # The promised time is what the customer is holding us to, so compute and
    # print it rather than making the kitchen add minutes in their head.
    if order.eta_minutes and accepted:
        ready = accepted + timedelta(minutes=order.eta_minutes)
        t.bold(f"{'DELIVER BY' if is_delivery else 'READY AT'} {ready:%H:%M}"
               f"   ({order.eta_minutes} min)")

    t.rule()

    # --- dip tubs, listed first and separately (Imran, voice note
    # 2026-08-03) --- a dip tub chosen as a meal's modifier used to print as
    # a buried sub-line under whichever item it was attached to, easy for a
    # busy packer to miss entirely. Every dip-tub modifier, whichever item it
    # came from, is rolled up here by name -- one number to count out,
    # before any cooking starts. Standalone Dips-category items (sold on
    # their own, no "(Dip Tub)" suffix) are unaffected and print in the cook
    # list below exactly as before -- nothing was reported wrong there.
    dip_tub_counts: dict[str, int] = {}
    for item in order.items:
        for modifier in item.modifiers:
            if modifier.name.endswith(DIP_TUB_SUFFIX):
                dip_tub_counts[modifier.name] = (
                    dip_tub_counts.get(modifier.name, 0) + item.quantity
                )
    if dip_tub_counts:
        t.bold("DIP TUBS")
        for name, qty in sorted(dip_tub_counts.items()):
            t.text(f"    {qty} x {name}")
        t.rule()

    # --- what to cook ---
    for item in order.items:
        t.bold(f"{item.quantity} x {item.name}")
        for modifier in item.modifiers:
            if modifier.name.endswith(DIP_TUB_SUFFIX):
                continue  # printed above, not again here
            t.text(f"    - {modifier.name}")
        if item.notes:
            for line in item.notes.split("\n"):
                if line.strip():
                    t.bold(f"    ** {line.strip()}")

    if order.notes:
        t.rule()
        t.bold("ORDER NOTES")
        t.text(order.notes)

    t.rule()

    # --- where it goes ---
    if order.customer_name:
        t.field("Name", order.customer_name)
    if order.customer_phone:
        # Bold: this is what the shop rings when the driver cannot find them.
        t.raw(escpos.BOLD_ON)
        t.field("Phone", order.customer_phone)
        t.raw(escpos.BOLD_OFF)

    if is_delivery:
        t.feed()
        t.bold("DELIVER TO")
        if order.delivery_address:
            t.text(order.delivery_address)
        if order.delivery_area:
            t.bold(order.delivery_area)

    t.rule()

    # --- money ---
    t.columns("Subtotal", money(order.subtotal, currency))
    if order.discount_amount:
        t.columns("Discount", f"-{money(order.discount_amount, currency)}")
    if order.tax_amount:
        t.columns("Tax", money(order.tax_amount, currency))
    if order.service_fee:
        t.columns("Service Fee", money(order.service_fee, currency))
    if order.delivery_fee:
        t.columns("Delivery", money(order.delivery_fee, currency))
    t.columns("TOTAL", money(order.total, currency), bold=True)

    t.feed()
    paid = (order.payment_status or "").lower() in {"paid", "refunded"}
    # A checkout session with no capture yet is NOT the same as genuinely
    # unpaid -- it is money that is very likely still on its way (Stripe
    # confirming the card, typically seconds). Printing "NOT PAID" here is
    # exactly what caused a real double-charge, 2026-08-02 (OI-61): a
    # customer paid online, the ticket said NOT PAID because it printed
    # before the authorisation landed, and staff took payment again on the
    # shop's own card machine. Since OI-65 a card order cannot reach the
    # kitchen at all until Stripe has confirmed the money -- the queue hides it
    # with no grace window, and `accept_order` refuses it outright -- so this
    # branch should now be effectively unreachable in practice. It stays
    # because a ticket is a physical, un-recallable printout: if it ever does
    # print, it must say something unambiguous rather than silently falling
    # into "NOT PAID" and inviting the exact same double-charge again.
    card_processing = not paid and order.stripe_checkout_session_id is not None
    if paid:
        # Unpaid is shouted, not whispered -- paid shouts too, just a calmer
        # message. Same bold+big weight as the NOT PAID line below.
        t.center("*** PAID ONLINE ***", bold=True, big=True)
    elif card_processing:
        # Short enough to survive double-size centering without wrapping --
        # see "*** PAID ONLINE ***"/"*** NOT PAID ***" above, same constraint.
        # Says APPROVED, not "processing": since OI-65 an unapproved card order
        # cannot reach the kitchen at all, so this state always means Stripe is
        # holding the money and the capture lands on Accept.
        t.center("*** CARD APPROVED ***", bold=True, big=True)
        t.center("DO NOT COLLECT CASH OR RE-CHARGE", bold=True)
    else:
        # Loud on purpose. A driver who assumes an order is prepaid does not
        # come back with the money.
        t.center("*** NOT PAID ***", bold=True, big=True)
        t.center(f"COLLECT {money(order.total, currency)}", bold=True)

    t.rule("=")
    t.cut()


async def build_ticket_for_order(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    *,
    width: int = 48,
    copies: int = 1,
) -> bytes:
    """Load an order and render its kitchen ticket.

    Raises LookupError if the order does not exist for this tenant, so the
    route can turn that into a 404 without leaking whether the id exists under
    some other tenant.
    """
    order = await order_service.get_order(db, order_id, tenant_id)
    if order is None:
        raise LookupError("Order not found.")

    config = (
        await db.execute(
            select(RestaurantConfig).where(RestaurantConfig.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()

    shop_name = (
        await db.execute(select(Tenant.name).where(Tenant.id == tenant_id))
    ).scalar_one_or_none() or "Order"

    currency = (config.currency if config else None) or "GBP"
    tz_name = (config.timezone if config else None) or "UTC"

    return build_online_order_ticket(
        order,
        shop_name=shop_name,
        currency=currency,
        width=width,
        utc_offset_minutes=_offset_minutes(tz_name, order.accepted_at or order.created_at),
        copies=copies,
    )


def _offset_minutes(tz_name: str, at: datetime | None) -> int:
    """Offset of the shop's timezone at a given instant, in minutes.

    Computed at the order's own timestamp rather than "now" so a ticket
    reprinted in winter still shows the summer time it was actually placed at.
    An unknown timezone falls back to UTC rather than raising -- a ticket with
    an hour-shifted time is bad, a ticket that fails to print is worse.
    """
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return 0
    moment = at or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    offset = moment.astimezone(tz).utcoffset()
    return int(offset.total_seconds() // 60) if offset else 0


def to_rawbt_url(payload: bytes) -> str:
    """Wrap ESC/POS bytes in the URL the tablet opens to print.

    RawBT is an Android ESC/POS driver that accepts a job via the `rawbt:`
    scheme and delivers it over Bluetooth, USB or **Ethernet/Wi-Fi on TCP:9100
    (AppSocket)**, which is the path we need. Base64 is built here rather than
    in the browser so the escape sequences live in one tested place.
    """
    return "rawbt:base64," + base64.b64encode(payload).decode("ascii")
