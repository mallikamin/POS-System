"""Card payment: authorise at checkout, capture on accept, cancel on reject.

The model these tests defend comes from the client's own answer (2026-07-29,
asked whether a website order is charged when placed or when accepted):
**"Once accepted."**

Everything here follows from that, and two asymmetries are the point:

    accept   a Stripe failure MUST block. If the money cannot be taken, the
             shop must not be told the order is accepted, because the next
             thing that happens is a ticket printing and food being cooked.

    reject   a Stripe failure MUST NOT block. Refusing to reject because
             Stripe is unreachable traps the shop with an order it has already
             declined, and an uncaptured authorisation expires by itself.

Get those two backwards and you either cook food you were not paid for, or you
strand the shop. Both are tested below.

Stripe itself is always mocked. These tests assert *our* decisions, never
Stripe's behaviour.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.tenant import Tenant
from app.models.user import User
from app.services import public_order_service, stripe_service
from app.services.public_order_service import PublicOrderError
from app.services.stripe_service import StripeError, StripeNotConfigured


def _card_order(tenant: Tenant, user: User, **overrides) -> Order:
    """An online order placed but not yet answered, with a card authorised."""
    fields = {
        "tenant_id": tenant.id,
        "order_number": "S250101-001",
        "order_type": "online",
        "status": "confirmed",
        "payment_status": "unpaid",
        "service_type": "delivery",
        "subtotal": 1000,
        "tax_amount": 0,
        "discount_amount": 0,
        "delivery_fee": 300,
        "total": 1300,
        "created_by": user.id,
        "accepted_at": None,
        "rejected_at": None,
        "customer_name": "Card Customer",
        "stripe_payment_intent_id": "pi_test_123",
        "stripe_checkout_session_id": "cs_test_123",
        "payment_authorized_at": datetime.now(timezone.utc),
        "payment_captured_at": None,
    }
    fields.update(overrides)
    return Order(**fields)


@pytest_asyncio.fixture
async def card_order(db: AsyncSession, tenant: Tenant, admin_user: User) -> Order:
    order = _card_order(tenant, admin_user)
    db.add(order)
    await db.flush()
    await db.commit()
    return order


@pytest_asyncio.fixture
async def cash_order(db: AsyncSession, tenant: Tenant, admin_user: User) -> Order:
    """The default: no card anywhere near it."""
    order = _card_order(
        tenant,
        admin_user,
        order_number="S250101-002",
        stripe_payment_intent_id=None,
        stripe_checkout_session_id=None,
        payment_authorized_at=None,
    )
    db.add(order)
    await db.flush()
    await db.commit()
    return order


# ---------------------------------------------------------------------------
# Accept -- the money moves here, or the order does not
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accepting_a_card_order_captures_it(
    db: AsyncSession, tenant: Tenant, admin_user: User, card_order: Order
) -> None:
    """Acceptance is the moment the money is taken. Not before."""
    with patch.object(
        stripe_service, "capture", new=AsyncMock(return_value="succeeded")
    ) as capture:
        order = await public_order_service.accept_order(
            db, tenant.id, card_order.id, admin_user.id, 30
        )

    capture.assert_awaited_once_with("pi_test_123")
    assert order.accepted_at is not None
    assert order.payment_captured_at is not None


@pytest.mark.asyncio
async def test_a_failed_capture_does_not_accept_the_order(
    db: AsyncSession, tenant: Tenant, admin_user: User, card_order: Order
) -> None:
    """The important one. No money, no acceptance, no kitchen ticket.

    If this ever inverts, the shop cooks food for a payment that never landed.
    """
    # Read the id up front. After the rollback/expunge below the fixture
    # instance is detached, and touching any attribute on it then raises
    # DetachedInstanceError rather than returning the value.
    order_id = card_order.id

    with patch.object(
        stripe_service, "capture", new=AsyncMock(side_effect=StripeError("card declined"))
    ):
        with pytest.raises(PublicOrderError, match="not been accepted"):
            await public_order_service.accept_order(
                db, tenant.id, card_order.id, admin_user.id, 30
            )

    # Re-read from the database rather than trusting the in-memory object.
    # `expunge_all` first: a `get` after a rollback can hand back the expired
    # instance from the identity map, and touching an attribute on that then
    # tries a synchronous lazy load (MissingGreenlet).
    await db.rollback()
    db.expunge_all()
    refreshed = (
        await db.execute(select(Order).where(Order.id == order_id))
    ).scalar_one()

    assert refreshed.accepted_at is None, "a declined card must not accept the order"
    assert refreshed.payment_captured_at is None
    assert refreshed.status == "confirmed", "it must not have reached the kitchen"


@pytest.mark.asyncio
async def test_a_capture_that_does_not_succeed_is_treated_as_failure(
    db: AsyncSession, tenant: Tenant, admin_user: User, card_order: Order
) -> None:
    """Stripe returning without raising is not the same as being paid.

    `requires_action` is a real status: the call succeeded, the money did not
    arrive. Reading "no exception" as "paid" is the classic way to give away
    food.
    """
    with patch.object(
        stripe_service, "capture", new=AsyncMock(return_value="requires_action")
    ):
        with pytest.raises(PublicOrderError, match="did not complete"):
            await public_order_service.accept_order(
                db, tenant.id, card_order.id, admin_user.id, 30
            )


@pytest.mark.asyncio
async def test_a_cash_order_accepts_without_touching_stripe(
    db: AsyncSession, tenant: Tenant, admin_user: User, cash_order: Order
) -> None:
    """Cash on handover is still the default and must be entirely unaffected."""
    with patch.object(stripe_service, "capture", new=AsyncMock()) as capture:
        order = await public_order_service.accept_order(
            db, tenant.id, cash_order.id, admin_user.id, 30
        )

    capture.assert_not_awaited()
    assert order.accepted_at is not None
    assert order.payment_captured_at is None


@pytest.mark.asyncio
async def test_an_already_captured_order_is_not_captured_twice(
    db: AsyncSession, tenant: Tenant, admin_user: User
) -> None:
    """Re-accepting must never charge a customer a second time."""
    order = _card_order(
        tenant,
        admin_user,
        order_number="S250101-003",
        payment_captured_at=datetime.now(timezone.utc),
    )
    db.add(order)
    await db.flush()
    await db.commit()

    with patch.object(stripe_service, "capture", new=AsyncMock()) as capture:
        await public_order_service.accept_order(
            db, tenant.id, order.id, admin_user.id, 30
        )

    capture.assert_not_awaited()


# ---------------------------------------------------------------------------
# Reject -- release the hold, and never get stuck
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rejecting_a_card_order_cancels_the_authorisation(
    db: AsyncSession, tenant: Tenant, admin_user: User, card_order: Order
) -> None:
    with patch.object(
        stripe_service, "cancel", new=AsyncMock(return_value=True)
    ) as cancel:
        order = await public_order_service.reject_order(
            db, tenant.id, card_order.id, admin_user.id, "Too busy"
        )

    cancel.assert_awaited_once_with("pi_test_123")
    assert order.rejected_at is not None
    assert order.status == "voided"


@pytest.mark.asyncio
async def test_rejection_still_succeeds_when_stripe_is_down(
    db: AsyncSession, tenant: Tenant, admin_user: User, card_order: Order
) -> None:
    """The mirror image of the capture test, and deliberately the opposite rule.

    The customer was never charged either way -- an uncaptured hold expires on
    its own. Trapping the shop with an order it has declined is the worse
    outcome, so Stripe being unreachable must not block the rejection.
    """
    with patch.object(stripe_service, "cancel", new=AsyncMock(return_value=False)):
        order = await public_order_service.reject_order(
            db, tenant.id, card_order.id, admin_user.id, "Kitchen closed"
        )

    assert order.rejected_at is not None
    assert order.status == "voided"


@pytest.mark.asyncio
async def test_a_captured_order_is_not_cancelled_on_reject(
    db: AsyncSession, tenant: Tenant, admin_user: User
) -> None:
    """Cancelling only applies to money still merely held.

    Once captured there is nothing to cancel, and calling cancel would be a
    silent no-op that hides a real problem: an order that took money and was
    then rejected needs a human, not an API call.
    """
    order = _card_order(
        tenant,
        admin_user,
        order_number="S250101-004",
        payment_captured_at=datetime.now(timezone.utc),
    )
    db.add(order)
    await db.flush()
    await db.commit()

    with patch.object(stripe_service, "cancel", new=AsyncMock()) as cancel:
        await public_order_service.reject_order(
            db, tenant.id, order.id, admin_user.id, "Sorry"
        )

    cancel.assert_not_awaited()


# ---------------------------------------------------------------------------
# The basket Stripe is asked to charge
# ---------------------------------------------------------------------------


def test_line_items_fall_back_to_one_line_when_the_breakdown_disagrees(
    tenant: Tenant, admin_user: User
) -> None:
    """The customer must be charged exactly what our confirmation said.

    If the itemised lines do not sum to the order total -- a discount, an
    unforeseen rounding path -- we charge the total as a single line rather
    than ship a basket that bills a different number.
    """
    order = _card_order(tenant, admin_user, total=9999)
    order.items = []

    lines = stripe_service._line_items(order, "GBP")

    charged = sum(line["quantity"] * line["price_data"]["unit_amount"] for line in lines)
    assert charged == 9999


def test_line_items_use_minor_units_with_no_float_arithmetic(
    tenant: Tenant, admin_user: User
) -> None:
    """£13.00 must reach Stripe as 1300, never as 13.0."""
    order = _card_order(tenant, admin_user)
    order.items = []

    lines = stripe_service._line_items(order, "GBP")

    for line in lines:
        amount = line["price_data"]["unit_amount"]
        assert isinstance(amount, int), f"{amount!r} is not an integer minor-unit amount"


# ---------------------------------------------------------------------------
# Webhook -- an unauthenticated POST claiming orders are paid
# ---------------------------------------------------------------------------


def test_webhook_is_refused_when_no_signing_secret_is_configured() -> None:
    """Fail closed. An unverifiable webhook is worse than no webhook.

    Without a secret this endpoint would accept anyone's POST saying an order
    had been paid.
    """
    with patch.object(stripe_service.settings, "STRIPE_WEBHOOK_SECRET", ""):
        with pytest.raises(StripeError, match="refusing"):
            stripe_service.verify_webhook(b"{}", "sig")


class _StripeLike:
    """Stands in for a real `StripeObject`.

    Subscriptable, but **any** attribute access raises `AttributeError` -- which
    is what the real class does for `.get`, as its own `__getattr__` tries to
    resolve `get` as a *field* of the response and fails.

    Deliberately not a `dict` subclass: `dict` supplies a working `.get()`, so a
    dict-based fake silently passes and reproduces nothing. That is the whole
    trap being pinned here -- mocked tests hand plain dicts to code that will
    receive StripeObjects in production.
    """

    def __init__(self, data: dict) -> None:
        object.__setattr__(self, "_data", data)

    def __getitem__(self, key: str):  # noqa: ANN204 - mirrors StripeObject
        return object.__getattribute__(self, "_data")[key]

    def __getattr__(self, name: str):  # noqa: ANN204 - mirrors StripeObject
        raise AttributeError(name)


def test_reading_a_stripe_response_never_uses_dot_get() -> None:
    """Regression: `StripeObject` has no `.get()`.

    Found by driving the real sandbox after every mocked test passed. Any code
    that calls `.get()` on a Stripe response raises `AttributeError: get` in
    production while looking perfectly correct in the suite.
    """
    obj = _StripeLike({"status": "requires_capture"})

    with pytest.raises(AttributeError):
        obj.get("status")  # the bug, pinned so nobody reintroduces it

    assert stripe_service.field(obj, "status") == "requires_capture"
    assert stripe_service.field(obj, "absent") is None
    assert stripe_service.field(obj, "absent", "fallback") == "fallback"
    assert stripe_service.field(None, "status") is None


def test_order_id_survives_a_real_shaped_stripe_event() -> None:
    """The webhook path specifically, with StripeObjects rather than dicts."""
    import uuid as _uuid

    order_id = _uuid.uuid4()
    event = _StripeLike(
        {
            "type": "payment_intent.succeeded",
            "data": _StripeLike(
                {"object": _StripeLike({"metadata": _StripeLike({"order_id": str(order_id)})})}
            ),
        }
    )

    assert stripe_service.order_id_from_event(event) == order_id
    assert stripe_service.field(event, "type") == "payment_intent.succeeded"


def test_order_id_is_read_from_event_metadata() -> None:
    import uuid as _uuid

    order_id = _uuid.uuid4()
    event = {"data": {"object": {"metadata": {"order_id": str(order_id)}}}}

    assert stripe_service.order_id_from_event(event) == order_id


@pytest.mark.parametrize(
    "event",
    [
        {},
        {"data": {}},
        {"data": {"object": {}}},
        {"data": {"object": {"metadata": {}}}},
        {"data": {"object": {"metadata": {"order_id": "not-a-uuid"}}}},
    ],
)
def test_a_webhook_without_a_usable_order_id_is_ignored_not_crashed(event: dict) -> None:
    """Stripe sends events we never asked for. None of them may 500.

    A non-2xx makes Stripe retry the same event indefinitely.
    """
    assert stripe_service.order_id_from_event(event) is None


# ---------------------------------------------------------------------------
# Not configured -- card is simply not on offer
# ---------------------------------------------------------------------------


def test_nothing_stripe_works_without_a_secret_key() -> None:
    """The whole feature is opt-in, exactly like email.

    On a box with no key the shop keeps taking cash on handover and nothing
    card-related is offered -- which is the state of production until the live
    keys are deployed.
    """
    with patch.object(stripe_service.settings, "STRIPE_SECRET_KEY", ""):
        with pytest.raises(StripeNotConfigured):
            stripe_service._client()
