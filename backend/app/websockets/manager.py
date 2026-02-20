"""WebSocket connection manager with room-based broadcasting.

Rooms follow the pattern:
    kitchen:{station_id}   — per-station ticket events
    kitchen:all            — all kitchen events for a tenant
    orders                 — order events for a tenant
    floor                  — table status changes for a tenant

Every room is scoped by tenant_id to guarantee isolation.
"""

import asyncio
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass(eq=False)
class ConnectedClient:
    """A WebSocket connection with metadata.

    eq=False preserves default object-identity __hash__,
    which is needed because instances are stored in sets.
    """
    ws: WebSocket
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    rooms: set[str] = field(default_factory=set)


class ConnectionManager:
    """Manages WebSocket connections and room-based message routing.

    Thread-safe for asyncio (single event loop). For multi-worker scaling,
    layer Redis pub/sub on top (publish to Redis, each worker relays to
    its local connections).
    """

    def __init__(self) -> None:
        # room_name -> set of ConnectedClient
        self._rooms: dict[str, set[ConnectedClient]] = defaultdict(set)
        # ws id -> ConnectedClient
        self._clients: dict[int, ConnectedClient] = {}

    async def connect(
        self, ws: WebSocket, tenant_id: uuid.UUID, user_id: uuid.UUID,
    ) -> ConnectedClient:
        """Accept the WebSocket and register the client."""
        await ws.accept()
        client = ConnectedClient(ws=ws, tenant_id=tenant_id, user_id=user_id)
        self._clients[id(ws)] = client
        logger.info("WS connected: user=%s tenant=%s", user_id, tenant_id)
        return client

    def disconnect(self, ws: WebSocket) -> None:
        """Remove a client from all rooms and the client registry."""
        client = self._clients.pop(id(ws), None)
        if client is None:
            return
        for room in list(client.rooms):
            self._rooms[room].discard(client)
            if not self._rooms[room]:
                del self._rooms[room]
        logger.info("WS disconnected: user=%s", client.user_id)

    def join(self, ws: WebSocket, room: str) -> None:
        """Subscribe a client to a room."""
        client = self._clients.get(id(ws))
        if client is None:
            return
        client.rooms.add(room)
        self._rooms[room].add(client)
        logger.debug("WS join room=%s user=%s", room, client.user_id)

    def leave(self, ws: WebSocket, room: str) -> None:
        """Unsubscribe a client from a room."""
        client = self._clients.get(id(ws))
        if client is None:
            return
        client.rooms.discard(room)
        self._rooms[room].discard(client)
        if not self._rooms[room]:
            del self._rooms[room]

    async def broadcast_to_room(
        self, room: str, tenant_id: uuid.UUID, message: dict,
    ) -> None:
        """Send a message to all clients in a room that belong to the given tenant.

        Tenant isolation: even if two tenants somehow join the same room name,
        only matching tenant_id connections receive the message.
        """
        clients = list(self._rooms.get(room, set()))
        tasks = []
        for client in clients:
            if client.tenant_id != tenant_id:
                continue
            tasks.append(self._safe_send(client, message))
        if tasks:
            await asyncio.gather(*tasks)

    async def broadcast_to_tenant(
        self, tenant_id: uuid.UUID, message: dict,
    ) -> None:
        """Send a message to ALL connections belonging to a tenant."""
        tasks = []
        for client in self._clients.values():
            if client.tenant_id == tenant_id:
                tasks.append(self._safe_send(client, message))
        if tasks:
            await asyncio.gather(*tasks)

    async def _safe_send(self, client: ConnectedClient, message: dict) -> None:
        """Send JSON to a client, swallowing errors for dead connections."""
        try:
            await client.ws.send_json(message)
        except Exception:
            logger.debug("WS send failed for user=%s, removing", client.user_id)
            self.disconnect(client.ws)

    @property
    def active_connections(self) -> int:
        return len(self._clients)

    def get_room_members(self, room: str) -> list[ConnectedClient]:
        """Get all clients in a room (for testing/debugging)."""
        return list(self._rooms.get(room, set()))


# Singleton instance used across the application
manager = ConnectionManager()
