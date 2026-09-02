"""Pydantic schemas for the order domain.

All monetary amounts are in paisa (integer). Frontend converts to PKR for display.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------


class OrderItemModifierCreate(BaseModel):
    modifier_id: uuid.UUID
    name: str = Field(..., max_length=100)
    price_adjustment: int = Field(default=0, description="Price adjustment in paisa")


class OrderItemCreate(BaseModel):
    menu_item_id: uuid.UUID
    name: str = Field(..., max_length=200, description="Denormalized item name")
    quantity: int = Field(..., ge=1)
    unit_price: int = Field(
        ..., ge=0, description="Unit price in paisa (base + modifiers)"
    )
    modifiers: list[OrderItemModifierCreate] = Field(default_factory=list)
    notes: str | None = Field(None, max_length=500)


class OrderCreate(BaseModel):
    order_type: str = Field(..., pattern=r"^(dine_in|takeaway|call_center)$")
    table_id: uuid.UUID | None = None
    waiter_id: uuid.UUID | None = None
    customer_name: str | None = Field(None, max_length=255)
    customer_phone: str | None = Field(None, max_length=20)
    items: list[OrderItemCreate] = Field(..., min_length=1)
    notes: str | None = None
    # Which site made this sale, and which channel it came through. Both are
    # optional: a tenant that has never configured locations or channels sends
    # neither and keeps its pre-locations behaviour exactly. When omitted, the
    # location falls back to the tenant's default site so the sale still
    # carries a TRN on its tax invoice.
    location_id: uuid.UUID | None = None
    sales_channel_id: uuid.UUID | None = None
    # Charges added at the till, in minor units, outside the tax (Martin,
    # FZ LLC 2026-09-02: "option to add charges such as delivery fees"). Both
    # default to 0 so every existing client keeps sending exactly what it did.
    delivery_fee: int = Field(0, ge=0, le=1_000_000)
    service_fee: int = Field(0, ge=0, le=1_000_000)

    @model_validator(mode="after")
    def call_center_requires_phone(self) -> "OrderCreate":
        if self.order_type == "call_center" and not self.customer_phone:
            raise ValueError("customer_phone is required for call_center orders")
        return self


class OrderStatusUpdate(BaseModel):
    status: str = Field(
        ...,
        pattern=r"^(confirmed|in_kitchen|ready|served|completed)$",
    )


class OrderVoidRequest(BaseModel):
    reason: str = Field(
        ..., min_length=1, max_length=500, description="Mandatory reason for voiding"
    )
    auth_token: str | None = Field(
        None, description="Token from POST /auth/verify-password"
    )


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------


class OrderItemModifierResponse(BaseModel):
    id: uuid.UUID
    modifier_id: uuid.UUID
    name: str
    price_adjustment: int

    model_config = {"from_attributes": True}


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    menu_item_id: uuid.UUID
    name: str
    quantity: int
    unit_price: int
    total: int
    notes: str | None = None
    status: str
    modifiers: list[OrderItemModifierResponse] = []

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    """Full order detail with items."""

    id: uuid.UUID
    order_number: str
    order_type: str
    status: str
    payment_status: str
    table_id: uuid.UUID | None = None
    table_session_id: uuid.UUID | None = None
    table_number: int | None = None
    table_label: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_id: uuid.UUID | None = None
    waiter_id: uuid.UUID | None = None
    waiter_name: str | None = None
    subtotal: int
    tax_amount: int
    discount_amount: int
    # Charges outside the tax. 0 on every order that predates them.
    delivery_fee: int = 0
    service_fee: int = 0
    tip: int = 0
    total: int
    # Which sales channel (Careem, Deliveroo, ...) the sale came through, when
    # the cashier said so. The name is resolved in the route, not stored here.
    sales_channel_id: uuid.UUID | None = None
    sales_channel_name: str | None = None
    notes: str | None = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime | None = None
    items: list[OrderItemResponse] = []

    model_config = {"from_attributes": True}


class PaymentPreviewResponse(BaseModel):
    """Shows what the order total would be under each payment method's tax rate."""

    order_id: uuid.UUID
    subtotal: int
    cash_tax_rate_bps: int
    cash_tax_amount: int
    cash_total: int
    card_tax_rate_bps: int
    card_tax_amount: int
    card_total: int
    # Ride on top of either total, outside the tax.
    delivery_fee: int = 0
    service_fee: int = 0
    tip: int = 0


class OrderListResponse(BaseModel):
    """Lightweight order for list views (no nested items)."""

    id: uuid.UUID
    order_number: str
    order_type: str
    status: str
    payment_status: str
    table_id: uuid.UUID | None = None
    table_number: int | None = None
    table_label: str | None = None
    waiter_id: uuid.UUID | None = None
    waiter_name: str | None = None
    item_count: int = 0
    total: int
    sales_channel_id: uuid.UUID | None = None
    sales_channel_name: str | None = None
    created_at: datetime
    created_by: uuid.UUID

    model_config = {"from_attributes": True}
