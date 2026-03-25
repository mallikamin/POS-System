"""QBXML builder for Credit Memo transactions.

Converts POS refund records to QuickBooks Desktop CreditMemo transactions.

A Credit Memo in QB is used for:
- Full refunds (entire order returned)
- Partial refunds (some items returned)
- Store credit issued to customer
- Voided sales receipts that need accounting adjustment

For POS refunds, this creates a credit against the customer's account,
reducing revenue and updating the customer balance.

NOTE: If the original transaction was a Sales Receipt (most POS orders),
you typically create a Credit Memo and optionally link it back to the
customer for tracking purposes.
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


def build_credit_memo_add_rq(
    refund_data: dict[str, Any],
    customer_name: str,
    income_account: str,  # QB account name for revenue reversal
    refund_account: str | None = None,  # Where refund goes (Cash, Bank, etc.)
    tax_account: str | None = None,  # Tax liability account (if tax was refunded)
) -> str:
    """Build a CreditMemoAddRq QBXML request.

    Args:
        refund_data: POS refund dict with keys:
            - order_number: str (original POS order number)
            - refund_reference: str (refund transaction ID)
            - refunded_at: datetime
            - items: list[dict] with {name, quantity, price_paisa, total_paisa}
            - subtotal_paisa: int
            - tax_paisa: int (tax amount being refunded)
            - total_paisa: int (total refund amount)
            - reason: str (refund reason)
        customer_name: QB customer name (must exist in QB or use "Walk-In Customer")
        income_account: Revenue account to reverse (e.g., "Food Sales")
        refund_account: Account to refund from (e.g., "Cash Drawer", optional)
        tax_account: Tax liability account (e.g., "Sales Tax Payable", required if tax > 0)

    Returns:
        QBXML string ready to send via QBWC.

    Example:
        >>> xml = build_credit_memo_add_rq(
        ...     refund_data={
        ...         "order_number": "240325-001",
        ...         "refund_reference": "REF-20240325-001",
        ...         "refunded_at": datetime(2024, 3, 25, 16, 0),
        ...         "items": [
        ...             {"name": "Chicken Biryani", "quantity": 1, "price_paisa": 85000, "total_paisa": 85000},
        ...         ],
        ...         "subtotal_paisa": 85000,
        ...         "tax_paisa": 15300,  # 18%
        ...         "total_paisa": 100300,
        ...         "reason": "Customer complaint - cold food",
        ...     },
        ...     customer_name="Walk-In Customer",
        ...     income_account="Food Sales",
        ...     refund_account="Cash Drawer",
        ...     tax_account="Sales Tax Payable",
        ... )
        >>> print(xml)  # Valid QBXML
    """
    # Validate required fields
    if not refund_data.get("order_number"):
        raise ValueError("order_number is required")
    if not refund_data.get("items"):
        raise ValueError("At least one refund item is required")

    # Extract refund fields
    order_number = truncate_field(refund_data["order_number"], "RefNumber")
    refund_reference = refund_data.get("refund_reference", "")
    refunded_at = refund_data.get("refunded_at", datetime.now())
    txn_date = refunded_at.strftime("%Y-%m-%d")
    subtotal_paisa = refund_data.get("subtotal_paisa", 0)
    tax_paisa = refund_data.get("tax_paisa", 0)
    total_paisa = refund_data.get("total_paisa", 0)
    reason = refund_data.get("reason", "")

    # Build memo (max 4095 chars)
    memo_parts = [f"REFUND - Original Order: {order_number}"]
    if refund_reference:
        memo_parts.append(f"Ref: {refund_reference}")
    if reason:
        memo_parts.append(f"Reason: {reason}")
    memo = truncate_field(" | ".join(memo_parts), "Memo")

    # Build QBXML
    root = etree.Element("QBXML")
    root.append(
        etree.Comment(
            f" Generated by Sitara POS - Refund for Order {order_number} "
        )
    )

    qbxml_msgs_rq = etree.SubElement(root, "QBXMLMsgsRq", onError="stopOnError")
    credit_memo_add_rq = etree.SubElement(
        qbxml_msgs_rq, "CreditMemoAddRq", requestID="1"
    )
    credit_memo_add = etree.SubElement(credit_memo_add_rq, "CreditMemoAdd")

    # Customer
    customer_ref = etree.SubElement(credit_memo_add, "CustomerRef")
    etree.SubElement(customer_ref, "FullName").text = customer_name

    # Transaction date
    etree.SubElement(credit_memo_add, "TxnDate").text = txn_date

    # RefNumber (use refund reference or append -REFUND to order number)
    ref_number = refund_reference if refund_reference else f"{order_number}-REFUND"
    etree.SubElement(credit_memo_add, "RefNumber").text = truncate_field(
        ref_number, "RefNumber"
    )

    # Memo
    etree.SubElement(credit_memo_add, "Memo").text = memo

    # Line items (what is being refunded)
    for idx, item in enumerate(refund_data["items"], start=1):
        item_name = item.get("name", f"Item {idx}")
        quantity = item.get("quantity", 1)
        price_paisa = item.get("price_paisa", 0)
        total_paisa = item.get("total_paisa", price_paisa * quantity)

        line = etree.SubElement(credit_memo_add, "CreditMemoLineAdd")

        # Item reference (must exist in QB)
        item_ref = etree.SubElement(line, "ItemRef")
        etree.SubElement(item_ref, "FullName").text = truncate_field(item_name, "Name")

        # Description
        desc = item.get("description", item_name)
        etree.SubElement(line, "Desc").text = truncate_field(desc, "Description")

        # Quantity (positive for credit memo)
        etree.SubElement(line, "Quantity").text = str(quantity)

        # Rate (price per unit)
        etree.SubElement(line, "Rate").text = paisa_to_decimal(price_paisa)

        # Amount (total for this line)
        etree.SubElement(line, "Amount").text = paisa_to_decimal(total_paisa)

        # Income account (revenue account to reverse)
        account_ref = etree.SubElement(line, "AccountRef")
        etree.SubElement(account_ref, "FullName").text = income_account

    # Sales Tax Refund (if applicable)
    if tax_paisa > 0:
        if not tax_account:
            raise ValueError("tax_account is required when tax_paisa > 0")

        # Add tax as a separate line
        tax_line = etree.SubElement(credit_memo_add, "CreditMemoLineAdd")

        # Use standard "Sales Tax" item
        tax_item_ref = etree.SubElement(tax_line, "ItemRef")
        etree.SubElement(tax_item_ref, "FullName").text = "Sales Tax"

        etree.SubElement(tax_line, "Desc").text = "Tax Refund (GST + PST)"
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
        "Built CreditMemoAddRq for order %s: %d items, total %s PKR",
        order_number,
        len(refund_data["items"]),
        paisa_to_decimal(total_paisa),
    )

    return qbxml_str
