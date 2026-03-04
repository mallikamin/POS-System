"""Floor plan endpoints -- floors, tables, and bulk position updates."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.database import get_db
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.floor import (
    BulkTablePositionUpdate,
    FloorCreate,
    FloorResponse,
    FloorStatusBoard,
    FloorUpdate,
    FloorWithTables,
    TableCreate,
    TableResponse,
    TableStatusUpdate,
    TableUpdate,
)
from app.services import floor_service

router = APIRouter(prefix="/floors", tags=["floors"])

_admin_dep = require_role("admin")


# ---------------------------------------------------------------------------
# Status Board (POS dine-in view uses this)
# ---------------------------------------------------------------------------

@router.get("/status-board", response_model=FloorStatusBoard)
async def get_status_board(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FloorStatusBoard:
    """Return all active floors with their tables for the POS dine-in view."""
    await floor_service.reconcile_table_occupancy(db, current_user.tenant_id)
    await db.commit()
    floors = await floor_service.list_floors(db, current_user.tenant_id, active_only=True)
    return FloorStatusBoard(floors=floors)


# ---------------------------------------------------------------------------
# Floors CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=list[FloorWithTables])
async def list_floors(
    active_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FloorWithTables]:
    floors = await floor_service.list_floors(db, current_user.tenant_id, active_only)
    return [FloorWithTables.model_validate(f) for f in floors]


@router.get("/{floor_id}", response_model=FloorWithTables)
async def get_floor(
    floor_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FloorWithTables:
    floor = await floor_service.get_floor(db, floor_id, current_user.tenant_id)
    if floor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Floor not found")
    return FloorWithTables.model_validate(floor)


@router.post("", response_model=FloorWithTables, status_code=status.HTTP_201_CREATED)
async def create_floor(
    body: FloorCreate,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> FloorWithTables:
    floor = await floor_service.create_floor(db, current_user.tenant_id, body)
    await db.commit()
    return FloorWithTables.model_validate(floor)


@router.patch("/{floor_id}", response_model=FloorWithTables)
async def update_floor(
    floor_id: uuid.UUID,
    body: FloorUpdate,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> FloorWithTables:
    floor = await floor_service.get_floor(db, floor_id, current_user.tenant_id)
    if floor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Floor not found")
    floor = await floor_service.update_floor(db, floor, body)
    await db.commit()
    return FloorWithTables.model_validate(floor)


@router.delete("/{floor_id}", response_model=MessageResponse)
async def delete_floor(
    floor_id: uuid.UUID,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    floor = await floor_service.get_floor(db, floor_id, current_user.tenant_id)
    if floor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Floor not found")
    await floor_service.delete_floor(db, floor)
    await db.commit()
    return MessageResponse(message="Floor deleted")


# ---------------------------------------------------------------------------
# Tables CRUD
# ---------------------------------------------------------------------------

@router.get("/{floor_id}/tables", response_model=list[TableResponse])
async def list_tables(
    floor_id: uuid.UUID,
    active_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TableResponse]:
    tables = await floor_service.list_tables(
        db, current_user.tenant_id, floor_id=floor_id, active_only=active_only
    )
    return [TableResponse.model_validate(t) for t in tables]


@router.post("/tables", response_model=TableResponse, status_code=status.HTTP_201_CREATED)
async def create_table(
    body: TableCreate,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> TableResponse:
    # Verify floor exists and belongs to tenant
    floor = await floor_service.get_floor(db, body.floor_id, current_user.tenant_id)
    if floor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Floor not found")
    table = await floor_service.create_table(db, current_user.tenant_id, body)
    await db.commit()
    return TableResponse.model_validate(table)


@router.patch("/tables/{table_id}", response_model=TableResponse)
async def update_table(
    table_id: uuid.UUID,
    body: TableUpdate,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> TableResponse:
    table = await floor_service.get_table(db, table_id, current_user.tenant_id)
    if table is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Table not found")
    table = await floor_service.update_table(db, table, body)
    await db.commit()
    return TableResponse.model_validate(table)


@router.delete("/tables/{table_id}", response_model=MessageResponse)
async def delete_table(
    table_id: uuid.UUID,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    table = await floor_service.get_table(db, table_id, current_user.tenant_id)
    if table is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Table not found")
    await floor_service.delete_table(db, table)
    await db.commit()
    return MessageResponse(message="Table deleted")


# ---------------------------------------------------------------------------
# Bulk Position Update (floor editor drag-and-drop)
# ---------------------------------------------------------------------------

@router.put("/tables/positions", response_model=list[TableResponse])
async def bulk_update_positions(
    body: BulkTablePositionUpdate,
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> list[TableResponse]:
    """Batch update table positions from the floor editor."""
    tables = await floor_service.bulk_update_positions(db, current_user.tenant_id, body)
    await db.commit()
    return [TableResponse.model_validate(t) for t in tables]


# ---------------------------------------------------------------------------
# Table Status Update (POS operational — cashier can update)
# ---------------------------------------------------------------------------

@router.patch("/tables/{table_id}/status", response_model=TableResponse)
async def update_table_status(
    table_id: uuid.UUID,
    body: TableStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TableResponse:
    """Update table status (available/occupied/reserved/cleaning). Any authenticated user."""
    table = await floor_service.get_table(db, table_id, current_user.tenant_id)
    if table is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Table not found")
    # Only allow status update from this endpoint
    status_update = TableUpdate(status=body.status)
    table = await floor_service.update_table(db, table, status_update)
    await db.commit()
    return TableResponse.model_validate(table)
