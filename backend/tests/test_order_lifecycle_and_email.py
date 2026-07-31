"""The rest of the online order's life, and the emails that announce it.

Two things are defended here, and both were shipped untested:

    1. `advance_order` -- the only path that lets an online order finish.
       Before it existed an accepted order sat in the shop's Active tab
       forever and the day's takings never settled.

    2. `email_service` -- a courtesy that must NEVER be able to fail an order.

The second is the one worth being paranoid about. By the time an email is sent
the customer has already been told yes or no, so an exception escaping this
module would roll back an accepted order because a mail server hiccuped. Every
test below that asserts "returns False" is really asserting "did not raise".
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import patch

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.tenant import Tenant
from app.models.user import User
from app.services import email_service, order_service, public_order_service
from app.services.public_order_service import PublicOrderError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _online_order(tenant: Tenant, user: User, **overrides) -> Order:
    fields = {
        "tenant_id": tenant.id,
        "order_number": "L250101-001",
        "order_type": "online",
        "status": "in_kitchen",
        "payment_status": "unpaid",
        "service_type": "delivery",
        "subtotal": 1000,
        "tax_amount": 0,
        "discount_amount": 0,
        "total": 1000,
        "created_by": user.id,
        "accepted_at": None,
        "customer_name": "Test Customer",
    }
    fields.update(overrides)
    return Order(**fields)


@pytest_asyncio.fixture
async def accepted_order(db: AsyncSession, tenant: Tenant, admin_user: User) -> Order:
    """An online order the shop has accepted and is cooking."""
    from datetime import datetime, timezone

    order = _online_order(
        tenant, admin_user, accepted_at=datetime.now(timezone.utc), eta_minutes=30
    )
    db.add(order)
    await db.flush()
    await db.commit()
    return order


# ---------------------------------------------------------------------------
# advance_order -- the guards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["draft", "confirmed", "in_kitchen", "voided", ""])
async def test_only_ready_and_completed_are_reachable(
    db: AsyncSession, tenant: Tenant, admin_user: User, accepted_order: Order, target: str
) -> None:
    """The public lifecycle exposes exactly two moves and no others.

    This endpoint is driven by a tablet in a shop, not by staff who understand
    the state machine. Letting it name any status would make it a back door
    into transitions the POS deliberately guards, `voided` above all.
    """
    with pytest.raises(PublicOrderError):
        await public_order_service.advance_order(
            db, tenant.id, accepted_order.id, admin_user.id, target
        )


@pytest.mark.asyncio
async def test_cannot_advance_an_order_that_was_never_accepted(
    db: AsyncSession, tenant: Tenant, admin_user: User
) -> None:
    """No skipping the accept. The customer has not been told anything yet."""
    order = _online_order(tenant, admin_user, order_number="L250101-002")
    db.add(order)
    await db.flush()
    await db.commit()

    with pytest.raises(PublicOrderError, match="Accept the order"):
        await public_order_service.advance_order(
            db, tenant.id, order.id, admin_user.id, "ready"
        )


@pytest.mark.asyncio
async def test_cannot_advance_a_rejected_order(
    db: AsyncSession, tenant: Tenant, admin_user: User
) -> None:
    """Rejection is terminal. The customer has already been told no."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    order = _online_order(
        tenant,
        admin_user,
        order_number="L250101-003",
        accepted_at=now,
        rejected_at=now,
    )
    db.add(order)
    await db.flush()
    await db.commit()

    with pytest.raises(PublicOrderError, match="rejected"):
        await public_order_service.advance_order(
            db, tenant.id, order.id, admin_user.id, "ready"
        )


@pytest.mark.asyncio
async def test_unknown_order_is_refused(
    db: AsyncSession, tenant: Tenant, admin_user: User
) -> None:
    with pytest.raises(PublicOrderError, match="not found"):
        await public_order_service.advance_order(
            db, tenant.id, uuid.uuid4(), admin_user.id, "ready"
        )


@pytest.mark.asyncio
async def test_a_non_online_order_is_not_reachable_from_here(
    db: AsyncSession, tenant: Tenant, admin_user: User, order: Order
) -> None:
    """The public routes must never be able to touch a till order.

    `order` is a takeaway created at the POS. An online endpoint reaching it
    would be a tenant-scoped but channel-crossing write.
    """
    with pytest.raises(PublicOrderError, match="not found"):
        await public_order_service.advance_order(
            db, tenant.id, order.id, admin_user.id, "ready"
        )


@pytest.mark.asyncio
async def test_generic_transition_cannot_accept_an_online_order(
    db: AsyncSession, tenant: Tenant, admin_user: User
) -> None:
    """The /orders "Send to Kitchen" button must not bypass the accept path.

    Accepting is what promises the customer an ETA, captures a card
    authorisation and notifies them. The generic state machine does none of
    that, so confirmed→in_kitchen for an online order is refused outright —
    food must never be cooked for an order that was never answered.
    """
    order = _online_order(
        tenant, admin_user, order_number="L250101-004", status="confirmed"
    )
    db.add(order)
    await db.flush()
    await db.commit()

    with pytest.raises(ValueError, match="Online Orders queue"):
        await order_service.transition_order(
            db, order.id, tenant.id, admin_user.id, "in_kitchen"
        )


@pytest.mark.asyncio
async def test_generic_transition_still_moves_an_accepted_online_order(
    db: AsyncSession, tenant: Tenant, admin_user: User, accepted_order: Order
) -> None:
    """Only the accept step is fenced off. The queue's own ready/completed
    moves run through this same function and must keep working."""
    moved = await order_service.transition_order(
        db, accepted_order.id, tenant.id, admin_user.id, "ready"
    )
    assert moved.status == "ready"


@pytest.mark.asyncio
async def test_notify_customer_never_waits_for_the_transport(
    db: AsyncSession, tenant: Tenant, admin_user: User
) -> None:
    """An unreachable provider burns its full transport timeout. That wait
    must live in a background task — while it was awaited inline it put ~15
    silent seconds inside every checkout and Accept tap on production
    (2026-07-29, the dead-SMTP period)."""
    release = asyncio.Event()
    ran = asyncio.Event()

    async def _stuck_send(*_a, **_k) -> bool:
        ran.set()
        await release.wait()
        return True

    order = _online_order(tenant, admin_user, order_number="L250101-005")
    with patch.object(
        public_order_service.email_service, "send_order_email", new=_stuck_send
    ):
        start = asyncio.get_running_loop().time()
        await public_order_service.notify_customer(db, tenant.id, order, "received")
        elapsed = asyncio.get_running_loop().time() - start

        assert elapsed < 1.0, "notify_customer blocked on the send"
        # The email is scheduled, not dropped -- it must still actually run.
        await asyncio.wait_for(ran.wait(), timeout=2)
        release.set()
        await asyncio.gather(
            *public_order_service._email_tasks, return_exceptions=True
        )


# ---------------------------------------------------------------------------
# email_service -- it must never raise
# ---------------------------------------------------------------------------


def _emailable(**overrides) -> Order:
    """A detached Order, good enough to render a body. Never persisted."""
    fields = {
        "order_number": "L250101-009",
        "customer_name": "Test Customer",
        "customer_email": "customer@example.com",
        "service_type": "delivery",
        "delivery_address": "1 Test Street",
        "payment_status": "unpaid",
        "status": "in_kitchen",
        "subtotal": 1499,
        "tax_amount": 0,
        "delivery_fee": 0,
        "total": 1499,
        "eta_minutes": 45,
        "rejection_reason": None,
    }
    fields.update(overrides)
    order = Order(**fields)
    order.items = []
    return order


@pytest.mark.asyncio
async def test_no_email_address_is_not_an_error() -> None:
    """Phone-only customers are normal, and predate email being collected."""
    sent = await email_service.send_order_email(_emailable(customer_email=None), "received")
    assert sent is False


@pytest.mark.asyncio
async def test_unknown_event_is_refused_not_raised() -> None:
    sent = await email_service.send_order_email(_emailable(), "nonsense_event")
    assert sent is False


@pytest.mark.asyncio
async def test_nothing_is_sent_while_unconfigured() -> None:
    """The default state of this system. It must be silent, not broken."""
    with patch.object(type(email_service.settings), "email_configured", property(lambda _: False)):
        sent = await email_service.send_order_email(_emailable(), "received")
    assert sent is False


@pytest.mark.asyncio
@pytest.mark.parametrize("event", ["received", "accepted", "rejected", "on_the_way"])
async def test_a_dead_mail_server_never_raises(event: str) -> None:
    """The whole point of the module.

    If this test ever fails, an accepted order can be rolled back by a mail
    server outage -- the customer is told yes, then the order vanishes.
    """
    with patch.object(
        type(email_service.settings), "email_configured", property(lambda _: True)
    ), patch.object(
        email_service, "_send_blocking", side_effect=OSError("connection refused")
    ):
        sent = await email_service.send_order_email(_emailable(), event)
    assert sent is False


def test_reply_to_is_set_and_prefers_the_explicit_address() -> None:
    """A customer hitting reply must reach a mailbox somebody reads.

    We relay as orders@<shop domain> because that is what the customer should
    see, but authenticating a domain for SENDING creates no mailbox. Without a
    Reply-To that lands somewhere real, "can you make it no onion" goes
    nowhere.
    """
    from email.message import EmailMessage

    captured: list[EmailMessage] = []

    with patch.object(email_service.settings, "SMTP_HOST", "localhost"), patch.object(
        email_service.settings, "EMAIL_FROM", "orders@example.com"
    ), patch.object(
        email_service.settings, "EMAIL_REPLY_TO", "shop@example.com"
    ), patch.object(email_service.smtplib, "SMTP") as smtp:
        smtp.return_value.__enter__.return_value.send_message = captured.append
        email_service._send_blocking("customer@example.com", "s", "b", "")

    assert captured[0]["Reply-To"] == "shop@example.com"


def test_reply_to_falls_back_to_the_from_address() -> None:
    from email.message import EmailMessage

    captured: list[EmailMessage] = []

    with patch.object(email_service.settings, "SMTP_HOST", "localhost"), patch.object(
        email_service.settings, "EMAIL_FROM", "orders@example.com"
    ), patch.object(email_service.settings, "EMAIL_REPLY_TO", ""), patch.object(
        email_service.smtplib, "SMTP"
    ) as smtp:
        smtp.return_value.__enter__.return_value.send_message = captured.append
        email_service._send_blocking("customer@example.com", "s", "b", "")

    assert captured[0]["Reply-To"] == "orders@example.com"


@pytest.mark.asyncio
@pytest.mark.parametrize("event", ["received", "accepted", "rejected", "on_the_way"])
async def test_every_event_builds_and_sends(event: str) -> None:
    captured: dict[str, str] = {}

    def _capture(to: str, subject: str, body: str, html: str) -> None:
        captured.update(to=to, subject=subject, body=body, html=html)

    with patch.object(
        type(email_service.settings), "email_configured", property(lambda _: True)
    ), patch.object(email_service, "_send_blocking", side_effect=_capture):
        sent = await email_service.send_order_email(_emailable(), event)

    assert sent is True
    assert captured["to"] == "customer@example.com"
    assert "L250101-009" in captured["subject"]
    assert captured["body"].strip()
    assert "<!doctype html>" in captured["html"].lower()
    assert "L250101-009" in captured["html"]
    assert "CHICK" in captured["html"]


# ---------------------------------------------------------------------------
# The Brevo HTTPS transport (OI-55)
#
# The droplet cannot reach any SMTP port, so production sends through
# api.brevo.com. The fake below is STRICT on purpose: it refuses requests the
# real API would refuse (wrong endpoint, missing api-key, malformed body).
# ERROR_LOG 2026-07-29: a mock that accepts anything proves your logic and
# nothing about the vendor -- that is how `timeout=` sailed through 40 tests.
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self.text = repr(payload)


class _StrictBrevo:
    """Stands in for httpx.AsyncClient, validating like the real endpoint.

    Contract per https://developers.brevo.com/reference/send-transac-email:
    POST /v3/smtp/email with an `api-key` header; `sender.email`, non-empty
    `to[].email`, `subject` and a content field are required; success is 201.
    """

    calls: list[dict] = []

    def __init__(self, **_kwargs) -> None:
        pass

    async def __aenter__(self) -> "_StrictBrevo":
        return self

    async def __aexit__(self, *_exc) -> bool:
        return False

    async def post(self, url: str, json: dict, headers: dict) -> _FakeResponse:
        _StrictBrevo.calls.append({"url": url, "json": json, "headers": headers})
        if url != "https://api.brevo.com/v3/smtp/email":
            return _FakeResponse(404, {"message": "not found"})
        if not str(headers.get("api-key", "")).startswith("xkeysib-"):
            return _FakeResponse(401, {"message": "Key not found", "code": "unauthorized"})
        allowed = {"sender", "to", "subject", "textContent", "htmlContent", "replyTo"}
        unknown = set(json) - allowed
        if unknown:
            return _FakeResponse(
                400, {"message": f"unknown fields {unknown}", "code": "invalid_parameter"}
            )
        sender = json.get("sender") or {}
        recipients = json.get("to") or []
        if (
            "@" not in str(sender.get("email", ""))
            or not recipients
            or any("@" not in str(r.get("email", "")) for r in recipients)
            or not str(json.get("subject", "")).strip()
            or not (json.get("textContent") or json.get("htmlContent"))
        ):
            return _FakeResponse(400, {"message": "missing field", "code": "missing_parameter"})
        reply_to = json.get("replyTo")
        if reply_to is not None and "@" not in str(reply_to.get("email", "")):
            return _FakeResponse(400, {"message": "bad replyTo", "code": "invalid_parameter"})
        return _FakeResponse(201, {"messageId": "<test@relay.brevo.com>"})


def _brevo_settings(key: str = "xkeysib-test-key"):
    """The settings production will run with: API key, no reachable SMTP."""
    return (
        patch.object(email_service.settings, "BREVO_API_KEY", key),
        patch.object(email_service.settings, "SMTP_HOST", ""),
        patch.object(email_service.settings, "EMAIL_FROM", "orders@example.com"),
        patch.object(email_service.settings, "EMAIL_FROM_NAME", "Chick Shack"),
        patch.object(email_service.settings, "EMAIL_REPLY_TO", "shop@example.com"),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("event", ["received", "accepted", "rejected", "on_the_way"])
async def test_brevo_transport_sends_every_event(event: str) -> None:
    """The exact request shape the real API documents, survives the strict fake."""
    _StrictBrevo.calls = []
    p1, p2, p3, p4, p5 = _brevo_settings()
    with p1, p2, p3, p4, p5, patch.object(email_service.httpx, "AsyncClient", _StrictBrevo):
        sent = await email_service.send_order_email(_emailable(), event)

    assert sent is True
    (call,) = _StrictBrevo.calls
    assert call["json"]["sender"] == {"email": "orders@example.com", "name": "Chick Shack"}
    assert call["json"]["to"] == [{"email": "customer@example.com"}]
    assert call["json"]["replyTo"] == {"email": "shop@example.com"}
    assert "L250101-009" in call["json"]["subject"]
    assert call["json"]["textContent"].strip()
    assert call["json"]["htmlContent"].strip()
    assert "L250101-009" in call["json"]["htmlContent"]


@pytest.mark.asyncio
async def test_brevo_key_alone_configures_email() -> None:
    """No SMTP host on this box, ever. The API key must be enough."""
    p1, p2, p3, p4, p5 = _brevo_settings()
    with p1, p2, p3, p4, p5:
        assert email_service.settings.email_configured is True


@pytest.mark.asyncio
async def test_brevo_is_preferred_over_smtp_when_both_are_set() -> None:
    """SMTP cannot work from this host, so a configured key must win."""
    _StrictBrevo.calls = []
    p1, p2, p3, p4, p5 = _brevo_settings()

    def _smtp_must_not_run(*_a, **_k) -> None:
        raise AssertionError("SMTP path used despite BREVO_API_KEY being set")

    with p1, patch.object(email_service.settings, "SMTP_HOST", "smtp.example.com"), p3, p4, p5, patch.object(
        email_service.httpx, "AsyncClient", _StrictBrevo
    ), patch.object(email_service, "_send_blocking", side_effect=_smtp_must_not_run):
        sent = await email_service.send_order_email(_emailable(), "received")

    assert sent is True
    assert len(_StrictBrevo.calls) == 1


@pytest.mark.asyncio
async def test_a_rejected_brevo_key_never_raises() -> None:
    """A 401 from the API is a logged failure, not a lost order."""
    p1, p2, p3, p4, p5 = _brevo_settings(key="wrong-key")
    with p1, p2, p3, p4, p5, patch.object(email_service.httpx, "AsyncClient", _StrictBrevo):
        sent = await email_service.send_order_email(_emailable(), "accepted")
    assert sent is False


@pytest.mark.asyncio
@pytest.mark.parametrize("event", ["received", "accepted", "rejected", "on_the_way"])
async def test_an_unreachable_brevo_api_never_raises(event: str) -> None:
    """The same guarantee the SMTP path makes: an outage costs an email,
    never an order."""

    class _Unreachable(_StrictBrevo):
        async def post(self, url: str, json: dict, headers: dict) -> _FakeResponse:
            raise httpx.ConnectError("connection reset")

    p1, p2, p3, p4, p5 = _brevo_settings()
    with p1, p2, p3, p4, p5, patch.object(email_service.httpx, "AsyncClient", _Unreachable):
        sent = await email_service.send_order_email(_emailable(), event)
    assert sent is False


# ---------------------------------------------------------------------------
# Wording -- a collecting customer must never be told their food is driving
# ---------------------------------------------------------------------------


def test_accepted_email_carries_the_lead_time() -> None:
    """Imran's whole reason for wanting email: a 14:00 order accepted at 15:30."""
    _, body = email_service._body_accepted(_emailable(eta_minutes=45), "Chick Shack", "GBP")
    assert "45 minutes" in body


def test_collection_is_never_described_as_delivery() -> None:
    subject, body = email_service._body_on_the_way(
        _emailable(service_type="collection"), "Chick Shack", "GBP"
    )
    assert "ready to collect" in subject.lower()
    assert "on its way" not in body.lower()


def test_delivery_is_never_described_as_collection() -> None:
    subject, body = email_service._body_on_the_way(
        _emailable(service_type="delivery"), "Chick Shack", "GBP"
    )
    assert "on its way" in subject.lower()
    assert "waiting for you at the shop" not in body.lower()


def test_rejection_falls_back_to_a_civil_reason() -> None:
    """A blank reason must never render as an empty accusation."""
    _, body = email_service._body_rejected(
        _emailable(rejection_reason="   "), "Chick Shack", "GBP"
    )
    assert "unable to take this order" in body.lower()


# ---------------------------------------------------------------------------
# The "received" email's payment line -- mirrors OrderConfirmation.tsx's three
# states exactly, since the website's confirmation page already gets this
# right and the email was silent about it entirely until this was noticed on
# a live sandbox card test.
# ---------------------------------------------------------------------------


def test_received_email_says_card_is_only_held_not_paid() -> None:
    """A card order between checkout and Accept: authorised, not captured."""
    order = _emailable(
        payment_status="unpaid",
        stripe_payment_intent_id="pi_test_123",
        payment_captured_at=None,
    )
    _, body = email_service._body_received(order, "Chick Shack", "GBP")
    html = email_service._html_received(order, "Chick Shack", "GBP")
    assert "we only charge you once the shop accepts" in body.lower()
    assert "we only charge you once the shop accepts" in html.lower()
    assert "paid" not in body.lower().split("we only charge")[0].split("\n")[-1]


def test_received_email_says_paid_once_captured() -> None:
    order = _emailable(payment_status="paid", stripe_payment_intent_id="pi_test_123")
    _, body = email_service._body_received(order, "Chick Shack", "GBP")
    assert "paid by card" in body.lower()


def test_received_email_says_payable_on_collection_for_cash() -> None:
    """No PaymentIntent at all -- the ordinary cash/collection flow."""
    order = _emailable(
        payment_status="unpaid", stripe_payment_intent_id=None, service_type="collection"
    )
    _, body = email_service._body_received(order, "Chick Shack", "GBP")
    assert "payable on collection" in body.lower()
    assert "card" not in body.lower()


# ---------------------------------------------------------------------------
# Money -- this is a GBP client and the POS was born in paisa
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "currency", "expected"),
    [
        (1499, "GBP", "£14.99"),
        (300, "GBP", "£3.00"),
        (0, "GBP", "£0.00"),
        (123456, "GBP", "£1,234.56"),
        (1000, "PKR", "Rs.10.00"),
    ],
)
def test_money_renders_minor_units(amount: int, currency: str, expected: str) -> None:
    assert email_service._money(amount, currency) == expected
