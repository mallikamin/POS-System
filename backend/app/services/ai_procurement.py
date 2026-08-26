"""The two AI-assisted procurement features. Both are strictly assistive.

    extract_delivery_note   a photo of a supplier's delivery note becomes a
                            PROPOSED goods receipt, which a human then checks,
                            corrects and confirms through the ordinary
                            receiving endpoint. Nothing here writes stock.

    advise_on_plan          reads the already-computed ordering plan and adds
                            judgement: risks, what to do first, a sentence
                            worth reading. It cannot change a quantity.

Two rules hold across both, and they are the reason this is safe to ship:

🔴 **The model never produces a number that is trusted.** OCR output is a
proposal on a review screen; the ordering quantities are computed in
`purchase_suggestion_service` by arithmetic the model never touches. The worst
a bad extraction can do is make somebody retype a line.

🔴 **The B1 rule (api-cost-playbook).** Everything static -- the task, the
rules, the output shape -- lives in the cached system block. The user message
carries only the small per-request delta: the image, and a compact numbered
allowlist. The model answers with INDEXES into that list, never free text
names, so there is no fuzzy name matching to get wrong and no reason to send
the ingredient master.

Money
-----
The model is asked for prices exactly as they appear on the document, in major
units, because that is what it can read. The single conversion to minor units
happens here, in Python, once. The model is never asked to do arithmetic on
money.
"""

from __future__ import annotations

import base64
import uuid
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.procurement import PurchaseOrder
from app.services import ai_client
from app.services.ai_client import AIUnavailable

# Anthropic accepts these image types, plus PDF as a document block.
SUPPORTED_IMAGE_TYPES = ("image/jpeg", "image/png", "image/gif", "image/webp")
SUPPORTED_DOCUMENT_TYPES = ("application/pdf",)


# ---------------------------------------------------------------------------
# OCR GOODS RECEIVING
# ---------------------------------------------------------------------------


class ExtractedLine(BaseModel):
    """One line the model believes it read off the delivery note."""

    line_index: int = Field(
        description=(
            "The index from the ORDER LINES list of the item this row matches. "
            "Use -1 when the row does not correspond to any listed item."
        )
    )
    quantity: str = Field(
        description="Quantity delivered, as a plain decimal number, e.g. '12.5'."
    )
    unit_price: str | None = Field(
        default=None,
        description=(
            "Unit price exactly as printed on the document, as a plain decimal "
            "in the document's own currency, e.g. '4.80'. Null if not shown."
        ),
    )
    document_text: str = Field(
        description="The item description as printed on the document."
    )
    confidence: str = Field(
        description="One of: high, medium, low."
    )


class ExtractedDeliveryNote(BaseModel):
    document_reference: str | None = Field(
        default=None,
        description="The supplier's delivery note or invoice number, if printed.",
    )
    supplier_name: str | None = Field(
        default=None, description="Supplier name as printed, if visible."
    )
    lines: list[ExtractedLine] = Field(default_factory=list)
    notes: str | None = Field(
        default=None,
        description=(
            "Anything the person checking this should know: unreadable areas, "
            "rows you could not match, ambiguity. One or two sentences."
        ),
    )


# 🔴 STATIC. Byte-identical on every call, which is what makes it a cache read
# rather than full-price input. Nothing tenant-specific, nothing dated, nothing
# from the request. Changing a single character here invalidates the cache for
# everybody, so change it deliberately.
_OCR_SYSTEM = """You read supplier delivery notes and goods-received notes for a \
restaurant's stock system, and turn them into structured lines.

You will be given an image or PDF of one document, and a numbered list of the \
lines on the purchase order it is being delivered against.

Your job:
1. Read every product row on the document.
2. Match each row to ONE entry in the ORDER LINES list, and return that entry's \
index. Match on meaning, not on exact wording: a supplier writes "PLAIN FLOUR \
T55 25KG SACK" for an order line that says "Flour". If a row genuinely matches \
nothing in the list, return -1 for it and describe it in document_text.
3. Report the quantity DELIVERED, not the quantity ordered, when the document \
shows both. Convert nothing: if the document says 2 sacks and the order line is \
in kg, report what the document says and note the discrepancy.
4. Report the unit price exactly as printed, in the document's own currency, as \
a plain decimal. Do not calculate, convert, or infer a price that is not shown; \
return null instead.
5. Set confidence to "low" for anything handwritten, smudged, ambiguous, or \
where you are unsure of the match.

Rules that matter more than completeness:
- Never invent a row, a quantity or a price. A missing value is null.
- Never guess at a digit you cannot read. Mark the line "low" and say so in notes.
- Prefer reporting a row with -1 and a clear document_text over forcing it onto \
a line it probably is not.

Everything you return is checked by a person before it changes any stock, so an \
honest "I could not read this" is more useful than a confident guess."""


def _document_block(data: bytes, media_type: str) -> dict:
    """The image or PDF content block, base64 encoded with no newlines."""
    encoded = base64.standard_b64encode(data).decode("utf-8")
    if media_type in SUPPORTED_DOCUMENT_TYPES:
        return {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": encoded,
            },
        }
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": encoded},
    }


def _order_line_allowlist(po: PurchaseOrder) -> str:
    """The compact numbered list the model answers with indexes into.

    🔴 This is the B1 fix in practice. The alternative -- sending the ingredient
    master, or the whole purchase order as JSON -- would put hundreds of tokens
    of context into the uncached user message on every single call, and get back
    free-text names that then need fuzzy matching. One line per order line, and
    an integer back.
    """
    rows = []
    for position, item in enumerate(po.items):
        outstanding = Decimal(str(item.quantity_ordered)) - Decimal(
            str(item.quantity_received)
        )
        rows.append(
            f"{position}. {item.ingredient.name} | unit: {item.unit} | "
            f"ordered: {Decimal(str(item.quantity_ordered)):g} | "
            f"still owed: {max(Decimal('0'), outstanding):g}"
        )
    return "\n".join(rows)


def _to_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


async def extract_delivery_note(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    po: PurchaseOrder,
    data: bytes,
    media_type: str,
    requested_by: uuid.UUID | None = None,
) -> dict:
    """Read a delivery note into PROPOSED receipt lines. Writes nothing.

    The result is shaped exactly like the manual receiving form so the review
    screen is the same screen, pre-filled. A human confirms it through the
    ordinary, already-verified receive endpoint.
    """
    if media_type not in SUPPORTED_IMAGE_TYPES + SUPPORTED_DOCUMENT_TYPES:
        raise AIUnavailable(
            "That file type cannot be read. Upload a photo (JPEG, PNG, WEBP) or "
            "a PDF of the delivery note."
        )
    if len(data) > settings.AI_MAX_UPLOAD_BYTES:
        raise AIUnavailable(
            f"That file is too large. The limit is "
            f"{settings.AI_MAX_UPLOAD_BYTES // (1024 * 1024)}MB; photograph the "
            "note again at a lower resolution."
        )
    if not po.items:
        raise AIUnavailable("This purchase order has no lines to match against.")

    result: ExtractedDeliveryNote = await ai_client.call_model(  # type: ignore[assignment]
        db,
        tenant_id=tenant_id,
        kind="ocr_receiving",
        system=_OCR_SYSTEM,
        content=[
            _document_block(data, media_type),
            {
                "type": "text",
                "text": f"ORDER LINES\n{_order_line_allowlist(po)}",
            },
        ],
        output_model=ExtractedDeliveryNote,
        requested_by=requested_by,
    )

    by_position = list(po.items)
    proposed: list[dict] = []
    unmatched: list[dict] = []

    for line in result.lines:
        quantity = _to_decimal(line.quantity)
        price_major = _to_decimal(line.unit_price)
        # ONE conversion, here. The model reads "4.80" off the paper; minor
        # units are this system's internal convention and never the model's
        # problem.
        price_minor = (
            (price_major * 100).quantize(Decimal("0.01"))
            if price_major is not None and price_major >= 0
            else None
        )

        if (
            line.line_index < 0
            or line.line_index >= len(by_position)
            or quantity is None
            or quantity <= 0
        ):
            unmatched.append(
                {
                    "document_text": line.document_text,
                    "quantity": str(quantity) if quantity is not None else None,
                    "confidence": line.confidence,
                }
            )
            continue

        item = by_position[line.line_index]
        proposed.append(
            {
                "purchase_order_item_id": item.id,
                "ingredient_name": item.ingredient.name,
                "unit": item.unit,
                "quantity_received": quantity,
                "unit_price_minor": price_minor,
                "ordered_quantity": Decimal(str(item.quantity_ordered)),
                "outstanding_quantity": max(
                    Decimal("0"),
                    Decimal(str(item.quantity_ordered))
                    - Decimal(str(item.quantity_received)),
                ),
                "document_text": line.document_text,
                "confidence": line.confidence,
            }
        )

    # A line proposed twice would double the delivery if the reviewer did not
    # notice. Surfaced rather than silently merged: which of the two is right is
    # a question for the person holding the paper.
    seen: set[uuid.UUID] = set()
    duplicates: set[uuid.UUID] = set()
    for row in proposed:
        item_id = row["purchase_order_item_id"]
        if item_id in seen:
            duplicates.add(item_id)
        seen.add(item_id)

    return {
        "document_reference": result.document_reference,
        "supplier_name": result.supplier_name,
        "lines": proposed,
        "unmatched": unmatched,
        "duplicate_line_ids": sorted(duplicates, key=str),
        "notes": result.notes,
    }


# ---------------------------------------------------------------------------
# ORDERING ADVICE
# ---------------------------------------------------------------------------


class PlanAdvice(BaseModel):
    summary: str = Field(
        description="Two sentences at most. What this order run is, and the "
        "single thing worth knowing about it."
    )
    risks: list[str] = Field(
        default_factory=list,
        description=(
            "Concrete risks in THIS plan, at most four. Lead times that will not "
            "make the production date, items nobody supplies, a spend that looks "
            "out of line, a quantity that looks like a data error. Say nothing "
            "rather than pad the list."
        ),
    )
    order_first: list[str] = Field(
        default_factory=list,
        description="Supplier names to send first, longest lead time first.",
    )


# 🔴 STATIC. See the note on _OCR_SYSTEM.
_ADVICE_SYSTEM = """You advise a restaurant's buyer on a purchase plan that has \
already been calculated for them.

The quantities you are shown were computed from the production target, the \
recipes, the stock on hand and what is already on order. They are arithmetic and \
they are correct. Do not recompute them, do not propose different numbers, and \
do not suggest ordering something that is not in the plan.

Your job is the judgement the arithmetic cannot do:
- Which supplier should be sent first, given lead times against the production date.
- What in this specific plan is likely to go wrong.
- Anything that looks like a data error rather than a real requirement (a \
quantity orders of magnitude away from the others, an item with no supplier).

Be brief and concrete. A buyer reads this in ten seconds between two other jobs. \
Name suppliers and items; do not give general advice about procurement. If the \
plan is unremarkable, say so in one sentence and return no risks -- an empty \
list is a valid and useful answer."""


def _plan_digest(plan: dict, days_until_production: int | None) -> str:
    """The compact per-request delta. Rows only, no schema, no restating rules.

    Deliberately not `json.dumps(plan)`. The plan carries UUIDs, per-line
    breakdowns and pricing the model has no use for, and sending them would be
    exactly the mistake this playbook calls B1.
    """
    rows = [f"Location: {plan['location_name']}"]
    if days_until_production is not None:
        rows.append(f"Production starts in: {days_until_production} days")
    rows.append(
        f"Estimated spend: {Decimal(str(plan['estimated_total_minor'])) / 100:.2f}"
    )

    rows.append("\nPRODUCTION TARGET")
    for target in plan["targets"]:
        rows.append(f"- {target['recipe_name']} x{Decimal(str(target['batches'])):g}")

    rows.append("\nTO ORDER (item | qty | supplier | lead days | cost)")
    for basket in plan["baskets"]:
        for line in basket["lines"]:
            rows.append(
                f"- {line['ingredient_name']} | "
                f"{Decimal(str(line['suggested_quantity'])):g} {line['unit']} | "
                f"{line['supplier_name']} | "
                f"{line['lead_time_days'] if line['lead_time_days'] is not None else '?'} | "
                f"{Decimal(str(line['estimated_cost_minor'])) / 100:.2f}"
            )

    if plan["unsourced"]:
        rows.append("\nNEEDED BUT NO SUPPLIER ON FILE")
        for line in plan["unsourced"]:
            rows.append(
                f"- {line['ingredient_name']} | "
                f"{Decimal(str(line['suggested_quantity'])):g} {line['unit']}"
            )

    return "\n".join(rows)


async def advise_on_plan(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    plan: dict,
    days_until_production: int | None = None,
    requested_by: uuid.UUID | None = None,
) -> dict:
    """One small call that reads the finished plan and adds judgement."""
    advice: PlanAdvice = await ai_client.call_model(  # type: ignore[assignment]
        db,
        tenant_id=tenant_id,
        kind="purchase_advice",
        system=_ADVICE_SYSTEM,
        content=[{"type": "text", "text": _plan_digest(plan, days_until_production)}],
        output_model=PlanAdvice,
        requested_by=requested_by,
        # A buyer's briefing note, not an essay.
        max_tokens=1200,
    )
    return advice.model_dump()
