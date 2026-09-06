"""Pydantic schemas for operating expenses (Martin M10).

🔴 Money is in MINOR UNITS, matching the inventory and procurement modules:
`amount_minor` of 850 is 8.50 AED. Nothing here multiplies or divides by 100.

🔴 No response model below carries a field default. A hand-built response with
defaults answers with a plausible wrong number when the builder forgets a field,
which is how the goods-receipt conversion reported 1 while the database held 400
(ERROR_LOG, 2026-09-04). A field that can genuinely be absent is typed `| None`
and passed explicitly.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, PlainSerializer

# Same reason as every other module in this codebase: Pydantic v2 serialises a
# `Decimal` to a JSON string, and the frontend types these as `number`.
Num = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float, when_used="json"),
]

ExpenseStatus = Literal["draft", "unpaid", "paid"]


# ---------------------------------------------------------------------------
# CATEGORIES
# ---------------------------------------------------------------------------


class ExpenseCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    notes: str | None = None


class ExpenseCategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    sort_order: int | None = None
    is_active: bool | None = None
    notes: str | None = None


class ExpenseCategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    sort_order: int
    is_active: bool
    notes: str | None
    expense_count: int


# ---------------------------------------------------------------------------
# EXPENSES
# ---------------------------------------------------------------------------


class ExpenseCreate(BaseModel):
    expense_date: date
    payee: str = Field(..., min_length=1, max_length=200)
    amount_minor: Num = Field(..., ge=0)
    # The VAT contained IN `amount_minor`, not added to it. The service refuses
    # a tax larger than the total, and the database refuses it again.
    tax_minor: Num = Field(default=Decimal("0"), ge=0)
    category_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    description: str | None = None
    reference_number: str | None = Field(None, max_length=100)
    status: ExpenseStatus = "unpaid"
    payment_method: str | None = Field(None, max_length=50)
    paid_on: date | None = None
    notes: str | None = None


class ExpenseUpdate(BaseModel):
    expense_date: date | None = None
    payee: str | None = Field(None, min_length=1, max_length=200)
    amount_minor: Num | None = Field(None, ge=0)
    tax_minor: Num | None = Field(None, ge=0)
    category_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    description: str | None = None
    reference_number: str | None = Field(None, max_length=100)
    status: ExpenseStatus | None = None
    payment_method: str | None = Field(None, max_length=50)
    paid_on: date | None = None
    notes: str | None = None


class ExpenseAttachmentResponse(BaseModel):
    id: uuid.UUID
    media_id: uuid.UUID
    filename: str | None
    content_type: str
    size_bytes: int
    # Routed through the expenses router, not /media/{id}: an invoice for rent
    # or salaries needs a token, and /media is deliberately unauthenticated so
    # an <img> tag can fetch a menu photograph.
    url: str


class ExpenseResponse(BaseModel):
    id: uuid.UUID
    expense_date: date
    payee: str
    description: str | None
    reference_number: str | None
    amount_minor: Num
    tax_minor: Num
    net_minor: Num
    status: str
    payment_method: str | None
    paid_on: date | None
    notes: str | None
    category_id: uuid.UUID | None
    category_name: str | None
    location_id: uuid.UUID | None
    location_name: str | None
    recorded_by: uuid.UUID | None
    recorded_by_name: str | None
    created_at: datetime
    attachments: list[ExpenseAttachmentResponse]


# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------


class ExpenseCategoryTotal(BaseModel):
    category_id: uuid.UUID | None
    category_name: str
    total_minor: Num
    expense_count: int


class ExpenseSummaryResponse(BaseModel):
    date_from: date | None
    date_to: date | None
    location_id: uuid.UUID | None
    total_minor: Num
    tax_total_minor: Num
    net_minor: Num
    unpaid_minor: Num
    expense_count: int
    by_category: list[ExpenseCategoryTotal]
