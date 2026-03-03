"""Table session endpoints for dine-in consolidation."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.table_session import (
    TableSessionBillSummary,
    TableSessionCloseRequest,
    TableSessionDetailResponse,
    TableSessionOpenRequest,
    TableSessionOrderSummary,
    TableSessionResponse,
)
from app.services import table_session_service

router = APIRouter(prefix="/table-sessions", tags=["table-sessions"])


def _to_response(session) -> TableSessionResponse:
    resp = TableSessionResponse.model_validate(session)
    if getattr(session, "table", None):
        resp.table_number = session.table.number
        resp.table_label = session.table.label
    resp.order_count = len(session.orders) if session.orders else 0
    return resp


def _to_detail(session) -> TableSessionDetailResponse:
    resp = TableSessionDetailResponse.model_validate(session)
    if getattr(session, "table", None):
        resp.table_number = session.table.number
        resp.table_label = session.table.label
    if session.orders:
        resp.orders = [
            TableSessionOrderSummary.model_validate(o) for o in session.orders
        ]
        resp.order_count = len(resp.orders)
    return resp


# ---------------------------------------------------------------------------
# Open Session (idempotent)
# ---------------------------------------------------------------------------

@router.post("/open", response_model=TableSessionResponse, status_code=status.HTTP_201_CREATED)
async def open_session(
    body: TableSessionOpenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TableSessionResponse:
    """Open a table session or return the existing open session for that table."""
    try:
        session = await table_session_service.open_session(
            db, current_user.tenant_id, current_user.id,
            body.table_id, body.notes,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    await db.commit()
    await db.refresh(session)
    return _to_response(session)


# ---------------------------------------------------------------------------
# Get Session by ID
# ---------------------------------------------------------------------------

@router.get("/{session_id}", response_model=TableSessionDetailResponse)
async def get_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TableSessionDetailResponse:
    session = await table_session_service.get_session(
        db, session_id, current_user.tenant_id
    )
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Table session not found")
    return _to_detail(session)


# ---------------------------------------------------------------------------
# Get Active Session by Table
# ---------------------------------------------------------------------------

@router.get("/table/{table_id}/active", response_model=TableSessionDetailResponse | None)
async def get_active_session_for_table(
    table_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TableSessionDetailResponse | None:
    session = await table_session_service.get_active_session_by_table(
        db, current_user.tenant_id, table_id
    )
    if session is None:
        return None
    return _to_detail(session)


# ---------------------------------------------------------------------------
# Close Session
# ---------------------------------------------------------------------------

@router.post("/{session_id}/close", response_model=TableSessionResponse)
async def close_session(
    session_id: uuid.UUID,
    body: TableSessionCloseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TableSessionResponse:
    try:
        session = await table_session_service.close_session(
            db, session_id, current_user.tenant_id,
            current_user.id, body.notes,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    await db.commit()
    await db.refresh(session)
    return _to_response(session)


# ---------------------------------------------------------------------------
# Bill Summary
# ---------------------------------------------------------------------------

@router.get("/{session_id}/bill-summary", response_model=TableSessionBillSummary)
async def get_bill_summary(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TableSessionBillSummary:
    try:
        summary = await table_session_service.get_bill_summary(
            db, session_id, current_user.tenant_id
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    return TableSessionBillSummary(**summary)
