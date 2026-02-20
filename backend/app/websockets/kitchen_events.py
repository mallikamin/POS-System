"""Kitchen WebSocket event emitters.

Events are broadcast to:
  - kitchen:{station_id}  (station-scoped, for per-station KDS screens)
  - kitchen:all            (global, for overview dashboards)

Event payload shape:
{
    "event": "kitchen.ticket.created" | "kitchen.ticket.updated",
    "data": {
        "ticket_id": str(uuid),
        "order_id": str(uuid),
        "station_id": str(uuid),
        "station_name": str,
        "order_number": str,
        "order_type": str,
        "status": str,
        "previous_status": str | null,
        "priority": int,
        "items": [
            {"order_item_id": str(uuid), "name": str, "quantity": int}
        ],
    }
}
"""

import uuid

from app.models.kitchen import KitchenTicket
from app.websockets.manager import manager


def _build_ticket_payload(ticket: KitchenTicket) -> dict:
    """Build the data portion of a ticket event from an ORM object."""
    items = []
    for ti in ticket.items:
        oi = ti.order_item
        items.append({
            "order_item_id": str(ti.order_item_id),
            "name": oi.name if oi else "Unknown",
            "quantity": ti.quantity,
        })
    return {
        "ticket_id": str(ticket.id),
        "order_id": str(ticket.order_id),
        "station_id": str(ticket.station_id),
        "station_name": ticket.station.name if ticket.station else None,
        "order_number": ticket.order.order_number if ticket.order else None,
        "order_type": ticket.order.order_type if ticket.order else None,
        "status": ticket.status,
        "priority": ticket.priority,
        "items": items,
    }


async def emit_ticket_created(
    tenant_id: uuid.UUID, ticket: KitchenTicket,
) -> None:
    """Broadcast a ticket.created event to station + global rooms."""
    payload = {
        "event": "kitchen.ticket.created",
        "data": {
            **_build_ticket_payload(ticket),
            "previous_status": None,
        },
    }
    station_room = f"kitchen:{ticket.station_id}"
    await manager.broadcast_to_room(station_room, tenant_id, payload)
    await manager.broadcast_to_room("kitchen:all", tenant_id, payload)


async def emit_ticket_updated(
    tenant_id: uuid.UUID,
    ticket: KitchenTicket,
    previous_status: str,
) -> None:
    """Broadcast a ticket.updated event to station + global rooms."""
    payload = {
        "event": "kitchen.ticket.updated",
        "data": {
            **_build_ticket_payload(ticket),
            "previous_status": previous_status,
        },
    }
    station_room = f"kitchen:{ticket.station_id}"
    await manager.broadcast_to_room(station_room, tenant_id, payload)
    await manager.broadcast_to_room("kitchen:all", tenant_id, payload)
