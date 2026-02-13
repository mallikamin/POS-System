"""QuickBooks integration endpoints — OAuth, mappings, sync, diagnostics."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_role
from app.config import settings
from app.database import get_db
from app.models.order import Order, OrderItem
from app.models.quickbooks import (
    QBAccountMapping,
    QBConnection,
    QBEntityMapping,
    QBSyncJob,
    QBSyncLog,
)
from app.models.user import User
from app.schemas.quickbooks import (
    QBAccountInfo,
    QBAccountListResponse,
    QBAccountMappingCreate,
    QBAccountMappingResponse,
    QBAccountMappingUpdate,
    QBCallbackRequest,
    QBCompanyInfo,
    QBConnectURL,
    QBConnectionStatus,
    QBDiagnosticApplyResponse,
    QBDiagnosticDecisionsRequest,
    QBDiagnosticReport,
    QBDiagnosticReportSummary,
    QBDiagnosticRequest,
    QBDisconnectResponse,
    QBEntityMappingResponse,
    QBHealthCheckResponse,
    QBManualSyncRequest,
    QBPreviewRequest,
    QBPreviewResponse,
    QBSmartDefaultsRequest,
    QBSmartDefaultsResponse,
    QBSyncJobResponse,
    QBSyncLogResponse,
    QBSyncStats,
    QBSyncTriggerResponse,
    QBTestFixtureInfo,
)
from app.services.quickbooks.client import QBAPIError, QBClient
from app.services.quickbooks.mappings import MappingService
from app.services.quickbooks.oauth import (
    disconnect as qb_disconnect,
    exchange_code_for_tokens,
    generate_auth_url,
    get_connection,
    validate_state,
)
from app.services.quickbooks.diagnostic import DiagnosticService, get_available_fixtures
from app.services.quickbooks.sync import SyncService, build_preview_sales_receipt
from app.services.quickbooks.templates import MAPPING_TEMPLATES

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/integrations/quickbooks",
    tags=["quickbooks"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _require_connection(
    db: AsyncSession, tenant_id: uuid.UUID,
) -> QBConnection:
    """Get active QB connection or raise 404."""
    conn = await get_connection(db, tenant_id)
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active QuickBooks connection. Please connect first.",
        )
    return conn


def _check_qb_configured() -> None:
    """Raise 503 if QB credentials aren't configured."""
    if not settings.qb_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="QuickBooks integration is not configured. Set QB_CLIENT_ID and QB_CLIENT_SECRET.",
        )


# =========================================================================
# OAUTH FLOW
# =========================================================================

@router.get("/connect", response_model=QBConnectURL)
async def connect_quickbooks(
    current_user: User = Depends(require_role("admin")),
) -> QBConnectURL:
    """Generate QuickBooks OAuth authorization URL.

    Admin only. Returns the URL the frontend should redirect/open.
    """
    _check_qb_configured()
    auth_url, state_token = generate_auth_url(current_user.tenant_id, current_user.id)
    return QBConnectURL(auth_url=auth_url, state=state_token)


@router.get("/callback")
async def quickbooks_callback(
    code: str = Query(...),
    state: str = Query(...),
    realmId: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle OAuth callback from Intuit.

    This endpoint is PUBLIC (no JWT) because Intuit redirects the browser
    here directly.  The tenant_id and user context come from the OAuth
    state token that was generated during the /connect call.

    After exchanging tokens, redirects the browser back to the QB admin page.
    """
    from fastapi.responses import RedirectResponse

    _check_qb_configured()

    # Validate CSRF state (contains tenant_id + user_id from /connect)
    state_data = validate_state(state)
    if state_data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state token. Please try connecting again.",
        )

    tenant_id = uuid.UUID(state_data["tenant_id"])
    user_id = uuid.UUID(state_data["user_id"])

    try:
        connection = await exchange_code_for_tokens(
            code=code,
            realm_id=realmId,
            tenant_id=tenant_id,
            user_id=user_id,
            db=db,
        )
    except Exception as exc:
        logger.error("QB OAuth code exchange failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to connect to QuickBooks. Please try again.",
        )

    await db.commit()

    # Redirect browser back to the QB admin page in the POS frontend
    return RedirectResponse(url="/admin/quickbooks?connected=1")


@router.get("/status", response_model=QBConnectionStatus)
async def get_connection_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QBConnectionStatus:
    """Get current QuickBooks connection status for this tenant."""
    conn = await get_connection(db, current_user.tenant_id)
    if conn is None:
        return QBConnectionStatus(is_connected=False)
    return QBConnectionStatus(
        is_connected=conn.is_active,
        realm_id=conn.realm_id,
        company_name=conn.company_name,
        connected_at=conn.connected_at,
        last_sync_at=conn.last_sync_at,
        last_sync_status=conn.last_sync_status,
        token_expires_at=conn.access_token_expires_at,
    )


@router.post("/disconnect", response_model=QBDisconnectResponse)
async def disconnect_quickbooks(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> QBDisconnectResponse:
    """Disconnect QuickBooks — revokes tokens and deactivates connection."""
    success = await qb_disconnect(db, current_user.tenant_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active QuickBooks connection to disconnect.",
        )
    return QBDisconnectResponse(message="QuickBooks disconnected successfully.")


# =========================================================================
# COMPANY INFO
# =========================================================================

@router.get("/company", response_model=QBCompanyInfo)
async def get_company_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QBCompanyInfo:
    """Fetch QuickBooks company info (live from API)."""
    conn = await _require_connection(db, current_user.tenant_id)
    client = QBClient(conn, db)
    try:
        info = await client.get_company_info()
    except QBAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return QBCompanyInfo(
        company_name=info.get("CompanyName", ""),
        legal_name=info.get("LegalName"),
        country=info.get("Country"),
        fiscal_year_start=info.get("FiscalYearStartMonth"),
        industry_type=info.get("IndustryType"),
        currency=info.get("HomeCurrency", {}).get("value") if isinstance(info.get("HomeCurrency"), dict) else None,
    )


# =========================================================================
# ACCOUNT MAPPINGS
# =========================================================================

@router.get("/mappings", response_model=list[QBAccountMappingResponse])
async def list_account_mappings(
    mapping_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[QBAccountMappingResponse]:
    """List all Chart of Accounts mappings."""
    conn = await _require_connection(db, current_user.tenant_id)
    svc = MappingService(conn, db)
    mappings = await svc.list_mappings(mapping_type=mapping_type)
    return [QBAccountMappingResponse.model_validate(m) for m in mappings]


@router.post(
    "/mappings",
    response_model=QBAccountMappingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_account_mapping(
    body: QBAccountMappingCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> QBAccountMappingResponse:
    """Create a new account mapping."""
    conn = await _require_connection(db, current_user.tenant_id)
    svc = MappingService(conn, db)
    mapping = await svc.create_mapping(
        mapping_type=body.mapping_type,
        qb_account_id=body.qb_account_id,
        qb_account_name=body.qb_account_name,
        qb_account_type=body.qb_account_type,
        qb_account_sub_type=body.qb_account_sub_type,
        pos_reference_id=body.pos_reference_id,
        pos_reference_type=body.pos_reference_type,
        pos_reference_name=body.pos_reference_name,
        is_default=body.is_default,
    )
    return QBAccountMappingResponse.model_validate(mapping)


@router.patch("/mappings/{mapping_id}", response_model=QBAccountMappingResponse)
async def update_account_mapping(
    mapping_id: uuid.UUID,
    body: QBAccountMappingUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> QBAccountMappingResponse:
    """Update an account mapping."""
    conn = await _require_connection(db, current_user.tenant_id)
    svc = MappingService(conn, db)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update.",
        )
    try:
        mapping = await svc.update_mapping(mapping_id, **updates)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return QBAccountMappingResponse.model_validate(mapping)


@router.delete("/mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account_mapping(
    mapping_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an account mapping."""
    conn = await _require_connection(db, current_user.tenant_id)
    svc = MappingService(conn, db)
    try:
        deleted = await svc.delete_mapping(mapping_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found.")


@router.post("/mappings/validate")
async def validate_mappings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Validate that all required mappings exist for sync to work."""
    conn = await _require_connection(db, current_user.tenant_id)
    svc = MappingService(conn, db)
    return await svc.validate_mappings()


# =========================================================================
# SMART DEFAULTS
# =========================================================================

@router.get("/mappings/templates")
async def list_mapping_templates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List available mapping templates (Pakistani Restaurant, QSR, Cafe, etc.)."""
    conn = await _require_connection(db, current_user.tenant_id)
    svc = MappingService(conn, db)
    return await svc.get_available_templates()


@router.post("/mappings/smart-defaults", response_model=QBSmartDefaultsResponse)
async def apply_smart_defaults(
    body: QBSmartDefaultsRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> QBSmartDefaultsResponse:
    """Apply a smart default mapping template.

    Auto-creates QB accounts if they don't exist and maps them.
    """
    conn = await _require_connection(db, current_user.tenant_id)
    svc = MappingService(conn, db)
    try:
        result = await svc.apply_smart_defaults(
            template=body.template,
            auto_create_accounts=body.auto_create_accounts,
        )
    except QBAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return QBSmartDefaultsResponse(
        accounts_created=result.get("accounts_created", 0),
        mappings_created=result.get("mappings_created", 0),
        mappings_skipped=result.get("mappings_skipped", 0),
        details=result.get("details", []),
    )


# =========================================================================
# QB ACCOUNT DISCOVERY (for mapping wizard)
# =========================================================================

@router.get("/accounts", response_model=QBAccountListResponse)
async def list_qb_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QBAccountListResponse:
    """Fetch Chart of Accounts from QuickBooks for the mapping wizard."""
    conn = await _require_connection(db, current_user.tenant_id)
    svc = MappingService(conn, db)
    try:
        accounts = await svc.fetch_qb_accounts()
    except QBAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    items = [
        QBAccountInfo(
            id=a.get("id", ""),
            name=a.get("name", ""),
            account_type=a.get("account_type", ""),
            account_sub_type=a.get("account_sub_type"),
            fully_qualified_name=a.get("fully_qualified_name"),
            current_balance=a.get("current_balance"),
            active=a.get("active", True),
        )
        for a in accounts
    ]
    return QBAccountListResponse(accounts=items, total=len(items))


# =========================================================================
# ENTITY MAPPINGS
# =========================================================================

@router.get("/entity-mappings", response_model=list[QBEntityMappingResponse])
async def list_entity_mappings(
    entity_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[QBEntityMappingResponse]:
    """List POS-to-QB entity mappings (menu items, customers, tax codes, etc.)."""
    conn = await _require_connection(db, current_user.tenant_id)
    stmt = select(QBEntityMapping).where(
        QBEntityMapping.tenant_id == current_user.tenant_id,
        QBEntityMapping.connection_id == conn.id,
    )
    if entity_type:
        stmt = stmt.where(QBEntityMapping.entity_type == entity_type)
    stmt = stmt.order_by(QBEntityMapping.entity_type, QBEntityMapping.pos_entity_name)
    result = await db.execute(stmt)
    mappings = list(result.scalars().all())
    return [QBEntityMappingResponse.model_validate(m) for m in mappings]


# =========================================================================
# SYNC OPERATIONS
# =========================================================================

@router.post("/sync", response_model=QBSyncTriggerResponse)
async def trigger_manual_sync(
    body: QBManualSyncRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> QBSyncTriggerResponse:
    """Manually trigger a sync operation."""
    conn = await _require_connection(db, current_user.tenant_id)
    sync_svc = SyncService(conn, db)
    batch_id = uuid.uuid4()

    jobs_created = 0

    if body.sync_type == "full_sync":
        result = await sync_svc.run_full_sync(batch_id=batch_id)
        return QBSyncTriggerResponse(
            jobs_created=result.get("total_synced", 0),
            message="Full sync completed.",
            batch_id=batch_id,
        )

    if body.sync_type == "daily_summary":
        date = body.date_from or datetime.now(timezone.utc)
        result = await sync_svc.run_daily_close(date)
        return QBSyncTriggerResponse(
            jobs_created=2 if result else 0,
            message="Daily close completed." if result else "Daily close failed.",
            batch_id=batch_id,
        )

    if body.sync_type == "sync_items":
        from app.models.menu import MenuItem
        stmt = select(MenuItem.id).where(MenuItem.tenant_id == current_user.tenant_id)
        if body.entity_ids:
            stmt = stmt.where(MenuItem.id.in_(body.entity_ids))
        result = await db.execute(stmt)
        item_ids = list(result.scalars().all())
        for item_id in item_ids:
            job = await sync_svc.enqueue_job("sync_menu_item", "menu_item", item_id, priority=7)
            if job is not None:
                jobs_created += 1

    elif body.sync_type == "sync_customers":
        # Sync all customers — query them and enqueue individual jobs with names
        from app.models.order import Order as OrderModel
        cust_stmt = (
            select(OrderModel.customer_name, OrderModel.customer_phone)
            .where(
                OrderModel.tenant_id == current_user.tenant_id,
                OrderModel.customer_name.isnot(None),
            )
            .distinct()
        )
        cust_result = await db.execute(cust_stmt)
        for row in cust_result.all():
            name = row[0]
            phone = row[1]
            if name:
                job = await sync_svc.enqueue_job(
                    "sync_customer", "customer", priority=7,
                    payload={"name": name, "phone": phone},
                )
                if job is not None:
                    jobs_created += 1

    elif body.sync_type == "setup_tax_codes":
        result = await sync_svc.setup_tax_code_mapping()
        return QBSyncTriggerResponse(
            jobs_created=len(result),
            message=f"Tax code mapping setup: {result}",
            batch_id=batch_id,
        )

    elif body.sync_type == "sync_orders":
        from app.models.order import Order
        stmt = select(Order.id).where(
            Order.tenant_id == current_user.tenant_id,
            Order.status == "completed",
        )
        if body.entity_ids:
            stmt = stmt.where(Order.id.in_(body.entity_ids))
        if body.date_from:
            stmt = stmt.where(Order.created_at >= body.date_from)
        if body.date_to:
            # Add 1 day to include the entire end day (date_to at midnight excludes that day)
            stmt = stmt.where(Order.created_at < body.date_to + timedelta(days=1))
        result = await db.execute(stmt)
        order_ids = list(result.scalars().all())
        for order_id in order_ids:
            job = await sync_svc.enqueue_job("create_sales_receipt", "order", order_id, priority=3)
            if job is not None:
                jobs_created += 1

    # Process queued jobs immediately
    if jobs_created > 0:
        processed = await sync_svc.process_pending_jobs(batch_size=jobs_created)

    return QBSyncTriggerResponse(
        jobs_created=jobs_created,
        message=f"Queued {jobs_created} sync jobs.",
        batch_id=batch_id,
    )


# =========================================================================
# SYNC STATUS & LOGS
# =========================================================================

@router.get("/sync/stats", response_model=QBSyncStats)
async def get_sync_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QBSyncStats:
    """Get aggregated sync statistics."""
    conn = await _require_connection(db, current_user.tenant_id)
    tid = current_user.tenant_id
    cid = conn.id

    # Total synced (completed logs)
    total_r = await db.execute(
        select(func.count(QBSyncLog.id)).where(
            QBSyncLog.tenant_id == tid,
            QBSyncLog.connection_id == cid,
            QBSyncLog.status == "success",
        )
    )
    total_synced = total_r.scalar_one()

    # Last 24h synced
    cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
    last_24h_r = await db.execute(
        select(func.count(QBSyncLog.id)).where(
            QBSyncLog.tenant_id == tid,
            QBSyncLog.connection_id == cid,
            QBSyncLog.status == "success",
            QBSyncLog.created_at >= cutoff,
        )
    )
    last_24h_synced = last_24h_r.scalar_one()

    # Last 24h failed
    last_24h_f = await db.execute(
        select(func.count(QBSyncLog.id)).where(
            QBSyncLog.tenant_id == tid,
            QBSyncLog.connection_id == cid,
            QBSyncLog.status == "failed",
            QBSyncLog.created_at >= cutoff,
        )
    )
    last_24h_failed = last_24h_f.scalar_one()

    # Pending jobs
    pending_r = await db.execute(
        select(func.count(QBSyncJob.id)).where(
            QBSyncJob.tenant_id == tid,
            QBSyncJob.connection_id == cid,
            QBSyncJob.status == "pending",
        )
    )
    pending_jobs = pending_r.scalar_one()

    # Failed jobs
    failed_r = await db.execute(
        select(func.count(QBSyncJob.id)).where(
            QBSyncJob.tenant_id == tid,
            QBSyncJob.connection_id == cid,
            QBSyncJob.status == "failed",
        )
    )
    failed_jobs = failed_r.scalar_one()

    # Dead letter jobs
    dead_r = await db.execute(
        select(func.count(QBSyncJob.id)).where(
            QBSyncJob.tenant_id == tid,
            QBSyncJob.connection_id == cid,
            QBSyncJob.status == "dead_letter",
        )
    )
    dead_letter_jobs = dead_r.scalar_one()

    # Sync by type
    type_r = await db.execute(
        select(QBSyncLog.sync_type, func.count(QBSyncLog.id)).where(
            QBSyncLog.tenant_id == tid,
            QBSyncLog.connection_id == cid,
            QBSyncLog.status == "success",
        ).group_by(QBSyncLog.sync_type)
    )
    sync_by_type = {row[0]: row[1] for row in type_r.all()}

    return QBSyncStats(
        total_synced=total_synced,
        last_24h_synced=last_24h_synced,
        last_24h_failed=last_24h_failed,
        pending_jobs=pending_jobs,
        failed_jobs=failed_jobs,
        dead_letter_jobs=dead_letter_jobs,
        last_sync_at=conn.last_sync_at,
        sync_by_type=sync_by_type,
    )


@router.get("/sync/jobs", response_model=list[QBSyncJobResponse])
async def list_sync_jobs(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[QBSyncJobResponse]:
    """List sync queue jobs."""
    conn = await _require_connection(db, current_user.tenant_id)
    stmt = select(QBSyncJob).where(
        QBSyncJob.tenant_id == current_user.tenant_id,
        QBSyncJob.connection_id == conn.id,
    )
    if status_filter:
        stmt = stmt.where(QBSyncJob.status == status_filter)
    stmt = stmt.order_by(QBSyncJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    jobs = list(result.scalars().all())
    return [QBSyncJobResponse.model_validate(j) for j in jobs]


@router.get("/sync/log", response_model=list[QBSyncLogResponse])
async def list_sync_log(
    sync_type: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[QBSyncLogResponse]:
    """List sync audit log entries."""
    conn = await _require_connection(db, current_user.tenant_id)
    stmt = select(QBSyncLog).where(
        QBSyncLog.tenant_id == current_user.tenant_id,
        QBSyncLog.connection_id == conn.id,
    )
    if sync_type:
        stmt = stmt.where(QBSyncLog.sync_type == sync_type)
    if status_filter:
        stmt = stmt.where(QBSyncLog.status == status_filter)
    stmt = stmt.order_by(QBSyncLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    logs = list(result.scalars().all())
    return [QBSyncLogResponse.model_validate(lg) for lg in logs]


# =========================================================================
# RETRY / DEAD LETTER
# =========================================================================

@router.post("/sync/jobs/{job_id}/retry", response_model=QBSyncJobResponse)
async def retry_sync_job(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> QBSyncJobResponse:
    """Retry a failed or dead-letter sync job."""
    conn = await _require_connection(db, current_user.tenant_id)
    result = await db.execute(
        select(QBSyncJob).where(
            QBSyncJob.id == job_id,
            QBSyncJob.tenant_id == current_user.tenant_id,
            QBSyncJob.connection_id == conn.id,
        )
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync job not found.")
    if job.status not in ("failed", "dead_letter"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry job with status '{job.status}'.",
        )

    job.status = "pending"
    job.retry_count = 0
    job.error_message = None
    job.error_detail = None
    job.next_retry_at = None
    await db.flush()

    # Process immediately
    sync_svc = SyncService(conn, db)
    await sync_svc.process_job(job)

    await db.refresh(job)
    return QBSyncJobResponse.model_validate(job)


# =========================================================================
# PREVIEW / SIMULATION (no QB connection required)
# =========================================================================

@router.get("/templates-preview")
async def list_templates_preview(
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """List available QB mapping templates — no connection required.

    Returns all 40 templates with their full mapping definitions.
    Used for browsing / simulation mode before OAuth is configured.
    """
    templates = []
    for key, data in MAPPING_TEMPLATES.items():
        templates.append({
            "template_name": key,
            "name": data["name"],
            "description": data["description"],
            "mapping_count": len(data["mappings"]),
            "mappings": data["mappings"],
        })
    return templates


@router.post("/preview/sales-receipt", response_model=QBPreviewResponse)
async def preview_sales_receipt(
    body: QBPreviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QBPreviewResponse:
    """Preview a QB Sales Receipt payload for a given order + template.

    Does NOT require a QuickBooks connection. Uses simulated account IDs
    from the selected template to generate the exact payload structure
    that would be sent to QuickBooks.
    """
    # Validate template
    template = MAPPING_TEMPLATES.get(body.template_name)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{body.template_name}' not found. "
            f"Use GET /templates-preview to list available templates.",
        )

    # Load order with relations
    result = await db.execute(
        select(Order)
        .where(
            Order.id == body.order_id,
            Order.tenant_id == current_user.tenant_id,
        )
        .options(
            selectinload(Order.items).selectinload(OrderItem.modifiers),
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )

    # Build preview payload
    payload = await build_preview_sales_receipt(order, template["mappings"])

    return QBPreviewResponse(
        template_name=body.template_name,
        template_display_name=template["name"],
        order_number=order.order_number,
        order_type=order.order_type,
        qb_entity_type="SalesReceipt",
        payload=payload,
        mappings_used=template["mappings"],
    )


# =========================================================================
# DIAGNOSTIC & ONBOARDING TOOL
# =========================================================================

@router.get("/diagnostic/fixtures", response_model=list[QBTestFixtureInfo])
async def list_test_fixtures(
    current_user: User = Depends(get_current_user),
) -> list[QBTestFixtureInfo]:
    """List available test fixtures (mock QB Chart of Accounts).

    Used for testing the diagnostic tool without a live QB connection.
    """
    return [QBTestFixtureInfo(**f) for f in get_available_fixtures()]


@router.post("/diagnostic/run", response_model=QBDiagnosticReport)
async def run_diagnostic(
    body: QBDiagnosticRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QBDiagnosticReport:
    """Run diagnostic gap analysis between a template and QB accounts.

    Either connects to live QB to fetch accounts, or uses a test fixture
    for offline testing. Returns a full report with match scores,
    candidates, and unmapped accounts.
    """
    # Get connection (optional — not required for fixture mode)
    conn = None
    if not body.fixture_name:
        conn = await get_connection(db, current_user.tenant_id)
        if conn is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No QB connection and no fixture specified. "
                "Connect to QB first or specify a fixture_name for testing.",
            )

    svc = DiagnosticService(conn, db)
    try:
        report = await svc.run_diagnostic(
            template_key=body.template_key,
            fixture_name=body.fixture_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return QBDiagnosticReport(**report)


@router.get("/diagnostic/reports", response_model=list[QBDiagnosticReportSummary])
async def list_diagnostic_reports(
    current_user: User = Depends(get_current_user),
) -> list[QBDiagnosticReportSummary]:
    """List all diagnostic reports (summaries only)."""
    reports = DiagnosticService.list_reports()
    return [QBDiagnosticReportSummary(**r) for r in reports]


@router.get("/diagnostic/reports/{report_id}", response_model=QBDiagnosticReport)
async def get_diagnostic_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
) -> QBDiagnosticReport:
    """Retrieve a specific diagnostic report by ID."""
    report = DiagnosticService.get_report(report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic report '{report_id}' not found.",
        )
    return QBDiagnosticReport(**report)


@router.post("/diagnostic/reports/{report_id}/decisions", response_model=QBDiagnosticReport)
async def update_diagnostic_decisions(
    report_id: str,
    body: QBDiagnosticDecisionsRequest,
    current_user: User = Depends(require_role("admin")),
) -> QBDiagnosticReport:
    """Update admin decisions on a diagnostic report.

    Each decision specifies: use_existing (map to QB account),
    create_new (create account in QB), or skip.
    """
    try:
        report = DiagnosticService.update_decisions(
            report_id,
            [d.model_dump() for d in body.decisions],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return QBDiagnosticReport(**report)


@router.post(
    "/diagnostic/reports/{report_id}/apply",
    response_model=QBDiagnosticApplyResponse,
)
async def apply_diagnostic_decisions(
    report_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> QBDiagnosticApplyResponse:
    """Apply diagnostic decisions — create QB accounts and mappings.

    All items must have a decision (use_existing/create_new/skip)
    before this endpoint will process the report.
    """
    conn = await _require_connection(db, current_user.tenant_id)
    svc = DiagnosticService(conn, db)
    try:
        result = await svc.apply_decisions(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except QBAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    await db.commit()
    return QBDiagnosticApplyResponse(**result)


@router.get("/diagnostic/health-check", response_model=QBHealthCheckResponse)
async def run_health_check(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QBHealthCheckResponse:
    """Check existing mappings against live QB accounts.

    Detects renamed, deactivated, and deleted accounts.
    Returns health grade: A (all OK), B (warnings), C (critical), F (broken).
    """
    conn = await _require_connection(db, current_user.tenant_id)
    svc = DiagnosticService(conn, db)
    try:
        result = await svc.health_check()
    except QBAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return QBHealthCheckResponse(**result)


@router.get("/diagnostic/reports/{report_id}/export/pdf")
async def export_diagnostic_pdf(
    report_id: str,
    current_user: User = Depends(get_current_user),
):
    """Export diagnostic report as a professional PDF.

    Returns a downloadable PDF with cover page, gap analysis table,
    unmapped accounts, and recommendations.
    """
    report = DiagnosticService.get_report(report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic report '{report_id}' not found.",
        )

    from app.services.quickbooks.export_pdf import generate_diagnostic_pdf

    pdf_bytes = generate_diagnostic_pdf(report)
    filename = f"qb_diagnostic_{report['template_key']}_{report_id[:8]}.pdf"

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/diagnostic/reports/{report_id}/export/excel")
async def export_diagnostic_excel(
    report_id: str,
    current_user: User = Depends(get_current_user),
):
    """Export diagnostic report as an Excel workbook.

    3 sheets: Gap Analysis, Unmapped QB Accounts, Summary & Recommendations.
    """
    report = DiagnosticService.get_report(report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic report '{report_id}' not found.",
        )

    from app.services.quickbooks.export_excel import generate_diagnostic_excel

    excel_bytes = generate_diagnostic_excel(report)
    filename = f"qb_diagnostic_{report['template_key']}_{report_id[:8]}.xlsx"

    return StreamingResponse(
        iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
