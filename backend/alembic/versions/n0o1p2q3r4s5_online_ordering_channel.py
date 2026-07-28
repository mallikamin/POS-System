"""Online ordering channel: service type, delivery, accept/reject + ETA.

Adds the fields the public storefront needs on `orders`. All are nullable (or
default 0) so every existing row stays valid and no backfill is required --
these are meaningless for dine_in/takeaway/call_center and must stay null there
rather than carrying a misleading default.

Note: `order_type` itself needs NO change. It is a plain String(20) with a
comment, not a CHECK constraint or enum -- the real constraint is a Pydantic
pattern in app/schemas/order.py. Adding 'online' is a schema-layer change only.

Revision ID: n0o1p2q3r4s5
Revises: m9n0o1p2q3r4
Create Date: 2026-07-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n0o1p2q3r4s5"
down_revision: Union[str, None] = "m9n0o1p2q3r4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "service_type",
            sa.String(length=20),
            nullable=True,
            comment="collection | delivery. Online orders only; null otherwise.",
        ),
    )
    op.add_column("orders", sa.Column("delivery_address", sa.Text(), nullable=True))
    op.add_column(
        "orders",
        sa.Column(
            "delivery_area",
            sa.String(length=100),
            nullable=True,
            comment="Named delivery area the fee was derived from, e.g. 'Arrochar'",
        ),
    )
    # server_default so the NOT NULL applies cleanly to existing rows; the
    # default is then dropped so the application layer stays the source of truth.
    op.add_column(
        "orders",
        sa.Column(
            "delivery_fee",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Delivery fee in minor units. 0 for collection.",
        ),
    )
    op.alter_column("orders", "delivery_fee", server_default=None)

    op.add_column(
        "orders",
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Set when the shop accepts an online order. Kitchen fires on this.",
        ),
    )
    op.add_column(
        "orders", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "orders", sa.Column("rejection_reason", sa.String(length=500), nullable=True)
    )
    op.add_column(
        "orders",
        sa.Column(
            "eta_minutes",
            sa.Integer(),
            nullable=True,
            comment="Lead time promised to the customer on acceptance",
        ),
    )

    # The order-queue tablet's only query: pending online orders, oldest first.
    op.create_index(
        "ix_orders_online_pending",
        "orders",
        ["tenant_id", "order_type", "accepted_at", "rejected_at"],
    )

    # Minimum basket for delivery. Server-enforced, not just a storefront check.
    op.add_column(
        "restaurant_configs",
        sa.Column(
            "delivery_minimum",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Minimum basket for delivery in minor units. 0 = no minimum.",
        ),
    )
    op.alter_column("restaurant_configs", "delivery_minimum", server_default=None)

    # Delivery areas: a table, not a config blob, because the fee must be
    # looked up server-side and the shop will eventually need to edit it.
    op.create_table(
        "delivery_areas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "code",
            sa.String(length=60),
            nullable=False,
            comment="Stable slug the storefront sends, e.g. 'garelochhead'",
        ),
        sa.Column(
            "name",
            sa.String(length=100),
            nullable=False,
            comment="As printed on the menu, e.g. 'Kilcreggan & Cove'",
        ),
        sa.Column(
            "fee",
            sa.Integer(),
            nullable=False,
            comment="Flat delivery fee in minor units (pence/paisa)",
        ),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        # server_default is required, not cosmetic: BaseMixin declares these with
        # server_default=func.now() and sends no value on INSERT, so without it
        # every insert fails on the NOT NULL. Matches every other table's
        # migration in this project.
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_delivery_area_tenant_code"),
    )
    op.create_index(
        "ix_delivery_areas_tenant_id", "delivery_areas", ["tenant_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_delivery_areas_tenant_id", table_name="delivery_areas")
    op.drop_table("delivery_areas")
    op.drop_column("restaurant_configs", "delivery_minimum")
    op.drop_index("ix_orders_online_pending", table_name="orders")
    op.drop_column("orders", "eta_minutes")
    op.drop_column("orders", "rejection_reason")
    op.drop_column("orders", "rejected_at")
    op.drop_column("orders", "accepted_at")
    op.drop_column("orders", "delivery_fee")
    op.drop_column("orders", "delivery_area")
    op.drop_column("orders", "delivery_address")
    op.drop_column("orders", "service_type")
