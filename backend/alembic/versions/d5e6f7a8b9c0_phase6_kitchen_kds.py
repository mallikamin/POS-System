"""Phase 6: Kitchen Display System (KDS) — stations, tickets, ticket items.

Revision ID: d5e6f7a8b9c0
Revises: c8d9e0f1a2b3
Create Date: 2026-02-20
"""
from alembic import op
import sqlalchemy as sa

revision = "d5e6f7a8b9c0"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- kitchen_stations ---
    op.create_table(
        "kitchen_stations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "name", name="uq_station_tenant_name"),
    )
    op.create_index("ix_kitchen_stations_tenant_active", "kitchen_stations", ["tenant_id", "is_active"])

    # --- kitchen_tickets ---
    op.create_table(
        "kitchen_tickets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("station_id", sa.Uuid(), sa.ForeignKey("kitchen_stations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("served_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "order_id", "station_id", name="uq_ticket_tenant_order_station"),
    )
    op.create_index("ix_kitchen_tickets_tenant_status", "kitchen_tickets", ["tenant_id", "status"])
    op.create_index("ix_kitchen_tickets_station_status", "kitchen_tickets", ["station_id", "status"])

    # --- kitchen_ticket_items ---
    op.create_table(
        "kitchen_ticket_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("kitchen_tickets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("order_item_id", sa.Uuid(), sa.ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("ticket_id", "order_item_id", name="uq_ticket_item_ticket_order_item"),
    )


def downgrade() -> None:
    op.drop_table("kitchen_ticket_items")
    op.drop_table("kitchen_tickets")
    op.drop_index("ix_kitchen_stations_tenant_active", table_name="kitchen_stations")
    op.drop_table("kitchen_stations")
