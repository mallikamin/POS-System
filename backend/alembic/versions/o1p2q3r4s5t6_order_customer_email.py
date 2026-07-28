"""Store the customer's email on the order.

`POST /public/{tenant}/orders` has accepted `customer_email` since the public
ordering API was built, and then silently dropped it: `orders` had no column for
it and `_link_customer` never set `customers.email`. That was harmless while
nothing emailed anyone. It stops being harmless now that order confirmations are
sent, so the address has to be persisted where the order can find it.

Kept on the ORDER, not only on the customer, because it is the address the
person gave for *this* order. A customer who later updates their profile email
must not retroactively change where a past confirmation was sent, and guests are
linked to a customer row only when they supply a phone number.

Revision ID: o1p2q3r4s5t6
Revises: n0o1p2q3r4s5
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "o1p2q3r4s5t6"
down_revision: str | None = "n0o1p2q3r4s5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "customer_email",
            sa.String(length=320),
            nullable=True,
            comment="Email given at checkout; where order confirmations are sent",
        ),
    )


def downgrade() -> None:
    op.drop_column("orders", "customer_email")
