"""Multi-location: locations, per-location stock, transfers, and sales channels.

Revision ID: x0y1z2a3b4c5
Revises: w9x0y1z2a3b4
Create Date: 2026-08-26

Why this exists
----------------
FZ LLC (`_context/clients/fz-llc-uae/`) runs two locations and the distinction
is operational, not cosmetic:

  * Location 1, production/wholesale -- runs the recipes, sells B2B, must issue
    an A4 VAT tax invoice carrying the full legal name and TRN.
  * Location 2, delivery only -- call centre, third-party apps, e-commerce.

Stock moves between them, a sale must deduct from the location that sold it,
and Martin's stated key customisation (scope doc Section 8) is net profit after
*channel commission*, not merely after product cost.

Safety
------
Every change here is ADDITIVE. All new columns on existing tables are nullable
(or carry a server_default), so no backfill is required and no existing row is
invalidated:

  * `orders.location_id` / `orders.sales_channel_id` are nullable -- a
    single-site tenant keeps writing orders exactly as before, and a null means
    "the tenant's default location".
  * `orders.channel_commission_minor` defaults to 0, so historical profit
    figures are unchanged rather than retroactively reduced.
  * `inventory_transactions.location_id` is nullable for rows written before
    locations existed.

Verified against production before writing this: `locations`, `sales_channels`
and `location_stock` do not exist, and `ingredients` / `inventory_transactions`
are EMPTY for every tenant, so nothing can be orphaned by the new FKs.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "x0y1z2a3b4c5"
down_revision: str | None = "w9x0y1z2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---------------------------------------------------------------- locations
    op.create_table(
        "locations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column(
            "location_type",
            sa.String(length=20),
            nullable=False,
            server_default="retail",
        ),
        sa.Column("legal_name", sa.String(length=300), nullable=True),
        sa.Column("tax_registration_number", sa.String(length=50), nullable=True),
        sa.Column("address_line1", sa.String(length=300), nullable=True),
        sa.Column("address_line2", sa.String(length=300), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column(
            "invoice_format",
            sa.String(length=30),
            nullable=False,
            server_default="thermal_ticket",
        ),
        sa.Column(
            "invoice_prefix", sa.String(length=10), nullable=False, server_default="INV"
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_location_tenant_code"),
        sa.CheckConstraint(
            "location_type IN ('production', 'delivery', 'retail')",
            name="ck_location_type",
        ),
        sa.CheckConstraint(
            "invoice_format IN ('a4_tax_invoice', 'thermal_ticket')",
            name="ck_location_invoice_format",
        ),
    )
    op.create_index("ix_locations_tenant_id", "locations", ["tenant_id"])
    op.create_index(
        "ix_location_tenant_active", "locations", ["tenant_id", "is_active"]
    )

    # ----------------------------------------------------------- sales_channels
    op.create_table(
        "sales_channels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column(
            "commission_bps", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "fixed_fee_minor", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_sales_channel_tenant_code"),
        sa.CheckConstraint(
            "commission_bps >= 0 AND commission_bps <= 10000",
            name="ck_sales_channel_commission_range",
        ),
    )
    op.create_index("ix_sales_channels_tenant_id", "sales_channels", ["tenant_id"])
    op.create_index(
        "ix_sales_channel_tenant_active", "sales_channels", ["tenant_id", "is_active"]
    )

    # ----------------------------------------------------------- location_stock
    op.create_table(
        "location_stock",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("ingredient_id", sa.Uuid(), nullable=False),
        sa.Column(
            "quantity", sa.Numeric(precision=12, scale=3), nullable=False,
            server_default="0",
        ),
        sa.Column(
            "reorder_point", sa.Numeric(precision=12, scale=3), nullable=False,
            server_default="0",
        ),
        sa.Column(
            "reorder_quantity", sa.Numeric(precision=12, scale=3), nullable=False,
            server_default="0",
        ),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "location_id", "ingredient_id", name="uq_location_stock_loc_ingredient"
        ),
    )
    op.create_index("ix_location_stock_tenant_id", "location_stock", ["tenant_id"])
    op.create_index(
        "ix_location_stock_tenant", "location_stock", ["tenant_id", "location_id"]
    )

    # ---------------------------------------------------------- stock_transfers
    op.create_table(
        "stock_transfers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("transfer_number", sa.String(length=40), nullable=False),
        sa.Column("from_location_id", sa.Uuid(), nullable=False),
        sa.Column("to_location_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="draft"
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_by", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["from_location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["to_location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["received_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "transfer_number", name="uq_transfer_tenant_number"
        ),
        sa.CheckConstraint(
            "from_location_id <> to_location_id", name="ck_transfer_distinct_locations"
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'in_transit', 'received', 'cancelled')",
            name="ck_transfer_status",
        ),
    )
    op.create_index("ix_stock_transfers_tenant_id", "stock_transfers", ["tenant_id"])
    op.create_index(
        "ix_transfer_tenant_status", "stock_transfers", ["tenant_id", "status"]
    )

    op.create_table(
        "stock_transfer_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("transfer_id", sa.Uuid(), nullable=False),
        sa.Column("ingredient_id", sa.Uuid(), nullable=False),
        sa.Column("quantity_sent", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column(
            "quantity_received", sa.Numeric(precision=12, scale=3), nullable=True
        ),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column(
            "unit_cost", sa.Numeric(precision=10, scale=2), nullable=False,
            server_default="0",
        ),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["transfer_id"], ["stock_transfers.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("quantity_sent > 0", name="ck_transfer_item_qty_positive"),
    )
    op.create_index(
        "ix_stock_transfer_items_tenant_id", "stock_transfer_items", ["tenant_id"]
    )
    op.create_index(
        "ix_transfer_item_transfer", "stock_transfer_items", ["transfer_id"]
    )

    # ------------------------------------------- additive columns on existing tables
    op.add_column("orders", sa.Column("location_id", sa.Uuid(), nullable=True))
    op.add_column("orders", sa.Column("sales_channel_id", sa.Uuid(), nullable=True))
    op.add_column(
        "orders",
        sa.Column(
            "channel_commission_minor",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Channel commission charged on this order, in minor units",
        ),
    )
    op.create_foreign_key(
        "fk_orders_location", "orders", "locations", ["location_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_orders_sales_channel", "orders", "sales_channels",
        ["sales_channel_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_orders_location_id", "orders", ["location_id"])
    op.create_index("ix_orders_sales_channel_id", "orders", ["sales_channel_id"])

    op.add_column(
        "inventory_transactions", sa.Column("location_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_invtx_location", "inventory_transactions", "locations",
        ["location_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index(
        "ix_inventory_transactions_location_id",
        "inventory_transactions",
        ["location_id"],
    )

    # The tz bug this module has carried since it was written. `transaction_date`
    # defaults to a tz-aware datetime but the column was declared without
    # timezone, so asyncpg refuses every write against Postgres. Never hit in
    # production only because no tenant has ever held stock. Same root cause as
    # recipes.effective_date, fixed in w9x0y1z2a3b4.
    op.alter_column(
        "inventory_transactions",
        "transaction_date",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "inventory_transactions",
        "transaction_date",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
    )

    op.drop_index("ix_inventory_transactions_location_id", "inventory_transactions")
    op.drop_constraint("fk_invtx_location", "inventory_transactions", type_="foreignkey")
    op.drop_column("inventory_transactions", "location_id")

    op.drop_index("ix_orders_sales_channel_id", "orders")
    op.drop_index("ix_orders_location_id", "orders")
    op.drop_constraint("fk_orders_sales_channel", "orders", type_="foreignkey")
    op.drop_constraint("fk_orders_location", "orders", type_="foreignkey")
    op.drop_column("orders", "channel_commission_minor")
    op.drop_column("orders", "sales_channel_id")
    op.drop_column("orders", "location_id")

    op.drop_table("stock_transfer_items")
    op.drop_table("stock_transfers")
    op.drop_table("location_stock")
    op.drop_table("sales_channels")
    op.drop_table("locations")
