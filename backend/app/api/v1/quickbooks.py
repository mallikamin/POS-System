"""QuickBooks integration endpoints (Attempt 2 — client-centric, no templates).

Streamlined flow:
  1. OAuth connect/disconnect
  2. Auto-match POS needs against partner's QB Chart of Accounts
  3. Review matches, customize decisions
  4. Apply decisions (create mappings + QB accounts)
  5. Sync operations + health check
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.config import settings
from app.database import get_db
from app.models.order import Order
from app.models.quickbooks import (
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
    QBCompanyInfo,
    QBConnectURL,
    QBConnectionStatus,
    QBDecisionsRequest,
    QBDisconnectResponse,
    QBEntityMappingResponse,
    QBHealthCheckResponse,
    QBManualSyncRequest,
    QBMatchApplyResponse,
    QBMatchResult,
    QBMatchResultSummary,
    QBSnapshotCreateResponse,
    QBSnapshotDetail,
    QBSnapshotSummary,
    QBSyncJobResponse,
    QBSyncLogResponse,
    QBSyncStats,
    QBSyncTriggerResponse,
)
from app.services.quickbooks.client import QBAPIError, QBClient
from app.services.quickbooks.diagnostic import MatchingService
from app.services.quickbooks.mappings import MappingService
from app.services.quickbooks.oauth import (
    disconnect as qb_disconnect,
    exchange_code_for_tokens,
    generate_auth_url,
    get_connection,
    validate_state,
)
from app.services.quickbooks.pos_needs import get_all_needs_as_dicts
from app.services.quickbooks.snapshot import SnapshotService
from app.services.quickbooks.sync import SyncService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/integrations/quickbooks",
    tags=["quickbooks"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _require_connection(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> QBConnection:
    conn = await get_connection(db, tenant_id)
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active QuickBooks connection. Please connect first.",
        )
    return conn


def _check_qb_configured() -> None:
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
    """Generate QuickBooks OAuth authorization URL."""
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
    """Handle OAuth callback from Intuit (public — no JWT)."""
    from fastapi.responses import RedirectResponse

    _check_qb_configured()

    state_data = validate_state(state)
    if state_data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state token.",
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
        logger.error("QB OAuth exchange failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to connect to QuickBooks.",
        )

    # Auto-fetch CoA and create backup + working copy snapshots
    try:
        snapshot_svc = SnapshotService(connection, db)
        snap_result = await snapshot_svc.create_initial_snapshots()
        logger.info(
            "Auto-created CoA snapshots on connect: %d accounts, v%d",
            snap_result["account_count"],
            snap_result["version"],
        )
    except Exception as exc:
        # Non-fatal: connection still works, snapshots can be created later
        logger.warning(
            "Failed to auto-create CoA snapshots on connect: %s",
            exc,
            exc_info=True,
        )

    await db.commit()
    return RedirectResponse(url="/admin/quickbooks?connected=1")


@router.get("/status", response_model=QBConnectionStatus)
async def get_connection_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QBConnectionStatus:
    """Get current QB connection status."""
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
    """Disconnect QB — revoke tokens and deactivate."""
    success = await qb_disconnect(db, current_user.tenant_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No active connection."
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
    """Fetch QB company info."""
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
        currency=info.get("HomeCurrency", {}).get("value")
        if isinstance(info.get("HomeCurrency"), dict)
        else None,
    )


# =========================================================================
# POS ACCOUNTING NEEDS (what the system requires)
# =========================================================================


@router.get("/needs")
async def list_pos_needs(
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """List all POS accounting needs — what the system requires mapped to QB."""
    return get_all_needs_as_dicts()


# =========================================================================
# ACCOUNT MATCHING (the core of Attempt 2)
# =========================================================================


@router.post("/match", response_model=QBMatchResult)
async def run_account_matching(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QBMatchResult:
    """Match POS needs against partner's QB Chart of Accounts.

    Uses the working copy from CoA snapshots if available.
    Falls back to live QB fetch if no snapshot exists.
    """
    conn = await _require_connection(db, current_user.tenant_id)

    # Try to use working copy from snapshot (no live QB call needed)
    snapshot_svc = SnapshotService(conn, db)
    working_accounts = await snapshot_svc.get_working_copy_accounts()

    svc = MatchingService(conn, db)
    try:
        result = await svc.run_matching(qb_accounts=working_accounts)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return QBMatchResult(**result)


@router.get("/match/results", response_model=list[QBMatchResultSummary])
async def list_match_results(
    current_user: User = Depends(get_current_user),
) -> list[QBMatchResultSummary]:
    """List previous match results."""
    return [QBMatchResultSummary(**r) for r in MatchingService.list_results()]


@router.get("/match/results/{result_id}", response_model=QBMatchResult)
async def get_match_result(
    result_id: str,
    current_user: User = Depends(get_current_user),
) -> QBMatchResult:
    """Get a specific match result."""
    result = MatchingService.get_result(result_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Match result not found."
        )
    return QBMatchResult(**result)


@router.post("/match/results/{result_id}/decisions", response_model=QBMatchResult)
async def update_match_decisions(
    result_id: str,
    body: QBDecisionsRequest,
    current_user: User = Depends(require_role("admin")),
) -> QBMatchResult:
    """Update admin decisions on match results."""
    try:
        result = MatchingService.update_decisions(
            result_id,
            [d.model_dump() for d in body.decisions],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return QBMatchResult(**result)


@router.post("/match/results/{result_id}/apply", response_model=QBMatchApplyResponse)
async def apply_match_decisions(
    result_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> QBMatchApplyResponse:
    """Apply decisions — create QB accounts + POS mappings."""
    conn = await _require_connection(db, current_user.tenant_id)
    svc = MatchingService(conn, db)
    try:
        result = await svc.apply_decisions(result_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except QBAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    await db.commit()
    return QBMatchApplyResponse(**result)


# =========================================================================
# COA SNAPSHOTS (backup + working copy)
# =========================================================================


@router.get("/snapshots", response_model=list[QBSnapshotSummary])
async def list_snapshots(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[QBSnapshotSummary]:
    """List all CoA snapshots for this connection."""
    conn = await _require_connection(db, current_user.tenant_id)
    svc = SnapshotService(conn, db)
    snapshots = await svc.list_snapshots()
    return [QBSnapshotSummary.model_validate(s) for s in snapshots]


@router.get("/snapshots/latest")
async def get_latest_snapshots(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the latest backup and working copy summaries."""
    conn = await _require_connection(db, current_user.tenant_id)
    svc = SnapshotService(conn, db)
    backup = await svc.get_latest_backup()
    working = await svc.get_latest_working_copy()
    return {
        "backup": QBSnapshotSummary.model_validate(backup) if backup else None,
        "working_copy": QBSnapshotSummary.model_validate(working) if working else None,
    }


@router.get("/snapshots/{snapshot_id}", response_model=QBSnapshotDetail)
async def get_snapshot_detail(
    snapshot_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QBSnapshotDetail:
    """Get full snapshot detail including account data."""
    conn = await _require_connection(db, current_user.tenant_id)
    svc = SnapshotService(conn, db)
    snapshot = await svc.get_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found."
        )
    return QBSnapshotDetail.model_validate(snapshot)


@router.get("/snapshots/{snapshot_id}/export")
async def export_snapshot_json(
    snapshot_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export snapshot as downloadable JSON file (for git archival)."""
    from fastapi.responses import Response

    conn = await _require_connection(db, current_user.tenant_id)
    svc = SnapshotService(conn, db)
    snapshot = await svc.get_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found."
        )

    json_str = svc.export_as_json(snapshot)
    filename = f"coa_backup_{snapshot.qb_realm_id}_v{snapshot.version}_{snapshot.snapshot_type}.json"
    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/snapshots/refresh", response_model=QBSnapshotCreateResponse)
async def refresh_snapshots(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> QBSnapshotCreateResponse:
    """Re-fetch CoA from QB and create a new versioned backup + working copy pair."""
    conn = await _require_connection(db, current_user.tenant_id)
    svc = SnapshotService(conn, db)
    try:
        result = await svc.refresh_snapshots()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    await db.commit()
    return QBSnapshotCreateResponse(**result)


# =========================================================================
# HEALTH CHECK
# =========================================================================


@router.get("/health-check", response_model=QBHealthCheckResponse)
async def run_health_check(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QBHealthCheckResponse:
    """Check existing mappings against live QB accounts."""
    conn = await _require_connection(db, current_user.tenant_id)
    svc = MatchingService(conn, db)
    try:
        result = await svc.health_check()
    except (QBAPIError, RuntimeError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return QBHealthCheckResponse(**result)


# =========================================================================
# ACCOUNT MAPPINGS (CRUD)
# =========================================================================


@router.get("/mappings", response_model=list[QBAccountMappingResponse])
async def list_account_mappings(
    mapping_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[QBAccountMappingResponse]:
    """List all account mappings."""
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
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update."
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
        await svc.delete_mapping(mapping_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/mappings/validate")
async def validate_mappings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Validate required mappings exist."""
    conn = await _require_connection(db, current_user.tenant_id)
    svc = MappingService(conn, db)
    return await svc.validate_mappings()


# =========================================================================
# QB ACCOUNT DISCOVERY
# =========================================================================


@router.get("/accounts", response_model=QBAccountListResponse)
async def list_qb_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QBAccountListResponse:
    """Fetch Chart of Accounts from QB."""
    conn = await _require_connection(db, current_user.tenant_id)
    svc = MappingService(conn, db)
    try:
        accounts = await svc.fetch_qb_accounts()
    except (QBAPIError, RuntimeError) as exc:
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
    """List POS-to-QB entity mappings."""
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
        for item_id in result.scalars().all():
            job = await sync_svc.enqueue_job(
                "sync_menu_item", "menu_item", item_id, priority=7
            )
            if job is not None:
                jobs_created += 1

    elif body.sync_type == "sync_customers":
        from app.models.order import Order as OrderModel

        cust_stmt = (
            select(OrderModel.customer_name, OrderModel.customer_phone)
            .where(
                OrderModel.tenant_id == current_user.tenant_id,
                OrderModel.customer_name.isnot(None),
            )
            .distinct()
        )
        for row in (await db.execute(cust_stmt)).all():
            if row[0]:
                job = await sync_svc.enqueue_job(
                    "sync_customer",
                    "customer",
                    priority=7,
                    payload={"name": row[0], "phone": row[1]},
                )
                if job is not None:
                    jobs_created += 1

    elif body.sync_type == "setup_tax_codes":
        result = await sync_svc.setup_tax_code_mapping()
        return QBSyncTriggerResponse(
            jobs_created=len(result),
            message=f"Tax codes set up: {result}",
            batch_id=batch_id,
        )

    elif body.sync_type == "sync_orders":
        stmt = select(Order.id).where(
            Order.tenant_id == current_user.tenant_id,
            Order.status == "completed",
        )
        if body.entity_ids:
            stmt = stmt.where(Order.id.in_(body.entity_ids))
        if body.date_from:
            stmt = stmt.where(Order.created_at >= body.date_from)
        if body.date_to:
            stmt = stmt.where(Order.created_at < body.date_to + timedelta(days=1))
        for order_id in (await db.execute(stmt)).scalars().all():
            job = await sync_svc.enqueue_job(
                "create_sales_receipt", "order", order_id, priority=3
            )
            if job is not None:
                jobs_created += 1

    if jobs_created > 0:
        await sync_svc.process_pending_jobs(batch_size=jobs_created)

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
    """Get sync statistics."""
    conn = await _require_connection(db, current_user.tenant_id)
    tid, cid = current_user.tenant_id, conn.id

    total_r = await db.execute(
        select(func.count(QBSyncLog.id)).where(
            QBSyncLog.tenant_id == tid,
            QBSyncLog.connection_id == cid,
            QBSyncLog.status == "success",
        )
    )
    cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
    last_24h_r = await db.execute(
        select(func.count(QBSyncLog.id)).where(
            QBSyncLog.tenant_id == tid,
            QBSyncLog.connection_id == cid,
            QBSyncLog.status == "success",
            QBSyncLog.created_at >= cutoff,
        )
    )
    last_24h_f = await db.execute(
        select(func.count(QBSyncLog.id)).where(
            QBSyncLog.tenant_id == tid,
            QBSyncLog.connection_id == cid,
            QBSyncLog.status == "failed",
            QBSyncLog.created_at >= cutoff,
        )
    )
    pending_r = await db.execute(
        select(func.count(QBSyncJob.id)).where(
            QBSyncJob.tenant_id == tid,
            QBSyncJob.connection_id == cid,
            QBSyncJob.status == "pending",
        )
    )
    failed_r = await db.execute(
        select(func.count(QBSyncJob.id)).where(
            QBSyncJob.tenant_id == tid,
            QBSyncJob.connection_id == cid,
            QBSyncJob.status == "failed",
        )
    )
    dead_r = await db.execute(
        select(func.count(QBSyncJob.id)).where(
            QBSyncJob.tenant_id == tid,
            QBSyncJob.connection_id == cid,
            QBSyncJob.status == "dead_letter",
        )
    )
    type_r = await db.execute(
        select(QBSyncLog.sync_type, func.count(QBSyncLog.id))
        .where(
            QBSyncLog.tenant_id == tid,
            QBSyncLog.connection_id == cid,
            QBSyncLog.status == "success",
        )
        .group_by(QBSyncLog.sync_type)
    )

    return QBSyncStats(
        total_synced=total_r.scalar_one(),
        last_24h_synced=last_24h_r.scalar_one(),
        last_24h_failed=last_24h_f.scalar_one(),
        pending_jobs=pending_r.scalar_one(),
        failed_jobs=failed_r.scalar_one(),
        dead_letter_jobs=dead_r.scalar_one(),
        last_sync_at=conn.last_sync_at,
        sync_by_type={row[0]: row[1] for row in type_r.all()},
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
    stmt = (
        stmt.order_by(QBSyncJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    return [QBSyncJobResponse.model_validate(j) for j in result.scalars().all()]


@router.get("/sync/log", response_model=list[QBSyncLogResponse])
async def list_sync_log(
    sync_type: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[QBSyncLogResponse]:
    """List sync audit log."""
    conn = await _require_connection(db, current_user.tenant_id)
    stmt = select(QBSyncLog).where(
        QBSyncLog.tenant_id == current_user.tenant_id,
        QBSyncLog.connection_id == conn.id,
    )
    if sync_type:
        stmt = stmt.where(QBSyncLog.sync_type == sync_type)
    if status_filter:
        stmt = stmt.where(QBSyncLog.status == status_filter)
    stmt = (
        stmt.order_by(QBSyncLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    return [QBSyncLogResponse.model_validate(lg) for lg in result.scalars().all()]


@router.post("/sync/jobs/{job_id}/retry", response_model=QBSyncJobResponse)
async def retry_sync_job(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> QBSyncJobResponse:
    """Retry a failed sync job."""
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )
    if job.status not in ("failed", "dead_letter"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry '{job.status}' job.",
        )

    job.status = "pending"
    job.retry_count = 0
    job.error_message = None
    job.error_detail = None
    job.next_retry_at = None
    await db.flush()

    sync_svc = SyncService(conn, db)
    await sync_svc.process_job(job)
    await db.refresh(job)
    return QBSyncJobResponse.model_validate(job)


# ---------------------------------------------------------------------------
# QuickBooks Desktop Connection Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/desktop/connect",
    response_model=QBConnectionStatus,
    dependencies=[Depends(require_role("admin"))],
)
async def connect_qb_desktop(
    password: str = Query(..., description="QBWC password (user sets once)"),
    company_name: str = Query(..., description="QB company name"),
    qb_version: str = Query(None, description='QB Desktop version, e.g. "Enterprise 2024"'),
    company_file_path: str = Query(None, description="QB company file path (optional)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QBConnectionStatus:
    """Create a QuickBooks Desktop connection.

    This generates QBWC credentials and stores them encrypted. The user must then:
    1. Download the QWC file (GET /desktop/qwc endpoint)
    2. Install QBWC from Intuit (https://qbwc.qbn.intuit.com/)
    3. Import the QWC file into QBWC
    4. QBWC will automatically start syncing every 15 minutes

    NOTE: Only one active QB connection (Online OR Desktop) per tenant.
    """
    from app.services.quickbooks.oauth import encrypt_token

    logger.info(
        "Creating QB Desktop connection for tenant=%s user=%s",
        current_user.tenant_id,
        current_user.id,
    )

    # Check if connection already exists
    existing_conn = await get_connection(db, current_user.tenant_id)
    if existing_conn:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"QuickBooks connection already exists (type: {existing_conn.connection_type}). "
            "Disconnect first to create a new connection.",
        )

    # Generate QBWC username (unique per tenant)
    qbwc_username = f"tenant_{str(current_user.tenant_id)[:8]}"

    # Create connection
    connection = QBConnection(
        tenant_id=current_user.tenant_id,
        connection_type="desktop",
        company_name=company_name,
        qbwc_username=qbwc_username,
        qbwc_password_encrypted=encrypt_token(password),
        qb_desktop_version=qb_version,
        company_file_path=company_file_path,
        is_active=True,
        connected_by=current_user.id,
        connected_at=datetime.now(timezone.utc),
    )
    db.add(connection)
    await db.flush()

    logger.info(
        "QB Desktop connection created: id=%s username=%s",
        connection.id,
        qbwc_username,
    )

    return QBConnectionStatus(
        is_connected=True,
        connection_type="desktop",
        company_name=company_name,
        connected_at=connection.connected_at.isoformat(),
        qbwc_username=qbwc_username,
        qb_desktop_version=qb_version,
        last_sync_at=None,
        last_sync_status=None,
    )


@router.get(
    "/desktop/qwc",
    dependencies=[Depends(require_role("admin"))],
    response_class=Response,
)
async def download_qwc_file(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download QWC file for QuickBooks Web Connector.

    User must:
    1. Download QBWC from Intuit: https://qbwc.qbn.intuit.com/
    2. Install QBWC on the PC running QB Desktop
    3. Import this QWC file into QBWC (File → Add an Application)
    4. QBWC will prompt for password (same as set during connection)
    5. QBWC will automatically poll every 15 minutes
    """
    from fastapi.responses import Response as FastAPIResponse

    from app.services.quickbooks.qwc import generate_qwc_file, generate_qwc_filename

    conn = await _require_connection(db, current_user.tenant_id)

    if conn.connection_type != "desktop":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QWC file is only for QuickBooks Desktop connections.",
        )

    if not conn.qbwc_username or not conn.qbwc_password_encrypted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Desktop connection is missing QBWC credentials.",
        )

    # Decrypt password for QWC file (QBWC needs plain text password)
    from app.services.quickbooks.oauth import decrypt_token

    try:
        password = decrypt_token(conn.qbwc_password_encrypted)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt QBWC password.",
        )

    # Generate QWC XML
    qwc_xml = generate_qwc_file(
        tenant_id=conn.tenant_id,
        connection_id=conn.id,
        username=conn.qbwc_username,
        password=password,
        server_url=f"{settings.BACKEND_URL}/api/v1/qbwc/",
        app_name="Sitara POS",
        poll_interval_minutes=15,
    )

    # Generate filename
    filename = generate_qwc_filename(conn.company_name, conn.id)

    logger.info(
        "Generated QWC file for tenant=%s connection=%s",
        current_user.tenant_id,
        conn.id,
    )

    return FastAPIResponse(
        content=qwc_xml,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get(
    "/desktop/status",
    response_model=dict,
    dependencies=[Depends(require_role("admin"))],
)
async def get_desktop_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get QuickBooks Desktop connection status and sync queue info."""
    conn = await _require_connection(db, current_user.tenant_id)

    if conn.connection_type != "desktop":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is only for Desktop connections.",
        )

    # Count pending sync jobs
    pending_result = await db.execute(
        select(func.count(QBSyncJob.id)).where(
            QBSyncJob.connection_id == conn.id,
            QBSyncJob.status == "pending",
        )
    )
    pending_count = pending_result.scalar() or 0

    return {
        "connection_id": str(conn.id),
        "company_name": conn.company_name,
        "qb_version": conn.qb_desktop_version,
        "last_qbwc_poll": (
            conn.last_qbwc_poll_at.isoformat() if conn.last_qbwc_poll_at else None
        ),
        "pending_sync_jobs": pending_count,
        "is_active": conn.is_active,
    }
