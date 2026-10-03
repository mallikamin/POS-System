"""Danny's D-99: visit loyalty. One visit per PAID bill, at most the owner's limit per
customer per day (default 1, 0 = no limit), claimable by the cashier (phone on the
order) or the customer (bill QR). A bill with a phone on it belongs to that customer.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.loyalty import LoyaltyVisit
from app.models.menu import Category, MenuItem
from app.models.payment import PaymentMethod
from app.models.restaurant_config import RestaurantConfig

PHONE = "03001234567"


def _auth(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


@pytest_asyncio.fixture
async def menu(db: AsyncSession, tenant) -> dict:
    cat = Category(tenant_id=tenant.id, name="Food", display_order=1, is_active=True)
    db.add(cat)
    await db.flush()
    karahi = MenuItem(tenant_id=tenant.id, category_id=cat.id, name="Chicken Karahi",
                      price=188900, is_available=True)
    coffee = MenuItem(tenant_id=tenant.id, category_id=cat.id, name="Cappuccino",
                      price=79900, is_available=True)
    db.add_all([karahi, coffee])
    db.add(PaymentMethod(tenant_id=tenant.id, code="cash", display_name="Cash",
                         is_active=True, sort_order=1, requires_reference=False))
    await db.flush()
    await db.commit()
    return {"karahi": karahi, "coffee": coffee}


async def _config(db, tenant, menu, enabled=True, per_day=1) -> RestaurantConfig:
    c = RestaurantConfig(tenant_id=tenant.id, payment_flow="order_first", tax_inclusive=False,
                         default_tax_rate=1600, cash_tax_rate_bps=1600, card_tax_rate_bps=800,
                         loyalty_enabled=enabled, loyalty_visits_required=5,
                         loyalty_reward_menu_item_id=menu["coffee"].id,
                         loyalty_max_visits_per_day=per_day)
    db.add(c)
    await db.flush()
    await db.commit()
    return c


async def _order(client, token, item, phone=None, order_type="takeaway") -> dict:
    body = {"order_type": order_type,
            "items": [{"menu_item_id": str(item.id), "name": item.name, "quantity": 1,
                       "unit_price": item.price}]}
    if phone:
        body["customer_name"] = "Ali"
        body["customer_phone"] = phone
    r = await client.post("/api/v1/orders", json=body, headers=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()


async def _pay(client, token, order: dict) -> None:
    r = await client.post("/api/v1/payments", headers=_auth(token), json={
        "order_id": order["id"], "method_code": "cash", "amount": order["total"],
        "tendered_amount": order["total"]})
    assert r.status_code == 201, r.text


async def _visits(db, tenant) -> int:
    return (await db.execute(select(func.count(LoyaltyVisit.id)).where(
        LoyaltyVisit.tenant_id == tenant.id))).scalar_one()


async def _code(db, order_id) -> str:
    from app.models.order import Order

    return (await db.execute(select(Order.loyalty_code).where(
        Order.id == uuid.UUID(order_id)))).scalar_one()


# --- off by default --------------------------------------------------------------

@pytest.mark.asyncio
async def test_off_means_no_code_and_no_visit(client, admin_token, db, tenant, menu):
    await _config(db, tenant, menu, enabled=False)
    o = await _order(client, admin_token, menu["karahi"], PHONE)
    await _pay(client, admin_token, o)
    assert await _code(db, o["id"]) is None
    assert await _visits(db, tenant) == 0


# --- cashier route -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_paid_bill_with_phone_counts_one_visit(client, admin_token, db, tenant, menu):
    await _config(db, tenant, menu)
    o = await _order(client, admin_token, menu["karahi"], "+92 300 1234567")
    assert len(await _code(db, o["id"])) == 10
    assert await _visits(db, tenant) == 0  # not paid yet
    await _pay(client, admin_token, o)
    assert await _visits(db, tenant) == 1
    r = await client.get(f"/api/v1/loyalty/customers/{PHONE}", headers=_auth(admin_token))
    p = r.json()
    assert (p["total_visits"], p["toward_next"], p["rewards_available"]) == (1, 1, 0)
    assert p["reward_label"] == "Free Cappuccino"


@pytest.mark.asyncio
async def test_walk_in_never_counts(client, admin_token, db, tenant, menu):
    await _config(db, tenant, menu)
    o = await _order(client, admin_token, menu["karahi"])
    await _pay(client, admin_token, o)
    assert await _visits(db, tenant) == 0


@pytest.mark.asyncio
async def test_second_bill_same_day_does_not_count(client, admin_token, db, tenant, menu):
    await _config(db, tenant, menu)
    for _ in range(2):
        o = await _order(client, admin_token, menu["karahi"], PHONE)
        await _pay(client, admin_token, o)
    assert await _visits(db, tenant) == 1


@pytest.mark.asyncio
async def test_daily_limit_is_the_owners_setting(client, admin_token, db, tenant, menu):
    cfg = await _config(db, tenant, menu, per_day=2)
    for _ in range(3):
        o = await _order(client, admin_token, menu["karahi"], PHONE)
        await _pay(client, admin_token, o)
    assert await _visits(db, tenant) == 2  # third bill over the limit

    cfg.loyalty_max_visits_per_day = 0  # no limit
    await db.commit()
    o = await _order(client, admin_token, menu["karahi"], PHONE)
    await _pay(client, admin_token, o)
    assert await _visits(db, tenant) == 3


@pytest.mark.asyncio
async def test_qr_claim_over_the_daily_limit(client, admin_token, db, tenant, menu):
    await _config(db, tenant, menu)
    first = await _order(client, admin_token, menu["karahi"], PHONE)
    await _pay(client, admin_token, first)
    o = await _order(client, admin_token, menu["karahi"])  # no phone at the till
    await _pay(client, admin_token, o)
    r = await client.post(f"/api/v1/public/loyalty/{await _code(db, o['id'])}",
                          json={"phone": PHONE, "consent": True})
    assert r.status_code == 200, r.text
    assert (r.json()["result"], r.json()["total_visits"]) == ("daily_limit", 1)
    assert await _visits(db, tenant) == 1


@pytest.mark.asyncio
async def test_phone_bill_over_the_limit_is_not_claimable_by_anyone_else(
        client, admin_token, db, tenant, menu):
    """The walk's failure: a regular's second bill of the day (limit 1) was left
    unclaimed, went up on the counter screen, and the next person could take it."""
    await _config(db, tenant, menu)
    for _ in range(2):
        o = await _order(client, admin_token, menu["karahi"], PHONE)
        await _pay(client, admin_token, o)
    assert await _visits(db, tenant) == 1
    code = await _code(db, o["id"])
    assert (await client.get(f"/api/v1/public/loyalty/{code}")).json()["status"] == "linked"
    r = await client.post(f"/api/v1/public/loyalty/{code}",
                          json={"phone": "03119998888", "consent": True})
    assert r.status_code == 400 and "linked" in r.json()["detail"]
    assert await _visits(db, tenant) == 1
    assert (await client.get("/api/v1/loyalty/display?idle=1", headers=_auth(admin_token))).json()["loyalty_code"] is None


# --- QR route ------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_qr_claim_flow(client, admin_token, db, tenant, menu):
    await _config(db, tenant, menu)
    o = await _order(client, admin_token, menu["karahi"])  # no phone at the till
    code = await _code(db, o["id"])

    info = (await client.get(f"/api/v1/public/loyalty/{code}")).json()
    assert info["status"] == "unpaid" and info["reward_label"] == "Free Cappuccino"
    early = await client.post(f"/api/v1/public/loyalty/{code}",
                              json={"phone": PHONE, "consent": True})
    assert early.status_code == 400  # not paid yet

    await _pay(client, admin_token, o)
    assert (await client.get(f"/api/v1/public/loyalty/{code}")).json()["status"] == "open"

    no_consent = await client.post(f"/api/v1/public/loyalty/{code}",
                                   json={"phone": PHONE, "consent": False})
    assert no_consent.status_code == 400

    r = await client.post(f"/api/v1/public/loyalty/{code.lower()}",
                          json={"phone": PHONE, "name": "Sara", "consent": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["total_visits"], body["toward_next"], body["visits_required"]) == (1, 1, 5)
    assert "*" in body["phone"] and PHONE not in str(body)

    again = await client.post(f"/api/v1/public/loyalty/{code}",
                              json={"phone": "03119998888", "consent": True})
    assert again.status_code == 400  # one visit per bill
    assert (await client.get(f"/api/v1/public/loyalty/{code}")).json()["status"] == "counted"
    assert await _visits(db, tenant) == 1
    cust = (await db.execute(select(Customer).where(Customer.phone == PHONE))).scalar_one()
    assert cust.name == "Sara"


@pytest.mark.asyncio
async def test_cashier_then_qr_cannot_double_count(client, admin_token, db, tenant, menu):
    await _config(db, tenant, menu)
    o = await _order(client, admin_token, menu["karahi"], PHONE)
    await _pay(client, admin_token, o)
    code = await _code(db, o["id"])
    r = await client.post(f"/api/v1/public/loyalty/{code}", json={"phone": PHONE, "consent": True})
    assert r.status_code == 400
    assert await _visits(db, tenant) == 1


@pytest.mark.asyncio
async def test_bad_code_and_bad_phone(client, admin_token, db, tenant, menu):
    await _config(db, tenant, menu)
    assert (await client.get("/api/v1/public/loyalty/NOPE123456")).status_code == 404
    o = await _order(client, admin_token, menu["karahi"])
    await _pay(client, admin_token, o)
    code = await _code(db, o["id"])
    r = await client.post(f"/api/v1/public/loyalty/{code}", json={"phone": "12345678", "consent": True})
    assert r.status_code == 400


# --- rewards -------------------------------------------------------------------------

async def _five_past_visits(db, tenant, menu, client, token) -> None:
    """Five paid visits on five earlier days."""
    for d in range(5):
        o = await _order(client, token, menu["karahi"], PHONE)
        await _pay(client, token, o)
        await db.execute(
            LoyaltyVisit.__table__.update()
            .where(LoyaltyVisit.order_id == uuid.UUID(o["id"]))
            .values(visit_date=date.today() - timedelta(days=10 - d)))
        await db.commit()


@pytest.mark.asyncio
async def test_redeem_after_five_visits(client, admin_token, db, tenant, menu):
    await _config(db, tenant, menu)
    await _five_past_visits(db, tenant, menu, client, admin_token)

    o = await _order(client, admin_token, menu["coffee"], PHONE)
    st = (await client.get(f"/api/v1/loyalty/orders/{o['id']}", headers=_auth(admin_token))).json()
    assert st["can_redeem"] is True and st["progress"]["rewards_available"] == 1

    r = await client.post(f"/api/v1/loyalty/orders/{o['id']}/redeem", headers=_auth(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["rewards_available"] == 0

    after = (await client.get(f"/api/v1/orders/{o['id']}", headers=_auth(admin_token))).json()
    assert after["discount_amount"] == 79900
    assert after["total"] == o["total"] - 79900

    twice = await client.post(f"/api/v1/loyalty/orders/{o['id']}/redeem", headers=_auth(admin_token))
    assert twice.status_code == 400


@pytest.mark.asyncio
async def test_no_redeem_without_reward_item_or_visits(client, admin_token, db, tenant, menu):
    await _config(db, tenant, menu)
    o = await _order(client, admin_token, menu["coffee"], PHONE)
    r = await client.post(f"/api/v1/loyalty/orders/{o['id']}/redeem", headers=_auth(admin_token))
    assert r.status_code == 400  # no visits yet

    await _five_past_visits(db, tenant, menu, client, admin_token)
    k = await _order(client, admin_token, menu["karahi"], PHONE)  # no coffee on the bill
    r = await client.post(f"/api/v1/loyalty/orders/{k['id']}/redeem", headers=_auth(admin_token))
    assert r.status_code == 400 and "reward item" in r.json()["detail"]


# --- counter display and admin ----------------------------------------------------------

@pytest.mark.asyncio
async def test_counter_display_shows_newest_unclaimed_paid_bill(client, admin_token, db, tenant, menu):
    await _config(db, tenant, menu)
    assert (await client.get("/api/v1/loyalty/display?idle=1", headers=_auth(admin_token))).json()["loyalty_code"] is None
    o = await _order(client, admin_token, menu["karahi"])
    await _pay(client, admin_token, o)
    shown = (await client.get("/api/v1/loyalty/display?idle=1", headers=_auth(admin_token))).json()
    assert shown["loyalty_code"] == await _code(db, o["id"])
    await client.post(f"/api/v1/public/loyalty/{shown['loyalty_code']}",
                      json={"phone": PHONE, "consent": True})
    assert (await client.get("/api/v1/loyalty/display?idle=1", headers=_auth(admin_token))).json()["loyalty_code"] is None


@pytest.mark.asyncio
async def test_counter_display_never_falls_back_to_an_older_bill(client, admin_token, db, tenant, menu):
    from app.models.payment import Payment

    await _config(db, tenant, menu)
    older = await _order(client, admin_token, menu["karahi"])
    await _pay(client, admin_token, older)
    # Paid a minute earlier (SQLite timestamps tie within a second).
    await db.execute(Payment.__table__.update()
                     .where(Payment.order_id == uuid.UUID(older["id"]))
                     .values(created_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
    await db.commit()
    newer = await _order(client, admin_token, menu["karahi"])
    await _pay(client, admin_token, newer)
    shown = (await client.get("/api/v1/loyalty/display?idle=1", headers=_auth(admin_token))).json()
    assert shown["loyalty_code"] == await _code(db, newer["id"])
    await client.post(f"/api/v1/public/loyalty/{shown['loyalty_code']}",
                      json={"phone": PHONE, "consent": True})
    # The older bill is still unclaimed, but its customer has gone: blank screen.
    assert (await client.get("/api/v1/loyalty/display?idle=1", headers=_auth(admin_token))).json()["loyalty_code"] is None


@pytest.mark.asyncio
async def test_settings_and_members(client, admin_token, db, tenant, menu):
    await _config(db, tenant, menu, enabled=False)
    r = await client.patch("/api/v1/config/restaurant", headers=_auth(admin_token), json={
        "loyalty_enabled": True, "loyalty_visits_required": 6,
        "loyalty_reward_menu_item_id": str(menu["coffee"].id)})
    assert r.status_code == 200, r.text
    assert (r.json()["loyalty_enabled"], r.json()["loyalty_visits_required"]) == (True, 6)
    bad = await client.patch("/api/v1/config/restaurant", headers=_auth(admin_token),
                             json={"loyalty_reward_menu_item_id": str(uuid.uuid4())})
    assert bad.status_code == 422
    r = await client.patch("/api/v1/config/restaurant", headers=_auth(admin_token),
                           json={"loyalty_max_visits_per_day": 0})
    assert r.status_code == 200 and r.json()["loyalty_max_visits_per_day"] == 0
    assert (await client.patch("/api/v1/config/restaurant", headers=_auth(admin_token),
                               json={"loyalty_max_visits_per_day": -1})).status_code == 422

    o = await _order(client, admin_token, menu["karahi"], PHONE)
    await _pay(client, admin_token, o)
    m = (await client.get("/api/v1/loyalty/members", headers=_auth(admin_token))).json()
    assert len(m) == 1 and m[0]["total_visits"] == 1 and m[0]["visits_required"] == 6


# --- customer-facing polish (D-106, D-107) -----------------------------------------------

@pytest.mark.asyncio
async def test_idle_counter_screen_still_explains_the_card(client, admin_token, db, tenant, menu):
    cfg = await _config(db, tenant, menu)
    idle = (await client.get("/api/v1/loyalty/display?idle=1", headers=_auth(admin_token))).json()
    assert idle == {"loyalty_code": None, "order_number": None, "total": None,
                    "reward_label": "Free Cappuccino", "visits_required": 5}
    # Without idle=1 (a counter page still on the old bundle) idle stays null, or
    # that page would read the object as a bill and show a QR for "null".
    assert (await client.get("/api/v1/loyalty/display", headers=_auth(admin_token))).json() is None
    o = await _order(client, admin_token, menu["karahi"])
    await _pay(client, admin_token, o)
    plain = (await client.get("/api/v1/loyalty/display", headers=_auth(admin_token))).json()
    assert plain["loyalty_code"] == await _code(db, o["id"])
    cfg.loyalty_enabled = False
    await db.commit()
    assert (await client.get("/api/v1/loyalty/display?idle=1", headers=_auth(admin_token))).json() is None


@pytest.mark.asyncio
async def test_claim_page_knows_the_shop_for_its_logo(client, admin_token, db, tenant, menu):
    await _config(db, tenant, menu)
    o = await _order(client, admin_token, menu["karahi"])
    info = (await client.get(f"/api/v1/public/loyalty/{await _code(db, o['id'])}")).json()
    assert info["tenant_slug"] == tenant.slug


@pytest.mark.asyncio
async def test_google_review_link_setting(client, admin_token, db, tenant, menu):
    await _config(db, tenant, menu)
    url = "https://www.google.com/maps?cid=2858650049585319157"
    r = await client.patch("/api/v1/config/restaurant", headers=_auth(admin_token),
                           json={"google_review_url": f"  {url} "})
    assert r.status_code == 200 and r.json()["google_review_url"] == url
    # Setting the link never opts the restaurant into the review email.
    assert r.json()["review_email_enabled"] is False
    r = await client.patch("/api/v1/config/restaurant", headers=_auth(admin_token),
                           json={"review_email_enabled": True})
    assert r.status_code == 200 and r.json()["review_email_enabled"] is True
    assert r.json()["google_review_url"] == url
    bad = await client.patch("/api/v1/config/restaurant", headers=_auth(admin_token),
                             json={"google_review_url": "http://example.com"})
    assert bad.status_code == 422
    r = await client.patch("/api/v1/config/restaurant", headers=_auth(admin_token),
                           json={"google_review_url": ""})
    assert r.status_code == 200 and r.json()["google_review_url"] is None
