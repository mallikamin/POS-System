"""Loyalty cards in Google Wallet: remember which guests were given a card.

* `loyalty_wallet_passes`: one row per guest per wallet (platform 'google'),
  written when the guest is handed an "Add to Google Wallet" link. Each counted
  visit then pushes the new count to that card. UNIQUE(customer_id, platform).

New table only. Nothing existing is altered.

Revision ID: f3a9c1d7e5b2
Revises: c107e2a5b9d1
Create Date: 2026-10-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f3a9c1d7e5b2"
down_revision = "c107e2a5b9d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "loyalty_wallet_passes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=True),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("platform", sa.String(length=10), nullable=False),
        sa.Column("object_id", sa.String(length=120), nullable=False),
        sa.UniqueConstraint("customer_id", "platform",
                            name="uq_loyalty_wallet_pass_customer_platform"),
    )
    op.create_index("ix_loyalty_wallet_passes_tenant_id", "loyalty_wallet_passes", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_loyalty_wallet_passes_tenant_id", table_name="loyalty_wallet_passes")
    op.drop_table("loyalty_wallet_passes")
