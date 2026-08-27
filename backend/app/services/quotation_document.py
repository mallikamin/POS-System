"""The quotation as an A4 document, and as the body of the email that sends it.

Same shape and the same reasoning as `purchase_order_document`: one structure,
two renderings, built together so the printed copy and the emailed copy can
never say different things.

The issuing identity comes from the LOCATION when there is one, falling back to
the tenant, exactly as the tax invoice does -- a tenant may trade under a
different registered entity per site, and a B2B customer needs to know which
one is offering them a price.

🔴 Money is INTEGER MINOR UNITS (sales-side convention). `_money_str` is the
only place that divides by 100, and it does so purely for display. VAT is
BACKED OUT of the total rather than added, because the prices already include
it -- adding 5% to a price that already contains 5% overstates the tax on every
document.
"""

from __future__ import annotations

import uuid
from html import escape as html_escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quotation import Quotation
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.services.quotation_service import display_status

# F26: was missing AED and fell back to an empty symbol, on a document
# that goes to the customer. Shared table now.
from app.utils.money import currency_symbol

_C_INK = "#111827"
_C_MUTED = "#6b7280"
_C_LINE = "#e5e7eb"
_C_BG = "#f9fafb"
_FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif"


def _money_str(minor: int, currency: str) -> str:
    amount = int(minor) / 100
    symbol = currency_symbol(currency)
    return f"{symbol}{amount:,.2f}" if symbol else f"{amount:,.2f} {currency}"


async def build_context(
    db: AsyncSession, tenant_id: uuid.UUID, quotation: Quotation
) -> dict:
    """Everything both renderings need. `quotation` must be eagerly loaded."""
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one()
    config = (
        await db.execute(
            select(RestaurantConfig).where(RestaurantConfig.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()

    location = quotation.location
    issuer_lines = []
    if location is not None:
        for value in (
            location.address_line1,
            location.address_line2,
            ", ".join(p for p in (location.city, location.country) if p) or None,
            location.phone,
            location.email,
        ):
            if value:
                issuer_lines.append(value)

    return {
        "currency": (config.currency if config else "AED") or "AED",
        "issuer_name": (
            location.legal_name
            if location is not None and location.legal_name
            else tenant.name
        ),
        "issuer_trn": location.tax_registration_number if location else None,
        "issuer_lines": issuer_lines,
        "status": display_status(quotation),
        "quotation": quotation,
    }


# ---------------------------------------------------------------------------
# PLAIN TEXT
# ---------------------------------------------------------------------------


def render_text(context: dict) -> str:
    quotation: Quotation = context["quotation"]
    currency = context["currency"]
    out: list[str] = []

    out.append(f"QUOTATION {quotation.quote_number}")
    out.append("")
    out.append(f"From:   {context['issuer_name']}")
    if context["issuer_trn"]:
        out.append(f"        TRN {context['issuer_trn']}")
    for line in context["issuer_lines"]:
        out.append(f"        {line}")
    out.append("")
    out.append(f"To:     {quotation.customer_name}")
    if quotation.customer_trn:
        out.append(f"        TRN {quotation.customer_trn}")
    if quotation.customer_address:
        out.append(f"        {quotation.customer_address}")
    out.append("")
    out.append(f"Date:         {quotation.issue_date:%d %b %Y}")
    out.append(f"Valid until:  {quotation.valid_until:%d %b %Y}")
    out.append("")
    out.append("-" * 68)
    out.append(f"{'Item':<38}{'Qty':>6}{'Price':>12}{'Total':>12}")
    out.append("-" * 68)
    for item in sorted(quotation.items, key=lambda i: i.display_order):
        out.append(
            f"{item.name[:38]:<38}{item.quantity:>6}"
            f"{_money_str(item.unit_price_minor, currency):>12}"
            f"{_money_str(item.line_total_minor, currency):>12}"
        )
        if item.description:
            out.append(f"  {item.description}")
    out.append("-" * 68)
    out.append(f"{'Subtotal':<56}{_money_str(quotation.subtotal_minor, currency):>12}")
    if quotation.discount_minor:
        out.append(
            f"{'Discount':<56}{'-' + _money_str(quotation.discount_minor, currency):>12}"
        )
    if quotation.tax_rate_bps:
        label = f"of which VAT {quotation.tax_rate_bps / 100:g}%"
        out.append(f"{label:<56}{_money_str(quotation.tax_minor, currency):>12}")
    out.append(f"{'TOTAL':<56}{_money_str(quotation.total_minor, currency):>12}")
    out.append("")
    if quotation.notes:
        out.append(quotation.notes)
        out.append("")
    if quotation.terms:
        out.append("Terms:")
        out.append(quotation.terms)
        out.append("")
    out.append(
        f"This quotation is valid until {quotation.valid_until:%d %b %Y}."
    )
    out.append("")
    out.append(context["issuer_name"])
    return "\n".join(out)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------


def render_html(context: dict) -> str:
    quotation: Quotation = context["quotation"]
    currency = context["currency"]

    issuer_block = "".join(
        f'<div style="font-size:13px; color:{_C_MUTED};">{html_escape(line)}</div>'
        for line in context["issuer_lines"]
    )
    trn_block = (
        f'<div style="font-size:13px; color:{_C_MUTED};">TRN '
        f"{html_escape(context['issuer_trn'])}</div>"
        if context["issuer_trn"]
        else ""
    )

    customer_extra = "".join(
        f'<div style="font-size:13px; color:{_C_MUTED};">{html_escape(value)}</div>'
        for value in (
            f"TRN {quotation.customer_trn}" if quotation.customer_trn else None,
            quotation.customer_address,
            quotation.customer_phone,
            quotation.customer_email,
        )
        if value
    )

    rows = []
    for item in sorted(quotation.items, key=lambda i: i.display_order):
        description = (
            f'<div style="font-size:11px; color:{_C_MUTED};">'
            f"{html_escape(item.description)}</div>"
            if item.description
            else ""
        )
        rows.append(
            f"""<tr>
<td style="padding:10px 8px; font-size:13px; color:{_C_INK}; border-bottom:1px solid {_C_LINE};">
{html_escape(item.name)}{description}</td>
<td style="padding:10px 8px; font-size:13px; color:{_C_INK}; text-align:right; border-bottom:1px solid {_C_LINE};">{item.quantity}</td>
<td style="padding:10px 8px; font-size:13px; color:{_C_INK}; text-align:right; white-space:nowrap; border-bottom:1px solid {_C_LINE};">{html_escape(_money_str(item.unit_price_minor, currency))}</td>
<td style="padding:10px 8px; font-size:13px; color:{_C_INK}; text-align:right; white-space:nowrap; border-bottom:1px solid {_C_LINE};">{html_escape(_money_str(item.line_total_minor, currency))}</td>
</tr>"""
        )

    totals = [("Subtotal", quotation.subtotal_minor, False)]
    if quotation.discount_minor:
        totals.append(("Discount", -quotation.discount_minor, False))
    if quotation.tax_rate_bps:
        totals.append(
            (f"of which VAT {quotation.tax_rate_bps / 100:g}%", quotation.tax_minor, False)
        )
    totals.append(("TOTAL", quotation.total_minor, True))
    totals_html = "".join(
        f"""<tr>
<td style="padding:5px 8px; font-size:{'15px' if bold else '13px'}; font-weight:{'700' if bold else '400'}; color:{_C_INK}; text-align:right;">{html_escape(label)}</td>
<td style="padding:5px 8px; font-size:{'15px' if bold else '13px'}; font-weight:{'700' if bold else '400'}; color:{_C_INK}; text-align:right; white-space:nowrap; min-width:120px;">{html_escape(_money_str(value, currency))}</td>
</tr>"""
        for label, value, bold in totals
    )

    extra_blocks = ""
    for heading, body in (("Notes", quotation.notes), ("Terms", quotation.terms)):
        if body:
            extra_blocks += f"""<div style="margin-top:18px; padding:12px 14px; background-color:{_C_BG}; border-radius:6px;">
<div style="font-size:11px; letter-spacing:1px; text-transform:uppercase; color:{_C_MUTED}; margin-bottom:4px;">{heading}</div>
<div style="font-size:13px; color:{_C_INK}; white-space:pre-wrap;">{html_escape(body)}</div>
</div>"""

    return f"""<!doctype html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quotation {html_escape(quotation.quote_number)}</title></head>
<body style="margin:0; padding:0; background-color:{_C_BG}; font-family:{_FONT};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{_C_BG};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="760" cellpadding="0" cellspacing="0" style="max-width:760px; width:100%; background-color:#ffffff; border-radius:8px; border:1px solid {_C_LINE};">
<tr><td style="padding:28px 32px;">

<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="vertical-align:top;">
<div style="font-size:11px; letter-spacing:1px; text-transform:uppercase; color:{_C_MUTED}; margin-bottom:6px;">From</div>
<div style="font-size:15px; font-weight:700; color:{_C_INK};">{html_escape(context['issuer_name'])}</div>
{trn_block}{issuer_block}
</td>
<td style="vertical-align:top; text-align:right;">
<div style="font-size:22px; font-weight:800; color:{_C_INK}; letter-spacing:1px;">QUOTATION</div>
<div style="font-size:15px; font-weight:700; color:{_C_INK}; margin-top:4px;">{html_escape(quotation.quote_number)}</div>
<div style="font-size:13px; color:{_C_MUTED}; margin-top:4px;">{quotation.issue_date:%d %b %Y}</div>
<div style="font-size:13px; color:{_C_INK}; margin-top:8px;"><strong>Valid until {quotation.valid_until:%d %b %Y}</strong></div>
</td>
</tr>
</table>

<div style="margin-top:26px;">
<div style="font-size:11px; letter-spacing:1px; text-transform:uppercase; color:{_C_MUTED}; margin-bottom:6px;">Prepared for</div>
<div style="font-size:15px; font-weight:700; color:{_C_INK};">{html_escape(quotation.customer_name)}</div>
{customer_extra}
</div>

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:26px; border-collapse:collapse;">
<tr>
<th style="padding:8px; font-size:11px; letter-spacing:1px; text-transform:uppercase; color:{_C_MUTED}; text-align:left; border-bottom:2px solid {_C_LINE};">Item</th>
<th style="padding:8px; font-size:11px; letter-spacing:1px; text-transform:uppercase; color:{_C_MUTED}; text-align:right; border-bottom:2px solid {_C_LINE};">Qty</th>
<th style="padding:8px; font-size:11px; letter-spacing:1px; text-transform:uppercase; color:{_C_MUTED}; text-align:right; border-bottom:2px solid {_C_LINE};">Price</th>
<th style="padding:8px; font-size:11px; letter-spacing:1px; text-transform:uppercase; color:{_C_MUTED}; text-align:right; border-bottom:2px solid {_C_LINE};">Total</th>
</tr>
{"".join(rows)}
</table>

<table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:14px; margin-left:auto;">
{totals_html}
</table>

{extra_blocks}

<div style="margin-top:26px; padding-top:16px; border-top:1px solid {_C_LINE}; font-size:12px; color:{_C_MUTED};">
Prices shown include VAT where applicable. This quotation is valid until {quotation.valid_until:%d %b %Y}.
</div>

</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""
