"""Schemas for the PUBLIC, UNAUTHENTICATED storefront API.

⚠️ THE CENTRAL RULE OF THIS FILE ⚠️

    The browser sends IDs and quantities. It NEVER sends prices.

The authenticated POS schema (`app/schemas/order.py`) accepts `unit_price` from
the client. That is defensible for a till operated by trusted staff on the shop
floor. On an endpoint anyone on the internet can POST to, it is a
"set your own price" button, so this module deliberately has no price field
anywhere in its request models. Every amount on the resulting order is computed
by the server from its own menu rows.

If you ever find yourself adding a price to a request schema here, stop.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Public menu (response only)
# ---------------------------------------------------------------------------


class PublicModifier(BaseModel):
    id: uuid.UUID
    name: str
    price_adjustment: int

    model_config = {"from_attributes": True}


class PublicModifierGroup(BaseModel):
    id: uuid.UUID
    name: str
    required: bool
    min_selections: int
    max_selections: int = Field(description="0 means unlimited")
    modifiers: list[PublicModifier] = []

    model_config = {"from_attributes": True}


class PublicMenuItem(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    price: int
    image_url: str | None = None
    modifier_groups: list[PublicModifierGroup] = []

    model_config = {"from_attributes": True}


class PublicCategory(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    display_order: int
    items: list[PublicMenuItem] = []

    model_config = {"from_attributes": True}


class PublicMenuResponse(BaseModel):
    """Only active categories, available items and available modifiers.

    Anything unavailable is omitted entirely rather than returned with a flag,
    so an out-of-stock item cannot be ordered by a stale browser tab.
    """

    currency: str
    categories: list[PublicCategory] = []


# ---------------------------------------------------------------------------
# Order placement (request)
# ---------------------------------------------------------------------------


class PublicOrderItemRequest(BaseModel):
    """One basket line. IDs and a quantity. No prices, no names.

    `extra="forbid"` is load-bearing, not tidiness. Pydantic's default is to
    ignore unknown fields, so a client posting `unit_price` would be silently
    ignored -- safe, but it leaves the caller believing the price was accepted
    and leaves the next developer unsure whether it was. Forbidding it turns
    the rule at the top of this file into a 422 that says so out loud.
    """

    model_config = {"extra": "forbid"}

    menu_item_id: uuid.UUID
    quantity: int = Field(..., ge=1, le=99)
    modifier_ids: list[uuid.UUID] = Field(default_factory=list, max_length=25)
    notes: str | None = Field(None, max_length=300)

    @field_validator("modifier_ids")
    @classmethod
    def no_duplicate_modifiers(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(v)) != len(v):
            raise ValueError("duplicate modifier_ids in one line")
        return v


class PublicOrderCreate(BaseModel):
    service_type: str = Field(..., pattern=r"^(collection|delivery)$")
    customer_name: str = Field(..., min_length=1, max_length=120)
    customer_phone: str = Field(..., min_length=7, max_length=20)
    customer_email: str | None = Field(None, max_length=320)

    items: list[PublicOrderItemRequest] = Field(..., min_length=1, max_length=60)
    notes: str | None = Field(None, max_length=500)

    # The customer's stated INTENT, chosen on the checkout page before this
    # request is even sent. Never used to decide whether money actually moves
    # -- Stripe's own state (checked via a separate `/checkout-session` call
    # made only after this one) is what governs that. This exists purely so
    # the "order received" email, which fires immediately on creation and
    # therefore before any Stripe interaction has happened, can say "prepaid"
    # rather than the misleading default "payable on delivery" for someone who
    # is about to be sent to Stripe. See `email_service._payment_status_text`.
    payment_method: Literal["cash", "card"] = "cash"

    # Delivery only. The AREA is sent, never the fee -- the server looks the fee
    # up. Chick Shack prices delivery by village (Garelochhead GBP 3, Arrochar
    # GBP 15) and most of those share one postcode prefix, so the area is the
    # only thing that can be trusted to derive a fee from.
    delivery_area_id: str | None = Field(None, max_length=60)
    delivery_address: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def delivery_requires_area_and_address(self) -> "PublicOrderCreate":
        if self.service_type == "delivery":
            if not self.delivery_area_id:
                raise ValueError("delivery_area_id is required for delivery orders")
            if not self.delivery_address:
                raise ValueError("delivery_address is required for delivery orders")
        return self


# ---------------------------------------------------------------------------
# Order placement (response)
# ---------------------------------------------------------------------------


class PublicOrderLine(BaseModel):
    name: str
    quantity: int
    unit_price: int
    total: int
    modifiers: list[str] = []


class PublicOrderResponse(BaseModel):
    """What the customer is shown after placing an order.

    Deliberately thin. It carries no internal IDs beyond the order's own, and
    no status the customer cannot act on.
    """

    id: uuid.UUID
    order_number: str
    status: str
    payment_status: str
    service_type: str
    customer_name: str
    lines: list[PublicOrderLine] = []
    subtotal: int
    tax_amount: int
    service_fee: int
    delivery_fee: int
    total: int
    currency: str
    eta_minutes: int | None = None
    created_at: datetime


class PublicOrderStatusResponse(BaseModel):
    """Polled by the customer's confirmation page while they wait."""

    order_number: str
    status: str
    accepted: bool
    rejected: bool
    rejection_reason: str | None = None
    eta_minutes: int | None = None
    # The rest of the journey, so the page can say "on its way" rather than
    # sitting on "confirmed" until the food arrives.
    service_type: str = "collection"
    ready: bool = False
    completed: bool = False
    paid: bool = False


# ---------------------------------------------------------------------------
# The merchant queue -- the shop's own view, NOT the customer's
# ---------------------------------------------------------------------------


class MerchantOrderSummary(BaseModel):
    """One card on the shop's order-queue tablet.

    Deliberately richer than `PublicOrderResponse`. That model is what we hand
    the customer and it withholds the phone number, the delivery address and
    the order notes. This one is the shop's own view of its own order, so it
    carries all three -- the address is the entire point of a delivery, and the
    phone number is how the shop resolves a problem order.

    Which is precisely why the endpoint returning this is authenticated. If you
    are tempted to expose it unauthenticated so the storefront can reuse it,
    stop: this is a list of names, phone numbers and home addresses.
    """

    id: uuid.UUID
    order_number: str
    status: str
    payment_status: str
    # Whether a card checkout was ever started for this order at all --
    # distinguishes "genuinely unpaid, collect cash" from "card payment
    # still processing", which `payment_status` alone cannot: both read
    # `unpaid` until the money actually lands. See OI-61.
    is_card_order: bool
    service_type: str
    placed_at: datetime

    customer_name: str
    customer_phone: str | None = None
    delivery_address: str | None = None
    delivery_area: str | None = None
    notes: str | None = None

    lines: list[PublicOrderLine] = []
    subtotal: int
    tax_amount: int
    service_fee: int
    delivery_fee: int
    total: int
    currency: str

    accepted_at: datetime | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None
    eta_minutes: int | None = None


class MerchantQueueResponse(BaseModel):
    state: str
    count: int
    total_count: int
    offset: int
    limit: int
    sort: Literal["asc", "desc"]
    orders: list[MerchantOrderSummary] = []
