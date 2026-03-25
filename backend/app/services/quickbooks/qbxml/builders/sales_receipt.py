"""QBXML builder for Sales Receipts.

Converts POS orders to QuickBooks Desktop SalesReceipt transactions.

A Sales Receipt in QB is used for:
- Cash sales (payment received at time of sale)
- Credit card sales
- Any transaction where payment is immediate (not invoiced)

This matches our POS flow where orders are paid before/during fulfillment.
"""

import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from lxml import etree

from app.services.quickbooks.qbxml.constants import (
    FIELD_LIMITS,
    QBXML_VERSION,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Currency Conversion
# ---------------------------------------------------------------------------


def paisa_to_decimal(paisa: int) -> str:
    """Convert paisa (integer) to decimal string for QB.

    >>> paisa_to_decimal(15000)
    '150.00'
    >>> paisa_to_decimal(99)
    '0.99'
    """
    d = Decimal(paisa) / Decimal(100)
    return str(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def truncate_field(value: str, field_name: str) -> str:
    """Truncate a field to QB's maximum length.

    Args:
        value: Field value
        field_name: Field name (for limit lookup)

    Returns:
        Truncated string if it exceeds limit, original otherwise.
    """
    limit = FIELD_LIMITS.get(field_name)
    if limit and len(value) > limit:
        logger.warning(
            "Truncating %s from %d to %d chars: %s...",
            field_name,
            len(value),
            limit,
            value[:30],
        )
        return value[:limit]
    return value


# ---------------------------------------------------------------------------
# QBXML Builder
# ---------------------------------------------------------------------------


def build_sales_receipt_add_rq(
    order_data: dict[str, Any],
    customer_name: str,
    deposit_to_account: str,  # QB account name (e.g., "Cash", "Undeposited Funds")
    income_account: str,  # QB account name for sales (e.g., "Food Sales")
    tax_account: str | None = None,  # QB account name for tax (e.g., "Sales Tax Payable")
) -> str:
    """Build a SalesReceiptAddRq QBXML request.

    Args:
        order_data: POS order dict with keys:
            - order_number: str
            - order_type: str ("dine_in", "takeaway", "call_center")
            - created_at: datetime
            - items: list[dict] with {name, quantity, price_paisa, total_paisa}
            - subtotal_paisa: int
            - tax_paisa: int
            - total_paisa: int
            - notes: str (optional)
        customer_name: QB customer name (must exist in QB or use "Walk-In Customer")
        deposit_to_account: Where payment goes (Cash, Undeposited Funds, etc.)
        income_account: Revenue account for sales
        tax_account: Tax liability account (optional, required if tax > 0)

    Returns:
        QBXML string ready to send via QBWC.

    Example:
        >>> xml = build_sales_receipt_add_rq(
        ...     order_data={
        ...         "order_number": "240325-001",
        ...         "order_type": "dine_in",
        ...         "created_at": datetime(2024, 3, 25, 14, 30),
        ...         "items": [
        ...             {"name": "Chicken Biryani", "quantity": 2, "price_paisa": 85000, "total_paisa": 170000},
        ...             {"name": "Mango Lassi", "quantity": 2, "price_paisa": 25000, "total_paisa": 50000},
        ...         ],
        ...         "subtotal_paisa": 220000,
        ...         "tax_paisa": 39600,  # 18% (GST 17% + PST 1%)
        ...         "total_paisa": 259600,
        ...         "notes": "Table 5, Server: Ali",
        ...     },
        ...     customer_name="Walk-In Customer",
        ...     deposit_to_account="Cash",
        ...     income_account="Food Sales",
        ...     tax_account="Sales Tax Payable",
        ... )
        >>> print(xml)  # Valid QBXML
    """
    # Validate required fields
    if not order_data.get("order_number"):
        raise ValueError("order_number is required")
    if not order_data.get("items"):
        raise ValueError("At least one order item is required")

    # Extract order fields
    order_number = truncate_field(order_data["order_number"], "RefNumber")
    order_type = order_data.get("order_type", "unknown")
    txn_date = order_data.get("created_at", datetime.now()).strftime("%Y-%m-%d")
    subtotal_paisa = order_data.get("subtotal_paisa", 0)
    tax_paisa = order_data.get("tax_paisa", 0)
    total_paisa = order_data.get("total_paisa", 0)
    notes = order_data.get("notes", "")

    # Build memo (max 4095 chars)
    memo_parts = [f"POS Order: {order_number}"]
    if order_type:
        memo_parts.append(f"Type: {order_type.replace('_', ' ').title()}")
    if notes:
        memo_parts.append(notes)
    memo = truncate_field(" | ".join(memo_parts), "Memo")

    # Build QBXML
    root = etree.Element("QBXML")
    root.append(etree.Comment(f" Generated by Sitara POS - Order {order_number} "))

    qbxml_msgs_rq = etree.SubElement(root, "QBXMLMsgsRq", onError="stopOnError")
    sales_receipt_add_rq = etree.SubElement(
        qbxml_msgs_rq, "SalesReceiptAddRq", requestID="1"
    )
    sales_receipt_add = etree.SubElement(sales_receipt_add_rq, "SalesReceiptAdd")

    # Customer
    customer_ref = etree.SubElement(sales_receipt_add, "CustomerRef")
    etree.SubElement(customer_ref, "FullName").text = customer_name

    # Transaction date
    etree.SubElement(sales_receipt_add, "TxnDate").text = txn_date

    # RefNumber (POS order number, must be unique in QB)
    etree.SubElement(sales_receipt_add, "RefNumber").text = order_number

    # Deposit to account (where money goes)
    deposit_ref = etree.SubElement(sales_receipt_add, "DepositToAccountRef")
    etree.SubElement(deposit_ref, "FullName").text = deposit_to_account

    # Memo
    etree.SubElement(sales_receipt_add, "Memo").text = memo

    # Line items
    for idx, item in enumerate(order_data["items"], start=1):
        item_name = item.get("name", f"Item {idx}")
        quantity = item.get("quantity", 1)
        price_paisa = item.get("price_paisa", 0)
        total_paisa = item.get("total_paisa", price_paisa * quantity)

        line = etree.SubElement(sales_receipt_add, "SalesReceiptLineAdd")

        # Item reference (must exist in QB as a Service or NonInventory item)
        item_ref = etree.SubElement(line, "ItemRef")
        etree.SubElement(item_ref, "FullName").text = truncate_field(item_name, "Name")

        # Description (optional, for display on QB forms)
        desc = item.get("description", item_name)
        etree.SubElement(line, "Desc").text = truncate_field(desc, "Description")

        # Quantity
        etree.SubElement(line, "Quantity").text = str(quantity)

        # Rate (price per unit)
        etree.SubElement(line, "Rate").text = paisa_to_decimal(price_paisa)

        # Amount (total for this line, QB will calculate: Quantity × Rate)
        # We include it explicitly for clarity
        etree.SubElement(line, "Amount").text = paisa_to_decimal(total_paisa)

        # Income account (where revenue is recorded)
        account_ref = etree.SubElement(line, "AccountRef")
        etree.SubElement(account_ref, "FullName").text = income_account

    # Sales Tax (if applicable)
    if tax_paisa > 0:
        if not tax_account:
            raise ValueError("tax_account is required when tax_paisa > 0")

        # Add tax as a separate line (QB Desktop requires manual tax lines)
        tax_line = etree.SubElement(sales_receipt_add, "SalesReceiptLineAdd")

        # Use a standard "Sales Tax" item (must exist in QB)
        # NOTE: In production, you should map POS tax types to specific QB tax items
        tax_item_ref = etree.SubElement(tax_line, "ItemRef")
        etree.SubElement(tax_item_ref, "FullName").text = "Sales Tax"

        etree.SubElement(tax_line, "Desc").text = "Sales Tax (GST + PST)"
        etree.SubElement(tax_line, "Amount").text = paisa_to_decimal(tax_paisa)

        # Tax account (liability account)
        tax_account_ref = etree.SubElement(tax_line, "AccountRef")
        etree.SubElement(tax_account_ref, "FullName").text = tax_account

    # Convert to string
    qbxml_str = etree.tostring(
        root,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8",
    ).decode("utf-8")

    logger.info(
        "Built SalesReceiptAddRq for order %s: %d items, total %s PKR",
        order_number,
        len(order_data["items"]),
        paisa_to_decimal(total_paisa),
    )

    return qbxml_str
