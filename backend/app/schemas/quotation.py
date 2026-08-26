"""Pydantic schemas for back-office quotations.

🔴 Money is INTEGER MINOR UNITS (sales-side convention, matching orders and the
tax invoice). Prices INCLUDE VAT; `tax_minor` is the VAT contained in the
total, not an amount added to it.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# `expired` is never stored. It is derived from `valid_until` at read time and
# only ever appears on the way out.
QuotationStatus = Literal["draft", "sent", "accepted", "declined", "converted"]
QuotationDisplayStatus = Literal[
    "draft", "sent", "accepted", "declined", "converted", "expired"
]


class QuotationLineCreate(BaseModel):
    """A line is either a menu item, or free text with its own price."""

    menu_item_id: uuid.UUID | None = None
    name: str | None = Field(None, max_length=300)
    description: str | None = None
    quantity: int = Field(..., ge=1)
    unit_price_minor: int | None = Field(
        None, ge=0, description="Defaults to the menu item's current price"
    )

    @model_validator(mode="after")
    def needs_an_identity(self) -> "QuotationLineCreate":
        if self.menu_item_id is None and not (self.name or "").strip():
            raise ValueError(
                "A line that is not a menu item needs a description of its own."
            )
        if self.menu_item_id is None and self.unit_price_minor is None:
            raise ValueError(
                "A line that is not a menu item needs a price of its own."
            )
        return self


class QuotationCreate(BaseModel):
    customer_name: str = Field(..., max_length=200)
    lines: list[QuotationLineCreate] = Field(..., min_length=1)
    location_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    customer_phone: str | None = Field(None, max_length=50)
    customer_email: str | None = Field(None, max_length=255)
    customer_address: str | None = None
    customer_trn: str | None = Field(None, max_length=50)
    valid_until: date | None = Field(
        None, description="Defaults to 30 days from today"
    )
    tax_rate_bps: int | None = Field(
        None, ge=0, le=10000, description="Defaults to the restaurant's VAT rate"
    )
    discount_minor: int = Field(default=0, ge=0)
    notes: str | None = None
    terms: str | None = None


class QuotationUpdate(BaseModel):
    customer_name: str | None = Field(None, max_length=200)
    customer_phone: str | None = Field(None, max_length=50)
    customer_email: str | None = Field(None, max_length=255)
    customer_address: str | None = None
    customer_trn: str | None = Field(None, max_length=50)
    location_id: uuid.UUID | None = None
    valid_until: date | None = None
    tax_rate_bps: int | None = Field(None, ge=0, le=10000)
    discount_minor: int | None = Field(None, ge=0)
    notes: str | None = None
    terms: str | None = None
    lines: list[QuotationLineCreate] | None = Field(None, min_length=1)


class QuotationItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    menu_item_id: uuid.UUID | None
    name: str
    description: str | None
    quantity: int
    unit_price_minor: int
    line_total_minor: int
    display_order: int


class QuotationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    quote_number: str
    status: QuotationStatus
    # What to show a human: `expired` when the date has passed and nobody has
    # decided yet. Derived, never stored.
    display_status: QuotationDisplayStatus
    location_id: uuid.UUID | None
    location_name: str | None
    customer_id: uuid.UUID | None
    customer_name: str
    customer_phone: str | None
    customer_email: str | None
    customer_address: str | None
    customer_trn: str | None
    issue_date: date
    valid_until: date
    tax_rate_bps: int
    subtotal_minor: int
    discount_minor: int
    tax_minor: int
    total_minor: int
    notes: str | None
    terms: str | None
    sent_at: datetime | None
    sent_to_email: str | None
    email_send_count: int
    last_email_error: str | None
    decided_at: datetime | None
    decline_reason: str | None
    converted_order_id: uuid.UUID | None
    converted_at: datetime | None
    created_at: datetime
    items: list[QuotationItemResponse]


class QuotationSendRequest(BaseModel):
    to: str | None = Field(None, max_length=255)
    message: str | None = Field(None, max_length=2000)
    skip_email: bool = Field(
        default=False,
        description="Mark it sent without emailing, for one handed over in person.",
    )


class QuotationSendResponse(BaseModel):
    quotation: QuotationResponse
    email_sent: bool
    sent_to: str | None
    error: str | None = None


class QuotationDecision(BaseModel):
    accepted: bool
    reason: str | None = Field(
        None, max_length=500, description="Why, when it was declined"
    )


class QuotationConversion(BaseModel):
    quotation: QuotationResponse
    order_id: uuid.UUID
    order_number: str
