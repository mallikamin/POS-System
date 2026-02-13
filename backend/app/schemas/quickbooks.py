"""Pydantic v2 schemas for QuickBooks Online integration.

Covers the full integration surface: OAuth flow, account/entity mappings,
sync jobs, sync logs, manual triggers, account discovery, and smart-default
mapping templates.

All monetary amounts follow the project convention: integer paisa
(1 PKR = 100 paisa).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# OAuth Flow
# ---------------------------------------------------------------------------

class QBConnectURL(BaseModel):
    """Response with OAuth authorization URL."""

    auth_url: str = Field(..., description="Full Intuit OAuth2 authorization URL")
    state: str = Field(..., description="CSRF token for callback verification")


class QBCallbackRequest(BaseModel):
    """OAuth callback parameters relayed by the frontend after redirect."""

    code: str = Field(..., min_length=1, description="Authorization code from Intuit")
    state: str = Field(..., min_length=1, description="CSRF state to validate")
    realm_id: str = Field(..., min_length=1, description="QuickBooks company realm ID")


class QBConnectionStatus(BaseModel):
    """Current QuickBooks connection state for a tenant."""

    is_connected: bool
    realm_id: str | None = None
    company_name: str | None = None
    connected_at: datetime | None = None
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    token_expires_at: datetime | None = None

    model_config = {"from_attributes": True}


class QBDisconnectResponse(BaseModel):
    """Confirmation after revoking QB connection."""

    message: str
    realm_id: str | None = None


# ---------------------------------------------------------------------------
# Account Mappings
# ---------------------------------------------------------------------------

class QBAccountMappingBase(BaseModel):
    """Shared fields for QB account mappings (Chart of Accounts linkage)."""

    mapping_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description=(
            "Semantic purpose: income, cogs, tax_payable, bank, expense, "
            "discount, tips, delivery_fee, etc."
        ),
    )
    pos_reference_id: uuid.UUID | None = Field(
        None,
        description="POS entity this mapping is specific to (e.g. a category UUID)",
    )
    pos_reference_type: str | None = Field(
        None,
        max_length=50,
        description="POS entity type: category, tax_rate, payment_method, etc.",
    )
    pos_reference_name: str | None = Field(
        None,
        max_length=255,
        description="Human-readable POS entity name for display",
    )
    qb_account_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="QuickBooks account ID from Chart of Accounts",
    )
    qb_account_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="QuickBooks account display name",
    )
    qb_account_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="QB account classification: Income, Expense, Bank, etc.",
    )
    qb_account_sub_type: str | None = Field(
        None,
        max_length=100,
        description="QB account sub-classification: SalesOfProductIncome, etc.",
    )
    is_default: bool = Field(
        False,
        description="Whether this is the default mapping for its mapping_type",
    )


class QBAccountMappingCreate(QBAccountMappingBase):
    """Request body to create a new account mapping."""

    pass


class QBAccountMappingUpdate(BaseModel):
    """Partial update for an existing account mapping.

    All fields optional -- only supplied fields are changed.
    """

    qb_account_id: str | None = Field(None, min_length=1, max_length=100)
    qb_account_name: str | None = Field(None, min_length=1, max_length=255)
    qb_account_type: str | None = Field(None, min_length=1, max_length=100)
    qb_account_sub_type: str | None = Field(None, max_length=100)
    is_default: bool | None = None


class QBAccountMappingResponse(QBAccountMappingBase):
    """Full account mapping as stored in the database."""

    id: uuid.UUID
    connection_id: uuid.UUID
    is_auto_created: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Entity Mappings (menu items, categories, customers <-> QB entities)
# ---------------------------------------------------------------------------

class QBEntityMappingResponse(BaseModel):
    """A linkage between a POS entity and its QuickBooks counterpart."""

    id: uuid.UUID
    entity_type: str = Field(
        ...,
        description="POS domain: menu_item, category, customer, tax_rate, payment_method",
    )
    pos_entity_id: uuid.UUID
    pos_entity_name: str
    qb_entity_id: str
    qb_entity_type: str = Field(
        ...,
        description="QB object type: Item, Customer, TaxCode, PaymentMethod",
    )
    qb_entity_name: str
    sync_direction: str = Field(
        ...,
        description="pos_to_qb, qb_to_pos, or bidirectional",
    )
    last_synced_at: datetime | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Sync Jobs
# ---------------------------------------------------------------------------

class QBSyncJobResponse(BaseModel):
    """A single sync job in the job queue."""

    id: uuid.UUID
    job_type: str = Field(
        ...,
        description="sales_receipt, credit_memo, journal_entry, customer, item, etc.",
    )
    entity_type: str = Field(
        ...,
        description="POS entity domain: order, refund, menu_item, customer, daily_summary",
    )
    entity_id: uuid.UUID | None = Field(
        None,
        description="Specific POS entity UUID (null for batch jobs like daily_summary)",
    )
    priority: int = Field(..., description="Lower = higher priority (0 = immediate)")
    status: str = Field(
        ...,
        description="pending, processing, completed, failed, dead_letter",
    )
    error_message: str | None = None
    retry_count: int
    created_at: datetime
    completed_at: datetime | None = None
    processing_duration_ms: int | None = Field(
        None,
        description="Wall-clock milliseconds from pick-up to completion",
    )

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Sync Logs
# ---------------------------------------------------------------------------

class QBSyncLogResponse(BaseModel):
    """An individual sync log entry (audit trail of every QB API call)."""

    id: uuid.UUID
    sync_type: str = Field(
        ...,
        description="sales_receipt, credit_memo, journal_entry, item, customer, etc.",
    )
    pos_entity_type: str | None = None
    pos_entity_id: uuid.UUID | None = None
    qb_entity_type: str | None = None
    qb_entity_id: str | None = None
    action: str = Field(
        ...,
        description="create, update, delete, void, query",
    )
    status: str = Field(..., description="success, failed, skipped")
    error_message: str | None = None
    error_code: str | None = None
    duration_ms: int | None = Field(
        None,
        description="Round-trip latency of the QB API call in milliseconds",
    )
    qb_doc_number: str | None = Field(
        None,
        description="QuickBooks document number assigned to the synced entity",
    )
    amount_paisa: int | None = Field(
        None,
        description="Transaction amount in paisa (for financial sync entries)",
    )
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Sync Statistics (aggregated)
# ---------------------------------------------------------------------------

class QBSyncStats(BaseModel):
    """Aggregated sync statistics for the dashboard widget."""

    total_synced: int = Field(..., description="All-time successfully synced count")
    last_24h_synced: int = Field(..., description="Successful syncs in the last 24 hours")
    last_24h_failed: int = Field(..., description="Failed syncs in the last 24 hours")
    pending_jobs: int = Field(..., description="Jobs waiting to be processed")
    failed_jobs: int = Field(..., description="Jobs in failed state (will retry)")
    dead_letter_jobs: int = Field(
        ...,
        description="Jobs that exhausted retries and need manual intervention",
    )
    last_sync_at: datetime | None = Field(
        None,
        description="Timestamp of most recent successful sync",
    )
    sync_by_type: dict[str, int] = Field(
        default_factory=dict,
        description="Breakdown by sync type: {sales_receipt: 45, credit_memo: 3, ...}",
    )


# ---------------------------------------------------------------------------
# Manual Sync Triggers
# ---------------------------------------------------------------------------

class QBManualSyncRequest(BaseModel):
    """Request to manually trigger a sync operation."""

    sync_type: str = Field(
        ...,
        pattern=r"^(full_sync|sync_items|sync_customers|sync_orders|daily_summary|setup_tax_codes)$",
        description="Type of sync to trigger",
    )
    date_from: datetime | None = Field(
        None,
        description="Start of date range (inclusive) for order/summary syncs",
    )
    date_to: datetime | None = Field(
        None,
        description="End of date range (inclusive) for order/summary syncs",
    )
    entity_ids: list[uuid.UUID] | None = Field(
        None,
        description="Specific POS entity UUIDs to sync (omit for all)",
    )


class QBSyncTriggerResponse(BaseModel):
    """Acknowledgement after a manual sync is enqueued."""

    jobs_created: int = Field(..., description="Number of sync jobs created")
    message: str
    batch_id: uuid.UUID = Field(
        ...,
        description="Batch identifier to track this group of sync jobs",
    )


# ---------------------------------------------------------------------------
# QB Account Discovery (Chart of Accounts fetch for the mapping wizard)
# ---------------------------------------------------------------------------

class QBAccountInfo(BaseModel):
    """A single QuickBooks account from their Chart of Accounts."""

    id: str = Field(..., description="QuickBooks account ID")
    name: str
    account_type: str = Field(
        ...,
        description="Top-level classification: Income, Expense, Bank, Other Current Asset, etc.",
    )
    account_sub_type: str | None = Field(
        None,
        description="Sub-classification: SalesOfProductIncome, CostOfGoodsSold, etc.",
    )
    fully_qualified_name: str | None = Field(
        None,
        description="Full path for sub-accounts: Food Sales:Dine-In Revenue",
    )
    current_balance: float | None = Field(
        None,
        description="Current account balance (in QB company currency)",
    )
    active: bool = True


class QBAccountListResponse(BaseModel):
    """Paginated list of QB accounts for the mapping UI."""

    accounts: list[QBAccountInfo] = Field(default_factory=list)
    total: int


class QBCompanyInfo(BaseModel):
    """QuickBooks company details fetched after OAuth connection."""

    company_name: str
    legal_name: str | None = None
    country: str | None = None
    fiscal_year_start: str | None = Field(
        None,
        description="Month name or number: January, February, etc.",
    )
    industry_type: str | None = None
    currency: str | None = Field(
        None,
        description="ISO 4217 code: PKR, USD, etc.",
    )


# ---------------------------------------------------------------------------
# Smart Default Mapping Templates
# ---------------------------------------------------------------------------

class QBMappingTemplate(BaseModel):
    """A predefined mapping template for a specific restaurant archetype."""

    template_name: str = Field(
        ...,
        description="Template key: pakistani_restaurant, international_restaurant, qsr, cafe",
    )
    description: str = Field(
        ...,
        description="Human-readable explanation of when to use this template",
    )
    mappings: list[QBAccountMappingCreate] = Field(
        default_factory=list,
        description="Pre-configured account mappings included in this template",
    )


class QBSmartDefaultsRequest(BaseModel):
    """Request to apply a smart-default mapping template."""

    template: str = Field(
        "pakistani_restaurant",
        min_length=1,
        max_length=100,
        description="Template key (e.g. pakistani_restaurant, biryani_house, pizza_chain). "
        "Use GET /mappings/templates for full list of 40 available templates.",
    )
    auto_create_accounts: bool = Field(
        True,
        description="Create missing QB accounts automatically if they do not exist",
    )


class QBSmartDefaultsResponse(BaseModel):
    """Result of applying smart-default mappings."""

    accounts_created: int = Field(
        ...,
        description="Number of new QB accounts created in QuickBooks",
    )
    mappings_created: int = Field(
        ...,
        description="Number of new POS-to-QB account mappings saved",
    )
    mappings_skipped: int = Field(
        ...,
        description="Mappings that already existed and were left unchanged",
    )
    details: list[str] = Field(
        default_factory=list,
        description="Human-readable log of each action taken",
    )


# ---------------------------------------------------------------------------
# Preview / Simulation (no QB connection required)
# ---------------------------------------------------------------------------

class QBPreviewRequest(BaseModel):
    """Request to preview a QB Sales Receipt payload for a given order + template."""

    order_id: uuid.UUID = Field(..., description="POS order UUID to preview")
    template_name: str = Field(
        "pakistani_restaurant",
        min_length=1,
        max_length=100,
        description="Template key (e.g. pakistani_restaurant, biryani_house)",
    )


class QBPreviewResponse(BaseModel):
    """Generated QB Sales Receipt payload for preview / simulation."""

    template_name: str
    template_display_name: str
    order_number: str
    order_type: str
    qb_entity_type: str = Field(
        "SalesReceipt",
        description="QuickBooks entity type that would be created",
    )
    payload: dict = Field(
        ...,
        description="Complete QB API payload that would be sent",
    )
    mappings_used: list[dict] = Field(
        default_factory=list,
        description="Template mappings applied to generate the payload",
    )


# ---------------------------------------------------------------------------
# Diagnostic & Onboarding Tool
# ---------------------------------------------------------------------------

class QBDiagnosticRequest(BaseModel):
    """Request to run a diagnostic gap analysis."""

    template_key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Template key from MAPPING_TEMPLATES (e.g. 'pakistani_restaurant')",
    )
    fixture_name: str | None = Field(
        None,
        description="Test fixture name (standard_fbr, non_standard, fresh_qb, "
        "mixed_urdu_english, heavy_custom). If set, uses mock data instead of live QB.",
    )


class QBMatchSignals(BaseModel):
    """Breakdown of scoring signals for one fuzzy match."""

    exact: float = Field(0.0, description="Exact name match (0 or 1)")
    jaccard: float = Field(0.0, description="Jaccard word overlap (0-1)")
    synonym: float = Field(0.0, description="Synonym set overlap (0-1)")
    type_match: float = Field(0.0, description="QB AccountType compatibility (0-1)")
    substring: float = Field(0.0, description="Substring containment ratio (0-1)")


class QBMatchCandidate(BaseModel):
    """A QB account that potentially matches a template mapping."""

    qb_account_id: str
    qb_account_name: str
    qb_account_type: str
    qb_account_sub_type: str | None = None
    fully_qualified_name: str | None = None
    active: bool = True
    score: float = Field(..., ge=0.0, le=1.0, description="Composite match score")
    signals: QBMatchSignals
    confidence: str = Field(..., description="high (>=0.85), medium (0.60-0.84), low (<0.60)")


class QBDiagnosticItem(BaseModel):
    """One row in the gap analysis — one template mapping and its match status."""

    mapping_type: str
    template_account_name: str
    template_account_type: str
    template_account_sub_type: str | None = None
    template_description: str = ""
    is_default: bool = False
    status: str = Field(
        ...,
        description="matched (high confidence), candidates (medium), unmatched (low/none)",
    )
    best_match: QBMatchCandidate | None = None
    candidates: list[QBMatchCandidate] = Field(default_factory=list)
    decision: str | None = Field(
        None,
        description="Admin decision: use_existing, create_new, skip, or null (pending)",
    )
    decision_account_id: str | None = None
    decision_account_name: str | None = None


class QBUnmappedAccount(BaseModel):
    """A QB account the client has that isn't covered by the chosen template."""

    qb_account_id: str
    qb_account_name: str
    qb_account_type: str
    qb_account_sub_type: str | None = None
    fully_qualified_name: str | None = None
    active: bool = True
    suggested_mapping_type: str | None = Field(
        None,
        description="Best-guess POS mapping type, or null if no confident guess",
    )


class QBDecisionSummary(BaseModel):
    """Counts of each decision type in the current report."""

    use_existing: int = 0
    create_new: int = 0
    skip: int = 0
    pending: int = 0
    ready_to_apply: bool = False


class QBDiagnosticReport(BaseModel):
    """Full diagnostic report — gap analysis results with match details."""

    id: str = Field(..., description="Report UUID for retrieval and export")
    template_key: str
    template_name: str
    created_at: str
    fixture_name: str | None = None
    is_live: bool = Field(False, description="True if report used live QB data")
    total_template_mappings: int
    total_qb_accounts: int
    matched: int
    candidates: int
    unmatched: int
    coverage_pct: float = Field(..., description="Percentage of auto-matched items")
    health_grade: str = Field(..., description="A (perfect), B (good), C (partial), F (poor)")
    summary: str = Field(..., description="Human-readable summary text")
    items: list[QBDiagnosticItem] = Field(default_factory=list)
    unmapped_qb_accounts: list[QBUnmappedAccount] = Field(default_factory=list)
    decision_summary: QBDecisionSummary | None = None
    apply_result: dict | None = Field(
        None, description="Result of apply_decisions() if applied",
    )
    applied_at: str | None = None


class QBDiagnosticReportSummary(BaseModel):
    """Lightweight report summary for list endpoint."""

    id: str
    template_key: str
    template_name: str
    created_at: str
    health_grade: str
    matched: int
    candidates: int
    unmatched: int
    total_template_mappings: int
    coverage_pct: float
    is_live: bool = False
    fixture_name: str | None = None


class QBDiagnosticDecision(BaseModel):
    """A single decision for one diagnostic item."""

    index: int = Field(..., ge=0, description="Index into items[]")
    decision: str = Field(
        ...,
        pattern=r"^(use_existing|create_new|skip)$",
        description="use_existing (map to QB account), create_new (create in QB), skip",
    )
    qb_account_id: str | None = Field(
        None,
        description="Required for use_existing — the QB account to map to",
    )
    qb_account_name: str | None = Field(
        None,
        description="QB account name (for display)",
    )


class QBDiagnosticDecisionsRequest(BaseModel):
    """Batch update of decisions on a diagnostic report."""

    decisions: list[QBDiagnosticDecision] = Field(
        ...,
        min_length=1,
        description="List of decisions to apply",
    )


class QBDiagnosticApplyResponse(BaseModel):
    """Result of applying diagnostic decisions to QB."""

    accounts_created: int
    mappings_created: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)
    report_id: str


class QBHealthCheckDetail(BaseModel):
    """Health status of a single mapping."""

    mapping_id: str
    mapping_type: str
    qb_account_id: str
    qb_account_name: str
    status: str = Field(..., description="healthy, warning, critical")
    issue: str | None = Field(
        None,
        description="account_renamed, account_deactivated, account_deleted, or null",
    )
    message: str
    current_name: str | None = None


class QBHealthCheckResponse(BaseModel):
    """Result of checking existing mappings against live QB."""

    grade: str = Field(..., description="A (all OK), B (warnings), C (some critical), F (broken)")
    total_mappings: int
    healthy: int
    warnings: int
    critical: int
    checked_at: str
    details: list[QBHealthCheckDetail] = Field(default_factory=list)


class QBTestFixtureInfo(BaseModel):
    """Info about an available test fixture."""

    name: str
    description: str
    account_count: int
