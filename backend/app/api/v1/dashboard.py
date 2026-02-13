"""Dashboard endpoints -- real-time KPIs and live operations."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardKpis, LiveOperations
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


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
