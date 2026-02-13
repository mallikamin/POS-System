from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.config import router as config_router
from app.api.v1.menu import router as menu_router
from app.api.v1.floor import router as floor_router
from app.api.v1.orders import router as orders_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.reports import router as reports_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(config_router)
api_v1_router.include_router(menu_router)
api_v1_router.include_router(floor_router)
api_v1_router.include_router(orders_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(reports_router)
