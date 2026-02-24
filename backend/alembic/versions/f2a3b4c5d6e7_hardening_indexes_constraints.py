"""hardening_indexes_constraints

Add partial unique index for single open cash drawer per tenant,
and add missing indexes on orders.created_by and orders.customer_phone.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-02-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Partial unique index: only one open cash drawer per tenant
    op.execute(
        "CREATE UNIQUE INDEX uix_one_open_drawer_per_tenant "
        "ON cash_drawer_sessions (tenant_id) WHERE status = 'open'"
    )

    # Missing indexes from DB audit
    op.create_index("ix_orders_created_by", "orders", ["created_by"])
    op.create_index("ix_orders_customer_phone", "orders", ["customer_phone"])


def downgrade() -> None:
    op.drop_index("ix_orders_customer_phone", table_name="orders")
    op.drop_index("ix_orders_created_by", table_name="orders")
    op.execute("DROP INDEX IF EXISTS uix_one_open_drawer_per_tenant")
