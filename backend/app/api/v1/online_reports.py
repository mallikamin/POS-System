"""OI-58: reports specific to online-ordering tenants (Chick Shack and
whichever comes next) -- prepaid vs cash-on-delivery, rejected orders, and
Stripe reconciliation. Daily Sales deliberately has no route here; it reuses
the existing `/reports/sales-summary` (and its `/csv`), which OI-58a already
fixed to expose `online_revenue`/`online_orders`.
"""

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.database import get_db
from app.models.user import User
from app.schemas.online_report import (
    PrepaidVsCodReport,
    RejectedOrdersReport,
    StripeReconciliationReport,
)
from app.services import online_report_service, public_order_service

router = APIRouter(prefix="/reports/online", tags=["reports"])

_admin = require_role("admin")


@router.get("/prepaid-vs-cod", response_model=PrepaidVsCodReport)
async def get_prepaid_vs_cod(
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> PrepaidVsCodReport:
    data = await online_report_service.get_prepaid_vs_cod(
        db, current_user.tenant_id, date_from, date_to
    )
    return PrepaidVsCodReport(**data)


@router.get("/prepaid-vs-cod/csv")
async def export_prepaid_vs_cod_csv(
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    data = await online_report_service.get_prepaid_vs_cod(
        db, current_user.tenant_id, date_from, date_to
    )
    currency = await public_order_service.get_currency(db, current_user.tenant_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Metric", "Value"])
    writer.writerow([f"Prepaid Revenue ({currency})", data["prepaid_revenue"] / 100])
    writer.writerow(["Prepaid Orders", data["prepaid_orders"]])
    writer.writerow(
        [f"Cash on Delivery Revenue ({currency})", data["cod_revenue"] / 100]
    )
    writer.writerow(["Cash on Delivery Orders", data["cod_orders"]])
    writer.writerow([f"Card Tips ({currency})", data["prepaid_tips"] / 100])
    writer.writerow([f"Cash Tips ({currency})", data["cod_tips"] / 100])
    writer.writerow(
        [
            f"Total Tips ({currency})",
            (data["prepaid_tips"] + data["cod_tips"]) / 100,
        ]
    )

    output.seek(0)
    filename = f"prepaid_vs_cod_{date_from}_{date_to}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/rejected-orders", response_model=RejectedOrdersReport)
async def get_rejected_orders(
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> RejectedOrdersReport:
    data = await online_report_service.get_rejected_orders(
        db, current_user.tenant_id, date_from, date_to
    )
    return RejectedOrdersReport(**data)


@router.get("/rejected-orders/csv")
async def export_rejected_orders_csv(
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    data = await online_report_service.get_rejected_orders(
        db, current_user.tenant_id, date_from, date_to
    )
    currency = await public_order_service.get_currency(db, current_user.tenant_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["Order Number", "Customer", "Rejected At", "Reason", f"Total ({currency})"]
    )
    for o in data["orders"]:
        writer.writerow(
            [
                o["order_number"],
                o["customer_name"] or "",
                o["rejected_at"],
                o["rejection_reason"],
                o["total"] / 100,
            ]
        )
    writer.writerow([])
    writer.writerow(["Total rejected", data["count"]])
    writer.writerow([f"Total value ({currency})", data["total_value"] / 100])

    output.seek(0)
    filename = f"rejected_orders_{date_from}_{date_to}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/stripe-reconciliation", response_model=StripeReconciliationReport)
async def get_stripe_reconciliation(
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> StripeReconciliationReport:
    data = await online_report_service.get_stripe_reconciliation(
        db, current_user.tenant_id, date_from, date_to
    )
    return StripeReconciliationReport(**data)


@router.get("/stripe-reconciliation/csv")
async def export_stripe_reconciliation_csv(
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    data = await online_report_service.get_stripe_reconciliation(
        db, current_user.tenant_id, date_from, date_to
    )
    currency = await public_order_service.get_currency(db, current_user.tenant_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Order Number",
            "DB Payment Status",
            f"DB Captured ({currency})",
            "Stripe Status",
            f"Stripe Amount Received ({currency})",
            "Matches",
            "Error",
        ]
    )
    for r in data["rows"]:
        writer.writerow(
            [
                r["order_number"],
                r["db_payment_status"],
                r["db_captured_amount"] / 100,
                r["stripe_status"] or "",
                (r["stripe_amount_received"] / 100)
                if r["stripe_amount_received"] is not None
                else "",
                "Yes" if r["matches"] else "No",
                r["error"] or "",
            ]
        )
    writer.writerow([])
    writer.writerow(["Orders checked", data["checked"]])
    writer.writerow(["Mismatches", data["mismatches"]])

    output.seek(0)
    filename = f"stripe_reconciliation_{date_from}_{date_to}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
