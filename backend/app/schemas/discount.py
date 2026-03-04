"""Pydantic schemas for discounts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Discount Type CRUD
# ---------------------------------------------------------------------------

class DiscountTypeCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    kind: str = Field(..., pattern=r"^(percent|fixed)$")
    value: int = Field(..., ge=0, description="Percent in basis points or fixed in paisa")
    is_active: bool = True


class DiscountTypeUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    kind: str | None = Field(None, pattern=r"^(percent|fixed)$")
    value: int | None = Field(None, ge=0)
    is_active: bool | None = None


class DiscountTypeResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    name: str
    kind: str
    value: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Apply / Remove Discount
# ---------------------------------------------------------------------------

class ApplyDiscountRequest(BaseModel):
    order_id: uuid.UUID | None = None
    table_session_id: uuid.UUID | None = None
    discount_type_id: uuid.UUID | None = Field(None, description="Use a catalog discount type")
    label: str | None = Field(None, max_length=200, description="Override label (auto-derived if using type)")
    source_type: str | None = Field(None, max_length=50, description="Override source_type (auto-derived if using type)")
    amount: int | None = Field(None, ge=0, description="Override amount in paisa (auto-calculated if percent type)")
    note: str | None = Field(None, max_length=500)
    manager_verify_token: str | None = Field(None, description="Required if discount exceeds approval threshold")


class OrderDiscountResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID | None = None
    table_session_id: uuid.UUID | None = None
    discount_type_id: uuid.UUID | None = None
    label: str
    source_type: str
    amount: int
    percent_bps: int
    note: str | None = None
    applied_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Discount summary for payment/receipt
# ---------------------------------------------------------------------------

class DiscountBreakdown(BaseModel):
    """Summary of discounts on an order."""
    order_id: uuid.UUID
    discounts: list[OrderDiscountResponse] = []
    total_discount: int = 0


class SessionDiscountBreakdown(BaseModel):
    """Summary of discounts on a table session."""
    session_id: uuid.UUID
    discounts: list[OrderDiscountResponse] = []
    total_discount: int = 0
