"""Currency formatting for anything the customer or a supplier actually reads.

One module because the symbol table was previously copied into four places and
they drifted. Three of the four copies were missing **AED**, and each fell back
to an EMPTY symbol, so a UAE tenant's purchase order, quotation and order email
would have rendered `380.00` with no currency on the document at all:

    backend/app/services/print_service.py            had AED    (correct)
    backend/app/services/purchase_order_document.py  no AED -> ""
    backend/app/services/quotation_document.py       no AED -> ""
    backend/app/services/email_service.py            no AED -> ""

Found by a codebase sweep during UAT (F26), not by anyone opening a document.

The fallback is the ISO code plus a space -- ugly, but never wrong, and never
silent. An unknown currency must never render as a bare number.
"""

# Symbols for the currencies this product actually ships in.
CURRENCY_SYMBOLS: dict[str, str] = {
    "GBP": "£",
    "PKR": "Rs.",
    "USD": "$",
    "EUR": "EUR ",
    "AED": "AED ",
}


def currency_symbol(currency: str | None) -> str:
    """The display symbol, or the ISO code plus a space if we do not know it."""
    code = (currency or "").upper()
    if not code:
        return ""
    return CURRENCY_SYMBOLS.get(code, f"{code} ")


def money(minor_units: int, currency: str | None) -> str:
    """Integer minor units to a display string. `1499, "GBP"` -> `£14.99`.

    Everything in this system is integer pence/paisa/fils on purpose, so this
    is one of the few places the decimal point is introduced.
    """
    return f"{currency_symbol(currency)}{minor_units / 100:,.2f}"
