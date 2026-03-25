"""QuickBooks Desktop QBXML constants and error mappings.

QBXML SDK version: 13.0 (compatible with QB Desktop 2016+)
Spec: https://developer.intuit.com/app/developer/qbdesktop/docs/api-reference/qbdesktop
"""

# ---------------------------------------------------------------------------
# QBXML Version
# ---------------------------------------------------------------------------

QBXML_VERSION = "13.0"
QBXML_COUNTRY = "US"  # Can be "US", "CA", "UK", "AU"

# ---------------------------------------------------------------------------
# Field Length Limits
# ---------------------------------------------------------------------------

# QB Desktop has strict field length limits. Exceeding them causes errors.
FIELD_LIMITS = {
    "Name": 41,  # Account names, item names, customer names
    "FullName": 159,  # Full hierarchical name (Parent:Child)
    "Description": 4095,  # Sales descriptions, notes
    "Memo": 4095,  # Transaction memos
    "RefNumber": 11,  # Invoice numbers, PO numbers
    "TxnID": 40,  # Transaction ID (QB-assigned)
    "ListID": 40,  # List ID (QB-assigned)
    "Address": {
        "Addr1": 41,
        "Addr2": 41,
        "Addr3": 41,
        "Addr4": 41,
        "Addr5": 41,
        "City": 31,
        "State": 21,
        "PostalCode": 13,
        "Country": 31,
    },
    "Phone": 21,
    "Email": 1023,
}

# ---------------------------------------------------------------------------
# QuickBooks Error Codes
# ---------------------------------------------------------------------------

# Common error codes returned in QBXML responses
# Format: {"statusCode": "statusSeverity", "statusMessage"}

QB_ERROR_CODES = {
    # Success
    "0": {"severity": "Info", "message": "Success"},
    # Authentication errors (3000-3099)
    "3120": {
        "severity": "Error",
        "message": "Invalid user credentials",
        "user_message": "QBWC username or password is incorrect. Please check your Desktop connection settings.",
    },
    "3140": {
        "severity": "Error",
        "message": "Company file not open",
        "user_message": "QuickBooks Desktop company file is not open. Please open the company file and try again.",
    },
    "3180": {
        "severity": "Error",
        "message": "QB not open",
        "user_message": "QuickBooks Desktop is not running. Please open QuickBooks and try again.",
    },
    # Data validation errors (3100-3199)
    "3100": {
        "severity": "Error",
        "message": "Name already exists",
        "user_message": "This item or account already exists in QuickBooks. Choose a different name or update the existing entry.",
    },
    "3120": {
        "severity": "Error",
        "message": "Missing required field",
        "user_message": "A required field is missing. Please check your data and try again.",
    },
    "3175": {
        "severity": "Error",
        "message": "List element not found",
        "user_message": "The referenced account, item, or customer was not found in QuickBooks. Please sync it first.",
    },
    "3200": {
        "severity": "Error",
        "message": "Edit sequence mismatch",
        "user_message": "This record was modified by another user. Please refresh and try again.",
    },
    # Permission errors (3200-3299)
    "3231": {
        "severity": "Error",
        "message": "User lacks permission",
        "user_message": "Your QuickBooks user does not have permission for this operation. Contact your QB administrator.",
    },
    # Transaction errors (3300-3399)
    "3310": {
        "severity": "Error",
        "message": "Transaction already exists",
        "user_message": "This transaction already exists in QuickBooks (duplicate RefNumber).",
    },
    "3380": {
        "severity": "Error",
        "message": "Invalid date",
        "user_message": "The transaction date is outside the allowed range. Check your fiscal year settings.",
    },
    # XML parsing errors (3400-3499)
    "3400": {
        "severity": "Error",
        "message": "XML parse error",
        "user_message": "The request data is invalid. This is a system error — please contact support.",
    },
    # Version errors (3500-3599)
    "3500": {
        "severity": "Error",
        "message": "Unsupported QBXML version",
        "user_message": "Your QuickBooks Desktop version does not support this operation. Upgrade QuickBooks or contact support.",
    },
}


def get_user_friendly_error(status_code: str, default_message: str = None) -> str:
    """Convert QB status code to user-friendly error message.

    Args:
        status_code: QB error code (e.g., "3100", "3175")
        default_message: Fallback message if code not found

    Returns:
        User-friendly error message.
    """
    error_info = QB_ERROR_CODES.get(status_code)
    if error_info:
        return error_info.get("user_message", error_info["message"])
    return default_message or f"QuickBooks error {status_code}"


# ---------------------------------------------------------------------------
# QBXML XML Namespaces
# ---------------------------------------------------------------------------

QBXML_NAMESPACE = "http://www.intuit.com/sb/cdm/v2"

# ---------------------------------------------------------------------------
# Transaction Types
# ---------------------------------------------------------------------------

TRANSACTION_TYPES = {
    "sales_receipt": "SalesReceipt",
    "invoice": "Invoice",
    "payment": "ReceivePayment",
    "credit_memo": "CreditMemo",
    "journal_entry": "JournalEntry",
    "purchase_order": "PurchaseOrder",
    "bill": "Bill",
    "bill_payment": "BillPaymentCheck",
}

# ---------------------------------------------------------------------------
# Item Types
# ---------------------------------------------------------------------------

ITEM_TYPES = {
    "service": "ItemService",
    "non_inventory": "ItemNonInventory",
    "inventory": "ItemInventory",
    "inventory_assembly": "ItemInventoryAssembly",
    "group": "ItemGroup",
    "discount": "ItemDiscount",
    "payment": "ItemPayment",
    "sales_tax": "ItemSalesTax",
    "sales_tax_group": "ItemSalesTaxGroup",
}

# ---------------------------------------------------------------------------
# Account Types
# ---------------------------------------------------------------------------

ACCOUNT_TYPES = [
    "AccountsPayable",
    "AccountsReceivable",
    "Bank",
    "CostOfGoodsSold",
    "CreditCard",
    "Equity",
    "Expense",
    "FixedAsset",
    "Income",
    "LongTermLiability",
    "NonPosting",
    "OtherAsset",
    "OtherCurrentAsset",
    "OtherCurrentLiability",
    "OtherExpense",
    "OtherIncome",
]

# ---------------------------------------------------------------------------
# Payment Methods
# ---------------------------------------------------------------------------

PAYMENT_METHOD_TYPES = [
    "AmericanExpress",
    "Cash",
    "Check",
    "DebitCard",
    "Discover",
    "ECheck",
    "GiftCard",
    "MasterCard",
    "Other",
    "OtherCreditCard",
    "Visa",
]
