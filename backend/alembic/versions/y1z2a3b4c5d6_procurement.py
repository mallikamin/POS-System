"""Procurement: suppliers, supplier catalogue, purchase orders, goods receipts.

Revision ID: y1z2a3b4c5d6
Revises: x0y1z2a3b4c5
Create Date: 2026-08-26

Why this exists
----------------
FZ LLC (`_context/clients/fz-llc-uae/`) scope doc Section 5:

    Select Location -> Select Supplier -> Select Items -> Create PO
        -> Send PO -> Receive Goods -> Update Inventory

Section 6 (OCR-assisted receiving) builds directly on `goods_receipts.source`,
and the Section 5.2 AI ordering suggestion reads the catalogue prices and the
outstanding purchase-order quantities. None of it had anywhere to live.

Safety
------
🟢 **Entirely additive. Six new tables, no column added to and no constraint
placed on any existing table.** Nothing already in the database can be
invalidated by this migration, and a tenant that never opens the procurement
screens is unaffected in every respect.

The only foreign keys pointing outward are to `tenants`, `locations`,
`ingredients` and `users`, all of which already exist. `downgrade()` drops the
six tables in dependency order and is exercised by an upgrade / downgrade /
upgrade round trip before this ships.

Money convention
----------------
🔴 Every `*_minor` column is MINOR UNITS stored as `Numeric` (200 = 2.00 AED),
matching `ingredients.cost_per_unit` and `recipes.cost_per_serving`. It is named
in the column for a reason: on 2026-08-26 a service multiplied an
already-minor-unit value by 100 and overstated cost 100x, and its unit test
agreed with the bug.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "y1z2a3b4c5d6"
down_revision: str | None = "x0y1z2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    """The BaseMixin columns, identical in every table here."""
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
    # ---------------------------------------------------------------- suppliers
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("contact_name", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("address_line1", sa.String(length=300), nullable=True),
        sa.Column("address_line2", sa.String(length=300), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("payment_terms", sa.String(length=200), nullable=True),
        sa.Column("tax_registration_number", sa.String(length=50), nullable=True),
        sa.Column(
            "lead_time_days", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_supplier_tenant_code"),
    )
    op.create_index("ix_suppliers_tenant_id", "suppliers", ["tenant_id"])
    op.create_index(
        "ix_supplier_tenant_active", "suppliers", ["tenant_id", "is_active"]
    )

    # ----------------------------------------------------------- supplier_items
    op.create_table(
        "supplier_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("ingredient_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_sku", sa.String(length=100), nullable=True),
        sa.Column("supplier_item_name", sa.String(length=300), nullable=True),
        sa.Column(
            "last_price_minor",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_purchased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "pack_size",
            sa.Numeric(precision=12, scale=3),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "minimum_order_quantity",
            sa.Numeric(precision=12, scale=3),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column(
            "is_preferred", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "supplier_id", "ingredient_id", name="uq_supplier_item_supplier_ingredient"
        ),
        sa.CheckConstraint(
            "last_price_minor >= 0", name="ck_supplier_item_price_positive"
        ),
    )
    op.create_index("ix_supplier_items_tenant_id", "supplier_items", ["tenant_id"])
    op.create_index(
        "ix_supplier_item_tenant", "supplier_items", ["tenant_id", "ingredient_id"]
    )

    # --------------------------------------------------------- purchase_orders
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("po_number", sa.String(length=40), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status", sa.String(length=30), nullable=False, server_default="draft"
        ),
        sa.Column("expected_date", sa.Date(), nullable=True),
        sa.Column("tax_bps", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "subtotal_minor",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "tax_minor",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "total_minor",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("delivery_instructions", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_to_email", sa.String(length=255), nullable=True),
        sa.Column(
            "email_send_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("last_email_error", sa.Text(), nullable=True),
        sa.Column("fully_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "po_number", name="uq_po_tenant_number"),
        sa.CheckConstraint(
            "status IN ('draft', 'sent', 'partially_received', 'received', "
            "'cancelled')",
            name="ck_po_status",
        ),
        sa.CheckConstraint("tax_bps >= 0 AND tax_bps <= 10000", name="ck_po_tax_range"),
    )
    op.create_index("ix_purchase_orders_tenant_id", "purchase_orders", ["tenant_id"])
    op.create_index("ix_po_tenant_status", "purchase_orders", ["tenant_id", "status"])
    op.create_index(
        "ix_po_tenant_supplier", "purchase_orders", ["tenant_id", "supplier_id"]
    )

    # ---------------------------------------------------- purchase_order_items
    op.create_table(
        "purchase_order_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_order_id", sa.Uuid(), nullable=False),
        sa.Column("ingredient_id", sa.Uuid(), nullable=False),
        sa.Column(
            "quantity_ordered", sa.Numeric(precision=12, scale=3), nullable=False
        ),
        sa.Column(
            "quantity_received",
            sa.Numeric(precision=12, scale=3),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column(
            "unit_price_minor",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "line_total_minor",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("supplier_sku", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"], ["purchase_orders.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "purchase_order_id", "ingredient_id", name="uq_po_item_po_ingredient"
        ),
        sa.CheckConstraint("quantity_ordered > 0", name="ck_po_item_qty_positive"),
        sa.CheckConstraint("unit_price_minor >= 0", name="ck_po_item_price_positive"),
    )
    op.create_index(
        "ix_purchase_order_items_tenant_id", "purchase_order_items", ["tenant_id"]
    )
    op.create_index("ix_po_item_po", "purchase_order_items", ["purchase_order_id"])

    # ---------------------------------------------------------- goods_receipts
    op.create_table(
        "goods_receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_number", sa.String(length=40), nullable=False),
        sa.Column("purchase_order_id", sa.Uuid(), nullable=False),
        sa.Column(
            "source", sa.String(length=20), nullable=False, server_default="manual"
        ),
        sa.Column("document_reference", sa.String(length=120), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_by", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"], ["purchase_orders.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["received_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "receipt_number", name="uq_goods_receipt_tenant_number"
        ),
        sa.CheckConstraint("source IN ('manual', 'ocr')", name="ck_goods_receipt_source"),
    )
    op.create_index("ix_goods_receipts_tenant_id", "goods_receipts", ["tenant_id"])
    op.create_index("ix_goods_receipt_po", "goods_receipts", ["purchase_order_id"])

    # ----------------------------------------------------- goods_receipt_lines
    op.create_table(
        "goods_receipt_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_order_item_id", sa.Uuid(), nullable=False),
        sa.Column("ingredient_id", sa.Uuid(), nullable=False),
        sa.Column(
            "quantity_received", sa.Numeric(precision=12, scale=3), nullable=False
        ),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column(
            "unit_price_minor",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["receipt_id"], ["goods_receipts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_item_id"],
            ["purchase_order_items.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "quantity_received > 0", name="ck_goods_receipt_line_qty_positive"
        ),
    )
    op.create_index(
        "ix_goods_receipt_lines_tenant_id", "goods_receipt_lines", ["tenant_id"]
    )
    op.create_index(
        "ix_goods_receipt_line_receipt", "goods_receipt_lines", ["receipt_id"]
    )


def downgrade() -> None:
    # Dependency order: lines before receipts, items before orders, catalogue
    # before suppliers.
    op.drop_index("ix_goods_receipt_line_receipt", table_name="goods_receipt_lines")
    op.drop_index("ix_goods_receipt_lines_tenant_id", table_name="goods_receipt_lines")
    op.drop_table("goods_receipt_lines")

    op.drop_index("ix_goods_receipt_po", table_name="goods_receipts")
    op.drop_index("ix_goods_receipts_tenant_id", table_name="goods_receipts")
    op.drop_table("goods_receipts")

    op.drop_index("ix_po_item_po", table_name="purchase_order_items")
    op.drop_index("ix_purchase_order_items_tenant_id", table_name="purchase_order_items")
    op.drop_table("purchase_order_items")

    op.drop_index("ix_po_tenant_supplier", table_name="purchase_orders")
    op.drop_index("ix_po_tenant_status", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_tenant_id", table_name="purchase_orders")
    op.drop_table("purchase_orders")

    op.drop_index("ix_supplier_item_tenant", table_name="supplier_items")
    op.drop_index("ix_supplier_items_tenant_id", table_name="supplier_items")
    op.drop_table("supplier_items")

    op.drop_index("ix_supplier_tenant_active", table_name="suppliers")
    op.drop_index("ix_suppliers_tenant_id", table_name="suppliers")
    op.drop_table("suppliers")
