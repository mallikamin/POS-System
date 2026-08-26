"""Back-office quotations.

Revision ID: a3b4c5d6e7f8
Revises: z2a3b4c5d6e7
Create Date: 2026-08-26

Why this exists
----------------
FZ LLC scope doc Section 2: *"Capacity to issue quotations directly from the
back office."* For a production site selling B2B, the sale starts with a priced
offer that expires, not with an order.

A quotation is deliberately NOT a draft order. It expires, it can be declined,
and it must not be able to touch stock, the kitchen or the day's takings.
`quotations.converted_order_id` records the one-way step from offer to order.

Safety
------
🟢 Two new tables. No existing table is altered. Every outward foreign key
points at something that already exists (`tenants`, `locations`, `customers`,
`menu_items`, `orders`, `users`), and all of them except the tenant are
nullable with `SET NULL`, so deleting a customer or a menu item cannot orphan
a historical quotation.

Money
-----
🔴 INTEGER minor units here, matching `orders` and the tax invoice -- not the
`Numeric` convention the inventory and procurement tables use for costs. Both
exist in this schema on purpose; sales-side money is integer.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: str | None = "z2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "quotations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("quote_number", sa.String(length=40), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("customer_name", sa.String(length=200), nullable=False),
        sa.Column("customer_phone", sa.String(length=50), nullable=True),
        sa.Column("customer_email", sa.String(length=255), nullable=True),
        sa.Column("customer_address", sa.Text(), nullable=True),
        sa.Column("customer_trn", sa.String(length=50), nullable=True),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="draft"
        ),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column(
            "tax_rate_bps", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "subtotal_minor", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "discount_minor", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "tax_minor", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "total_minor", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("terms", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_to_email", sa.String(length=255), nullable=True),
        sa.Column(
            "email_send_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("last_email_error", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decline_reason", sa.Text(), nullable=True),
        sa.Column("converted_order_id", sa.Uuid(), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["location_id"], ["locations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["converted_order_id"], ["orders.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "quote_number", name="uq_quotation_tenant_number"
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'sent', 'accepted', 'declined', 'converted')",
            name="ck_quotation_status",
        ),
        sa.CheckConstraint(
            "tax_rate_bps >= 0 AND tax_rate_bps <= 10000",
            name="ck_quotation_tax_range",
        ),
    )
    op.create_index("ix_quotations_tenant_id", "quotations", ["tenant_id"])
    op.create_index(
        "ix_quotation_tenant_status", "quotations", ["tenant_id", "status"]
    )

    op.create_table(
        "quotation_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("quotation_id", sa.Uuid(), nullable=False),
        sa.Column("menu_item_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "unit_price_minor", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "line_total_minor", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "display_order", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["quotation_id"], ["quotations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id"], ["menu_items.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("quantity > 0", name="ck_quotation_item_qty_positive"),
        sa.CheckConstraint(
            "unit_price_minor >= 0", name="ck_quotation_item_price_positive"
        ),
    )
    op.create_index("ix_quotation_items_tenant_id", "quotation_items", ["tenant_id"])
    op.create_index(
        "ix_quotation_item_quotation", "quotation_items", ["quotation_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_quotation_item_quotation", table_name="quotation_items")
    op.drop_index("ix_quotation_items_tenant_id", table_name="quotation_items")
    op.drop_table("quotation_items")

    op.drop_index("ix_quotation_tenant_status", table_name="quotations")
    op.drop_index("ix_quotations_tenant_id", table_name="quotations")
    op.drop_table("quotations")
