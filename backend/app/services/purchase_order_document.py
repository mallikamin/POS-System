"""The purchase order as a document: what the supplier actually receives.

Two renderings of one structure, built once so they cannot drift:

    render_text  the plain-text body of the email, and the fallback for any
                 mail client that will not display HTML
    render_html  the A4-shaped document, used both as the email body and as
                 the browser print view

Why the buyer's identity comes from the LOCATION
------------------------------------------------
Same reasoning as `tax_invoice_service`: a tenant may trade under a different
registered entity per site, and the supplier needs to know which entity is
ordering and where to deliver. The location's legal name, TRN and address are
used when present, falling back to the tenant's name so a single-site
restaurant that never filled those in still gets a valid document.

Money
-----
🔴 Every `*_minor` value here is in MINOR UNITS (`200` = 2.00 AED), matching the
rest of the procurement and inventory modules. `_money_str` is the ONLY place
that divides by 100, and it does so purely for display.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from html import escape as html_escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import Location
from app.models.procurement import PurchaseOrder
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant

# F26: this table was missing AED and fell back to an EMPTY symbol, so a
# UAE supplier's purchase order rendered bare numbers. Shared table now.
from app.utils.money import currency_symbol


def _money_str(value_minor, currency: str) -> str:
    """Minor units to a display string. The only division by 100 in the module."""
    amount = Decimal(str(value_minor)) / Decimal(100)
    symbol = currency_symbol(currency)
    formatted = f"{amount:,.2f}"
    return f"{symbol}{formatted}" if symbol else f"{formatted} {currency}"


def _qty_str(value) -> str:
    """Trim trailing zeros so 25.000 prints as 25, not 25.000."""
    quantity = Decimal(str(value)).normalize()
    text = format(quantity, "f")
    return text


def _stock_equivalent(item) -> str | None:
    """"= 800 g", for a line ordered in a unit the kitchen does not cook in.

    Martin M8. Returns None when the purchase unit and the stocking unit are
    the same, which is every line raised before the conversion existed, so no
    existing purchase order document changes at all.
    """
    conversion = Decimal(str(item.units_per_purchase_unit or 1))
    if conversion == 1 or item.unit == item.ingredient.unit:
        return None
    total = Decimal(str(item.quantity_ordered)) * conversion
    return f"= {_qty_str(total)} {item.ingredient.unit}"


@dataclass
class DocumentParty:
    name: str
    trn: str | None = None
    contact_name: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    country: str | None = None
    phone: str | None = None
    email: str | None = None

    def address_lines(self) -> list[str]:
        parts = [
            self.address_line1,
            self.address_line2,
            ", ".join(p for p in (self.city, self.country) if p) or None,
        ]
        return [p for p in parts if p]


@dataclass
class DocumentLine:
    description: str
    supplier_sku: str | None
    quantity: Decimal
    unit: str
    unit_price_minor: Decimal
    line_total_minor: Decimal
    notes: str | None = None
    # What the quantity works out to in the kitchen's own units, when the two
    # differ (Martin M8). The supplier is asked for cans and only cans; this
    # rides along in the notes column so the person checking the delivery in
    # can see the weight without doing the arithmetic. None when there is no
    # conversion, which keeps every existing document byte-identical.
    stock_equivalent: str | None = None


@dataclass
class PurchaseOrderDocument:
    po_number: str
    issue_date: date
    expected_date: date | None
    currency: str
    buyer: DocumentParty
    supplier: DocumentParty
    deliver_to_name: str
    deliver_to_lines: list[str]
    lines: list[DocumentLine] = field(default_factory=list)
    subtotal_minor: Decimal = Decimal("0")
    tax_bps: int = 0
    tax_minor: Decimal = Decimal("0")
    total_minor: Decimal = Decimal("0")
    delivery_instructions: str | None = None
    # "Additional comments" on the order (Martin, FZ LLC 2026-09-02): anything
    # for the supplier that is not a delivery instruction. Printed under it.
    additional_comments: str | None = None


async def build_document(
    db: AsyncSession, tenant_id: uuid.UUID, po: PurchaseOrder
) -> PurchaseOrderDocument:
    """Assemble everything the document needs. `po` must be eagerly loaded."""
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one()
    config = (
        await db.execute(
            select(RestaurantConfig).where(RestaurantConfig.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    currency = (config.currency if config else "AED") or "AED"

    # F48: the document date is the day the order was raised IN THE TENANT'S
    # TIME ZONE, not UTC. A PO sent at 21:50 UTC on the 27th was printing
    # "27 Aug" while the buyer in Dubai had raised it on the 28th and the list
    # screen (browser clock) said so. Timestamps are stored tz-aware, so this
    # is a conversion, not a guess; an unknown zone name falls back to UTC.
    try:
        zone: ZoneInfo | timezone = ZoneInfo((config.timezone if config else None) or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        zone = timezone.utc
    raised_at = po.sent_at or po.created_at or datetime.now(timezone.utc)

    location: Location = po.location

    buyer = DocumentParty(
        name=(location.legal_name or tenant.name),
        trn=location.tax_registration_number,
        address_line1=location.address_line1,
        address_line2=location.address_line2,
        city=location.city,
        country=location.country,
        phone=location.phone,
        email=location.email,
    )
    supplier = DocumentParty(
        name=po.supplier.name,
        trn=po.supplier.tax_registration_number,
        contact_name=po.supplier.contact_name,
        address_line1=po.supplier.address_line1,
        address_line2=po.supplier.address_line2,
        city=po.supplier.city,
        country=po.supplier.country,
        phone=po.supplier.phone,
        email=po.supplier.email,
    )

    lines = [
        DocumentLine(
            description=item.ingredient.name,
            supplier_sku=item.supplier_sku,
            quantity=Decimal(str(item.quantity_ordered)),
            unit=item.unit,
            unit_price_minor=Decimal(str(item.unit_price_minor)),
            line_total_minor=Decimal(str(item.line_total_minor)),
            notes=item.notes,
            stock_equivalent=_stock_equivalent(item),
        )
        for item in po.items
    ]

    return PurchaseOrderDocument(
        po_number=po.po_number,
        issue_date=raised_at.astimezone(zone).date(),
        expected_date=po.expected_date,
        currency=currency,
        buyer=buyer,
        supplier=supplier,
        deliver_to_name=location.name,
        deliver_to_lines=DocumentParty(
            name=location.name,
            address_line1=location.address_line1,
            address_line2=location.address_line2,
            city=location.city,
            country=location.country,
        ).address_lines(),
        lines=lines,
        subtotal_minor=Decimal(str(po.subtotal_minor)),
        tax_bps=po.tax_bps,
        tax_minor=Decimal(str(po.tax_minor)),
        total_minor=Decimal(str(po.total_minor)),
        delivery_instructions=po.delivery_instructions,
        additional_comments=po.notes,
    )


# ---------------------------------------------------------------------------
# PLAIN TEXT
# ---------------------------------------------------------------------------


def render_text(doc: PurchaseOrderDocument) -> str:
    """The email's text body. Readable on its own, not a degraded HTML."""
    out: list[str] = []
    out.append(f"PURCHASE ORDER {doc.po_number}")
    out.append("")
    out.append(f"From:   {doc.buyer.name}")
    if doc.buyer.trn:
        out.append(f"        TRN {doc.buyer.trn}")
    for line in doc.buyer.address_lines():
        out.append(f"        {line}")
    if doc.buyer.phone:
        out.append(f"        {doc.buyer.phone}")
    out.append("")
    out.append(f"To:     {doc.supplier.name}")
    if doc.supplier.contact_name:
        out.append(f"        Attn: {doc.supplier.contact_name}")
    out.append("")
    out.append(f"Order date:      {doc.issue_date:%d %b %Y}")
    if doc.expected_date:
        out.append(f"Required by:     {doc.expected_date:%d %b %Y}")
    out.append(f"Deliver to:      {doc.deliver_to_name}")
    for line in doc.deliver_to_lines:
        out.append(f"                 {line}")
    out.append("")
    out.append("-" * 72)
    out.append(f"{'Item':<32}{'Qty':>12}{'Unit price':>14}{'Total':>14}")
    out.append("-" * 72)
    for line in doc.lines:
        name = line.description
        if line.supplier_sku:
            name = f"{name} [{line.supplier_sku}]"
        out.append(
            f"{name[:32]:<32}"
            f"{_qty_str(line.quantity) + ' ' + line.unit:>12}"
            f"{_money_str(line.unit_price_minor, doc.currency):>14}"
            f"{_money_str(line.line_total_minor, doc.currency):>14}"
        )
        if line.stock_equivalent:
            out.append(f"  {line.stock_equivalent}")
        if line.notes:
            out.append(f"  note: {line.notes}")
    out.append("-" * 72)
    out.append(f"{'Subtotal':<58}{_money_str(doc.subtotal_minor, doc.currency):>14}")
    if doc.tax_bps:
        label = f"VAT {doc.tax_bps / 100:g}%"
        out.append(f"{label:<58}{_money_str(doc.tax_minor, doc.currency):>14}")
    out.append(f"{'TOTAL':<58}{_money_str(doc.total_minor, doc.currency):>14}")
    out.append("")
    if doc.delivery_instructions:
        out.append("Delivery instructions:")
        out.append(doc.delivery_instructions)
        out.append("")
    if doc.additional_comments:
        out.append("Additional comments:")
        out.append(doc.additional_comments)
        out.append("")
    out.append("Please confirm receipt of this order and the expected delivery date.")
    out.append("")
    out.append(doc.buyer.name)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_C_INK = "#111827"
_C_MUTED = "#6b7280"
_C_LINE = "#e5e7eb"
_C_BG = "#f9fafb"
_FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif"


def _party_block(title: str, party: DocumentParty) -> str:
    rows = [
        f'<div style="font-size:11px; letter-spacing:1px; text-transform:uppercase; '
        f'color:{_C_MUTED}; margin-bottom:6px;">{html_escape(title)}</div>',
        f'<div style="font-size:15px; font-weight:700; color:{_C_INK};">'
        f"{html_escape(party.name)}</div>",
    ]
    if party.contact_name:
        rows.append(
            f'<div style="font-size:13px; color:{_C_INK};">Attn: '
            f"{html_escape(party.contact_name)}</div>"
        )
    if party.trn:
        rows.append(
            f'<div style="font-size:13px; color:{_C_MUTED};">TRN '
            f"{html_escape(party.trn)}</div>"
        )
    for line in party.address_lines():
        rows.append(
            f'<div style="font-size:13px; color:{_C_MUTED};">{html_escape(line)}</div>'
        )
    for value in (party.phone, party.email):
        if value:
            rows.append(
                f'<div style="font-size:13px; color:{_C_MUTED};">'
                f"{html_escape(value)}</div>"
            )
    return "".join(rows)


def render_html(doc: PurchaseOrderDocument) -> str:
    """A4-shaped document. Inline styles only, so it survives email clients."""
    line_rows = []
    for line in doc.lines:
        sku = (
            f'<div style="font-size:11px; color:{_C_MUTED};">'
            f"{html_escape(line.supplier_sku)}</div>"
            if line.supplier_sku
            else ""
        )
        note = (
            f'<div style="font-size:11px; color:{_C_MUTED};">'
            f"{html_escape(line.notes)}</div>"
            if line.notes
            else ""
        )
        # Martin M8. The supplier is invoiced for cans; the equivalent in the
        # kitchen's own unit sits under it, muted, for whoever checks the
        # delivery in. Empty string when there is no conversion, so a document
        # for an ingredient bought in its stocking unit is unchanged.
        equivalent = (
            f'<div style="font-size:11px; color:{_C_MUTED};">'
            f"{html_escape(line.stock_equivalent)}</div>"
            if line.stock_equivalent
            else ""
        )
        line_rows.append(
            f"""<tr>
<td style="padding:10px 8px; font-size:13px; color:{_C_INK}; border-bottom:1px solid {_C_LINE};">
{html_escape(line.description)}{sku}{note}</td>
<td style="padding:10px 8px; font-size:13px; color:{_C_INK}; text-align:right; white-space:nowrap; border-bottom:1px solid {_C_LINE};">
{html_escape(_qty_str(line.quantity))} {html_escape(line.unit)}{equivalent}</td>
<td style="padding:10px 8px; font-size:13px; color:{_C_INK}; text-align:right; white-space:nowrap; border-bottom:1px solid {_C_LINE};">
{html_escape(_money_str(line.unit_price_minor, doc.currency))}</td>
<td style="padding:10px 8px; font-size:13px; color:{_C_INK}; text-align:right; white-space:nowrap; border-bottom:1px solid {_C_LINE};">
{html_escape(_money_str(line.line_total_minor, doc.currency))}</td>
</tr>"""
        )

    total_rows = [("Subtotal", doc.subtotal_minor, False)]
    if doc.tax_bps:
        total_rows.append((f"VAT {doc.tax_bps / 100:g}%", doc.tax_minor, False))
    total_rows.append(("TOTAL", doc.total_minor, True))
    totals_html = "".join(
        f"""<tr>
<td style="padding:5px 8px; font-size:{'15px' if bold else '13px'}; font-weight:{'700' if bold else '400'}; color:{_C_INK}; text-align:right;">{html_escape(label)}</td>
<td style="padding:5px 8px; font-size:{'15px' if bold else '13px'}; font-weight:{'700' if bold else '400'}; color:{_C_INK}; text-align:right; white-space:nowrap; min-width:120px;">{html_escape(_money_str(value, doc.currency))}</td>
</tr>"""
        for label, value, bold in total_rows
    )

    expected = (
        f'<div style="font-size:13px; color:{_C_INK};"><strong>Required by:</strong> '
        f'{doc.expected_date:%d %b %Y}</div>'
        if doc.expected_date
        else ""
    )
    deliver_lines = "".join(
        f'<div style="font-size:13px; color:{_C_MUTED};">{html_escape(line)}</div>'
        for line in doc.deliver_to_lines
    )
    instructions = (
        f"""<div style="margin-top:20px; padding:12px 14px; background-color:{_C_BG}; border-radius:6px;">
<div style="font-size:11px; letter-spacing:1px; text-transform:uppercase; color:{_C_MUTED}; margin-bottom:4px;">Delivery instructions</div>
<div style="font-size:13px; color:{_C_INK};">{html_escape(doc.delivery_instructions)}</div>
</div>"""
        if doc.delivery_instructions
        else ""
    )
    comments = (
        f"""<div style="margin-top:12px; padding:12px 14px; background-color:{_C_BG}; border-radius:6px;">
<div style="font-size:11px; letter-spacing:1px; text-transform:uppercase; color:{_C_MUTED}; margin-bottom:4px;">Additional comments</div>
<div style="font-size:13px; color:{_C_INK}; white-space:pre-wrap;">{html_escape(doc.additional_comments)}</div>
</div>"""
        if doc.additional_comments
        else ""
    )

    return f"""<!doctype html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Purchase Order {html_escape(doc.po_number)}</title></head>
<body style="margin:0; padding:0; background-color:{_C_BG}; font-family:{_FONT};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{_C_BG};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="760" cellpadding="0" cellspacing="0" style="max-width:760px; width:100%; background-color:#ffffff; border-radius:8px; border:1px solid {_C_LINE};">
<tr><td style="padding:28px 32px;">

<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="vertical-align:top;">{_party_block("From", doc.buyer)}</td>
<td style="vertical-align:top; text-align:right;">
<div style="font-size:22px; font-weight:800; color:{_C_INK}; letter-spacing:1px;">PURCHASE ORDER</div>
<div style="font-size:15px; font-weight:700; color:{_C_INK}; margin-top:4px;">{html_escape(doc.po_number)}</div>
<div style="font-size:13px; color:{_C_MUTED}; margin-top:4px;">{doc.issue_date:%d %b %Y}</div>
</td>
</tr>
</table>

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:26px;">
<tr>
<td style="vertical-align:top; width:50%;">{_party_block("Supplier", doc.supplier)}</td>
<td style="vertical-align:top; width:50%;">
<div style="font-size:11px; letter-spacing:1px; text-transform:uppercase; color:{_C_MUTED}; margin-bottom:6px;">Deliver to</div>
<div style="font-size:15px; font-weight:700; color:{_C_INK};">{html_escape(doc.deliver_to_name)}</div>
{deliver_lines}
{expected}
</td>
</tr>
</table>

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:26px; border-collapse:collapse;">
<tr>
<th style="padding:8px; font-size:11px; letter-spacing:1px; text-transform:uppercase; color:{_C_MUTED}; text-align:left; border-bottom:2px solid {_C_LINE};">Item</th>
<th style="padding:8px; font-size:11px; letter-spacing:1px; text-transform:uppercase; color:{_C_MUTED}; text-align:right; border-bottom:2px solid {_C_LINE};">Quantity</th>
<th style="padding:8px; font-size:11px; letter-spacing:1px; text-transform:uppercase; color:{_C_MUTED}; text-align:right; border-bottom:2px solid {_C_LINE};">Unit price</th>
<th style="padding:8px; font-size:11px; letter-spacing:1px; text-transform:uppercase; color:{_C_MUTED}; text-align:right; border-bottom:2px solid {_C_LINE};">Total</th>
</tr>
{"".join(line_rows)}
</table>

<table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:14px; margin-left:auto;">
{totals_html}
</table>

{instructions}
{comments}

<div style="margin-top:26px; padding-top:16px; border-top:1px solid {_C_LINE}; font-size:12px; color:{_C_MUTED};">
Please confirm receipt of this order and the expected delivery date.
</div>

</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""
