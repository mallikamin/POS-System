"""Danny's D-97: percentage service charge on the bill.

Adds two config columns and two order columns, all NOT NULL with a server
default, so every existing row reads as "no service charge" and **nothing
existing changes**: a tenant's totals only move once an admin sets a rate.

* `restaurant_configs.service_charge_bps`       rate in basis points, 0 = off
* `restaurant_configs.service_charge_dine_in_only`  default true
* `orders.service_charge`                       amount in minor units
* `orders.service_charge_bps`                   rate snapshotted on the order

Deliberately separate from `service_fee` (Chick Shack's flat online "Platform
Fee", charged outside tax). A Punjab service charge is part of the taxable
value (PRA Restaurant Services Rules 2012), so it is taxed; see
`order_service.taxable_base`.

Revision ID: d97a5c0e1b2f
Revises: d4e5f6a7b8c9
Create Date: 2026-10-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d97a5c0e1b2f"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "restaurant_configs",
        sa.Column("service_charge_bps", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "restaurant_configs",
        sa.Column(
            "service_charge_dine_in_only",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "orders",
        sa.Column("service_charge", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "orders",
        sa.Column("service_charge_bps", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("orders", "service_charge_bps")
    op.drop_column("orders", "service_charge")
    op.drop_column("restaurant_configs", "service_charge_dine_in_only")
    op.drop_column("restaurant_configs", "service_charge_bps")
