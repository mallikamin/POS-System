"""Optional tip on online orders (OI-81).

Imran (2026-08-13): customers should be able to add a tip at checkout,
presets or a custom amount. Card orders charge order + tip in one Stripe
payment; cash orders carry the tip in the bill total and the rider or the
counter collects it.

One column only, on `orders`. No config column: the preset amounts are a
storefront concern, and the £20 server-side cap lives in the request schema
(`PublicOrderCreate.tip`), not in data. Snapshotted at creation like
`service_fee`, so nothing can rewrite the tip of an order already placed.
0 for every order predating this feature and for every non-online channel.

Revision ID: u7v8w9x0y1z2
Revises: t6u7v8w9x0y1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u7v8w9x0y1z2"
down_revision: str | None = "t6u7v8w9x0y1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "tip",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Tip in minor units, chosen by the customer at checkout. "
            "Included in `total`. Excluded from tax and from the delivery "
            "minimum. 0 = no tip.",
        ),
    )


def downgrade() -> None:
    op.drop_column("orders", "tip")
