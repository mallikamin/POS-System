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
    order_label: str | None = None  # e.g. "260304-001" — set for session receipts


class ReceiptDiscountLine(BaseModel):
    label: str
    source_type: str
    amount: int  # paisa


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
    waiter_name: str | None = None

    items: list[ReceiptItem]
    subtotal: int  # paisa
    tax_label: str
    tax_rate_display: str  # e.g. "16%"
    tax_amount: int  # paisa
    discount_lines: list[ReceiptDiscountLine] = []
    discount_amount: int  # paisa
    # Charges outside the tax. Printed as their own lines so the visible
    # lines always add up to the total; 0 on orders that carry none.
    delivery_fee: int = 0
    service_fee: int = 0
    tip: int = 0
    total: int  # paisa
    # How this tenant prints: 'thermal' (80mm roll) or 'a4'.
    receipt_format: str = "thermal"

    payments: list[ReceiptPayment]
    payment_status: str

    cash_tax_rate_bps: int = 0
    card_tax_rate_bps: int = 0

    currency: str
