"""Google Ads click id on the order (F34).

Until now nothing in our own data could answer "did the ad produce this sale?".
The browser conversion tag can only answer it when the customer accepted
cookies: a card order leaves the domain via `window.location.assign` for Stripe
Checkout and returns to a fixed `STRIPE_SUCCESS_URL`, so the click id is no
longer on the URL by the time the conversion fires, and `url_passthrough`
cannot survive that hop. Consent defaults to denied for UK PECR, so the common
case is an order that converted and cannot be proven to have converted.

Measured on 2026-08-27, the day the Search campaign went live: one click at
15:00-16:00 UK, one order at 16:51 from a customer with no prior row anywhere
in the history, and no way to join the two. GBP 2.28 of spend that could not be
justified to the client.

Storing the click id on the order makes that join a SELECT, independent of
cookies, of consent, of the Stripe redirect, and of Google reporting back. It
is also what an Offline Conversion Import needs, which is the proven pattern
from bilal-app (`gads_oci_export.py` + the /api/gads-click beacon).

Additive and safe by construction:

* Both columns are NULLABLE with no server default, so all 266 existing rows
  read NULL, which is the truthful value: those orders were placed before any
  click id was ever captured.
* Nothing reads these columns to decide anything operational. No order, ticket,
  receipt, payment or Stripe interaction consults them. A NULL is the norm --
  most orders are not from an ad -- so "absent" can never be an error state.
* `click_type` records which of the three Google parameters this is. `gbraid`
  and `wbraid` are the iOS/privacy-safe variants and are NOT interchangeable
  with `gclid` on upload, so the kind is stored rather than inferred from the
  value's shape.

NOT BACKFILLED, and unbackfillable. We never captured the data, so there is
nothing to backfill from. `260827-D001` in particular stays NULL: the
circumstantial case for it is strong but it is not a recorded fact, and writing
a guessed click id would turn an inference into false evidence.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: str | None = "c5d6e7f8a9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "gclid",
            sa.String(length=150),
            nullable=True,
            comment=(
                "Google Ads click id from the landing URL, if the order came from an ad"
            ),
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "click_type",
            sa.String(length=10),
            nullable=True,
            comment="One of gclid, gbraid, wbraid",
        ),
    )
    # Indexed because the only queries that will ever touch this column are
    # "which orders carry a click id" and the join that builds the offline
    # conversion upload. Both are sparse lookups over a table that is mostly
    # NULL here, which is exactly what an index is for.
    op.create_index("ix_orders_gclid", "orders", ["gclid"])


def downgrade() -> None:
    op.drop_index("ix_orders_gclid", table_name="orders")
    op.drop_column("orders", "click_type")
    op.drop_column("orders", "gclid")
