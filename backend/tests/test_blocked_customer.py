"""A customer the shop has blocked cannot place an online order.

Why this file exists
--------------------
Chick Shack asked on 2026-08-28 to stop one specific customer from reordering.
`customers.risk_flag` already had a `blocked` value, and it could already be
set through `PATCH /customers/{id}`, but nothing on the public order path ever
read it: the flag painted a badge on the call-centre page and did nothing else.
Setting it would have changed nothing on the storefront.

The rule, enforced on the ENDPOINT (a client-side check is a suggestion):

    A `blocked` customer of this tenant, matched by phone OR email, is refused
    with a customer-readable 409 before any order row, customer row or Stripe
    session exists.

Every test asserts what the endpoint returns and what the tables hold.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.menu import Category, MenuItem
from app.models.order import Order
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.models.user import Role
from app.services.public_order_service import CUSTOMER_BLOCKED_MESSAGE

pytestmark = pytest.mark.asyncio

ORDER_URL = "/api/v1/public/test-restaurant/orders"

BLOCKED_PHONE = "4915737378527"
BLOCKED_EMAIL = "Blocked.Customer@example.com"


@pytest_asyncio.fixture
async def uk_menu(db: AsyncSession, tenant: Tenant, admin_role: Role) -> MenuItem:
    """An orderable tenant: config, a role for the online system user, an item."""
    db.add(RestaurantConfig(tenant_id=tenant.id, currency="GBP", default_tax_rate=0))
    await db.flush()
    category = Category(tenant_id=tenant.id, name="Chicken", display_order=1)
    db.add(category)
    await db.flush()
    item = MenuItem(
        tenant_id=tenant.id,
        category_id=category.id,
        name="Peri Peri Half Chicken",
        price=850,
        is_available=True,
    )
    db.add(item)
    await db.commit()
    return item


@pytest_asyncio.fixture
async def blocked_customer(db: AsyncSession, tenant: Tenant) -> Customer:
    customer = Customer(
        tenant_id=tenant.id,
        name="Blocked Customer",
        phone=BLOCKED_PHONE,
        email=BLOCKED_EMAIL,
        risk_flag="blocked",
    )
    db.add(customer)
    await db.commit()
    return customer


def _basket(item: MenuItem, **overrides) -> dict:
    payload = {
        "service_type": "collection",
        "customer_name": "Somebody",
        "customer_phone": "07909313456",
        "items": [{"menu_item_id": str(item.id), "quantity": 1}],
    }
    payload.update(overrides)
    return payload


async def _counts(db: AsyncSession) -> tuple[int, int]:
    orders = (await db.execute(select(func.count(Order.id)))).scalar_one()
    customers = (await db.execute(select(func.count(Customer.id)))).scalar_one()
    return orders, customers


# ---------------------------------------------------------------------------
# The refusal
# ---------------------------------------------------------------------------


async def test_blocked_phone_is_refused_and_nothing_is_written(
    client: AsyncClient, db: AsyncSession, uk_menu: MenuItem, blocked_customer: Customer
):
    before = await _counts(db)

    resp = await client.post(ORDER_URL, json=_basket(uk_menu, customer_phone=BLOCKED_PHONE))

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == CUSTOMER_BLOCKED_MESSAGE
    assert await _counts(db) == before, "a refused order must leave no rows behind"


async def test_blocked_phone_typed_with_spaces_and_plus_is_still_refused(
    client: AsyncClient, uk_menu: MenuItem, blocked_customer: Customer
):
    """The link normalises to digits; the block must compare the same string."""
    resp = await client.post(
        ORDER_URL, json=_basket(uk_menu, customer_phone="+49 1573 737 8527")
    )
    assert resp.status_code == 409, resp.text


async def test_blocked_email_with_a_new_phone_is_refused(
    client: AsyncClient, db: AsyncSession, uk_menu: MenuItem, blocked_customer: Customer
):
    """The phone-only link would have created a fresh, unflagged customer here.

    Email is the second net, and it is case-insensitive: the customer typed it
    in mixed case when the shop first saw them.
    """
    before = await _counts(db)

    resp = await client.post(
        ORDER_URL,
        json=_basket(
            uk_menu,
            customer_phone="07000000001",
            customer_email="blocked.customer@EXAMPLE.com",
        ),
    )

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == CUSTOMER_BLOCKED_MESSAGE
    assert await _counts(db) == before


# ---------------------------------------------------------------------------
# What must NOT be refused
# ---------------------------------------------------------------------------


async def test_a_different_customer_still_orders(
    client: AsyncClient, uk_menu: MenuItem, blocked_customer: Customer
):
    resp = await client.post(
        ORDER_URL,
        json=_basket(uk_menu, customer_phone="07909313456", customer_email="ok@example.com"),
    )
    assert resp.status_code == 201, resp.text


async def test_same_name_alone_is_not_a_block(
    client: AsyncClient, uk_menu: MenuItem, blocked_customer: Customer
):
    """Two people can share a name. A false block costs the shop a customer."""
    resp = await client.post(
        ORDER_URL,
        json=_basket(uk_menu, customer_name="Blocked Customer", customer_phone="07000000002"),
    )
    assert resp.status_code == 201, resp.text


async def test_high_risk_is_a_warning_not_a_refusal(
    client: AsyncClient, db: AsyncSession, tenant: Tenant, uk_menu: MenuItem
):
    """`high` is recomputed from order history by a heuristic. Only a deliberate
    `blocked` refuses; a tenant must never lose customers to arithmetic."""
    db.add(
        Customer(tenant_id=tenant.id, name="Risky", phone="07000000003", risk_flag="high")
    )
    await db.commit()

    resp = await client.post(ORDER_URL, json=_basket(uk_menu, customer_phone="07000000003"))
    assert resp.status_code == 201, resp.text


async def test_a_block_on_another_tenant_does_not_reach_this_shop(
    client: AsyncClient,
    db: AsyncSession,
    other_tenant: Tenant,
    uk_menu: MenuItem,
):
    """Blocks are per shop. The same phone blocked at one restaurant is a
    perfectly good customer at another."""
    db.add(
        Customer(
            tenant_id=other_tenant.id,
            name="Blocked Elsewhere",
            phone=BLOCKED_PHONE,
            risk_flag="blocked",
        )
    )
    await db.commit()

    resp = await client.post(ORDER_URL, json=_basket(uk_menu, customer_phone=BLOCKED_PHONE))
    assert resp.status_code == 201, resp.text


async def test_unblocking_lets_the_customer_order_again(
    client: AsyncClient, db: AsyncSession, uk_menu: MenuItem, blocked_customer: Customer
):
    """The flag is the whole mechanism; flipping it back must be enough."""
    blocked_customer.risk_flag = "normal"
    await db.commit()

    resp = await client.post(ORDER_URL, json=_basket(uk_menu, customer_phone=BLOCKED_PHONE))
    assert resp.status_code == 201, resp.text
