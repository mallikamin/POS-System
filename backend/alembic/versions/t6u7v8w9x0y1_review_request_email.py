"""Claim column for the "how did we do" review-request email.

Malik (2026-08-10), from Imran's Google review QR: send every online customer a
short email asking for a Google review, three hours after the kitchen accepts
their order.

Why a timestamp on `orders` rather than a log table or a scheduler:

* **It is a CLAIM, not a record.** The backend runs `--workers 4`, so four
  processes sweep for due orders at the same moment. The sweep takes an order
  with `UPDATE ... WHERE review_email_sent_at IS NULL`, which makes the
  database pick exactly one winner. A read-then-send would let two workers both
  decide an order was unsent and email the customer twice. This is the same
  pattern `payment_authorized_at` uses for card publication (OI-65).
* **Anchored on acceptance, not placement.** A pre-order placed at 14:00 is not
  accepted until the shop opens at 16:00, and the food only exists after
  acceptance. `accepted_at + 3h` is the honest "they have eaten by now" mark.
* Nullable with no server default, so every existing order is treated as
  "never sent". The sweep's own age cutoff, not this column, is what stops
  history being emailed on deploy.

Revision ID: t6u7v8w9x0y1
Revises: s5t6u7v8w9x0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "t6u7v8w9x0y1"
down_revision: str | None = "s5t6u7v8w9x0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Per-tenant, never hardcoded. A review link belongs to one restaurant's
    # Google Business Profile, so baking Chick Shack's into the shared email
    # service would be OI-73's hardcoded "(PKR)" in a new costume -- and would
    # send Cosa Nostra's customers to a chicken shop in Garelochhead.
    #
    # It doubles as the feature switch: no URL, no review email. So this
    # migration is inert on deploy and the feature turns on for exactly the
    # tenant whose URL is filled in.
    op.add_column(
        "restaurant_configs",
        sa.Column(
            "google_review_url",
            sa.String(500),
            nullable=True,
            comment="This tenant's Google 'write a review' link. NULL means "
            "the review-request email is switched off for this tenant.",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "review_email_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Set when the review-request email is sent. This is the "
            "claim the sweep competes on (conditional UPDATE guarded on it "
            "being NULL), so four workers cannot double-email one customer.",
        ),
    )
    # The sweep runs on a timer and asks the same question every time: which
    # online orders are accepted, not yet asked, and old enough? Without this
    # it is a full scan of `orders`, which only grows.
    op.create_index(
        "ix_orders_review_email_due",
        "orders",
        ["tenant_id", "accepted_at"],
        unique=False,
        postgresql_where=sa.text("review_email_sent_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_orders_review_email_due", table_name="orders")
    op.drop_column("orders", "review_email_sent_at")
    op.drop_column("restaurant_configs", "google_review_url")
