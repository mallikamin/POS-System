"""Kitchen service -- station CRUD, ticket queue, and ticket state machine."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.kitchen import KitchenStation, KitchenTicket, KitchenTicketItem


# ---------------------------------------------------------------------------
# Ticket State Machine
# ---------------------------------------------------------------------------

VALID_TICKET_TRANSITIONS: dict[str, list[str]] = {
    "new": ["preparing"],
    "preparing": ["ready"],
    "ready": ["served"],
    "served": [],
}


# ---------------------------------------------------------------------------
# Station CRUD
# ---------------------------------------------------------------------------


async def list_stations(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    active_only: bool = False,
) -> list[KitchenStation]:
    stmt = select(KitchenStation).where(KitchenStation.tenant_id == tenant_id)
    if active_only:
        stmt = stmt.where(KitchenStation.is_active == True)  # noqa: E712
    stmt = stmt.order_by(KitchenStation.display_order, KitchenStation.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_station(
    db: AsyncSession,
    station_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> KitchenStation | None:
    result = await db.execute(
        select(KitchenStation).where(
            KitchenStation.id == station_id,
            KitchenStation.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_station(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    name: str,
    display_order: int = 0,
    is_active: bool = True,
    description: str | None = None,
) -> KitchenStation:
    # Check for duplicate name
    existing = await db.execute(
        select(KitchenStation).where(
            KitchenStation.tenant_id == tenant_id,
            KitchenStation.name == name,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Station '{name}' already exists")
    station = KitchenStation(
        tenant_id=tenant_id,
        name=name,
        display_order=display_order,
        is_active=is_active,
        description=description,
    )
    db.add(station)
    await db.flush()
    return station


async def update_station(
    db: AsyncSession,
    station: KitchenStation,
    tenant_id: uuid.UUID,
    update_data: dict,
) -> KitchenStation:
    new_name = update_data.get("name")
    if new_name is not None and new_name != station.name:
        existing = await db.execute(
            select(KitchenStation).where(
                KitchenStation.tenant_id == tenant_id,
                KitchenStation.name == new_name,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError(f"Station '{new_name}' already exists")
    for field, value in update_data.items():
        setattr(station, field, value)
    await db.flush()
    return station


# ---------------------------------------------------------------------------
# Ticket Queries
# ---------------------------------------------------------------------------


async def get_station_queue(
    db: AsyncSession,
    station_id: uuid.UUID,
    tenant_id: uuid.UUID,
    active_only: bool = True,
) -> list[KitchenTicket]:
    """Get tickets for a station, optionally filtering to active only."""
    stmt = (
        select(KitchenTicket)
        .options(
            selectinload(KitchenTicket.items).selectinload(
                KitchenTicketItem.order_item
            ),
            selectinload(KitchenTicket.order),
        )
        .where(
            KitchenTicket.tenant_id == tenant_id,
            KitchenTicket.station_id == station_id,
        )
    )
    if active_only:
        stmt = stmt.where(KitchenTicket.status.notin_(["served"]))
    stmt = stmt.order_by(
        KitchenTicket.priority.desc(),
        KitchenTicket.created_at.asc(),
    )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def get_ticket(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> KitchenTicket | None:
    result = await db.execute(
        select(KitchenTicket)
        .options(
            selectinload(KitchenTicket.items).selectinload(
                KitchenTicketItem.order_item
            ),
            selectinload(KitchenTicket.order),
            selectinload(KitchenTicket.station),
        )
        .where(
            KitchenTicket.id == ticket_id,
            KitchenTicket.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Ticket State Transitions
# ---------------------------------------------------------------------------


async def transition_ticket(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    tenant_id: uuid.UUID,
    new_status: str,
) -> KitchenTicket:
    """Transition a ticket to a new status following the state machine."""
    ticket = await get_ticket(db, ticket_id, tenant_id)
    if ticket is None:
        raise ValueError("Ticket not found")

    current = ticket.status
    allowed = VALID_TICKET_TRANSITIONS.get(current, [])
    if new_status not in allowed:
        raise ValueError(
            f"Cannot transition from '{current}' to '{new_status}'. Allowed: {allowed}"
        )

    now = datetime.now(timezone.utc)
    ticket.status = new_status

    if new_status == "preparing":
        ticket.started_at = now
    elif new_status == "ready":
        ticket.completed_at = now
    elif new_status == "served":
        ticket.served_at = now

    await db.flush()

    # Re-fetch with all relationships
    tid = ticket.id
    db.expunge(ticket)
    return await get_ticket(db, tid, tenant_id)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Ticket Creation (called from order service or route)
# ---------------------------------------------------------------------------


async def create_ticket_for_order(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    station_id: uuid.UUID,
    order_item_ids_quantities: list[tuple[uuid.UUID, int]],
    priority: int = 0,
    notes: str | None = None,
) -> KitchenTicket:
    """Create a kitchen ticket for an order at a specific station."""
    ticket = KitchenTicket(
        tenant_id=tenant_id,
        order_id=order_id,
        station_id=station_id,
        status="new",
        priority=priority,
        notes=notes,
    )
    db.add(ticket)
    await db.flush()

    for item_id, qty in order_item_ids_quantities:
        ticket_item = KitchenTicketItem(
            tenant_id=tenant_id,
            ticket_id=ticket.id,
            order_item_id=item_id,
            quantity=qty,
        )
        db.add(ticket_item)

    await db.flush()
    return await get_ticket(db, ticket.id, tenant_id)  # type: ignore[return-value]
