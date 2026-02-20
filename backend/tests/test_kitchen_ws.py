"""Tests for kitchen WebSocket events (Phase 6 real-time).

Covers: event emission on status transition, tenant isolation,
payload shape, room-scoped delivery, and the connection manager.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.kitchen import KitchenStation, KitchenTicket, KitchenTicketItem
from app.models.menu import Category, MenuItem
from app.models.order import Order, OrderItem
from app.models.user import User
from app.websockets.manager import ConnectionManager, ConnectedClient
from app.websockets.kitchen_events import (
    emit_ticket_created,
    emit_ticket_updated,
    _build_ticket_payload,
)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# Fixtures
# =========================================================================

@pytest_asyncio.fixture
async def station(db: AsyncSession, tenant) -> KitchenStation:
    s = KitchenStation(
        tenant_id=tenant.id, name="Grill", display_order=1, is_active=True,
    )
    db.add(s)
    await db.flush()
    await db.commit()
    return s


@pytest_asyncio.fixture
async def category_and_item(db: AsyncSession, tenant) -> tuple[Category, MenuItem]:
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
    _, item = category_and_item
    o = Order(
        tenant_id=tenant.id, order_number="W250101-001",
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
    o._test_items = [oi]  # type: ignore[attr-defined]
    return o


@pytest_asyncio.fixture
async def ticket(
    db: AsyncSession, tenant, station: KitchenStation, order_with_items: Order,
) -> KitchenTicket:
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
# 1. ConnectionManager unit tests
# =========================================================================
class TestConnectionManager:

    async def test_connect_and_disconnect(self):
        mgr = ConnectionManager()
        ws = AsyncMock()
        client = await mgr.connect(ws, uuid.uuid4(), uuid.uuid4())
        assert mgr.active_connections == 1
        mgr.disconnect(ws)
        assert mgr.active_connections == 0

    async def test_join_and_leave_room(self):
        mgr = ConnectionManager()
        ws = AsyncMock()
        tenant_id = uuid.uuid4()
        client = await mgr.connect(ws, tenant_id, uuid.uuid4())
        mgr.join(ws, "kitchen:all")
        assert len(mgr.get_room_members("kitchen:all")) == 1
        mgr.leave(ws, "kitchen:all")
        assert len(mgr.get_room_members("kitchen:all")) == 0

    async def test_broadcast_to_room(self):
        mgr = ConnectionManager()
        tenant_id = uuid.uuid4()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await mgr.connect(ws1, tenant_id, uuid.uuid4())
        await mgr.connect(ws2, tenant_id, uuid.uuid4())
        mgr.join(ws1, "kitchen:all")
        mgr.join(ws2, "kitchen:all")

        msg = {"event": "test", "data": {}}
        await mgr.broadcast_to_room("kitchen:all", tenant_id, msg)

        ws1.send_json.assert_called_once_with(msg)
        ws2.send_json.assert_called_once_with(msg)

    async def test_broadcast_tenant_isolation(self):
        """Messages are only delivered to matching tenant."""
        mgr = ConnectionManager()
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        ws_a = AsyncMock()
        ws_b = AsyncMock()
        await mgr.connect(ws_a, tenant_a, uuid.uuid4())
        await mgr.connect(ws_b, tenant_b, uuid.uuid4())
        mgr.join(ws_a, "kitchen:all")
        mgr.join(ws_b, "kitchen:all")

        msg = {"event": "test", "data": {}}
        await mgr.broadcast_to_room("kitchen:all", tenant_a, msg)

        ws_a.send_json.assert_called_once_with(msg)
        ws_b.send_json.assert_not_called()

    async def test_broadcast_to_tenant(self):
        mgr = ConnectionManager()
        tenant_id = uuid.uuid4()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await mgr.connect(ws1, tenant_id, uuid.uuid4())
        await mgr.connect(ws2, tenant_id, uuid.uuid4())

        msg = {"event": "global", "data": {}}
        await mgr.broadcast_to_tenant(tenant_id, msg)

        ws1.send_json.assert_called_once_with(msg)
        ws2.send_json.assert_called_once_with(msg)

    async def test_disconnect_removes_from_rooms(self):
        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect(ws, uuid.uuid4(), uuid.uuid4())
        mgr.join(ws, "kitchen:all")
        mgr.join(ws, "orders")
        assert len(mgr.get_room_members("kitchen:all")) == 1
        mgr.disconnect(ws)
        assert len(mgr.get_room_members("kitchen:all")) == 0
        assert len(mgr.get_room_members("orders")) == 0

    async def test_safe_send_handles_dead_connection(self):
        """Dead connections are silently removed on send failure."""
        mgr = ConnectionManager()
        ws = AsyncMock()
        ws.send_json.side_effect = RuntimeError("connection closed")
        tenant_id = uuid.uuid4()
        await mgr.connect(ws, tenant_id, uuid.uuid4())
        mgr.join(ws, "kitchen:all")

        # Should not raise
        await mgr.broadcast_to_room("kitchen:all", tenant_id, {"event": "test"})
        assert mgr.active_connections == 0  # auto-removed


# =========================================================================
# 2. Kitchen event emitter unit tests
# =========================================================================
class TestKitchenEventEmitters:

    async def test_emit_ticket_created_calls_broadcast(self):
        """emit_ticket_created broadcasts to station room + kitchen:all."""
        tenant_id = uuid.uuid4()
        station_id = uuid.uuid4()

        # Build a mock ticket with all needed attributes
        ticket = MagicMock()
        ticket.id = uuid.uuid4()
        ticket.order_id = uuid.uuid4()
        ticket.station_id = station_id
        ticket.status = "new"
        ticket.priority = 0
        ticket.station.name = "Grill"
        ticket.order.order_number = "T250101-001"
        ticket.order.order_type = "dine_in"
        ticket.items = []

        with patch("app.websockets.kitchen_events.manager") as mock_mgr:
            mock_mgr.broadcast_to_room = AsyncMock()
            await emit_ticket_created(tenant_id, ticket)

            assert mock_mgr.broadcast_to_room.call_count == 2
            calls = mock_mgr.broadcast_to_room.call_args_list

            # First call: station-scoped room
            assert calls[0][0][0] == f"kitchen:{station_id}"
            assert calls[0][0][1] == tenant_id
            payload = calls[0][0][2]
            assert payload["event"] == "kitchen.ticket.created"
            assert payload["data"]["previous_status"] is None

            # Second call: kitchen:all
            assert calls[1][0][0] == "kitchen:all"

    async def test_emit_ticket_updated_includes_previous_status(self):
        tenant_id = uuid.uuid4()
        station_id = uuid.uuid4()

        ticket = MagicMock()
        ticket.id = uuid.uuid4()
        ticket.order_id = uuid.uuid4()
        ticket.station_id = station_id
        ticket.status = "preparing"
        ticket.priority = 0
        ticket.station.name = "Grill"
        ticket.order.order_number = "T250101-001"
        ticket.order.order_type = "dine_in"
        ticket.items = []

        with patch("app.websockets.kitchen_events.manager") as mock_mgr:
            mock_mgr.broadcast_to_room = AsyncMock()
            await emit_ticket_updated(tenant_id, ticket, "new")

            payload = mock_mgr.broadcast_to_room.call_args_list[0][0][2]
            assert payload["event"] == "kitchen.ticket.updated"
            assert payload["data"]["status"] == "preparing"
            assert payload["data"]["previous_status"] == "new"

    async def test_payload_shape(self):
        """Verify the full payload structure matches the documented contract."""
        ticket = MagicMock()
        ticket.id = uuid.uuid4()
        ticket.order_id = uuid.uuid4()
        ticket.station_id = uuid.uuid4()
        ticket.status = "ready"
        ticket.priority = 1
        ticket.station.name = "Fryer"
        ticket.order.order_number = "T250101-002"
        ticket.order.order_type = "takeaway"

        mock_ti = MagicMock()
        mock_ti.order_item_id = uuid.uuid4()
        mock_ti.order_item.name = "Seekh Kebab"
        mock_ti.quantity = 3
        ticket.items = [mock_ti]

        payload = _build_ticket_payload(ticket)

        # Required top-level keys
        assert set(payload.keys()) == {
            "ticket_id", "order_id", "station_id", "station_name",
            "order_number", "order_type", "status", "priority", "items",
        }

        # Item shape
        assert len(payload["items"]) == 1
        item = payload["items"][0]
        assert set(item.keys()) == {"order_item_id", "name", "quantity"}
        assert item["name"] == "Seekh Kebab"
        assert item["quantity"] == 3


# =========================================================================
# 3. Integration: event emitted on status transition via HTTP
# =========================================================================
class TestTransitionEmitsEvent:

    async def test_transition_emits_ticket_updated(
        self, client: AsyncClient, cashier_token: str, ticket: KitchenTicket,
    ):
        """PATCH /tickets/{id}/status emits kitchen.ticket.updated."""
        with patch("app.api.v1.kitchen.emit_ticket_updated", new_callable=AsyncMock) as mock_emit:
            resp = await client.patch(
                f"/api/v1/kitchen/tickets/{ticket.id}/status",
                json={"status": "preparing"},
                headers=_auth(cashier_token),
            )
            assert resp.status_code == 200

            mock_emit.assert_called_once()
            args = mock_emit.call_args[0]
            # args: (tenant_id, ticket, previous_status)
            assert args[2] == "new"  # previous_status

    async def test_transition_event_has_correct_tenant(
        self, client: AsyncClient, cashier_token: str,
        ticket: KitchenTicket, tenant,
    ):
        """Event is emitted with the correct tenant_id."""
        with patch("app.api.v1.kitchen.emit_ticket_updated", new_callable=AsyncMock) as mock_emit:
            await client.patch(
                f"/api/v1/kitchen/tickets/{ticket.id}/status",
                json={"status": "preparing"},
                headers=_auth(cashier_token),
            )
            tenant_id_arg = mock_emit.call_args[0][0]
            assert tenant_id_arg == tenant.id

    async def test_failed_transition_does_not_emit(
        self, client: AsyncClient, cashier_token: str, ticket: KitchenTicket,
    ):
        """Invalid transitions should NOT emit events."""
        with patch("app.api.v1.kitchen.emit_ticket_updated", new_callable=AsyncMock) as mock_emit:
            resp = await client.patch(
                f"/api/v1/kitchen/tickets/{ticket.id}/status",
                json={"status": "served"},  # invalid: new -> served
                headers=_auth(cashier_token),
            )
            assert resp.status_code == 400
            mock_emit.assert_not_called()


# =========================================================================
# 4. Tenant isolation: cross-tenant broadcast prevention
# =========================================================================
class TestWsTenantIsolation:

    async def test_cross_tenant_no_broadcast(self):
        """Events for tenant A are never delivered to tenant B connections."""
        mgr = ConnectionManager()
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()

        ws_a = AsyncMock()
        ws_b = AsyncMock()
        await mgr.connect(ws_a, tenant_a, uuid.uuid4())
        await mgr.connect(ws_b, tenant_b, uuid.uuid4())

        station_id = uuid.uuid4()
        room = f"kitchen:{station_id}"
        mgr.join(ws_a, room)
        mgr.join(ws_b, room)

        # Broadcast for tenant_a only
        await mgr.broadcast_to_room(room, tenant_a, {"event": "test"})

        ws_a.send_json.assert_called_once()
        ws_b.send_json.assert_not_called()

    async def test_transition_uses_user_tenant(
        self, client: AsyncClient, cashier_token: str,
        other_tenant_token: str, ticket: KitchenTicket,
    ):
        """Cross-tenant transition attempt fails, no event emitted."""
        with patch("app.api.v1.kitchen.emit_ticket_updated", new_callable=AsyncMock) as mock_emit:
            resp = await client.patch(
                f"/api/v1/kitchen/tickets/{ticket.id}/status",
                json={"status": "preparing"},
                headers=_auth(other_tenant_token),
            )
            assert resp.status_code == 400
            mock_emit.assert_not_called()
