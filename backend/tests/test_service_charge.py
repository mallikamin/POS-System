"""Danny's D-97: percentage service charge, taxed (PRA Restaurant Services Rules 2012).

Numbers used throughout: 2 x Rs 350.00 = 70000 paisa food.
  service charge 5%      = 3500
  taxable base           = 73500
  cash tax 16%           = 11760   -> total 85260
  card tax 8%            = 5880    -> total 79380
Without a service charge: tax 11200 -> total 81200.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floor import Floor, Table
from app.models.menu import Category, MenuItem
from app.models.order import Order
from app.models.payment import PaymentMethod
from app.models.restaurant_config import RestaurantConfig
from app.services import order_service


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def menu_item(db: AsyncSession, tenant) -> MenuItem:
    cat = Category(tenant_id=tenant.id, name="Karahi", display_order=1, is_active=True)
    db.add(cat)
    await db.flush()
    item = MenuItem(
        tenant_id=tenant.id, category_id=cat.id,
        name="Chicken Karahi", price=35000, is_available=True,
    )
    db.add(item)
    await db.flush()
    await db.commit()
    return item


async def _config(db: AsyncSession, tenant, bps: int, dine_in_only: bool = True) -> RestaurantConfig:
    config = RestaurantConfig(
        tenant_id=tenant.id, payment_flow="order_first", tax_inclusive=False,
        default_tax_rate=1600, cash_tax_rate_bps=1600, card_tax_rate_bps=800,
        service_charge_bps=bps, service_charge_dine_in_only=dine_in_only,
    )
    db.add(config)
    await db.flush()
    await db.commit()
    return config


@pytest_asyncio.fixture
async def table(db: AsyncSession, tenant) -> Table:
    f = Floor(tenant_id=tenant.id, name="Main Hall", display_order=1, is_active=True)
    db.add(f)
    await db.flush()
    t = Table(tenant_id=tenant.id, floor_id=f.id, number=7, capacity=4,
              shape="square", status="available")
    db.add(t)
    await db.flush()
    await db.commit()
    return t


@pytest_asyncio.fixture
async def methods(db: AsyncSession, tenant) -> None:
    db.add_all([
        PaymentMethod(tenant_id=tenant.id, code="cash", display_name="Cash",
                      is_active=True, sort_order=1, requires_reference=False),
        PaymentMethod(tenant_id=tenant.id, code="card", display_name="Card",
                      is_active=True, sort_order=2, requires_reference=True),
    ])
    await db.flush()
    await db.commit()


def _payload(item_id: uuid.UUID, order_type: str, table_id: uuid.UUID | None = None) -> dict:
    body = {
        "order_type": order_type,
        "items": [{"menu_item_id": str(item_id), "name": "Chicken Karahi",
                   "quantity": 2, "unit_price": 35000}],
    }
    if table_id:
        body["table_id"] = str(table_id)
    return body


@pytest.mark.asyncio
async def test_dine_in_charges_service_and_taxes_it(
    client: AsyncClient, cashier_token: str, db, tenant, menu_item, table,
):
    await _config(db, tenant, 500)
    resp = await client.post("/api/v1/orders", json=_payload(menu_item.id, "dine_in", table.id),
                             headers=_auth(cashier_token))
    assert resp.status_code == 201, resp.text
    o = resp.json()
    assert o["subtotal"] == 70000
    assert o["service_charge"] == 3500
    assert o["service_charge_bps"] == 500
    assert o["tax_amount"] == 11760  # 16% of 73500, not of 70000
    assert o["total"] == 85260


@pytest.mark.asyncio
async def test_takeaway_not_charged_when_dine_in_only(
    client: AsyncClient, cashier_token: str, db, tenant, menu_item,
):
    await _config(db, tenant, 500, dine_in_only=True)
    resp = await client.post("/api/v1/orders", json=_payload(menu_item.id, "takeaway"),
                             headers=_auth(cashier_token))
    o = resp.json()
    assert o["service_charge"] == 0 and o["service_charge_bps"] == 0
    assert (o["tax_amount"], o["total"]) == (11200, 81200)


@pytest.mark.asyncio
async def test_takeaway_charged_when_all_channels(
    client: AsyncClient, cashier_token: str, db, tenant, menu_item,
):
    await _config(db, tenant, 500, dine_in_only=False)
    resp = await client.post("/api/v1/orders", json=_payload(menu_item.id, "takeaway"),
                             headers=_auth(cashier_token))
    o = resp.json()
    assert (o["service_charge"], o["tax_amount"], o["total"]) == (3500, 11760, 85260)


@pytest.mark.asyncio
async def test_no_rate_is_byte_identical(
    client: AsyncClient, cashier_token: str, db, tenant, menu_item, table,
):
    """Every tenant that never sets a rate must get exactly the old totals."""
    await _config(db, tenant, 0)
    resp = await client.post("/api/v1/orders", json=_payload(menu_item.id, "dine_in", table.id),
                             headers=_auth(cashier_token))
    o = resp.json()
    assert (o["service_charge"], o["tax_amount"], o["total"]) == (0, 11200, 81200)


@pytest.mark.asyncio
async def test_payment_preview_cash_and_card_include_taxed_service(
    client: AsyncClient, cashier_token: str, db, tenant, menu_item, table,
):
    await _config(db, tenant, 500)
    order_id = (await client.post("/api/v1/orders",
                                  json=_payload(menu_item.id, "dine_in", table.id),
                                  headers=_auth(cashier_token))).json()["id"]
    p = (await client.get(f"/api/v1/orders/{order_id}/payment-preview",
                          headers=_auth(cashier_token))).json()
    assert p["service_charge"] == 3500
    assert (p["cash_tax_amount"], p["cash_total"]) == (11760, 85260)
    assert (p["card_tax_amount"], p["card_total"]) == (5880, 79380)


@pytest.mark.asyncio
async def test_table_settle_by_card_retaxes_and_receipt_shows_service(
    client: AsyncClient, admin_token: str, db, tenant, menu_item, table, methods,
):
    await _config(db, tenant, 500)
    resp = await client.post("/api/v1/orders", json=_payload(menu_item.id, "dine_in", table.id),
                             headers=_auth(admin_token))
    session_id = resp.json()["table_session_id"]
    assert session_id

    prev = (await client.get(f"/api/v1/payments/table-sessions/{session_id}/payment-preview",
                             headers=_auth(admin_token))).json()
    assert prev["service_charge"] == 3500
    assert (prev["cash_total"], prev["card_total"]) == (85260, 79380)

    paid = await client.post(f"/api/v1/payments/table-sessions/{session_id}/pay",
                             headers=_auth(admin_token),
                             json={"method_code": "card", "amount": 79380, "reference": "T1"})
    assert paid.status_code == 201, paid.text
    body = paid.json()
    assert body["payment_status"] == "paid" and body["due_amount"] == 0
    assert body["service_charge"] == 3500
    assert body["total"] == 79380

    rec = (await client.get(f"/api/v1/receipts/sessions/{session_id}",
                            headers=_auth(admin_token))).json()
    assert rec["subtotal"] == 70000
    assert (rec["service_charge"], rec["service_charge_bps"]) == (3500, 500)
    assert rec["tax_amount"] == 5880
    # The printed lines add up to the total.
    assert rec["subtotal"] + rec["service_charge"] + rec["tax_amount"] == rec["total"] == 79380


@pytest.mark.asyncio
async def test_config_patch_sets_rate_and_caps_it(
    client: AsyncClient, admin_token: str, db, tenant,
):
    await _config(db, tenant, 0)
    r = await client.patch("/api/v1/config/restaurant", headers=_auth(admin_token),
                           json={"service_charge_bps": 500})
    assert r.status_code == 200, r.text
    assert r.json()["service_charge_bps"] == 500
    assert r.json()["service_charge_dine_in_only"] is True
    too_high = await client.patch("/api/v1/config/restaurant", headers=_auth(admin_token),
                                  json={"service_charge_bps": 5000})
    assert too_high.status_code == 422


def test_order_total_rule_includes_service_charge():
    o = Order(subtotal=70000, service_charge=3500, tax_amount=11760, discount_amount=1000,
              delivery_fee=0, service_fee=0, tip=0)
    assert order_service.taxable_base(o) == 73500
    assert order_service.order_total(o, prices_include_tax=False) == 73500 + 11760 - 1000
    assert order_service.service_charge_for(70000, 500) == 3500
    assert order_service.service_charge_for(70000, 0) == 0
