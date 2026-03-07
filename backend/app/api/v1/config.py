"""Restaurant configuration endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.database import get_db
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tenant import RestaurantConfigResponse

router = APIRouter(prefix="/config", tags=["config"])


class RestaurantConfigUpdate(BaseModel):
    """Fields that can be updated on restaurant configuration."""

    restaurant_name: str | None = Field(None, min_length=1, max_length=200)
    receipt_header: str | None = None
    receipt_footer: str | None = None
    default_tax_rate: int | None = Field(None, ge=0, le=10000)
    cash_tax_rate_bps: int | None = Field(None, ge=0, le=10000)
    card_tax_rate_bps: int | None = Field(None, ge=0, le=10000)
    payment_flow: str | None = Field(None, pattern=r"^(order_first|pay_first)$")
    timezone: str | None = None
    currency: str | None = Field(None, min_length=2, max_length=10)
    tax_inclusive: bool | None = None
    discount_approval_threshold_bps: int | None = Field(None, ge=0, le=10000)
    discount_approval_threshold_fixed: int | None = Field(None, ge=0)


@router.get("/restaurant", response_model=RestaurantConfigResponse)
async def get_restaurant_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RestaurantConfigResponse:
    """Retrieve the restaurant configuration for the authenticated user's tenant."""
    result = await db.execute(
        select(RestaurantConfig).where(
            RestaurantConfig.tenant_id == current_user.tenant_id
        )
    )
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant configuration not found for this tenant",
        )

    # Include tenant name in response
    tenant_result = await db.execute(
        select(Tenant.name).where(Tenant.id == current_user.tenant_id)
    )
    tenant_name = tenant_result.scalar_one_or_none()

    resp = RestaurantConfigResponse.model_validate(config)
    resp.restaurant_name = tenant_name
    return resp


@router.patch(
    "/restaurant",
    response_model=RestaurantConfigResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def update_restaurant_config(
    data: RestaurantConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RestaurantConfigResponse:
    """Update restaurant configuration (admin only)."""
    result = await db.execute(
        select(RestaurantConfig).where(
            RestaurantConfig.tenant_id == current_user.tenant_id
        )
    )
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant configuration not found for this tenant",
        )

    # Update restaurant name on tenant if provided
    if data.restaurant_name is not None:
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.id == current_user.tenant_id)
        )
        tenant = tenant_result.scalar_one()
        tenant.name = data.restaurant_name

    # Update config fields
    if data.receipt_header is not None:
        config.receipt_header = data.receipt_header
    if data.receipt_footer is not None:
        config.receipt_footer = data.receipt_footer
    if data.default_tax_rate is not None:
        config.default_tax_rate = data.default_tax_rate
    if data.cash_tax_rate_bps is not None:
        config.cash_tax_rate_bps = data.cash_tax_rate_bps
    if data.card_tax_rate_bps is not None:
        config.card_tax_rate_bps = data.card_tax_rate_bps
    if data.payment_flow is not None:
        config.payment_flow = data.payment_flow
    if data.timezone is not None:
        config.timezone = data.timezone
    if data.currency is not None:
        config.currency = data.currency
    if data.tax_inclusive is not None:
        config.tax_inclusive = data.tax_inclusive
    if data.discount_approval_threshold_bps is not None:
        config.discount_approval_threshold_bps = data.discount_approval_threshold_bps
    if data.discount_approval_threshold_fixed is not None:
        config.discount_approval_threshold_fixed = (
            data.discount_approval_threshold_fixed
        )

    await db.commit()
    await db.refresh(config)
    return RestaurantConfigResponse.model_validate(config)
