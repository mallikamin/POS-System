"""Slice 1: waiter assignment, walk-in customer, manager role schema

Revision ID: l8m9n0o1p2q3
Revises: k7l8m9n0o1p2
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa

revision = "l8m9n0o1p2q3"
down_revision = "k7l8m9n0o1p2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Waiter assignment on table sessions
    op.add_column(
        "table_sessions",
        sa.Column(
            "assigned_waiter_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="Staff member assigned as waiter for this session",
        ),
    )
    op.create_index("ix_table_sessions_waiter", "table_sessions", ["assigned_waiter_id"])

    # Waiter + customer linkage on orders
    op.add_column(
        "orders",
        sa.Column(
            "waiter_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="Waiter/server assigned to this order",
        ),
    )
    op.create_index("ix_orders_waiter", "orders", ["waiter_id"])

    op.add_column(
        "orders",
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
            comment="Linked customer record",
        ),
    )
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_customer_id", table_name="orders")
    op.drop_column("orders", "customer_id")
    op.drop_index("ix_orders_waiter", table_name="orders")
    op.drop_column("orders", "waiter_id")
    op.drop_index("ix_table_sessions_waiter", table_name="table_sessions")
    op.drop_column("table_sessions", "assigned_waiter_id")
