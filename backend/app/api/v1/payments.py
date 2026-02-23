"""Payment endpoints -- create, split, refund, and cash drawer sessions."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.database import get_db
from app.models.user import User
from app.schemas.payment import (
    CashDrawerCloseRequest,
    CashDrawerOpenRequest,
    CashDrawerSessionResponse,
    PaymentCreate,
    PaymentMethodResponse,
    PaymentSummary,
    RefundCreate,
    SplitPaymentCreate,
)
from app.services import payment_service

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


@router.post("/split", response_model=PaymentSummary, status_code=status.HTTP_201_CREATED)
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
    dependencies=[Depends(require_role("admin"))],
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


@router.get("/drawer/session", response_model=CashDrawerSessionResponse | None)
async def get_drawer_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CashDrawerSessionResponse | None:
    session = await payment_service.get_active_drawer_session(db, current_user.tenant_id)
    return CashDrawerSessionResponse.model_validate(session) if session else None


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
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


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
