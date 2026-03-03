"""Pydantic schemas for report endpoints."""

from pydantic import BaseModel


class DiscountBreakdownEntry(BaseModel):
    source_type: str
    label: str
    count: int
    total: int  # paisa


class SalesSummary(BaseModel):
    total_revenue: int  # paisa
    total_orders: int
    avg_order_value: int  # paisa
    total_tax: int  # paisa
    total_discount: int  # paisa
    net_revenue: int  # total_revenue - total_discount
    cash_revenue: int = 0  # paisa — paid via cash
    card_revenue: int = 0  # paisa — paid via card
    other_revenue: int = 0  # paisa — mobile wallet, bank transfer, etc.
    dine_in_revenue: int
    dine_in_orders: int
    takeaway_revenue: int
    takeaway_orders: int
    call_center_revenue: int
    call_center_orders: int
    discount_breakdown: list[DiscountBreakdownEntry] = []


class ItemPerformanceEntry(BaseModel):
    menu_item_id: str
    name: str
    quantity_sold: int
    revenue: int  # paisa


class CategoryBreakdown(BaseModel):
    category_name: str
    revenue: int  # paisa
    order_count: int


class ItemPerformance(BaseModel):
    top_items: list[ItemPerformanceEntry]
    bottom_items: list[ItemPerformanceEntry]
    categories: list[CategoryBreakdown]


class HourlyBucket(BaseModel):
    hour: int  # 0-23
    order_count: int
    revenue: int  # paisa


class HourlyBreakdown(BaseModel):
    date: str
    buckets: list[HourlyBucket]


# ---------------------------------------------------------------------------
# Void Report (#13)
# ---------------------------------------------------------------------------


class VoidReasonEntry(BaseModel):
    reason: str
    count: int
    total_value: int  # paisa


class VoidUserEntry(BaseModel):
    user_id: str
    user_name: str
    count: int
    total_value: int  # paisa


class VoidReport(BaseModel):
    total_voids: int
    total_voided_value: int  # paisa
    by_reason: list[VoidReasonEntry]
    by_user: list[VoidUserEntry]


# ---------------------------------------------------------------------------
# Payment-Method Report (#19)
# ---------------------------------------------------------------------------


class PaymentMethodReportEntry(BaseModel):
    method: str
    method_code: str
    count: int
    total: int  # paisa


class PaymentMethodReport(BaseModel):
    entries: list[PaymentMethodReportEntry]
    total_collected: int  # paisa
