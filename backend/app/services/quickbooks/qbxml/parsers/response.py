"""QBXML response parser.

Parses QBXML responses from QuickBooks Desktop to extract:
- Status code and severity
- TxnID / ListID (QB-assigned identifiers)
- Error messages
- Response data
"""

import logging
from dataclasses import dataclass
from typing import Any
from lxml import etree

from app.services.quickbooks.qbxml.constants import get_user_friendly_error

logger = logging.getLogger(__name__)


@dataclass
class QBXMLParseResult:
    """Parsed QBXML response."""

    success: bool
    status_code: str
    status_severity: str  # "Info" | "Warn" | "Error"
    status_message: str
    user_message: str | None = None  # User-friendly error message
    txn_id: str | None = None  # Transaction ID (for sales receipts, invoices, etc.)
    list_id: str | None = None  # List ID (for customers, items, accounts, etc.)
    edit_sequence: str | None = None  # Edit sequence (for updates)
    time_created: str | None = None  # When QB created the record
    response_data: dict[str, Any] | None = None  # Full response data (optional)


def parse_qbxml_response(response_xml: str) -> QBXMLParseResult:
    """Parse a QBXML response from QuickBooks Desktop.

    Args:
        response_xml: QBXML response string from QB Desktop

    Returns:
        QBXMLParseResult with parsed data.

    Raises:
        ValueError: If XML is malformed or missing required fields.

    Example:
        >>> result = parse_qbxml_response('''<?xml version="1.0"?>
        ... <QBXML>
        ...   <QBXMLMsgsRs>
        ...     <SalesReceiptAddRs statusCode="0" statusSeverity="Info" statusMessage="Success">
        ...       <SalesReceiptRet>
        ...         <TxnID>12345-6789</TxnID>
        ...         <TimeCreated>2024-03-25T14:30:00</TimeCreated>
        ...         <RefNumber>240325-001</RefNumber>
        ...         <TotalAmount>2596.00</TotalAmount>
        ...       </SalesReceiptRet>
        ...     </SalesReceiptAddRs>
        ...   </QBXMLMsgsRs>
        ... </QBXML>''')
        >>> result.success
        True
        >>> result.txn_id
        '12345-6789'
    """
    try:
        root = etree.fromstring(response_xml.encode("utf-8"))
    except Exception as e:
        logger.error("Failed to parse QBXML response: %s", e, exc_info=True)
        raise ValueError(f"Invalid QBXML: {e}") from e

    # Find the response element (e.g., SalesReceiptAddRs, CustomerAddRs, etc.)
    # QB responses follow pattern: <{Operation}Rs> under <QBXMLMsgsRs>
    msgs_rs = root.find(".//QBXMLMsgsRs")
    if msgs_rs is None:
        raise ValueError("No QBXMLMsgsRs element found in response")

    # Get first response child (should be only one in single-request mode)
    response_elem = msgs_rs[0] if len(msgs_rs) > 0 else None
    if response_elem is None:
        raise ValueError("No response element found under QBXMLMsgsRs")

    # Extract status attributes (always present on response element)
    status_code = response_elem.get("statusCode", "")
    status_severity = response_elem.get("statusSeverity", "")
    status_message = response_elem.get("statusMessage", "")

    # Determine success (statusCode 0 = success, anything else = error/warning)
    success = status_code == "0"

    # Generate user-friendly error message if failed
    user_message = None
    if not success:
        user_message = get_user_friendly_error(status_code, status_message)

    # Extract QB-assigned IDs (if success)
    txn_id = None
    list_id = None
    edit_sequence = None
    time_created = None

    if success:
        # Look for return element (e.g., SalesReceiptRet, CustomerRet)
        # Pattern: <{Entity}Ret> is the return data element
        ret_elem = response_elem.find(".//*Ret")
        if ret_elem is not None:
            # TxnID (for transactions)
            txn_id_elem = ret_elem.find(".//TxnID")
            if txn_id_elem is not None:
                txn_id = txn_id_elem.text

            # ListID (for list entities like customers, items, accounts)
            list_id_elem = ret_elem.find(".//ListID")
            if list_id_elem is not None:
                list_id = list_id_elem.text

            # EditSequence (for updates)
            edit_seq_elem = ret_elem.find(".//EditSequence")
            if edit_seq_elem is not None:
                edit_sequence = edit_seq_elem.text

            # TimeCreated
            time_created_elem = ret_elem.find(".//TimeCreated")
            if time_created_elem is not None:
                time_created = time_created_elem.text

    logger.info(
        "Parsed QBXML response: statusCode=%s severity=%s success=%s txnID=%s listID=%s",
        status_code,
        status_severity,
        success,
        txn_id,
        list_id,
    )

    return QBXMLParseResult(
        success=success,
        status_code=status_code,
        status_severity=status_severity,
        status_message=status_message,
        user_message=user_message,
        txn_id=txn_id,
        list_id=list_id,
        edit_sequence=edit_sequence,
        time_created=time_created,
    )


def extract_full_response_data(response_xml: str) -> dict[str, Any]:
    """Extract all data from QBXML response as a dict (for debugging/logging).

    Args:
        response_xml: QBXML response string

    Returns:
        Dict representation of the response (simplified).

    Note:
        This is a helper for debugging. For production use, prefer parse_qbxml_response()
        which extracts only the essential fields.
    """
    try:
        root = etree.fromstring(response_xml.encode("utf-8"))
    except Exception as e:
        return {"error": f"Failed to parse XML: {e}"}

    def elem_to_dict(elem: etree._Element) -> dict | str:
        """Recursively convert XML element to dict."""
        if len(elem) == 0:
            # Leaf node: return text
            return elem.text or ""
        else:
            # Branch node: return dict of children
            result = {}
            for child in elem:
                tag = child.tag
                value = elem_to_dict(child)
                # Handle multiple children with same tag (e.g., multiple lines)
                if tag in result:
                    # Convert to list
                    if not isinstance(result[tag], list):
                        result[tag] = [result[tag]]
                    result[tag].append(value)
                else:
                    result[tag] = value
            # Include attributes
            for attr_name, attr_value in elem.attrib.items():
                result[f"@{attr_name}"] = attr_value
            return result

    return elem_to_dict(root)
