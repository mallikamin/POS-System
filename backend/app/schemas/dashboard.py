"""Pydantic schemas for dashboard KPIs and live operations."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class DashboardKpis(BaseModel):
    today_revenue: int  # paisa
    yesterday_revenue: int  # paisa
    today_orders: int
    avg_order_value: int  # paisa
    # D-55: yesterday up to the same clock time, the like-for-like comparison.
    yesterday_same_time_revenue: int  # paisa
    yesterday_same_time_orders: int
    yesterday_same_time_avg_order_value: int  # paisa
    compared_until: str | None  # yesterday's local cut-off, "2026-09-25T02:27"
    table_utilization: float  # 0.0 - 1.0
    active_orders: int
    pending_kitchen: int


class LiveOrderItem(BaseModel):
    id: uuid.UUID
    order_number: str
    order_type: str
    status: str
    table_id: uuid.UUID | None = None
    table_number: int | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    item_count: int
    total: int  # paisa
    created_at: datetime


class ActivityEvent(BaseModel):
    """One line of the owner's live feed (D-57). No defaults: every field is
    read from a recorded status change or payment."""

    id: str
    at: str  # ISO instant
    kind: str  # placed | in_kitchen | ready | served | completed | voided | paid | settled | refund
    where: str  # "Tree House, Table 1" or "Takeaway #260926-004"
    text: str  # "settled the bill, Cash"
    amount: int | None  # paisa, when the event carries money
    order_number: str


class ActivityFeed(BaseModel):
    date: str  # the restaurant's day the feed covers
    events: list[ActivityEvent]


class LiveOperations(BaseModel):
    dine_in: list[LiveOrderItem]
    takeaway: list[LiveOrderItem]
    call_center: list[LiveOrderItem]
    online: list[LiveOrderItem] = []
