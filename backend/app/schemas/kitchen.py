"""Pydantic schemas for the kitchen domain (KDS)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Station schemas
# ---------------------------------------------------------------------------

class StationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    display_order: int = Field(default=0)
    is_active: bool = Field(default=True)
    description: str | None = Field(None, max_length=255)


class StationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    display_order: int | None = None
    is_active: bool | None = None
    description: str | None = None


class StationResponse(BaseModel):
    id: uuid.UUID
    name: str
    display_order: int
    is_active: bool
    description: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Ticket item schemas
# ---------------------------------------------------------------------------

class TicketItemResponse(BaseModel):
    id: uuid.UUID
    order_item_id: uuid.UUID
    quantity: int
    # Denormalized from order_item for display
    item_name: str | None = None
    item_notes: str | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Ticket schemas
# ---------------------------------------------------------------------------

class TicketStatusUpdate(BaseModel):
    status: str = Field(
        ..., pattern=r"^(preparing|ready|served)$",
    )


class TicketResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    station_id: uuid.UUID
    status: str
    priority: int
    notes: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    served_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    # Nested
    order_number: str | None = None
    order_type: str | None = None
    items: list[TicketItemResponse] = []

    model_config = {"from_attributes": True}
