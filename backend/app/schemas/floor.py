"""Pydantic schemas for the floor plan domain."""

import uuid

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Floor
# ---------------------------------------------------------------------------

class FloorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    display_order: int = Field(default=0)
    is_active: bool = Field(default=True)


class FloorUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    display_order: int | None = None
    is_active: bool | None = None


class FloorResponse(BaseModel):
    id: uuid.UUID
    name: str
    display_order: int
    is_active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------

class TableCreate(BaseModel):
    floor_id: uuid.UUID
    number: int = Field(..., ge=1)
    label: str | None = Field(None, max_length=50)
    capacity: int = Field(default=4, ge=1, le=50)
    pos_x: float = Field(default=0.0)
    pos_y: float = Field(default=0.0)
    width: float = Field(default=80.0, gt=0)
    height: float = Field(default=80.0, gt=0)
    rotation: float = Field(default=0.0, ge=0, lt=360)
    shape: str = Field(default="square", pattern=r"^(square|round|rectangle)$")
    is_active: bool = Field(default=True)


class TableUpdate(BaseModel):
    number: int | None = Field(None, ge=1)
    label: str | None = None
    capacity: int | None = Field(None, ge=1, le=50)
    pos_x: float | None = None
    pos_y: float | None = None
    width: float | None = Field(None, gt=0)
    height: float | None = Field(None, gt=0)
    rotation: float | None = Field(None, ge=0, lt=360)
    shape: str | None = Field(None, pattern=r"^(square|round|rectangle)$")
    status: str | None = Field(None, pattern=r"^(available|occupied|reserved|cleaning)$")
    is_active: bool | None = None


class TableResponse(BaseModel):
    id: uuid.UUID
    floor_id: uuid.UUID
    number: int
    label: str | None = None
    capacity: int
    pos_x: float
    pos_y: float
    width: float
    height: float
    rotation: float
    shape: str
    status: str
    is_active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Bulk position update (drag-and-drop editor)
# ---------------------------------------------------------------------------

class TablePositionUpdate(BaseModel):
    """Position data for a single table in a bulk update."""
    id: uuid.UUID
    pos_x: float
    pos_y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    rotation: float = Field(ge=0, lt=360)


class BulkTablePositionUpdate(BaseModel):
    """Batch update table positions from the floor editor."""
    tables: list[TablePositionUpdate] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Floor with tables (composite responses)
# ---------------------------------------------------------------------------

class FloorWithTables(FloorResponse):
    """Floor including all its tables."""
    tables: list[TableResponse] = []

    model_config = {"from_attributes": True}


class FloorStatusBoard(BaseModel):
    """All floors with tables — used by POS dine-in view."""
    floors: list[FloorWithTables]
