"""Danny's D-104: carry a table-level discount into the table's orders.

* `orders.session_discount_share`: this bill's share of the table (session)
  discount, included in `discount_amount` and therefore in `total`. Default 0,
  so no existing order changes value.

Existing open tables with a table discount get their shares the next time the
table is paid or its discounts change (`allocate_session_discounts`).

Revision ID: a104d5e6f7b8
Revises: e8b1f4c2a9d3
Create Date: 2026-10-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a104d5e6f7b8"
down_revision = "e8b1f4c2a9d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column(
        "session_discount_share", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("orders", "session_discount_share")
