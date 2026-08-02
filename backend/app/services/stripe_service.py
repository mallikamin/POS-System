"""Card payment for online orders, via Stripe Checkout with manual capture.

The whole design follows one decision the client made himself (2026-07-29, asked
directly whether a website order should be charged when placed or when
accepted): **"Once accepted."**

That is not a preference, it is the correct model for a shop that manually
accepts every order and takes pre-orders around the clock. A customer can order
at 02:00 for a shop that opens at 16:00. If we charged on placement, a rejected
pre-order would owe a refund, and the rejection screen's "nothing has been
charged" would be a lie. So:

    checkout   PaymentIntent created with capture_method="manual".
               The money is AUTHORISED -- held, not taken.
    accept     the intent is CAPTURED. The only moment money moves.
    reject     the intent is CANCELLED. Nothing was ever taken.

There is therefore **no refund path in this module, deliberately.** If you find
yourself adding one, check first whether you have accidentally moved the charge
back to placement.

⚠️ **An authorisation expires.** Roughly 5 days on Visa and 7 on
Mastercard/Amex for card-not-present. A pre-order held longer than that will
fail at capture. `payment_authorized_at` exists so that is visible in advance
rather than discovered on the Accept tap.

Failure policy differs from email on purpose. An email failure is swallowed,
because the order is the product and the email is a courtesy. **A capture
failure is not swallowed** -- if the money cannot be taken, the shop must not
be told the order is accepted and must not start cooking. Money failures
surface; courtesy failures do not.

The SDK is synchronous, so every call runs in a worker thread rather than
blocking the event loop, exactly as `email_service` does.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.models.order import Order

logger = logging.getLogger(__name__)

# Stripe recommends short client-side timeouts; a checkout that hangs is worse
# than one that fails, because the customer is sitting in front of it.
_STRIPE_TIMEOUT_SECONDS = 20


def field(obj: Any, key: str, default: Any = None) -> Any:
    """Read a key from a Stripe response, or a plain dict, safely.

    ⚠️ **`StripeObject` does not have `.get()`.** It subclasses dict but
    overrides attribute access, so `response.get("status")` raises
    `AttributeError: get` rather than returning anything. Subscripting works and
    raises `KeyError` when the key is absent -- and absent keys are normal,
    because Stripe omits fields rather than nulling them.

    This was caught by driving the real sandbox; every mocked test passed
    happily with plain dicts, which is precisely the blind spot mocks create.
    """
    try:
        return obj[key]
    except (KeyError, TypeError, IndexError):
        return default


class StripeError(Exception):
    """Anything that should stop the caller. Money problems are not swallowed."""


class StripeNotConfigured(StripeError):
    """No secret key. Card payment is simply not offered."""


def _client() -> Any:
    """Return the configured stripe module.

    Imported lazily so the application starts, and the whole non-card system
    keeps working, on a box where the package is not installed yet -- which is
    the state of every deploy before this feature ships.
    """
    if not settings.stripe_configured:
        raise StripeNotConfigured("Stripe is not configured.")
    try:
        import stripe
    except ModuleNotFoundError as exc:  # pragma: no cover - deployment state
        raise StripeNotConfigured(
            "The stripe package is not installed on this backend."
        ) from exc

    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.max_network_retries = 2

    # ⚠️ `timeout=` is NOT a per-call argument. Passing it to `.create()` sends
    # it to Stripe as a request FIELD, and the API rejects the whole call with
    # "Received unknown parameter: timeout" -- a 502 at the moment a customer
    # is trying to pay. It was written that way here and every mocked test
    # passed, because a mock accepts any keyword you hand it. Found by making
    # one real call.
    #
    # The timeout belongs on the HTTP client, set once. Assigned only if unset,
    # so this does not build a fresh connection pool on every call.
    if stripe.default_http_client is None:
        stripe.default_http_client = stripe.RequestsClient(
            timeout=_STRIPE_TIMEOUT_SECONDS
        )

    return stripe


def _with_order(url: str, order: Order, *, paid: bool) -> str:
    """Append the order id to a return URL, preserving any query it already has.

    `paid` reflects which of the two URLs Stripe used, not whether money was
    actually taken -- the customer landing on the success URL means they
    finished the Checkout page, and the authorisation still has to be captured
    when the shop accepts. The storefront uses it to decide which screen to
    show; the database is the authority on payment.
    """
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}order={order.id}&paid={'1' if paid else '0'}"


# ---------------------------------------------------------------------------
# Building the basket Stripe will show
# ---------------------------------------------------------------------------


def _line_items(order: Order, currency: str) -> list[dict[str, Any]]:
    """Itemise the order for the Checkout page.

    Two things matter more than presentation here.

    First, **the customer must be charged exactly what our own confirmation
    said.** So the itemised lines are built, summed, and checked against
    `order.total`. If they disagree for any reason -- a discount, a rounding
    path nobody thought about, a future field -- we do not ship a basket that
    charges a different number. We fall back to a single line for the exact
    order total, which is always right even when the breakdown is not.

    Second, Stripe wants minor units, which is what the order already stores.
    No float conversion happens anywhere in this file.
    """
    lines: list[dict[str, Any]] = []

    for item in order.items:
        modifiers = ", ".join(m.name for m in item.modifiers)
        name = f"{item.name} ({modifiers})" if modifiers else item.name
        description = (item.notes or "").strip() or None
        lines.append(
            {
                "quantity": item.quantity,
                "price_data": {
                    "currency": currency.lower(),
                    "unit_amount": item.total // item.quantity
                    if item.quantity
                    else item.total,
                    "product_data": (
                        {"name": name[:250], "description": description[:250]}
                        if description
                        else {"name": name[:250]}
                    ),
                },
            }
        )

    if order.service_fee:
        lines.append(
            {
                "quantity": 1,
                "price_data": {
                    "currency": currency.lower(),
                    "unit_amount": order.service_fee,
                    "product_data": {"name": "Service Fee"},
                },
            }
        )

    if order.delivery_fee:
        lines.append(
            {
                "quantity": 1,
                "price_data": {
                    "currency": currency.lower(),
                    "unit_amount": order.delivery_fee,
                    "product_data": {"name": "Delivery"},
                },
            }
        )

    itemised = sum(line["quantity"] * line["price_data"]["unit_amount"] for line in lines)

    if itemised != order.total:
        # Not an error worth failing an order over, but absolutely worth saying
        # out loud -- it means the breakdown and the total have diverged.
        logger.warning(
            "Order %s itemised to %s but totals %s; charging the total as one line",
            order.order_number,
            itemised,
            order.total,
        )
        return [
            {
                "quantity": 1,
                "price_data": {
                    "currency": currency.lower(),
                    "unit_amount": order.total,
                    "product_data": {"name": f"Order {order.order_number}"},
                },
            }
        ]

    return lines


# ---------------------------------------------------------------------------
# Authorise
# ---------------------------------------------------------------------------


def _create_session_blocking(
    order: Order,
    currency: str,
    shop_name: str,
    success_url: str,
    cancel_url: str,
) -> Any:
    stripe = _client()
    return stripe.checkout.Session.create(
        mode="payment",
        line_items=_line_items(order, currency),
        # The entire model in one parameter: hold the money, do not take it.
        payment_intent_data={
            "capture_method": "manual",
            "description": f"{shop_name} order {order.order_number}",
            # Carried on the PaymentIntent so a webhook or a human in the Stripe
            # dashboard can get back to our order without a lookup table.
            "metadata": {
                "order_id": str(order.id),
                "order_number": order.order_number,
                "tenant_id": str(order.tenant_id),
            },
        },
        metadata={
            "order_id": str(order.id),
            "order_number": order.order_number,
            "tenant_id": str(order.tenant_id),
        },
        customer_email=(order.customer_email or None),
        success_url=success_url,
        cancel_url=cancel_url,
        # Stripe deduplicates on this, so a double-tap or a retried request
        # returns the same session instead of authorising the customer twice.
        idempotency_key=f"checkout:{order.id}",
    )


async def create_checkout_session(
    order: Order,
    *,
    currency: str = "GBP",
    shop_name: str = "Chick Shack",
    success_url: str | None = None,
    cancel_url: str | None = None,
) -> tuple[str, str, str]:
    """Authorise the order. Returns (checkout_url, session_id, payment_intent_id).

    Raises rather than returning a sentinel: a customer who was told they are
    being taken to a payment page must not silently end up somewhere else.
    """
    success = success_url or settings.STRIPE_SUCCESS_URL
    cancel = cancel_url or settings.STRIPE_CANCEL_URL
    if not success or not cancel:
        # StripeNotConfigured, not StripeError, so the route answers 503 "card
        # payment is not available" instead of 502 Bad Gateway. Missing config
        # is not a broken server, and telling a customer our server is broken
        # when we simply have not finished setting up reads far worse than the
        # truth -- and sends whoever debugs it looking in the wrong place.
        raise StripeNotConfigured(
            "STRIPE_SUCCESS_URL and STRIPE_CANCEL_URL must be set before "
            "offering card payment."
        )

    # The account settles in one currency. A session in any other is rejected by
    # Stripe on the payment page, in front of a customer who has already
    # committed to the order. Fail here, internally, where it is our problem.
    expected = (settings.STRIPE_ACCOUNT_CURRENCY or "").strip().lower()
    if expected and currency.strip().lower() != expected:
        logger.error(
            "Tenant currency %s does not match the Stripe account currency %s; "
            "refusing to create a checkout session for order %s",
            currency,
            expected.upper(),
            order.order_number,
        )
        raise StripeNotConfigured(
            f"This shop is configured in {currency.upper()} but the Stripe "
            f"account settles in {expected.upper()}. Card payment is not "
            "available until they match."
        )

    # Stripe sends the customer back to a bare URL, and the storefront is a
    # single page with its state in memory -- so without this it would reload to
    # an empty menu, having just taken their money. The order id travels in the
    # query string and is what the page uses to put the confirmation screen back.
    success = _with_order(success, order, paid=True)
    cancel = _with_order(cancel, order, paid=False)

    try:
        session = await asyncio.to_thread(
            _create_session_blocking, order, currency, shop_name, success, cancel
        )
    except StripeNotConfigured:
        raise
    except Exception as exc:
        logger.exception("Stripe checkout session failed for order %s", order.order_number)
        raise StripeError(str(exc)) from exc

    # ⚠️ Usually `None` here, confirmed against the real sandbox: Stripe does
    # not create the PaymentIntent when the session itself is created, only
    # once the customer actually submits payment on the Checkout page. This
    # write is opportunistic only and must not be relied on -- a comment here
    # once claimed it was always an id string at this point, and that claim
    # was wrong, which is exactly how `orders.stripe_payment_intent_id` ended
    # up permanently `None` for a real, successfully-authorised order (2026-07-31).
    # `resolve_payment_intent_id` below is the reliable path, used right
    # before capture.
    payment_intent = field(session, "payment_intent") or ""
    if not isinstance(payment_intent, str):
        payment_intent = field(payment_intent, "id", "")

    logger.info(
        "Created checkout session %s for order %s", session["id"], order.order_number
    )
    return session["url"], session["id"], str(payment_intent)


def _retrieve_session_blocking(checkout_session_id: str) -> Any:
    stripe = _client()
    return stripe.checkout.Session.retrieve(checkout_session_id)


async def resolve_payment_intent_id(checkout_session_id: str) -> str | None:
    """Look up the PaymentIntent Stripe actually attached to a Checkout Session.

    The reliable way to find it -- `create_checkout_session` returns one only
    opportunistically, because Stripe has usually not created it yet at that
    point. Call this once the session has had a chance to complete (e.g.
    right before capturing on Accept) rather than trusting whatever was
    captured at session-creation time.

    Returns `None` when the customer never actually completed the Checkout
    page (session still `open`/`expired`) -- an ordinary abandoned card
    checkout, not an error. The caller should treat that exactly like a cash
    order: nothing to capture.
    """
    try:
        session = await asyncio.to_thread(_retrieve_session_blocking, checkout_session_id)
    except StripeNotConfigured:
        raise
    except Exception as exc:
        logger.exception("Could not retrieve Checkout Session %s", checkout_session_id)
        raise StripeError(str(exc)) from exc

    payment_intent = field(session, "payment_intent") or ""
    if not isinstance(payment_intent, str):
        payment_intent = field(payment_intent, "id", "")
    return payment_intent or None


# ---------------------------------------------------------------------------
# Capture (accept) and cancel (reject)
# ---------------------------------------------------------------------------


def _capture_blocking(payment_intent_id: str, amount: int | None) -> Any:
    stripe = _client()
    params: dict[str, Any] = {}
    if amount is not None:
        # A partial capture automatically releases the remainder, so this is
        # also how an order reduced after the fact would settle honestly.
        params["amount_to_capture"] = amount
    return stripe.PaymentIntent.capture(payment_intent_id, **params)


async def capture(payment_intent_id: str, amount: int | None = None) -> str:
    """Take the money that was held. Returns the resulting PaymentIntent status.

    **Failures propagate.** If the card cannot be charged, the shop must not be
    told the order is accepted, because the next thing that happens is a ticket
    printing in the kitchen.

    Treated as success when the intent is already `succeeded` -- a retried
    Accept tap must not read as a payment failure.
    """
    try:
        intent = await asyncio.to_thread(_capture_blocking, payment_intent_id, amount)
    except StripeNotConfigured:
        raise
    except Exception as exc:
        message = str(exc)
        if "already been captured" in message or "already succeeded" in message:
            logger.info("PaymentIntent %s was already captured", payment_intent_id)
            return "succeeded"
        logger.exception("Capture failed for %s", payment_intent_id)
        raise StripeError(message) from exc

    status = field(intent, "status", "")
    logger.info("Captured %s -> %s", payment_intent_id, status)
    return str(status)


def _retrieve_blocking(payment_intent_id: str) -> Any:
    stripe = _client()
    return stripe.PaymentIntent.retrieve(payment_intent_id)


async def capture_for_order(payment_intent_id: str, order_total: int) -> str:
    """Capture what the order is worth **now**, never what was authorised then.

    `capture()` with no amount takes the full authorised amount. That is wrong
    the moment an order changes between authorisation and acceptance: the shop
    strikes an item the kitchen has run out of, taps Accept, and the customer is
    charged the original, higher figure. Nothing in the system would notice --
    Stripe did exactly as it was told.

    So the amount is read back from Stripe and bounded:

    * already `succeeded` -- a retried Accept tap. Not an error, and emphatically
      not a second charge.
    * nothing capturable -- the hold expired, was cancelled, or never completed.
      Raise, so the shop is told before it starts cooking.
    * total **above** what is held -- refuse. Capturing the lesser amount would
      quietly undercharge, and how to recover that is a human's decision, not a
      default this function should pick.
    * otherwise capture the order total exactly. Stripe releases the remainder
      of a partial capture by itself.
    """
    try:
        intent = await asyncio.to_thread(_retrieve_blocking, payment_intent_id)
    except StripeNotConfigured:
        raise
    except Exception as exc:
        logger.exception("Could not read PaymentIntent %s", payment_intent_id)
        raise StripeError(str(exc)) from exc

    status = str(field(intent, "status", ""))
    if status == "succeeded":
        logger.info("PaymentIntent %s was already captured", payment_intent_id)
        return "succeeded"

    capturable = int(field(intent, "amount_capturable", 0) or 0)
    if capturable <= 0:
        raise StripeError(
            f"No money is being held for this order (the authorisation is "
            f"'{status}'). It may have expired -- an authorisation lasts about "
            "5 days. Take payment another way."
        )

    if order_total > capturable:
        raise StripeError(
            f"The order is now worth more than was authorised "
            f"({order_total} vs {capturable}). Capturing would undercharge, so "
            "nothing has been taken -- collect the difference or re-authorise."
        )

    return await capture(payment_intent_id, amount=order_total)


async def retrieve_payment_intent(payment_intent_id: str) -> dict[str, Any]:
    """Read-only lookup for reconciliation (OI-58d) -- never mutates Stripe state.

    Unlike `capture_for_order`, this is not on any money-moving path, so a
    failure here should be reported to the caller as a diagnosable error
    rather than treated as an outage to work around.
    """
    try:
        intent = await asyncio.to_thread(_retrieve_blocking, payment_intent_id)
    except StripeNotConfigured:
        raise
    except Exception as exc:
        logger.exception("Could not read PaymentIntent %s", payment_intent_id)
        raise StripeError(str(exc)) from exc

    return {
        "status": str(field(intent, "status", "")),
        "amount_received": int(field(intent, "amount_received", 0) or 0),
        "amount_capturable": int(field(intent, "amount_capturable", 0) or 0),
    }


def _cancel_blocking(payment_intent_id: str) -> Any:
    stripe = _client()
    return stripe.PaymentIntent.cancel(payment_intent_id)


async def cancel(payment_intent_id: str) -> bool:
    """Release a hold on rejection. Returns True if the money is not ours.

    **Failures are swallowed here, unlike capture, and the asymmetry is
    deliberate.** Refusing to reject an order because Stripe is unreachable
    would trap the shop with an order it has already declined, and the customer
    was never charged either way -- an uncaptured authorisation expires on its
    own within days. Getting stuck is the worse outcome, so we log loudly and
    let the rejection stand.
    """
    try:
        intent = await asyncio.to_thread(_cancel_blocking, payment_intent_id)
    except StripeNotConfigured:
        logger.warning(
            "Stripe not configured; cannot cancel %s. The hold will expire.",
            payment_intent_id,
        )
        return False
    except Exception:
        logger.exception(
            "Could not cancel authorisation %s. It expires on its own, but check "
            "Stripe -- the customer may see a pending amount until it does.",
            payment_intent_id,
        )
        return False

    logger.info(
        "Cancelled authorisation %s -> %s", payment_intent_id, field(intent, "status")
    )
    return True


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


def verify_webhook(payload: bytes, signature: str) -> dict[str, Any]:
    """Verify a webhook came from Stripe and return the event.

    Without this the endpoint is an unauthenticated POST that claims orders
    have been paid. Verification is mandatory: if no signing secret is
    configured, the endpoint refuses everything rather than trusting anything.
    """
    if not settings.stripe_webhook_configured:
        raise StripeError("STRIPE_WEBHOOK_SECRET is not set; refusing the webhook.")

    stripe = _client()
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as exc:
        # Covers both a bad signature and a malformed body. Neither is worth
        # distinguishing to the caller -- both are "not from Stripe".
        raise StripeError(f"Webhook signature verification failed: {exc}") from exc

    # A valid signature proves the event came from Stripe. It does not prove it
    # came from the right *mode*. Test and live are separate worlds with
    # separate keys, and a test event driving a production order -- marking it
    # paid when no money exists -- is the kind of thing nobody finds until the
    # books do not balance. The endpoint secret differs per mode so this is
    # unlikely, but the assertion costs one comparison and removes the question.
    if bool(field(event, "livemode", False)) is not is_live_mode():
        raise StripeError(
            "Webhook mode mismatch: this event's livemode does not match the "
            "configured Stripe key. Refusing it."
        )

    return event


def is_live_mode() -> bool:
    """True when configured with a live key rather than a test one.

    `rk_live_` is included because a **restricted** key is a perfectly ordinary
    thing to deploy -- arguably the better thing to deploy -- and matching only
    `sk_live_` would classify a live restricted key as test mode, then reject
    every genuine live event as a mode mismatch.
    """
    return settings.STRIPE_SECRET_KEY.startswith(("sk_live_", "rk_live_"))


def _metadata_uuid(event: dict[str, Any], key: str) -> uuid.UUID | None:
    obj = field(field(event, "data", {}), "object", {}) or {}
    metadata = field(obj, "metadata", {}) or {}
    raw = field(metadata, key)
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except (ValueError, AttributeError):
        logger.warning("Webhook carried an unparseable %s: %r", key, raw)
        return None


def order_id_from_event(event: dict[str, Any]) -> uuid.UUID | None:
    """Pull our order id out of an event's metadata, if it carries one."""
    return _metadata_uuid(event, "order_id")


def tenant_id_from_event(event: dict[str, Any]) -> uuid.UUID | None:
    """Pull the tenant id out of an event's metadata, if it carries one.

    Every other route in `public.py` is scrupulously tenant-scoped; the webhook
    looked an order up by id alone. The metadata already carries the tenant, so
    checking it costs nothing and keeps the one unauthenticated write path in
    the system to the same standard as the rest.
    """
    return _metadata_uuid(event, "tenant_id")


def authorization_timestamp() -> datetime:
    return datetime.now(timezone.utc)
