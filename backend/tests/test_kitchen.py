"""Tests for kitchen endpoints (Phase 6 — KDS).

Covers: station CRUD, ticket state transitions, station queue,
tenant isolation, and invalid transitions.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kitchen import KitchenStation, KitchenTicket, KitchenTicketItem
from app.models.menu import Category, MenuItem
from app.models.order import Order, OrderItem
from app.models.user import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# Fixtures
# =========================================================================

@pytest_asyncio.fixture
async def station(db: AsyncSession, tenant) -> KitchenStation:
    """A single active kitchen station."""
    s = KitchenStation(
        tenant_id=tenant.id, name="Grill", display_order=1, is_active=True,
    )
    db.add(s)
    await db.flush()
    await db.commit()
    return s


@pytest_asyncio.fixture
async def category_and_item(db: AsyncSession, tenant) -> tuple[Category, MenuItem]:
    """A category + menu item for building orders."""
    cat = Category(tenant_id=tenant.id, name="BBQ", display_order=1, is_active=True)
    db.add(cat)
    await db.flush()
    item = MenuItem(
        tenant_id=tenant.id, category_id=cat.id,
        name="Seekh Kebab", price=25000, is_available=True,
    )
    db.add(item)
    await db.flush()
    await db.commit()
    return cat, item


@pytest_asyncio.fixture
async def order_with_items(
    db: AsyncSession, tenant, admin_user: User, category_and_item,
) -> Order:
    """An in_kitchen order with one item."""
    _, item = category_and_item
    o = Order(
        tenant_id=tenant.id, order_number="K250101-001",
        order_type="dine_in", status="in_kitchen", payment_status="unpaid",
        subtotal=25000, tax_amount=4000, discount_amount=0, total=29000,
        created_by=admin_user.id,
    )
    db.add(o)
    await db.flush()
    oi = OrderItem(
        tenant_id=tenant.id, order_id=o.id, menu_item_id=item.id,
        name="Seekh Kebab", quantity=2, unit_price=25000, total=50000,
        status="sent",
    )
    db.add(oi)
    await db.flush()
    await db.commit()
    # Attach item list for test access
    o._test_items = [oi]  # type: ignore[attr-defined]
    return o


@pytest_asyncio.fixture
async def ticket(
    db: AsyncSession, tenant, station: KitchenStation, order_with_items: Order,
) -> KitchenTicket:
    """A kitchen ticket (status=new) with one ticket item."""
    o = order_with_items
    t = KitchenTicket(
        tenant_id=tenant.id, order_id=o.id, station_id=station.id,
        status="new", priority=0,
    )
    db.add(t)
    await db.flush()
    oi = o._test_items[0]  # type: ignore[attr-defined]
    ti = KitchenTicketItem(
        tenant_id=tenant.id, ticket_id=t.id,
        order_item_id=oi.id, quantity=oi.quantity,
    )
    db.add(ti)
    await db.flush()
    await db.commit()
    return t


# =========================================================================
# 1. Station CRUD
# =========================================================================
class TestStationCRUD:
    """POST/GET/PATCH /api/v1/kitchen/stations"""

    async def test_create_station(
        self, client: AsyncClient, cashier_token: str,
    ):
        resp = await client.post(
            "/api/v1/kitchen/stations",
            json={"name": "Fryer", "display_order": 2, "description": "Deep fry station"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Fryer"
        assert body["display_order"] == 2
        assert body["is_active"] is True
        assert body["description"] == "Deep fry station"

    async def test_create_duplicate_station_409(
        self, client: AsyncClient, cashier_token: str, station: KitchenStation,
    ):
        resp = await client.post(
            "/api/v1/kitchen/stations",
            json={"name": "Grill"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()

    async def test_list_stations(
        self, client: AsyncClient, cashier_token: str, station: KitchenStation,
    ):
        resp = await client.get(
            "/api/v1/kitchen/stations",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
        assert any(s["name"] == "Grill" for s in resp.json())

    async def test_get_station(
        self, client: AsyncClient, cashier_token: str, station: KitchenStation,
    ):
        resp = await client.get(
            f"/api/v1/kitchen/stations/{station.id}",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Grill"

    async def test_get_station_not_found(
        self, client: AsyncClient, cashier_token: str,
    ):
        resp = await client.get(
            f"/api/v1/kitchen/stations/{uuid.uuid4()}",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 404

    async def test_update_station(
        self, client: AsyncClient, cashier_token: str, station: KitchenStation,
    ):
        resp = await client.patch(
            f"/api/v1/kitchen/stations/{station.id}",
            json={"name": "Charcoal Grill", "display_order": 5},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Charcoal Grill"
        assert body["display_order"] == 5

    async def test_update_station_duplicate_name_409(
        self, client: AsyncClient, cashier_token: str, station: KitchenStation,
    ):
        # Create a second station
        resp = await client.post(
            "/api/v1/kitchen/stations",
            json={"name": "Beverage"},
            headers=_auth(cashier_token),
        )
        sid2 = resp.json()["id"]
        # Try to rename it to "Grill"
        resp = await client.patch(
            f"/api/v1/kitchen/stations/{sid2}",
            json={"name": "Grill"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 409

    async def test_deactivate_station(
        self, client: AsyncClient, cashier_token: str, station: KitchenStation,
    ):
        resp = await client.patch(
            f"/api/v1/kitchen/stations/{station.id}",
            json={"is_active": False},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_no_auth_401(self, client: AsyncClient):
        resp = await client.get("/api/v1/kitchen/stations")
        assert resp.status_code == 401


# =========================================================================
# 2. Ticket State Transitions
# =========================================================================
class TestTicketTransitions:
    """PATCH /api/v1/kitchen/tickets/{ticket_id}/status"""

    async def test_new_to_preparing(
        self, client: AsyncClient, cashier_token: str, ticket: KitchenTicket,
    ):
        resp = await client.patch(
            f"/api/v1/kitchen/tickets/{ticket.id}/status",
            json={"status": "preparing"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "preparing"
        assert body["started_at"] is not None

    async def test_preparing_to_ready(
        self, client: AsyncClient, cashier_token: str, ticket: KitchenTicket,
    ):
        # First transition to preparing
        await client.patch(
            f"/api/v1/kitchen/tickets/{ticket.id}/status",
            json={"status": "preparing"},
            headers=_auth(cashier_token),
        )
        resp = await client.patch(
            f"/api/v1/kitchen/tickets/{ticket.id}/status",
            json={"status": "ready"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ready"
        assert body["completed_at"] is not None

    async def test_ready_to_served(
        self, client: AsyncClient, cashier_token: str, ticket: KitchenTicket,
    ):
        await client.patch(
            f"/api/v1/kitchen/tickets/{ticket.id}/status",
            json={"status": "preparing"},
            headers=_auth(cashier_token),
        )
        await client.patch(
            f"/api/v1/kitchen/tickets/{ticket.id}/status",
            json={"status": "ready"},
            headers=_auth(cashier_token),
        )
        resp = await client.patch(
            f"/api/v1/kitchen/tickets/{ticket.id}/status",
            json={"status": "served"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "served"
        assert body["served_at"] is not None

    async def test_full_lifecycle_timestamps(
        self, client: AsyncClient, cashier_token: str, ticket: KitchenTicket,
    ):
        """Run through full lifecycle and verify all timestamps are populated."""
        for next_status in ["preparing", "ready", "served"]:
            resp = await client.patch(
                f"/api/v1/kitchen/tickets/{ticket.id}/status",
                json={"status": next_status},
                headers=_auth(cashier_token),
            )
            assert resp.status_code == 200

        body = resp.json()
        assert body["started_at"] is not None
        assert body["completed_at"] is not None
        assert body["served_at"] is not None


# =========================================================================
# 3. Invalid Transitions
# =========================================================================
class TestInvalidTransitions:

    async def test_new_to_ready_rejected(
        self, client: AsyncClient, cashier_token: str, ticket: KitchenTicket,
    ):
        resp = await client.patch(
            f"/api/v1/kitchen/tickets/{ticket.id}/status",
            json={"status": "ready"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 400
        assert "cannot transition" in resp.json()["detail"].lower()

    async def test_new_to_served_rejected(
        self, client: AsyncClient, cashier_token: str, ticket: KitchenTicket,
    ):
        resp = await client.patch(
            f"/api/v1/kitchen/tickets/{ticket.id}/status",
            json={"status": "served"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 400

    async def test_served_to_anything_rejected(
        self, client: AsyncClient, cashier_token: str, ticket: KitchenTicket,
    ):
        """Served is terminal — no further transitions."""
        for s in ["preparing", "ready", "served"]:
            await client.patch(
                f"/api/v1/kitchen/tickets/{ticket.id}/status",
                json={"status": "preparing"},
                headers=_auth(cashier_token),
            )
        # Now at "ready" — transition to served
        await client.patch(
            f"/api/v1/kitchen/tickets/{ticket.id}/status",
            json={"status": "served"},
            headers=_auth(cashier_token),
        )
        # Try going back
        resp = await client.patch(
            f"/api/v1/kitchen/tickets/{ticket.id}/status",
            json={"status": "preparing"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 400

    async def test_invalid_status_value_422(
        self, client: AsyncClient, cashier_token: str, ticket: KitchenTicket,
    ):
        resp = await client.patch(
            f"/api/v1/kitchen/tickets/{ticket.id}/status",
            json={"status": "cancelled"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 422

    async def test_nonexistent_ticket_400(
        self, client: AsyncClient, cashier_token: str,
    ):
        resp = await client.patch(
            f"/api/v1/kitchen/tickets/{uuid.uuid4()}/status",
            json={"status": "preparing"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"].lower()


# =========================================================================
# 4. Station Queue
# =========================================================================
class TestStationQueue:

    async def test_queue_returns_tickets(
        self, client: AsyncClient, cashier_token: str,
        station: KitchenStation, ticket: KitchenTicket,
    ):
        resp = await client.get(
            f"/api/v1/kitchen/stations/{station.id}/queue",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        tickets = resp.json()
        assert len(tickets) >= 1
        assert tickets[0]["station_id"] == str(station.id)
        assert tickets[0]["status"] == "new"

    async def test_queue_includes_item_details(
        self, client: AsyncClient, cashier_token: str,
        station: KitchenStation, ticket: KitchenTicket,
    ):
        resp = await client.get(
            f"/api/v1/kitchen/stations/{station.id}/queue",
            headers=_auth(cashier_token),
        )
        tickets = resp.json()
        assert len(tickets[0]["items"]) >= 1
        item = tickets[0]["items"][0]
        assert item["item_name"] == "Seekh Kebab"
        assert item["quantity"] == 2

    async def test_queue_includes_order_info(
        self, client: AsyncClient, cashier_token: str,
        station: KitchenStation, ticket: KitchenTicket,
    ):
        resp = await client.get(
            f"/api/v1/kitchen/stations/{station.id}/queue",
            headers=_auth(cashier_token),
        )
        tickets = resp.json()
        assert tickets[0]["order_number"] == "K250101-001"
        assert tickets[0]["order_type"] == "dine_in"

    async def test_queue_excludes_served_by_default(
        self, client: AsyncClient, cashier_token: str,
        station: KitchenStation, ticket: KitchenTicket,
    ):
        """Served tickets are excluded from active queue."""
        for s in ["preparing", "ready", "served"]:
            await client.patch(
                f"/api/v1/kitchen/tickets/{ticket.id}/status",
                json={"status": s},
                headers=_auth(cashier_token),
            )
        resp = await client.get(
            f"/api/v1/kitchen/stations/{station.id}/queue",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    async def test_queue_includes_served_when_requested(
        self, client: AsyncClient, cashier_token: str,
        station: KitchenStation, ticket: KitchenTicket,
    ):
        for s in ["preparing", "ready", "served"]:
            await client.patch(
                f"/api/v1/kitchen/tickets/{ticket.id}/status",
                json={"status": s},
                headers=_auth(cashier_token),
            )
        resp = await client.get(
            f"/api/v1/kitchen/stations/{station.id}/queue?active_only=false",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_queue_nonexistent_station_404(
        self, client: AsyncClient, cashier_token: str,
    ):
        resp = await client.get(
            f"/api/v1/kitchen/stations/{uuid.uuid4()}/queue",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 404


# =========================================================================
# 5. Get Ticket
# =========================================================================
class TestGetTicket:

    async def test_get_ticket_success(
        self, client: AsyncClient, cashier_token: str, ticket: KitchenTicket,
    ):
        resp = await client.get(
            f"/api/v1/kitchen/tickets/{ticket.id}",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(ticket.id)
        assert body["status"] == "new"

    async def test_get_ticket_not_found(
        self, client: AsyncClient, cashier_token: str,
    ):
        resp = await client.get(
            f"/api/v1/kitchen/tickets/{uuid.uuid4()}",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 404


# =========================================================================
# 6. Tenant Isolation
# =========================================================================
class TestTenantIsolation:

    async def test_station_not_visible_cross_tenant(
        self, client: AsyncClient, other_tenant_token: str,
        station: KitchenStation,
    ):
        resp = await client.get(
            f"/api/v1/kitchen/stations/{station.id}",
            headers=_auth(other_tenant_token),
        )
        assert resp.status_code == 404

    async def test_ticket_not_visible_cross_tenant(
        self, client: AsyncClient, other_tenant_token: str,
        ticket: KitchenTicket,
    ):
        resp = await client.get(
            f"/api/v1/kitchen/tickets/{ticket.id}",
            headers=_auth(other_tenant_token),
        )
        assert resp.status_code == 404

    async def test_transition_cross_tenant_rejected(
        self, client: AsyncClient, other_tenant_token: str,
        ticket: KitchenTicket,
    ):
        resp = await client.patch(
            f"/api/v1/kitchen/tickets/{ticket.id}/status",
            json={"status": "preparing"},
            headers=_auth(other_tenant_token),
        )
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"].lower()

    async def test_station_list_isolated(
        self, client: AsyncClient, cashier_token: str,
        other_tenant_token: str, station: KitchenStation,
    ):
        """Tenant B sees no stations from Tenant A."""
        resp = await client.get(
            "/api/v1/kitchen/stations",
            headers=_auth(other_tenant_token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    async def test_queue_cross_tenant_404(
        self, client: AsyncClient, other_tenant_token: str,
        station: KitchenStation,
    ):
        resp = await client.get(
            f"/api/v1/kitchen/stations/{station.id}/queue",
            headers=_auth(other_tenant_token),
        )
        assert resp.status_code == 404
