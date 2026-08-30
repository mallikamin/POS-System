"""Cookie-banner choice on the order, so the upload decision has evidence.

F34 gave us the click id. This gives us the permission question that sits next
to it, and the two are only useful together.

Why it exists. On 2026-08-29 Chick Shack took a real order carrying a real
`gclid` (`260829-D005`, GBP 29.47, 17:20 UK). Google Ads reported ZERO
conversions for that day once it had closed. Nothing is broken: `index.html`
defaults consent to denied for UK PECR and sets `ads_data_redaction`, which
strips the click identifier from the ping when `ad_storage` is denied. A
customer who does not tap Allow is therefore invisible to the browser tag by
design.

That leaves an offline upload from our own `orders.gclid` as the only reliable
route -- and immediately raises a question we could not answer: may we upload a
click id belonging to someone who declined advertising cookies? Technically yes,
we hold it independently of Google. Legally that is a different question under
UK PECR/GDPR, and it should be settled on data rather than on whichever answer
is convenient on the day.

So: record the answer at the moment of the order, and record it for EVERY order
rather than only the ad ones. The denominator is the point. "How many of our
customers decline?" is what says how much the browser tag is structurally
missing, and it cannot be reconstructed later.

Three states, all meaningful:

* ``granted``  -- the customer tapped Allow on that device.
* ``denied``   -- the customer actively declined.
* ``NULL``     -- the banner was never answered, or the order predates this
                  column. NOT the same as ``denied``, and must never be
                  collapsed into it when the upload list is built.

Additive and safe by construction. Nullable, no server default, no backfill.
Nothing operational reads it: no order, ticket, receipt, payment or Stripe
interaction consults this column, so an absent value can never be an error
state. Existing rows read NULL, which is the truthful value -- the choice was
not recorded when they were placed.

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9b0c1d2e3f4"
down_revision: str | None = "f8a9b0c1d2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "ads_consent",
            sa.String(length=10),
            nullable=True,
            comment=(
                "granted or denied on the cookie banner when the order was placed"
            ),
        ),
    )
    # Deliberately NOT indexed, unlike `gclid`. This column is read in exactly
    # one place -- a periodic aggregate over the whole table when the upload
    # list is assembled -- which is a sequential scan either way. An index here
    # would cost every insert on the hot ordering path and buy nothing.


def downgrade() -> None:
    op.drop_column("orders", "ads_consent")
