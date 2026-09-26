"""Payment endpoints -- create, split, refund, and cash drawer sessions."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.payment import (
    CashDrawerAttachmentResponse,
    CashDrawerCloseRequest,
    CashDrawerOpenRequest,
    CashDrawerSessionResponse,
    CashDrawerSummary,
    PaymentCreate,
    PaymentMethodResponse,
    PaymentSummary,
    RefundCreate,
    SessionPaymentCreate,
    SessionPaymentPreview,
    SessionPaymentSummary,
    SessionSplitPaymentCreate,
    SplitPaymentCreate,
)
from app.services import media_service, payment_service
from app.services.media_service import ImageTooLarge, InvalidDocument, MAX_UPLOAD_BYTES

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/methods", response_model=list[PaymentMethodResponse])
async def list_payment_methods(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PaymentMethodResponse]:
    methods = await payment_service.list_payment_methods(db, current_user.tenant_id)
    await db.commit()
    return [PaymentMethodResponse.model_validate(method) for method in methods]


@router.get("/orders/{order_id}/summary", response_model=PaymentSummary)
async def get_order_payment_summary(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentSummary:
    try:
        return await payment_service.get_order_payment_summary(
            db, order_id, current_user.tenant_id
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.post("", response_model=PaymentSummary, status_code=status.HTTP_201_CREATED)
async def create_payment(
    body: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentSummary:
    try:
        summary = await payment_service.create_payment(
            db, current_user.tenant_id, current_user.id, body
        )
        await db.commit()
        return summary
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post(
    "/split", response_model=PaymentSummary, status_code=status.HTTP_201_CREATED
)
async def split_payment(
    body: SplitPaymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentSummary:
    try:
        summary = await payment_service.split_payment(
            db, current_user.tenant_id, current_user.id, body
        )
        await db.commit()
        return summary
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post(
    "/refund",
    response_model=PaymentSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("payment.refund"))],
)
async def refund_payment(
    body: RefundCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentSummary:
    try:
        summary = await payment_service.create_refund(
            db, current_user.tenant_id, current_user.id, body
        )
        await db.commit()
        return summary
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


# ---------------------------------------------------------------------------
# Session Payment (P2)
# ---------------------------------------------------------------------------


@router.get(
    "/table-sessions/{session_id}/summary", response_model=SessionPaymentSummary
)
async def get_session_payment_summary(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionPaymentSummary:
    try:
        return await payment_service.get_session_payment_summary(
            db, session_id, current_user.tenant_id
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.get(
    "/table-sessions/{session_id}/payment-preview",
    response_model=SessionPaymentPreview,
)
async def get_session_payment_preview(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionPaymentPreview:
    try:
        return await payment_service.get_session_payment_preview(
            db, session_id, current_user.tenant_id
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.post(
    "/table-sessions/{session_id}/pay",
    response_model=SessionPaymentSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_session_payment(
    session_id: uuid.UUID,
    body: SessionPaymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionPaymentSummary:
    try:
        summary = await payment_service.create_session_payment(
            db, current_user.tenant_id, current_user.id, session_id, body
        )
        await db.commit()
        return summary
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post(
    "/table-sessions/{session_id}/split",
    response_model=SessionPaymentSummary,
    status_code=status.HTTP_201_CREATED,
)
async def split_session_payment(
    session_id: uuid.UUID,
    body: SessionSplitPaymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionPaymentSummary:
    try:
        summary = await payment_service.split_session_payment(
            db, current_user.tenant_id, current_user.id, session_id, body
        )
        await db.commit()
        return summary
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/drawer/session", response_model=CashDrawerSessionResponse | None)
async def get_drawer_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CashDrawerSessionResponse | None:
    session = await payment_service.get_active_drawer_session(
        db, current_user.tenant_id
    )
    return CashDrawerSessionResponse.model_validate(session) if session else None


@router.get("/drawer/summary", response_model=CashDrawerSummary | None)
async def get_drawer_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CashDrawerSummary | None:
    summary = await payment_service.get_drawer_summary(db, current_user.tenant_id)
    return CashDrawerSummary(**summary) if summary else None


@router.post(
    "/drawer/open",
    response_model=CashDrawerSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def open_drawer(
    body: CashDrawerOpenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CashDrawerSessionResponse:
    try:
        session = await payment_service.open_drawer_session(
            db, current_user.tenant_id, current_user.id, body
        )
        await db.commit()
        return CashDrawerSessionResponse.model_validate(session)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A cash drawer is already open for this tenant"
        )
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post(
    "/drawer/{session_id}/attachments",
    response_model=CashDrawerAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_drawer_attachment(
    session_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CashDrawerAttachmentResponse:
    """Pin a photo or PDF to a drawer session at close (Danny's D-78). Same
    size cap and file checks as expense attachments."""
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"An attachment must be {MAX_UPLOAD_BYTES // (1024 * 1024)} MB or smaller.",
        )
    # The session is checked BEFORE the bytes are stored, so a bad id leaves
    # no orphan media row behind.
    try:
        await payment_service.get_drawer_session_by_id(db, current_user.tenant_id, session_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    try:
        media = await media_service.store_document(
            db, current_user.tenant_id, data, original_filename=file.filename
        )
    except ImageTooLarge:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"An attachment must be {MAX_UPLOAD_BYTES // (1024 * 1024)} MB or smaller.",
        )
    except InvalidDocument as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"That file cannot be attached ({exc}). Use a PDF or a photo.",
        )
    row = await payment_service.add_drawer_attachment(
        db, current_user.tenant_id, session_id, media, file.filename
    )
    await db.commit()
    return CashDrawerAttachmentResponse(
        id=row.id,
        filename=row.filename,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        url=f"/api/v1/payments/drawer/{session_id}/attachments/{row.id}",
    )


@router.get("/drawer/{session_id}/attachments/{attachment_id}")
async def download_drawer_attachment(
    session_id: uuid.UUID,
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Serve one drawer attachment. `inline` + `nosniff`, as for expenses, so
    a crafted upload cannot be sniffed as HTML on this origin."""
    try:
        row = await payment_service.get_drawer_attachment(
            db, current_user.tenant_id, session_id, attachment_id
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    media = await media_service.get_media_bytes(db, row.media_id)
    if media is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The file is no longer stored.")
    safe_name = (row.filename or "attachment").replace('"', "")
    return Response(
        content=media.data,
        media_type=media.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe_name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=300",
        },
    )


@router.post("/drawer/close", response_model=CashDrawerSessionResponse)
async def close_drawer(
    body: CashDrawerCloseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CashDrawerSessionResponse:
    try:
        session = await payment_service.close_drawer_session(
            db, current_user.tenant_id, current_user.id, body
        )
        await db.commit()
        return CashDrawerSessionResponse.model_validate(session)
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
