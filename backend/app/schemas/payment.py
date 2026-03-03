"""Pydantic schemas for payments and cash drawer sessions."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class PaymentMethodResponse(BaseModel):
    id: uuid.UUID
    code: str
    display_name: str
    is_active: bool
    requires_reference: bool
    sort_order: int

    model_config = {"from_attributes": True}


class PaymentResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    method_id: uuid.UUID
    kind: str
    status: str
    amount: int
    tendered_amount: int | None = None
    change_amount: int
    reference: str | None = None
    note: str | None = None
    processed_by: uuid.UUID
    processed_at: datetime
    created_at: datetime
    method: PaymentMethodResponse | None = None

    model_config = {"from_attributes": True}


class PaymentCreate(BaseModel):
    order_id: uuid.UUID
    method_code: str = Field(..., pattern=r"^(cash|card|mobile_wallet|bank_transfer)$")
    amount: int = Field(..., gt=0, description="Amount in paisa to apply against order")
    tendered_amount: int | None = Field(
        None, ge=0, description="Cash tendered amount in paisa"
    )
    reference: str | None = Field(None, max_length=120)
    note: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def validate_cash_tender(self) -> "PaymentCreate":
        if self.method_code == "cash":
            if self.tendered_amount is not None and self.tendered_amount < self.amount:
                raise ValueError("tendered_amount must be >= amount for cash payments")
        return self


class SplitPaymentAllocation(BaseModel):
    method_code: str = Field(..., pattern=r"^(cash|card|mobile_wallet|bank_transfer)$")
    amount: int = Field(..., gt=0)
    tendered_amount: int | None = Field(None, ge=0)
    reference: str | None = Field(None, max_length=120)


class SplitPaymentCreate(BaseModel):
    order_id: uuid.UUID
    allocations: list[SplitPaymentAllocation] = Field(..., min_length=2)
    note: str | None = Field(None, max_length=500)


class RefundCreate(BaseModel):
    payment_id: uuid.UUID
    amount: int = Field(..., gt=0)
    note: str | None = Field(None, max_length=500)


class PaymentSummary(BaseModel):
    order_id: uuid.UUID
    order_number: str
    order_total: int
    paid_amount: int
    refunded_amount: int
    due_amount: int
    payment_status: str
    payments: list[PaymentResponse]


class CashDrawerOpenRequest(BaseModel):
    opening_float: int = Field(default=0, ge=0)
    note: str | None = Field(None, max_length=500)


class CashDrawerCloseRequest(BaseModel):
    closing_balance_counted: int = Field(..., ge=0)
    note: str | None = Field(None, max_length=500)


# ---------------------------------------------------------------------------
# Session Payment schemas (P2)
# ---------------------------------------------------------------------------

class SessionPaymentOrderDue(BaseModel):
    order_id: uuid.UUID
    order_number: str
    order_total: int
    paid_amount: int
    due_amount: int
    payment_status: str


class SessionPaymentSummary(BaseModel):
    session_id: uuid.UUID
    table_id: uuid.UUID
    table_label: str | None = None
    order_count: int
    subtotal: int
    tax_amount: int
    discount_amount: int
    total: int
    paid_amount: int
    due_amount: int
    payment_status: str  # unpaid | partial | paid
    orders: list[SessionPaymentOrderDue]


class SessionPaymentCreate(BaseModel):
    method_code: str = Field(..., pattern=r"^(cash|card|mobile_wallet|bank_transfer)$")
    amount: int = Field(..., gt=0, description="Amount in paisa to apply against session due")
    tendered_amount: int | None = Field(None, ge=0)
    reference: str | None = Field(None, max_length=120)
    note: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def validate_cash_tender(self) -> "SessionPaymentCreate":
        if self.method_code == "cash":
            if self.tendered_amount is not None and self.tendered_amount < self.amount:
                raise ValueError("tendered_amount must be >= amount for cash payments")
        return self


class SessionSplitPaymentCreate(BaseModel):
    allocations: list[SplitPaymentAllocation] = Field(..., min_length=2)
    note: str | None = Field(None, max_length=500)


class SessionPaymentPreview(BaseModel):
    session_id: uuid.UUID
    subtotal: int
    cash_tax_rate_bps: int
    cash_tax_amount: int
    cash_total: int
    card_tax_rate_bps: int
    card_tax_amount: int
    card_total: int


class CashDrawerSessionResponse(BaseModel):
    id: uuid.UUID
    status: str
    opened_by: uuid.UUID
    opened_at: datetime
    opening_float: int
    closed_by: uuid.UUID | None = None
    closed_at: datetime | None = None
    closing_balance_expected: int | None = None
    closing_balance_counted: int | None = None
    note: str | None = None

    model_config = {"from_attributes": True}
