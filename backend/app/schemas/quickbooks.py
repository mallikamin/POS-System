"""Pydantic v2 schemas for QuickBooks Online integration (Attempt 2).

Client-centric approach — no templates. POS declares what it needs,
fuzzy-matches against partner's actual QB Chart of Accounts.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# OAuth Flow
# ---------------------------------------------------------------------------


class QBConnectURL(BaseModel):
    auth_url: str
    state: str


class QBConnectionStatus(BaseModel):
    is_connected: bool
    connection_type: str | None = None  # "online" | "desktop"
    realm_id: str | None = None  # QB Online only
    company_name: str | None = None
    connected_at: datetime | None | str = None
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    token_expires_at: datetime | None = None  # QB Online only
    # QB Desktop fields
    qbwc_username: str | None = None
    qb_desktop_version: str | None = None
    last_qbwc_poll_at: datetime | None = None
    model_config = {"from_attributes": True}


class QBDisconnectResponse(BaseModel):
    message: str
    realm_id: str | None = None


class QBCompanyInfo(BaseModel):
    company_name: str
    legal_name: str | None = None
    country: str | None = None
    fiscal_year_start: str | None = None
    industry_type: str | None = None
    currency: str | None = None


# ---------------------------------------------------------------------------
# Account Mappings
# ---------------------------------------------------------------------------


class QBAccountMappingBase(BaseModel):
    mapping_type: str = Field(..., min_length=1, max_length=50)
    pos_reference_id: uuid.UUID | None = None
    pos_reference_type: str | None = Field(None, max_length=50)
    pos_reference_name: str | None = Field(None, max_length=255)
    qb_account_id: str = Field(..., min_length=1, max_length=100)
    qb_account_name: str = Field(..., min_length=1, max_length=255)
    qb_account_type: str = Field(..., min_length=1, max_length=100)
    qb_account_sub_type: str | None = Field(None, max_length=100)
    is_default: bool = False


class QBAccountMappingCreate(QBAccountMappingBase):
    pass


class QBAccountMappingUpdate(BaseModel):
    qb_account_id: str | None = Field(None, min_length=1, max_length=100)
    qb_account_name: str | None = Field(None, min_length=1, max_length=255)
    qb_account_type: str | None = Field(None, min_length=1, max_length=100)
    qb_account_sub_type: str | None = Field(None, max_length=100)
    is_default: bool | None = None


class QBAccountMappingResponse(QBAccountMappingBase):
    id: uuid.UUID
    connection_id: uuid.UUID
    is_auto_created: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Entity Mappings
# ---------------------------------------------------------------------------


class QBEntityMappingResponse(BaseModel):
    id: uuid.UUID
    entity_type: str
    pos_entity_id: uuid.UUID
    pos_entity_name: str
    qb_entity_id: str
    qb_entity_type: str
    qb_entity_name: str
    sync_direction: str
    last_synced_at: datetime | None = None
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


class QBSyncJobResponse(BaseModel):
    id: uuid.UUID
    job_type: str
    entity_type: str
    entity_id: uuid.UUID | None = None
    priority: int
    status: str
    error_message: str | None = None
    retry_count: int
    created_at: datetime
    completed_at: datetime | None = None
    processing_duration_ms: int | None = None
    model_config = {"from_attributes": True}


class QBSyncLogResponse(BaseModel):
    id: uuid.UUID
    sync_type: str
    pos_entity_type: str | None = None
    pos_entity_id: uuid.UUID | None = None
    qb_entity_type: str | None = None
    qb_entity_id: str | None = None
    action: str
    status: str
    error_message: str | None = None
    error_code: str | None = None
    duration_ms: int | None = None
    qb_doc_number: str | None = None
    amount_paisa: int | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class QBSyncStats(BaseModel):
    total_synced: int
    last_24h_synced: int
    last_24h_failed: int
    pending_jobs: int
    failed_jobs: int
    dead_letter_jobs: int
    last_sync_at: datetime | None = None
    sync_by_type: dict[str, int] = Field(default_factory=dict)


class QBManualSyncRequest(BaseModel):
    sync_type: str = Field(
        ...,
        pattern=r"^(full_sync|sync_items|sync_customers|sync_orders|daily_summary|setup_tax_codes)$",
    )
    date_from: datetime | None = None
    date_to: datetime | None = None
    entity_ids: list[uuid.UUID] | None = None


class QBSyncTriggerResponse(BaseModel):
    jobs_created: int
    message: str
    batch_id: uuid.UUID


# ---------------------------------------------------------------------------
# QB Account Discovery
# ---------------------------------------------------------------------------


class QBAccountInfo(BaseModel):
    id: str
    name: str
    account_type: str
    account_sub_type: str | None = None
    fully_qualified_name: str | None = None
    current_balance: float | None = None
    active: bool = True


class QBAccountListResponse(BaseModel):
    accounts: list[QBAccountInfo] = Field(default_factory=list)
    total: int


# ---------------------------------------------------------------------------
# Account Matching (Attempt 2 — replaces diagnostic/templates)
# ---------------------------------------------------------------------------


class QBMatchSignals(BaseModel):
    exact: float = 0.0
    anchor: float = 0.0
    jaccard: float = 0.0
    synonym: float = 0.0
    type_match: float = 0.0
    substring: float = 0.0


class QBMatchCandidate(BaseModel):
    qb_account_id: str
    qb_account_name: str
    qb_account_type: str
    qb_account_sub_type: str | None = None
    fully_qualified_name: str | None = None
    active: bool = True
    score: float = Field(..., ge=0.0, le=1.0)
    signals: QBMatchSignals
    confidence: str


class QBMatchItem(BaseModel):
    """One POS accounting need and its match status."""

    need_key: str
    need_label: str
    need_description: str
    expected_qb_types: list[str] = Field(default_factory=list)
    expected_qb_sub_type: str | None = None
    required: bool = False
    status: str  # matched, candidates, unmatched
    best_match: QBMatchCandidate | None = None
    candidates: list[QBMatchCandidate] = Field(default_factory=list)
    decision: str | None = None
    decision_account_id: str | None = None
    decision_account_name: str | None = None


class QBUnmappedAccount(BaseModel):
    qb_account_id: str
    qb_account_name: str
    qb_account_type: str
    qb_account_sub_type: str | None = None
    fully_qualified_name: str | None = None
    active: bool = True
    suggested_mapping_type: str | None = None


class QBDecisionSummary(BaseModel):
    use_existing: int = 0
    create_new: int = 0
    skip: int = 0
    pending: int = 0
    ready_to_apply: bool = False


class QBMatchResult(BaseModel):
    """Full match result — POS needs vs QB accounts."""

    id: str
    created_at: str
    is_live: bool = False
    total_needs: int
    total_qb_accounts: int
    matched: int
    candidates: int
    unmatched: int
    required_total: int = 0
    required_matched: int = 0
    coverage_pct: float
    health_grade: str
    items: list[QBMatchItem] = Field(default_factory=list)
    unmapped_qb_accounts: list[QBUnmappedAccount] = Field(default_factory=list)
    decision_summary: QBDecisionSummary | None = None
    apply_result: dict | None = None
    applied_at: str | None = None


class QBMatchResultSummary(BaseModel):
    id: str
    created_at: str
    health_grade: str
    matched: int
    candidates: int
    unmatched: int
    total_needs: int
    coverage_pct: float
    is_live: bool = False


class QBDecision(BaseModel):
    index: int = Field(..., ge=0)
    decision: str = Field(..., pattern=r"^(use_existing|create_new|skip)$")
    qb_account_id: str | None = None
    qb_account_name: str | None = None


class QBDecisionsRequest(BaseModel):
    decisions: list[QBDecision] = Field(..., min_length=1)


class QBMatchApplyResponse(BaseModel):
    accounts_created: int
    mappings_created: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)
    result_id: str


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------


class QBHealthCheckDetail(BaseModel):
    mapping_id: str
    mapping_type: str
    qb_account_id: str
    qb_account_name: str
    status: str
    issue: str | None = None
    message: str
    current_name: str | None = None


class QBHealthCheckResponse(BaseModel):
    grade: str
    total_mappings: int
    healthy: int
    warnings: int
    critical: int
    checked_at: str
    details: list[QBHealthCheckDetail] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# CoA Snapshots
# ---------------------------------------------------------------------------


class QBSnapshotSummary(BaseModel):
    """Summary view of a CoA snapshot (without full account data)."""

    id: uuid.UUID
    snapshot_type: str
    account_count: int
    is_locked: bool
    version: int
    qb_company_name: str
    qb_realm_id: str
    fetched_at: datetime
    created_at: datetime
    notes: str | None = None
    model_config = {"from_attributes": True}


class QBSnapshotDetail(QBSnapshotSummary):
    """Full snapshot including account data."""

    coa_data: list[dict] = Field(default_factory=list)


class QBSnapshotCreateResponse(BaseModel):
    """Response after creating snapshots."""

    backup_id: str
    working_copy_id: str
    account_count: int
    version: int
    company_name: str
    fetched_at: str
