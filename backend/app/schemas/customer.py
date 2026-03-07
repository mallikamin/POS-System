"""Pydantic schemas for the customer domain (call-center channel)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(
        ...,
        min_length=7,
        max_length=20,
        pattern=r"^\d{7,20}$",
        description="Digits only, e.g. 03001234567",
    )
    email: str | None = Field(None, max_length=320)
    alt_contact: str | None = Field(None, max_length=50)
    default_address: str | None = Field(None, max_length=2000)
    city: str | None = Field(None, max_length=100)
    alt_address: str | None = Field(None, max_length=2000)
    alt_city: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=2000)


class CustomerUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    phone: str | None = Field(
        None,
        min_length=7,
        max_length=20,
        pattern=r"^\d{7,20}$",
    )
    email: str | None = None
    alt_contact: str | None = None
    default_address: str | None = None
    city: str | None = None
    alt_address: str | None = None
    alt_city: str | None = None
    notes: str | None = None
    risk_flag: str | None = Field(None, pattern=r"^(normal|high|blocked)$")


class CustomerResponse(BaseModel):
    id: uuid.UUID
    name: str
    phone: str
    email: str | None = None
    alt_contact: str | None = None
    default_address: str | None = None
    city: str | None = None
    alt_address: str | None = None
    alt_city: str | None = None
    notes: str | None = None
    order_count: int
    total_spent: int = 0
    last_order_at: datetime | None = None
    risk_flag: str = "normal"
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CustomerOrderHistoryItem(BaseModel):
    """Lightweight order summary for customer history."""

    id: uuid.UUID
    order_number: str
    order_type: str
    status: str
    payment_status: str
    total: int
    items_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}
