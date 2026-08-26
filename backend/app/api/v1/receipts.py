"""Receipt endpoints -- structured receipt data for printing."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.receipt import ReceiptData
from app.schemas.tax_invoice import TaxInvoiceData
from app.services import receipt_service, tax_invoice_service
from app.services.tax_invoice_service import TaxInvoiceError

router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.get("/orders/{order_id}/tax-invoice", response_model=TaxInvoiceData)
async def get_order_tax_invoice(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaxInvoiceData:
    """A4 VAT tax invoice for an order, with VAT shown as its own figure.

    Distinct from the thermal receipt above: this is the legal document a B2B
    customer needs, carrying the supplier's registered name and TRN.
    """
    try:
        return await tax_invoice_service.get_tax_invoice(
            db, current_user.tenant_id, order_id
        )
    except TaxInvoiceError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.get("/orders/{order_id}", response_model=ReceiptData)
async def get_order_receipt(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReceiptData:
    """Get structured receipt data for an order."""
    try:
        return await receipt_service.get_receipt_data(
            db, current_user.tenant_id, order_id, current_user.full_name
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.get("/sessions/{session_id}", response_model=ReceiptData)
async def get_session_receipt(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReceiptData:
    """Get consolidated receipt data for all orders in a table session."""
    try:
        return await receipt_service.get_session_receipt_data(
            db, current_user.tenant_id, session_id, current_user.full_name
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
