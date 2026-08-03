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

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.tenant import Tenant
from app.models.user import User
from app.services import audit_service, public_order_service, stripe_service
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
async def card_order_pending_intent(
    db: AsyncSession, tenant: Tenant, admin_user: User
) -> Order:
    """A real card order whose Checkout Session was created but whose
    PaymentIntent id never landed on the order -- the exact shape of the
    260731-001 incident (2026-07-31): `stripe_checkout_session_id` set,
    `stripe_payment_intent_id` and `payment_authorized_at` both still `None`,
    because Stripe had not created the PaymentIntent yet at the moment the
    session was created and nothing ever went back to resolve it.
    """
    order = _card_order(
        tenant,
        admin_user,
        order_number="S250101-004",
        stripe_payment_intent_id=None,
        payment_authorized_at=None,
    )
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
        stripe_service, "capture_for_order", new=AsyncMock(return_value="succeeded")
    ) as capture:
        order = await public_order_service.accept_order(
            db, tenant.id, card_order.id, admin_user.id, 30
        )

    # The order total is passed, not left to default to the authorised amount.
    capture.assert_awaited_once_with("pi_test_123", 1300)
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
        stripe_service,
        "capture_for_order",
        new=AsyncMock(side_effect=StripeError("card declined")),
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
        stripe_service, "capture_for_order", new=AsyncMock(return_value="requires_action")
    ):
        with pytest.raises(PublicOrderError, match="did not complete"):
            await public_order_service.accept_order(
                db, tenant.id, card_order.id, admin_user.id, 30
            )


@pytest.mark.asyncio
async def test_accepting_a_card_order_resolves_a_missing_intent_id_and_captures_it(
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    card_order_pending_intent: Order,
) -> None:
    """The exact real-world failure, order 260731-001 (2026-07-31): a checkout
    session that completed on Stripe's side, but whose PaymentIntent id never
    landed on the order. Accept must resolve it from Stripe and still
    capture -- not silently skip, which is what shipped that day: the order
    reached the kitchen as `in_kitchen` with `payment_status` still `unpaid`
    while Stripe was sitting on a fully authorised, capturable £12.99.
    """
    with (
        patch.object(
            stripe_service,
            "authorization_for_session",
            new=AsyncMock(return_value=("pi_resolved_456", True)),
        ) as resolve,
        patch.object(
            stripe_service, "capture_for_order", new=AsyncMock(return_value="succeeded")
        ) as capture,
    ):
        order = await public_order_service.accept_order(
            db, tenant.id, card_order_pending_intent.id, admin_user.id, 30
        )

    resolve.assert_awaited_once_with("cs_test_123")
    capture.assert_awaited_once_with("pi_resolved_456", 1300)
    assert order.stripe_payment_intent_id == "pi_resolved_456"
    assert order.payment_captured_at is not None
    assert order.payment_authorized_at is not None
    assert order.accepted_at is not None


@pytest.mark.asyncio
async def test_an_abandoned_card_checkout_is_refused_not_accepted(
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    card_order_pending_intent: Order,
) -> None:
    """OI-65 -- THE INVARIANT. Inverts this test's own previous expectation.

    It used to assert that an abandoned card checkout "falls through and accepts
    exactly like an ordinary unpaid order". That is precisely the hole: it makes
    Accept willing to commit the kitchen against money nobody has confirmed, and
    it is what the tablet's ungated "All" tab reached on 2026-08-03 (order
    260803-003, accepted 2m34s in, authorised 3m36s later).

    A card order is not acceptable until Stripe confirms the money -- by ANY
    route, including a direct API call that never went near the queue filter.
    """
    with (
        patch.object(
            stripe_service,
            "authorization_for_session",
            new=AsyncMock(return_value=(None, False)),
        ),
        patch.object(stripe_service, "capture_for_order", new=AsyncMock()) as capture,
    ):
        with pytest.raises(
            public_order_service.CardPaymentNotConfirmed, match="has not gone through"
        ):
            await public_order_service.accept_order(
                db, tenant.id, card_order_pending_intent.id, admin_user.id, 30
            )

    capture.assert_not_awaited()
    await db.refresh(card_order_pending_intent)
    assert card_order_pending_intent.accepted_at is None
    assert card_order_pending_intent.status == "confirmed"


@pytest.mark.asyncio
async def test_an_intent_that_exists_but_is_not_authorised_is_refused(
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    card_order_pending_intent: Order,
) -> None:
    """A PaymentIntent existing proves the customer STARTED paying, never that
    they finished -- they may be sitting on the 3-D Secure step, or Stripe may
    still be `processing`. Publishing (or accepting) on "an intent exists" would
    reintroduce the whole failure mode one step later, which is why the gate
    asks for the authorisation status and not just the id."""
    with (
        patch.object(
            stripe_service,
            "authorization_for_session",
            new=AsyncMock(return_value=("pi_in_flight", False)),
        ),
        patch.object(stripe_service, "capture_for_order", new=AsyncMock()) as capture,
    ):
        with pytest.raises(public_order_service.CardPaymentNotConfirmed):
            await public_order_service.accept_order(
                db, tenant.id, card_order_pending_intent.id, admin_user.id, 30
            )

    capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_accept_refuses_when_stripe_cannot_be_reached(
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    card_order_pending_intent: Order,
) -> None:
    """Unable to confirm the money is not the same as confirmed, and must not be
    treated as such. Refusing is recoverable -- staff retry in a moment. Cooking
    against a payment we could not verify is not."""
    with (
        patch.object(
            stripe_service,
            "authorization_for_session",
            new=AsyncMock(side_effect=StripeError("network down")),
        ),
        patch.object(stripe_service, "capture_for_order", new=AsyncMock()) as capture,
    ):
        with pytest.raises(PublicOrderError, match="Could not check the card payment"):
            await public_order_service.accept_order(
                db, tenant.id, card_order_pending_intent.id, admin_user.id, 30
            )

    capture.assert_not_awaited()
    await db.refresh(card_order_pending_intent)
    assert card_order_pending_intent.accepted_at is None


# ---------------------------------------------------------------------------
# OI-65 -- the queue re-derives authorisations from Stripe instead of waiting
# to be told. Removing the grace window means a card order has no timeout to
# release it, so publication must never hinge on one webhook delivery arriving.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_queue_publishes_a_card_order_stripe_has_authorised(
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    card_order_pending_intent: Order,
) -> None:
    """The webhook never arrived. The poll must still find the money and publish."""
    with patch.object(
        stripe_service,
        "authorization_for_session",
        new=AsyncMock(return_value=("pi_found_789", True)),
    ):
        published = await public_order_service.publish_authorized_card_orders(
            db, tenant.id
        )

    assert [o.id for o in published] == [card_order_pending_intent.id]
    await db.refresh(card_order_pending_intent)
    assert card_order_pending_intent.payment_authorized_at is not None
    assert card_order_pending_intent.stripe_payment_intent_id == "pi_found_789"


@pytest.mark.asyncio
async def test_the_queue_does_not_publish_an_unauthorised_card_order(
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    card_order_pending_intent: Order,
) -> None:
    """Still on the Checkout page. It stays invisible -- for as long as it takes."""
    with patch.object(
        stripe_service,
        "authorization_for_session",
        new=AsyncMock(return_value=(None, False)),
    ):
        published = await public_order_service.publish_authorized_card_orders(
            db, tenant.id
        )

    assert published == []
    await db.refresh(card_order_pending_intent)
    assert card_order_pending_intent.payment_authorized_at is None


@pytest.mark.asyncio
async def test_a_stripe_outage_cannot_take_the_order_queue_down(
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    card_order_pending_intent: Order,
) -> None:
    """This runs on the tablet's 10-second poll. If it could raise, a Stripe
    outage would stop the shop seeing its CASH orders too -- far worse than a
    delayed card order. The order simply stays unpublished and is retried."""
    with patch.object(
        stripe_service,
        "authorization_for_session",
        new=AsyncMock(side_effect=StripeError("stripe is down")),
    ):
        published = await public_order_service.publish_authorized_card_orders(
            db, tenant.id
        )

    assert published == []
    await db.refresh(card_order_pending_intent)
    assert card_order_pending_intent.payment_authorized_at is None


@pytest.mark.asyncio
async def test_only_one_caller_can_ever_publish_the_same_order(
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    card_order_pending_intent: Order,
) -> None:
    """Three things race to publish: the webhook and the tablet's two separate
    10-second polls. Exactly one must win, or the customer gets two "order
    received" emails for one order. The claim is a conditional UPDATE precisely
    so the database picks the winner rather than a Python read-then-write."""
    first = await public_order_service.mark_card_order_authorized(
        db, card_order_pending_intent, "pi_race_a"
    )
    second = await public_order_service.mark_card_order_authorized(
        db, card_order_pending_intent, "pi_race_b"
    )

    assert first is True
    assert second is False, "the second caller must not also claim the publication"
    # The loser must not have overwritten the winner's intent id either.
    assert card_order_pending_intent.stripe_payment_intent_id == "pi_race_a"


@pytest.mark.asyncio
async def test_the_queue_never_re_publishes_an_already_published_order(
    db: AsyncSession, tenant: Tenant, admin_user: User, card_order: Order
) -> None:
    """`card_order` is already authorised. Re-publishing would send the customer
    a second "we've got your order" email on every single poll."""
    with patch.object(
        stripe_service, "authorization_for_session", new=AsyncMock()
    ) as check:
        published = await public_order_service.publish_authorized_card_orders(
            db, tenant.id
        )

    check.assert_not_awaited()
    assert published == []


@pytest.mark.asyncio
async def test_the_queue_never_asks_stripe_about_a_cash_order(
    db: AsyncSession, tenant: Tenant, admin_user: User, cash_order: Order
) -> None:
    """Cash on delivery has no payment to process. It is never gated, never
    delayed, and never the subject of a Stripe call."""
    with patch.object(
        stripe_service, "authorization_for_session", new=AsyncMock()
    ) as check:
        published = await public_order_service.publish_authorized_card_orders(
            db, tenant.id
        )

    check.assert_not_awaited()
    assert published == []


@pytest.mark.asyncio
async def test_a_card_order_gets_no_received_email_until_the_payment_lands(
    db: AsyncSession, tenant: Tenant, admin_user: User
) -> None:
    """The "order received" email used to fire inside POST /orders, before the
    customer had even reached Stripe's Checkout page. With no grace window that
    becomes a lie: the shop never sees the order, so promising food for it is
    wrong for exactly the customer who then abandons payment. It moves to the
    moment the authorisation lands -- which is also the moment the shop can see
    it. Cash on delivery is unaffected and still emails immediately.
    """
    order = _card_order(
        tenant,
        admin_user,
        order_number="S250101-009",
        stripe_payment_intent_id=None,
        payment_authorized_at=None,
        customer_email="leanne@example.com",
    )
    db.add(order)
    await db.commit()

    sent: list[str] = []

    async def _record(_db, _tenant, _order, event, **_kw):
        sent.append(event)

    with (
        patch.object(
            stripe_service,
            "authorization_for_session",
            new=AsyncMock(return_value=("pi_late_001", True)),
        ),
        patch.object(public_order_service, "notify_customer", new=_record),
    ):
        published = await public_order_service.publish_authorized_card_orders(
            db, tenant.id
        )

    # The service publishes; the route sends. Assert the publish half here and
    # that it is reported exactly once, so the caller cannot double-send.
    assert len(published) == 1
    assert published[0].order_number == "S250101-009"

    with patch.object(
        stripe_service,
        "authorization_for_session",
        new=AsyncMock(return_value=("pi_late_001", True)),
    ):
        again = await public_order_service.publish_authorized_card_orders(db, tenant.id)
    assert again == []


@pytest.mark.asyncio
async def test_a_cash_order_accepts_without_touching_stripe(
    db: AsyncSession, tenant: Tenant, admin_user: User, cash_order: Order
) -> None:
    """Cash on handover is still the default and must be entirely unaffected."""
    with patch.object(stripe_service, "capture_for_order", new=AsyncMock()) as capture:
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

    with patch.object(stripe_service, "capture_for_order", new=AsyncMock()) as capture:
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


# ---------------------------------------------------------------------------
# Hardening (docs/STRIPE_HARDENING_CHECKLIST.md) -- the gap between a feature
# that works and one that can be pointed at real money.
# ---------------------------------------------------------------------------


# --- H-4: capture what the order is worth NOW ------------------------------


@pytest.mark.asyncio
async def test_capture_is_bounded_by_the_current_order_total() -> None:
    """H-4. The shop strikes a sold-out item, then accepts.

    A bare `capture()` takes the full authorised amount, so the customer would
    be charged the original, higher figure and nothing in the system would
    notice -- Stripe did exactly what it was told.
    """
    intent = _StripeLike({"status": "requires_capture", "amount_capturable": 1300})

    with patch.object(stripe_service, "_retrieve_blocking", return_value=intent):
        with patch.object(
            stripe_service, "capture", new=AsyncMock(return_value="succeeded")
        ) as capture:
            result = await stripe_service.capture_for_order("pi_x", 900)

    assert result == "succeeded"
    capture.assert_awaited_once_with("pi_x", amount=900)


@pytest.mark.asyncio
async def test_capture_refuses_when_the_order_is_worth_more_than_was_held() -> None:
    """H-4. Undercharging is a human's decision, not a silent default."""
    intent = _StripeLike({"status": "requires_capture", "amount_capturable": 1000})

    with patch.object(stripe_service, "_retrieve_blocking", return_value=intent):
        with patch.object(stripe_service, "capture", new=AsyncMock()) as capture:
            with pytest.raises(StripeError, match="worth more than was authorised"):
                await stripe_service.capture_for_order("pi_x", 1300)

    # Nothing may be taken when the amounts disagree.
    capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_capture_of_an_already_succeeded_intent_is_not_a_second_charge() -> None:
    """H-4. A retried Accept tap must be a no-op, never a double charge."""
    intent = _StripeLike({"status": "succeeded", "amount_capturable": 0})

    with patch.object(stripe_service, "_retrieve_blocking", return_value=intent):
        with patch.object(stripe_service, "capture", new=AsyncMock()) as capture:
            assert await stripe_service.capture_for_order("pi_x", 1300) == "succeeded"

    capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_capture_raises_when_the_authorisation_is_gone() -> None:
    """H-4. An expired hold must stop the order, not fail quietly.

    An authorisation lasts ~5 days on Visa. A pre-order held longer fails here,
    and the shop has to be told before the kitchen starts.
    """
    intent = _StripeLike({"status": "canceled", "amount_capturable": 0})

    with patch.object(stripe_service, "_retrieve_blocking", return_value=intent):
        with pytest.raises(StripeError, match="No money is being held"):
            await stripe_service.capture_for_order("pi_x", 1300)


# --- resolve_payment_intent_id: the fix for the 260731-001 incident ---------
# `create_checkout_session` only writes `stripe_payment_intent_id`
# opportunistically -- confirmed against the real sandbox, Stripe has usually
# not created the PaymentIntent yet at that point. This is the reliable path,
# used at Accept.


@pytest.mark.asyncio
async def test_resolve_payment_intent_id_reads_the_id_off_the_session() -> None:
    session = _StripeLike({"id": "cs_x", "payment_intent": "pi_resolved"})

    with patch.object(stripe_service, "_retrieve_session_blocking", return_value=session):
        result = await stripe_service.resolve_payment_intent_id("cs_x")

    assert result == "pi_resolved"


@pytest.mark.asyncio
async def test_resolve_payment_intent_id_handles_an_expanded_payment_intent() -> None:
    """`payment_intent` is an id string normally, but an expanded object if
    anyone ever adds `expand=["payment_intent"]`. Handle both, like `field`
    already documents for other Stripe responses.
    """
    session = _StripeLike(
        {"id": "cs_x", "payment_intent": _StripeLike({"id": "pi_expanded"})}
    )

    with patch.object(stripe_service, "_retrieve_session_blocking", return_value=session):
        result = await stripe_service.resolve_payment_intent_id("cs_x")

    assert result == "pi_expanded"


@pytest.mark.asyncio
async def test_resolve_payment_intent_id_is_none_for_an_abandoned_checkout() -> None:
    """The customer never actually paid -- Stripe never created a
    PaymentIntent for the session. `None`, not an error: an ordinary
    abandoned card checkout.
    """
    session = _StripeLike({"id": "cs_x", "payment_intent": None})

    with patch.object(stripe_service, "_retrieve_session_blocking", return_value=session):
        result = await stripe_service.resolve_payment_intent_id("cs_x")

    assert result is None


# --- H-2: a test event must not drive production ---------------------------


def _signed_event(livemode: bool) -> object:
    return _StripeLike({"type": "payment_intent.succeeded", "livemode": livemode})


@pytest.mark.parametrize(
    ("secret_key", "livemode", "accepted"),
    [
        ("sk_test_abc", False, True),
        ("sk_live_abc", True, True),
        ("sk_live_abc", False, False),  # a test event aimed at production
        ("sk_test_abc", True, False),  # a live event aimed at the test box
        # A restricted key is an ordinary thing to deploy, and arguably the
        # better thing. Matching only `sk_live_` would read a live restricted
        # key as test mode and reject every genuine event.
        ("rk_live_abc", True, True),
        ("rk_test_abc", False, True),
    ],
)
def test_webhook_mode_must_match_the_configured_key(
    secret_key: str, livemode: bool, accepted: bool
) -> None:
    """H-2. A valid signature proves the sender, not the mode.

    A test event marking a production order paid puts money in the books that
    does not exist anywhere else.
    """
    event = _signed_event(livemode)

    with patch.object(stripe_service.settings, "STRIPE_WEBHOOK_SECRET", "whsec_x"), \
         patch.object(stripe_service.settings, "STRIPE_SECRET_KEY", secret_key), \
         patch.object(stripe_service, "_client") as client:
        client.return_value.Webhook.construct_event.return_value = event

        if accepted:
            assert stripe_service.verify_webhook(b"{}", "sig") is event
        else:
            with pytest.raises(StripeError, match="mode mismatch"):
                stripe_service.verify_webhook(b"{}", "sig")


# --- H-3: the webhook is tenant-scoped like every other route --------------


def test_tenant_id_is_read_from_event_metadata() -> None:
    """H-3. The metadata already carries it, so the check costs nothing."""
    import uuid as _uuid

    tenant_id = _uuid.uuid4()
    event = _StripeLike(
        {
            "data": _StripeLike(
                {
                    "object": _StripeLike(
                        {"metadata": _StripeLike({"tenant_id": str(tenant_id)})}
                    )
                }
            )
        }
    )

    assert stripe_service.tenant_id_from_event(event) == tenant_id
    # An event with no tenant metadata must not blow up -- older intents and
    # events we never asked for both arrive without it.
    assert stripe_service.tenant_id_from_event({"data": {"object": {}}}) is None


# --- H-7 / H-8: misconfiguration is 503, not 502 ---------------------------


@pytest.mark.asyncio
async def test_a_currency_that_the_stripe_account_cannot_settle_is_refused(
    tenant: Tenant, admin_user: User
) -> None:
    """H-7. The account settles in one currency.

    A tenant misconfigured to PKR would otherwise fail at Stripe, on the payment
    page, in front of a customer who has already committed to the order.
    """
    order = _card_order(tenant, admin_user)
    order.items = []

    with patch.object(stripe_service.settings, "STRIPE_SUCCESS_URL", "https://x/ok"), \
         patch.object(stripe_service.settings, "STRIPE_CANCEL_URL", "https://x/no"), \
         patch.object(stripe_service.settings, "STRIPE_ACCOUNT_CURRENCY", "gbp"):
        with pytest.raises(StripeNotConfigured, match="PKR"):
            await stripe_service.create_checkout_session(order, currency="PKR")


@pytest.mark.asyncio
async def test_unset_return_urls_read_as_unavailable_not_as_a_broken_server(
    tenant: Tenant, admin_user: User
) -> None:
    """H-8. `StripeNotConfigured` is what the route turns into a 503.

    A 502 tells the customer our server is broken and sends whoever debugs it
    looking in entirely the wrong place.
    """
    order = _card_order(tenant, admin_user)
    order.items = []

    with patch.object(stripe_service.settings, "STRIPE_SUCCESS_URL", ""), \
         patch.object(stripe_service.settings, "STRIPE_CANCEL_URL", ""):
        with pytest.raises(StripeNotConfigured):
            await stripe_service.create_checkout_session(order, currency="GBP")


# --- Regression: `timeout=` is not a Stripe API parameter -------------------


class _StrictSessionApi:
    """A fake that rejects unknown parameters, exactly as the real API does.

    The bug this pins: `timeout=20` was passed to `checkout.Session.create()`.
    It is **not** a per-call argument -- the SDK forwards it to Stripe as a
    request FIELD, and the API answers
    `Received unknown parameter: timeout`, which surfaced as a 502 to a
    customer trying to pay.

    Every mocked test passed, because `unittest.mock` accepts any keyword you
    give it and asserts nothing about whether Stripe would. That is the same
    blind spot that hid `StripeObject.get`, so the fix is the same shape: a fake
    that is strict where the mock was permissive.
    """

    #: Everything Stripe genuinely accepts on a Checkout Session create call
    #: that this service uses. `timeout` is deliberately absent.
    ALLOWED = {
        "mode",
        "line_items",
        "payment_intent_data",
        "metadata",
        "customer_email",
        "success_url",
        "cancel_url",
        "idempotency_key",
    }

    def __init__(self) -> None:
        self.captured: dict = {}

    def create(self, **kwargs):  # noqa: ANN003, ANN201 - mirrors the SDK
        unknown = set(kwargs) - self.ALLOWED
        if unknown:
            raise TypeError(f"Received unknown parameter: {sorted(unknown)[0]}")
        self.captured = kwargs
        return {
            "id": "cs_test_1",
            "url": "https://checkout.stripe.com/c/pay/cs_test_1",
            "payment_intent": "pi_test_1",
        }


@pytest.mark.asyncio
async def test_checkout_session_sends_no_parameter_stripe_would_reject(
    tenant: Tenant, admin_user: User
) -> None:
    """The whole call must survive an API that refuses unknown fields."""
    order = _card_order(tenant, admin_user)
    order.items = []

    sessions = _StrictSessionApi()
    fake_stripe = type(
        "FakeStripe", (), {"checkout": type("C", (), {"Session": sessions})()}
    )()

    with patch.object(stripe_service, "_client", return_value=fake_stripe), \
         patch.object(stripe_service.settings, "STRIPE_SUCCESS_URL", "https://x/ok"), \
         patch.object(stripe_service.settings, "STRIPE_CANCEL_URL", "https://x/no"), \
         patch.object(stripe_service.settings, "STRIPE_ACCOUNT_CURRENCY", "gbp"):
        url, session_id, intent_id = await stripe_service.create_checkout_session(
            order, currency="GBP"
        )

    assert session_id == "cs_test_1"
    assert intent_id == "pi_test_1"
    assert url.startswith("https://checkout.stripe.com/")
    assert "timeout" not in sessions.captured, (
        "timeout is an HTTP-client setting, never a Stripe API parameter"
    )
    # The return URLs must still have carried the order id through.
    assert f"order={order.id}" in sessions.captured["success_url"]


def test_the_http_timeout_is_configured_on_the_client_not_the_call() -> None:
    """Where the timeout is supposed to live, so the fix is not undone.

    Deleting the client configuration would make every Stripe call fall back to
    the SDK default of 80 seconds -- a customer staring at a spinner through
    four of our own 20-second budgets.
    """
    import stripe as real_stripe

    original = real_stripe.default_http_client
    try:
        real_stripe.default_http_client = None
        with patch.object(
            stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test_x"
        ):
            stripe_service._client()
        assert real_stripe.default_http_client is not None
        assert getattr(real_stripe.default_http_client, "_timeout", None) == 20
    finally:
        real_stripe.default_http_client = original


# --- The return trip: Stripe sends the customer back to a fresh page load ---


def test_return_urls_carry_the_order_id(tenant: Tenant, admin_user: User) -> None:
    """Without this the customer lands on an empty menu having just paid.

    The storefront is a single page holding its state in memory. Stripe returns
    the browser as a **new page load**, so the only way the confirmation screen
    can be rebuilt is if the order id comes back on the URL.
    """
    order = _card_order(tenant, admin_user)

    success = stripe_service._with_order("https://chickshackg84.com/", order, paid=True)
    cancel = stripe_service._with_order("https://chickshackg84.com/", order, paid=False)

    assert f"order={order.id}" in success
    assert success.endswith("paid=1")
    assert f"order={order.id}" in cancel
    assert cancel.endswith("paid=0")


def test_return_urls_do_not_break_a_url_that_already_has_a_query(
    tenant: Tenant, admin_user: User
) -> None:
    """A `?` already in the configured URL must not become a second `?`.

    Easy to get wrong and invisible until someone configures a return URL with
    a tracking parameter on it, at which point the whole query string is
    silently malformed and the order id never arrives.
    """
    order = _card_order(tenant, admin_user)

    url = stripe_service._with_order(
        "https://chickshackg84.com/?utm_source=qr", order, paid=True
    )

    assert url.count("?") == 1
    assert "utm_source=qr" in url, "the existing query must survive"
    assert f"order={order.id}" in url


# --- H-5: the money must be visible to the shop, not just to Stripe --------


@pytest.mark.asyncio
async def test_capturing_marks_the_order_paid_and_writes_a_payment_row(
    db: AsyncSession, tenant: Tenant, admin_user: User, card_order: Order
) -> None:
    """H-5. Asserted end to end, because reading the code is not evidence.

    The Z-report, the dashboard and the drawer session all read `payments`,
    never `orders.payment_status`. A capture that writes no row is money the
    shop cannot see, and staff chase a customer who has already paid.
    """
    from app.models.payment import Payment

    order_id = card_order.id

    with patch.object(
        stripe_service, "capture_for_order", new=AsyncMock(return_value="succeeded")
    ):
        await public_order_service.accept_order(
            db, tenant.id, order_id, admin_user.id, 30
        )
    await db.commit()

    db.expunge_all()
    refreshed = (
        await db.execute(select(Order).where(Order.id == order_id))
    ).scalar_one()
    assert refreshed.payment_status == "paid", (
        "the tablet would keep showing its unpaid banner on a charged order"
    )

    payments = (
        await db.execute(select(Payment).where(Payment.order_id == order_id))
    ).scalars().all()
    assert len(payments) == 1, "exactly one Payment row per capture"
    assert payments[0].amount == 1300
    assert payments[0].reference == "pi_test_123", "traceable back to Stripe"


# --- H-3 / H-10: the webhook, driven through the actual route --------------


def _intent_event(event_type: str, order_id, tenant_id, livemode: bool = False) -> object:
    return _StripeLike(
        {
            "id": "evt_test_1",
            "type": event_type,
            "livemode": livemode,
            "data": _StripeLike(
                {
                    "object": _StripeLike(
                        {
                            "metadata": _StripeLike(
                                {
                                    "order_id": str(order_id),
                                    "tenant_id": str(tenant_id),
                                }
                            )
                        }
                    )
                }
            ),
        }
    )


@pytest.mark.asyncio
async def test_a_webhook_for_another_tenants_order_is_ignored(
    client, db: AsyncSession, tenant: Tenant, admin_user: User, card_order: Order
) -> None:
    """H-3. Tenant-scope the one unauthenticated write path in the system."""
    import uuid as _uuid

    event = _intent_event("payment_intent.succeeded", card_order.id, _uuid.uuid4())

    with patch.object(stripe_service, "verify_webhook", return_value=event):
        response = await client.post("/api/v1/public/stripe/webhook", content=b"{}")

    assert response.status_code == 200, "Stripe must never be told to retry"
    assert response.json()["status"] == "ignored"

    db.expunge_all()
    refreshed = (
        await db.execute(select(Order).where(Order.id == card_order.id))
    ).scalar_one()
    assert refreshed.payment_captured_at is None, (
        "an event claiming the wrong tenant must not mark an order captured"
    )


@pytest.mark.asyncio
async def test_a_duplicate_webhook_delivery_changes_nothing(
    client, db: AsyncSession, tenant: Tenant, admin_user: User, card_order: Order
) -> None:
    """H-10. Stripe warns that events can arrive more than once.

    There is no event-id ledger, deliberately: every branch is a no-op when the
    state already matches. This pins that property. **If a branch is ever added
    that does something non-idempotent -- writes a Payment row, sends an email
    -- this test stops being sufficient and the ledger becomes necessary.**
    """
    event = _intent_event("payment_intent.succeeded", card_order.id, tenant.id)

    with patch.object(stripe_service, "verify_webhook", return_value=event):
        first = await client.post("/api/v1/public/stripe/webhook", content=b"{}")
        second = await client.post("/api/v1/public/stripe/webhook", content=b"{}")

    assert first.status_code == 200 and second.status_code == 200

    db.expunge_all()
    refreshed = (
        await db.execute(select(Order).where(Order.id == card_order.id))
    ).scalar_one()
    captured_at = refreshed.payment_captured_at
    assert captured_at is not None, "the first delivery should have recorded it"

    # Replay a third time and prove the timestamp does not move.
    with patch.object(stripe_service, "verify_webhook", return_value=event):
        third = await client.post("/api/v1/public/stripe/webhook", content=b"{}")
    assert third.status_code == 200

    db.expunge_all()
    again = (
        await db.execute(select(Order).where(Order.id == card_order.id))
    ).scalar_one()
    assert again.payment_captured_at == captured_at, "a replay must not rewrite state"


def _capturable_event(order_id, tenant_id, *, intent_id: str) -> object:
    """`payment_intent.amount_capturable_updated`, whose object IS the intent.

    Unlike `_intent_event`, this one carries the PaymentIntent's own `id` --
    the field the webhook must now read to backfill
    `orders.stripe_payment_intent_id`.
    """
    return _StripeLike(
        {
            "id": "evt_test_capturable",
            "type": "payment_intent.amount_capturable_updated",
            "livemode": False,
            "data": _StripeLike(
                {
                    "object": _StripeLike(
                        {
                            "id": intent_id,
                            "metadata": _StripeLike(
                                {
                                    "order_id": str(order_id),
                                    "tenant_id": str(tenant_id),
                                }
                            ),
                        }
                    )
                }
            ),
        }
    )


@pytest.mark.asyncio
async def test_webhook_backfills_a_missing_intent_id_from_the_event_itself(
    client,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    card_order_pending_intent: Order,
) -> None:
    """Defense in depth for the 260731-001 incident: `amount_capturable_updated`
    fires exactly when authorisation completes and its own object IS the
    PaymentIntent, so this is a second reliable place (besides Accept's own
    `resolve_payment_intent_id` call) to learn its id -- provided the write
    is not gated on `payment_authorized_at`, which is exactly the mistake
    that let this go unbackfilled originally.
    """
    event = _capturable_event(
        card_order_pending_intent.id, tenant.id, intent_id="pi_from_webhook"
    )

    with patch.object(stripe_service, "verify_webhook", return_value=event):
        response = await client.post("/api/v1/public/stripe/webhook", content=b"{}")

    assert response.status_code == 200

    db.expunge_all()
    refreshed = (
        await db.execute(
            select(Order).where(Order.id == card_order_pending_intent.id)
        )
    ).scalar_one()
    assert refreshed.stripe_payment_intent_id == "pi_from_webhook"
    assert refreshed.payment_authorized_at is not None


@pytest.mark.asyncio
async def test_webhook_never_overwrites_an_intent_id_already_on_the_order(
    client, db: AsyncSession, tenant: Tenant, admin_user: User, card_order: Order
) -> None:
    """`card_order` already carries `pi_test_123`. A replayed or out-of-order
    event must not clobber it with a different id.
    """
    event = _capturable_event(card_order.id, tenant.id, intent_id="pi_someone_elses")

    with patch.object(stripe_service, "verify_webhook", return_value=event):
        response = await client.post("/api/v1/public/stripe/webhook", content=b"{}")

    assert response.status_code == 200

    db.expunge_all()
    refreshed = (
        await db.execute(select(Order).where(Order.id == card_order.id))
    ).scalar_one()
    assert refreshed.stripe_payment_intent_id == "pi_test_123"


# ---------------------------------------------------------------------------
# Late authorisation -- the customer finishes paying *after* the shop has
# already answered the order (Accept or Reject), not before.
#
# `accept_order`/`reject_order` only ever act on a PaymentIntent that already
# exists. Both leave a gap for the ordinary case where the card is still
# authorising when staff tap the button: the order is answered with nothing
# to capture/cancel, and if the authorisation lands moments later nothing was
# previously watching for it. `reconcile_late_authorization`, triggered from
# the same `amount_capturable_updated` event that already backfills the
# intent id, closes that gap. These tests are the same shape as the Accept/
# Reject tests above, just triggered from the webhook instead of the button.
# ---------------------------------------------------------------------------


def _calls_with_action(mock: AsyncMock, action: str) -> list:
    return [c for c in mock.await_args_list if c.kwargs.get("action") == action]


@pytest_asyncio.fixture
async def accepted_card_order_pending_intent(
    db: AsyncSession, tenant: Tenant, admin_user: User
) -> Order:
    """Staff tapped Accept before the customer's card finished authorising.

    Same shape as `card_order_pending_intent` -- no intent id yet, so Accept's
    own live resolve found nothing to capture and fell through as an ordinary
    unpaid order -- except the order really was accepted and the kitchen is
    already cooking. This is exactly the state a late `amount_capturable_
    updated` event must reconcile.
    """
    order = _card_order(
        tenant,
        admin_user,
        order_number="S250101-005",
        stripe_payment_intent_id=None,
        payment_authorized_at=None,
        accepted_at=datetime.now(timezone.utc),
        status="in_kitchen",
    )
    db.add(order)
    await db.flush()
    await db.commit()
    return order


@pytest_asyncio.fixture
async def rejected_card_order_pending_intent(
    db: AsyncSession, tenant: Tenant, admin_user: User
) -> Order:
    """Staff tapped Reject before the customer's card finished authorising.

    Reject's own cancel step had nothing to release yet. A late `amount_
    capturable_updated` event must release the hold once it does exist,
    rather than leaving it to expire on its own days later.
    """
    order = _card_order(
        tenant,
        admin_user,
        order_number="S250101-006",
        stripe_payment_intent_id=None,
        payment_authorized_at=None,
        rejected_at=datetime.now(timezone.utc),
        status="voided",
    )
    db.add(order)
    await db.flush()
    await db.commit()
    return order


@pytest.mark.asyncio
async def test_late_authorization_captures_an_already_accepted_order(
    client,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    accepted_card_order_pending_intent: Order,
) -> None:
    """The race this mechanism exists for. The kitchen already committed to
    the food -- take the payment now, exactly as Accept itself would have if
    the authorisation had landed a few seconds earlier.
    """
    from app.models.payment import Payment

    order_id = accepted_card_order_pending_intent.id
    event = _capturable_event(order_id, tenant.id, intent_id="pi_late_capture")

    with patch.object(stripe_service, "verify_webhook", return_value=event), patch.object(
        stripe_service, "capture_for_order", new=AsyncMock(return_value="succeeded")
    ) as capture, patch.object(
        audit_service, "log_action", new=AsyncMock()
    ) as log_action:
        response = await client.post("/api/v1/public/stripe/webhook", content=b"{}")

    assert response.status_code == 200
    capture.assert_awaited_once_with("pi_late_capture", 1300)

    db.expunge_all()
    refreshed = (
        await db.execute(select(Order).where(Order.id == order_id))
    ).scalar_one()
    assert refreshed.payment_captured_at is not None
    assert refreshed.payment_status == "paid", (
        "the tablet must stop showing NOT PAID once the late capture lands"
    )

    payments = (
        await db.execute(select(Payment).where(Payment.order_id == order_id))
    ).scalars().all()
    assert len(payments) == 1, "exactly one Payment row, same as a normal Accept capture"
    assert payments[0].amount == 1300
    assert payments[0].reference == "pi_late_capture"

    captured_calls = _calls_with_action(log_action, "stripe_captured")
    assert len(captured_calls) == 1, "the late capture must leave a durable audit trail"
    assert captured_calls[0].kwargs["entity_id"] == order_id


@pytest.mark.asyncio
async def test_late_authorization_resends_the_accepted_email_once_paid(
    client,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    accepted_card_order_pending_intent: Order,
) -> None:
    """OI-61: the "accepted" email already sent (if any) was built from the
    payment state at Accept time, which was still unpaid, and told the
    customer "Payable on..." -- confirmed as the direct cause of a real
    double-charge, 2026-08-02 (staff took payment again in person, reading
    that as genuinely unpaid). Once this webhook performs the late capture,
    the "accepted" email must be re-sent so the customer holds a correct one.
    """
    order_id = accepted_card_order_pending_intent.id
    event = _capturable_event(order_id, tenant.id, intent_id="pi_late_capture")

    captured: list[tuple] = []
    done = asyncio.Event()

    async def _capture_send(*args, **kwargs) -> bool:
        captured.append((args, kwargs))
        done.set()
        return True

    with patch.object(stripe_service, "verify_webhook", return_value=event), patch.object(
        stripe_service, "capture_for_order", new=AsyncMock(return_value="succeeded")
    ), patch.object(
        public_order_service.email_service, "send_order_email", new=_capture_send
    ):
        response = await client.post("/api/v1/public/stripe/webhook", content=b"{}")
        assert response.status_code == 200
        await asyncio.wait_for(done.wait(), timeout=2)
        await asyncio.gather(
            *public_order_service._email_tasks, return_exceptions=True
        )

    assert len(captured) == 1
    args, _kwargs = captured[0]
    sent_order, sent_event = args[0], args[1]
    assert sent_event == "accepted"
    assert sent_order.id == order_id
    assert sent_order.payment_status == "paid", (
        "the re-sent email must be built from the order AFTER the late "
        "capture, not the stale pre-capture snapshot"
    )


@pytest.mark.asyncio
async def test_late_authorization_does_not_resend_email_while_still_pending(
    client,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    card_order_pending_intent: Order,
) -> None:
    """No decision has been made yet, so there is no "accepted" email to correct.

    Since OI-65 this delivery is not silent, though: it is the moment the card
    order becomes visible to the shop, so it sends the customer's one and only
    "order received" email -- the one that no longer fires at order-placement
    time. What must NOT fire is "accepted", because nobody has accepted it.
    """
    order_id = card_order_pending_intent.id
    event = _capturable_event(order_id, tenant.id, intent_id="pi_still_pending")

    captured: list[tuple] = []
    done = asyncio.Event()

    async def _capture_send(*args, **kwargs) -> bool:
        captured.append((args, kwargs))
        done.set()
        return True

    with patch.object(stripe_service, "verify_webhook", return_value=event), patch.object(
        stripe_service, "capture_for_order", new=AsyncMock()
    ), patch.object(
        public_order_service.email_service, "send_order_email", new=_capture_send
    ):
        response = await client.post("/api/v1/public/stripe/webhook", content=b"{}")
        assert response.status_code == 200
        await asyncio.wait_for(done.wait(), timeout=2)
        await asyncio.gather(
            *public_order_service._email_tasks, return_exceptions=True
        )

    assert [args[1] for args, _ in captured] == ["received"]


@pytest.mark.asyncio
async def test_late_authorization_releases_an_already_rejected_order(
    client,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    rejected_card_order_pending_intent: Order,
) -> None:
    """The mirror case: the shop already said no before the hold existed to
    release. Once it exists, it must not be left to just expire quietly --
    same principle as `reject_order`'s own cancel step, triggered late.
    """
    order_id = rejected_card_order_pending_intent.id
    event = _capturable_event(order_id, tenant.id, intent_id="pi_late_cancel")

    with patch.object(stripe_service, "verify_webhook", return_value=event), patch.object(
        stripe_service, "cancel", new=AsyncMock(return_value=True)
    ) as cancel, patch.object(audit_service, "log_action", new=AsyncMock()) as log_action:
        response = await client.post("/api/v1/public/stripe/webhook", content=b"{}")

    assert response.status_code == 200
    cancel.assert_awaited_once_with("pi_late_cancel")

    db.expunge_all()
    refreshed = (
        await db.execute(select(Order).where(Order.id == order_id))
    ).scalar_one()
    assert refreshed.payment_captured_at is None
    assert refreshed.status == "voided", "still rejected, not resurrected by a late hold"

    assert len(_calls_with_action(log_action, "stripe_canceled")) == 1


@pytest.mark.asyncio
async def test_late_authorization_does_nothing_while_still_pending(
    client,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    card_order_pending_intent: Order,
) -> None:
    """An order still awaiting an answer is untouched by this path -- Accept's
    own live resolve-and-capture handles it when the shop actually answers,
    exactly as it does today.
    """
    order_id = card_order_pending_intent.id
    event = _capturable_event(order_id, tenant.id, intent_id="pi_still_pending")

    with patch.object(stripe_service, "verify_webhook", return_value=event), patch.object(
        stripe_service, "capture_for_order", new=AsyncMock()
    ) as capture, patch.object(stripe_service, "cancel", new=AsyncMock()) as cancel:
        response = await client.post("/api/v1/public/stripe/webhook", content=b"{}")

    assert response.status_code == 200
    capture.assert_not_awaited()
    cancel.assert_not_awaited()

    db.expunge_all()
    refreshed = (
        await db.execute(select(Order).where(Order.id == order_id))
    ).scalar_one()
    assert refreshed.stripe_payment_intent_id == "pi_still_pending"
    assert refreshed.payment_captured_at is None


@pytest.mark.asyncio
async def test_late_authorization_does_not_double_capture_on_replay(
    client, db: AsyncSession, tenant: Tenant, admin_user: User
) -> None:
    """Stripe can redeliver the same event. A second delivery for an order
    already captured must not charge the customer again -- the same
    `payment_captured_at is None` guard `accept_order` itself relies on.
    """
    order = _card_order(
        tenant,
        admin_user,
        order_number="S250101-007",
        stripe_payment_intent_id="pi_already_captured",
        payment_authorized_at=datetime.now(timezone.utc),
        accepted_at=datetime.now(timezone.utc),
        status="in_kitchen",
        payment_captured_at=datetime.now(timezone.utc),
    )
    db.add(order)
    await db.flush()
    await db.commit()

    event = _capturable_event(order.id, tenant.id, intent_id="pi_already_captured")

    with patch.object(stripe_service, "verify_webhook", return_value=event), patch.object(
        stripe_service, "capture_for_order", new=AsyncMock()
    ) as capture:
        response = await client.post("/api/v1/public/stripe/webhook", content=b"{}")

    assert response.status_code == 200
    capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_late_capture_that_fails_leaves_the_order_accepted_and_uncaptured(
    client,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    accepted_card_order_pending_intent: Order,
) -> None:
    """The one outcome this mechanism cannot fix: food already made, the card
    genuinely fails at the capture moment. The order must not be silently
    corrupted (still accepted, still uncaptured) and Stripe must still get a
    2xx -- retrying cannot change a declined card, so there is nothing to gain
    by making Stripe retry forever. The failure must still be durably logged
    so a human can follow up.
    """
    order_id = accepted_card_order_pending_intent.id
    event = _capturable_event(order_id, tenant.id, intent_id="pi_late_fail")

    with patch.object(stripe_service, "verify_webhook", return_value=event), patch.object(
        stripe_service,
        "capture_for_order",
        new=AsyncMock(side_effect=StripeError("card declined")),
    ), patch.object(audit_service, "log_action", new=AsyncMock()) as log_action:
        response = await client.post("/api/v1/public/stripe/webhook", content=b"{}")

    assert response.status_code == 200

    db.expunge_all()
    refreshed = (
        await db.execute(select(Order).where(Order.id == order_id))
    ).scalar_one()
    assert refreshed.payment_captured_at is None
    assert refreshed.accepted_at is not None, "the order stays accepted -- it cannot be undone"

    assert len(_calls_with_action(log_action, "stripe_capture_failed")) == 1


# ---------------------------------------------------------------------------
# Durable Stripe audit trail -- every transaction, so a dispute can be
# answered from our own records rather than only Stripe's.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkout_session_creation_is_audit_logged(
    db: AsyncSession, cash_order: Order
) -> None:
    with patch.object(audit_service, "log_action", new=AsyncMock()) as log_action:
        await public_order_service.log_stripe_checkout_session_created(
            db, cash_order, session_id="cs_new_123", intent_id=None
        )

    calls = _calls_with_action(log_action, "stripe_checkout_created")
    assert len(calls) == 1
    assert calls[0].kwargs["entity_id"] == cash_order.id
    assert calls[0].kwargs["changes"]["session_id"] == "cs_new_123"


@pytest.mark.asyncio
async def test_accept_capture_is_audit_logged(
    db: AsyncSession, tenant: Tenant, admin_user: User, card_order: Order
) -> None:
    with patch.object(
        stripe_service, "capture_for_order", new=AsyncMock(return_value="succeeded")
    ), patch.object(audit_service, "log_action", new=AsyncMock()) as log_action:
        await public_order_service.accept_order(
            db, tenant.id, card_order.id, admin_user.id, 30
        )

    calls = _calls_with_action(log_action, "stripe_captured")
    assert len(calls) == 1
    assert calls[0].kwargs["user_id"] == admin_user.id, (
        "attributed to the staff member who tapped Accept, not left blank"
    )


@pytest.mark.asyncio
async def test_reject_cancel_is_audit_logged(
    db: AsyncSession, tenant: Tenant, admin_user: User, card_order: Order
) -> None:
    with patch.object(
        stripe_service, "cancel", new=AsyncMock(return_value=True)
    ), patch.object(audit_service, "log_action", new=AsyncMock()) as log_action:
        await public_order_service.reject_order(
            db, tenant.id, card_order.id, admin_user.id, "Too busy"
        )

    calls = _calls_with_action(log_action, "stripe_canceled")
    assert len(calls) == 1
    assert calls[0].kwargs["user_id"] == admin_user.id


@pytest.mark.asyncio
async def test_a_webhook_event_that_changes_nothing_is_still_audit_logged(
    client, db: AsyncSession, tenant: Tenant, admin_user: User, card_order: Order
) -> None:
    """`payment_intent.payment_failed` deliberately leaves the order untouched
    -- the shop may still take cash -- but it is a real Stripe event a dispute
    conversation may need evidence of, so it is logged regardless.
    """
    event = _intent_event("payment_intent.payment_failed", card_order.id, tenant.id)

    with patch.object(stripe_service, "verify_webhook", return_value=event), patch.object(
        audit_service, "log_action", new=AsyncMock()
    ) as log_action:
        response = await client.post("/api/v1/public/stripe/webhook", content=b"{}")

    assert response.status_code == 200
    calls = _calls_with_action(
        log_action, "stripe_webhook_payment_intent.payment_failed"
    )
    assert len(calls) == 1
    assert calls[0].kwargs["entity_id"] == card_order.id
