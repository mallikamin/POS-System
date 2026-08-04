"""Per-tenant switch to stop taking online orders during a rush.

Imran (via Malik, 2026-08-04): during a rush he wants one button that stops
online ordering -- collection AND delivery together -- and resumes it just as
cleanly. While it is off the customer must not be able to place an order at
all; the storefront tells them to phone the shop instead.

Modelled as a per-tenant boolean on `restaurant_configs`, defaulting to
`false`, so no existing tenant's behaviour changes on deploy. Deliberately NOT
a storefront-only flag: `create_public_order` refuses while it is set, because
a client-side check is a suggestion, not a rule (the lesson from OI-61/OI-65 --
see `app/services/order_visibility.py`).

Orders attempted while paused are lost by design, per Malik's explicit
instruction: the point is to divert customers to the phone, and a queue of
orders landing the moment the shop unpauses would defeat that.

Revision ID: s5t6u7v8w9x0
Revises: r4s5t6u7v8w9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "s5t6u7v8w9x0"
down_revision: str | None = "r4s5t6u7v8w9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "restaurant_configs",
        sa.Column(
            "online_ordering_paused",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="When true the storefront stops taking online orders "
            "(collection and delivery both) and tells customers to phone the "
            "shop. Enforced server-side in create_public_order, not just in "
            "the UI.",
        ),
    )


def downgrade() -> None:
    op.drop_column("restaurant_configs", "online_ordering_paused")
