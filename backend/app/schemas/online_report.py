"""Schemas for OI-58's online-ordering-specific reports."""

from datetime import date, datetime

from pydantic import BaseModel


class PrepaidVsCodReport(BaseModel):
    date_from: date
    date_to: date
    prepaid_revenue: int  # paisa/pence -- card via Stripe Checkout
    prepaid_orders: int
    cod_revenue: int  # cash / pay-on-delivery
    cod_orders: int
    # OI-81: tips, split by the same prepaid/COD rule as the revenue above.
    prepaid_tips: int = 0  # tips charged with the card payment
    cod_tips: int = 0  # tips riding a cash bill, collected in person


class RejectedOrderEntry(BaseModel):
    order_number: str
    customer_name: str | None = None
    rejected_at: datetime
    rejection_reason: str
    total: int  # paisa/pence


class RejectedOrdersReport(BaseModel):
    date_from: date
    date_to: date
    count: int
    total_value: int  # paisa/pence
    orders: list[RejectedOrderEntry] = []


class StripeReconciliationRow(BaseModel):
    order_number: str
    db_payment_status: str
    db_captured_amount: int  # paisa/pence
    stripe_status: str | None = None
    stripe_amount_received: int | None = None
    matches: bool
    error: str | None = None


class StripeReconciliationReport(BaseModel):
    date_from: date
    date_to: date
    checked: int
    mismatches: int
    rows: list[StripeReconciliationRow] = []
