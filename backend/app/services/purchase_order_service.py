"""The purchase-order workflow, from draft to stock on the shelf.

    Select Location -> Select Supplier -> Select Items -> Create PO
        -> Send PO by email -> Receive Goods -> Update Inventory

Decisions worth knowing before changing anything here
-----------------------------------------------------
* 🔴 **Money is in MINOR UNITS as `Numeric`**, matching `Ingredient.cost_per_unit`.
  `200` means 2.00 AED. There is no `* 100` in this file and there must not be
  one: that exact "conversion" overstated cost 100x elsewhere on 2026-08-26,
  and the unit test agreed with the bug rather than catching it.

* **VAT is ADDED on top of a purchase**, unlike a sale. UAE suppliers quote net
  prices; UAE shelf prices include VAT. `tax_invoice_service` backs VAT out of
  a gross sale for exactly the same reason this adds it to a net purchase. The
  asymmetry is real.

* **Totals are always derived, never assigned.** `recalculate_totals` runs
  after every change to the lines, so the header cannot disagree with the body.

* **Over-delivery is accepted and recorded, not refused.** If the supplier
  ships 12 sacks against an order for 10, the 12 are physically in the store
  room, and refusing to book them would make the stock figure -- the number the
  whole system depends on -- wrong on purpose. The excess stays visible as
  `quantity_received > quantity_ordered`. Same reasoning as `stock_service`
  allowing a negative balance rather than blocking a till.

* **Status is computed from the lines**, never set by hand, so it cannot claim
  "received" while something is still owed.

* **All stock movement goes through `stock_service.move_stock`.** Nothing here
  touches `location_stock` or writes an `InventoryTransaction` directly.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import Ingredient
from app.models.procurement import (
    PO_RECEIVABLE_STATUSES,
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderItem,
    SupplierItem,
)
from app.services import stock_service, supplier_service
from app.services.supplier_service import ProcurementError

logger = logging.getLogger(__name__)

_CENT = Decimal("0.01")
_QTY = Decimal("0.001")


def _money(value) -> Decimal:
    """Normalise to two decimal places in minor units."""
    return Decimal(str(value)).quantize(_CENT)


def _qty(value) -> Decimal:
    return Decimal(str(value)).quantize(_QTY)


def _rate(value) -> Decimal:
    """A cost PER STOCKING UNIT, four decimal places.

    Separate from `_money` on purpose (Martin M8). `_money` is for sums
    actually charged, which are settled to two places. This is a rate derived
    by division -- fils per gram -- and rounding it to two places at the point
    of division puts the error straight into every recipe cost.
    """
    return Decimal(str(value)).quantize(Decimal("0.0001"))


# ---------------------------------------------------------------------------
# NUMBERING
# ---------------------------------------------------------------------------


async def _next_po_number(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    """Sequential per tenant, date-stamped: PO-260826-003.

    Same shape as `TRF-` transfer numbers, deliberately: an operator reading a
    stock movement log should not have to learn two numbering schemes.
    """
    today = datetime.now(timezone.utc)
    prefix = f"PO-{today:%y%m%d}-"
    count = (
        await db.execute(
            select(func.count(PurchaseOrder.id)).where(
                PurchaseOrder.tenant_id == tenant_id,
                PurchaseOrder.po_number.like(f"{prefix}%"),
            )
        )
    ).scalar_one()
    return f"{prefix}{count + 1:03d}"


async def _next_receipt_number(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    """GRN-260826-003. Goods Received Note, the term every supplier uses."""
    today = datetime.now(timezone.utc)
    prefix = f"GRN-{today:%y%m%d}-"
    count = (
        await db.execute(
            select(func.count(GoodsReceipt.id)).where(
                GoodsReceipt.tenant_id == tenant_id,
                GoodsReceipt.receipt_number.like(f"{prefix}%"),
            )
        )
    ).scalar_one()
    return f"{prefix}{count + 1:03d}"


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------


def _po_options():
    """Eager loads every read of a PO needs.

    Every relationship the response model touches is loaded up front. The
    alternative is a `MissingGreenlet` the first time one is read after the
    session has moved on, which this codebase has been bitten by before.
    """
    return (
        selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.ingredient),
        selectinload(PurchaseOrder.supplier),
        selectinload(PurchaseOrder.location),
        selectinload(PurchaseOrder.receipts).selectinload(GoodsReceipt.lines),
    )


async def get_purchase_order(
    db: AsyncSession, tenant_id: uuid.UUID, po_id: uuid.UUID
) -> PurchaseOrder:
    """Load a PO with everything attached, refreshed from the database.

    🔴 `populate_existing` is not optional here. Without it, SQLAlchemy returns
    the instance already in the identity map and LEAVES ITS ALREADY-LOADED
    COLLECTIONS ALONE -- so a re-read taken immediately after writing a goods
    receipt came back with the empty `receipts` list loaded at the start of the
    request, and the newly written receipt was invisible. Caught end to end
    against the real API on 2026-08-26; no unit test would have seen it, because
    a fresh session per test never has a stale collection to return.
    """
    po = (
        await db.execute(
            select(PurchaseOrder)
            .where(PurchaseOrder.id == po_id, PurchaseOrder.tenant_id == tenant_id)
            .options(*_po_options())
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if po is None:
        raise ProcurementError("No such purchase order for this restaurant.")
    return po


async def list_purchase_orders(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    status: str | None = None,
    supplier_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    limit: int = 200,
) -> list[PurchaseOrder]:
    stmt = (
        select(PurchaseOrder)
        .where(PurchaseOrder.tenant_id == tenant_id)
        .options(*_po_options())
        .order_by(PurchaseOrder.created_at.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(PurchaseOrder.status == status)
    if supplier_id:
        stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
    if location_id:
        stmt = stmt.where(PurchaseOrder.location_id == location_id)
    return list((await db.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# TOTALS AND STATUS -- both derived, never assigned
# ---------------------------------------------------------------------------


async def recalculate_totals(db: AsyncSession, po: PurchaseOrder) -> None:
    """Rebuild every line total and the header totals from the lines."""
    subtotal = Decimal("0")
    for item in po.items:
        item.line_total_minor = _money(
            Decimal(str(item.quantity_ordered)) * Decimal(str(item.unit_price_minor))
        )
        subtotal += Decimal(str(item.line_total_minor))

    po.subtotal_minor = _money(subtotal)
    # Added on top: a supplier quotes net. See the module docstring.
    po.tax_minor = _money(subtotal * Decimal(po.tax_bps) / Decimal(10000))
    po.total_minor = _money(Decimal(str(po.subtotal_minor)) + Decimal(str(po.tax_minor)))
    await db.flush()


def _derive_status(po: PurchaseOrder) -> str:
    """What the lines say the status is.

    Only ever called for a PO that has been sent; draft and cancelled are
    states a human puts it in, not states the quantities imply.
    """
    if not po.items:
        return po.status
    total_received = sum(Decimal(str(i.quantity_received)) for i in po.items)
    if total_received <= 0:
        return "sent"
    fully = all(
        Decimal(str(i.quantity_received)) >= Decimal(str(i.quantity_ordered))
        for i in po.items
    )
    return "received" if fully else "partially_received"


# ---------------------------------------------------------------------------
# CREATE AND EDIT
# ---------------------------------------------------------------------------


async def _resolve_line(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    supplier_id: uuid.UUID,
    line: dict,
) -> tuple[Ingredient, Decimal, str | None]:
    """Validate one requested line and work out its price.

    Price precedence: what the caller typed, else what we last paid this
    supplier, else the ingredient's own cost. Falling all the way through to
    zero is allowed -- a PO for an item never bought before genuinely has no
    known price, and refusing to draft it would be unhelpful.
    """
    ingredient = (
        await db.execute(
            select(Ingredient).where(
                Ingredient.id == line["ingredient_id"],
                Ingredient.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if ingredient is None:
        raise ProcurementError("No such ingredient for this restaurant.")
    if ingredient.is_produced:
        raise ProcurementError(
            f"{ingredient.name} is produced in-house from a recipe and cannot be "
            "purchased. Order the raw ingredients it is made from."
        )

    quantity = _qty(line["quantity_ordered"])
    if quantity <= 0:
        raise ProcurementError("A purchase-order quantity must be greater than zero.")

    catalogue = (
        await db.execute(
            select(SupplierItem).where(
                SupplierItem.supplier_id == supplier_id,
                SupplierItem.ingredient_id == ingredient.id,
            )
        )
    ).scalar_one_or_none()

    price = line.get("unit_price_minor")
    if price is None:
        if catalogue is not None and Decimal(str(catalogue.last_price_minor)) > 0:
            price = catalogue.last_price_minor
        else:
            # Martin M8: for an ingredient with a purchase unit the whole line
            # is expressed in purchase units, so the fallback price must be the
            # price of a can, not the price of a gram. Falling through to
            # `cost_per_unit` here would under-price the order by the
            # conversion factor -- 400x for a tomato can.
            price = (
                ingredient.purchase_cost_minor
                if ingredient.purchase_unit
                else ingredient.cost_per_unit
            )
    price = _money(price)
    if price < 0:
        raise ProcurementError("A unit price cannot be negative.")

    sku = line.get("supplier_sku") or (catalogue.supplier_sku if catalogue else None)
    return ingredient, price, sku


def purchase_unit_of(ingredient: Ingredient) -> tuple[str, Decimal]:
    """The unit a purchase order line is written in, and its conversion.

    ("can", 400) for an ingredient with a purchase unit, ("g", 1) for one
    bought in the unit it is stocked in. Every line-writing path goes through
    this so the unit and its conversion can never be set from different places
    and disagree.
    """
    if ingredient.purchase_unit:
        return ingredient.purchase_unit, Decimal(
            str(ingredient.units_per_purchase_unit or 1)
        )
    return ingredient.unit, Decimal("1")


async def create_purchase_order(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    supplier_id: uuid.UUID,
    location_id: uuid.UUID,
    lines: list[dict],
    tax_bps: int = 0,
    expected_date: date | None = None,
    notes: str | None = None,
    delivery_instructions: str | None = None,
    created_by: uuid.UUID | None = None,
) -> PurchaseOrder:
    """Draft a PO. Nothing is ordered and no stock moves until it is sent."""
    if not lines:
        raise ProcurementError("A purchase order needs at least one item.")

    supplier = await supplier_service.get_supplier(db, tenant_id, supplier_id)
    if not supplier.is_active:
        raise ProcurementError(f"{supplier.name} is not an active supplier.")
    # Raises if the location is not this tenant's. Goods land here on receipt,
    # so getting it wrong puts stock in the wrong building.
    location = await stock_service.resolve_location(db, tenant_id, location_id)

    po = PurchaseOrder(
        tenant_id=tenant_id,
        po_number=await _next_po_number(db, tenant_id),
        supplier_id=supplier.id,
        location_id=location.id,
        status="draft",
        expected_date=expected_date,
        tax_bps=tax_bps,
        notes=notes,
        delivery_instructions=delivery_instructions,
        created_by=created_by,
    )
    db.add(po)
    # Flush before the children reference po.id -- the async flush-before-FK
    # rule this codebase has been bitten by before.
    await db.flush()

    seen: set[uuid.UUID] = set()
    for line in lines:
        ingredient, price, sku = await _resolve_line(db, tenant_id, supplier.id, line)
        if ingredient.id in seen:
            raise ProcurementError(
                f"{ingredient.name} appears twice on the same order; combine the "
                "quantities into one line."
            )
        seen.add(ingredient.id)
        order_unit, conversion = purchase_unit_of(ingredient)
        db.add(
            PurchaseOrderItem(
                tenant_id=tenant_id,
                purchase_order_id=po.id,
                ingredient_id=ingredient.id,
                quantity_ordered=_qty(line["quantity_ordered"]),
                unit=order_unit,
                units_per_purchase_unit=conversion,
                unit_price_minor=price,
                supplier_sku=sku,
                notes=line.get("notes"),
            )
        )

    await db.flush()
    po = await get_purchase_order(db, tenant_id, po.id)
    await recalculate_totals(db, po)
    return await get_purchase_order(db, tenant_id, po.id)


async def update_purchase_order(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    po_id: uuid.UUID,
    data: dict,
    lines: list[dict] | None = None,
) -> PurchaseOrder:
    """Edit a draft PO. Once sent, only the receiving path may change it.

    Refusing to edit a sent PO is deliberate: the supplier already has a copy
    of a specific document, and silently changing our copy of it means the two
    no longer describe the same agreement.
    """
    po = await get_purchase_order(db, tenant_id, po_id)
    if po.status != "draft":
        raise ProcurementError(
            f"Only a draft purchase order can be edited; this one is {po.status}. "
            "Cancel it and raise a new one if the order really changed."
        )

    for field, value in data.items():
        setattr(po, field, value)

    if lines is not None:
        if not lines:
            raise ProcurementError("A purchase order needs at least one item.")
        for item in list(po.items):
            await db.delete(item)
        await db.flush()

        seen: set[uuid.UUID] = set()
        for line in lines:
            ingredient, price, sku = await _resolve_line(
                db, tenant_id, po.supplier_id, line
            )
            if ingredient.id in seen:
                raise ProcurementError(
                    f"{ingredient.name} appears twice on the same order; combine "
                    "the quantities into one line."
                )
            seen.add(ingredient.id)
            order_unit, conversion = purchase_unit_of(ingredient)
            db.add(
                PurchaseOrderItem(
                    tenant_id=tenant_id,
                    purchase_order_id=po.id,
                    ingredient_id=ingredient.id,
                    quantity_ordered=_qty(line["quantity_ordered"]),
                    unit=order_unit,
                    units_per_purchase_unit=conversion,
                    unit_price_minor=price,
                    supplier_sku=sku,
                    notes=line.get("notes"),
                )
            )
        await db.flush()

    po = await get_purchase_order(db, tenant_id, po_id)
    await recalculate_totals(db, po)
    return await get_purchase_order(db, tenant_id, po_id)


async def cancel_purchase_order(
    db: AsyncSession, *, tenant_id: uuid.UUID, po_id: uuid.UUID
) -> PurchaseOrder:
    """Cancel a PO. Anything already received stays received.

    Stock that physically arrived is not un-arrived by cancelling the paperwork,
    so no reversing movement is written. A PO that is fully received cannot be
    cancelled at all.
    """
    po = await get_purchase_order(db, tenant_id, po_id)
    if po.status == "received":
        raise ProcurementError(
            "A fully received purchase order cannot be cancelled. Return the "
            "goods with a stock adjustment so the movement stays on record."
        )
    if po.status == "cancelled":
        return po

    po.status = "cancelled"
    po.cancelled_at = datetime.now(timezone.utc)
    await db.flush()
    return await get_purchase_order(db, tenant_id, po_id)


async def mark_sent(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    po_id: uuid.UUID,
    sent_to_email: str | None = None,
    email_delivered: bool = False,
    email_error: str | None = None,
) -> PurchaseOrder:
    """Move a draft PO to `sent`.

    Separate from the emailing itself so a PO handed over by phone, WhatsApp or
    a printout is still a first-class sent order. An email that fails does NOT
    roll the status back: the buyer's intent is recorded, the failure is
    recorded next to it, and a resend is one click. Losing the whole order
    because a mail server hiccuped would be the worse outcome -- the same
    reasoning `email_service` already applies to customer email.
    """
    po = await get_purchase_order(db, tenant_id, po_id)
    if po.status == "cancelled":
        raise ProcurementError("A cancelled purchase order cannot be sent.")
    if not po.items:
        raise ProcurementError("A purchase order with no items cannot be sent.")

    if po.status == "draft":
        po.status = "sent"
    po.sent_at = po.sent_at or datetime.now(timezone.utc)
    if sent_to_email:
        po.sent_to_email = sent_to_email
    if email_delivered:
        po.email_send_count = (po.email_send_count or 0) + 1
        po.last_email_error = None
    elif email_error:
        po.last_email_error = email_error[:1000]

    await db.flush()
    return await get_purchase_order(db, tenant_id, po_id)


# ---------------------------------------------------------------------------
# RECEIVING
# ---------------------------------------------------------------------------


async def receive_goods(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    po_id: uuid.UUID,
    lines: list[dict],
    source: str = "manual",
    document_reference: str | None = None,
    notes: str | None = None,
    performed_by: uuid.UUID | None = None,
) -> tuple[PurchaseOrder, GoodsReceipt]:
    """Book a delivery in: add the stock, record what arrived and at what price.

    `lines` is [{"purchase_order_item_id": UUID, "quantity_received": Decimal,
    "unit_price_minor": Decimal | None}, ...]. Omitted prices fall back to the
    price on the order line.

    Every quantity lands at the PO's own location through
    `stock_service.move_stock`, and the ingredient's cost and the supplier's
    price history are updated from what was actually charged.
    """
    if source not in ("manual", "ocr"):
        raise ProcurementError("A goods receipt is either 'manual' or 'ocr'.")
    if not lines:
        raise ProcurementError("A goods receipt needs at least one line.")

    po = await get_purchase_order(db, tenant_id, po_id)
    if po.status not in PO_RECEIVABLE_STATUSES:
        raise ProcurementError(
            f"Goods can only be received against a sent order; this one is "
            f"{po.status}."
        )

    by_id = {item.id: item for item in po.items}

    receipt = GoodsReceipt(
        tenant_id=tenant_id,
        receipt_number=await _next_receipt_number(db, tenant_id),
        purchase_order_id=po.id,
        source=source,
        document_reference=document_reference,
        received_at=datetime.now(timezone.utc),
        received_by=performed_by,
        notes=notes,
    )
    db.add(receipt)
    await db.flush()

    for line in lines:
        item = by_id.get(line["purchase_order_item_id"])
        if item is None:
            raise ProcurementError(
                "That line does not belong to this purchase order."
            )

        quantity = _qty(line["quantity_received"])
        if quantity <= 0:
            raise ProcurementError(
                "A received quantity must be greater than zero. Leave a line off "
                "the receipt entirely if none of it arrived."
            )

        price = line.get("unit_price_minor")
        price = _money(price if price is not None else item.unit_price_minor)
        if price < 0:
            raise ProcurementError("A received unit price cannot be negative.")

        # Martin M8. The line counts purchase units ("3 cans"); stock counts
        # stocking units ("1200 g"). This is the one place the two meet, and
        # both numbers below have to cross the conversion together: the
        # quantity multiplied by it, the unit cost divided by it. Converting
        # only one would book the right weight at 400x the right price.
        conversion = Decimal(str(item.units_per_purchase_unit or 1))
        stock_quantity = _qty(quantity * conversion)
        stock_unit_cost = _rate(price / conversion) if conversion > 0 else _rate(price)

        db.add(
            GoodsReceiptLine(
                tenant_id=tenant_id,
                receipt_id=receipt.id,
                purchase_order_item_id=item.id,
                ingredient_id=item.ingredient_id,
                quantity_received=quantity,
                unit=item.unit,
                units_per_purchase_unit=conversion,
                unit_price_minor=price,
            )
        )

        item.quantity_received = _qty(
            Decimal(str(item.quantity_received)) + quantity
        )

        await stock_service.move_stock(
            db,
            tenant_id=tenant_id,
            ingredient_id=item.ingredient_id,
            quantity_delta=stock_quantity,
            transaction_type="purchase",
            location_id=po.location_id,
            unit_cost=stock_unit_cost,
            performed_by=performed_by,
            reference_number=po.po_number,
            notes=f"Goods receipt {receipt.receipt_number}",
        )

        await _apply_purchase_price(
            db, tenant_id, po.supplier_id, item.ingredient_id, price, conversion
        )

    await db.flush()

    po = await get_purchase_order(db, tenant_id, po_id)
    po.status = _derive_status(po)
    if po.status == "received" and po.fully_received_at is None:
        po.fully_received_at = datetime.now(timezone.utc)
    await db.flush()

    return await get_purchase_order(db, tenant_id, po_id), receipt


async def _apply_purchase_price(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    supplier_id: uuid.UUID,
    ingredient_id: uuid.UUID,
    price_minor: Decimal,
    conversion: Decimal = Decimal("1"),
) -> None:
    """Update what we know an ingredient costs, from what we just paid.

    `price_minor` is per PURCHASE unit and `conversion` is the stocking units
    in one of them (Martin M8), so a can at 8.50 with 400 g in it writes 850 to
    the purchase price and 2.125 to the cost of a gram. Both stay in step
    because they are written together, here, from the same pair of numbers.

    Three writes, and the last one is guarded:

    * The supplier's catalogue price always updates. That is a fact about this
      supplier and nothing else reads it as an authority. It is stored per
      purchase unit, matching the PO line it came from.
    * The ingredient's own `purchase_cost_minor` follows it, so the admin form
      shows the price actually last paid for a can.
    * The ingredient master's `cost_per_unit` updates ONLY for a purchased
      ingredient. For an `is_produced` one it is a rollup owned by
      `recipe_service.sync_produced_ingredient_cost`, and overwriting it here
      would silently corrupt every recipe cost that depends on it.

    Existing recipes are not re-costed by this. `RecipeItem` snapshots the unit
    cost it was built with on purpose, so a price change never rewrites the
    history of what a dish used to cost -- `recipe_service` has an explicit
    recalculation path for when someone wants that.
    """
    if price_minor <= 0:
        return

    await supplier_service.record_purchase_price(
        db, tenant_id, supplier_id, ingredient_id, price_minor
    )

    ingredient = (
        await db.execute(
            select(Ingredient).where(
                Ingredient.id == ingredient_id, Ingredient.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if ingredient is not None and not ingredient.is_produced:
        divisor = conversion if conversion and conversion > 0 else Decimal("1")
        ingredient.purchase_cost_minor = _money(price_minor)
        ingredient.cost_per_unit = _rate(price_minor / divisor)
        await db.flush()


# ---------------------------------------------------------------------------
# REPORTING
# ---------------------------------------------------------------------------


async def receiving_history(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    location_id: uuid.UUID | None = None,
    limit: int = 100,
) -> list[dict]:
    """Every goods receipt, newest first. Martin's Section 9 receiving history."""
    stmt = (
        select(GoodsReceipt, PurchaseOrder)
        .join(PurchaseOrder, PurchaseOrder.id == GoodsReceipt.purchase_order_id)
        .where(GoodsReceipt.tenant_id == tenant_id)
        .options(selectinload(GoodsReceipt.lines))
        .order_by(GoodsReceipt.received_at.desc())
        .limit(limit)
    )
    if location_id is not None:
        stmt = stmt.where(PurchaseOrder.location_id == location_id)

    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": receipt.id,
            "receipt_number": receipt.receipt_number,
            "purchase_order_id": po.id,
            "po_number": po.po_number,
            "source": receipt.source,
            "document_reference": receipt.document_reference,
            "received_at": receipt.received_at,
            "line_count": len(receipt.lines),
            "total_minor": _money(
                sum(
                    Decimal(str(line.quantity_received))
                    * Decimal(str(line.unit_price_minor))
                    for line in receipt.lines
                )
                if receipt.lines
                else Decimal("0")
            ),
            "notes": receipt.notes,
        }
        for receipt, po in rows
    ]


async def outstanding_quantities(
    db: AsyncSession, tenant_id: uuid.UUID, location_id: uuid.UUID | None = None
) -> dict[uuid.UUID, Decimal]:
    """How much of each ingredient is already on order and not yet delivered.

    The ordering suggestion must subtract this, or it will re-order everything
    that is already in a van on its way to the door.

    🔴 **Returned in STOCKING units**, which is what the caller compares
    against stock on hand. The line itself counts purchase units (Martin M8:
    "2 cans"), so the outstanding quantity is multiplied by the line's own
    snapshotted conversion before it is summed. Leaving that out would say two
    cans are coming when what is coming is 800 g, and the suggestion would
    order 798 g more of them.
    """
    stmt = (
        select(
            PurchaseOrderItem.ingredient_id,
            func.sum(
                (
                    PurchaseOrderItem.quantity_ordered
                    - PurchaseOrderItem.quantity_received
                )
                * PurchaseOrderItem.units_per_purchase_unit
            ),
        )
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id)
        .where(
            PurchaseOrder.tenant_id == tenant_id,
            PurchaseOrder.status.in_(PO_RECEIVABLE_STATUSES),
        )
        .group_by(PurchaseOrderItem.ingredient_id)
    )
    if location_id is not None:
        stmt = stmt.where(PurchaseOrder.location_id == location_id)

    return {
        ingredient_id: _qty(outstanding)
        for ingredient_id, outstanding in (await db.execute(stmt)).all()
        if outstanding is not None and Decimal(str(outstanding)) > 0
    }
