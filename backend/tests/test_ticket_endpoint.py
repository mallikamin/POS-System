"""Integration tests for the kitchen-ticket endpoint.

`test_public_ordering.py` covers the request *schemas* only -- it never makes an
HTTP call. These are the first tests that exercise a public-ordering route
end to end, through the app, the service layer and the database.

The endpoint matters more than most: it is the last step before paper comes out
of a printer in the client's kitchen, and it returns the customer's name, phone
and home address.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderItem, OrderItemModifier
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.models.user import User

pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _url(order_id, fmt: str | None = None) -> str:
    base = f"/api/v1/public/manage/orders/{order_id}/ticket"
    return f"{base}?format={fmt}" if fmt else base


@pytest_asyncio.fixture
async def gbp_config(db: AsyncSession, tenant: Tenant) -> RestaurantConfig:
    """A UK shop on London time -- the configuration Chick Shack runs."""
    config = RestaurantConfig(
        tenant_id=tenant.id, currency="GBP", timezone="Europe/London"
    )
    db.add(config)
    await db.commit()
    return config


@pytest_asyncio.fixture
async def online_order(
    db: AsyncSession, tenant: Tenant, admin_user: User
) -> Order:
    """An accepted online delivery order, unpaid (cash on delivery)."""
    placed = datetime(2026, 7, 27, 17, 42, tzinfo=timezone.utc)
    order = Order(
        tenant_id=tenant.id,
        order_number="260727-001",
        order_type="online",
        status="in_kitchen",
        payment_status="unpaid",
        customer_name="Ahmed Khan",
        customer_phone="07909313456",
        subtotal=2450,
        tax_amount=0,
        discount_amount=0,
        delivery_fee=1500,
        total=3950,
        service_type="delivery",
        delivery_address="Flat 4, 128 Marchmont Crescent",
        delivery_area="Arrochar",
        accepted_at=placed + timedelta(minutes=2),
        eta_minutes=45,
        created_by=admin_user.id,
    )
    db.add(order)
    await db.flush()

    item = OrderItem(
        tenant_id=tenant.id,
        order_id=order.id,
        menu_item_id=uuid.uuid4(),
        name="Peri Peri Half Chicken",
        quantity=2,
        unit_price=850,
        total=1700,
    )
    db.add(item)
    await db.flush()
    db.add(
        OrderItemModifier(
            tenant_id=tenant.id,
            order_item_id=item.id,
            modifier_id=uuid.uuid4(),
            name="Hot",
            price_adjustment=0,
        )
    )
    await db.commit()
    return order


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


async def test_ticket_requires_authentication(
    client: AsyncClient, online_order: Order
):
    """The ticket carries a customer's name, phone and home address.

    Every other route in public.py is deliberately unauthenticated. This one
    must not be, or a UUID is the only thing between a stranger and a
    residential address.
    """
    resp = await client.get(_url(online_order.id))
    assert resp.status_code in (401, 403)


async def test_another_tenant_cannot_read_the_ticket(
    client: AsyncClient, online_order: Order, other_tenant_token: str
):
    """Tenant isolation, checked on the route rather than assumed from the
    service layer."""
    resp = await client.get(_url(online_order.id), headers=_auth(other_tenant_token))
    assert resp.status_code == 404


async def test_unknown_order_is_404_not_500(
    client: AsyncClient, admin_token: str, gbp_config: RestaurantConfig
):
    resp = await client.get(_url(uuid.uuid4()), headers=_auth(admin_token))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Formats
# ---------------------------------------------------------------------------


async def test_default_format_returns_a_usable_rawbt_url(
    client: AsyncClient, admin_token: str, online_order: Order,
    gbp_config: RestaurantConfig,
):
    """This is the payload the tablet navigates to on the Accept tap."""
    resp = await client.get(_url(online_order.id), headers=_auth(admin_token))
    assert resp.status_code == 200

    body = resp.json()
    assert body["url"].startswith("rawbt:base64,")
    decoded = base64.b64decode(body["url"].removeprefix("rawbt:base64,"))
    assert len(decoded) == body["bytes"]
    assert decoded.startswith(b"\x1b@")  # ESC @ initialise


async def test_prn_format_returns_raw_escpos_bytes(
    client: AsyncClient, admin_token: str, online_order: Order,
    gbp_config: RestaurantConfig,
):
    resp = await client.get(_url(online_order.id, "prn"), headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/octet-stream"
    assert ".prn" in resp.headers["content-disposition"]
    assert resp.content.startswith(b"\x1b@")


async def test_preview_format_is_readable_text(
    client: AsyncClient, admin_token: str, online_order: Order,
    gbp_config: RestaurantConfig,
):
    resp = await client.get(
        _url(online_order.id, "preview"), headers=_auth(admin_token)
    )
    assert resp.status_code == 200
    body = resp.text
    assert "260727-001" in body
    assert "2 x Peri Peri Half Chicken" in body
    assert "Arrochar" in body


async def test_an_unknown_format_is_rejected(
    client: AsyncClient, admin_token: str, online_order: Order
):
    resp = await client.get(
        _url(online_order.id, "postscript"), headers=_auth(admin_token)
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Content the kitchen depends on
# ---------------------------------------------------------------------------


async def test_ticket_uses_the_configured_currency_not_the_default(
    client: AsyncClient, admin_token: str, online_order: Order,
    gbp_config: RestaurantConfig,
):
    """The product defaults to PKR. A UK ticket showing Rs. would be visible
    to the client's customers on day one."""
    resp = await client.get(
        _url(online_order.id, "preview"), headers=_auth(admin_token)
    )
    assert "£39.50" in resp.text
    assert "Rs." not in resp.text


async def test_ticket_shows_shop_local_time_not_utc(
    client: AsyncClient, admin_token: str, online_order: Order,
    gbp_config: RestaurantConfig,
):
    """Server is UTC, shop is Europe/London. In July that is BST, +1.

    Accepted 17:44 UTC + 45 min ETA = 18:29 UTC = 19:29 in the shop.
    """
    resp = await client.get(
        _url(online_order.id, "preview"), headers=_auth(admin_token)
    )
    assert "19:29" in resp.text


async def test_unpaid_delivery_tells_the_driver_what_to_collect(
    client: AsyncClient, admin_token: str, online_order: Order,
    gbp_config: RestaurantConfig,
):
    resp = await client.get(
        _url(online_order.id, "preview"), headers=_auth(admin_token)
    )
    assert "NOT PAID" in resp.text
    assert "COLLECT £39.50" in resp.text


async def test_narrow_paper_width_is_honoured(
    client: AsyncClient, admin_token: str, online_order: Order,
    gbp_config: RestaurantConfig,
):
    """58mm paper is 32 columns. If the width is ignored, every line is
    truncated by the printer and nobody finds out until it is live."""
    resp = await client.get(
        f"{_url(online_order.id, 'preview')}&width=32", headers=_auth(admin_token)
    )
    assert resp.status_code == 200
    assert all(len(line) <= 32 for line in resp.text.splitlines())
