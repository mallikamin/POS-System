"""QuickBooks integration models: connections, account mappings, entity mappings,
sync queue, sync audit log, and CoA snapshots.

OAuth tokens are stored Fernet-encrypted.  All monetary amounts remain in paisa.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import BaseMixin


# ---------------------------------------------------------------------------
# 1. QBConnection
# ---------------------------------------------------------------------------

class QBConnection(BaseMixin, Base):
    """One QuickBooks Online connection per tenant.

    Stores Fernet-encrypted OAuth2 tokens and cached company metadata.
    realm_id is QuickBooks' unique company identifier.
    """

    __tablename__ = "qb_connections"
    __table_args__ = (
        UniqueConstraint("tenant_id", "realm_id", name="uq_qbconn_tenant_realm"),
        Index("ix_qbconn_tenant_active", "tenant_id", "is_active"),
    )

    realm_id: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="QuickBooks company ID",
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)

    access_token_encrypted: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Fernet-encrypted OAuth2 access token",
    )
    refresh_token_encrypted: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Fernet-encrypted OAuth2 refresh token",
    )
    access_token_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    refresh_token_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )

    scope: Mapped[str] = mapped_column(
        String(500), default="com.intuit.quickbooks.accounting", nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    connected_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False,
    )
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )

    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    last_sync_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="success | failed | in_progress",
    )

    company_info: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="Cached QB company metadata",
    )

    webhook_verifier_token: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True,
    )


# ---------------------------------------------------------------------------
# 2. QBAccountMapping
# ---------------------------------------------------------------------------

class QBAccountMapping(BaseMixin, Base):
    """Maps POS accounting concepts to QuickBooks Chart of Accounts entries.

    mapping_type examples: income, cogs, tax_payable, bank, expense,
    other_current_liability, equity, discount, service_charge, tip,
    delivery_fee, rounding, foodpanda_commission, cash_over_short,
    gift_card_liability.

    When pos_reference_id is set, the mapping applies to a specific POS entity
    (e.g. a category or payment method) rather than being a global default.
    """

    __tablename__ = "qb_account_mappings"
    __table_args__ = (
        Index(
            "ix_qbacctmap_tenant_conn_type",
            "tenant_id", "connection_id", "mapping_type",
        ),
        UniqueConstraint(
            "connection_id", "mapping_type", "qb_account_name",
            name="uq_qbacctmap_conn_type_name",
        ),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("qb_connections.id", ondelete="CASCADE"), nullable=False,
    )

    mapping_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="income | cogs | tax_payable | bank | expense | discount | etc.",
    )

    pos_reference_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True,
        comment="e.g. category_id for category-level income mapping",
    )
    pos_reference_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="category | tax_rate | payment_method | modifier_group",
    )
    pos_reference_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )

    qb_account_id: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="QuickBooks account ID",
    )
    qb_account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    qb_account_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Income | Cost of Goods Sold | Expense | Other Current Liability | Bank | Equity etc.",
    )
    qb_account_sub_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
    )

    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_auto_created: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True,
    )


# ---------------------------------------------------------------------------
# 3. QBEntityMapping
# ---------------------------------------------------------------------------

class QBEntityMapping(BaseMixin, Base):
    """Links individual POS entities to their QuickBooks counterparts.

    entity_type: menu_item, category, customer, tax_code, tax_rate,
    payment_method, vendor, class_ref, department, employee,
    discount_item, service_charge_item.

    sync_direction controls whether changes flow POS->QB, QB->POS, or both.
    sync_hash stores a SHA-256 of the last synced state to detect drift.
    """

    __tablename__ = "qb_entity_mappings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "connection_id", "entity_type", "pos_entity_id",
            name="uq_qbentmap_tenant_conn_type_entity",
        ),
        Index("ix_qbentmap_tenant_type", "tenant_id", "entity_type"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("qb_connections.id", ondelete="CASCADE"), nullable=False,
    )

    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="menu_item | category | customer | tax_code | tax_rate | payment_method | vendor | class_ref | department | employee | discount_item | service_charge_item",
    )
    pos_entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    pos_entity_name: Mapped[str] = mapped_column(String(255), nullable=False)

    qb_entity_id: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="QuickBooks entity ID",
    )
    qb_entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Item | Customer | TaxCode | TaxRate | PaymentMethod | Vendor | Class | Department | Employee",
    )
    qb_entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    qb_entity_ref: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="Full QB ref object for API calls",
    )

    sync_direction: Mapped[str] = mapped_column(
        String(20), default="pos_to_qb", nullable=False,
        comment="pos_to_qb | qb_to_pos | bidirectional",
    )
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    sync_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="SHA-256 of last synced state",
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True,
    )


# ---------------------------------------------------------------------------
# 4. QBSyncJob
# ---------------------------------------------------------------------------

class QBSyncJob(BaseMixin, Base):
    """Async job queue for real-time QuickBooks sync operations.

    Jobs are picked up by a background worker and retried on failure
    with exponential back-off up to max_retries.

    priority: 0 = critical, 5 = normal, 10 = bulk.
    status: pending | processing | completed | failed | dead_letter | cancelled.
    idempotency_key prevents duplicate syncs for the same business event.
    """

    __tablename__ = "qb_sync_queue"
    __table_args__ = (
        Index("ix_qbsyncq_tenant_status_prio", "tenant_id", "status", "priority"),
        Index("ix_qbsyncq_tenant_retry", "tenant_id", "next_retry_at"),
        UniqueConstraint(
            "tenant_id", "idempotency_key",
            name="uq_qbsyncq_tenant_idempotency",
        ),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("qb_connections.id", ondelete="CASCADE"), nullable=False,
    )

    job_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="create_sales_receipt | create_credit_memo | sync_item | daily_summary | full_sync | etc.",
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="order | order_void | order_refund | menu_item | category | customer | tax_config | payment_method | vendor | daily_close | chart_of_accounts",
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    priority: Mapped[int] = mapped_column(
        Integer, default=5, nullable=False,
        comment="0 = critical, 5 = normal, 10 = bulk",
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False,
        comment="pending | processing | completed | failed | dead_letter | cancelled",
    )

    payload: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="Serialized data for the sync operation",
    )
    result: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="QB API response data on success",
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="Full QB error response",
    )

    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    processing_duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )

    idempotency_key: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Prevents duplicate syncs",
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True,
    )


# ---------------------------------------------------------------------------
# 5. QBSyncLog
# ---------------------------------------------------------------------------

class QBSyncLog(BaseMixin, Base):
    """Full audit trail for every QuickBooks API interaction.

    Records HTTP request/response details, timing, and financial amounts
    for post-hoc debugging and reconciliation.
    """

    __tablename__ = "qb_sync_log"
    __table_args__ = (
        Index(
            "ix_qbsynclog_tenant_type_created",
            "tenant_id", "sync_type", "created_at",
        ),
        Index(
            "ix_qbsynclog_tenant_entity",
            "tenant_id", "pos_entity_type", "pos_entity_id",
        ),
        Index("ix_qbsynclog_tenant_batch", "tenant_id", "batch_id"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("qb_connections.id", ondelete="CASCADE"), nullable=False,
    )

    sync_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Same values as job_type + oauth_connect | oauth_refresh | oauth_disconnect | account_create | webhook",
    )

    pos_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pos_entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    qb_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    qb_entity_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    action: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="create | update | delete | void | query | read | oauth",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="success | failed | skipped | partial",
    )

    http_method: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="GET | POST | PUT | DELETE",
    )
    http_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    request_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="QuickBooks error code",
    )

    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    qb_doc_number: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="e.g. Sales Receipt number",
    )
    amount_paisa: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="For quick financial audit (paisa)",
    )

    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True, comment="Groups related sync operations",
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True,
    )


# ---------------------------------------------------------------------------
# 6. QBCoASnapshot
# ---------------------------------------------------------------------------

class QBCoASnapshot(BaseMixin, Base):
    """Immutable backup + working copy of a partner's QB Chart of Accounts.

    On first OAuth connect, we immediately fetch the full CoA and store:
      - snapshot_type='original_backup' (locked, never modified)
      - snapshot_type='working_copy' (cloned from backup, used for matching)

    The original_backup serves as a safety net — we can always prove what the
    partner's books looked like before we touched anything.
    """

    __tablename__ = "qb_coa_snapshots"
    __table_args__ = (
        Index("ix_qbcoa_tenant_conn_type", "tenant_id", "connection_id", "snapshot_type"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("qb_connections.id", ondelete="CASCADE"), nullable=False,
    )

    snapshot_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="original_backup | working_copy",
    )

    coa_data: Mapped[list] = mapped_column(
        JSONB, nullable=False,
        comment="Full array of QB account objects at time of snapshot",
    )

    account_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )

    is_locked: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="True for original_backup — prevents edits",
    )

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        comment="When the CoA was fetched from QB API",
    )

    qb_company_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Company name at time of snapshot for identification",
    )

    qb_realm_id: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="QB company ID at time of snapshot",
    )

    notes: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )

    version: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False,
        comment="Incremented on refresh — tracks how many times CoA was re-fetched",
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True,
    )
