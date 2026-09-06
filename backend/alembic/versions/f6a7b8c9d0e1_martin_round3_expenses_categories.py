"""Martin round 3: expenses, expense categories, ingredient categories.

Martin Zubeldia (FZ LLC), 2026-09-06:

    "There is no expenses menu to attach the invoices of my expenses (not the
     ones from suppliers which are already in the receiving of ingredients, but
     other expenses such as rent, salaries etc...)"

    "Ingredients. Theres a fixed set of Categories. Don't see a menu or
     drop-down menu where I can add a category"

Four new tables. **Nothing existing is altered and no existing row is touched**,
which is what makes this migration safe to run on a live tenant mid-service:

  * `expense_categories` and `expenses` + `expense_attachments` (M10)
  * `ingredient_categories` (M11)

🔴 `ingredients.category` is deliberately NOT converted to a foreign key. It
stays the string it has always been; the new table is the master list that fills
the dropdown. Converting it would mean rewriting every ingredient row on every
tenant to close a usability gap, and a null FK would then mean "uncategorised"
where the string today means "General".

The backfill at the end is the one data write, and it only INSERTS: every
distinct category already in use on each tenant becomes a master row, so the
dropdown opens on day one showing exactly what the data already contains.
Expense categories are NOT seeded here -- `expense_service.list_categories`
seeds them lazily on first open, so a tenant that never opens the screen never
gets ten rows it did not ask for.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- M11: the ingredient category master list -------------------------
    op.create_table(
        "ingredient_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "name", name="uq_ingredient_category_tenant_name"
        ),
    )
    op.create_index(
        "ix_ingredient_categories_tenant_id",
        "ingredient_categories",
        ["tenant_id"],
    )
    op.create_index(
        "ix_ingredient_category_tenant_active",
        "ingredient_categories",
        ["tenant_id", "is_active"],
    )

    # ---- M10: expense categories ------------------------------------------
    op.create_table(
        "expense_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "name", name="uq_expense_category_tenant_name"
        ),
    )
    op.create_index(
        "ix_expense_categories_tenant_id", "expense_categories", ["tenant_id"]
    )
    op.create_index(
        "ix_expense_category_tenant_active",
        "expense_categories",
        ["tenant_id", "is_active"],
    )

    # ---- M10: the expenses themselves -------------------------------------
    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("payee", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reference_number", sa.String(length=100), nullable=True),
        # Minor units, like every other money column in this codebase. 850 is
        # 8.50 AED. The total INCLUDES the tax; `tax_minor` is the part of it
        # that is VAT.
        sa.Column(
            "amount_minor", sa.Numeric(14, 2), nullable=False, server_default="0"
        ),
        sa.Column("tax_minor", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="unpaid"
        ),
        sa.Column("payment_method", sa.String(length=50), nullable=True),
        sa.Column("paid_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        # SET NULL, not CASCADE: closing a branch must not delete the rent it
        # paid, or every historical total silently shrinks.
        sa.ForeignKeyConstraint(
            ["location_id"], ["locations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["category_id"], ["expense_categories.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("amount_minor >= 0", name="ck_expense_amount_not_negative"),
        sa.CheckConstraint("tax_minor >= 0", name="ck_expense_tax_not_negative"),
        sa.CheckConstraint(
            "tax_minor <= amount_minor", name="ck_expense_tax_within_total"
        ),
    )
    op.create_index("ix_expenses_tenant_id", "expenses", ["tenant_id"])
    op.create_index("ix_expenses_location_id", "expenses", ["location_id"])
    op.create_index("ix_expenses_category_id", "expenses", ["category_id"])
    op.create_index("ix_expense_tenant_date", "expenses", ["tenant_id", "expense_date"])
    op.create_index("ix_expense_tenant_status", "expenses", ["tenant_id", "status"])
    op.create_index(
        "ix_expense_tenant_category", "expenses", ["tenant_id", "category_id"]
    )

    # ---- M10: the invoices pinned to them ---------------------------------
    op.create_table(
        "expense_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("expense_id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["expense_id"], ["expenses.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["media_id"], ["media_files.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_expense_attachments_tenant_id", "expense_attachments", ["tenant_id"]
    )
    op.create_index(
        "ix_expense_attachment_expense", "expense_attachments", ["expense_id"]
    )

    # ---- M11 backfill: the dropdown opens knowing what is already there ----
    #
    # INSERT only, one row per (tenant, category) already in use. `DISTINCT ON`
    # keeps the first spelling encountered when a tenant already has "Dairy" and
    # "dairy", which the unique constraint on (tenant_id, name) would otherwise
    # not stop -- it is case-SENSITIVE, so both would land and the dropdown would
    # show the duplicate this table exists to remove. Ordering by the lowercase
    # name then the raw name makes the choice deterministic rather than whatever
    # the planner returned first.
    op.execute(
        """
        INSERT INTO ingredient_categories (id, tenant_id, name, sort_order, is_active)
        SELECT DISTINCT ON (tenant_id, lower(trim(category)))
               gen_random_uuid(),
               tenant_id,
               trim(category),
               0,
               true
          FROM ingredients
         WHERE category IS NOT NULL
           AND trim(category) <> ''
         ORDER BY tenant_id, lower(trim(category)), trim(category)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_expense_attachment_expense", table_name="expense_attachments")
    op.drop_index("ix_expense_attachments_tenant_id", table_name="expense_attachments")
    op.drop_table("expense_attachments")

    op.drop_index("ix_expense_tenant_category", table_name="expenses")
    op.drop_index("ix_expense_tenant_status", table_name="expenses")
    op.drop_index("ix_expense_tenant_date", table_name="expenses")
    op.drop_index("ix_expenses_category_id", table_name="expenses")
    op.drop_index("ix_expenses_location_id", table_name="expenses")
    op.drop_index("ix_expenses_tenant_id", table_name="expenses")
    op.drop_table("expenses")

    op.drop_index("ix_expense_category_tenant_active", table_name="expense_categories")
    op.drop_index("ix_expense_categories_tenant_id", table_name="expense_categories")
    op.drop_table("expense_categories")

    op.drop_index(
        "ix_ingredient_category_tenant_active", table_name="ingredient_categories"
    )
    op.drop_index(
        "ix_ingredient_categories_tenant_id", table_name="ingredient_categories"
    )
    op.drop_table("ingredient_categories")
