"""OI-84: the gap between placing a card order and creating its Stripe session.

Malik watched this happen on the live order screen on 2026-08-16: an order
chimed, appeared, vanished for about thirty seconds, then came back.

The storefront places a card order in two requests. The first creates and
COMMITS the row; the second sets `stripe_checkout_session_id` roughly 0.3s
later. Everything that asked "is this a card order?" read the session id, so in
that gap a card order was byte-for-byte indistinguishable from cash on delivery:
visible on the tablet, and -- much worse -- `accept_order`'s money guard was
keyed on the same field, so the whole card-verification block was skipped and
the order could be accepted as cash. Kitchen committed, nothing authorised,
nothing ever captured.

These tests pin the shape of an order in that window, which no existing fixture
covered: `intends_card_payment` true, `stripe_checkout_session_id` NULL.

Deliberately also asserts the paths NOT changed -- cash orders, authorised card
orders, session-but-unauthorised card orders -- because a test that only
exercises the line you just edited proves nothing about the ones you did not
(the OI-61 lesson).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.tenant import Tenant
from app.models.user import User
from app.services import public_order_service
from app.services.order_visibility import is_real_order


def _order(tenant: Tenant, user: User, **overrides) -> Order:
    fields = {
        "tenant_id": tenant.id,
        "order_number": "W250101-001",
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
        "customer_name": "Window Customer",
        "intends_card_payment": False,
        "stripe_payment_intent_id": None,
        "stripe_checkout_session_id": None,
        "payment_authorized_at": None,
        "payment_captured_at": None,
    }
    fields.update(overrides)
    return Order(**fields)


@pytest_asyncio.fixture
async def in_the_window(db: AsyncSession, tenant: Tenant, admin_user: User) -> Order:
    """The bug's exact shape: card chosen, Stripe session not created yet."""
    order = _order(
        tenant,
        admin_user,
        order_number="W250101-002",
        intends_card_payment=True,
        stripe_checkout_session_id=None,
    )
    db.add(order)
    await db.flush()
    await db.commit()
    return order


async def _visible_numbers(db: AsyncSession, tenant: Tenant) -> set[str]:
    result = await db.execute(
        select(Order.order_number).where(
            Order.tenant_id == tenant.id, is_real_order()
        )
    )
    return set(result.scalars().all())


# ---------------------------------------------------------------------------
# Visibility -- the flicker Malik saw
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_card_order_without_a_stripe_session_is_not_real(
    db: AsyncSession, tenant: Tenant, in_the_window: Order
) -> None:
    """THE regression test. Before OI-84 this order was 'real' and chimed."""
    assert in_the_window.order_number not in await _visible_numbers(db, tenant)


@pytest.mark.asyncio
async def test_a_cash_order_is_real_the_moment_it_is_placed(
    db: AsyncSession, tenant: Tenant, admin_user: User
) -> None:
    """The arm that must NOT have been broken by narrowing the first one."""
    order = _order(tenant, admin_user, order_number="W250101-003")
    db.add(order)
    await db.commit()
    assert order.order_number in await _visible_numbers(db, tenant)


@pytest.mark.asyncio
async def test_a_card_order_with_a_session_but_no_authorisation_stays_hidden(
    db: AsyncSession, tenant: Tenant, admin_user: User
) -> None:
    """Unchanged OI-65 behaviour: reaching Stripe is not paying."""
    order = _order(
        tenant,
        admin_user,
        order_number="W250101-004",
        intends_card_payment=True,
        stripe_checkout_session_id="cs_test_window",
    )
    db.add(order)
    await db.commit()
    assert order.order_number not in await _visible_numbers(db, tenant)


@pytest.mark.asyncio
async def test_a_card_order_becomes_real_when_stripe_authorises(
    db: AsyncSession, tenant: Tenant, admin_user: User
) -> None:
    order = _order(
        tenant,
        admin_user,
        order_number="W250101-005",
        intends_card_payment=True,
        stripe_checkout_session_id="cs_test_window2",
        payment_authorized_at=datetime.now(timezone.utc),
    )
    db.add(order)
    await db.commit()
    assert order.order_number in await _visible_numbers(db, tenant)


@pytest.mark.asyncio
async def test_an_already_answered_order_stays_visible(
    db: AsyncSession, tenant: Tenant, admin_user: User
) -> None:
    """History must stay legible even for a card order that was never paid."""
    order = _order(
        tenant,
        admin_user,
        order_number="W250101-006",
        intends_card_payment=True,
        stripe_checkout_session_id=None,
        rejected_at=datetime.now(timezone.utc),
    )
    db.add(order)
    await db.commit()
    assert order.order_number in await _visible_numbers(db, tenant)


# ---------------------------------------------------------------------------
# The money path -- the part that was worse than a flicker
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accept_refuses_a_card_order_that_never_reached_stripe(
    db: AsyncSession, tenant: Tenant, admin_user: User, in_the_window: Order
) -> None:
    """Before OI-84 this was ACCEPTED as though it were cash on delivery.

    `accept_order` guarded on `stripe_checkout_session_id`, which is NULL here,
    so the entire card block was skipped: no authorisation checked, no capture
    attempted, `accepted_at` set, and the order then pinned visible forever by
    the `accepted_at` arm of the predicate. Food cooked, no money held.
    """
    with pytest.raises(
        public_order_service.CardPaymentNotConfirmed, match="has not gone through"
    ):
        await public_order_service.accept_order(
            db, tenant.id, in_the_window.id, admin_user.id, 30
        )

    await db.refresh(in_the_window)
    assert in_the_window.accepted_at is None
    assert in_the_window.payment_captured_at is None
    assert in_the_window.payment_status == "unpaid"
