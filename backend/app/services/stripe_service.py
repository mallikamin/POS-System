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
    return stripe


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
        timeout=_STRIPE_TIMEOUT_SECONDS,
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
        raise StripeError(
            "STRIPE_SUCCESS_URL and STRIPE_CANCEL_URL must be set before "
            "offering card payment."
        )

    try:
        session = await asyncio.to_thread(
            _create_session_blocking, order, currency, shop_name, success, cancel
        )
    except StripeNotConfigured:
        raise
    except Exception as exc:
        logger.exception("Stripe checkout session failed for order %s", order.order_number)
        raise StripeError(str(exc)) from exc

    payment_intent = session.get("payment_intent") or ""
    if isinstance(payment_intent, dict):
        payment_intent = payment_intent.get("id", "")

    logger.info(
        "Created checkout session %s for order %s", session["id"], order.order_number
    )
    return session["url"], session["id"], str(payment_intent)


# ---------------------------------------------------------------------------
# Capture (accept) and cancel (reject)
# ---------------------------------------------------------------------------


def _capture_blocking(payment_intent_id: str, amount: int | None) -> Any:
    stripe = _client()
    params: dict[str, Any] = {"timeout": _STRIPE_TIMEOUT_SECONDS}
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

    status = intent.get("status", "")
    logger.info("Captured %s -> %s", payment_intent_id, status)
    return str(status)


def _cancel_blocking(payment_intent_id: str) -> Any:
    stripe = _client()
    return stripe.PaymentIntent.cancel(
        payment_intent_id, timeout=_STRIPE_TIMEOUT_SECONDS
    )


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

    logger.info("Cancelled authorisation %s -> %s", payment_intent_id, intent.get("status"))
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
        return stripe.Webhook.construct_event(
            payload, signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as exc:
        # Covers both a bad signature and a malformed body. Neither is worth
        # distinguishing to the caller -- both are "not from Stripe".
        raise StripeError(f"Webhook signature verification failed: {exc}") from exc


def order_id_from_event(event: dict[str, Any]) -> uuid.UUID | None:
    """Pull our order id out of an event's metadata, if it carries one."""
    obj = (event.get("data") or {}).get("object") or {}
    metadata = obj.get("metadata") or {}
    raw = metadata.get("order_id")
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except (ValueError, AttributeError):
        logger.warning("Webhook carried an unparseable order_id: %r", raw)
        return None


def authorization_timestamp() -> datetime:
    return datetime.now(timezone.utc)
