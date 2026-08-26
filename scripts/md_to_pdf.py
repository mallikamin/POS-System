"""Render a client-facing Markdown document to a clean, branded PDF.

Written for the FZ LLC deliverables (the UAT walkthrough and the proposal), but
deliberately general: any document written in the restricted Markdown subset
below renders correctly.

    python scripts/md_to_pdf.py <input.md> <output.pdf> [--title "..."] \
        [--subtitle "..."]

Supported Markdown
------------------
    # ## ###      headings
    paragraphs    blank-line separated
    - item        bullet list
    1. item       numbered list
    > text        callout box
    | a | b |     table, with the --- separator row
    ---           horizontal rule
    **bold**  *italic*  `code`   inline

Anything else is rendered as plain text rather than silently dropped, because a
client document quietly losing a line is worse than one with an odd-looking
line in it.

Why reportlab rather than an HTML-to-PDF converter: it is already a dependency
of this project (the Z-report and receipt printing use it), it needs no browser
or system binary, and it produces the same output on every machine. A
"print to PDF from the browser" step depends on whoever is doing the printing.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#6b7280")
LINE = colors.HexColor("#e5e7eb")
ACCENT = colors.HexColor("#1d4ed8")
CALLOUT_BG = colors.HexColor("#f3f4f6")
TABLE_HEAD = colors.HexColor("#f9fafb")


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=22,
            textColor=INK,
            spaceBefore=16,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13.5,
            leading=18,
            textColor=INK,
            spaceBefore=14,
            spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "H3",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=15,
            textColor=INK,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.8,
            leading=14.5,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=7,
        ),
        "callout": ParagraphStyle(
            "Callout",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.3,
            leading=13.5,
            textColor=INK,
            leftIndent=8,
            rightIndent=8,
            spaceBefore=4,
            spaceAfter=4,
        ),
        "cell": ParagraphStyle(
            "Cell",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.8,
            leading=12,
            textColor=INK,
            spaceAfter=0,
        ),
        "cellhead": ParagraphStyle(
            "CellHead",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.8,
            leading=12,
            textColor=INK,
            spaceAfter=0,
        ),
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=30,
            textColor=INK,
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=16,
            textColor=MUTED,
            spaceAfter=24,
        ),
    }


# ---------------------------------------------------------------------------
# INLINE FORMATTING
# ---------------------------------------------------------------------------

# Emoji and other symbols outside the Helvetica repertoire render as black
# boxes in a PDF, which looks broken. Mapped to something a PDF can draw, or
# dropped, rather than shipped as tofu.
_SYMBOLS = {
    # Deliberately ASCII, not HTML entities. The standard PDF Helvetica has no
    # glyph for an arrow or a warning sign, and reportlab draws a missing glyph
    # as NOTHING -- so `raw -> dough -> croissant` silently became
    # `raw   dough   croissant`, which is worse than a plain hyphen-arrow. If
    # these ever need to be real symbols, embed a font that has them.
    "⚠️": "NOTE: ",
    "⚠": "NOTE: ",
    "🔴": "",
    "🟢": "",
    "📌": "",
    "→": "-&gt;",
    "←": "&lt;-",
    "×": "x",
    "—": " - ",
    "–": "-",
    "’": "'",
    "‘": "'",
    "“": '"',
    "”": '"',
    "…": "...",
    "£": "GBP ",
    "•": "-",
}


def inline(text: str) -> str:
    """Markdown inline formatting to reportlab's mini-HTML."""
    # Escape FIRST, so a stray `<` or `&` in the source cannot break the
    # parser. Only then substitute the symbols, because several of their
    # replacements are HTML entities and escaping after would turn `&#9888;`
    # into the literal text `&amp;#9888;` on the page.
    text = html.escape(text, quote=False)
    for symbol, replacement in _SYMBOLS.items():
        text = text.replace(symbol, replacement)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(
        r"`(.+?)`",
        r'<font face="Courier" size="8.6">\1</font>',
        text,
    )
    # [label](url) -> label, with the URL kept visible. A PDF a client prints
    # loses the hyperlink, so the address has to be readable on paper.
    text = re.sub(r"\[(.+?)\]\((https?://[^)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"\[(.+?)\]\(([^)]+)\)", r"\1", text)
    return text


# ---------------------------------------------------------------------------
# BLOCK PARSING
# ---------------------------------------------------------------------------


def _table(rows: list[str], st: dict, width: float) -> Table:
    parsed = []
    for row in rows:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        parsed.append(cells)

    # Drop the |---|---| separator row.
    body = [
        r
        for r in parsed
        if not all(re.fullmatch(r":?-{2,}:?", c or "") for c in r if c != "")
        or not r
    ]
    if len(parsed) > 1 and all(
        re.fullmatch(r":?-{2,}:?", c) for c in parsed[1] if c
    ):
        body = [parsed[0]] + parsed[2:]

    columns = max(len(r) for r in body)
    data = []
    for index, row in enumerate(body):
        padded = row + [""] * (columns - len(row))
        style = st["cellhead"] if index == 0 else st["cell"]
        data.append([Paragraph(inline(c), style) for c in padded])

    table = Table(data, colWidths=[width / columns] * columns, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEAD),
                ("LINEBELOW", (0, 0), (-1, 0), 0.9, LINE),
                ("LINEBELOW", (0, 1), (-1, -2), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _callout(lines: list[str], st: dict, width: float) -> Table:
    paragraphs = []
    buffer: list[str] = []
    for line in lines:
        if line.strip():
            buffer.append(line.strip())
        elif buffer:
            paragraphs.append(Paragraph(inline(" ".join(buffer)), st["callout"]))
            buffer = []
    if buffer:
        paragraphs.append(Paragraph(inline(" ".join(buffer)), st["callout"]))

    table = Table([[paragraphs]], colWidths=[width])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CALLOUT_BG),
                ("LINEBEFORE", (0, 0), (0, -1), 2.5, ACCENT),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def build_flowables(markdown: str, st: dict, width: float) -> list:
    lines = markdown.replace("\r\n", "\n").split("\n")
    flow: list = []
    index = 0
    bullets: list[str] = []
    numbers: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            flow.append(Paragraph(inline(" ".join(paragraph)), st["body"]))
            paragraph = []

    def flush_lists() -> None:
        nonlocal bullets, numbers
        for items, kind, mark in (
            (bullets, "bullet", "•"),
            (numbers, "1", None),
        ):
            if items:
                flow.append(
                    ListFlowable(
                        [
                            ListItem(
                                Paragraph(inline(text), st["body"]), leftIndent=16
                            )
                            for text in items
                        ],
                        bulletType=kind,
                        bulletFontSize=8,
                        start=mark,
                        leftIndent=14,
                    )
                )
                flow.append(Spacer(1, 3))
        bullets, numbers = [], []

    def flush_all() -> None:
        flush_paragraph()
        flush_lists()

    while index < len(lines):
        raw = lines[index]
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            flush_all()
            index += 1
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            flush_all()
            block = []
            while (
                index < len(lines)
                and lines[index].strip().startswith("|")
                and lines[index].strip().endswith("|")
            ):
                block.append(lines[index])
                index += 1
            flow.append(Spacer(1, 4))
            flow.append(_table(block, st, width))
            flow.append(Spacer(1, 9))
            continue

        if stripped.startswith(">"):
            flush_all()
            block = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                block.append(lines[index].strip().lstrip(">").strip())
                index += 1
            flow.append(Spacer(1, 4))
            flow.append(_callout(block, st, width))
            flow.append(Spacer(1, 9))
            continue

        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", stripped):
            flush_all()
            flow.append(Spacer(1, 6))
            flow.append(HRFlowable(width="100%", thickness=0.6, color=LINE))
            flow.append(Spacer(1, 8))
            index += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            flush_all()
            level = len(heading.group(1))
            style = st["h1"] if level == 1 else st["h2"] if level == 2 else st["h3"]
            # A heading with nothing under it at the foot of a page is a
            # widow; keep it with whatever follows.
            flow.append(
                KeepTogether(
                    [Paragraph(inline(heading.group(2)), style), Spacer(1, 1)]
                )
            )
            index += 1
            continue

        bullet = re.match(r"^\s*[-*+]\s+(.*)$", line)
        if bullet:
            flush_paragraph()
            if numbers:
                flush_lists()
            bullets.append(bullet.group(1))
            index += 1
            continue

        numbered = re.match(r"^\s*\d+[.)]\s+(.*)$", line)
        if numbered:
            flush_paragraph()
            if bullets:
                flush_lists()
            numbers.append(numbered.group(1))
            index += 1
            continue

        if bullets or numbers:
            # A wrapped continuation of the last list item.
            target = bullets if bullets else numbers
            target[-1] = f"{target[-1]} {stripped}"
            index += 1
            continue

        paragraph.append(stripped)
        index += 1

    flush_all()
    return flow


# ---------------------------------------------------------------------------
# DOCUMENT
# ---------------------------------------------------------------------------


def render(
    source: Path, target: Path, title: str | None, subtitle: str | None
) -> None:
    markdown = source.read_text(encoding="utf-8")
    st = _styles()

    margin = 18 * mm
    width = A4[0] - 2 * margin

    doc = BaseDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=20 * mm,
        title=title or source.stem,
        author="Sitara Infotech",
    )

    def footer(canvas, document) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7.6)
        canvas.setFillColor(MUTED)
        canvas.drawString(margin, 12 * mm, "Sitara Infotech")
        canvas.drawRightString(
            A4[0] - margin, 12 * mm, f"Page {document.page}"
        )
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(margin, 15 * mm, A4[0] - margin, 15 * mm)
        canvas.restoreState()

    frame = Frame(
        margin,
        20 * mm,
        width,
        A4[1] - margin - 20 * mm,
        id="body",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=footer)])

    flow: list = []
    if title:
        flow.append(Spacer(1, 26 * mm))
        flow.append(Paragraph(inline(title), st["title"]))
        if subtitle:
            flow.append(Paragraph(inline(subtitle), st["subtitle"]))
        flow.append(HRFlowable(width="100%", thickness=1.2, color=ACCENT))
        flow.append(PageBreak())

    flow.extend(build_flowables(markdown, st, width))
    doc.build(flow)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("target")
    parser.add_argument("--title", default=None)
    parser.add_argument("--subtitle", default=None)
    args = parser.parse_args()

    source = Path(args.source)
    if not source.is_file():
        print(f"No such file: {source}", file=sys.stderr)
        return 1

    target = Path(args.target)
    target.parent.mkdir(parents=True, exist_ok=True)
    render(source, target, args.title, args.subtitle)
    print(f"{target}  ({target.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
