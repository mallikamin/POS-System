"""Kitchen endpoints -- station CRUD, ticket queue, and ticket state transitions."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.kitchen import (
    StationCreate,
    StationResponse,
    StationUpdate,
    TicketItemResponse,
    TicketResponse,
    TicketStatusUpdate,
)
from app.services import kitchen_service
from app.websockets.kitchen_events import emit_ticket_created, emit_ticket_updated

router = APIRouter(prefix="/kitchen", tags=["kitchen"])


# ---------------------------------------------------------------------------
# Station CRUD
# ---------------------------------------------------------------------------

@router.get("/stations", response_model=list[StationResponse])
async def list_stations(
    active_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[StationResponse]:
    stations = await kitchen_service.list_stations(
        db, current_user.tenant_id, active_only=active_only
    )
    return [StationResponse.model_validate(s) for s in stations]


@router.get("/stations/{station_id}", response_model=StationResponse)
async def get_station(
    station_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StationResponse:
    station = await kitchen_service.get_station(db, station_id, current_user.tenant_id)
    if station is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Station not found")
    return StationResponse.model_validate(station)


@router.post(
    "/stations",
    response_model=StationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_station(
    body: StationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StationResponse:
    try:
        station = await kitchen_service.create_station(
            db, current_user.tenant_id,
            name=body.name,
            display_order=body.display_order,
            is_active=body.is_active,
            description=body.description,
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    await db.refresh(station)
    return StationResponse.model_validate(station)


@router.patch("/stations/{station_id}", response_model=StationResponse)
async def update_station(
    station_id: uuid.UUID,
    body: StationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StationResponse:
    station = await kitchen_service.get_station(db, station_id, current_user.tenant_id)
    if station is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Station not found")
    try:
        station = await kitchen_service.update_station(
            db, station, current_user.tenant_id,
            body.model_dump(exclude_unset=True),
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    await db.refresh(station)
    return StationResponse.model_validate(station)


# ---------------------------------------------------------------------------
# Ticket Queue
# ---------------------------------------------------------------------------

def _ticket_to_response(ticket) -> TicketResponse:
    """Build a TicketResponse with denormalized order + item fields."""
    items = []
    for ti in ticket.items:
        oi = ti.order_item
        items.append(TicketItemResponse(
            id=ti.id,
            order_item_id=ti.order_item_id,
            quantity=ti.quantity,
            item_name=oi.name if oi else None,
            item_notes=oi.notes if oi else None,
        ))
    return TicketResponse(
        id=ticket.id,
        order_id=ticket.order_id,
        station_id=ticket.station_id,
        status=ticket.status,
        priority=ticket.priority,
        notes=ticket.notes,
        started_at=ticket.started_at,
        completed_at=ticket.completed_at,
        served_at=ticket.served_at,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        order_number=ticket.order.order_number if ticket.order else None,
        order_type=ticket.order.order_type if ticket.order else None,
        items=items,
    )


@router.get("/stations/{station_id}/queue", response_model=list[TicketResponse])
async def get_station_queue(
    station_id: uuid.UUID,
    active_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TicketResponse]:
    station = await kitchen_service.get_station(db, station_id, current_user.tenant_id)
    if station is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Station not found")
    tickets = await kitchen_service.get_station_queue(
        db, station_id, current_user.tenant_id, active_only=active_only,
    )
    return [_ticket_to_response(t) for t in tickets]


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TicketResponse:
    ticket = await kitchen_service.get_ticket(db, ticket_id, current_user.tenant_id)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    return _ticket_to_response(ticket)


# ---------------------------------------------------------------------------
# Ticket Status Transition
# ---------------------------------------------------------------------------

@router.patch("/tickets/{ticket_id}/status", response_model=TicketResponse)
async def transition_ticket(
    ticket_id: uuid.UUID,
    body: TicketStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TicketResponse:
    # Capture previous status before transition
    pre_ticket = await kitchen_service.get_ticket(
        db, ticket_id, current_user.tenant_id
    )
    previous_status = pre_ticket.status if pre_ticket else None

    try:
        ticket = await kitchen_service.transition_ticket(
            db, ticket_id, current_user.tenant_id, body.status,
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    await db.refresh(ticket)
    # Re-fetch fully loaded after refresh
    ticket = await kitchen_service.get_ticket(db, ticket.id, current_user.tenant_id)

    # Emit WebSocket event (fire-and-forget, don't block the response)
    await emit_ticket_updated(current_user.tenant_id, ticket, previous_status or "new")

    return _ticket_to_response(ticket)
