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
from html import escape as html_escape

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

# Brand constants, pulled from storefront/tailwind.config.js so the email
# doesn't look like a different business than the site. No logo/mascot asset
# exists (checked 2026-07-30) -- the wordmark is styled text everywhere,
# including here. Archivo Black/Inter (the site's fonts) don't render in most
# email clients, so headings fall back to a bold system sans-serif stack.
_C_INK = "#12100f"
_C_FLAME = "#e2361d"
_C_FLAME_DARK = "#b82413"
_C_EMBER = "#f5a524"
_C_CREAM = "#faf7f2"
_C_BODY_TEXT = "#2a2523"
_C_MUTED = "#6b6b6b"
_C_PAGE_BG = "#f2ede6"
_C_LINE = "#ecebe9"
_FONT_STACK = "'Helvetica Neue', Helvetica, Arial, sans-serif"


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
    if order.service_fee:
        rows.append(f"{'Service Fee':<48} {_money(order.service_fee, currency)}")
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


def _payment_status_text(order: Order, *, intends_card_payment: bool = False) -> str:
    """Same three states, same reasoning, as `OrderConfirmation.tsx` on the
    website: money is only TAKEN when the shop accepts, so a card order sitting
    between checkout and acceptance is "held", not "paid" -- the customer's
    bank shows a pending amount and nothing has actually left their account.
    An email claiming "paid" here, followed by the shop rejecting the order,
    would make the email a lie.

    `intends_card_payment` covers a fourth state neither the order's own
    columns nor `OrderConfirmation.tsx` can see: the "order received" email
    fires immediately on creation, before the customer has even been sent to
    Stripe, so `stripe_payment_intent_id` is never set yet for a card order at
    this point -- without this explicit, caller-supplied signal every card
    order would silently fall through to the cash wording below. See
    `PublicOrderCreate.payment_method`.
    """
    if order.payment_status == "paid":
        return "Paid by card."
    # `stripe_checkout_session_id`, not `stripe_payment_intent_id` -- the
    # session is written the instant checkout starts, well before Stripe has
    # necessarily created a PaymentIntent (see `accept_order`'s own comment on
    # this exact distinction). Keying this off the intent id left a window,
    # right after checkout started but before authorisation landed, where a
    # card order fell through to the "Payable on..." branch below and told
    # the customer to expect a cash collection despite having just paid --
    # confirmed as the direct cause of a real double-charge, 2026-08-02
    # (OI-61): staff read that as "unpaid" and took payment again in person.
    if order.stripe_checkout_session_id and order.payment_captured_at is None:
        return "Card details taken. We only charge you once the shop accepts your order."
    if intends_card_payment:
        return "Prepaid by card -- we only charge you once the shop accepts your order."
    return f"Payable on {'collection' if _collecting(order) else 'delivery'}."


# ---------------------------------------------------------------------------
# HTML bodies
#
# `customer_name` and `delivery_address` come straight from the public
# checkout form -- they are attacker-controlled strings, not staff-entered
# ones. Every dynamic value below goes through `html_escape` before it lands
# in markup. The plain-text bodies above never had this exposure because
# nothing there is parsed as markup.
# ---------------------------------------------------------------------------


def _html_items_table(order: Order, currency: str) -> str:
    rows = []
    for item in order.items:
        modifiers = [m.name for m in item.modifiers]
        mod_line = ""
        if modifiers:
            mod_text = html_escape(", ".join(modifiers))
            mod_line = (
                f'<div style="font-size:12px; color:{_C_MUTED}; margin-top:2px;">'
                f"{mod_text}</div>"
            )
        rows.append(
            f"""<tr>
<td style="padding:8px 0; font-size:14px; color:{_C_BODY_TEXT}; border-bottom:1px solid {_C_LINE};">
{item.quantity} &times; {html_escape(item.name)}{mod_line}
</td>
<td style="padding:8px 0; font-size:14px; color:{_C_BODY_TEXT}; text-align:right; white-space:nowrap; border-bottom:1px solid {_C_LINE};">
{html_escape(_money(item.total, currency))}
</td>
</tr>"""
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        + "".join(rows)
        + "</table>"
    )


def _html_totals_table(order: Order, currency: str) -> str:
    rows = [("Subtotal", order.subtotal, False)]
    if order.tax_amount:
        rows.append(("Tax", order.tax_amount, False))
    if order.service_fee:
        rows.append(("Service Fee", order.service_fee, False))
    if order.delivery_fee:
        rows.append(("Delivery", order.delivery_fee, False))
    rows.append(("TOTAL", order.total, True))

    cells = []
    for label, amount, bold in rows:
        size = "15px" if bold else "13px"
        weight = "700" if bold else "400"
        cells.append(
            f"""<tr>
<td style="padding:4px 0; font-size:{size}; font-weight:{weight}; color:{_C_BODY_TEXT};">{label}</td>
<td style="padding:4px 0; font-size:{size}; font-weight:{weight}; color:{_C_BODY_TEXT}; text-align:right;">{html_escape(_money(amount, currency))}</td>
</tr>"""
        )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="margin-top:8px; border-top:1px solid {_C_LINE}; padding-top:8px;">'
        + "".join(cells)
        + "</table>"
    )


def _html_fulfilment_line(order: Order) -> str:
    if _collecting(order):
        return "Collection"
    return f"Delivery to: {html_escape(order.delivery_address or '')}"


def _html_button(url: str, label: str) -> str:
    return f"""<table role="presentation" cellpadding="0" cellspacing="0" style="margin:20px 0 0 0;">
<tr>
<td style="border-radius:6px; background-color:{_C_FLAME};">
<a href="{html_escape(url)}" style="display:inline-block; padding:12px 24px; font-size:14px; font-weight:700; color:#ffffff; text-decoration:none; border-radius:6px;">{html_escape(label)}</a>
</td>
</tr>
</table>"""


def _html_tracking_button(order: Order) -> str:
    # Mirrors `_tracking_line`'s guard exactly: no route exists yet, so no
    # dead-end button ships (see "Known gaps to close later" in the runbook).
    if not settings.ORDER_TRACKING_BASE_URL:
        return ""
    base = settings.ORDER_TRACKING_BASE_URL.rstrip("/")
    return _html_button(f"{base}/{order.id}", "Track your order")


def _html_order_label(order: Order) -> str:
    return (
        f'<p style="margin:0 0 4px 0; font-size:13px; color:{_C_MUTED}; '
        f'text-transform:uppercase; letter-spacing:0.5px;">'
        f"Order {html_escape(order.order_number)}</p>"
    )


def _html_shell(
    *, badge_label: str, badge_color: str, headline_html: str, content_html: str, shop: str
) -> str:
    """The shared header/footer every event email renders inside.

    Deliberately no logo/photo -- no such asset exists for this client
    (checked 2026-07-30), and inline styles + a system font stack is what
    actually survives Gmail/Outlook/Apple Mail, unlike the site's real fonts.
    `headline_html` is pre-built by the caller (it mixes escaped dynamic
    values with literal markup like &mdash;), everything else here is static
    or already escaped by its builder.
    """
    return f"""<!doctype html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0; padding:0; background-color:{_C_PAGE_BG}; font-family:{_FONT_STACK};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{_C_PAGE_BG};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px; width:100%; background-color:#ffffff; border-radius:10px; overflow:hidden;">
<tr>
<td style="background-color:{_C_INK}; padding:28px 32px; text-align:center;">
<div style="font-family:{_FONT_STACK}; font-weight:800; font-size:26px; letter-spacing:1px; text-transform:uppercase;">
<span style="color:{_C_CREAM};">CHICK&nbsp;</span><span style="color:{_C_FLAME};">SHACK</span>
</div>
<div style="display:inline-block; margin-top:14px; padding:6px 16px; border-radius:999px; background-color:{badge_color}; color:#ffffff; font-weight:700; font-size:12px; letter-spacing:1px; text-transform:uppercase;">
{html_escape(badge_label)}
</div>
</td>
</tr>
<tr>
<td style="padding:28px 32px;">
<p style="margin:0 0 20px 0; font-size:17px; line-height:1.5; color:{_C_BODY_TEXT}; font-weight:600;">{headline_html}</p>
{content_html}
</td>
</tr>
<tr>
<td style="padding:18px 32px; background-color:{_C_PAGE_BG}; border-top:1px solid {_C_LINE};">
<p style="margin:0; font-size:12px; color:{_C_MUTED};">{html_escape(shop)}</p>
</td>
</tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def _html_received(
    order: Order, shop: str, currency: str, intends_card_payment: bool = False
) -> str:
    name = html_escape(order.customer_name or "there")
    content = (
        _html_order_label(order)
        + _html_items_table(order, currency)
        + _html_totals_table(order, currency)
        + f'<p style="margin:16px 0 0 0; font-size:13px; color:{_C_MUTED};">{_html_fulfilment_line(order)}</p>'
        + f'<p style="margin:4px 0 0 0; font-size:13px; color:{_C_MUTED};">{html_escape(_payment_status_text(order, intends_card_payment=intends_card_payment))}</p>'
        + _html_tracking_button(order)
        + f'<p style="margin:16px 0 0 0; font-size:14px; color:{_C_BODY_TEXT};">'
        f"We&rsquo;ll email you again as soon as the shop confirms your "
        f"{'collection' if _collecting(order) else 'delivery'} time.</p>"
    )
    return _html_shell(
        badge_label="Order received",
        badge_color=_C_EMBER,
        headline_html=f"Thanks, {name} &mdash; we&rsquo;ve got your order.",
        content_html=content,
        shop=shop,
    )


def _html_accepted(order: Order, shop: str, currency: str) -> str:
    name = html_escape(order.customer_name or "there")
    eta = order.eta_minutes
    when = f"in about {eta} minutes" if eta else "shortly"
    headline = (
        f"confirmed &mdash; ready for collection {when}."
        if _collecting(order)
        else f"confirmed &mdash; on its way to you {when}."
    )
    payment_line = (
        f'<strong style="color:{_C_BODY_TEXT};">Paid</strong>'
        if order.payment_status == "paid"
        else f"Due on {'collection' if _collecting(order) else 'delivery'}"
    )
    content = (
        _html_order_label(order)
        + _html_items_table(order, currency)
        + _html_totals_table(order, currency)
        + f'<p style="margin:16px 0 0 0; font-size:13px; color:{_C_MUTED};">{_html_fulfilment_line(order)}</p>'
        + f'<p style="margin:4px 0 0 0; font-size:13px; color:{_C_MUTED};">Payment: {payment_line}</p>'
        + _html_tracking_button(order)
    )
    return _html_shell(
        badge_label="Confirmed",
        badge_color=_C_FLAME,
        headline_html=f"Hi {name} &mdash; your order is {headline}",
        content_html=content,
        shop=shop,
    )


def _html_rejected(order: Order, shop: str, currency: str) -> str:
    name = html_escape(order.customer_name or "there")
    reason = html_escape(
        (order.rejection_reason or "").strip()
        or "The shop is unable to take this order right now."
    )
    content = (
        f'<p style="margin:0 0 16px 0; font-size:14px; color:{_C_BODY_TEXT};">{reason}</p>'
        f'<p style="margin:0 0 16px 0; font-size:14px; color:{_C_BODY_TEXT};">'
        "Nothing has been charged. If you&rsquo;d like to sort something out, "
        "please give us a call and we&rsquo;ll do our best.</p>"
        + _html_order_label(order)
        + f'<p style="margin:0; font-size:14px; color:{_C_BODY_TEXT};">'
        f"Total would have been {html_escape(_money(order.total, currency))}</p>"
    )
    return _html_shell(
        badge_label="Order not taken",
        badge_color=_C_FLAME_DARK,
        headline_html=f"Sorry {name} &mdash; we can&rsquo;t take this order.",
        content_html=content,
        shop=shop,
    )


def _html_on_the_way(order: Order, shop: str, currency: str) -> str:
    if _collecting(order):
        headline = "Your order is ready and waiting for you at the shop."
    else:
        headline = "Your order has left the shop and is on its way to you."
    payment_line = (
        "(paid)"
        if order.payment_status == "paid"
        else f"&mdash; payable on {'collection' if _collecting(order) else 'delivery'}"
    )
    content = (
        _html_order_label(order)
        + f'<p style="margin:0; font-size:15px; font-weight:700; color:{_C_BODY_TEXT};">'
        f"{html_escape(_money(order.total, currency))} {payment_line}</p>"
        + _html_tracking_button(order)
    )
    return _html_shell(
        badge_label="Ready for collection" if _collecting(order) else "On its way",
        badge_color=_C_EMBER,
        headline_html=headline,
        content_html=content,
        shop=shop,
    )


def _html_review(order: Order, shop: str, currency: str, review_url: str = "") -> str:
    """The "how did we do" email, sent 3 hours after the shop accepts.

    `review_url` is passed in, never imported from settings and never a
    literal: a Google review link belongs to one restaurant's Business
    Profile, and a second tenant must not be able to inherit Chick Shack's.
    `send_order_email` refuses the event outright when it is empty, so no
    dead button can ship -- the same guard `_html_tracking_button` applies to
    a tracking URL that does not exist yet.

    Deliberately NO food photography. `menu_items.image_url` is null on every
    live row, the photos exist only in the storefront and are matched by name
    there, and Malik's call (2026-08-10) was to ship the item as text now
    rather than block this on a database backfill.
    """
    name = html_escape(order.customer_name or "there")
    items = "".join(
        f'<p style="margin:0 0 2px 0; font-size:15px; color:{_C_BODY_TEXT};">'
        f"{item.quantity} &times; {html_escape(item.name)}</p>"
        for item in order.items
    )
    content = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse; background-color:{_C_CREAM}; border-radius:8px;">'
        f'<tr><td style="padding:14px 16px;">'
        + _html_order_label(order)
        + items
        + f'<p style="margin:6px 0 0 0; font-size:13px; color:{_C_MUTED};">'
        f"{html_escape(_money(order.total, currency))}</p>"
        "</td></tr></table>"
        f'<p style="margin:22px 0; font-size:15px; line-height:1.6; color:{_C_BODY_TEXT};">'
        "If you have a minute, a quick Google review would really help us. It tells us "
        "what we should improve, and it helps other people find us.</p>"
        + _html_button(review_url, "Leave a Google review")
        + f'<p style="margin:20px 0 0 0; font-size:13px; line-height:1.5; color:{_C_MUTED};">'
        "Thanks again. Your feedback genuinely helps a small shop.</p>"
    )
    return _html_shell(
        badge_label="Thank you",
        badge_color=_C_EMBER,
        headline_html=f"Hi {name}, thanks for ordering from us. We hope it was good.",
        content_html=content,
        shop=shop,
    )


_HTML_BUILDERS = {
    "received": _html_received,
    "accepted": _html_accepted,
    "rejected": _html_rejected,
    "on_the_way": _html_on_the_way,
    "review": _html_review,
}


# ---------------------------------------------------------------------------
# Bodies
# ---------------------------------------------------------------------------


def _body_received(
    order: Order, shop: str, currency: str, intends_card_payment: bool = False
) -> tuple[str, str]:
    subject = f"{shop}: we've got your order {order.order_number}"
    body = f"""Hi {order.customer_name or 'there'},

Thanks for your order. We've received it and the shop will confirm it shortly.

Order {order.order_number}

{_order_lines(order, currency)}

{_totals(order, currency)}

{'Collection' if _collecting(order) else 'Delivery to: ' + (order.delivery_address or '')}
{_payment_status_text(order, intends_card_payment=intends_card_payment)}
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
Payment: {'PAID' if order.payment_status == 'paid' else 'due on ' + ('collection' if _collecting(order) else 'delivery')}
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


def _body_review(
    order: Order, shop: str, currency: str, review_url: str = ""
) -> tuple[str, str]:
    subject = f"{shop}: how did we do with order {order.order_number}?"
    items = "\n".join(f"  {item.quantity} x {item.name}" for item in order.items)
    body = f"""Hi {order.customer_name or 'there'},

Thanks for ordering from us. We hope it was good.

Order {order.order_number}
{items}
{_money(order.total, currency)}

If you have a minute, a quick Google review would really help us. It tells us
what we should improve, and it helps other people find us.

Leave a review: {review_url}

Thanks again. Your feedback genuinely helps a small shop.

{shop}
"""
    return subject, body


_BUILDERS = {
    "received": _body_received,
    "accepted": _body_accepted,
    "rejected": _body_rejected,
    "on_the_way": _body_on_the_way,
    "review": _body_review,
}


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------


async def _send_via_brevo(to: str, subject: str, text: str, html: str) -> None:
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
        "textContent": text,
    }
    if html:
        payload["htmlContent"] = html
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


def _send_blocking(to: str, subject: str, text: str, html: str) -> None:
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
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")

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
    intends_card_payment: bool = False,
    review_url: str = "",
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

    # A review email with no link is a thank-you note with a dead button on it.
    # Refuse rather than send something broken -- and because the URL is the
    # feature's own switch, an unconfigured tenant lands here and is skipped.
    if event == "review" and not (review_url or "").strip():
        logger.info(
            "No google_review_url for this tenant; skipping review email for order %s",
            order.order_number,
        )
        return False

    # Only the "received" builders accept this kwarg -- it is the sole event
    # sent before any Stripe interaction has happened, see
    # `_payment_status_text`. Likewise `review_url` belongs to exactly one
    # event. An empty dict for every other event keeps their signatures
    # untouched.
    extra: dict[str, object] = {}
    if event == "received":
        extra = {"intends_card_payment": intends_card_payment}
    elif event == "review":
        extra = {"review_url": review_url.strip()}
    subject, text = _BUILDERS[event](order, shop_name, currency, **extra)
    html = _HTML_BUILDERS[event](order, shop_name, currency, **extra)

    try:
        if settings.BREVO_API_KEY:
            await _send_via_brevo(to, subject, text, html)
        else:
            await asyncio.to_thread(_send_blocking, to, subject, text, html)
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
