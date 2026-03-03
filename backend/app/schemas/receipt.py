"""Receipt data response schema."""

from datetime import datetime

from pydantic import BaseModel


class ReceiptItem(BaseModel):
    class ModifierLine(BaseModel):
        name: str
        price_adjustment: int  # paisa

    name: str
    quantity: int
    unit_price: int  # paisa
    total: int  # paisa
    modifiers: list[ModifierLine] = []


class ReceiptPayment(BaseModel):
    method: str
    amount: int  # paisa
    tendered: int | None = None
    change: int | None = None


class ReceiptData(BaseModel):
    restaurant_name: str
    receipt_header: str | None = None
    receipt_footer: str | None = None
    order_number: str
    order_type: str
    date: datetime
    table_label: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    cashier_name: str

    items: list[ReceiptItem]
    subtotal: int  # paisa
    tax_label: str
    tax_rate_display: str  # e.g. "16%"
    tax_amount: int  # paisa
    discount_amount: int  # paisa
    total: int  # paisa

    payments: list[ReceiptPayment]
    payment_status: str

    currency: str
