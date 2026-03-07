"""Report endpoints -- sales summary, item performance, hourly breakdown, Z-report."""

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.database import get_db
from app.models.user import User
from app.schemas.report import (
    HourlyBreakdown,
    ItemPerformance,
    PaymentMethodReport,
    SalesSummary,
    VoidReport,
    WaiterPerformanceReport,
)
from app.schemas.zreport import ZReport
from app.services import report_service
from app.services import zreport_service

router = APIRouter(prefix="/reports", tags=["reports"])

_admin = require_role("admin")


@router.get("/sales-summary", response_model=SalesSummary)
async def get_sales_summary(
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> SalesSummary:
    """Get sales summary for a date range."""
    data = await report_service.get_sales_summary(
        db, current_user.tenant_id, date_from, date_to
    )
    return SalesSummary(**data)


@router.get("/item-performance", response_model=ItemPerformance)
async def get_item_performance(
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> ItemPerformance:
    """Get top/bottom items and category breakdown for a date range."""
    data = await report_service.get_item_performance(
        db, current_user.tenant_id, date_from, date_to
    )
    return ItemPerformance(**data)


@router.get("/hourly-breakdown", response_model=HourlyBreakdown)
async def get_hourly_breakdown(
    target_date: date = Query(default_factory=date.today, alias="date"),
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> HourlyBreakdown:
    """Get hourly order/revenue breakdown for a specific date."""
    data = await report_service.get_hourly_breakdown(
        db, current_user.tenant_id, target_date
    )
    return HourlyBreakdown(**data)


@router.get("/sales-summary/csv")
async def export_sales_csv(
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export sales summary as CSV."""
    data = await report_service.get_sales_summary(
        db, current_user.tenant_id, date_from, date_to
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Revenue (PKR)", data["total_revenue"] / 100])
    writer.writerow(["Total Discount (PKR)", data["total_discount"] / 100])
    writer.writerow(["Net Revenue (PKR)", data["net_revenue"] / 100])
    writer.writerow(["Total Orders", data["total_orders"]])
    writer.writerow(["Avg Order Value (PKR)", data["avg_order_value"] / 100])
    writer.writerow(["Total Tax (PKR)", data["total_tax"] / 100])
    writer.writerow(["Cash Revenue (PKR)", data["cash_revenue"] / 100])
    writer.writerow(["Card Revenue (PKR)", data["card_revenue"] / 100])
    writer.writerow(["Other Revenue (PKR)", data["other_revenue"] / 100])
    writer.writerow(["Dine-In Revenue (PKR)", data["dine_in_revenue"] / 100])
    writer.writerow(["Dine-In Orders", data["dine_in_orders"]])
    writer.writerow(["Takeaway Revenue (PKR)", data["takeaway_revenue"] / 100])
    writer.writerow(["Takeaway Orders", data["takeaway_orders"]])
    writer.writerow(["Call Center Revenue (PKR)", data["call_center_revenue"] / 100])
    writer.writerow(["Call Center Orders", data["call_center_orders"]])
    # Discount breakdown
    for entry in data.get("discount_breakdown", []):
        writer.writerow([f"Discount: {entry['label']} (PKR)", entry["total"] / 100])

    output.seek(0)
    filename = f"sales_summary_{date_from}_{date_to}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/void-report", response_model=VoidReport)
async def get_void_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> VoidReport:
    """Get void report with reason and user analytics for a date range."""
    data = await report_service.get_void_report(
        db, current_user.tenant_id, date_from, date_to
    )
    return VoidReport(**data)


@router.get("/payment-method", response_model=PaymentMethodReport)
async def get_payment_method_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> PaymentMethodReport:
    """Get payment-method breakdown for a date range."""
    data = await report_service.get_payment_method_report(
        db, current_user.tenant_id, date_from, date_to
    )
    return PaymentMethodReport(**data)


@router.get("/waiter-performance", response_model=WaiterPerformanceReport)
async def get_waiter_performance(
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> WaiterPerformanceReport:
    """Get waiter performance breakdown for a date range."""
    data = await report_service.get_waiter_performance(
        db, current_user.tenant_id, date_from, date_to
    )
    return WaiterPerformanceReport(**data)


@router.get("/z-report", response_model=ZReport)
async def get_z_report(
    target_date: date = Query(default_factory=date.today, alias="date"),
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> ZReport:
    """Generate Z-Report (daily settlement) for a given date."""
    data = await zreport_service.generate_zreport(
        db, current_user.tenant_id, target_date, current_user.full_name
    )
    return ZReport(**data)
