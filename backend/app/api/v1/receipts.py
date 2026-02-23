"""Receipt endpoints -- structured receipt data for printing."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.receipt import ReceiptData
from app.services import receipt_service

router = APIRouter(prefix="/receipts", tags=["receipts"])


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
