"""A voided online order is dead: no money, no food, no exceptions.

Written after a real incident. Chick Shack order 260828-C001 was cancelled at
the shop's request on 2026-08-28, and the tablet went on showing
`NOT PAID -- COLLECT £45.74` with a live `Mark paid` button beside it. The
server would have honoured the tap and written a real Payment row for £45.74:
money that never existed, in the Z-report and every sales report that reads
payments.

The cause was that both layers asked a FLAG (`rejected_at`) whether the order
was still live, instead of asking its STATUS. Until then the only way an online
order could reach `voided` was `reject_order`, which sets that flag, so the
wrong question kept returning the right answer by accident. A manager void, or
the cancel-after-accept flow, sets the status without the flag.

These tests therefore assert what the ENDPOINT does, not what a component
renders. A test that checked `rejected_at` would have passed throughout the
incident.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.models.user import User

pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def gbp_config(db: AsyncSession, tenant: Tenant) -> RestaurantConfig:
    config = RestaurantConfig(
        tenant_id=tenant.id, currency="GBP", timezone="Europe/London"
    )
    db.add(config)
    await db.commit()
    return config


@pytest_asyncio.fixture
async def voided_order(db: AsyncSession, tenant: Tenant, admin_user: User) -> Order:
    """An accepted, unpaid, cash-on-collection order that was then voided.

    `rejected_at` is deliberately left null: this is a void that did NOT come
    through the reject path, which is exactly the case both guards missed.
    """
    placed = datetime(2026, 8, 28, 10, 54, tzinfo=timezone.utc)
    order = Order(
        tenant_id=tenant.id,
        order_number="260828-C001",
        order_type="online",
        status="voided",
        payment_status="unpaid",
        customer_name="Sean Taylor",
        customer_phone="07580526182",
        subtotal=4504,
        tax_amount=0,
        discount_amount=0,
        delivery_fee=0,
        total=4574,
        service_type="collection",
        accepted_at=placed + timedelta(hours=3, minutes=27),
        rejected_at=None,
        eta_minutes=45,
        created_by=admin_user.id,
    )
    db.add(order)
    await db.flush()
    db.add(
        OrderItem(
            tenant_id=tenant.id,
            order_id=order.id,
            menu_item_id=uuid.uuid4(),
            name="Double Chicken Fillet Wrap Meal",
            quantity=1,
            unit_price=1199,
            total=1199,
        )
    )
    await db.commit()
    return order


async def test_mark_paid_is_refused_on_a_voided_order(
    client: AsyncClient,
    admin_token: str,
    voided_order: Order,
    gbp_config: RestaurantConfig,
):
    """The money bug itself. A 200 here is £45.74 of phantom takings."""
    resp = await client.post(
        f"/api/v1/public/manage/orders/{voided_order.id}/paid",
        json={"method_code": "cash"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 409, resp.text
    assert "cancelled" in resp.json()["detail"].lower()


async def test_no_payment_row_is_written_for_a_voided_order(
    db: AsyncSession,
    client: AsyncClient,
    admin_token: str,
    voided_order: Order,
    gbp_config: RestaurantConfig,
):
    """Asserted against the payments table, because that is what the Z-report
    reads. A refusal that still left a row behind would be no fix at all."""
    await client.post(
        f"/api/v1/public/manage/orders/{voided_order.id}/paid",
        json={"method_code": "cash"},
        headers=_auth(admin_token),
    )
    count = await db.scalar(
        select(func.count()).select_from(Payment).where(
            Payment.order_id == voided_order.id
        )
    )
    assert count == 0

    refreshed = await db.scalar(
        select(Order).where(Order.id == voided_order.id)
    )
    await db.refresh(refreshed)
    assert refreshed.payment_status == "unpaid"
    assert refreshed.status == "voided"


async def test_a_voided_order_cannot_be_marked_ready(
    client: AsyncClient,
    admin_token: str,
    voided_order: Order,
    gbp_config: RestaurantConfig,
):
    """Cancelled food is not cooked, and the customer is not told it is on its
    way."""
    resp = await client.post(
        f"/api/v1/public/manage/orders/{voided_order.id}/ready",
        json={},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 409, resp.text
    assert "cancelled" in resp.json()["detail"].lower()


async def test_a_voided_order_cannot_be_completed(
    client: AsyncClient,
    admin_token: str,
    voided_order: Order,
    gbp_config: RestaurantConfig,
):
    """`complete` carries `mark_paid`, so this is the same money bug by a
    second route."""
    resp = await client.post(
        f"/api/v1/public/manage/orders/{voided_order.id}/complete",
        json={"mark_paid": True},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 409, resp.text


async def test_a_rejected_order_is_still_refused(
    db: AsyncSession,
    client: AsyncClient,
    admin_token: str,
    voided_order: Order,
    gbp_config: RestaurantConfig,
):
    """No regression: the old `rejected_at` check was replaced, not widened.
    `reject_order` sets status to `voided` too, so rejections stay covered."""
    voided_order.rejected_at = datetime.now(timezone.utc)
    voided_order.rejection_reason = "Too busy right now"
    await db.commit()

    resp = await client.post(
        f"/api/v1/public/manage/orders/{voided_order.id}/paid",
        json={"method_code": "cash"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 409, resp.text
