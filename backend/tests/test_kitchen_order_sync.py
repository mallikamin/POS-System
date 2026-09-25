"""The kitchen board and the order move together.

Danny's UAT, 2026-09-25 (D-21, D-13, D-28): the kitchen bumped a dine-in meal
to Served and the order stayed "In Kitchen" for ever. Paying it never completed
it, so its recipes never left stock, and the table was freed with the order
still open. The reverse was broken too: an order completed at the POS left its
ticket in NEW on the kitchen board.

These walk the same endpoints the screens call.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floor import Table
from app.models.inventory import Ingredient, InventoryTransaction, Recipe, RecipeItem
from app.models.kitchen import KitchenStation, KitchenTicket
from app.models.location import Location, LocationStock
from app.models.menu import Category, MenuItem
from app.models.order import Order
from app.models.tenant import Tenant
from app.models.user import Permission, Role, RolePermission, User
from app.services import stock_service


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def kitchen_setup(db: AsyncSession, tenant: Tenant, admin_role: Role):
    """A restaurant with one station, one site, and a karahi that uses 0.5 kg chicken."""
    site = Location(
        tenant_id=tenant.id, name="Restaurant", code="MAIN", location_type="retail",
        invoice_format="thermal_ticket", is_default=True,
    )
    station = KitchenStation(tenant_id=tenant.id, name="Main Kitchen", display_order=0, is_active=True)
    chicken = Ingredient(tenant_id=tenant.id, name="Chicken", unit="kg", cost_per_unit=Decimal("700"))
    category = Category(tenant_id=tenant.id, name="Pakistani", display_order=0)
    db.add_all([site, station, chicken, category])
    await db.flush()
    karahi = MenuItem(
        tenant_id=tenant.id, category_id=category.id, name="Chicken Karahi",
        price=200000, is_available=True,
    )
    db.add(karahi)
    await db.flush()
    recipe = Recipe(tenant_id=tenant.id, menu_item_id=karahi.id, yield_servings=Decimal("1"))
    db.add(recipe)
    await db.flush()
    db.add(RecipeItem(
        tenant_id=tenant.id, recipe_id=recipe.id, ingredient_id=chicken.id,
        quantity=Decimal("0.5"), unit="kg", waste_factor=Decimal("0"),
    ))
    await stock_service.move_stock(
        db, tenant_id=tenant.id, ingredient_id=chicken.id, quantity_delta=Decimal("10"),
        transaction_type="purchase", location_id=site.id,
    )
    perm = Permission(tenant_id=tenant.id, code="order.void", description="Void orders")
    db.add(perm)
    await db.flush()
    db.add(RolePermission(tenant_id=tenant.id, role_id=admin_role.id, permission_id=perm.id))
    await db.commit()
    return {"site_id": site.id, "chicken_id": chicken.id, "karahi": karahi}


async def _place(client: AsyncClient, token: str, karahi: MenuItem, table: Table | None, waiter: User | None = None):
    body = {
        "order_type": "dine_in" if table else "takeaway",
        "items": [{"menu_item_id": str(karahi.id), "name": karahi.name, "quantity": 1, "unit_price": karahi.price}],
    }
    if table:
        body["table_id"] = str(table.id)
    if waiter:
        body["waiter_id"] = str(waiter.id)
    r = await client.post("/api/v1/orders", json=body, headers=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()


async def _ticket(client: AsyncClient, token: str, order_id: str) -> dict:
    stations = (await client.get("/api/v1/kitchen/stations", headers=_auth(token))).json()
    queue = (
        await client.get(
            f"/api/v1/kitchen/stations/{stations[0]['id']}/queue",
            params={"active_only": False, "served_within_minutes": 30},
            headers=_auth(token),
        )
    ).json()
    return next(t for t in queue if t["order_id"] == order_id)


async def _bump(client: AsyncClient, token: str, ticket_id: str, status: str) -> None:
    r = await client.patch(
        f"/api/v1/kitchen/tickets/{ticket_id}/status", json={"status": status}, headers=_auth(token)
    )
    assert r.status_code == 200, r.text


async def _order(client: AsyncClient, token: str, order_id: str) -> dict:
    return (await client.get(f"/api/v1/orders/{order_id}", headers=_auth(token))).json()


async def _chicken_left(db: AsyncSession, setup: dict) -> Decimal:
    # Read the ids BEFORE expiring: an expired ORM attribute lazy-loads, which
    # async sessions refuse.
    site_id, chicken_id = setup["site_id"], setup["chicken_id"]
    db.expire_all()
    quantity = (
        await db.execute(
            select(LocationStock.quantity).where(
                LocationStock.location_id == site_id, LocationStock.ingredient_id == chicken_id
            )
        )
    ).scalar_one()
    return Decimal(str(quantity))


async def test_kitchen_serves_then_bill_is_paid_completes_and_deducts(
    client, db, admin_token, admin_user, table, kitchen_setup
):
    """The exact Danny's walk: kitchen bumps to Served, then the bill is settled."""
    order = await _place(client, admin_token, kitchen_setup["karahi"], table)
    ticket = await _ticket(client, admin_token, order["id"])

    await _bump(client, admin_token, ticket["id"], "preparing")
    await _bump(client, admin_token, ticket["id"], "ready")
    assert (await _order(client, admin_token, order["id"]))["status"] == "ready"
    await _bump(client, admin_token, ticket["id"], "served")
    assert (await _order(client, admin_token, order["id"]))["status"] == "served"

    r = await client.post(
        "/api/v1/payments",
        json={"order_id": order["id"], "method_code": "cash", "amount": order["total"],
              "tendered_amount": order["total"]},
        headers=_auth(admin_token),
    )
    assert r.status_code == 201, r.text

    assert (await _order(client, admin_token, order["id"]))["status"] == "completed"
    assert await _chicken_left(db, kitchen_setup) == Decimal("9.5")


async def test_bill_paid_first_then_kitchen_serves_completes_and_deducts(
    client, db, admin_token, table, kitchen_setup
):
    """The other order of events (D-28): paid first, served last, still done."""
    order = await _place(client, admin_token, kitchen_setup["karahi"], table)
    r = await client.post(
        "/api/v1/payments",
        json={"order_id": order["id"], "method_code": "cash", "amount": order["total"],
              "tendered_amount": order["total"]},
        headers=_auth(admin_token),
    )
    assert r.status_code == 201, r.text
    ticket = await _ticket(client, admin_token, order["id"])
    for status in ("preparing", "ready", "served"):
        await _bump(client, admin_token, ticket["id"], status)

    assert (await _order(client, admin_token, order["id"]))["status"] == "completed"
    assert await _chicken_left(db, kitchen_setup) == Decimal("9.5")
    consumed = (
        await db.execute(
            select(InventoryTransaction).where(
                InventoryTransaction.transaction_type == "consumption",
            )
        )
    ).scalars().all()
    assert len(consumed) == 1  # deducted once, not once per path


async def test_unpaid_served_order_waits_for_the_bill(client, db, admin_token, table, kitchen_setup):
    order = await _place(client, admin_token, kitchen_setup["karahi"], table)
    ticket = await _ticket(client, admin_token, order["id"])
    for status in ("preparing", "ready", "served"):
        await _bump(client, admin_token, ticket["id"], status)

    assert (await _order(client, admin_token, order["id"]))["status"] == "served"
    assert await _chicken_left(db, kitchen_setup) == Decimal("10")


async def test_order_completed_at_the_pos_clears_the_kitchen_ticket(
    client, db, admin_token, kitchen_setup
):
    """D-13: no ghost tickets left in NEW after the POS finishes the order."""
    order = await _place(client, admin_token, kitchen_setup["karahi"], None)
    for status in ("ready", "served", "completed"):
        r = await client.patch(
            f"/api/v1/orders/{order['id']}/status", json={"status": status}, headers=_auth(admin_token)
        )
        assert r.status_code == 200, r.text

    db.expire_all()
    ticket = (
        await db.execute(select(KitchenTicket).where(KitchenTicket.order_id == uuid.UUID(order["id"])))
    ).scalar_one()
    assert ticket.status == "served"
    assert ticket.served_at is not None


async def test_voided_order_leaves_the_kitchen_board(client, db, admin_token, kitchen_setup):
    order = await _place(client, admin_token, kitchen_setup["karahi"], None)
    verify = await client.post(
        "/api/v1/auth/verify-password", json={"password": "admin123"}, headers=_auth(admin_token)
    )
    assert verify.status_code == 200, verify.text
    r = await client.post(
        f"/api/v1/orders/{order['id']}/void",
        json={"reason": "customer left", "auth_token": verify.json()["auth_token"]},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200, r.text
    stations = (await client.get("/api/v1/kitchen/stations", headers=_auth(admin_token))).json()
    active = (
        await client.get(
            f"/api/v1/kitchen/stations/{stations[0]['id']}/queue",
            params={"active_only": True},
            headers=_auth(admin_token),
        )
    ).json()
    assert all(t["order_id"] != order["id"] for t in active)


async def test_ticket_shows_table_and_waiter(client, admin_token, admin_user, table, kitchen_setup):
    """D-14: the kitchen can see whose food it is."""
    order = await _place(client, admin_token, kitchen_setup["karahi"], table, waiter=admin_user)
    ticket = await _ticket(client, admin_token, order["id"])
    assert ticket["table_label"] == "T1"
    assert ticket["waiter_name"] == admin_user.full_name


async def test_old_served_tickets_drop_off_the_board(client, db, admin_token, kitchen_setup):
    from datetime import datetime, timedelta, timezone

    order = await _place(client, admin_token, kitchen_setup["karahi"], None)
    db.expire_all()
    ticket = (
        await db.execute(select(KitchenTicket).where(KitchenTicket.order_id == uuid.UUID(order["id"])))
    ).scalar_one()
    ticket.status = "served"
    ticket.served_at = datetime.now(timezone.utc) - timedelta(hours=2)
    await db.commit()

    stations = (await client.get("/api/v1/kitchen/stations", headers=_auth(admin_token))).json()
    queue = (
        await client.get(
            f"/api/v1/kitchen/stations/{stations[0]['id']}/queue",
            params={"active_only": False, "served_within_minutes": 30},
            headers=_auth(admin_token),
        )
    ).json()
    assert all(t["order_id"] != order["id"] for t in queue)


async def test_unpaid_dine_in_cannot_be_completed(client, db, admin_token, table, kitchen_setup):
    """D-37: Complete on a served, unpaid table freed it and took the stock with no payment."""
    order = await _place(client, admin_token, kitchen_setup["karahi"], table)
    for status in ("ready", "served"):
        r = await client.patch(
            f"/api/v1/orders/{order['id']}/status", json={"status": status}, headers=_auth(admin_token)
        )
        assert r.status_code == 200, r.text

    r = await client.patch(
        f"/api/v1/orders/{order['id']}/status", json={"status": "completed"}, headers=_auth(admin_token)
    )
    assert r.status_code in (400, 409), r.text
    assert "Settle the bill" in r.text
    assert (await _order(client, admin_token, order["id"]))["status"] == "served"
    assert await _chicken_left(db, kitchen_setup) == Decimal("10")


async def test_ticket_carries_the_portion(client, db, tenant, admin_token, table, kitchen_setup):
    """D-36: the kitchen saw "Chicken Karahi" and could not tell Half from Full."""
    from app.models.menu import MenuItemModifierGroup, Modifier, ModifierGroup

    karahi = kitchen_setup["karahi"]
    karahi_id, karahi_name, karahi_price = karahi.id, karahi.name, karahi.price
    group = ModifierGroup(
        tenant_id=tenant.id, name="Portion", display_order=0, required=True,
        min_selections=1, max_selections=1,
    )
    db.add(group)
    await db.flush()
    full = Modifier(tenant_id=tenant.id, group_id=group.id, name="Full", price_adjustment=96000, display_order=1)
    db.add_all([full, MenuItemModifierGroup(tenant_id=tenant.id, menu_item_id=karahi_id, modifier_group_id=group.id)])
    await db.commit()

    r = await client.post(
        "/api/v1/orders",
        json={
            "order_type": "dine_in", "table_id": str(table.id),
            "items": [{
                "menu_item_id": str(karahi_id), "name": karahi_name, "quantity": 1,
                "unit_price": karahi_price + 96000,
                "modifiers": [{"modifier_id": str(full.id), "name": "Full", "price_adjustment": 96000}],
            }],
        },
        headers=_auth(admin_token),
    )
    assert r.status_code == 201, r.text
    ticket = await _ticket(client, admin_token, r.json()["id"])
    assert ticket["items"][0]["modifiers"] == ["Full"]


async def test_online_orders_are_not_driven_by_the_kitchen(db, tenant, admin_user, kitchen_setup):
    """Online orders keep their own accept / dispatch flow."""
    from app.services import kitchen_service

    order = Order(
        tenant_id=tenant.id, order_number="W-1", order_type="online", status="in_kitchen",
        payment_status="paid", subtotal=100, tax_amount=0, discount_amount=0, total=100,
        created_by=admin_user.id,
    )
    db.add(order)
    await db.flush()
    station = (await db.execute(select(KitchenStation))).scalars().first()
    db.add(KitchenTicket(tenant_id=tenant.id, order_id=order.id, station_id=station.id, status="served"))
    await db.flush()

    await kitchen_service.sync_order_from_tickets(db, tenant.id, order.id, admin_user.id)
    assert order.status == "in_kitchen"
