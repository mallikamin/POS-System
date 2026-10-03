"""Separate the review email's switch from the Google review link.

* `restaurant_configs.review_email_enabled`: the online review-request email
  now needs this opt-in AND `google_review_url`. Until now the link alone
  switched the email on, so a restaurant could not show a review QR (counter
  screen, D-107) without also emailing customers.

Every tenant that already has a link keeps its email (flag set true), so no
behaviour changes on deploy. Every other tenant: false.

Revision ID: c107e2a5b9d1
Revises: a104d5e6f7b8
Create Date: 2026-10-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c107e2a5b9d1"
down_revision = "a104d5e6f7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("restaurant_configs", sa.Column(
        "review_email_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute(
        "UPDATE restaurant_configs SET review_email_enabled = true "
        "WHERE google_review_url IS NOT NULL AND btrim(google_review_url) <> ''"
    )


def downgrade() -> None:
    op.drop_column("restaurant_configs", "review_email_enabled")
