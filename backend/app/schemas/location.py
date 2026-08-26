"""Pydantic schemas for locations, per-location stock, transfers and channels."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

LocationType = Literal["production", "delivery", "retail"]
InvoiceFormat = Literal["a4_tax_invoice", "thermal_ticket"]
TransferStatus = Literal["draft", "in_transit", "received", "cancelled"]


# ---------------------------------------------------------------------------
# LOCATIONS
# ---------------------------------------------------------------------------


class LocationBase(BaseModel):
    name: str = Field(..., max_length=200)
    code: str = Field(..., max_length=30, description="Short handle, e.g. PROD")
    location_type: LocationType = "retail"

    # Legal identity, needed on an A4 tax invoice.
    legal_name: str | None = Field(None, max_length=300)
    tax_registration_number: str | None = Field(None, max_length=50)
    address_line1: str | None = Field(None, max_length=300)
    address_line2: str | None = Field(None, max_length=300)
    city: str | None = Field(None, max_length=120)
    country: str | None = Field(None, max_length=120)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=255)

    invoice_format: InvoiceFormat = "thermal_ticket"
    invoice_prefix: str = Field(default="INV", max_length=10)
    is_active: bool = True
    is_default: bool = False
    notes: str | None = None

    @model_validator(mode="after")
    def a4_invoices_need_a_legal_identity(self) -> "LocationBase":
        """A tax invoice without a legal name or TRN is not a tax invoice.

        Refusing this at the edge is deliberate: the alternative is discovering
        it when a customer rejects the first B2B invoice for being invalid.
        """
        if self.invoice_format == "a4_tax_invoice":
            missing = [
                field
                for field in ("legal_name", "tax_registration_number")
                if not getattr(self, field)
            ]
            if missing:
                raise ValueError(
                    "A location issuing A4 tax invoices needs "
                    + " and ".join(m.replace("_", " ") for m in missing)
                    + "."
                )
        return self


class LocationCreate(LocationBase):
    pass


class LocationUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    location_type: LocationType | None = None
    legal_name: str | None = Field(None, max_length=300)
    tax_registration_number: str | None = Field(None, max_length=50)
    address_line1: str | None = Field(None, max_length=300)
    address_line2: str | None = Field(None, max_length=300)
    city: str | None = Field(None, max_length=120)
    country: str | None = Field(None, max_length=120)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=255)
    invoice_format: InvoiceFormat | None = None
    invoice_prefix: str | None = Field(None, max_length=10)
    is_active: bool | None = None
    is_default: bool | None = None
    notes: str | None = None


class LocationResponse(LocationBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime


# ---------------------------------------------------------------------------
# SALES CHANNELS
# ---------------------------------------------------------------------------


class SalesChannelBase(BaseModel):
    name: str = Field(..., max_length=120)
    code: str = Field(..., max_length=40)
    commission_bps: int = Field(
        default=0, ge=0, le=10000,
        description="Commission in basis points. 1500 = 15.00%",
    )
    fixed_fee_minor: int = Field(
        default=0, ge=0, description="Flat per-order fee in minor units"
    )
    is_active: bool = True
    notes: str | None = None


class SalesChannelCreate(SalesChannelBase):
    pass


class SalesChannelUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    commission_bps: int | None = Field(None, ge=0, le=10000)
    fixed_fee_minor: int | None = Field(None, ge=0)
    is_active: bool | None = None
    notes: str | None = None


class SalesChannelResponse(SalesChannelBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime

    @property
    def commission_percent(self) -> float:
        return self.commission_bps / 100


# ---------------------------------------------------------------------------
# STOCK
# ---------------------------------------------------------------------------


class LocationStockRow(BaseModel):
    location_id: uuid.UUID
    location_name: str
    ingredient_id: uuid.UUID
    ingredient_name: str
    unit: str
    quantity: Decimal
    reorder_point: Decimal
    reorder_quantity: Decimal
    cost_per_unit: Decimal
    is_produced: bool
    is_low: bool


class StockMovementRow(BaseModel):
    """One line of the stock ledger, shaped for a human reading a history panel.

    `location_name` and `performed_by_name` are nullable and that is meaningful,
    not an oversight: a movement with no location predates the multi-site model,
    and one with no performer was done by the system rather than a person, which
    is exactly what consumption from an online order looks like.
    """

    id: uuid.UUID
    ingredient_id: uuid.UUID
    ingredient_name: str
    location_id: uuid.UUID | None
    location_name: str | None
    transaction_type: str
    quantity: Decimal
    unit: str
    balance_after: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    transaction_date: datetime
    performed_by_name: str | None
    notes: str | None
    reference_number: str | None
    order_id: uuid.UUID | None


class StockAdjustRequest(BaseModel):
    ingredient_id: uuid.UUID
    location_id: uuid.UUID | None = None
    quantity_delta: Decimal = Field(
        ..., description="Signed. Positive adds, negative removes."
    )
    reason: str = Field(..., max_length=500, description="Why -- required, not optional")

    @model_validator(mode="after")
    def non_zero(self) -> "StockAdjustRequest":
        if self.quantity_delta == 0:
            raise ValueError("A stock adjustment of zero is not an adjustment.")
        return self


class ReorderLevelRequest(BaseModel):
    ingredient_id: uuid.UUID
    location_id: uuid.UUID
    reorder_point: Decimal = Field(..., ge=0)
    reorder_quantity: Decimal = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# PRODUCTION
# ---------------------------------------------------------------------------


class ProductionRunRequest(BaseModel):
    recipe_id: uuid.UUID
    batches: Decimal = Field(..., gt=0, description="How many times to run the recipe")
    location_id: uuid.UUID | None = None
    reference_number: str | None = Field(None, max_length=100)


class ProductionRunResponse(BaseModel):
    reference_number: str
    recipe_id: uuid.UUID
    recipe_name: str
    location_id: uuid.UUID
    location_name: str
    batches: Decimal
    produced_ingredient_id: uuid.UUID
    produced_quantity: Decimal
    unit_cost: Decimal
    consumed: list[dict]


# ---------------------------------------------------------------------------
# TRANSFERS
# ---------------------------------------------------------------------------


class TransferLineCreate(BaseModel):
    ingredient_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0)


class TransferCreate(BaseModel):
    from_location_id: uuid.UUID
    to_location_id: uuid.UUID
    lines: list[TransferLineCreate] = Field(..., min_length=1)
    notes: str | None = None

    @model_validator(mode="after")
    def distinct_locations(self) -> "TransferCreate":
        if self.from_location_id == self.to_location_id:
            raise ValueError("A transfer needs two different locations.")
        return self


class TransferReceiveLine(BaseModel):
    item_id: uuid.UUID
    quantity_received: Decimal = Field(..., ge=0)


class TransferReceiveRequest(BaseModel):
    lines: list[TransferReceiveLine] = Field(
        default_factory=list,
        description="Short deliveries only. Omitted lines are received in full.",
    )


class TransferItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ingredient_id: uuid.UUID
    ingredient_name: str
    quantity_sent: Decimal
    quantity_received: Decimal | None
    unit: str
    unit_cost: Decimal


class TransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transfer_number: str
    from_location_id: uuid.UUID
    from_location_name: str
    to_location_id: uuid.UUID
    to_location_name: str
    status: TransferStatus
    notes: str | None
    sent_at: datetime | None
    received_at: datetime | None
    created_at: datetime
    items: list[TransferItemResponse]


# ---------------------------------------------------------------------------
# PROFITABILITY
# ---------------------------------------------------------------------------


class ProfitBucket(BaseModel):
    name: str
    orders: int
    revenue_minor: int
    product_cost_minor: int
    commission_minor: int
    net_profit_minor: int
    net_margin_pct: float


class ProfitabilityResponse(BaseModel):
    totals: ProfitBucket
    by_channel: list[ProfitBucket]
    by_location: list[ProfitBucket]


class LocationOrderRow(BaseModel):
    """One invoiceable sale at a location.

    A deliberately separate, additive read model: filtering the main orders
    endpoint by location would mean editing a code path a live restaurant
    depends on, for a screen only multi-location tenants use.
    """

    id: uuid.UUID
    order_number: str
    order_type: str
    status: str
    payment_status: str
    total_minor: int
    channel_name: str | None
    customer_name: str | None
    created_at: datetime
