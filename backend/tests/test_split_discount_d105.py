"""Danny's D-105: a split cash/card payment on a discounted bill must settle it.

The split screens took the discount off BEFORE tax, while the server charges
tax on the full bill and takes the discount off after (`order_total`). The tax
read from the parts came out wrong: a table discount left the bill 'partial',
a bill discount was refused as "exceeds due amount". Each part now carries its
share of the discount, and the server adds it back to read the tax.
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

# 1000 food, half cash (16%) half card (8%): 580 + 540 = 1120; Rs 200 off, 100 per part.
HALVES = [{"method_code": "cash", "amount": 48000, "discount": 10000},
          {"method_code": "card", "amount": 44000, "discount": 10000}]


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
    for i, code in enumerate(("cash", "card")):
        db.add(PaymentMethod(tenant_id=tenant.id, code=code, display_name=code.title(),
                             is_active=True, sort_order=i, requires_reference=False))
    await db.flush()
    await db.commit()
    return item, t


def _h(token):
    return {"Authorization": f"Bearer {token}"}


async def _order(client, token, item, table=None) -> dict:
    body = {"order_type": "dine_in" if table else "takeaway",
            "items": [{"menu_item_id": str(item.id), "name": "Karahi", "quantity": 1,
                       "unit_price": 100000}]}
    if table:
        body["table_id"] = str(table.id)
    r = await client.post("/api/v1/orders", headers=_h(token), json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def _status(db, order_id) -> tuple[str, int]:
    db.expire_all()
    o = (await db.execute(select(Order).where(Order.id == uuid.UUID(order_id)))).scalar_one()
    return o.payment_status, o.total


@pytest.mark.asyncio
async def test_table_discount_split_cash_card_settles(client, admin_token, admin_user, db, tenant, setup):
    item, table = setup
    o = await _order(client, admin_token, item, table)
    sid = o["table_session_id"]
    await discount_service.apply_discount(db, tenant.id, admin_user.id, None, uuid.UUID(sid), None,
                                          "Table", "manual", 20000, None)
    await db.commit()
    r = await client.post(f"/api/v1/payments/table-sessions/{sid}/split", headers=_h(admin_token),
                          json={"allocations": HALVES})
    assert r.status_code == 201, r.text
    assert await _status(db, o["id"]) == ("paid", 92000)


@pytest.mark.asyncio
async def test_bill_discount_split_cash_card_settles(client, admin_token, admin_user, db, tenant, setup):
    item, _ = setup
    o = await _order(client, admin_token, item)
    await discount_service.apply_discount(db, tenant.id, admin_user.id, uuid.UUID(o["id"]), None,
                                          None, "Bill", "manual", 20000, None)
    await db.commit()
    r = await client.post("/api/v1/payments/split", headers=_h(admin_token),
                          json={"order_id": o["id"], "allocations": HALVES})
    assert r.status_code == 201, r.text
    assert await _status(db, o["id"]) == ("paid", 92000)


@pytest.mark.asyncio
async def test_split_without_a_discount_unchanged(client, admin_token, db, tenant, setup):
    item, _ = setup
    o = await _order(client, admin_token, item)
    r = await client.post("/api/v1/payments/split", headers=_h(admin_token), json={
        "order_id": o["id"], "allocations": [{"method_code": "cash", "amount": 58000},
                                             {"method_code": "card", "amount": 54000}]})
    assert r.status_code == 201, r.text
    assert await _status(db, o["id"]) == ("paid", 112000)


@pytest.mark.asyncio
async def test_split_shares_must_add_up_to_the_discount(client, admin_token, admin_user, db, tenant, setup):
    item, _ = setup
    o = await _order(client, admin_token, item)
    await discount_service.apply_discount(db, tenant.id, admin_user.id, uuid.UUID(o["id"]), None,
                                          None, "Bill", "manual", 20000, None)
    await db.commit()
    wrong = [dict(HALVES[0], discount=5000), HALVES[1]]
    r = await client.post("/api/v1/payments/split", headers=_h(admin_token),
                          json={"order_id": o["id"], "allocations": wrong})
    assert r.status_code == 400 and "must add up" in r.json()["detail"]
    assert (await _status(db, o["id"]))[0] == "unpaid"
