"""P1-B: discount types and order discounts

Revision ID: j6k7l8m9n0o1
Revises: i5j6k7l8m9n0
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa

revision = "j6k7l8m9n0o1"
down_revision = "i5j6k7l8m9n0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discount_types",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False, comment="percent | fixed"),
        sa.Column("value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.UniqueConstraint("tenant_id", "code", name="uq_discount_type_tenant_code"),
    )
    op.create_index("ix_discount_types_tenant_id", "discount_types", ["tenant_id"])
    op.create_index("ix_discount_types_tenant_active", "discount_types", ["tenant_id", "is_active"])

    op.create_table(
        "order_discounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=True),
        sa.Column("table_session_id", sa.Uuid(), sa.ForeignKey("table_sessions.id", ondelete="CASCADE"), nullable=True),
        sa.Column("discount_type_id", sa.Uuid(), sa.ForeignKey("discount_types.id", ondelete="SET NULL"), nullable=True),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False, comment="Discount in paisa"),
        sa.Column("percent_bps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("applied_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_order_discounts_tenant_id", "order_discounts", ["tenant_id"])
    op.create_index("ix_order_discounts_order", "order_discounts", ["order_id"])
    op.create_index("ix_order_discounts_session", "order_discounts", ["table_session_id"])


def downgrade() -> None:
    op.drop_index("ix_order_discounts_session", table_name="order_discounts")
    op.drop_index("ix_order_discounts_order", table_name="order_discounts")
    op.drop_index("ix_order_discounts_tenant_id", table_name="order_discounts")
    op.drop_table("order_discounts")
    op.drop_index("ix_discount_types_tenant_active", table_name="discount_types")
    op.drop_index("ix_discount_types_tenant_id", table_name="discount_types")
    op.drop_table("discount_types")
