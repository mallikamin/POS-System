"""Pydantic schemas for table sessions (dine-in consolidation)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------


class TableSessionOpenRequest(BaseModel):
    table_id: uuid.UUID
    waiter_id: uuid.UUID | None = None
    notes: str | None = Field(None, max_length=500)


class TableSessionCloseRequest(BaseModel):
    notes: str | None = Field(None, max_length=500)


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------


class TableSessionOrderSummary(BaseModel):
    """Lightweight order info within a session."""

    id: uuid.UUID
    order_number: str
    status: str
    payment_status: str
    subtotal: int
    tax_amount: int
    discount_amount: int
    total: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TableSessionResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    table_id: uuid.UUID
    table_number: int | None = None
    table_label: str | None = None
    status: str
    opened_by: uuid.UUID
    opened_at: datetime
    closed_by: uuid.UUID | None = None
    closed_at: datetime | None = None
    assigned_waiter_id: uuid.UUID | None = None
    assigned_waiter_name: str | None = None
    notes: str | None = None
    order_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class TableSessionDetailResponse(TableSessionResponse):
    """Session with nested orders."""

    orders: list[TableSessionOrderSummary] = []


class TableSessionBillSummary(BaseModel):
    """Consolidated bill for all orders in a session."""

    session_id: uuid.UUID
    table_id: uuid.UUID
    table_number: int | None = None
    table_label: str | None = None
    status: str
    subtotal: int = 0
    tax_amount: int = 0
    discount_amount: int = 0
    total: int = 0
    paid_amount: int = 0
    due_amount: int = 0
    order_count: int = 0
    orders: list[TableSessionOrderSummary] = []
