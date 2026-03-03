from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.config import router as config_router
from app.api.v1.menu import router as menu_router
from app.api.v1.floor import router as floor_router
from app.api.v1.orders import router as orders_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.reports import router as reports_router
from app.api.v1.quickbooks import router as quickbooks_router
from app.api.v1.payments import router as payments_router
from app.api.v1.customers import router as customers_router
from app.api.v1.kitchen import router as kitchen_router
from app.api.v1.staff import router as staff_router
from app.api.v1.receipts import router as receipts_router
from app.api.v1.table_sessions import router as table_sessions_router
from app.api.v1.discounts import router as discounts_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(config_router)
api_v1_router.include_router(menu_router)
api_v1_router.include_router(floor_router)
api_v1_router.include_router(orders_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(reports_router)
api_v1_router.include_router(quickbooks_router)
api_v1_router.include_router(payments_router)
api_v1_router.include_router(customers_router)
api_v1_router.include_router(kitchen_router)
api_v1_router.include_router(staff_router)
api_v1_router.include_router(receipts_router)
api_v1_router.include_router(table_sessions_router)
api_v1_router.include_router(discounts_router)
