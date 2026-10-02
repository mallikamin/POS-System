"""Restaurant configuration endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.database import get_db
from app.models.menu import MenuItem
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
    receipt_format: str | None = Field(None, pattern=r"^(thermal|a4)$")
    # Empty string clears it back to "Takeaway".
    takeaway_label: str | None = Field(None, max_length=40)
    default_tax_rate: int | None = Field(None, ge=0, le=10000)
    cash_tax_rate_bps: int | None = Field(None, ge=0, le=10000)
    card_tax_rate_bps: int | None = Field(None, ge=0, le=10000)
    # D-97. Capped at 30%: a typo like 500 meaning 5.00% must not become 50%.
    service_charge_bps: int | None = Field(None, ge=0, le=3000)
    service_charge_dine_in_only: bool | None = None
    # D-99 visit loyalty. An empty string for the item id clears the reward item.
    loyalty_enabled: bool | None = None
    loyalty_visits_required: int | None = Field(None, ge=1, le=50)
    loyalty_reward_menu_item_id: str | None = None
    loyalty_reward_label: str | None = Field(None, max_length=80)
    loyalty_max_visits_per_day: int | None = Field(None, ge=0, le=20)  # 0 = no limit
    payment_flow: str | None = Field(None, pattern=r"^(order_first|pay_first)$")
    timezone: str | None = None
    currency: str | None = Field(None, min_length=2, max_length=10)
    tax_inclusive: bool | None = None
    discount_approval_threshold_bps: int | None = Field(None, ge=0, le=10000)
    discount_approval_threshold_fixed: int | None = Field(None, ge=0)
    online_ordering_only: bool | None = None
    # Presentation only. Hides nav entries and dashboard cards; does NOT gate
    # the endpoints behind them (OI-93). Empty string clears it.
    hidden_ui_modules: str | None = Field(None, max_length=500)


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

    # Include the tenant's name AND its slug. The slug is what makes the session
    # self-describing: without it the frontend had to infer which shop it was
    # signed in to from a localStorage value that any URL could overwrite.
    tenant_result = await db.execute(
        select(Tenant.name, Tenant.slug).where(Tenant.id == current_user.tenant_id)
    )
    tenant_row = tenant_result.one_or_none()

    resp = RestaurantConfigResponse.model_validate(config)
    if tenant_row is not None:
        resp.restaurant_name, resp.tenant_slug = tenant_row
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
    if data.receipt_format is not None:
        config.receipt_format = data.receipt_format
    if data.takeaway_label is not None:
        config.takeaway_label = data.takeaway_label.strip() or None
    if data.default_tax_rate is not None:
        config.default_tax_rate = data.default_tax_rate
    if data.cash_tax_rate_bps is not None:
        config.cash_tax_rate_bps = data.cash_tax_rate_bps
    if data.card_tax_rate_bps is not None:
        config.card_tax_rate_bps = data.card_tax_rate_bps
    if data.service_charge_bps is not None:
        config.service_charge_bps = data.service_charge_bps
    if data.service_charge_dine_in_only is not None:
        config.service_charge_dine_in_only = data.service_charge_dine_in_only
    if data.loyalty_enabled is not None:
        config.loyalty_enabled = data.loyalty_enabled
    if data.loyalty_visits_required is not None:
        config.loyalty_visits_required = data.loyalty_visits_required
    if data.loyalty_max_visits_per_day is not None:
        config.loyalty_max_visits_per_day = data.loyalty_max_visits_per_day
    if data.loyalty_reward_label is not None:
        config.loyalty_reward_label = data.loyalty_reward_label.strip() or None
    if data.loyalty_reward_menu_item_id is not None:
        if data.loyalty_reward_menu_item_id == "":
            config.loyalty_reward_menu_item_id = None
        else:
            try:
                item_id = uuid.UUID(data.loyalty_reward_menu_item_id)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="Invalid reward item") from exc
            owned = (await db.execute(
                select(MenuItem.id).where(MenuItem.id == item_id,
                                          MenuItem.tenant_id == current_user.tenant_id)
            )).scalar_one_or_none()
            if owned is None:
                raise HTTPException(status_code=422, detail="Reward item not on this menu")
            config.loyalty_reward_menu_item_id = item_id
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
    if data.online_ordering_only is not None:
        config.online_ordering_only = data.online_ordering_only
    if data.hidden_ui_modules is not None:
        # Normalised on the way in so the frontend never has to cope with
        # "Dine-In , quickbooks-online" typed by a human into a settings box.
        config.hidden_ui_modules = ",".join(
            part.strip().lower()
            for part in data.hidden_ui_modules.split(",")
            if part.strip()
        )

    await db.commit()
    await db.refresh(config)

    # PATCH previously returned a response with no restaurant_name, because only
    # the GET above bothered to fetch it. A client that re-read config from this
    # response therefore lost the shop's name until the next full reload -- which
    # is what puts "Restaurant not loaded" on screen. Same lookup as the GET.
    tenant_result = await db.execute(
        select(Tenant.name, Tenant.slug).where(Tenant.id == current_user.tenant_id)
    )
    tenant_row = tenant_result.one_or_none()
    resp = RestaurantConfigResponse.model_validate(config)
    if tenant_row is not None:
        resp.restaurant_name, resp.tenant_slug = tenant_row
    return resp
