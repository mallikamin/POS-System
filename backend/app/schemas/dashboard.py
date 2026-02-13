"""Pydantic schemas for dashboard KPIs and live operations."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class DashboardKpis(BaseModel):
    today_revenue: int  # paisa
    yesterday_revenue: int  # paisa
    today_orders: int
    avg_order_value: int  # paisa
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


class LiveOperations(BaseModel):
    dine_in: list[LiveOrderItem]
    takeaway: list[LiveOrderItem]
    call_center: list[LiveOrderItem]
