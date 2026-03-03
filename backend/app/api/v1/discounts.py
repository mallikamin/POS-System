"""Discount endpoints — discount type CRUD + apply/remove discounts on orders."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_permission, require_role
from app.database import get_db
from app.models.user import User
from app.schemas.discount import (
    ApplyDiscountRequest,
    DiscountBreakdown,
    DiscountTypeCreate,
    DiscountTypeResponse,
    DiscountTypeUpdate,
    OrderDiscountResponse,
)
from app.services import discount_service

router = APIRouter(prefix="/discounts", tags=["discounts"])

_admin_dep = require_role("admin")
_discount_manage_dep = require_permission("discount.manage")
_discount_apply_dep = require_permission("discount.apply")


# ---------------------------------------------------------------------------
# Discount Types (admin CRUD)
# ---------------------------------------------------------------------------

@router.get("/types", response_model=list[DiscountTypeResponse])
async def list_discount_types(
    active_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DiscountTypeResponse]:
    types = await discount_service.list_discount_types(
        db, current_user.tenant_id, active_only
    )
    return [DiscountTypeResponse.model_validate(t) for t in types]


@router.post(
    "/types",
    response_model=DiscountTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_discount_type(
    body: DiscountTypeCreate,
    current_user: User = Depends(_discount_manage_dep),
    db: AsyncSession = Depends(get_db),
) -> DiscountTypeResponse:
    dt = await discount_service.create_discount_type(
        db, current_user.tenant_id, body
    )
    await db.commit()
    return DiscountTypeResponse.model_validate(dt)


@router.patch("/types/{type_id}", response_model=DiscountTypeResponse)
async def update_discount_type(
    type_id: uuid.UUID,
    body: DiscountTypeUpdate,
    current_user: User = Depends(_discount_manage_dep),
    db: AsyncSession = Depends(get_db),
) -> DiscountTypeResponse:
    dt = await discount_service.get_discount_type(db, type_id, current_user.tenant_id)
    if dt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discount type not found")
    dt = await discount_service.update_discount_type(db, dt, body)
    await db.commit()
    return DiscountTypeResponse.model_validate(dt)


@router.delete("/types/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_discount_type(
    type_id: uuid.UUID,
    current_user: User = Depends(_discount_manage_dep),
    db: AsyncSession = Depends(get_db),
) -> None:
    dt = await discount_service.get_discount_type(db, type_id, current_user.tenant_id)
    if dt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discount type not found")
    await discount_service.delete_discount_type(db, dt)
    await db.commit()


# ---------------------------------------------------------------------------
# Apply / Remove Discounts
# ---------------------------------------------------------------------------

@router.post("/apply", response_model=OrderDiscountResponse, status_code=status.HTTP_201_CREATED)
async def apply_discount(
    body: ApplyDiscountRequest,
    current_user: User = Depends(_discount_apply_dep),
    db: AsyncSession = Depends(get_db),
) -> OrderDiscountResponse:
    try:
        od = await discount_service.apply_discount(
            db,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            order_id=body.order_id,
            table_session_id=body.table_session_id,
            discount_type_id=body.discount_type_id,
            label=body.label,
            source_type=body.source_type,
            amount=body.amount,
            note=body.note,
            manager_verify_token=body.manager_verify_token,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    await db.commit()
    return OrderDiscountResponse.model_validate(od)


@router.delete("/{discount_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_discount(
    discount_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await discount_service.remove_discount(db, discount_id, current_user.tenant_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    await db.commit()


# ---------------------------------------------------------------------------
# List Discounts on Order
# ---------------------------------------------------------------------------

@router.get("/orders/{order_id}", response_model=DiscountBreakdown)
async def get_order_discounts(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DiscountBreakdown:
    discounts = await discount_service.list_order_discounts(
        db, current_user.tenant_id, order_id
    )
    total_discount = sum(d.amount for d in discounts)
    return DiscountBreakdown(
        order_id=order_id,
        discounts=[OrderDiscountResponse.model_validate(d) for d in discounts],
        total_discount=total_discount,
    )
