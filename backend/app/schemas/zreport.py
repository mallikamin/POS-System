"""Z-Report / Daily Settlement response schemas."""

from datetime import date, datetime

from pydantic import BaseModel


class DrawerSummary(BaseModel):
    opening_float: int
    cash_in: int
    cash_out_change: int
    cash_out_refund: int
    expected_balance: int
    counted_balance: int | None = None
    variance: int | None = None
    session_status: str | None = None  # open | closed | None


class ChannelBreakdown(BaseModel):
    channel: str
    orders: int
    revenue: int


class PaymentMethodBreakdown(BaseModel):
    method: str
    count: int
    total: int
    payment_count: int = 0
    refund_count: int = 0
    gross_total: int = 0
    refund_total: int = 0
    net_total: int = 0


class StatusBreakdown(BaseModel):
    status: str
    count: int


class TopItem(BaseModel):
    name: str
    quantity: int
    revenue: int


class DiscountTypeBreakdown(BaseModel):
    source_type: str
    label: str
    count: int
    total: int  # paisa


class ZReport(BaseModel):
    date: date
    generated_at: datetime
    generated_by: str

    # Drawer
    drawer: DrawerSummary | None = None

    # Sales
    total_orders: int
    total_revenue: int
    total_tax: int
    total_discount: int
    net_revenue: int = 0  # total_revenue - total_discount
    settled_orders: int = 0
    fully_refunded_orders: int = 0
    net_tax: int = 0

    by_channel: list[ChannelBreakdown]
    by_payment_method: list[PaymentMethodBreakdown]
    by_status: list[StatusBreakdown]
    top_items: list[TopItem]
    discount_breakdown: list[DiscountTypeBreakdown] = []
