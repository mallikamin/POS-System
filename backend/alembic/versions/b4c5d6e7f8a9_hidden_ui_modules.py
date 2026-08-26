"""Per-tenant UI module visibility.

Adds `restaurant_configs.hidden_ui_modules`: a comma-separated list of UI module
slugs a tenant should not be shown, e.g. "dine-in,quickbooks-online".

⚠️ PRESENTATION ONLY. This is not an entitlement and not a security boundary.
It hides navigation entries and dashboard cards. Every admin endpoint in this
system is gated by ROLE and nothing else, so the routes behind a hidden module
remain reachable. The real per-tenant module gate is OI-93 and is not built.

Entirely additive and safe by construction: the column is NOT NULL with a server
default of the empty string, so every existing row gets "hide nothing", which is
precisely today's behaviour. No existing tenant's screens change as a result of
this migration. That property is the reason it can ship to a live shared server
during trading hours.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b4c5d6e7f8a9"
down_revision: str | None = "a3b4c5d6e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "restaurant_configs",
        sa.Column(
            "hidden_ui_modules",
            sa.String(length=500),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    op.drop_column("restaurant_configs", "hidden_ui_modules")
