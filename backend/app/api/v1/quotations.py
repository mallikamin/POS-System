"""Back-office quotations: offer a price, send it, win or lose it.

Every endpoint is tenant-scoped through `current_user.tenant_id`.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.models.quotation import Quotation
from app.models.user import User
from app.schemas.quotation import (
    QuotationConversion,
    QuotationCreate,
    QuotationDecision,
    QuotationItemResponse,
    QuotationResponse,
    QuotationSendRequest,
    QuotationSendResponse,
    QuotationUpdate,
)
from app.services import email_service, quotation_document, quotation_service
from app.services.quotation_service import QuotationError, display_status

router = APIRouter(prefix="/quotations", tags=["quotations"])


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _out(quotation: Quotation) -> QuotationResponse:
    return QuotationResponse(
        id=quotation.id,
        quote_number=quotation.quote_number,
        status=quotation.status,
        display_status=display_status(quotation),
        location_id=quotation.location_id,
        location_name=quotation.location.name if quotation.location else None,
        customer_id=quotation.customer_id,
        customer_name=quotation.customer_name,
        customer_phone=quotation.customer_phone,
        customer_email=quotation.customer_email,
        customer_address=quotation.customer_address,
        customer_trn=quotation.customer_trn,
        issue_date=quotation.issue_date,
        valid_until=quotation.valid_until,
        tax_rate_bps=quotation.tax_rate_bps,
        subtotal_minor=quotation.subtotal_minor,
        discount_minor=quotation.discount_minor,
        tax_minor=quotation.tax_minor,
        total_minor=quotation.total_minor,
        notes=quotation.notes,
        terms=quotation.terms,
        sent_at=quotation.sent_at,
        sent_to_email=quotation.sent_to_email,
        email_send_count=quotation.email_send_count,
        last_email_error=quotation.last_email_error,
        decided_at=quotation.decided_at,
        decline_reason=quotation.decline_reason,
        converted_order_id=quotation.converted_order_id,
        converted_at=quotation.converted_at,
        created_at=quotation.created_at,
        items=[
            QuotationItemResponse.model_validate(item)
            for item in sorted(quotation.items, key=lambda i: i.display_order)
        ],
    )


@router.get("", response_model=list[QuotationResponse])
async def list_quotations(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(200, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[QuotationResponse]:
    rows = await quotation_service.list_quotations(
        db, current_user.tenant_id, status_filter, limit
    )
    return [_out(q) for q in rows]


@router.post(
    "",
    response_model=QuotationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def create_quotation(
    data: QuotationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuotationResponse:
    payload = data.model_dump()
    payload["lines"] = [line.model_dump() for line in data.lines]
    try:
        quotation = await quotation_service.create_quotation(
            db,
            tenant_id=current_user.tenant_id,
            data=payload,
            created_by=current_user.id,
        )
    except QuotationError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return _out(quotation)


@router.get("/{quotation_id}", response_model=QuotationResponse)
async def get_quotation(
    quotation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuotationResponse:
    try:
        quotation = await quotation_service.get_quotation(
            db, current_user.tenant_id, quotation_id
        )
    except QuotationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _out(quotation)


@router.patch(
    "/{quotation_id}",
    response_model=QuotationResponse,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def update_quotation(
    quotation_id: uuid.UUID,
    data: QuotationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuotationResponse:
    payload = data.model_dump(exclude_unset=True)
    if data.lines is not None:
        payload["lines"] = [line.model_dump() for line in data.lines]
    try:
        quotation = await quotation_service.update_quotation(
            db,
            tenant_id=current_user.tenant_id,
            quotation_id=quotation_id,
            data=payload,
        )
    except QuotationError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return _out(quotation)


@router.get(
    "/{quotation_id}/document",
    response_class=Response,
    responses={200: {"content": {"text/html": {}}}},
)
async def quotation_document_view(
    quotation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """The printable quotation, identical to what the customer is emailed."""
    try:
        quotation = await quotation_service.get_quotation(
            db, current_user.tenant_id, quotation_id
        )
    except QuotationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    context = await quotation_document.build_context(
        db, current_user.tenant_id, quotation
    )
    return Response(
        content=quotation_document.render_html(context), media_type="text/html"
    )


@router.post(
    "/{quotation_id}/send",
    response_model=QuotationSendResponse,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def send_quotation(
    quotation_id: uuid.UUID,
    data: QuotationSendRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuotationSendResponse:
    """Email the quotation and mark it sent.

    A failed email does not roll the status back. The offer was made; the
    failure is recorded next to it and the response says plainly whether the
    email went out, so nobody assumes the customer has it.
    """
    data = data or QuotationSendRequest()
    try:
        quotation = await quotation_service.get_quotation(
            db, current_user.tenant_id, quotation_id
        )
    except QuotationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if data.skip_email:
        try:
            quotation = await quotation_service.mark_sent(
                db, tenant_id=current_user.tenant_id, quotation_id=quotation_id
            )
        except QuotationError as exc:
            raise _bad_request(exc) from exc
        await db.commit()
        return QuotationSendResponse(
            quotation=_out(quotation), email_sent=False, sent_to=None
        )

    # F50 (the F39 hazard, on quotations): the mail service on this server is
    # configured for ONE tenant's account and sending domain, so any other
    # tenant's quotation would go out under that identity. The UI no longer
    # offers email; refuse it here too so the API cannot do what the screen
    # cannot. Re-enable per tenant once tenant-scoped mail exists (OI-93 family).
    raise _bad_request(
        QuotationError(
            "Emailing quotations is not enabled. Mark it sent and pass the "
            "printed quotation to the customer."
        )
    )

    to = (data.to or quotation.customer_email or "").strip()  # pragma: no cover
    if not to:
        raise _bad_request(
            QuotationError(
                "This customer has no email address. Add one, supply a different "
                "address, or mark the quotation sent without emailing it."
            )
        )

    context = await quotation_document.build_context(
        db, current_user.tenant_id, quotation
    )
    text = quotation_document.render_text(context)
    if data.message:
        text = f"{data.message}\n\n{text}"

    sent, error = await email_service.send_document_email(
        to=to,
        subject=f"Quotation {quotation.quote_number} - {context['issuer_name']}",
        text=text,
        html=quotation_document.render_html(context),
    )

    try:
        quotation = await quotation_service.mark_sent(
            db,
            tenant_id=current_user.tenant_id,
            quotation_id=quotation_id,
            sent_to_email=to,
            email_delivered=sent,
            email_error=error or None,
        )
    except QuotationError as exc:
        raise _bad_request(exc) from exc
    await db.commit()

    return QuotationSendResponse(
        quotation=_out(quotation),
        email_sent=sent,
        sent_to=to,
        error=error or None,
    )


@router.post(
    "/{quotation_id}/decide",
    response_model=QuotationResponse,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def decide_quotation(
    quotation_id: uuid.UUID,
    data: QuotationDecision,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuotationResponse:
    """Record that the customer accepted or declined."""
    try:
        quotation = await quotation_service.decide(
            db,
            tenant_id=current_user.tenant_id,
            quotation_id=quotation_id,
            accepted=data.accepted,
            reason=data.reason,
        )
    except QuotationError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return _out(quotation)


@router.post(
    "/{quotation_id}/convert",
    response_model=QuotationConversion,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def convert_quotation(
    quotation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuotationConversion:
    """Turn an accepted quotation into a real order, at the quoted prices."""
    try:
        quotation, order = await quotation_service.convert_to_order(
            db,
            tenant_id=current_user.tenant_id,
            quotation_id=quotation_id,
            created_by=current_user.id,
        )
    except QuotationError as exc:
        raise _bad_request(exc) from exc
    await db.commit()

    quotation = await quotation_service.get_quotation(
        db, current_user.tenant_id, quotation_id
    )
    return QuotationConversion(
        quotation=_out(quotation),
        order_id=order.id,
        order_number=order.order_number,
    )
