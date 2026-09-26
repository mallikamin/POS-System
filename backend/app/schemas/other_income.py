"""Pydantic schemas for other income (Danny's D-63). Money in integer minor units."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

IncomeMethod = Literal["cash", "bank"]


class IncomeCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class IncomeCategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    sort_order: int
    is_active: bool
    income_count: int


class OtherIncomeCreate(BaseModel):
    received_on: date
    payer: str = Field(..., min_length=1, max_length=200)
    amount_minor: int = Field(..., gt=0)
    method: IncomeMethod = "cash"
    category_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    description: str | None = None
    reference_number: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class OtherIncomeUpdate(BaseModel):
    received_on: date | None = None
    payer: str | None = Field(default=None, min_length=1, max_length=200)
    amount_minor: int | None = Field(default=None, gt=0)
    method: IncomeMethod | None = None
    category_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    description: str | None = None
    reference_number: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class OpeningBalanceSet(BaseModel):
    """D-62: cash in hand at the START of `as_of`. Cash only."""

    as_of: date
    cash_minor: int = Field(..., ge=0)
    notes: str | None = Field(default=None, max_length=500)


class OpeningBalanceResponse(BaseModel):
    as_of: date
    cash_minor: int
    notes: str | None
    recorded_by_name: str | None
    updated_at: datetime


class OtherIncomeResponse(BaseModel):
    id: uuid.UUID
    received_on: date
    payer: str
    amount_minor: int
    method: IncomeMethod
    category_id: uuid.UUID | None
    category_name: str | None
    location_id: uuid.UUID | None
    location_name: str | None
    description: str | None
    reference_number: str | None
    notes: str | None
    recorded_by_name: str | None
    created_at: datetime
