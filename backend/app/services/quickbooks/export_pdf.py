"""
Generate a professional diagnostic PDF report using reportlab.

Produces a multi-section, print-ready A4 document containing:
  1. Cover / Header  -- title, template info, health grade, summary stats
  2. Gap Analysis    -- every template mapping with match status + decisions
  3. Unmapped QB Accounts -- client accounts the template doesn't cover
  4. Recommendations -- auto-generated guidance based on health grade
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

_CLR_PRIMARY = colors.HexColor("#1a56db")       # deep blue
_CLR_PRIMARY_LIGHT = colors.HexColor("#e1effe")  # light blue tint
_CLR_HEADER_BG = colors.HexColor("#1e3a5f")      # dark navy
_CLR_HEADER_FG = colors.white

_CLR_MATCHED_BG = colors.HexColor("#d1fae5")     # green tint
_CLR_MATCHED_FG = colors.HexColor("#065f46")

_CLR_CANDIDATE_BG = colors.HexColor("#fef3c7")   # yellow tint
_CLR_CANDIDATE_FG = colors.HexColor("#92400e")

_CLR_UNMATCHED_BG = colors.HexColor("#fee2e2")   # red tint
_CLR_UNMATCHED_FG = colors.HexColor("#991b1b")

_CLR_GRADE_MAP: dict[str, colors.HexColor] = {
    "A": colors.HexColor("#059669"),  # green
    "B": colors.HexColor("#2563eb"),  # blue
    "C": colors.HexColor("#d97706"),  # orange
    "F": colors.HexColor("#dc2626"),  # red
}

_CLR_BORDER = colors.HexColor("#d1d5db")   # light grey
_CLR_ROW_ALT = colors.HexColor("#f9fafb")  # very light grey (alternating)
_CLR_WHITE = colors.white


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

def _build_styles() -> dict[str, ParagraphStyle]:
    """Return a dict of reusable ParagraphStyles."""
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "PDFTitle",
            parent=base["Title"],
            fontSize=22,
            leading=28,
            textColor=_CLR_HEADER_BG,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "PDFSubtitle",
            parent=base["Normal"],
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#6b7280"),
            spaceAfter=12,
        ),
        "section": ParagraphStyle(
            "PDFSection",
            parent=base["Heading2"],
            fontSize=14,
            leading=18,
            textColor=_CLR_HEADER_BG,
            spaceBefore=18,
            spaceAfter=8,
            borderWidth=0,
            borderPadding=0,
        ),
        "body": ParagraphStyle(
            "PDFBody",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#374151"),
        ),
        "body_bold": ParagraphStyle(
            "PDFBodyBold",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#374151"),
            fontName="Helvetica-Bold",
        ),
        "cell": ParagraphStyle(
            "PDFCell",
            parent=base["Normal"],
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#374151"),
            wordWrap="CJK",
        ),
        "cell_bold": ParagraphStyle(
            "PDFCellBold",
            parent=base["Normal"],
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#374151"),
            fontName="Helvetica-Bold",
            wordWrap="CJK",
        ),
        "cell_header": ParagraphStyle(
            "PDFCellHeader",
            parent=base["Normal"],
            fontSize=7.5,
            leading=10,
            textColor=_CLR_WHITE,
            fontName="Helvetica-Bold",
            wordWrap="CJK",
        ),
        "stat_value": ParagraphStyle(
            "PDFStatValue",
            parent=base["Normal"],
            fontSize=18,
            leading=22,
            textColor=_CLR_HEADER_BG,
            fontName="Helvetica-Bold",
            alignment=TA_CENTER,
        ),
        "stat_label": ParagraphStyle(
            "PDFStatLabel",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#6b7280"),
            alignment=TA_CENTER,
        ),
        "grade": ParagraphStyle(
            "PDFGrade",
            parent=base["Normal"],
            fontSize=48,
            leading=52,
            fontName="Helvetica-Bold",
            alignment=TA_CENTER,
        ),
        "recommendation": ParagraphStyle(
            "PDFRecommendation",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#374151"),
            spaceBefore=6,
            spaceAfter=4,
        ),
    }


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_header(report: dict, styles: dict[str, ParagraphStyle]) -> list:
    """Section 1: Cover / Header with title, template info, grade, stats."""
    elements: list = []

    # Title
    elements.append(Paragraph("QuickBooks Diagnostic Report", styles["title"]))

    # Template + date line
    template_name = report.get("template_name", report.get("template_key", ""))
    created_at = report.get("created_at", "")
    if isinstance(created_at, str) and "T" in created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            date_str = dt.strftime("%B %d, %Y at %H:%M UTC")
        except (ValueError, TypeError):
            date_str = created_at
    else:
        date_str = str(created_at)

    elements.append(
        Paragraph(
            f"Template: <b>{_esc(template_name)}</b> &nbsp;|&nbsp; "
            f"Generated: {_esc(date_str)}",
            styles["subtitle"],
        )
    )

    # Grade + summary stats in a horizontal layout
    grade = report.get("health_grade", "?")
    grade_color = _CLR_GRADE_MAP.get(grade, colors.HexColor("#6b7280"))

    grade_style = ParagraphStyle(
        "GradeInline",
        parent=styles["grade"],
        textColor=grade_color,
    )

    grade_cell = [
        Paragraph(grade, grade_style),
        Paragraph("Health Grade", styles["stat_label"]),
    ]

    total = report.get("total_template_mappings", 0)
    matched = report.get("matched", 0)
    candidates = report.get("candidates", 0)
    unmatched = report.get("unmatched", 0)
    coverage = report.get("coverage_pct", 0)

    stat_cells = [
        _stat_block(str(total), "Total Mappings", styles),
        _stat_block(str(matched), "Matched", styles),
        _stat_block(str(candidates), "Candidates", styles),
        _stat_block(str(unmatched), "Unmatched", styles),
        _stat_block(f"{coverage}%", "Coverage", styles),
    ]

    # Build a table: grade on the left, stats on the right
    avail_width = A4[0] - 2 * 1.5 * cm
    grade_col_w = 2.5 * cm
    stat_col_w = (avail_width - grade_col_w) / len(stat_cells)

    row_data = [grade_cell] + stat_cells
    tbl = Table(
        [row_data],
        colWidths=[grade_col_w] + [stat_col_w] * len(stat_cells),
        rowHeights=[None],
    )
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.5, _CLR_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, _CLR_BORDER),
        ("BACKGROUND", (0, 0), (0, 0), _CLR_PRIMARY_LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))

    elements.append(tbl)
    elements.append(Spacer(1, 12))

    return elements


def _stat_block(
    value: str,
    label: str,
    styles: dict[str, ParagraphStyle],
) -> list:
    """Helper: returns a list of two Paragraphs (value + label) for a stat cell."""
    return [
        Paragraph(value, styles["stat_value"]),
        Paragraph(label, styles["stat_label"]),
    ]


def _build_gap_analysis(report: dict, styles: dict[str, ParagraphStyle]) -> list:
    """Section 2: Gap Analysis Table -- all template mapping items."""
    elements: list = []
    elements.append(Paragraph("Gap Analysis", styles["section"]))

    items: list[dict] = report.get("items", [])
    if not items:
        elements.append(Paragraph("No mapping items in report.", styles["body"]))
        return elements

    # Table header
    headers = ["#", "Mapping Type", "Template Account", "Status",
               "Best Match", "Score", "Decision"]
    header_paras = [Paragraph(h, styles["cell_header"]) for h in headers]

    table_data = [header_paras]

    for idx, item in enumerate(items, start=1):
        status = item.get("status", "unmatched")
        best_match = item.get("best_match") or {}
        score_raw = best_match.get("score", 0)
        score_str = f"{score_raw:.0%}" if isinstance(score_raw, (int, float)) else str(score_raw)

        decision = item.get("decision") or ""
        decision_name = item.get("decision_account_name") or ""
        decision_display = decision
        if decision_name and decision != decision_name:
            decision_display = f"{decision}: {decision_name}"

        row = [
            Paragraph(str(idx), styles["cell"]),
            Paragraph(_esc(item.get("mapping_type", "")), styles["cell"]),
            Paragraph(_esc(item.get("template_account_name", "")), styles["cell_bold"]),
            Paragraph(_status_label(status), styles["cell_bold"]),
            Paragraph(_esc(best_match.get("qb_account_name", "-")), styles["cell"]),
            Paragraph(score_str, styles["cell"]),
            Paragraph(_esc(decision_display), styles["cell"]),
        ]
        table_data.append(row)

    # Column widths (A4 usable ~ 18 cm)
    avail = A4[0] - 2 * 1.5 * cm
    col_widths = [
        0.6 * cm,      # #
        2.5 * cm,       # Mapping Type
        4.0 * cm,       # Template Account
        2.0 * cm,       # Status
        4.5 * cm,       # Best Match
        1.3 * cm,       # Score
        avail - (0.6 + 2.5 + 4.0 + 2.0 + 4.5 + 1.3) * cm,  # Decision
    ]

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    style_cmds: list[tuple] = [
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), _CLR_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), _CLR_WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7.5),

        # Grid
        ("GRID", (0, 0), (-1, -1), 0.25, _CLR_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]

    # Row-level status colouring
    for row_idx, item in enumerate(items, start=1):
        status = item.get("status", "unmatched")
        if status == "matched":
            style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), _CLR_MATCHED_BG))
        elif status == "candidates":
            style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), _CLR_CANDIDATE_BG))
        elif status == "unmatched":
            style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), _CLR_UNMATCHED_BG))

    tbl.setStyle(TableStyle(style_cmds))
    elements.append(tbl)
    elements.append(Spacer(1, 12))

    # Legend
    legend_data = [
        [
            _colour_swatch(_CLR_MATCHED_BG, "Matched", styles),
            _colour_swatch(_CLR_CANDIDATE_BG, "Candidates", styles),
            _colour_swatch(_CLR_UNMATCHED_BG, "Unmatched", styles),
        ]
    ]
    legend_tbl = Table(legend_data, colWidths=[4 * cm, 4 * cm, 4 * cm])
    legend_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(legend_tbl)
    elements.append(Spacer(1, 8))

    return elements


def _build_unmapped_accounts(report: dict, styles: dict[str, ParagraphStyle]) -> list:
    """Section 3: Unmapped QB Accounts table."""
    elements: list = []
    elements.append(Paragraph("Unmapped QuickBooks Accounts", styles["section"]))

    unmapped: list[dict] = report.get("unmapped_qb_accounts", [])
    if not unmapped:
        elements.append(
            Paragraph(
                "All client QB accounts are covered by this template.",
                styles["body"],
            )
        )
        return elements

    elements.append(
        Paragraph(
            f"The client has <b>{len(unmapped)}</b> QuickBooks account(s) that are "
            "not mapped by this template. These may be irrelevant to POS sync "
            "or may indicate the template needs extending.",
            styles["body"],
        )
    )
    elements.append(Spacer(1, 6))

    headers = ["#", "QB Account Name", "Account Type", "Suggested POS Type"]
    header_paras = [Paragraph(h, styles["cell_header"]) for h in headers]
    table_data = [header_paras]

    for idx, acct in enumerate(unmapped, start=1):
        row = [
            Paragraph(str(idx), styles["cell"]),
            Paragraph(_esc(acct.get("qb_account_name", "")), styles["cell_bold"]),
            Paragraph(_esc(acct.get("qb_account_type", "")), styles["cell"]),
            Paragraph(_esc(acct.get("suggested_mapping_type", "-")), styles["cell"]),
        ]
        table_data.append(row)

    avail = A4[0] - 2 * 1.5 * cm
    col_widths = [
        0.8 * cm,
        avail * 0.40,
        avail * 0.25,
        avail - 0.8 * cm - avail * 0.40 - avail * 0.25,
    ]

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    style_cmds: list[tuple] = [
        ("BACKGROUND", (0, 0), (-1, 0), _CLR_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), _CLR_WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.25, _CLR_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]

    # Alternating row backgrounds for readability
    for row_idx in range(1, len(table_data)):
        if row_idx % 2 == 0:
            style_cmds.append(
                ("BACKGROUND", (0, row_idx), (-1, row_idx), _CLR_ROW_ALT)
            )

    tbl.setStyle(TableStyle(style_cmds))
    elements.append(tbl)
    elements.append(Spacer(1, 12))

    return elements


def _build_recommendations(report: dict, styles: dict[str, ParagraphStyle]) -> list:
    """Section 4: Recommendations based on health grade."""
    elements: list = []
    elements.append(Paragraph("Recommendations", styles["section"]))

    grade = report.get("health_grade", "F")
    matched = report.get("matched", 0)
    candidates = report.get("candidates", 0)
    unmatched = report.get("unmatched", 0)
    total = report.get("total_template_mappings", 0)
    coverage = report.get("coverage_pct", 0)

    grade_color = _CLR_GRADE_MAP.get(grade, colors.HexColor("#6b7280"))

    # Grade badge inline
    elements.append(
        Paragraph(
            f'Overall Grade: <font color="{grade_color.hexval()}" size="16">'
            f'<b>{grade}</b></font> &nbsp; ({coverage}% coverage)',
            styles["body_bold"],
        )
    )
    elements.append(Spacer(1, 8))

    if grade == "A":
        elements.append(
            Paragraph(
                "Ready to apply. All mappings auto-matched with high confidence. "
                "No manual review is required. You can proceed to apply the "
                "template and start syncing orders to QuickBooks immediately.",
                styles["recommendation"],
            )
        )
    elif grade == "B":
        elements.append(
            Paragraph(
                f"Review <b>{candidates}</b> candidate mapping(s) before applying. "
                "These mappings have potential matches but the confidence score "
                "is below the auto-match threshold. For each candidate, verify "
                "that the suggested QB account is correct, or select an "
                "alternative from the candidate list.",
                styles["recommendation"],
            )
        )
    elif grade == "C":
        elements.append(
            Paragraph(
                f"<b>{unmatched}</b> mapping(s) need attention. No matching "
                "QuickBooks accounts were found for these template entries. "
                "Options for each unmatched item:",
                styles["recommendation"],
            )
        )
        elements.append(
            Paragraph(
                "&bull; &nbsp;<b>Create new</b> -- Create the account in "
                "QuickBooks with the recommended name and type.<br/>"
                "&bull; &nbsp;<b>Map to existing</b> -- Choose an existing "
                "QB account that serves the same purpose.<br/>"
                "&bull; &nbsp;<b>Skip</b> -- Omit this mapping (only if the "
                "POS does not use this account type).",
                styles["recommendation"],
            )
        )
        if candidates > 0:
            elements.append(
                Paragraph(
                    f"Additionally, <b>{candidates}</b> candidate mapping(s) "
                    "should be reviewed for accuracy.",
                    styles["recommendation"],
                )
            )
    else:  # F
        elements.append(
            Paragraph(
                f"Low coverage ({coverage}%). Only <b>{matched}</b> of "
                f"<b>{total}</b> required mappings could be matched. "
                "This template may not be suitable for this QuickBooks setup. "
                "Consider the following:",
                styles["recommendation"],
            )
        )
        elements.append(
            Paragraph(
                "&bull; &nbsp;<b>Try a different template</b> -- A template "
                "designed for a different business type or region may be a "
                "better fit.<br/>"
                "&bull; &nbsp;<b>Customize heavily</b> -- Create all missing "
                "accounts in QuickBooks, then re-run the diagnostic.<br/>"
                "&bull; &nbsp;<b>Contact support</b> -- The POS team can "
                "create a custom template tailored to this Chart of Accounts.",
                styles["recommendation"],
            )
        )

    elements.append(Spacer(1, 16))

    # Footer
    elements.append(
        Paragraph(
            f"Report ID: {report.get('id', 'N/A')}",
            ParagraphStyle(
                "Footer",
                parent=styles["body"],
                fontSize=7,
                textColor=colors.HexColor("#9ca3af"),
            ),
        )
    )

    return elements


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    """Escape XML-special characters for reportlab Paragraph markup."""
    if not text:
        return ""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _status_label(status: str) -> str:
    """Return a human-readable status label."""
    return {
        "matched": "Matched",
        "candidates": "Candidates",
        "unmatched": "Unmatched",
    }.get(status, status.title())


def _colour_swatch(bg: colors.HexColor, label: str, styles: dict) -> list:
    """Build a small coloured swatch + label for the legend."""
    # We return a list so it can be used as a Table cell
    swatch_tbl = Table(
        [[Paragraph(f"&nbsp;&nbsp; {label}", styles["cell_bold"])]],
        colWidths=[3.5 * cm],
        rowHeights=[0.5 * cm],
    )
    swatch_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("BOX", (0, 0), (-1, -1), 0.25, _CLR_BORDER),
    ]))
    return swatch_tbl


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_diagnostic_pdf(report: dict) -> bytes:
    """
    Generate a professional diagnostic PDF from a report dict.

    Args:
        report: Diagnostic report dict as returned by
                ``DiagnosticService.run_diagnostic()``.

    Returns:
        PDF file content as bytes, ready to be written to disk or
        returned as an HTTP response.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="QuickBooks Diagnostic Report",
        author="POS System",
    )

    styles = _build_styles()

    elements: list = []
    elements.extend(_build_header(report, styles))
    elements.extend(_build_gap_analysis(report, styles))
    elements.extend(_build_unmapped_accounts(report, styles))
    elements.extend(_build_recommendations(report, styles))

    doc.build(elements)
    return buf.getvalue()
