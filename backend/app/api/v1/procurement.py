"""Suppliers, purchase orders, goods receiving.

Martin's Section 5 end to end. Every endpoint is tenant-scoped through
`current_user.tenant_id`: a caller can only ever see and order for their own
restaurant.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.models.procurement import GoodsReceipt, PurchaseOrder
from app.models.user import User
from app.schemas.procurement import (
    AIUsageSummary,
    GoodsReceiptLineResponse,
    GoodsReceiptRequest,
    GoodsReceiptResponse,
    GoodsReceiptResult,
    PurchaseOrderCreate,
    PurchaseOrderItemResponse,
    PurchaseOrderResponse,
    PurchaseOrderSendRequest,
    PurchaseOrderSendResponse,
    PurchaseOrderUpdate,
    ReceivingHistoryRow,
    ScanResult,
    SuggestionRequest,
    SuggestionResponse,
    SupplierCreate,
    SupplierItemRow,
    SupplierItemUpsert,
    SupplierPurchaseRow,
    SupplierResponse,
    SupplierUpdate,
)
from app.services import (
    ai_client,
    ai_procurement,
    email_service,
    purchase_order_document,
    purchase_order_service,
    purchase_suggestion_service,
    supplier_service,
)
from app.services.ai_client import AIUnavailable
from app.services.stock_service import StockError
from app.services.supplier_service import ProcurementError

router = APIRouter(prefix="/procurement", tags=["procurement"])

# Both are "the caller asked for something that cannot be done", never a 500.
# `StockError` reaches here because receiving goods moves stock.
_CALLER_ERRORS = (ProcurementError, StockError)


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ---------------------------------------------------------------------------
# RESPONSE BUILDERS
# ---------------------------------------------------------------------------


def _receipt_out(receipt: GoodsReceipt) -> GoodsReceiptResponse:
    return GoodsReceiptResponse(
        id=receipt.id,
        receipt_number=receipt.receipt_number,
        purchase_order_id=receipt.purchase_order_id,
        source=receipt.source,
        document_reference=receipt.document_reference,
        received_at=receipt.received_at,
        notes=receipt.notes,
        lines=[
            GoodsReceiptLineResponse(
                id=line.id,
                purchase_order_item_id=line.purchase_order_item_id,
                ingredient_id=line.ingredient_id,
                quantity_received=line.quantity_received,
                unit=line.unit,
                unit_price_minor=line.unit_price_minor,
            )
            for line in receipt.lines
        ],
    )


def _po_out(po: PurchaseOrder) -> PurchaseOrderResponse:
    """Flatten a PO for the wire, resolving the names the UI needs.

    `quantity_outstanding` is computed here rather than stored: it is always
    ordered minus received, and a stored copy would be one more thing that can
    disagree with the two numbers it comes from. Clamped at zero so an
    over-delivery reads as "nothing outstanding", not a negative debt.
    """
    return PurchaseOrderResponse(
        id=po.id,
        po_number=po.po_number,
        supplier_id=po.supplier_id,
        supplier_name=po.supplier.name,
        supplier_email=po.supplier.email,
        location_id=po.location_id,
        location_name=po.location.name,
        status=po.status,
        expected_date=po.expected_date,
        tax_bps=po.tax_bps,
        subtotal_minor=po.subtotal_minor,
        tax_minor=po.tax_minor,
        total_minor=po.total_minor,
        notes=po.notes,
        delivery_instructions=po.delivery_instructions,
        sent_at=po.sent_at,
        sent_to_email=po.sent_to_email,
        email_send_count=po.email_send_count,
        last_email_error=po.last_email_error,
        fully_received_at=po.fully_received_at,
        cancelled_at=po.cancelled_at,
        created_at=po.created_at,
        items=[
            PurchaseOrderItemResponse(
                id=item.id,
                ingredient_id=item.ingredient_id,
                ingredient_name=item.ingredient.name,
                quantity_ordered=item.quantity_ordered,
                quantity_received=item.quantity_received,
                quantity_outstanding=max(
                    Decimal("0"),
                    Decimal(str(item.quantity_ordered))
                    - Decimal(str(item.quantity_received)),
                ),
                unit=item.unit,
                unit_price_minor=item.unit_price_minor,
                line_total_minor=item.line_total_minor,
                supplier_sku=item.supplier_sku,
                notes=item.notes,
            )
            for item in po.items
        ],
        receipts=[_receipt_out(r) for r in po.receipts],
    )


# ---------------------------------------------------------------------------
# SUPPLIERS
# ---------------------------------------------------------------------------


@router.get("/suppliers", response_model=list[SupplierResponse])
async def list_suppliers(
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SupplierResponse]:
    """Every supplier, with how many orders and how much spend against each."""
    suppliers = await supplier_service.list_suppliers(
        db, current_user.tenant_id, include_inactive
    )
    # One grouped query for every supplier rather than a count per row.
    totals = await supplier_service.supplier_spend_totals(db, current_user.tenant_id)
    out = []
    for supplier in suppliers:
        row = SupplierResponse.model_validate(supplier)
        stats = totals.get(supplier.id)
        if stats:
            row.order_count = stats["order_count"]
            row.total_spend_minor = stats["total_spend_minor"]
        out.append(row)
    return out


@router.post(
    "/suppliers",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def create_supplier(
    data: SupplierCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SupplierResponse:
    try:
        supplier = await supplier_service.create_supplier(
            db, current_user.tenant_id, data.model_dump()
        )
    except _CALLER_ERRORS as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return SupplierResponse.model_validate(supplier)


@router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SupplierResponse:
    try:
        supplier = await supplier_service.get_supplier(
            db, current_user.tenant_id, supplier_id
        )
    except _CALLER_ERRORS as exc:
        raise _not_found(exc) from exc
    return SupplierResponse.model_validate(supplier)


@router.patch(
    "/suppliers/{supplier_id}",
    response_model=SupplierResponse,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def update_supplier(
    supplier_id: uuid.UUID,
    data: SupplierUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SupplierResponse:
    try:
        supplier = await supplier_service.update_supplier(
            db,
            current_user.tenant_id,
            supplier_id,
            data.model_dump(exclude_unset=True),
        )
    except _CALLER_ERRORS as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return SupplierResponse.model_validate(supplier)


@router.delete(
    "/suppliers/{supplier_id}",
    response_model=SupplierResponse,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def deactivate_supplier(
    supplier_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SupplierResponse:
    """Deactivate, never delete. The purchase history is the point of the record."""
    try:
        supplier = await supplier_service.deactivate_supplier(
            db, current_user.tenant_id, supplier_id
        )
    except _CALLER_ERRORS as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return SupplierResponse.model_validate(supplier)


@router.get(
    "/suppliers/{supplier_id}/history", response_model=list[SupplierPurchaseRow]
)
async def supplier_history(
    supplier_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SupplierPurchaseRow]:
    try:
        rows = await supplier_service.supplier_purchase_history(
            db, current_user.tenant_id, supplier_id, limit
        )
    except _CALLER_ERRORS as exc:
        raise _not_found(exc) from exc
    return [SupplierPurchaseRow(**r) for r in rows]


# ---------------------------------------------------------------------------
# SUPPLIER CATALOGUE
# ---------------------------------------------------------------------------


@router.get("/catalogue", response_model=list[SupplierItemRow])
async def list_catalogue(
    supplier_id: uuid.UUID | None = Query(None),
    ingredient_id: uuid.UUID | None = Query(None),
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SupplierItemRow]:
    """Which suppliers sell which ingredients, and at what price."""
    rows = await supplier_service.list_supplier_items(
        db, current_user.tenant_id, supplier_id, ingredient_id, include_inactive
    )
    return [SupplierItemRow(**r) for r in rows]


@router.post(
    "/suppliers/{supplier_id}/items",
    response_model=SupplierItemRow,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def upsert_catalogue_item(
    supplier_id: uuid.UUID,
    data: SupplierItemUpsert,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SupplierItemRow:
    """Add or update one ingredient in a supplier's catalogue."""
    try:
        item = await supplier_service.upsert_supplier_item(
            db, current_user.tenant_id, supplier_id, data.model_dump()
        )
    except _CALLER_ERRORS as exc:
        raise _bad_request(exc) from exc
    await db.commit()

    rows = await supplier_service.list_supplier_items(
        db, current_user.tenant_id, supplier_id, data.ingredient_id, True
    )
    row = next((r for r in rows if r["id"] == item.id), None)
    if row is None:  # pragma: no cover -- just written
        raise HTTPException(status_code=500, detail="Catalogue row vanished after write.")
    return SupplierItemRow(**row)


@router.delete(
    "/catalogue/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def remove_catalogue_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await supplier_service.remove_supplier_item(db, current_user.tenant_id, item_id)
    except _CALLER_ERRORS as exc:
        raise _not_found(exc) from exc
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# PURCHASE ORDERS
# ---------------------------------------------------------------------------


@router.get("/purchase-orders", response_model=list[PurchaseOrderResponse])
async def list_purchase_orders(
    status_filter: str | None = Query(None, alias="status"),
    supplier_id: uuid.UUID | None = Query(None),
    location_id: uuid.UUID | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PurchaseOrderResponse]:
    rows = await purchase_order_service.list_purchase_orders(
        db, current_user.tenant_id, status_filter, supplier_id, location_id, limit
    )
    return [_po_out(po) for po in rows]


@router.post(
    "/purchase-orders",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def create_purchase_order(
    data: PurchaseOrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PurchaseOrderResponse:
    """Draft an order. Nothing is sent and no stock moves until it is."""
    try:
        po = await purchase_order_service.create_purchase_order(
            db,
            tenant_id=current_user.tenant_id,
            supplier_id=data.supplier_id,
            location_id=data.location_id,
            lines=[line.model_dump() for line in data.lines],
            tax_bps=data.tax_bps,
            expected_date=data.expected_date,
            notes=data.notes,
            delivery_instructions=data.delivery_instructions,
            created_by=current_user.id,
        )
    except _CALLER_ERRORS as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return _po_out(po)


@router.get("/receiving-history", response_model=list[ReceivingHistoryRow])
async def receiving_history(
    location_id: uuid.UUID | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReceivingHistoryRow]:
    """Every goods receipt, newest first (Martin's Section 9)."""
    rows = await purchase_order_service.receiving_history(
        db, current_user.tenant_id, location_id, limit
    )
    return [ReceivingHistoryRow(**r) for r in rows]


@router.get("/purchase-orders/{po_id}", response_model=PurchaseOrderResponse)
async def get_purchase_order(
    po_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PurchaseOrderResponse:
    try:
        po = await purchase_order_service.get_purchase_order(
            db, current_user.tenant_id, po_id
        )
    except _CALLER_ERRORS as exc:
        raise _not_found(exc) from exc
    return _po_out(po)


@router.patch(
    "/purchase-orders/{po_id}",
    response_model=PurchaseOrderResponse,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def update_purchase_order(
    po_id: uuid.UUID,
    data: PurchaseOrderUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PurchaseOrderResponse:
    """Edit a draft. A sent order is deliberately immutable."""
    payload = data.model_dump(exclude_unset=True)
    lines = payload.pop("lines", None)
    try:
        po = await purchase_order_service.update_purchase_order(
            db,
            tenant_id=current_user.tenant_id,
            po_id=po_id,
            data=payload,
            lines=lines,
        )
    except _CALLER_ERRORS as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return _po_out(po)


@router.get(
    "/purchase-orders/{po_id}/document",
    response_class=Response,
    responses={200: {"content": {"text/html": {}}}},
)
async def purchase_order_document_view(
    po_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """The printable PO, exactly as the supplier receives it by email.

    Same renderer as the email body, so what the buyer prints and what the
    supplier reads can never be two different documents.
    """
    try:
        po = await purchase_order_service.get_purchase_order(
            db, current_user.tenant_id, po_id
        )
    except _CALLER_ERRORS as exc:
        raise _not_found(exc) from exc
    doc = await purchase_order_document.build_document(db, current_user.tenant_id, po)
    return Response(
        content=purchase_order_document.render_html(doc), media_type="text/html"
    )


@router.post(
    "/purchase-orders/{po_id}/send",
    response_model=PurchaseOrderSendResponse,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def send_purchase_order(
    po_id: uuid.UUID,
    data: PurchaseOrderSendRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PurchaseOrderSendResponse:
    """Email the order to the supplier and mark it sent.

    A failed email does NOT fail the request or roll the status back. The order
    is recorded as placed, the failure is recorded next to it, and the response
    says plainly whether the email went out so the buyer can pick up the phone
    instead of assuming.
    """
    data = data or PurchaseOrderSendRequest()

    try:
        po = await purchase_order_service.get_purchase_order(
            db, current_user.tenant_id, po_id
        )
    except _CALLER_ERRORS as exc:
        raise _not_found(exc) from exc

    if po.status == "cancelled":
        raise _bad_request(ProcurementError("A cancelled purchase order cannot be sent."))
    if not po.items:
        raise _bad_request(
            ProcurementError("A purchase order with no items cannot be sent.")
        )

    if data.skip_email:
        try:
            po = await purchase_order_service.mark_sent(
                db, tenant_id=current_user.tenant_id, po_id=po_id
            )
        except _CALLER_ERRORS as exc:
            raise _bad_request(exc) from exc
        await db.commit()
        return PurchaseOrderSendResponse(
            purchase_order=_po_out(po), email_sent=False, sent_to=None
        )

    to = (data.to or po.supplier.email or "").strip()
    if not to:
        raise _bad_request(
            ProcurementError(
                f"{po.supplier.name} has no email address on file. Add one, supply "
                "a different address, or mark the order sent without emailing it."
            )
        )

    doc = await purchase_order_document.build_document(db, current_user.tenant_id, po)
    text = purchase_order_document.render_text(doc)
    html = purchase_order_document.render_html(doc)
    if data.message:
        text = f"{data.message}\n\n{text}"

    sent, error = await email_service.send_document_email(
        to=to,
        subject=f"Purchase Order {po.po_number} - {doc.buyer.name}",
        text=text,
        html=html,
        bcc=(po.location.email or "") if data.cc_self else "",
    )

    try:
        po = await purchase_order_service.mark_sent(
            db,
            tenant_id=current_user.tenant_id,
            po_id=po_id,
            sent_to_email=to,
            email_delivered=sent,
            email_error=error or None,
        )
    except _CALLER_ERRORS as exc:
        raise _bad_request(exc) from exc
    await db.commit()

    return PurchaseOrderSendResponse(
        purchase_order=_po_out(po),
        email_sent=sent,
        sent_to=to,
        error=error or None,
    )


@router.post(
    "/purchase-orders/{po_id}/receive",
    response_model=GoodsReceiptResult,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def receive_goods(
    po_id: uuid.UUID,
    data: GoodsReceiptRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoodsReceiptResult:
    """Book a delivery in. Stock lands at the order's own location."""
    try:
        po, receipt = await purchase_order_service.receive_goods(
            db,
            tenant_id=current_user.tenant_id,
            po_id=po_id,
            lines=[line.model_dump() for line in data.lines],
            source=data.source,
            document_reference=data.document_reference,
            notes=data.notes,
            performed_by=current_user.id,
        )
    except _CALLER_ERRORS as exc:
        raise _bad_request(exc) from exc
    await db.commit()

    # Re-read so the receipt's lines are attached to the live session rather
    # than an expired instance -- the MissingGreenlet trap this codebase has
    # been bitten by before.
    po = await purchase_order_service.get_purchase_order(
        db, current_user.tenant_id, po_id
    )
    fresh = next((r for r in po.receipts if r.id == receipt.id), None)
    if fresh is None:  # pragma: no cover -- just written
        raise HTTPException(status_code=500, detail="Receipt vanished after write.")
    return GoodsReceiptResult(purchase_order=_po_out(po), receipt=_receipt_out(fresh))


# ---------------------------------------------------------------------------
# ORDERING SUGGESTION
#
# 🔴 The quantities are COMPUTED, never generated. The optional AI layer adds
# commentary and cannot change a number. See `purchase_suggestion_service`.
# ---------------------------------------------------------------------------


@router.post(
    "/suggest-order",
    response_model=SuggestionResponse,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def suggest_order(
    data: SuggestionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuggestionResponse:
    """What to buy for a production target, from stock, recipes and open orders.

    Explodes each target through the recipe tree to raw ingredients, subtracts
    what is on hand and what is already on order, rounds up to whole packs, and
    groups the result into one basket per supplier.

    `include_advice` adds an AI review of the finished plan. If the AI is not
    configured, is capped out, or fails, the plan is still returned in full and
    `advice_error` explains why the commentary is missing. The numbers never
    depend on it.
    """
    try:
        plan = await purchase_suggestion_service.build_suggestion(
            db,
            tenant_id=current_user.tenant_id,
            location_id=data.location_id,
            targets=[t.model_dump() for t in data.targets],
        )
    except _CALLER_ERRORS as exc:
        raise _bad_request(exc) from exc

    advice_error: str | None = None
    if data.include_advice:
        try:
            plan["advice"] = await ai_procurement.advise_on_plan(
                db,
                tenant_id=current_user.tenant_id,
                plan=plan,
                days_until_production=data.days_until_production,
                requested_by=current_user.id,
            )
        except AIUnavailable as exc:
            # Deliberately not an error response. The plan is the product.
            advice_error = str(exc)
        # The usage row is written inside the AI client and must be kept even
        # when the call itself failed, so the cap counts the attempt.
        await db.commit()

    return SuggestionResponse(**plan, advice_error=advice_error)


# ---------------------------------------------------------------------------
# OCR GOODS RECEIVING
# ---------------------------------------------------------------------------


@router.post(
    "/purchase-orders/{po_id}/scan-delivery-note",
    response_model=ScanResult,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def scan_delivery_note(
    po_id: uuid.UUID,
    file: UploadFile = File(..., description="Photo or PDF of the delivery note"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScanResult:
    """Read a delivery note into PROPOSED receipt lines. Changes no stock.

    The result pre-fills the ordinary receiving form. A person checks it and
    confirms through `/purchase-orders/{id}/receive`, which is the same
    endpoint, with the same validation, that manual receiving uses. That is the
    point: the model proposes, a human disposes, and only one code path ever
    moves stock.
    """
    try:
        po = await purchase_order_service.get_purchase_order(
            db, current_user.tenant_id, po_id
        )
    except _CALLER_ERRORS as exc:
        raise _not_found(exc) from exc

    data = await file.read()
    if not data:
        raise _bad_request(ProcurementError("That file is empty."))

    try:
        result = await ai_procurement.extract_delivery_note(
            db,
            tenant_id=current_user.tenant_id,
            po=po,
            data=data,
            media_type=(file.content_type or "").split(";")[0].strip(),
            requested_by=current_user.id,
        )
    except AIUnavailable as exc:
        # 503, not 500: the request was fine, the assist is unavailable, and
        # the manual path is right there.
        await db.commit()  # keep the usage row that records the failed attempt
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    await db.commit()
    return ScanResult(**result)


# ---------------------------------------------------------------------------
# AI USAGE
# ---------------------------------------------------------------------------


@router.get(
    "/ai-usage",
    response_model=AIUsageSummary,
    dependencies=[Depends(require_role("admin"))],
)
async def ai_usage(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIUsageSummary:
    """What the AI features have cost, broken out by feature.

    The cost is an ESTIMATE from the published rate table, for reconciling
    against the Anthropic console. It is not an invoice.
    """
    today = datetime.now(timezone.utc).date()
    data = await ai_client.usage_summary(
        db,
        current_user.tenant_id,
        date_from or (today - timedelta(days=30)),
        date_to or today,
    )
    return AIUsageSummary(**data)


@router.post(
    "/purchase-orders/{po_id}/cancel",
    response_model=PurchaseOrderResponse,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def cancel_purchase_order(
    po_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PurchaseOrderResponse:
    """Cancel. Anything already received stays received."""
    try:
        po = await purchase_order_service.cancel_purchase_order(
            db, tenant_id=current_user.tenant_id, po_id=po_id
        )
    except _CALLER_ERRORS as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return _po_out(po)
