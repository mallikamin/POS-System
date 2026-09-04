"""Pydantic schemas for suppliers, purchase orders and goods receipts.

🔴 Every `*_minor` field is in MINOR UNITS (200 = 2.00 AED), matching
`Ingredient.cost_per_unit` and the rest of the inventory module. Nothing in the
API layer multiplies or divides by 100; the frontend formats for display.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, model_validator

PurchaseOrderStatus = Literal[
    "draft", "sent", "partially_received", "received", "cancelled"
]
ReceiptSource = Literal["manual", "ocr"]


# ---------------------------------------------------------------------------
# SUPPLIERS
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Decimal on the wire
# ---------------------------------------------------------------------------
# Pydantic v2 serialises `Decimal` to a JSON **string**, not a number, while the
# frontend types every one of these fields as `number` and does arithmetic on
# them. That mismatch took `/admin/ingredients` down completely in UAT
# (`current_stock.toFixed is not a function`, F14); the schemas here carry the
# same latent fault on the stock, supplier, purchase-order, receiving and
# order-planner screens, several of which only survive because JS coerces
# strings in `*`, `/` and `>`.
#
# `Num` serialises as a JSON number and leaves VALIDATION untouched -- inbound
# parsing still goes through `Decimal`, so request precision and every
# `ge`/`gt` constraint are unchanged, and no money is computed in float on the
# server. Only the outbound representation moves, and it moves to what the
# client already assumed.
Num = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float, when_used="json"),
]


class SupplierBase(BaseModel):
    name: str = Field(..., max_length=200)
    code: str = Field(..., max_length=30, description="Short handle, e.g. ALMAYA")
    contact_name: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    address_line1: str | None = Field(None, max_length=300)
    address_line2: str | None = Field(None, max_length=300)
    city: str | None = Field(None, max_length=120)
    country: str | None = Field(None, max_length=120)
    payment_terms: str | None = Field(None, max_length=200)
    tax_registration_number: str | None = Field(None, max_length=50)
    lead_time_days: int = Field(default=0, ge=0, le=365)
    is_active: bool = True
    notes: str | None = None


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    contact_name: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    address_line1: str | None = Field(None, max_length=300)
    address_line2: str | None = Field(None, max_length=300)
    city: str | None = Field(None, max_length=120)
    country: str | None = Field(None, max_length=120)
    payment_terms: str | None = Field(None, max_length=200)
    tax_registration_number: str | None = Field(None, max_length=50)
    lead_time_days: int | None = Field(None, ge=0, le=365)
    is_active: bool | None = None
    notes: str | None = None


class SupplierResponse(SupplierBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    # Filled by the list endpoint from one grouped query, not per-row.
    order_count: int = 0
    total_spend_minor: Num = Decimal("0")


# ---------------------------------------------------------------------------
# SUPPLIER CATALOGUE
# ---------------------------------------------------------------------------


class SupplierItemUpsert(BaseModel):
    ingredient_id: uuid.UUID
    supplier_sku: str | None = Field(None, max_length=100)
    supplier_item_name: str | None = Field(None, max_length=300)
    last_price_minor: Num = Field(default=Decimal("0"), ge=0)
    pack_size: Num = Field(default=Decimal("0"), ge=0)
    minimum_order_quantity: Num = Field(default=Decimal("0"), ge=0)
    lead_time_days: int | None = Field(None, ge=0, le=365)
    is_preferred: bool = False
    is_active: bool = True
    notes: str | None = None


class SupplierItemRow(BaseModel):
    id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    ingredient_id: uuid.UUID
    ingredient_name: str
    ingredient_image_url: str | None = None
    unit: str
    supplier_sku: str | None
    supplier_item_name: str | None
    last_price_minor: Num
    last_purchased_at: datetime | None
    pack_size: Num
    minimum_order_quantity: Num
    lead_time_days: int | None
    is_preferred: bool
    is_active: bool
    notes: str | None


class SupplierPurchaseRow(BaseModel):
    """One line of a supplier's purchase history (Martin's Section 5.1)."""

    id: uuid.UUID
    po_number: str
    status: PurchaseOrderStatus
    location_id: uuid.UUID
    location_name: str
    expected_date: date | None
    total_minor: Num
    sent_at: datetime | None
    fully_received_at: datetime | None
    created_at: datetime


# ---------------------------------------------------------------------------
# PURCHASE ORDERS
# ---------------------------------------------------------------------------


class PurchaseOrderLineCreate(BaseModel):
    ingredient_id: uuid.UUID
    quantity_ordered: Num = Field(..., gt=0)
    # Omitted means "use what we last paid this supplier, else the ingredient's
    # own cost". MINOR UNITS when supplied.
    unit_price_minor: Num | None = Field(None, ge=0)
    supplier_sku: str | None = Field(None, max_length=100)
    notes: str | None = None


class PurchaseOrderCreate(BaseModel):
    supplier_id: uuid.UUID
    location_id: uuid.UUID
    lines: list[PurchaseOrderLineCreate] = Field(..., min_length=1)
    tax_bps: int = Field(default=0, ge=0, le=10000, description="500 = 5.00% VAT")
    expected_date: date | None = None
    notes: str | None = None
    delivery_instructions: str | None = None


class PurchaseOrderUpdate(BaseModel):
    """Draft-only edit. Lines are replaced wholesale when supplied."""

    expected_date: date | None = None
    tax_bps: int | None = Field(None, ge=0, le=10000)
    notes: str | None = None
    delivery_instructions: str | None = None
    lines: list[PurchaseOrderLineCreate] | None = Field(None, min_length=1)


class PurchaseOrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ingredient_id: uuid.UUID
    ingredient_name: str
    ingredient_image_url: str | None = None
    # Counted and priced in `unit`, which is the ingredient's PURCHASE unit
    # when it has one (Martin M8). Two cans, not eight hundred grams.
    quantity_ordered: Num
    quantity_received: Num
    quantity_outstanding: Num
    unit: str
    # Stocking units in one `unit`, snapshotted when the line was written.
    # 1 whenever the ingredient is bought in the unit it is stocked in.
    #
    # REQUIRED, with no default, on purpose. It was written with `= 1` first
    # and `_receipt_out` in the routes forgot to pass it, so every goods
    # receipt reported a conversion of 1 while the database held 400 -- caught
    # only by reading the raw row on 2026-09-04. A default here turns a missing
    # field into a plausible wrong number instead of an error.
    units_per_purchase_unit: Num
    # The stocking unit, so a screen can say "2 cans (800 g)" without a second
    # round trip for the ingredient.
    stock_unit: str | None = None
    unit_price_minor: Num
    line_total_minor: Num
    supplier_sku: str | None
    notes: str | None


class GoodsReceiptLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    purchase_order_item_id: uuid.UUID
    ingredient_id: uuid.UUID
    quantity_received: Num
    unit: str
    # Required, no default. See the note on `PurchaseOrderItemResponse`.
    units_per_purchase_unit: Num
    unit_price_minor: Num


class GoodsReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    receipt_number: str
    purchase_order_id: uuid.UUID
    source: ReceiptSource
    document_reference: str | None
    received_at: datetime
    notes: str | None
    lines: list[GoodsReceiptLineResponse]


class PurchaseOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    po_number: str
    supplier_id: uuid.UUID
    supplier_name: str
    supplier_email: str | None
    location_id: uuid.UUID
    location_name: str
    status: PurchaseOrderStatus
    expected_date: date | None
    tax_bps: int
    subtotal_minor: Num
    tax_minor: Num
    total_minor: Num
    notes: str | None
    delivery_instructions: str | None
    sent_at: datetime | None
    sent_to_email: str | None
    email_send_count: int
    last_email_error: str | None
    fully_received_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    items: list[PurchaseOrderItemResponse]
    receipts: list[GoodsReceiptResponse] = Field(default_factory=list)


class PurchaseOrderSendRequest(BaseModel):
    """Email the PO to the supplier.

    `to` overrides the supplier's stored address for this send only, for the
    common case of a different orders@ mailbox.
    """

    to: str | None = Field(None, max_length=255)
    cc_self: bool = Field(
        default=False,
        description="Blind-copy the location's own email address, when it has one.",
    )
    message: str | None = Field(
        None, max_length=2000, description="Optional note above the order"
    )
    skip_email: bool = Field(
        default=False,
        description=(
            "Mark the order as sent without emailing it, for an order placed by "
            "phone or handed over as a printout."
        ),
    )


class PurchaseOrderSendResponse(BaseModel):
    purchase_order: PurchaseOrderResponse
    email_sent: bool
    sent_to: str | None
    error: str | None = None


class GoodsReceiptLineRequest(BaseModel):
    purchase_order_item_id: uuid.UUID
    quantity_received: Num = Field(..., gt=0)
    # What was actually charged, when it differs from the order. MINOR UNITS.
    unit_price_minor: Num | None = Field(None, ge=0)


class GoodsReceiptRequest(BaseModel):
    lines: list[GoodsReceiptLineRequest] = Field(..., min_length=1)
    document_reference: str | None = Field(
        None, max_length=120, description="The supplier's delivery note number"
    )
    source: ReceiptSource = "manual"
    notes: str | None = None

    @model_validator(mode="after")
    def no_duplicate_lines(self) -> "GoodsReceiptRequest":
        seen = {line.purchase_order_item_id for line in self.lines}
        if len(seen) != len(self.lines):
            raise ValueError(
                "The same order line appears twice on one receipt; combine the "
                "quantities."
            )
        return self


class GoodsReceiptResult(BaseModel):
    purchase_order: PurchaseOrderResponse
    receipt: GoodsReceiptResponse


# ==========================================================================
# ORDERING SUGGESTION
#
# 🔴 Every quantity in these responses is COMPUTED by
# `purchase_suggestion_service`, never generated by a model. Only `advice` is
# model-written, and it is prose.
# ==========================================================================


class ProductionTarget(BaseModel):
    recipe_id: uuid.UUID
    batches: Num = Field(
        ..., gt=0, description="How many times to run this recipe over the period"
    )


class SuggestionRequest(BaseModel):
    location_id: uuid.UUID | None = None
    targets: list[ProductionTarget] = Field(..., min_length=1)
    days_until_production: int | None = Field(
        None, ge=0, le=365, description="Used to judge lead times"
    )
    include_advice: bool = Field(
        default=False,
        description=(
            "Ask the AI advisor to review the computed plan. The plan itself is "
            "identical either way."
        ),
    )


class SuggestionTargetRow(BaseModel):
    recipe_id: uuid.UUID
    recipe_name: str
    batches: Num
    yield_servings: Num
    produces: str


class ProductionPlanRow(BaseModel):
    """A sub-recipe that has to be MADE, not bought."""

    ingredient_id: uuid.UUID
    ingredient_name: str
    unit: str
    quantity_to_make: Num


class SuggestionLine(BaseModel):
    ingredient_id: uuid.UUID
    ingredient_name: str
    unit: str
    required: Num
    on_hand: Num
    on_order: Num
    shortfall: Num
    suggested_quantity: Num
    unit_price_minor: Num
    estimated_cost_minor: Num
    supplier_id: uuid.UUID | None
    supplier_name: str | None
    lead_time_days: int | None
    pack_size: Num
    has_supplier: bool


class SuggestionBasket(BaseModel):
    """One supplier's worth of the plan: one purchase order, ready to raise."""

    supplier_id: uuid.UUID
    supplier_name: str
    lead_time_days: int | None
    lines: list[SuggestionLine]
    estimated_total_minor: Num


class PlanAdviceOut(BaseModel):
    summary: str
    risks: list[str] = Field(default_factory=list)
    order_first: list[str] = Field(default_factory=list)


class SuggestionResponse(BaseModel):
    location_id: uuid.UUID
    location_name: str
    targets: list[SuggestionTargetRow]
    production_plan: list[ProductionPlanRow]
    lines: list[SuggestionLine]
    baskets: list[SuggestionBasket]
    unsourced: list[SuggestionLine]
    estimated_total_minor: Num
    advice: PlanAdviceOut | None = None
    # Populated when advice was asked for and could not be produced. The plan
    # is still complete and correct; only the commentary is missing.
    advice_error: str | None = None


# ==========================================================================
# OCR GOODS RECEIVING
# ==========================================================================


class ScannedLine(BaseModel):
    """A PROPOSED receipt line. Nothing has been booked into stock."""

    purchase_order_item_id: uuid.UUID
    ingredient_name: str
    unit: str
    quantity_received: Num
    unit_price_minor: Num | None
    ordered_quantity: Num
    outstanding_quantity: Num
    document_text: str
    confidence: str


class UnmatchedLine(BaseModel):
    document_text: str
    quantity: str | None
    confidence: str


class ScanResult(BaseModel):
    document_reference: str | None
    supplier_name: str | None
    lines: list[ScannedLine]
    unmatched: list[UnmatchedLine]
    duplicate_line_ids: list[uuid.UUID]
    notes: str | None


# ==========================================================================
# AI USAGE
# ==========================================================================


class AIUsageKindRow(BaseModel):
    """One row of the AI spend breakdown.

    F28: this was `list[dict]` on `AIUsageSummary`, so the `Decimal` cost inside
    it bypassed the `Num` serializer entirely and went out as a JSON **string**
    while the sibling `estimated_cost_usd` on the parent went out as a number.
    An untyped container is a hole in the contract: the schema cannot describe
    what it does not name.
    """

    kind: str
    calls: int
    tokens: int
    estimated_cost_usd: Num
    failures: int


class AIUsageSummary(BaseModel):
    """What the AI features have cost this restaurant. Estimated, not invoiced."""

    date_from: date
    date_to: date
    calls: int
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    estimated_cost_usd: Num
    by_kind: list[AIUsageKindRow]
    today_calls: int
    today_tokens: int
    # Today's spend and the ceiling it is measured against. This is the pair an
    # owner reads; the call and token caps are engineering backstops.
    today_cost_usd: Num
    daily_call_cap: int
    daily_token_cap: int
    daily_cost_cap_usd: Num


class ReceivingHistoryRow(BaseModel):
    id: uuid.UUID
    receipt_number: str
    purchase_order_id: uuid.UUID
    po_number: str
    source: ReceiptSource
    document_reference: str | None
    received_at: datetime
    line_count: int
    total_minor: Num
    notes: str | None
