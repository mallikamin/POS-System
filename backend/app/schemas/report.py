"""Pydantic schemas for report endpoints."""

from pydantic import BaseModel


class DiscountBreakdownEntry(BaseModel):
    source_type: str
    label: str
    count: int
    total: int  # paisa


class PeriodHeadline(BaseModel):
    """The comparison period's headline figures (D-55). No defaults: every
    field is computed, never assumed."""

    total_revenue: int  # paisa
    total_orders: int
    avg_order_value: int  # paisa
    total_tax: int  # paisa
    total_discount: int  # paisa
    net_revenue: int
    date_from: str
    date_to: str
    # Local time the previous period was cut at to match "so far today", e.g.
    # "2026-09-25T02:27". None when the whole previous period is compared.
    cut_at: str | None


class SalesSummary(BaseModel):
    total_revenue: int  # paisa
    total_orders: int
    avg_order_value: int  # paisa
    total_tax: int  # paisa
    total_discount: int  # paisa
    net_revenue: int  # total_revenue - total_discount
    previous: PeriodHeadline | None  # only when asked with compare=true
    cash_revenue: int = 0  # paisa — paid via cash
    card_revenue: int = 0  # paisa — paid via card
    other_revenue: int = 0  # paisa — mobile wallet, bank transfer, etc.
    dine_in_revenue: int
    dine_in_orders: int
    takeaway_revenue: int
    takeaway_orders: int
    call_center_revenue: int
    call_center_orders: int
    online_revenue: int = 0
    online_orders: int = 0
    discount_breakdown: list[DiscountBreakdownEntry] = []


class ItemPerformanceEntry(BaseModel):
    menu_item_id: str
    name: str
    image_url: str | None  # the menu photo (D-52); None if the dish has none
    quantity_sold: int
    revenue: int  # paisa
    # The comparison period (D-55). None when not asked; 0 when it sold nothing.
    previous_quantity: int | None
    previous_revenue: int | None


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
    date: str  # first day of the range
    date_to: str  # last day (same as `date` for one day)
    buckets: list[HourlyBucket]


class TableSizeItem(BaseModel):
    name: str
    visits_with: int  # visits that included this dish
    quantity: int
    share_pct: int  # visits_with / visits, rounded


class TableSizeEntry(BaseModel):
    capacity: int  # seats
    visits: int  # table sessions
    orders: int
    revenue: int  # paisa
    avg_per_visit: int  # paisa
    enough_data: bool  # False below min_visits: no item pattern shown
    top_items: list[TableSizeItem]


class TableSizeReport(BaseModel):
    min_visits: int
    sizes: list[TableSizeEntry]


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


# ---------------------------------------------------------------------------
# Waiter Performance Report (#11)
# ---------------------------------------------------------------------------


class WaiterPerformanceEntry(BaseModel):
    waiter_id: str
    waiter_name: str
    order_count: int
    total_revenue: int  # paisa
    avg_order_value: int  # paisa


class WaiterPerformanceReport(BaseModel):
    entries: list[WaiterPerformanceEntry]
    total_orders_with_waiter: int
    total_orders_without_waiter: int
