"""D-103: the payment previews must ask for what the bill is for, discounts included.
D-104 (open): a TABLE-level discount leaves the order 'partial' after the table pays.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.floor import Floor, Table
from app.models.menu import Category, MenuItem
from app.models.order import Order
from app.models.payment import PaymentMethod
from app.models.restaurant_config import RestaurantConfig
from app.services import discount_service


@pytest_asyncio.fixture
async def setup(db, tenant):
    db.add(RestaurantConfig(tenant_id=tenant.id, payment_flow="order_first", tax_inclusive=False,
                            default_tax_rate=1600, cash_tax_rate_bps=1600, card_tax_rate_bps=800))
    cat = Category(tenant_id=tenant.id, name="F", display_order=1, is_active=True)
    db.add(cat)
    await db.flush()
    item = MenuItem(tenant_id=tenant.id, category_id=cat.id, name="Karahi", price=100000,
                    is_available=True)
    f = Floor(tenant_id=tenant.id, name="H", display_order=1, is_active=True)
    db.add_all([item, f])
    await db.flush()
    t = Table(tenant_id=tenant.id, floor_id=f.id, number=1, capacity=4, shape="square",
              status="available")
    db.add(t)
    db.add(PaymentMethod(tenant_id=tenant.id, code="cash", display_name="Cash", is_active=True,
                         sort_order=1, requires_reference=False))
    await db.flush()
    await db.commit()
    return item, t


async def _table_with_discount(client, h, db, tenant, admin_user, item, table, level):
    o = (await client.post("/api/v1/orders", headers=h, json={
        "order_type": "dine_in", "table_id": str(table.id),
        "items": [{"menu_item_id": str(item.id), "name": "Karahi", "quantity": 1,
                   "unit_price": 100000}]})).json()
    sid = o["table_session_id"]
    await discount_service.apply_discount(
        db, tenant.id, admin_user.id,
        uuid.UUID(o["id"]) if level == "order" else None,
        uuid.UUID(sid) if level == "session" else None,
        None, "Test", "manual", 20000, None)
    await db.commit()
    return o, sid


@pytest.mark.asyncio
@pytest.mark.parametrize("level", ["order", "session"])
async def test_preview_asks_for_the_discounted_bill(client, admin_token, admin_user, db, tenant,
                                                    setup, level):
    item, table = setup
    h = {"Authorization": f"Bearer {admin_token}"}
    o, sid = await _table_with_discount(client, h, db, tenant, admin_user, item, table, level)
    prev = (await client.get(f"/api/v1/payments/table-sessions/{sid}/payment-preview", headers=h)).json()
    summ = (await client.get(f"/api/v1/payments/table-sessions/{sid}/summary", headers=h)).json()
    # 1000 food + 16% = 1160, minus 200 off = 960. Card: 1000 + 8% - 200 = 880.
    assert prev["cash_total"] == summ["due_amount"] == 96000
    assert prev["card_total"] == 88000
    if level == "order":
        one = (await client.get(f"/api/v1/orders/{o['id']}/payment-preview", headers=h)).json()
        assert (one["cash_total"], one["card_total"]) == (96000, 88000)


@pytest.mark.asyncio
async def test_order_discount_table_settles_fully(client, admin_token, admin_user, db, tenant, setup):
    item, table = setup
    h = {"Authorization": f"Bearer {admin_token}"}
    o, sid = await _table_with_discount(client, h, db, tenant, admin_user, item, table, "order")
    r = await client.post(f"/api/v1/payments/table-sessions/{sid}/pay", headers=h,
                          json={"method_code": "cash", "amount": 96000, "tendered_amount": 96000})
    assert r.status_code == 201
    db.expire_all()
    order = (await db.execute(select(Order).where(Order.id == uuid.UUID(o["id"])))).scalar_one()
    assert order.payment_status == "paid"


@pytest.mark.xfail(strict=True, reason="D-104 open: a table-level discount is not carried "
                                       "into the orders, so the order stays 'partial'")
@pytest.mark.asyncio
async def test_session_discount_table_settles_fully(client, admin_token, admin_user, db, tenant, setup):
    item, table = setup
    h = {"Authorization": f"Bearer {admin_token}"}
    o, sid = await _table_with_discount(client, h, db, tenant, admin_user, item, table, "session")
    await client.post(f"/api/v1/payments/table-sessions/{sid}/pay", headers=h,
                      json={"method_code": "cash", "amount": 96000, "tendered_amount": 96000})
    db.expire_all()
    order = (await db.execute(select(Order).where(Order.id == uuid.UUID(o["id"])))).scalar_one()
    assert order.payment_status == "paid"
