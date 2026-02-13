"""Restaurant configuration endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.restaurant_config import RestaurantConfig
from app.models.user import User
from app.schemas.tenant import RestaurantConfigResponse

router = APIRouter(prefix="/config", tags=["config"])


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

    return RestaurantConfigResponse.model_validate(config)
