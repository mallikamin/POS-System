"""Chick Shack "Welcome Back" offer: 20% off, food subtotal >= GBP 30,
Thursday 8 October 2026 (UK) only. See `app/services/promotions.py`."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discount import OrderDiscount
from app.models.menu import Category, MenuItem
from app.models.order import Order
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.models.user import Role
from app.services import promotions
from app.services.promotions import Promotion

WELCOME = promotions.PROMOTIONS["chick-shack"][0]


# ---------------------------------------------------------------------------
# The real Chick Shack window and rule, unpatched
# ---------------------------------------------------------------------------


def _utc(*a: int) -> datetime:
    return datetime(*a, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "now, running",
    [
        (_utc(2026, 10, 7, 22, 59, 59), False),  # Wed 23:59:59 BST
        (_utc(2026, 10, 7, 23, 0, 0), True),  # Thu 00:00 BST
        (_utc(2026, 10, 8, 15, 0, 0), True),  # Thu 16:00 BST, opening
        (_utc(2026, 10, 8, 20, 59, 59), True),  # Thu 21:59:59 BST
        (_utc(2026, 10, 8, 21, 0, 0), False),  # Thu 22:00 BST, shop close
        (_utc(2026, 10, 8, 22, 30, 0), False),  # Thu night pre-order for Friday
        (_utc(2026, 10, 15, 15, 0, 0), False),  # the following Thursday
    ],
)
def test_runs_on_thursday_8_october_uk_time_only(now: datetime, running: bool):
    assert (promotions.active_promotion("chick-shack", now) is not None) is running


def test_no_other_shop_gets_it():
    thursday = _utc(2026, 10, 8, 15, 0, 0)
    for slug in ("ali-fish-chips", "dannys", "martin-fz", "demo-restaurant", None):
        assert promotions.active_promotion(slug, thursday) is None


@pytest.mark.parametrize(
    "subtotal, discount",
    [
        (2999, 0),  # one penny under GBP 30
        (3000, 600),  # exactly GBP 30 -> GBP 6 off
        (3003, 601),  # 600.6 rounds half up
        (4550, 910),
    ],
)
def test_twenty_percent_from_thirty_pounds(subtotal: int, discount: int):
    assert WELCOME.percent_bps == 2000 and WELCOME.min_subtotal == 3000
    assert promotions.discount_for(WELCOME, subtotal) == discount


# ---------------------------------------------------------------------------
# End to end through the public order endpoint, with a promotion running now
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def item(db: AsyncSession, tenant: Tenant, admin_role: Role) -> MenuItem:
    db.add(RestaurantConfig(tenant_id=tenant.id, currency="GBP", default_tax_rate=0))
    category = Category(tenant_id=tenant.id, name="Chicken", display_order=1)
    db.add(category)
    await db.flush()
    menu_item = MenuItem(
        tenant_id=tenant.id,
        category_id=category.id,
        name="Family Bucket",
        price=1500,
        is_available=True,
    )
    db.add(menu_item)
    await db.commit()
    return menu_item


@pytest.fixture
def running_now(monkeypatch, tenant: Tenant):
    now = datetime.now(timezone.utc)
    promo = Promotion(
        code="test-promo",
        label="Welcome Back 20% off",
        percent_bps=2000,
        min_subtotal=3000,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=1),
    )
    monkeypatch.setitem(promotions.PROMOTIONS, tenant.slug, (promo,))
    return promo


async def _order(client: AsyncClient, tenant: Tenant, item: MenuItem, qty: int):
    return await client.post(
        f"/api/v1/public/{tenant.slug}/orders",
        json={
            "service_type": "collection",
            "customer_name": "Test Customer",
            "customer_phone": "07909313456",
            "items": [{"menu_item_id": str(item.id), "quantity": qty}],
        },
    )


@pytest.mark.asyncio
async def test_menu_advertises_running_promotion(
    client: AsyncClient, tenant: Tenant, item: MenuItem, running_now
):
    body = (await client.get(f"/api/v1/public/{tenant.slug}/menu")).json()
    assert body["promotion"]["percent_bps"] == 2000
    assert body["promotion"]["min_subtotal"] == 3000


@pytest.mark.asyncio
async def test_menu_says_none_when_nothing_runs(
    client: AsyncClient, tenant: Tenant, item: MenuItem
):
    body = (await client.get(f"/api/v1/public/{tenant.slug}/menu")).json()
    assert body["promotion"] is None


@pytest.mark.asyncio
async def test_order_of_thirty_pounds_gets_twenty_percent_off(
    client: AsyncClient, db: AsyncSession, tenant: Tenant, item: MenuItem, running_now
):
    resp = await _order(client, tenant, item, 2)  # 2 x 15.00 = 30.00
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["subtotal"] == 3000
    assert body["discount_amount"] == 600
    assert body["total"] == 3000 - 600 + body["service_fee"] + body["delivery_fee"]

    order = await db.get(Order, uuid.UUID(body["id"]))
    assert order.discount_amount == 600 and order.total == body["total"]
    rows = (
        await db.execute(select(OrderDiscount).where(OrderDiscount.order_id == order.id))
    ).scalars().all()
    assert [(r.amount, r.percent_bps, r.source_type) for r in rows] == [
        (600, 2000, "promotion")
    ]


@pytest.mark.asyncio
async def test_order_under_thirty_pounds_gets_nothing(
    client: AsyncClient, db: AsyncSession, tenant: Tenant, item: MenuItem, running_now
):
    resp = await _order(client, tenant, item, 1)  # 15.00
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["discount_amount"] == 0
    assert body["total"] == 1500 + body["service_fee"]
    rows = (
        await db.execute(
            select(OrderDiscount).where(OrderDiscount.order_id == uuid.UUID(body["id"]))
        )
    ).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_no_discount_outside_the_window(
    client: AsyncClient, tenant: Tenant, item: MenuItem
):
    resp = await _order(client, tenant, item, 4)  # 60.00, no promotion running
    assert resp.status_code == 201, resp.text
    assert resp.json()["discount_amount"] == 0
