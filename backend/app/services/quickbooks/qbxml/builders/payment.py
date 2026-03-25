"""QBXML builder for Receive Payment transactions.

Converts POS payment records to QuickBooks Desktop ReceivePayment transactions.

ReceivePayment in QB is used for:
- Recording customer payments against existing invoices
- Partial payments or installment payments
- Payments received after the sale (not immediate like Sales Receipt)

For POS, this is used when:
- Customer pays in installments
- Partial payments (split payment scenario where invoice exists)
- Payment received separately from order (rare in restaurant context)

NOTE: Most POS payments happen at time of sale and are included in Sales
Receipt. This builder is for edge cases where payment is separate from the
sales transaction.
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


def build_receive_payment_add_rq(
    payment_data: dict[str, Any],
    customer_name: str,
    payment_method_name: str,  # QB payment method (Cash, Check, Credit Card, etc.)
    deposit_to_account: str | None = None,  # Where to deposit (optional)
    apply_to_txn_id: str | None = None,  # QB TxnID of invoice to apply payment to
) -> str:
    """Build a ReceivePaymentAddRq QBXML request.

    Args:
        payment_data: POS payment dict with keys:
            - reference: str (payment reference/transaction ID)
            - amount: int (payment amount in paisa)
            - processed_at: datetime
            - note: str (optional)
            - order_number: str (POS order number for reference)
        customer_name: QB customer name (must exist in QB)
        payment_method_name: QB payment method name (Cash, Check, etc.)
        deposit_to_account: QB account to deposit to (optional, defaults to Undeposited Funds)
        apply_to_txn_id: QB TxnID of invoice to apply this payment to (optional)

    Returns:
        QBXML string ready to send via QBWC.

    Example:
        >>> xml = build_receive_payment_add_rq(
        ...     payment_data={
        ...         "reference": "PAY-20240325-001",
        ...         "amount": 259600,  # Rs. 2,596.00
        ...         "processed_at": datetime(2024, 3, 25, 15, 30),
        ...         "note": "Partial payment for order 240325-001",
        ...         "order_number": "240325-001",
        ...     },
        ...     customer_name="Walk-In Customer",
        ...     payment_method_name="Cash",
        ...     deposit_to_account="Cash Drawer",
        ...     apply_to_txn_id="12345-6789012345",
        ... )
        >>> print(xml)  # Valid QBXML
    """
    # Validate required fields
    if not payment_data.get("amount"):
        raise ValueError("payment amount is required")
    if not customer_name:
        raise ValueError("customer_name is required")
    if not payment_method_name:
        raise ValueError("payment_method_name is required")

    # Extract payment fields
    reference = payment_data.get("reference", "")
    amount_paisa = payment_data["amount"]
    processed_at = payment_data.get("processed_at", datetime.now())
    txn_date = processed_at.strftime("%Y-%m-%d")
    note = payment_data.get("note", "")
    order_number = payment_data.get("order_number", "")

    # Build memo (max 4095 chars)
    memo_parts = []
    if order_number:
        memo_parts.append(f"POS Order: {order_number}")
    if reference:
        memo_parts.append(f"Ref: {reference}")
    if note:
        memo_parts.append(note)
    memo = truncate_field(" | ".join(memo_parts), "Memo") if memo_parts else ""

    # Build QBXML
    root = etree.Element("QBXML")
    root.append(
        etree.Comment(f" Generated by Sitara POS - Payment {reference or 'N/A'} ")
    )

    qbxml_msgs_rq = etree.SubElement(root, "QBXMLMsgsRq", onError="stopOnError")
    receive_payment_add_rq = etree.SubElement(
        qbxml_msgs_rq, "ReceivePaymentAddRq", requestID="1"
    )
    receive_payment_add = etree.SubElement(receive_payment_add_rq, "ReceivePaymentAdd")

    # Customer reference
    customer_ref = etree.SubElement(receive_payment_add, "CustomerRef")
    etree.SubElement(customer_ref, "FullName").text = customer_name

    # Transaction date
    etree.SubElement(receive_payment_add, "TxnDate").text = txn_date

    # Total amount received
    etree.SubElement(receive_payment_add, "TotalAmount").text = paisa_to_decimal(
        amount_paisa
    )

    # Payment method
    payment_method_ref = etree.SubElement(receive_payment_add, "PaymentMethodRef")
    etree.SubElement(payment_method_ref, "FullName").text = payment_method_name

    # Reference number (payment reference/transaction ID)
    if reference:
        etree.SubElement(receive_payment_add, "RefNumber").text = truncate_field(
            reference, "RefNumber"
        )

    # Memo
    if memo:
        etree.SubElement(receive_payment_add, "Memo").text = memo

    # Deposit to account (optional)
    if deposit_to_account:
        deposit_ref = etree.SubElement(receive_payment_add, "DepositToAccountRef")
        etree.SubElement(deposit_ref, "FullName").text = deposit_to_account

    # Apply to specific invoice (optional)
    # If apply_to_txn_id is provided, link this payment to an existing invoice
    if apply_to_txn_id:
        applied_to = etree.SubElement(receive_payment_add, "AppliedToTxnAdd")
        etree.SubElement(applied_to, "TxnID").text = apply_to_txn_id
        # QB will auto-calculate the applied amount based on TotalAmount
        # If you want to specify partial amount, add:
        # etree.SubElement(applied_to, "PaymentAmount").text = paisa_to_decimal(amount_paisa)

    # Convert to string
    qbxml_str = etree.tostring(
        root,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8",
    ).decode("utf-8")

    logger.info(
        "Built ReceivePaymentAddRq: %s PKR to customer %s",
        paisa_to_decimal(amount_paisa),
        customer_name,
    )

    return qbxml_str
