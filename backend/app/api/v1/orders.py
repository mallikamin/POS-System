"""Order endpoints -- create, list, detail, status transitions, void."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.database import get_db
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.order import (
    OrderCreate,
    OrderListResponse,
    OrderResponse,
    OrderStatusUpdate,
    OrderVoidRequest,
    PaymentPreviewResponse,
)
from app.services import order_service
from app.services import audit_service
from app.services.auth_service import validate_verify_token

router = APIRouter(prefix="/orders", tags=["orders"])


def _to_order_response(order) -> OrderResponse:
    resp = OrderResponse.model_validate(order)
    if getattr(order, "table", None):
        resp.table_number = order.table.number
        resp.table_label = order.table.label
    return resp


# ---------------------------------------------------------------------------
# Create Order
# ---------------------------------------------------------------------------

@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """Create a new order from cart data. Auto-sends to kitchen."""
    order = await order_service.create_order(
        db, current_user.tenant_id, current_user.id, body
    )
    await audit_service.log_action(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        entity_type="order",
        entity_id=order.id,
        action="create",
        detail=f"Order {order.order_number} created ({order.order_type})",
    )
    await db.commit()
    await db.refresh(order)
    return _to_order_response(order)


# ---------------------------------------------------------------------------
# List Orders
# ---------------------------------------------------------------------------

@router.get("", response_model=PaginatedResponse[OrderListResponse])
async def list_orders(
    status_filter: str | None = Query(None, alias="status"),
    type_filter: str | None = Query(None, alias="type"),
    active_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[OrderListResponse]:
    """List orders with optional filtering and pagination."""
    offset = (page - 1) * page_size
    orders, total = await order_service.list_orders(
        db,
        current_user.tenant_id,
        status_filter=status_filter,
        type_filter=type_filter,
        active_only=active_only,
        offset=offset,
        limit=page_size,
    )
    items = [
        OrderListResponse(
            id=o.id,
            order_number=o.order_number,
            order_type=o.order_type,
            status=o.status,
            payment_status=o.payment_status,
            table_id=o.table_id,
            table_number=o.table.number if o.table else None,
            table_label=o.table.label if o.table else None,
            item_count=len(o.items),
            total=o.total,
            created_at=o.created_at,
            created_by=o.created_by,
        )
        for o in orders
    ]
    return PaginatedResponse.create(items, total, page, page_size)


# ---------------------------------------------------------------------------
# Get Order Detail
# ---------------------------------------------------------------------------

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """Get a single order with all items and modifiers."""
    order = await order_service.get_order(db, order_id, current_user.tenant_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return _to_order_response(order)


# ---------------------------------------------------------------------------
# Transition Order Status
# ---------------------------------------------------------------------------

@router.patch("/{order_id}/status", response_model=OrderResponse)
async def transition_order(
    order_id: uuid.UUID,
    body: OrderStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """Transition an order to a new status (validates state machine)."""
    try:
        order = await order_service.transition_order(
            db, order_id, current_user.tenant_id, current_user.id, body.status
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    await audit_service.log_action(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        entity_type="order",
        entity_id=order.id,
        action="status_change",
        detail=f"Order {order.order_number} → {body.status}",
    )
    await db.commit()
    await db.refresh(order)
    return _to_order_response(order)


# ---------------------------------------------------------------------------
# Payment Preview (dual totals by payment method)
# ---------------------------------------------------------------------------

@router.get("/{order_id}/payment-preview", response_model=PaymentPreviewResponse)
async def get_payment_preview(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentPreviewResponse:
    """Return cash and card total previews for an order based on method-specific tax rates."""
    preview = await order_service.get_payment_preview(
        db, order_id, current_user.tenant_id
    )
    if preview is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return preview


# ---------------------------------------------------------------------------
# Void Order (admin only)
# ---------------------------------------------------------------------------

@router.post("/{order_id}/void", response_model=OrderResponse)
async def void_order(
    order_id: uuid.UUID,
    body: OrderVoidRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """Void an order. Admin only. Requires password re-auth token."""
    # Validate re-auth token if provided
    if body.auth_token:
        verified_user_id = validate_verify_token(body.auth_token)
        if verified_user_id is None or verified_user_id != str(current_user.id):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired re-auth token")
    try:
        order = await order_service.void_order(
            db, order_id, current_user.tenant_id, current_user.id, body.reason
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    await audit_service.log_action(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        entity_type="order",
        entity_id=order.id,
        action="void",
        detail=f"Order {order.order_number} voided: {body.reason or 'No reason'}",
    )
    await db.commit()
    await db.refresh(order)
    return _to_order_response(order)
