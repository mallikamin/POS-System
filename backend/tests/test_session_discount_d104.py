"""Danny's D-104: a TABLE-level discount must land inside the table's orders.

It used to live only on the session: the table paid the discounted amount, the
order stayed 'partial', the session never closed and stock was never deducted.
Every figure the till shows (summary, preview, bill summary, receipt) must equal
what the payment endpoints take, and the orders must end up 'paid'.
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
from app.models.table_session import TableSession
from app.services import discount_service


@pytest_asyncio.fixture
async def setup(db, tenant):
    db.add(RestaurantConfig(tenant_id=tenant.id, payment_flow="order_first", tax_inclusive=False,
                            default_tax_rate=1600, cash_tax_rate_bps=1600, card_tax_rate_bps=800))
    cat = Category(tenant_id=tenant.id, name="F", display_order=1, is_active=True)
    db.add(cat)
    await db.flush()
    karahi = MenuItem(tenant_id=tenant.id, category_id=cat.id, name="Karahi", price=100000,
                      is_available=True)
    naan = MenuItem(tenant_id=tenant.id, category_id=cat.id, name="Naan", price=30000,
                    is_available=True)
    f = Floor(tenant_id=tenant.id, name="H", display_order=1, is_active=True)
    db.add_all([karahi, naan, f])
    await db.flush()
    t = Table(tenant_id=tenant.id, floor_id=f.id, number=1, capacity=4, shape="square",
              status="available")
    db.add(t)
    for i, code in enumerate(("cash", "card")):
        db.add(PaymentMethod(tenant_id=tenant.id, code=code, display_name=code.title(),
                             is_active=True, sort_order=i, requires_reference=False))
    await db.flush()
    await db.commit()
    return {"karahi": karahi, "naan": naan, "table": t}


def _h(token):
    return {"Authorization": f"Bearer {token}"}


async def _order(client, token, s, item) -> dict:
    r = await client.post("/api/v1/orders", headers=_h(token), json={
        "order_type": "dine_in", "table_id": str(s["table"].id),
        "items": [{"menu_item_id": str(item.id), "name": item.name, "quantity": 1,
                   "unit_price": item.price}]})
    assert r.status_code == 201, r.text
    return r.json()


async def _table_discount(db, tenant, admin_user, sid, amount):
    od = await discount_service.apply_discount(
        db, tenant.id, admin_user.id, None, uuid.UUID(sid), None, "Table", "manual", amount, None)
    await db.commit()
    return od


async def _orders(db, sid) -> list[Order]:
    db.expire_all()
    return list((await db.execute(
        select(Order).where(Order.table_session_id == uuid.UUID(sid)).order_by(Order.created_at, Order.id)
    )).scalars().all())


async def _session_status(db, sid) -> str:
    db.expire_all()
    return (await db.execute(
        select(TableSession.status).where(TableSession.id == uuid.UUID(sid)))).scalar_one()


async def _serve_all(client, token, db, sid) -> None:
    """Paid bills complete when served; the table closes on paid AND completed (D-101)."""
    for o in await _orders(db, sid):
        for status in ("ready", "served"):
            r = await client.patch(f"/api/v1/orders/{o.id}/status", headers=_h(token),
                                   json={"status": status})
            assert r.status_code == 200, r.text


async def _due_everywhere(client, token, sid) -> tuple[int, int, int]:
    summ = (await client.get(f"/api/v1/payments/table-sessions/{sid}/summary", headers=_h(token))).json()
    bill = (await client.get(f"/api/v1/table-sessions/{sid}/bill-summary", headers=_h(token))).json()
    prev = (await client.get(f"/api/v1/payments/table-sessions/{sid}/payment-preview", headers=_h(token))).json()
    return summ["due_amount"], bill["due_amount"], prev["cash_total"]


@pytest.mark.asyncio
async def test_discount_goes_into_the_order_and_the_table_settles_by_cash(
        client, admin_token, admin_user, db, tenant, setup):
    o = await _order(client, admin_token, setup, setup["karahi"])
    sid = o["table_session_id"]
    await _table_discount(db, tenant, admin_user, sid, 20000)
    [order] = await _orders(db, sid)
    # 1000 + 16% = 1160, minus 200 = 960, inside the order itself.
    assert (order.session_discount_share, order.discount_amount, order.total) == (20000, 20000, 96000)
    assert await _due_everywhere(client, admin_token, sid) == (96000, 96000, 96000)

    r = await client.post(f"/api/v1/payments/table-sessions/{sid}/pay", headers=_h(admin_token),
                          json={"method_code": "cash", "amount": 96000, "tendered_amount": 100000})
    assert r.status_code == 201, r.text
    [order] = await _orders(db, sid)
    assert order.payment_status == "paid"
    await _serve_all(client, admin_token, db, sid)
    assert await _session_status(db, sid) == "closed"


@pytest.mark.asyncio
async def test_table_settles_by_card_at_the_card_total(client, admin_token, admin_user, db, tenant, setup):
    o = await _order(client, admin_token, setup, setup["karahi"])
    sid = o["table_session_id"]
    await _table_discount(db, tenant, admin_user, sid, 20000)
    prev = (await client.get(f"/api/v1/payments/table-sessions/{sid}/payment-preview",
                             headers=_h(admin_token))).json()
    assert prev["card_total"] == 88000  # 1000 + 8% - 200
    r = await client.post(f"/api/v1/payments/table-sessions/{sid}/pay", headers=_h(admin_token),
                          json={"method_code": "card", "amount": 88000})
    assert r.status_code == 201, r.text
    [order] = await _orders(db, sid)
    assert (order.payment_status, order.total) == ("paid", 88000)
    await _serve_all(client, admin_token, db, sid)
    assert await _session_status(db, sid) == "closed"


@pytest.mark.asyncio
async def test_two_bills_share_the_discount_exactly(client, admin_token, admin_user, db, tenant, setup):
    a = await _order(client, admin_token, setup, setup["karahi"])
    sid = a["table_session_id"]
    b = await _order(client, admin_token, setup, setup["naan"])
    assert b["table_session_id"] == sid
    await _table_discount(db, tenant, admin_user, sid, 10001)  # odd paisa: rounding
    orders = await _orders(db, sid)
    # Proportional to food, 1000 : 300 of 100.01, within a paisa of rounding (which
    # bill takes the remainder depends on creation order, a same-second tie in SQLite).
    karahi = next(o for o in orders if o.subtotal == 100000)
    assert abs(karahi.session_discount_share - 10001 * 100000 / 130000) <= 1
    assert sum(o.session_discount_share for o in orders) == 10001
    due = (await _due_everywhere(client, admin_token, sid))
    expected = 116000 + 34800 - 10001
    assert due == (expected, expected, expected)

    r = await client.post(f"/api/v1/payments/table-sessions/{sid}/pay", headers=_h(admin_token),
                          json={"method_code": "cash", "amount": expected, "tendered_amount": expected})
    assert r.status_code == 201, r.text
    assert [o.payment_status for o in await _orders(db, sid)] == ["paid", "paid"]
    await _serve_all(client, admin_token, db, sid)
    assert await _session_status(db, sid) == "closed"


@pytest.mark.asyncio
async def test_bill_added_after_the_discount_still_settles(client, admin_token, admin_user, db, tenant, setup):
    a = await _order(client, admin_token, setup, setup["karahi"])
    sid = a["table_session_id"]
    await _table_discount(db, tenant, admin_user, sid, 20000)
    await _order(client, admin_token, setup, setup["naan"])  # ordered after the discount
    expected = 116000 + 34800 - 20000
    assert await _due_everywhere(client, admin_token, sid) == (expected, expected, expected)
    r = await client.post(f"/api/v1/payments/table-sessions/{sid}/pay", headers=_h(admin_token),
                          json={"method_code": "cash", "amount": expected, "tendered_amount": expected})
    assert r.status_code == 201, r.text
    orders = await _orders(db, sid)
    assert [o.payment_status for o in orders] == ["paid", "paid"]
    assert sum(o.session_discount_share for o in orders) == 20000
    await _serve_all(client, admin_token, db, sid)
    assert await _session_status(db, sid) == "closed"


@pytest.mark.asyncio
async def test_removing_the_discount_restores_the_bill(client, admin_token, admin_user, db, tenant, setup):
    o = await _order(client, admin_token, setup, setup["karahi"])
    sid = o["table_session_id"]
    od = await _table_discount(db, tenant, admin_user, sid, 20000)
    await discount_service.remove_discount(db, od.id, tenant.id)
    await db.commit()
    [order] = await _orders(db, sid)
    assert (order.session_discount_share, order.discount_amount, order.total) == (0, 0, 116000)
    assert await _due_everywhere(client, admin_token, sid) == (116000, 116000, 116000)


@pytest.mark.asyncio
async def test_order_and_table_discounts_together(client, admin_token, admin_user, db, tenant, setup):
    o = await _order(client, admin_token, setup, setup["karahi"])
    sid = o["table_session_id"]
    await discount_service.apply_discount(db, tenant.id, admin_user.id, uuid.UUID(o["id"]), None,
                                          None, "Bill", "manual", 5000, None)
    await db.commit()
    await _table_discount(db, tenant, admin_user, sid, 20000)
    [order] = await _orders(db, sid)
    assert (order.discount_amount, order.total) == (25000, 91000)
    # The bill summary used to take the order's own discount off a second time.
    assert await _due_everywhere(client, admin_token, sid) == (91000, 91000, 91000)
    r = await client.post(f"/api/v1/payments/table-sessions/{sid}/pay", headers=_h(admin_token),
                          json={"method_code": "cash", "amount": 91000, "tendered_amount": 91000})
    assert r.status_code == 201, r.text
    assert (await _orders(db, sid))[0].payment_status == "paid"


@pytest.mark.asyncio
async def test_receipt_shows_the_discounted_total_once(client, admin_token, admin_user, db, tenant, setup):
    o = await _order(client, admin_token, setup, setup["karahi"])
    sid = o["table_session_id"]
    await _table_discount(db, tenant, admin_user, sid, 20000)
    await client.post(f"/api/v1/payments/table-sessions/{sid}/pay", headers=_h(admin_token),
                      json={"method_code": "cash", "amount": 96000, "tendered_amount": 96000})
    rec = (await client.get(f"/api/v1/receipts/sessions/{sid}", headers=_h(admin_token))).json()
    assert (rec["total"], rec["discount_amount"], rec["payment_status"]) == (96000, 20000, "paid")
    assert [d["amount"] for d in rec["discount_lines"]] == [20000]


@pytest.mark.asyncio
async def test_table_discount_refused_when_every_bill_has_a_payment(
        client, admin_token, admin_user, db, tenant, setup):
    o = await _order(client, admin_token, setup, setup["karahi"])
    sid = o["table_session_id"]
    r = await client.post("/api/v1/payments", headers=_h(admin_token), json={
        "order_id": o["id"], "method_code": "cash", "amount": 50000, "tendered_amount": 50000})
    assert r.status_code == 201, r.text
    with pytest.raises(ValueError, match="already has a payment"):
        await discount_service.apply_discount(db, tenant.id, admin_user.id, None, uuid.UUID(sid),
                                              None, "Table", "manual", 20000, None)
