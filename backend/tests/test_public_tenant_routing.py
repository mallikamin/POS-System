"""Tenant routing on the public storefront routes, and the merchant queue.

Why this file exists
--------------------
`public.py` used to resolve the storefront's tenant with

    SELECT id FROM tenants WHERE is_active LIMIT 1

There is no ORDER BY in that query, so with more than one active tenant it
returns an arbitrary row. This deployment already carries several
(`demo-restaurant`, `yk-online`, `yk-desktop`, `chick-shack`), which meant a UK
storefront could have been served a Pakistani menu priced in rupees -- or worse,
had a customer's order written against another restaurant's books.

Every test below that involves two tenants exists to keep that from coming back.
The single-tenant tests would all have passed against the broken version, so they
are not the point; the cross-tenant ones are.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu import Category, MenuItem
from app.models.order import Order
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.models.user import Role, User

pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


QUEUE_URL = "/api/v1/public/manage/orders"


# ---------------------------------------------------------------------------
# Fixtures -- a menu for each of the two tenants, with distinguishable items
# ---------------------------------------------------------------------------


async def _make_menu(
    db: AsyncSession, tenant_id: uuid.UUID, item_name: str, price: int
) -> MenuItem:
    category = Category(
        tenant_id=tenant_id, name=f"{item_name} Category", display_order=1
    )
    db.add(category)
    await db.flush()

    item = MenuItem(
        tenant_id=tenant_id,
        category_id=category.id,
        name=item_name,
        price=price,
        is_available=True,
    )
    db.add(item)
    await db.commit()
    return item


@pytest_asyncio.fixture
async def uk_menu(db: AsyncSession, tenant: Tenant, admin_role: Role) -> MenuItem:
    """A fully orderable tenant: config, at least one role, and an item.

    `admin_role` is not incidental. `create_public_order` attaches its orders to
    a dedicated non-login user, and creating that user needs some active role to
    hang it on -- without one every order fails with "Restaurant is not
    configured to take online orders". A cross-tenant test asserting 409 would
    then pass whether or not cross-tenant ordering was actually blocked.
    """
    db.add(RestaurantConfig(tenant_id=tenant.id, currency="GBP"))
    await db.flush()
    return await _make_menu(db, tenant.id, "Peri Peri Half Chicken", 850)


@pytest_asyncio.fixture
async def pk_menu(db: AsyncSession, other_tenant: Tenant) -> MenuItem:
    db.add(RestaurantConfig(tenant_id=other_tenant.id, currency="PKR"))
    await db.flush()
    return await _make_menu(db, other_tenant.id, "Chicken Karahi", 145000)


# ---------------------------------------------------------------------------
# Slug resolution
# ---------------------------------------------------------------------------


async def test_menu_is_served_for_a_known_slug(
    client: AsyncClient, uk_menu: MenuItem
):
    resp = await client.get("/api/v1/public/test-restaurant/menu")
    assert resp.status_code == 200
    names = [i["name"] for c in resp.json()["categories"] for i in c["items"]]
    assert "Peri Peri Half Chicken" in names


async def test_unknown_slug_is_404(client: AsyncClient, uk_menu: MenuItem):
    resp = await client.get("/api/v1/public/no-such-restaurant/menu")
    assert resp.status_code == 404


@pytest.mark.parametrize("slug", ["manage", "orders", "menu", "health"])
async def test_reserved_slugs_are_refused(
    client: AsyncClient, uk_menu: MenuItem, slug: str
):
    """A tenant slugged `manage` would make /public/manage/orders ambiguous."""
    resp = await client.get(f"/api/v1/public/{slug}/menu")
    assert resp.status_code == 404


async def test_inactive_tenant_is_404(
    client: AsyncClient, db: AsyncSession, tenant: Tenant, uk_menu: MenuItem
):
    tenant.is_active = False
    await db.commit()

    resp = await client.get("/api/v1/public/test-restaurant/menu")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# The cross-tenant tests -- the actual reason this file exists
# ---------------------------------------------------------------------------


async def test_each_slug_gets_only_its_own_menu(
    client: AsyncClient, uk_menu: MenuItem, pk_menu: MenuItem
):
    """Two active tenants, two menus, no bleed in either direction.

    Against the old `LIMIT 1` resolver one of these two assertions was a coin
    toss decided by Postgres' physical row order.
    """
    uk = await client.get("/api/v1/public/test-restaurant/menu")
    pk = await client.get("/api/v1/public/other-restaurant/menu")
    assert uk.status_code == 200 and pk.status_code == 200

    uk_names = [i["name"] for c in uk.json()["categories"] for i in c["items"]]
    pk_names = [i["name"] for c in pk.json()["categories"] for i in c["items"]]

    assert "Peri Peri Half Chicken" in uk_names
    assert "Chicken Karahi" not in uk_names
    assert "Chicken Karahi" in pk_names
    assert "Peri Peri Half Chicken" not in pk_names


async def test_currency_follows_the_slug_not_the_first_row(
    client: AsyncClient, uk_menu: MenuItem, pk_menu: MenuItem
):
    """The failure this guards is a UK customer shown prices in rupees."""
    uk = await client.get("/api/v1/public/test-restaurant/menu")
    pk = await client.get("/api/v1/public/other-restaurant/menu")

    assert uk.json()["currency"] == "GBP"
    assert pk.json()["currency"] == "PKR"


async def test_order_is_written_to_the_tenant_named_in_the_path(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    uk_menu: MenuItem,
    pk_menu: MenuItem,
):
    """An order placed on one storefront must never land on another's books."""
    resp = await client.post(
        "/api/v1/public/test-restaurant/orders",
        json={
            "service_type": "collection",
            "customer_name": "Imran R",
            "customer_phone": "07909313456",
            "items": [{"menu_item_id": str(uk_menu.id), "quantity": 1}],
        },
    )
    assert resp.status_code == 201, resp.text

    order = await db.get(Order, uuid.UUID(resp.json()["id"]))
    assert order is not None
    assert order.tenant_id == tenant.id


async def _set_paused(db: AsyncSession, tenant_id, paused: bool) -> None:
    await db.execute(
        RestaurantConfig.__table__.update()
        .where(RestaurantConfig.tenant_id == tenant_id)
        .values(online_ordering_paused=paused)
    )
    await db.commit()


async def test_a_paused_shop_refuses_the_order_and_writes_nothing(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    uk_menu: MenuItem,
):
    """Imran's rush button (2026-08-04). THE guarantee: while it is on, a
    customer cannot place an order -- and no half-order is left behind for the
    shop to trip over.

    Enforced on the endpoint, not merely hidden in the storefront: a stale
    browser tab, a bookmarked checkout or a direct POST must all be refused.
    That is the lesson from OI-61/OI-65 -- a client-side check is a suggestion.
    """
    before = (await db.execute(select(func.count(Order.id)))).scalar_one()
    await _set_paused(db, tenant.id, True)

    resp = await client.post(
        "/api/v1/public/test-restaurant/orders",
        json={
            "service_type": "collection",
            "customer_name": "Imran R",
            "customer_phone": "07909313456",
            "items": [{"menu_item_id": str(uk_menu.id), "quantity": 1}],
        },
    )

    assert resp.status_code == 503, resp.text
    assert "07719 566 889" in resp.json()["detail"]
    after = (await db.execute(select(func.count(Order.id)))).scalar_one()
    assert after == before, "a paused shop must not create an order row at all"


async def test_resuming_lets_orders_through_again(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    uk_menu: MenuItem,
):
    """The resume half has to work as cleanly as the pause half."""
    await _set_paused(db, tenant.id, True)
    await _set_paused(db, tenant.id, False)

    resp = await client.post(
        "/api/v1/public/test-restaurant/orders",
        json={
            "service_type": "collection",
            "customer_name": "Imran R",
            "customer_phone": "07909313456",
            "items": [{"menu_item_id": str(uk_menu.id), "quantity": 1}],
        },
    )
    assert resp.status_code == 201, resp.text


async def test_the_menu_tells_the_storefront_it_is_paused(
    client: AsyncClient, db: AsyncSession, tenant: Tenant, uk_menu: MenuItem
):
    """So the customer sees Imran's wording instead of a dead button."""
    live = await client.get("/api/v1/public/test-restaurant/menu")
    assert live.json()["ordering_paused"] is False
    assert live.json()["ordering_paused_message"] is None

    await _set_paused(db, tenant.id, True)
    paused = await client.get("/api/v1/public/test-restaurant/menu")
    assert paused.json()["ordering_paused"] is True
    assert "07719 566 889" in paused.json()["ordering_paused_message"]


async def test_pausing_is_per_tenant_and_cannot_close_another_shop(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    uk_menu: MenuItem,
    pk_menu: MenuItem,
):
    """One tenant's rush must never close another tenant's storefront.

    Asserted on the menu flag rather than by placing an order, because the
    `pk_menu` fixture deliberately has no role for its tenant (see `uk_menu`'s
    docstring) and so cannot place orders for unrelated reasons -- an order
    assertion here would pass whether or not pausing were tenant-scoped.
    """
    await _set_paused(db, tenant.id, True)

    other = await client.get("/api/v1/public/other-restaurant/menu")
    assert other.json()["ordering_paused"] is False
    assert other.json()["ordering_paused_message"] is None

    # ...and the paused one really is paused, so this is a genuine comparison.
    mine = await client.get("/api/v1/public/test-restaurant/menu")
    assert mine.json()["ordering_paused"] is True


async def test_online_order_numbers_carry_the_collection_delivery_letter(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    uk_menu: MenuItem,
):
    """Imran, 2026-08-04: `260804-C001` collection, `260804-D002` delivery.

    ONE shared counter -- the letter marks the category, it does not start a
    separate sequence -- so the numbers stay easy to track in order.
    """
    resp = await client.post(
        "/api/v1/public/test-restaurant/orders",
        json={
            "service_type": "collection",
            "customer_name": "Imran R",
            "customer_phone": "07909313456",
            "items": [{"menu_item_id": str(uk_menu.id), "quantity": 1}],
        },
    )
    assert resp.status_code == 201, resp.text
    first = resp.json()["order_number"]
    assert "-C" in first, first
    assert first.split("-C")[1] == "001"


async def test_the_counter_is_shared_across_collection_and_delivery(
    db: AsyncSession, tenant: Tenant, admin_user: User, uk_menu: MenuItem
):
    """ONE counter, not one per letter.

    The number is allocated from the highest already issued today with the
    letter stripped, so a delivery order following a collection order gets the
    NEXT number, never a second `001`.

    Deriving it from `count(*)` instead was the bug Malik caught: `-C006` and
    `-D006` are different strings, so even the unique constraint on
    order_number could not catch the collision, and the shared counter forked.
    """
    from app.services.order_service import generate_order_number

    today = datetime.now(timezone.utc).strftime("%y%m%d")

    assert await generate_order_number(db, tenant.id, "collection") == f"{today}-C001"

    await _online_order(db, tenant.id, admin_user.id, f"{today}-C001")
    assert await generate_order_number(db, tenant.id, "delivery") == f"{today}-D002"

    await _online_order(db, tenant.id, admin_user.id, f"{today}-D002")
    assert await generate_order_number(db, tenant.id, "collection") == f"{today}-C003"

    # A number is never re-issued after a row is removed -- it may already be
    # printed on a receipt. `count(*)` would have rewound to 002 here.
    await _online_order(db, tenant.id, admin_user.id, f"{today}-C003")
    order = (
        await db.execute(
            select(Order).where(Order.order_number == f"{today}-D002")
        )
    ).scalar_one()
    await db.delete(order)
    await db.commit()
    assert await generate_order_number(db, tenant.id, "delivery") == f"{today}-D004"


async def test_till_orders_keep_the_plain_number_and_share_the_same_counter(
    db: AsyncSession, tenant: Tenant, admin_user: User, uk_menu: MenuItem
):
    """Dine-in/takeaway/call-centre pass no service_type and stay `YYMMDD-NNN`,
    but draw from the same daily sequence as the online ones."""
    from app.services.order_service import generate_order_number

    today = datetime.now(timezone.utc).strftime("%y%m%d")
    await _online_order(db, tenant.id, admin_user.id, f"{today}-C001")

    assert await generate_order_number(db, tenant.id) == f"{today}-002"


async def test_service_fee_is_snapshotted_onto_the_order_from_tenant_config(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    uk_menu: MenuItem,
):
    """Imran, voice note 2026-08-02: a flat per-order fee, all orders. Modelled
    on `restaurant_configs` (0 for every tenant but the one that charges it)
    and snapshotted onto the order at creation, same pattern as delivery_fee.
    """
    await db.execute(
        RestaurantConfig.__table__.update()
        .where(RestaurantConfig.tenant_id == tenant.id)
        .values(service_fee=70)
    )
    await db.commit()

    resp = await client.post(
        "/api/v1/public/test-restaurant/orders",
        json={
            "service_type": "collection",
            "customer_name": "Imran R",
            "customer_phone": "07909313456",
            "items": [{"menu_item_id": str(uk_menu.id), "quantity": 1}],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["service_fee"] == 70
    assert body["total"] == body["subtotal"] + body["tax_amount"] + body["service_fee"]

    order = await db.get(Order, uuid.UUID(body["id"]))
    assert order.service_fee == 70


async def test_zero_service_fee_tenant_is_unaffected(
    client: AsyncClient,
    uk_menu: MenuItem,
):
    """`uk_menu`'s config never sets `service_fee` -- confirms the 0-default
    doesn't silently add a fee for every other tenant."""
    resp = await client.post(
        "/api/v1/public/test-restaurant/orders",
        json={
            "service_type": "collection",
            "customer_name": "Imran R",
            "customer_phone": "07909313456",
            "items": [{"menu_item_id": str(uk_menu.id), "quantity": 1}],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["service_fee"] == 0
    assert body["total"] == body["subtotal"] + body["tax_amount"]


# ---------------------------------------------------------------------------
# OI-81: the tip -- the one client-sent amount on an order
# ---------------------------------------------------------------------------


async def test_tip_is_added_to_the_total_and_snapshotted(
    client: AsyncClient,
    db: AsyncSession,
    uk_menu: MenuItem,
):
    """A £3.50 tip lands in the total (Imran's own worked example: £25.75 +
    £3.50 charges £29.25) and is snapshotted onto the order like service_fee,
    so nothing can rewrite it later. Tax is charged on goods only, never on
    the tip."""
    resp = await client.post(
        "/api/v1/public/test-restaurant/orders",
        json={
            "service_type": "collection",
            "customer_name": "Imran R",
            "customer_phone": "07909313456",
            "items": [{"menu_item_id": str(uk_menu.id), "quantity": 1}],
            "tip": 350,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["tip"] == 350
    assert body["total"] == body["subtotal"] + body["tax_amount"] + 350

    order = await db.get(Order, uuid.UUID(body["id"]))
    assert order.tip == 350
    assert order.total == body["total"]


async def test_no_tip_sent_means_zero_not_an_error(
    client: AsyncClient,
    uk_menu: MenuItem,
):
    """Every basket placed by the pre-tip storefront bundle sends no `tip`
    key at all -- that must keep working unchanged forever."""
    resp = await client.post(
        "/api/v1/public/test-restaurant/orders",
        json={
            "service_type": "collection",
            "customer_name": "Imran R",
            "customer_phone": "07909313456",
            "items": [{"menu_item_id": str(uk_menu.id), "quantity": 1}],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["tip"] == 0
    assert body["total"] == body["subtotal"] + body["tax_amount"]


@pytest.mark.parametrize("bad_tip", [-1, 2001, 100000])
async def test_out_of_range_tip_is_rejected(
    client: AsyncClient,
    uk_menu: MenuItem,
    bad_tip: int,
):
    """The £20 cap is the server's, not the browser's: a fat-fingered "350"
    instead of "3.50" must never become a real card charge, whatever a
    tampered client sends."""
    resp = await client.post(
        "/api/v1/public/test-restaurant/orders",
        json={
            "service_type": "collection",
            "customer_name": "Imran R",
            "customer_phone": "07909313456",
            "items": [{"menu_item_id": str(uk_menu.id), "quantity": 1}],
            "tip": bad_tip,
        },
    )
    assert resp.status_code == 422


async def test_cannot_order_another_tenants_item_through_your_slug(
    client: AsyncClient, uk_menu: MenuItem, pk_menu: MenuItem
):
    """Posting a valid item ID belonging to a different tenant must fail.

    Menu item IDs are UUIDs and the public menu exposes them, so this is a
    reachable request, not a theoretical one.
    """
    resp = await client.post(
        "/api/v1/public/test-restaurant/orders",
        json={
            "service_type": "collection",
            "customer_name": "Imran R",
            "customer_phone": "07909313456",
            "items": [{"menu_item_id": str(pk_menu.id), "quantity": 1}],
        },
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# The merchant queue -- what the shop's tablet polls
# ---------------------------------------------------------------------------


async def _online_order(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    number: str,
    *,
    minutes_ago: int = 0,
    days_ago: int = 0,
    accepted: bool = False,
    rejected: bool = False,
    stripe_checkout_session_id: str | None = None,
    payment_authorized_at: datetime | None = None,
) -> Order:
    now = datetime.now(timezone.utc)
    placed_at = now - timedelta(minutes=minutes_ago, days=days_ago)
    order = Order(
        tenant_id=tenant_id,
        order_number=number,
        order_type="online",
        status="voided" if rejected else ("in_kitchen" if accepted else "confirmed"),
        payment_status="unpaid",
        customer_name="Imran R",
        customer_phone="07909313456",
        subtotal=850,
        tax_amount=0,
        discount_amount=0,
        delivery_fee=300,
        total=1150,
        service_type="delivery",
        delivery_address="12 Feorlin Way",
        delivery_area="Garelochhead",
        created_by=user_id,
        created_at=placed_at,
        accepted_at=placed_at if accepted else None,
        rejected_at=placed_at if rejected else None,
        eta_minutes=30 if accepted else None,
        stripe_checkout_session_id=stripe_checkout_session_id,
        payment_authorized_at=payment_authorized_at,
    )
    db.add(order)
    await db.commit()
    return order


async def test_queue_requires_authentication(client: AsyncClient):
    """It is a list of names, phone numbers and home addresses."""
    resp = await client.get(QUEUE_URL)
    assert resp.status_code in (401, 403)


async def test_queue_returns_only_the_callers_tenant(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    other_tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    await _online_order(db, tenant.id, admin_user.id, "260728-001")
    await _online_order(db, other_tenant.id, admin_user.id, "260728-999")

    resp = await client.get(QUEUE_URL, headers=_auth(admin_token))
    assert resp.status_code == 200

    numbers = [o["order_number"] for o in resp.json()["orders"]]
    assert numbers == ["260728-001"]


async def test_pending_excludes_accepted_and_rejected(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    await _online_order(db, tenant.id, admin_user.id, "260728-001")
    await _online_order(db, tenant.id, admin_user.id, "260728-002", accepted=True)
    await _online_order(db, tenant.id, admin_user.id, "260728-003", rejected=True)

    resp = await client.get(QUEUE_URL, headers=_auth(admin_token))
    numbers = [o["order_number"] for o in resp.json()["orders"]]
    assert numbers == ["260728-001"]


# ---------------------------------------------------------------------------
# OI-61 -- a card order isn't offered to staff as a decision until Stripe has
# actually confirmed the authorisation. Structural fix for the race that let
# staff accept (and, on 2026-08-02, double-charge a customer for) an order
# before its payment had landed: if it can't be seen, it can't be acted on
# too early.
# ---------------------------------------------------------------------------


async def test_unauthorised_card_order_is_kept_off_the_pending_queue(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    await _online_order(
        db,
        tenant.id,
        admin_user.id,
        "260803-card-pending",
        stripe_checkout_session_id="cs_test_1",
        payment_authorized_at=None,
    )
    resp = await client.get(QUEUE_URL, headers=_auth(admin_token))
    numbers = [o["order_number"] for o in resp.json()["orders"]]
    assert numbers == []


async def test_authorised_card_order_is_offered_normally(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    await _online_order(
        db,
        tenant.id,
        admin_user.id,
        "260803-card-authorised",
        stripe_checkout_session_id="cs_test_2",
        payment_authorized_at=datetime.now(timezone.utc),
    )
    resp = await client.get(QUEUE_URL, headers=_auth(admin_token))
    numbers = [o["order_number"] for o in resp.json()["orders"]]
    assert numbers == ["260803-card-authorised"]


async def test_cash_order_is_unaffected_by_the_card_payment_gate(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    await _online_order(db, tenant.id, admin_user.id, "260803-cash")
    resp = await client.get(QUEUE_URL, headers=_auth(admin_token))
    numbers = [o["order_number"] for o in resp.json()["orders"]]
    assert numbers == ["260803-cash"]


async def test_an_unpaid_card_order_never_surfaces_however_old_it_gets(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    """OI-65: there is NO grace window. The payment is the only thing that publishes.

    This inverts OI-61's original behaviour deliberately. That version showed an
    unauthorised card order once 5 minutes had passed, so an abandoned checkout
    wouldn't be "lost" -- and production disproved the trade the next day: order
    260803-003 (2026-08-03) took 366s to authorise, the window expired, and the
    order became acceptable while the money was still unconfirmed.

    An abandoned checkout SHOULD be lost. Nobody paid, so there is nothing to
    cook. If the customer takes two hours, the order appears in two hours.
    """
    for age in (10, 6 * 60, 20 * 60):
        await _online_order(
            db,
            tenant.id,
            admin_user.id,
            f"260803-abandoned-{age}",
            minutes_ago=age,
            stripe_checkout_session_id=f"cs_test_{age}",
            payment_authorized_at=None,
        )
    resp = await client.get(QUEUE_URL, headers=_auth(admin_token))
    assert [o["order_number"] for o in resp.json()["orders"]] == []


async def test_an_unpaid_card_order_is_in_no_view_of_the_pos_at_all(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    """It is not in the POS. Not Pending, not Active, not All -- nowhere.

    OI-61 scoped this condition to `pending` only, so the "All" tab still
    listed unpaid card orders and still drew live Accept buttons on them. That
    is the route staff actually took on 2026-08-03 (order 260803-003). Gating
    one view and leaving another open is not a rule, so the gate now applies to
    every state and this test checks all three.
    """
    await _online_order(
        db,
        tenant.id,
        admin_user.id,
        "260803-unpaid-card",
        stripe_checkout_session_id="cs_test_all",
        payment_authorized_at=None,
    )
    for state in ("pending", "active", "all"):
        resp = await client.get(f"{QUEUE_URL}?state={state}", headers=_auth(admin_token))
        numbers = [o["order_number"] for o in resp.json()["orders"]]
        assert "260803-unpaid-card" not in numbers, f"leaked into state={state}"


async def test_an_already_answered_order_stays_visible_even_if_unauthorised(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    """The one deliberate exception to the gate.

    Hiding an order the kitchen is already cooking would be worse than showing
    it, and the log has to stay legible. Only reachable for rows answered
    before OI-65 shipped -- `accept_order` now refuses unconfirmed card orders.
    """
    await _online_order(
        db,
        tenant.id,
        admin_user.id,
        "260803-legacy-accepted",
        accepted=True,
        stripe_checkout_session_id="cs_test_legacy",
        payment_authorized_at=None,
    )
    resp = await client.get(f"{QUEUE_URL}?state=active", headers=_auth(admin_token))
    numbers = [o["order_number"] for o in resp.json()["orders"]]
    assert numbers == ["260803-legacy-accepted"]


async def test_a_cash_order_is_never_gated_in_any_view(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    """Cash on delivery has no payment to process, so it lands as-is."""
    await _online_order(db, tenant.id, admin_user.id, "260803-cash-flag")
    for state in ("pending", "all"):
        resp = await client.get(f"{QUEUE_URL}?state={state}", headers=_auth(admin_token))
        rows = {o["order_number"]: o for o in resp.json()["orders"]}
        assert "260803-cash-flag" in rows, f"cash order missing from state={state}"
        assert rows["260803-cash-flag"]["is_card_order"] is False


async def test_active_is_accepted_and_still_working(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    await _online_order(db, tenant.id, admin_user.id, "260728-001")
    await _online_order(db, tenant.id, admin_user.id, "260728-002", accepted=True)
    await _online_order(db, tenant.id, admin_user.id, "260728-003", rejected=True)

    resp = await client.get(
        QUEUE_URL, params={"state": "active"}, headers=_auth(admin_token)
    )
    numbers = [o["order_number"] for o in resp.json()["orders"]]
    assert numbers == ["260728-002"]


async def test_pending_is_oldest_first(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    """A work queue, not a log.

    The customer who has been waiting longest is the one who needs answering,
    so pending ascends by placement time while the other views descend.
    """
    await _online_order(db, tenant.id, admin_user.id, "260728-new", minutes_ago=1)
    await _online_order(db, tenant.id, admin_user.id, "260728-old", minutes_ago=20)

    resp = await client.get(QUEUE_URL, headers=_auth(admin_token))
    numbers = [o["order_number"] for o in resp.json()["orders"]]
    assert numbers == ["260728-old", "260728-new"]


async def test_queue_card_carries_what_the_shop_needs_to_work_the_order(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    """Phone, address and area -- the three fields the customer-facing
    response deliberately withholds and the shop cannot operate without."""
    await _online_order(db, tenant.id, admin_user.id, "260728-001")

    resp = await client.get(QUEUE_URL, headers=_auth(admin_token))
    card = resp.json()["orders"][0]

    assert card["customer_phone"] == "07909313456"
    assert card["delivery_address"] == "12 Feorlin Way"
    assert card["delivery_area"] == "Garelochhead"
    assert card["currency"] == "GBP"


# ---------------------------------------------------------------------------
# OI-57 -- date scoping, pagination, sort
# ---------------------------------------------------------------------------


async def test_pending_defaults_to_today_only(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    """The exact bug reported: a 3-day-old unaccepted order was polluting
    today's Pending tab with nothing to age it out."""
    await _online_order(db, tenant.id, admin_user.id, "260728-old", days_ago=3)
    await _online_order(db, tenant.id, admin_user.id, "260728-today")

    resp = await client.get(QUEUE_URL, headers=_auth(admin_token))
    body = resp.json()
    numbers = [o["order_number"] for o in body["orders"]]
    assert numbers == ["260728-today"]
    assert body["total_count"] == 1


async def test_active_also_defaults_to_today_only(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    await _online_order(
        db, tenant.id, admin_user.id, "260728-old", days_ago=3, accepted=True
    )
    await _online_order(
        db, tenant.id, admin_user.id, "260728-today", accepted=True
    )

    resp = await client.get(
        QUEUE_URL, params={"state": "active"}, headers=_auth(admin_token)
    )
    numbers = [o["order_number"] for o in resp.json()["orders"]]
    assert numbers == ["260728-today"]


async def test_all_stays_unscoped_without_a_date_range(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    """`all` is a browsable log -- it must keep showing old orders unless a
    date range explicitly narrows it, unlike Pending/Active."""
    await _online_order(db, tenant.id, admin_user.id, "260728-old", days_ago=3)
    await _online_order(db, tenant.id, admin_user.id, "260728-today")

    resp = await client.get(
        QUEUE_URL, params={"state": "all"}, headers=_auth(admin_token)
    )
    numbers = {o["order_number"] for o in resp.json()["orders"]}
    assert numbers == {"260728-old", "260728-today"}


async def test_explicit_date_reaches_a_past_days_pending_orders(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    old_order = await _online_order(
        db, tenant.id, admin_user.id, "260728-old", days_ago=3
    )
    await _online_order(db, tenant.id, admin_user.id, "260728-today")

    target_date = old_order.created_at.date().isoformat()
    resp = await client.get(
        QUEUE_URL, params={"date": target_date}, headers=_auth(admin_token)
    )
    numbers = [o["order_number"] for o in resp.json()["orders"]]
    assert numbers == ["260728-old"]


async def test_date_range_scopes_the_all_tab(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    old_order = await _online_order(
        db, tenant.id, admin_user.id, "260728-old", days_ago=3
    )
    await _online_order(db, tenant.id, admin_user.id, "260728-today")

    target_date = old_order.created_at.date().isoformat()
    resp = await client.get(
        QUEUE_URL,
        params={"state": "all", "date_from": target_date, "date_to": target_date},
        headers=_auth(admin_token),
    )
    numbers = [o["order_number"] for o in resp.json()["orders"]]
    assert numbers == ["260728-old"]


async def test_pagination_offset_and_total_count(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    for i in range(3):
        await _online_order(
            db, tenant.id, admin_user.id, f"260728-{i}", minutes_ago=(3 - i)
        )

    first_page = await client.get(
        QUEUE_URL,
        params={"state": "all", "limit": 2, "offset": 0},
        headers=_auth(admin_token),
    )
    body = first_page.json()
    assert body["total_count"] == 3
    assert body["count"] == 2
    assert body["offset"] == 0
    assert body["limit"] == 2

    second_page = await client.get(
        QUEUE_URL,
        params={"state": "all", "limit": 2, "offset": 2},
        headers=_auth(admin_token),
    )
    body2 = second_page.json()
    assert body2["total_count"] == 3
    assert body2["count"] == 1

    seen = [o["order_number"] for o in body["orders"]] + [
        o["order_number"] for o in body2["orders"]
    ]
    assert sorted(seen) == ["260728-0", "260728-1", "260728-2"]


async def test_sort_toggle_overrides_the_default_for_active_and_all(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    await _online_order(
        db, tenant.id, admin_user.id, "260728-new", minutes_ago=1, accepted=True
    )
    await _online_order(
        db, tenant.id, admin_user.id, "260728-old", minutes_ago=20, accepted=True
    )

    default_resp = await client.get(
        QUEUE_URL, params={"state": "active"}, headers=_auth(admin_token)
    )
    assert default_resp.json()["sort"] == "desc"
    default_numbers = [o["order_number"] for o in default_resp.json()["orders"]]
    assert default_numbers == ["260728-new", "260728-old"]

    asc_resp = await client.get(
        QUEUE_URL,
        params={"state": "active", "sort": "asc"},
        headers=_auth(admin_token),
    )
    assert asc_resp.json()["sort"] == "asc"
    asc_numbers = [o["order_number"] for o in asc_resp.json()["orders"]]
    assert asc_numbers == ["260728-old", "260728-new"]


async def test_pending_response_reports_its_default_sort(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    admin_token: str,
    uk_menu: MenuItem,
):
    resp = await client.get(QUEUE_URL, headers=_auth(admin_token))
    assert resp.json()["sort"] == "asc"


# ---------------------------------------------------------------------------
# OI-84: the card intent must be written by the order's own INSERT
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_card_order_records_the_intent_at_creation_and_stays_hidden(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_token: str,
    uk_menu: MenuItem,
):
    """The end-to-end shape of OI-84, through the real endpoint.

    Placing a card order is ONE request; the Stripe session is set by a second
    one afterwards. So at this exact moment `stripe_checkout_session_id` is
    still NULL, and before OI-84 that made the order indistinguishable from
    cash on delivery: it surfaced on the tablet and chimed, then vanished.

    Asserted here rather than only on a hand-built row, because the flag is set
    in `create_public_order` and nothing else would catch that line regressing.
    """
    resp = await client.post(
        "/api/v1/public/test-restaurant/orders",
        json={
            "service_type": "collection",
            "customer_name": "Card Customer",
            "customer_phone": "07909313456",
            "payment_method": "card",
            "items": [{"menu_item_id": str(uk_menu.id), "quantity": 1}],
        },
    )
    assert resp.status_code == 201, resp.text

    order = await db.get(Order, uuid.UUID(resp.json()["id"]))
    assert order is not None
    assert order.intends_card_payment is True
    assert order.stripe_checkout_session_id is None, (
        "the session is created by a later request; this test is worthless if "
        "that ever changes without the rest of OI-84 being revisited"
    )

    queue = await client.get(QUEUE_URL, headers=_auth(admin_token))
    assert resp.json()["id"] not in [o["id"] for o in queue.json()["orders"]]


@pytest.mark.asyncio
async def test_a_cash_order_records_no_card_intent_and_is_visible(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_token: str,
    uk_menu: MenuItem,
):
    """The other side of the same line, so a blanket `True` would fail."""
    resp = await client.post(
        "/api/v1/public/test-restaurant/orders",
        json={
            "service_type": "collection",
            "customer_name": "Cash Customer",
            "customer_phone": "07909313457",
            "payment_method": "cash",
            "items": [{"menu_item_id": str(uk_menu.id), "quantity": 1}],
        },
    )
    assert resp.status_code == 201, resp.text

    order = await db.get(Order, uuid.UUID(resp.json()["id"]))
    assert order is not None
    assert order.intends_card_payment is False

    queue = await client.get(QUEUE_URL, headers=_auth(admin_token))
    assert resp.json()["id"] in [o["id"] for o in queue.json()["orders"]]
