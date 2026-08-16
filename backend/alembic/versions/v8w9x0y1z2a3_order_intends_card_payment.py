"""Record the customer's card intent at order creation (OI-84).

Revision ID: v8w9x0y1z2a3
Revises: u7v8w9x0y1z2
Create Date: 2026-08-16

Why this column exists
----------------------
The storefront places a card order in two requests: the first creates and
COMMITS the row, the second sets `stripe_checkout_session_id` about 0.3s later.
Everything that asked "is this a card order?" read the session id, so during
that gap a card order was indistinguishable from cash on delivery. It surfaced
on the tablet and chimed, vanished when the session id landed, and reappeared
~30s later when Stripe authorised. Worse, `accept_order`'s money guard was keyed
on the same field, so an order caught in the gap could be accepted as cash --
kitchen committed, no authorisation checked, no capture ever attempted.

The backfill is deliberately `stripe_checkout_session_id IS NOT NULL`, which is
exactly the old inference. Every existing row therefore keeps the visibility and
payment wording it already had, and no historical order changes meaning.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v8w9x0y1z2a3"
down_revision: str | None = "u7v8w9x0y1z2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "intends_card_payment",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment=(
                "Customer chose to pay by card at checkout. Set at creation, "
                "before Stripe exists."
            ),
        ),
    )
    # Reproduce the old inference for existing rows, so nothing in history
    # changes visibility or payment wording.
    op.execute(
        """
        UPDATE orders
        SET intends_card_payment = true
        WHERE stripe_checkout_session_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("orders", "intends_card_payment")
