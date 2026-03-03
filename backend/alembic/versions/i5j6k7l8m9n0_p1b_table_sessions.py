"""P1-B: table sessions for dine-in consolidation

Revision ID: i5j6k7l8m9n0
Revises: h4i5j6k7l8m9
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa

revision = "i5j6k7l8m9n0"
down_revision = "h4i5j6k7l8m9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "table_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("table_id", sa.Uuid(), sa.ForeignKey("tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("opened_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_table_sessions_tenant_id", "table_sessions", ["tenant_id"])
    op.create_index("ix_table_sessions_table_id", "table_sessions", ["table_id"])
    op.create_index("ix_table_sessions_tenant_status", "table_sessions", ["tenant_id", "status"])
    op.create_index("ix_table_sessions_table_status", "table_sessions", ["table_id", "status"])

    op.add_column(
        "orders",
        sa.Column("table_session_id", sa.Uuid(), sa.ForeignKey("table_sessions.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_orders_table_session_id", "orders", ["table_session_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_table_session_id", table_name="orders")
    op.drop_column("orders", "table_session_id")
    op.drop_index("ix_table_sessions_table_status", table_name="table_sessions")
    op.drop_index("ix_table_sessions_tenant_status", table_name="table_sessions")
    op.drop_index("ix_table_sessions_table_id", table_name="table_sessions")
    op.drop_index("ix_table_sessions_tenant_id", table_name="table_sessions")
    op.drop_table("table_sessions")
