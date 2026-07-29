"""Per-tenant flag for shops that take orders only from their website.

Raised by Imran's live walkthrough on 2026-07-29 (OI-54): his tablet lands on
"Select Order Channel — Dine-In / Takeaway / Call Center", and all three are
dead ends for Chick Shack, which takes orders only from chickshackg84.com. The
flag sends such a tenant straight to the online-orders queue instead.

Per-tenant on purpose: the core POS keeps all channels for every other tenant.

The backfill flips the flag for the `chick-shack` tenant here rather than in a
manual server step, because "merge to main" is the whole deploy and a manual
step is a step that gets forgotten. Idempotent, keyed on the tenant slug, and a
no-op on databases that have no such tenant (local demo, CI).

Revision ID: q3r4s5t6u7v8
Revises: p2q3r4s5t6u7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "q3r4s5t6u7v8"
down_revision: str | None = "p2q3r4s5t6u7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "restaurant_configs",
        sa.Column(
            "online_ordering_only",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="True for a shop that takes orders ONLY from its website: "
            "the POS lands on the online-orders queue and hides the "
            "dine-in/takeaway/call-center channels.",
        ),
    )
    op.execute(
        """
        UPDATE restaurant_configs
        SET online_ordering_only = TRUE
        WHERE tenant_id IN (SELECT id FROM tenants WHERE slug = 'chick-shack')
        """
    )


def downgrade() -> None:
    op.drop_column("restaurant_configs", "online_ordering_only")
