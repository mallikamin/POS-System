"""Danny's D-63 other income and D-62 opening cash balance.

Three new tables, `income_categories`, `other_income` and `opening_balances`.
**Nothing existing is altered and no existing row is touched**, so this is
safe on a live tenant mid-service. Categories are seeded lazily by
`other_income_service` on first open, like expense categories, so no data is
written here.

🔴 Chained on `f6a7b8c9d0e1`, the last COMMITTED revision. The uncommitted Meta
Pixel migration `b0c1d2e3f4a5` in the working tree also revises
`f6a7b8c9d0e1`; when that work is committed its `down_revision` must be moved
to this revision, or alembic will see two heads.

Revision ID: c3d4e5f6a7b8
Revises: f6a7b8c9d0e1
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "income_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_income_category_tenant_name"),
    )
    op.create_index(
        "ix_income_categories_tenant_id", "income_categories", ["tenant_id"]
    )
    op.create_index(
        "ix_income_category_tenant_active",
        "income_categories",
        ["tenant_id", "is_active"],
    )

    op.create_table(
        "other_income",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("payer", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reference_number", sa.String(length=100), nullable=True),
        # Integer minor units, like payments. 350000 is Rs 3,500.
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False, server_default="cash"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["category_id"], ["income_categories.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("amount_minor > 0", name="ck_other_income_amount_positive"),
        sa.CheckConstraint("method IN ('cash', 'bank')", name="ck_other_income_method"),
    )
    op.create_index("ix_other_income_tenant_id", "other_income", ["tenant_id"])
    op.create_index("ix_other_income_location_id", "other_income", ["location_id"])
    op.create_index("ix_other_income_category_id", "other_income", ["category_id"])
    op.create_index(
        "ix_other_income_tenant_date", "other_income", ["tenant_id", "received_on"]
    )

    # D-62: cash in hand on the go-live day. One row per tenant; cash only.
    op.create_table(
        "opening_balances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("cash_minor", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_opening_balance_tenant"),
        sa.CheckConstraint("cash_minor >= 0", name="ck_opening_balance_cash_not_negative"),
    )
    op.create_index("ix_opening_balances_tenant_id", "opening_balances", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_opening_balances_tenant_id", table_name="opening_balances")
    op.drop_table("opening_balances")
    op.drop_index("ix_other_income_tenant_date", table_name="other_income")
    op.drop_index("ix_other_income_category_id", table_name="other_income")
    op.drop_index("ix_other_income_location_id", table_name="other_income")
    op.drop_index("ix_other_income_tenant_id", table_name="other_income")
    op.drop_table("other_income")
    op.drop_index("ix_income_category_tenant_active", table_name="income_categories")
    op.drop_index("ix_income_categories_tenant_id", table_name="income_categories")
    op.drop_table("income_categories")
