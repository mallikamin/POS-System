"""restaurant_configs.theme: optional per-tenant visual identity

Additive and nullable on purpose. Every existing row gets NULL, the frontend
stamps no theme attribute for NULL, and the standard palette applies. No tenant
changes appearance because this column exists; a tenant changes appearance only
when someone writes a theme name into its row.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7f8a9b0c1d2"
down_revision: str | None = "d6e7f8a9b0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "restaurant_configs",
        sa.Column("theme", sa.String(length=40), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("restaurant_configs", "theme")
