"""Report endpoints -- sales summary, item performance, hourly breakdown, Z-report."""

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.database import get_db
from app.models.user import User
from app.schemas.report import (
    HourlyBreakdown,
    ItemPerformance,
    PaymentMethodReport,
    SalesSummary,
    TableSizeReport,
    VoidReport,
    WaiterPerformanceReport,
)
from app.schemas.zreport import ZReport
from app.services import public_order_service
from app.services import report_service
from app.services import zreport_service
from app.utils.tenant_time import local_today, tenant_timezone

router = APIRouter(prefix="/reports", tags=["reports"])

_admin = require_role("admin")


@router.get("/sales-summary", response_model=SalesSummary)
async def get_sales_summary(
    date_from: date = Query(...),
    date_to: date = Query(...),
    compare: bool = Query(False),
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> SalesSummary:
    """Get sales summary for a date range; `compare` adds the previous period."""
    data = await report_service.get_sales_summary(
        db, current_user.tenant_id, date_from, date_to, compare=compare
    )
    return SalesSummary(**data)


@router.get("/item-performance", response_model=ItemPerformance)
async def get_item_performance(
    date_from: date = Query(...),
    date_to: date = Query(...),
    compare: bool = Query(False),
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> ItemPerformance:
    """Get top/bottom items and category breakdown for a date range."""
    data = await report_service.get_item_performance(
        db, current_user.tenant_id, date_from, date_to, compare=compare
    )
    return ItemPerformance(**data)


@router.get("/hourly-breakdown", response_model=HourlyBreakdown)
async def get_hourly_breakdown(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    single_date: date | None = Query(None, alias="date"),
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> HourlyBreakdown:
    """Hourly order/revenue breakdown over a date range (D-53).

    `?date=` (one day) still works for older clients. With nothing given it is
    the restaurant's today, not the server's: `date.today` was the container's
    UTC day, yesterday in Pakistan until 5 am.
    """
    start = date_from or single_date
    if start is None:
        start = local_today(await tenant_timezone(db, current_user.tenant_id))
    data = await report_service.get_hourly_breakdown(
        db, current_user.tenant_id, start, date_to or start
    )
    return HourlyBreakdown(**data)


@router.get("/table-size", response_model=TableSizeReport)
async def get_table_size_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> TableSizeReport:
    """Dine-in visits, spend and dishes by table size (D-56)."""
    data = await report_service.get_table_size_report(
        db, current_user.tenant_id, date_from, date_to
    )
    return TableSizeReport(**data)


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
    # The label must follow the tenant, not the country the POS was written in.
    # Same helper the online reports (OI-58) already use: one source of truth
    # for "what currency is this tenant in", never re-expressed inline.
    currency = await public_order_service.get_currency(db, current_user.tenant_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Metric", "Value"])
    writer.writerow([f"Total Revenue ({currency})", data["total_revenue"] / 100])
    writer.writerow([f"Total Discount ({currency})", data["total_discount"] / 100])
    writer.writerow([f"Net Revenue ({currency})", data["net_revenue"] / 100])
    writer.writerow(["Total Orders", data["total_orders"]])
    writer.writerow([f"Avg Order Value ({currency})", data["avg_order_value"] / 100])
    writer.writerow([f"Total Tax ({currency})", data["total_tax"] / 100])
    writer.writerow([f"Cash Revenue ({currency})", data["cash_revenue"] / 100])
    writer.writerow([f"Card Revenue ({currency})", data["card_revenue"] / 100])
    writer.writerow([f"Other Revenue ({currency})", data["other_revenue"] / 100])
    writer.writerow([f"Dine-In Revenue ({currency})", data["dine_in_revenue"] / 100])
    writer.writerow(["Dine-In Orders", data["dine_in_orders"]])
    writer.writerow([f"Takeaway Revenue ({currency})", data["takeaway_revenue"] / 100])
    writer.writerow(["Takeaway Orders", data["takeaway_orders"]])
    writer.writerow(
        [f"Call Center Revenue ({currency})", data["call_center_revenue"] / 100]
    )
    writer.writerow(["Call Center Orders", data["call_center_orders"]])
    writer.writerow([f"Online Revenue ({currency})", data["online_revenue"] / 100])
    writer.writerow(["Online Orders", data["online_orders"]])
    # Discount breakdown
    for entry in data.get("discount_breakdown", []):
        writer.writerow(
            [f"Discount: {entry['label']} ({currency})", entry["total"] / 100]
        )

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
