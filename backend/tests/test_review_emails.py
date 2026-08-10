"""The "how did we do" review-request email.

Malik, 2026-08-10: ask every online customer for a Google review, three hours
after the kitchen accepts. His explicit call was to fire on a timer rather than
on the shop tapping "Complete", so that staff behaviour cannot decide whether
the email goes.

What these tests defend, in order of how much damage each would do:

    double-send    four uvicorn workers sweep on the same timer. If the claim
                   were a read-then-write, one customer would get four emails.
    wrong tenant   a Google review link belongs to one Business Profile. A
                   tenant with no link configured must send nothing at all,
                   which is also how the feature ships inert.
    1am email      an order accepted at 22:00 falls due at 01:00. It must wait
                   for the morning rather than buzz a customer's phone.
    stale burst    switching the feature on must not mail everyone who ordered
                   in the last week.
    rejected       never ask someone to review an order you turned down.

The email transport is always mocked. These assert *our* decisions about who
gets asked and when, never that SMTP works.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from html import escape as html_escape
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.models.user import User
from app.services import email_service, public_order_service


async def _drain_emails() -> None:
    """`notify_customer` is fire-and-forget; let the tasks it spawned finish."""
    await asyncio.gather(
        *public_order_service._email_tasks, return_exceptions=True
    )

REVIEW_URL = "https://g.page/r/Ccxrn-XKIKecEBI/review"

# 13:00 UTC is inside the 09:00-22:00 send window in Europe/London all year,
# in both GMT and BST. Picking a fixed instant keeps these tests from failing
# at particular times of day, which is exactly the OI-63 trap still open in
# this suite.
MIDDAY = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)


def _order(tenant: Tenant, user: User, accepted_ago: timedelta, **overrides) -> Order:
    fields = {
        "tenant_id": tenant.id,
        "order_number": "260810-C001",
        "order_type": "online",
        "status": "completed",
        "payment_status": "paid",
        "service_type": "delivery",
        "subtotal": 2396,
        "tax_amount": 0,
        "discount_amount": 0,
        "delivery_fee": 300,
        "service_fee": 70,
        "total": 2766,
        "created_by": user.id,
        "accepted_at": MIDDAY - accepted_ago,
        "rejected_at": None,
        "customer_name": "Sarah",
        "customer_email": "sarah@example.com",
        # Cash on delivery: no Stripe anywhere, so `is_real_order()` is
        # satisfied by the session id being NULL.
        "stripe_checkout_session_id": None,
        "stripe_payment_intent_id": None,
        "payment_authorized_at": None,
        "review_email_sent_at": None,
    }
    fields.update(overrides)
    return Order(**fields)


@pytest_asyncio.fixture
async def config(db: AsyncSession, tenant: Tenant) -> RestaurantConfig:
    """Chick Shack's real shape: GBP, London, review link set."""
    cfg = RestaurantConfig(
        tenant_id=tenant.id,
        currency="GBP",
        timezone="Europe/London",
        google_review_url=REVIEW_URL,
    )
    db.add(cfg)
    await db.flush()
    await db.commit()
    return cfg


@pytest_asyncio.fixture
async def due_order(db: AsyncSession, tenant: Tenant, admin_user: User) -> Order:
    """Accepted 4 hours ago, so comfortably past the 3-hour delay.

    No `OrderItem` rows: `send_order_email` is mocked in every DB test here, so
    nothing renders the lines. What the email actually *says* is covered by the
    builder tests at the bottom, which need no database at all.
    """
    order = _order(tenant, admin_user, timedelta(hours=4))
    db.add(order)
    await db.flush()
    await db.commit()
    return order


def _frozen_now():
    """Patch the service's clock so 'now' is a fixed, in-window instant."""
    return patch.object(public_order_service, "datetime", _FrozenDatetime)


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return MIDDAY if tz else MIDDAY.replace(tzinfo=None)


# ---------------------------------------------------------------------------
# The happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_due_order_gets_one_review_email(
    db: AsyncSession, tenant: Tenant, config: RestaurantConfig, due_order: Order
) -> None:
    with _frozen_now(), patch(
        "app.services.email_service.send_order_email", new_callable=AsyncMock
    ) as send:
        claimed = await public_order_service.send_due_review_emails(db, tenant.id)
        # notify_customer is fire-and-forget; let the task actually run.
        await _drain_emails()

    assert [o.id for o in claimed] == [due_order.id]
    assert send.await_count == 1
    _, kwargs = send.await_args
    args, _ = send.await_args
    assert args[1] == "review"
    assert kwargs["review_url"] == REVIEW_URL


@pytest.mark.asyncio
async def test_the_claim_is_written_so_a_second_sweep_sends_nothing(
    db: AsyncSession, tenant: Tenant, config: RestaurantConfig, due_order: Order
) -> None:
    """The double-send guard. This is the one that matters with 4 workers."""
    with _frozen_now(), patch(
        "app.services.email_service.send_order_email", new_callable=AsyncMock
    ):
        first = await public_order_service.send_due_review_emails(db, tenant.id)
        second = await public_order_service.send_due_review_emails(db, tenant.id)
        await _drain_emails()

    assert len(first) == 1
    assert second == [], "a second sweep re-sent an email that was already claimed"

    await db.refresh(due_order)
    assert due_order.review_email_sent_at is not None


# ---------------------------------------------------------------------------
# Who must NOT be asked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_tenant_with_no_review_url_sends_nothing(
    db: AsyncSession, tenant: Tenant, due_order: Order
) -> None:
    """No config row at all: the feature is off, which is how it ships."""
    with _frozen_now(), patch(
        "app.services.email_service.send_order_email", new_callable=AsyncMock
    ) as send:
        claimed = await public_order_service.send_due_review_emails(db, tenant.id)

    assert claimed == []
    assert send.await_count == 0


@pytest.mark.asyncio
async def test_an_order_accepted_too_recently_waits(
    db: AsyncSession, tenant: Tenant, config: RestaurantConfig, admin_user: User
) -> None:
    order = _order(tenant, admin_user, timedelta(hours=1), order_number="260810-C002")
    db.add(order)
    await db.flush()
    await db.commit()

    with _frozen_now(), patch(
        "app.services.email_service.send_order_email", new_callable=AsyncMock
    ):
        assert await public_order_service.send_due_review_emails(db, tenant.id) == []


@pytest.mark.asyncio
async def test_a_stale_order_is_never_asked_about(
    db: AsyncSession, tenant: Tenant, config: RestaurantConfig, admin_user: User
) -> None:
    """Switching the feature on must not mailshot last week's customers."""
    order = _order(tenant, admin_user, timedelta(days=3), order_number="260807-C003")
    db.add(order)
    await db.flush()
    await db.commit()

    with _frozen_now(), patch(
        "app.services.email_service.send_order_email", new_callable=AsyncMock
    ):
        assert await public_order_service.send_due_review_emails(db, tenant.id) == []


@pytest.mark.asyncio
async def test_a_rejected_order_is_never_asked_about(
    db: AsyncSession, tenant: Tenant, config: RestaurantConfig, admin_user: User
) -> None:
    order = _order(
        tenant,
        admin_user,
        timedelta(hours=4),
        order_number="260810-C004",
        rejected_at=MIDDAY - timedelta(hours=3, minutes=50),
    )
    db.add(order)
    await db.flush()
    await db.commit()

    with _frozen_now(), patch(
        "app.services.email_service.send_order_email", new_callable=AsyncMock
    ):
        assert await public_order_service.send_due_review_emails(db, tenant.id) == []


@pytest.mark.asyncio
async def test_an_order_with_no_email_address_is_skipped(
    db: AsyncSession, tenant: Tenant, config: RestaurantConfig, admin_user: User
) -> None:
    order = _order(
        tenant,
        admin_user,
        timedelta(hours=4),
        order_number="260810-C005",
        customer_email=None,
    )
    db.add(order)
    await db.flush()
    await db.commit()

    with _frozen_now(), patch(
        "app.services.email_service.send_order_email", new_callable=AsyncMock
    ):
        assert await public_order_service.send_due_review_emails(db, tenant.id) == []


@pytest.mark.asyncio
async def test_an_unpaid_card_order_is_never_asked_about(
    db: AsyncSession, tenant: Tenant, config: RestaurantConfig, admin_user: User
) -> None:
    """`is_real_order()` again: a Stripe session nobody ever paid is not an order.

    Reusing the one rule rather than re-expressing it here is the whole point
    of `order_visibility.py` (OI-61/65/66/68/73).
    """
    order = _order(
        tenant,
        admin_user,
        timedelta(hours=4),
        order_number="260810-C006",
        accepted_at=None,
        stripe_checkout_session_id="cs_live_abandoned",
        payment_authorized_at=None,
    )
    db.add(order)
    await db.flush()
    await db.commit()

    with _frozen_now(), patch(
        "app.services.email_service.send_order_email", new_callable=AsyncMock
    ):
        assert await public_order_service.send_due_review_emails(db, tenant.id) == []


# ---------------------------------------------------------------------------
# The overnight window -- Malik's own question
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nothing_is_sent_in_the_middle_of_the_night(
    db: AsyncSession, tenant: Tenant, config: RestaurantConfig, admin_user: User
) -> None:
    """An order accepted at 22:00 falls due at 01:00 and must wait for 09:00."""
    one_am_utc = datetime(2026, 8, 11, 0, 30, tzinfo=timezone.utc)  # 01:30 BST

    class _Night(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return one_am_utc if tz else one_am_utc.replace(tzinfo=None)

    order = _order(
        tenant,
        admin_user,
        timedelta(0),
        order_number="260810-C007",
        accepted_at=one_am_utc - timedelta(hours=4),
    )
    db.add(order)
    await db.flush()
    await db.commit()

    with patch.object(public_order_service, "datetime", _Night), patch(
        "app.services.email_service.send_order_email", new_callable=AsyncMock
    ) as send:
        assert await public_order_service.send_due_review_emails(db, tenant.id) == []
        assert send.await_count == 0

    # ...and the same order goes out once the morning sweep runs.
    morning = datetime(2026, 8, 11, 8, 30, tzinfo=timezone.utc)  # 09:30 BST

    class _Morning(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return morning if tz else morning.replace(tzinfo=None)

    with patch.object(public_order_service, "datetime", _Morning), patch(
        "app.services.email_service.send_order_email", new_callable=AsyncMock
    ):
        claimed = await public_order_service.send_due_review_emails(db, tenant.id)
        await _drain_emails()

    assert [o.order_number for o in claimed] == ["260810-C007"]


# ---------------------------------------------------------------------------
# What the email actually says. No database: the builders are pure functions.
# ---------------------------------------------------------------------------


def _rendered_order() -> SimpleNamespace:
    """Only the fields the review builders actually read."""
    return SimpleNamespace(
        order_number="260810-C012",
        customer_name="Sarah",
        total=2485,
        items=[
            SimpleNamespace(quantity=2, name="Peri Peri Wrap Meal"),
            SimpleNamespace(quantity=1, name="Chips"),
        ],
    )


def test_the_plain_text_email_names_the_items_and_carries_the_link() -> None:
    subject, body = email_service._body_review(
        _rendered_order(), "Chick Shack", "GBP", review_url=REVIEW_URL
    )
    assert subject == "Chick Shack: how did we do with order 260810-C012?"
    assert "2 x Peri Peri Wrap Meal" in body
    assert "1 x Chips" in body
    # The link must be visible as text, not hidden behind a button: this is
    # what a text-only client shows and what spam filters read.
    assert REVIEW_URL in body
    assert "£24.85" in body


def test_the_html_email_names_the_items_and_carries_the_link() -> None:
    html = email_service._html_review(
        _rendered_order(), "Chick Shack", "GBP", review_url=REVIEW_URL
    )
    assert "Peri Peri Wrap Meal" in html
    assert "Chips" in html
    assert REVIEW_URL in html
    assert "Leave a Google review" in html
    # Malik, 2026-08-10: item as TEXT for now, no photo. The POS has no food
    # photography (image_url is null on all 87 live rows), so an <img> here
    # would be a broken tile in every customer's inbox.
    assert "<img" not in html


def test_a_review_email_with_no_link_is_refused_rather_than_sent_broken() -> None:
    """The tenant switch, enforced at the send boundary too.

    The sweep already refuses to claim an order for a tenant with no URL, but
    this is the second lock: any other caller reaching `send_order_email`
    directly must not be able to post a thank-you note with a dead button on
    it.
    """

    async def _run() -> bool:
        order = _rendered_order()
        order.customer_email = "sarah@example.com"
        return await email_service.send_order_email(
            order, "review", shop_name="Chick Shack", currency="GBP", review_url=""
        )

    assert asyncio.run(_run()) is False


@pytest.mark.asyncio
async def test_two_workers_racing_on_one_order_produce_exactly_one_winner(
    db: AsyncSession, tenant: Tenant, config: RestaurantConfig, due_order: Order
) -> None:
    """The claim itself, not the SELECT that usually hides it.

    ⚠️ `test_the_claim_is_written_so_a_second_sweep_sends_nothing` above does
    NOT prove this. Run sequentially, the second sweep never reaches the claim
    because the SELECT has already filtered the order out. That is a query
    filter, and a query filter is not an invariant (OI-61 -> OI-65).

    The real shape is four uvicorn workers whose SELECTs all run BEFORE any of
    their UPDATEs, so every one of them believes the order is unsent. What must
    then hold is that the database picks exactly one winner. This drives the
    conditional UPDATE twice directly, which is that moment.
    """
    from sqlalchemy import update

    from app.models.order import Order as OrderModel

    claim_at = datetime.now(timezone.utc)

    async def _claim() -> int:
        result = await db.execute(
            update(OrderModel)
            .where(
                OrderModel.id == due_order.id,
                OrderModel.review_email_sent_at.is_(None),
            )
            .values(review_email_sent_at=claim_at)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount

    assert await _claim() == 1, "the first worker should win the order"
    assert await _claim() == 0, (
        "a second worker also claimed an order that was already taken -- "
        "this is the four-emails-to-one-customer bug"
    )


@pytest.mark.asyncio
async def test_a_peak_dinner_order_survives_the_overnight_wait(
    db: AsyncSession, tenant: Tenant, config: RestaurantConfig, admin_user: User
) -> None:
    """The dead zone between the send window and the staleness cutoff.

    ⚠️ This is a real bug that shipped and was caught in production on
    2026-08-10, by dry-running the query at the moment the feature was switched
    on. With `REVIEW_EMAIL_MAX_AGE` at 12h:

        accepted 19:30 -> due 22:30 -> window shut -> waits for 09:00
                       -> by 09:00 it is 13.5h old -> silently dropped

    Every order accepted between roughly 19:00 and 21:00, which is the busiest
    part of the night, was binned without a trace. The failure was invisible
    because a missing email looks exactly like a quiet evening.

    `test_nothing_is_sent_in_the_middle_of_the_night` did NOT catch it: its
    order is accepted at 21:30, only 11h before the morning sweep, so it fell
    inside even the broken 12h cutoff. The bug lived in the gap between two
    passing tests.
    """
    # Accepted 19:30 BST on the 10th (18:30 UTC), the middle of service.
    accepted = datetime(2026, 8, 10, 18, 30, tzinfo=timezone.utc)
    order = _order(
        tenant,
        admin_user,
        timedelta(0),
        order_number="260810-D009",
        accepted_at=accepted,
    )
    db.add(order)
    await db.flush()
    await db.commit()

    # 09:30 BST the next morning: 08:30 UTC, 14h after acceptance.
    morning = datetime(2026, 8, 11, 8, 30, tzinfo=timezone.utc)

    class _Morning(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return morning if tz else morning.replace(tzinfo=None)

    with patch.object(public_order_service, "datetime", _Morning), patch(
        "app.services.email_service.send_order_email", new_callable=AsyncMock
    ):
        claimed = await public_order_service.send_due_review_emails(db, tenant.id)
        await _drain_emails()

    assert [o.order_number for o in claimed] == ["260810-D009"], (
        "a peak-dinner order aged out overnight and was never asked about"
    )


# ---------------------------------------------------------------------------
# Greeting: first name only (Malik, 2026-08-10, reviewing the real rendered
# emails: "Hi Howard Pearson," reads like a mail merge, not a person)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stored,greeting",
    [
        ("Howard Pearson", "Howard"),
        ("Gerardine Anduuru", "Gerardine"),
        # People type their own name in a hurry.
        ("howard pearson", "Howard"),
        # A name that already carries capitals is left alone rather than
        # flattened to "Mcdonald" / "O'brien".
        ("McDonald Smith", "McDonald"),
        ("O'Brien", "O'Brien"),
        ("  Sarah   ", "Sarah"),
        ("", "there"),
        (None, "there"),
    ],
)
def test_the_greeting_uses_the_first_name_only(stored, greeting) -> None:
    order = SimpleNamespace(
        order_number="260810-C012",
        customer_name=stored,
        total=2485,
        items=[SimpleNamespace(quantity=1, name="Chips")],
    )
    _, body = email_service._body_review(
        order, "Chick Shack", "GBP", review_url=REVIEW_URL
    )
    html = email_service._html_review(
        order, "Chick Shack", "GBP", review_url=REVIEW_URL
    )
    assert body.startswith(f"Hi {greeting},")
    # The HTML part escapes the name, so an apostrophe arrives as O&#x27;Brien.
    # That is the escaping working, not a greeting bug.
    assert f"Hi {html_escape(greeting)}," in html
    if stored and " " in str(stored).strip():
        assert str(stored).strip() not in body, "the full name leaked into the text part"


# ---------------------------------------------------------------------------
# Bcc
# ---------------------------------------------------------------------------


def test_bcc_reaches_the_brevo_payload() -> None:
    """Production sends through Brevo, so this is the path that must carry it."""
    captured: dict = {}

    class _Resp:
        status_code = 201
        text = ""

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            captured.update(json or {})
            return _Resp()

    with patch.object(email_service.httpx, "AsyncClient", _Client):
        asyncio.run(
            email_service._send_via_brevo(
                "customer@example.com", "subj", "text", "<p>html</p>", "boss@example.com"
            )
        )

    assert captured["to"] == [{"email": "customer@example.com"}]
    assert captured["bcc"] == [{"email": "boss@example.com"}]


def test_no_bcc_key_is_sent_when_there_is_no_bcc() -> None:
    """The default must not put an empty bcc on every ordinary order email."""
    captured: dict = {}

    class _Resp:
        status_code = 201
        text = ""

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            captured.update(json or {})
            return _Resp()

    with patch.object(email_service.httpx, "AsyncClient", _Client):
        asyncio.run(
            email_service._send_via_brevo(
                "customer@example.com", "subj", "text", "<p>html</p>"
            )
        )

    assert "bcc" not in captured


def test_the_smtp_path_bccs_without_telling_the_customer() -> None:
    """Bcc must be invisible to the recipient, which is the whole point of it.

    `send_message` builds the envelope from the Bcc header and then strips it,
    so the delivered message must not contain the address while the recipient
    list must.
    """
    sent: dict = {}

    class _SMTP:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self, *a, **k):
            pass

        def login(self, *a, **k):
            pass

        def send_message(self, message):
            sent["recipients"] = message.get_all("Bcc") or []
            sent["to"] = message["To"]

    with patch.object(email_service.smtplib, "SMTP", _SMTP), patch.object(
        email_service.smtplib, "SMTP_SSL", _SMTP
    ):
        email_service._send_blocking(
            "customer@example.com", "subj", "text", "<p>h</p>", "boss@example.com"
        )

    assert sent["to"] == "customer@example.com"
    assert sent["recipients"] == ["boss@example.com"], (
        "the Bcc header must be present for smtplib to build the envelope from"
    )
