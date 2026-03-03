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
