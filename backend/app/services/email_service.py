"""Transactional email for online orders.

Four messages, all to the customer:

    received   we have your order, the shop has not answered yet
    accepted   confirmed, with the lead time the shop promised
    rejected   turned down, with the shop's reason
    on_the_way out for delivery, or ready to collect

⚠️ **An email must never be able to fail an order.**

The order is the product; the email is a courtesy on top of it. Every send is
wrapped so that a dead mail server, a bad password or a DNS blip cannot roll
back an accepted order or 500 a checkout. Failures are logged loudly and
swallowed. This mirrors the SAVEPOINT reasoning already used for audit logging:
a non-critical side effect must not poison the caller.

Two transports, chosen by configuration (OI-55):

    BREVO_API_KEY set  -> Brevo's HTTPS API. Production must use this: the
        DigitalOcean droplet cannot reach ANY outbound SMTP port (25/465/587
        time out, 2525 resets) and api.mailjet.com TLS-resets from that box,
        while api.brevo.com handshakes fine -- all measured FROM THE DROPLET
        on 2026-07-29. A connectivity claim proves only the path it ran on.

    SMTP_* set         -> plain smtplib, kept for any future host whose
        egress permits mail. Synchronous, so sends run in a worker thread.

If `settings.email_configured` is false, every function here returns without
doing anything. That is the default, and it is why the system runs unchanged
until someone supplies credentials.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

import httpx

from app.config import settings
from app.models.order import Order

logger = logging.getLogger(__name__)

# A send is a courtesy, not a transaction. Keep it short so a hung mail server
# cannot tie up a worker thread (or the event loop) for the length of a service.
_SMTP_TIMEOUT_SECONDS = 15
_API_TIMEOUT_SECONDS = 15

# Contract verified against https://developers.brevo.com/reference/send-transac-email
# on 2026-07-29: POST with an `api-key` header; body carries `sender`, `to`,
# `subject`, `textContent`, `replyTo`; success is HTTP 201 with a messageId.
_BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"


def _money(amount: int, currency: str) -> str:
    """Integer minor units to a display string. 1499 GBP -> "£14.99"."""
    symbol = {"GBP": "£", "PKR": "Rs.", "USD": "$", "EUR": "€"}.get(currency, "")
    return f"{symbol}{amount / 100:,.2f}"


def _order_lines(order: Order, currency: str) -> str:
    rows = []
    for item in order.items:
        line = f"  {item.quantity} x {item.name}"
        modifiers = [m.name for m in item.modifiers]
        if modifiers:
            line += f" ({', '.join(modifiers)})"
        rows.append(f"{line:<48} {_money(item.total, currency)}")
    return "\n".join(rows)


def _totals(order: Order, currency: str) -> str:
    rows = [f"{'Subtotal':<48} {_money(order.subtotal, currency)}"]
    if order.tax_amount:
        rows.append(f"{'Tax':<48} {_money(order.tax_amount, currency)}")
    if order.delivery_fee:
        rows.append(f"{'Delivery':<48} {_money(order.delivery_fee, currency)}")
    rows.append(f"{'TOTAL':<48} {_money(order.total, currency)}")
    return "\n".join(rows)


def _tracking_line(order: Order) -> str:
    if not settings.ORDER_TRACKING_BASE_URL:
        return ""
    base = settings.ORDER_TRACKING_BASE_URL.rstrip("/")
    return f"\nTrack your order:\n{base}/{order.id}\n"


def _collecting(order: Order) -> bool:
    return (order.service_type or "collection") != "delivery"


# ---------------------------------------------------------------------------
# Bodies
# ---------------------------------------------------------------------------


def _body_received(order: Order, shop: str, currency: str) -> tuple[str, str]:
    subject = f"{shop}: we've got your order {order.order_number}"
    body = f"""Hi {order.customer_name or 'there'},

Thanks for your order. We've received it and the shop will confirm it shortly.

Order {order.order_number}

{_order_lines(order, currency)}

{_totals(order, currency)}

{'Collection' if _collecting(order) else 'Delivery to: ' + (order.delivery_address or '')}
{_tracking_line(order)}
We'll email you again as soon as the shop confirms your {'collection' if _collecting(order) else 'delivery'} time.

{shop}
"""
    return subject, body


def _body_accepted(order: Order, shop: str, currency: str) -> tuple[str, str]:
    eta = order.eta_minutes
    when = f"in about {eta} minutes" if eta else "shortly"
    subject = f"{shop}: order {order.order_number} confirmed"
    headline = (
        f"Your order is confirmed and will be ready for collection {when}."
        if _collecting(order)
        else f"Your order is confirmed and will be delivered {when}."
    )
    body = f"""Hi {order.customer_name or 'there'},

{headline}

Order {order.order_number}

{_order_lines(order, currency)}

{_totals(order, currency)}

{'Collection' if _collecting(order) else 'Delivery to: ' + (order.delivery_address or '')}
Payment: {'paid' if order.payment_status == 'paid' else 'due on ' + ('collection' if _collecting(order) else 'delivery')}
{_tracking_line(order)}
{shop}
"""
    return subject, body


def _body_rejected(order: Order, shop: str, currency: str) -> tuple[str, str]:
    reason = (order.rejection_reason or "").strip() or (
        "The shop is unable to take this order right now."
    )
    subject = f"{shop}: sorry, we couldn't take order {order.order_number}"
    body = f"""Hi {order.customer_name or 'there'},

We're sorry, but we aren't able to take this order.

{reason}

Nothing has been charged. If you'd like to sort something out, please give us a
call and we'll do our best.

Order {order.order_number}
Total would have been {_money(order.total, currency)}

{shop}
"""
    return subject, body


def _body_on_the_way(order: Order, shop: str, currency: str) -> tuple[str, str]:
    if _collecting(order):
        subject = f"{shop}: order {order.order_number} is ready to collect"
        headline = "Your order is ready and waiting for you at the shop."
    else:
        subject = f"{shop}: order {order.order_number} is on its way"
        headline = "Your order has left the shop and is on its way to you."

    body = f"""Hi {order.customer_name or 'there'},

{headline}

Order {order.order_number}
{_money(order.total, currency)} {'(paid)' if order.payment_status == 'paid' else '- payable on ' + ('collection' if _collecting(order) else 'delivery')}
{_tracking_line(order)}
{shop}
"""
    return subject, body


_BUILDERS = {
    "received": _body_received,
    "accepted": _body_accepted,
    "rejected": _body_rejected,
    "on_the_way": _body_on_the_way,
}


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------


async def _send_via_brevo(to: str, subject: str, body: str) -> None:
    """One transactional send through Brevo's HTTPS API.

    Raises on anything but the documented 201 so the caller's catch-all can
    log it -- a 2xx-that-isn't-201 from this endpoint would mean the contract
    changed under us, which is worth a loud log line, not a silent success.
    """
    sender: dict[str, str] = {"email": settings.EMAIL_FROM}
    if settings.EMAIL_FROM_NAME:
        sender["name"] = settings.EMAIL_FROM_NAME

    payload: dict[str, object] = {
        "sender": sender,
        "to": [{"email": to}],
        "subject": subject,
        "textContent": body,
    }
    # Same reasoning as the SMTP path: the sending address is not a mailbox,
    # so replies must be pointed at one the shop actually reads.
    reply_to = settings.EMAIL_REPLY_TO or settings.EMAIL_FROM
    if reply_to:
        payload["replyTo"] = {"email": reply_to}

    async with httpx.AsyncClient(timeout=_API_TIMEOUT_SECONDS) as client:
        response = await client.post(
            _BREVO_ENDPOINT,
            json=payload,
            headers={"api-key": settings.BREVO_API_KEY, "accept": "application/json"},
        )
    if response.status_code != 201:
        raise RuntimeError(
            f"Brevo refused the send: HTTP {response.status_code} "
            f"{response.text[:300]}"
        )


def _send_blocking(to: str, subject: str, body: str) -> None:
    """Synchronous SMTP send. Runs in a worker thread, never on the loop."""
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr(
        (settings.EMAIL_FROM_NAME or None, settings.EMAIL_FROM)  # type: ignore[arg-type]
    )
    message["To"] = to
    # A sending domain is not a mailbox. We relay as orders@<shop> because that
    # is what a customer should see, but nothing guarantees that address
    # receives anything -- so point replies at one the shop actually reads.
    reply_to = settings.EMAIL_REPLY_TO or settings.EMAIL_FROM
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(body)

    if settings.SMTP_SSL:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=_SMTP_TIMEOUT_SECONDS,
            context=context,
        ) as server:
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)
        return

    with smtplib.SMTP(
        settings.SMTP_HOST, settings.SMTP_PORT, timeout=_SMTP_TIMEOUT_SECONDS
    ) as server:
        if settings.SMTP_STARTTLS:
            server.starttls(context=ssl.create_default_context())
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(message)


async def send_order_email(
    order: Order,
    event: str,
    *,
    shop_name: str = "Chick Shack",
    currency: str = "GBP",
) -> bool:
    """Send one order email. Returns True only if it actually went out.

    Never raises. A failure here must not touch the order: by the time this is
    called the customer has already been told yes or no, and un-accepting an
    order because a mail server hiccuped would be far worse than a missing
    email.
    """
    if event not in _BUILDERS:
        logger.error("Unknown order email event %r", event)
        return False

    to = (order.customer_email or "").strip()
    if not to:
        # Expected for phone-only customers and for orders placed before email
        # was collected. Not an error.
        logger.info("Order %s has no email address; skipping %s", order.order_number, event)
        return False

    if not settings.email_configured:
        logger.warning(
            "Email not configured (BREVO_API_KEY or SMTP_HOST, plus EMAIL_FROM); "
            "would have sent %r for order %s",
            event,
            order.order_number,
        )
        return False

    subject, body = _BUILDERS[event](order, shop_name, currency)

    try:
        if settings.BREVO_API_KEY:
            await _send_via_brevo(to, subject, body)
        else:
            await asyncio.to_thread(_send_blocking, to, subject, body)
    except Exception:
        # Deliberately broad: smtplib raises a wide family, DNS/socket errors
        # surface as OSError, and httpx has its own tree. Nothing here is
        # worth propagating.
        logger.exception(
            "Failed to send %r email for order %s", event, order.order_number
        )
        return False

    logger.info("Sent %r email for order %s", event, order.order_number)
    return True
