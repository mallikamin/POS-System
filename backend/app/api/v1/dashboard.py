"""Dashboard endpoints -- real-time KPIs and live operations."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.database import get_db
from app.models.user import User
from app.schemas.dashboard import ActivityFeed, DashboardKpis, LiveOperations
from app.services import activity_feed_service, dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/activity", response_model=ActivityFeed)
async def get_activity_feed(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> ActivityFeed:
    """Today's live feed for the owner, newest first (D-57). Admin only: it
    carries every bill's amount."""
    data = await activity_feed_service.get_activity_feed(db, current_user.tenant_id)
    return ActivityFeed(**data)


@router.get("/kpis", response_model=DashboardKpis)
async def get_kpis(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardKpis:
    """Get today's dashboard KPIs (revenue, orders, utilization)."""
    data = await dashboard_service.get_dashboard_kpis(db, current_user.tenant_id)
    return DashboardKpis(**data)


@router.get("/live", response_model=LiveOperations)
async def get_live_operations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LiveOperations:
    """Get active orders grouped by channel for live operations view."""
    data = await dashboard_service.get_live_operations(db, current_user.tenant_id)
    return LiveOperations(**data)
