"""phase7_payments

Revision ID: 4f7e5a9c1b21
Revises: a1b2c3d4e5f6
Create Date: 2026-02-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4f7e5a9c1b21"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_methods",
        sa.Column("code", sa.String(length=30), nullable=False, comment="cash | card | mobile_wallet | bank_transfer"),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("requires_reference", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_payment_method_tenant_code"),
    )
    op.create_index("ix_payment_methods_tenant_active", "payment_methods", ["tenant_id", "is_active"], unique=False)
    op.create_index(op.f("ix_payment_methods_tenant_id"), "payment_methods", ["tenant_id"], unique=False)

    op.create_table(
        "cash_drawer_sessions",
        sa.Column("status", sa.String(length=20), nullable=False, comment="open | closed"),
        sa.Column("opened_by", sa.Uuid(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("opening_float", sa.Integer(), nullable=False, comment="Opening float in paisa"),
        sa.Column("closed_by", sa.Uuid(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closing_balance_expected", sa.Integer(), nullable=True, comment="System expected closing balance in paisa"),
        sa.Column("closing_balance_counted", sa.Integer(), nullable=True, comment="Cashier counted closing balance in paisa"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["closed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["opened_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cash_drawer_tenant_opened", "cash_drawer_sessions", ["tenant_id", "opened_at"], unique=False)
    op.create_index("ix_cash_drawer_tenant_status", "cash_drawer_sessions", ["tenant_id", "status"], unique=False)
    op.create_index(op.f("ix_cash_drawer_sessions_tenant_id"), "cash_drawer_sessions", ["tenant_id"], unique=False)

    op.create_table(
        "payments",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("method_id", sa.Uuid(), nullable=False),
        sa.Column("parent_payment_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False, comment="payment | refund"),
        sa.Column("status", sa.String(length=20), nullable=False, comment="pending | completed | failed"),
        sa.Column("amount", sa.Integer(), nullable=False, comment="Amount in paisa"),
        sa.Column("tendered_amount", sa.Integer(), nullable=True, comment="Cash tendered amount in paisa"),
        sa.Column("change_amount", sa.Integer(), nullable=False, comment="Cash change returned in paisa"),
        sa.Column("reference", sa.String(length=120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("processed_by", sa.Uuid(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["method_id"], ["payment_methods.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_payment_id"], ["payments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["processed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_tenant_order", "payments", ["tenant_id", "order_id"], unique=False)
    op.create_index("ix_payments_tenant_created", "payments", ["tenant_id", "created_at"], unique=False)
    op.create_index(op.f("ix_payments_order_id"), "payments", ["order_id"], unique=False)
    op.create_index(op.f("ix_payments_method_id"), "payments", ["method_id"], unique=False)
    op.create_index(op.f("ix_payments_parent_payment_id"), "payments", ["parent_payment_id"], unique=False)
    op.create_index(op.f("ix_payments_tenant_id"), "payments", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_payments_tenant_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_parent_payment_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_method_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_order_id"), table_name="payments")
    op.drop_index("ix_payments_tenant_created", table_name="payments")
    op.drop_index("ix_payments_tenant_order", table_name="payments")
    op.drop_table("payments")

    op.drop_index(op.f("ix_cash_drawer_sessions_tenant_id"), table_name="cash_drawer_sessions")
    op.drop_index("ix_cash_drawer_tenant_status", table_name="cash_drawer_sessions")
    op.drop_index("ix_cash_drawer_tenant_opened", table_name="cash_drawer_sessions")
    op.drop_table("cash_drawer_sessions")

    op.drop_index(op.f("ix_payment_methods_tenant_id"), table_name="payment_methods")
    op.drop_index("ix_payment_methods_tenant_active", table_name="payment_methods")
    op.drop_table("payment_methods")
