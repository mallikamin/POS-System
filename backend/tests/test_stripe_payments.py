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
