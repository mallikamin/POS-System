"""Flat per-order service fee, itemised separately from delivery.

Imran (voice note, 2026-08-02): wants a flat 70p added to every order --
collection and delivery alike -- to offset the ~£0.72 Stripe processing fee
shown on a real captured payment. Modelled the same way `delivery_fee`
already is: a per-tenant amount on `restaurant_configs` (0 for every tenant
but Chick Shack, so this cannot silently affect anyone else), snapshotted
onto the order at creation time as `orders.service_fee` so a later config
change never rewrites the total of an order already placed.

Revision ID: r4s5t6u7v8w9
Revises: q3r4s5t6u7v8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "r4s5t6u7v8w9"
down_revision: str | None = "q3r4s5t6u7v8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "restaurant_configs",
        sa.Column(
            "service_fee",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Flat service fee in minor units, added to every online "
            "order regardless of payment method. 0 = disabled.",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "service_fee",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Service fee in minor units, snapshotted from the "
            "tenant's config at order creation. 0 for orders predating "
            "this feature and for tenants that don't charge one.",
        ),
    )
    op.execute(
        """
        UPDATE restaurant_configs
        SET service_fee = 70
        WHERE tenant_id IN (SELECT id FROM tenants WHERE slug = 'chick-shack')
        """
    )


def downgrade() -> None:
    op.drop_column("orders", "service_fee")
    op.drop_column("restaurant_configs", "service_fee")
