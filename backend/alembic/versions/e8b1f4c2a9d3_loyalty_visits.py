"""Danny's D-99: visit-based loyalty (stamp card), one visit per paid bill.

* `restaurant_configs`: loyalty_enabled (default false), loyalty_visits_required
  (default 5), loyalty_reward_menu_item_id, loyalty_reward_label,
  loyalty_max_visits_per_day (default 1, 0 = no limit; the owner's setting).
* `orders.loyalty_code`: the one-time code behind the QR on the bill, the
  receipt and the counter display. Set at creation only when loyalty is on.
* `loyalty_visits`: the ledger. UNIQUE(order_id) = one visit per bill, however
  it is claimed (cashier, receipt QR, counter QR), so a race between the
  cashier and a scan cannot double-count. The per-day limit is a setting, so
  it is enforced in the service (customer row lock), not by a constraint.
* `loyalty_redemptions`: each reward given, tied to the discount line it made.

Every new config column defaults to "off", so no tenant changes until an admin
switches loyalty on. Nothing existing is altered.

Revision ID: e8b1f4c2a9d3
Revises: d97a5c0e1b2f
Create Date: 2026-10-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e8b1f4c2a9d3"
down_revision = "d97a5c0e1b2f"
branch_labels = None
depends_on = None


def _base_cols() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=True),
    ]


def upgrade() -> None:
    op.add_column("restaurant_configs", sa.Column(
        "loyalty_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("restaurant_configs", sa.Column(
        "loyalty_visits_required", sa.Integer(), nullable=False, server_default="5"))
    op.add_column("restaurant_configs", sa.Column(
        "loyalty_reward_menu_item_id", sa.Uuid(), sa.ForeignKey("menu_items.id",
                                                                ondelete="SET NULL"),
        nullable=True))
    op.add_column("restaurant_configs", sa.Column(
        "loyalty_reward_label", sa.String(length=80), nullable=True))
    op.add_column("restaurant_configs", sa.Column(
        "loyalty_max_visits_per_day", sa.Integer(), nullable=False, server_default="1"))

    op.add_column("orders", sa.Column("loyalty_code", sa.String(length=16), nullable=True))
    op.create_index("ix_orders_loyalty_code", "orders", ["loyalty_code"], unique=True)

    op.create_table(
        "loyalty_visits",
        *_base_cols(),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("visit_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.UniqueConstraint("order_id", name="uq_loyalty_visit_order"),
    )
    op.create_index("ix_loyalty_visits_tenant_customer_date", "loyalty_visits",
                    ["tenant_id", "customer_id", "visit_date"])

    op.create_table(
        "loyalty_redemptions",
        *_base_cols(),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("order_discount_id", sa.Uuid(),
                  sa.ForeignKey("order_discounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("redeemed_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("order_id", name="uq_loyalty_redemption_order"),
    )
    op.create_index("ix_loyalty_redemptions_tenant_customer", "loyalty_redemptions",
                    ["tenant_id", "customer_id"])


def downgrade() -> None:
    op.drop_index("ix_loyalty_redemptions_tenant_customer", table_name="loyalty_redemptions")
    op.drop_table("loyalty_redemptions")
    op.drop_index("ix_loyalty_visits_tenant_customer_date", table_name="loyalty_visits")
    op.drop_table("loyalty_visits")
    op.drop_index("ix_orders_loyalty_code", table_name="orders")
    op.drop_column("orders", "loyalty_code")
    op.drop_column("restaurant_configs", "loyalty_max_visits_per_day")
    op.drop_column("restaurant_configs", "loyalty_reward_label")
    op.drop_column("restaurant_configs", "loyalty_reward_menu_item_id")
    op.drop_column("restaurant_configs", "loyalty_visits_required")
    op.drop_column("restaurant_configs", "loyalty_enabled")
