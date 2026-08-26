"""A4 VAT tax invoice.

A different document from the thermal ticket, not a restyling of it. Martin's
scope doc, Section 2: "Capacity to issue invoices as tickets or as A4 invoices
with a proper tax invoice template, including mandatory fields for VAT and the
full company name."

The mandatory fields below follow the UAE Federal Tax Authority's requirements
for a tax invoice: the words "Tax Invoice", the supplier's legal name, address
and TRN, a sequential invoice number, the date of issue, a description of each
line with unit price and quantity, the VAT rate and amount per line, and the
total payable with tax shown separately. Where the recipient is VAT registered
their name and TRN appear too.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class TaxInvoiceParty(BaseModel):
    """Supplier or recipient. TRN is what makes it a tax document."""

    name: str
    trn: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    country: str | None = None
    phone: str | None = None
    email: str | None = None


class TaxInvoiceLine(BaseModel):
    description: str
    quantity: int
    # All money is in minor units (fils), integers, never floats.
    unit_price_net_minor: int
    line_net_minor: int
    vat_rate_bps: int
    vat_amount_minor: int
    line_gross_minor: int


class TaxInvoiceData(BaseModel):
    document_title: str = "TAX INVOICE"

    invoice_number: str
    order_number: str
    issue_date: date
    issued_at: datetime

    supplier: TaxInvoiceParty
    recipient: TaxInvoiceParty | None = None

    currency: str
    lines: list[TaxInvoiceLine]

    subtotal_net_minor: int
    discount_minor: int
    vat_total_minor: int
    total_gross_minor: int

    vat_rate_bps: int
    # True when the menu prices already include VAT, in which case the net and
    # VAT figures above were derived from the gross rather than added to it.
    prices_include_vat: bool

    location_id: uuid.UUID | None = None
    location_name: str | None = None
    payment_status: str
    notes: str | None = None
