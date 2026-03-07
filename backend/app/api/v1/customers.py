"""Customer endpoints -- search, CRUD, order history for call-center channel."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.customer import (
    CustomerCreate,
    CustomerOrderHistoryItem,
    CustomerResponse,
    CustomerUpdate,
)
from app.services import customer_service

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/search", response_model=list[CustomerResponse])
async def search_customers(
    phone: str = Query(
        ..., min_length=1, max_length=20, description="Phone digits to search"
    ),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CustomerResponse]:
    """Search customers by partial phone number match."""
    customers = await customer_service.search_by_phone(
        db, current_user.tenant_id, phone, limit
    )
    for customer in customers:
        await customer_service.update_customer_stats(
            db, current_user.tenant_id, customer
        )
    return [CustomerResponse.model_validate(c) for c in customers]


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CustomerResponse:
    customer = await customer_service.get_customer(
        db, customer_id, current_user.tenant_id
    )
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    await customer_service.update_customer_stats(
        db, current_user.tenant_id, customer
    )
    return CustomerResponse.model_validate(customer)


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    body: CustomerCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CustomerResponse:
    try:
        customer = await customer_service.create_customer(
            db, current_user.tenant_id, body
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    await db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: uuid.UUID,
    body: CustomerUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CustomerResponse:
    customer = await customer_service.get_customer(
        db, customer_id, current_user.tenant_id
    )
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    try:
        customer = await customer_service.update_customer(
            db, customer, current_user.tenant_id, body
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    await db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@router.get("/{customer_id}/orders", response_model=list[CustomerOrderHistoryItem])
async def get_customer_order_history(
    customer_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CustomerOrderHistoryItem]:
    """Get recent orders for a customer (matched by phone number)."""
    customer = await customer_service.get_customer(
        db, customer_id, current_user.tenant_id
    )
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    orders = await customer_service.get_order_history(
        db, current_user.tenant_id, customer.phone, limit
    )
    return [CustomerOrderHistoryItem.model_validate(o) for o in orders]
