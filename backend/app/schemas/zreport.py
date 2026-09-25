"""Z-Report / Daily Settlement response schemas."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.inventory import Num


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


# ---------------------------------------------------------------------------
# Daily summary sections (Danny's UAT D-60): inventory used, stock left, cash
# position. No field below has a default: every one is set by
# zreport_service, so a forgotten value fails validation instead of showing a
# plausible zero (see ERROR_LOG 2026-09-26, D-44).
#
# Ingredient quantities and costs are Decimal on the server and plain JSON
# numbers on the wire (`Num`). Costs are MINOR units, like
# Ingredient.cost_per_unit; they are never multiplied by 100.
# ---------------------------------------------------------------------------


class InventoryUsedRow(BaseModel):
    ingredient_id: uuid.UUID
    ingredient_name: str
    unit: str
    # Left the shelf because a dish was sold (consumption with an order).
    sold_quantity: Num
    sold_cost: Num
    # Consumed making an in-house item (consumption with no order).
    production_quantity: Num
    production_cost: Num
    waste_quantity: Num
    waste_cost: Num
    # Manual corrections, SIGNED: negative took stock away, positive added it.
    adjustment_quantity: Num
    adjustment_cost: Num
    # sold + production + waste for this ingredient; the sort key.
    used_cost: Num
    # True when at least one movement recorded a zero cost and was priced at
    # the ingredient's CURRENT cost_per_unit instead.
    costed_at_current_price: bool


class InventoryUsed(BaseModel):
    rows: list[InventoryUsedRow]
    total_sold_cost: Num
    total_production_cost: Num
    total_waste_cost: Num
    total_adjustment_cost: Num
    # Cost of goods that left the business: sold + waste. Production inputs
    # are excluded on purpose; see zreport_service._inventory_used.
    total_cost_of_goods_used: Num


class StockLeftRow(BaseModel):
    location_id: uuid.UUID
    location_name: str
    ingredient_id: uuid.UUID
    ingredient_name: str
    unit: str
    closing_quantity: Num
    reorder_point: Num
    is_low: bool


class StockLeft(BaseModel):
    # The instant the day ended (UTC); closing quantities are as of then.
    as_of: datetime
    multiple_locations: bool
    low_count: int
    rows: list[StockLeftRow]


class DrawerPosition(BaseModel):
    session_status: str  # open | closed
    opened_at: datetime
    closed_at: datetime | None
    opening_float: int
    cash_taken: int
    cash_refunds: int
    cash_paid_out: int
    expected_in_drawer: int
    counted_closing: int | None
    over_short: int | None  # counted - expected; None until counted


class CashExpenseLine(BaseModel):
    payee: str
    payment_method: str  # as typed on the Expenses screen
    amount: int  # minor units


class CashPosition(BaseModel):
    # The whole restaurant day, minor units.
    cash_taken: int
    cash_refunds: int
    cash_paid_out: int
    cash_expenses: list[CashExpenseLine]  # what cash_paid_out is made of
    net_cash: int  # cash_taken - cash_refunds - cash_paid_out
    drawer_opened: bool
    drawers: list[DrawerPosition]


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

    # D-60 daily summary. Required, no defaults.
    inventory_used: InventoryUsed
    stock_left: StockLeft
    cash_position: CashPosition
