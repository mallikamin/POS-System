"""P2: discount approval threshold config

Revision ID: k7l8m9n0o1p2
Revises: j6k7l8m9n0o1
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa

revision = "k7l8m9n0o1p2"
down_revision = "j6k7l8m9n0o1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "restaurant_configs",
        sa.Column(
            "discount_approval_threshold_bps",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Percent threshold in basis points (0 = disabled)",
        ),
    )
    op.add_column(
        "restaurant_configs",
        sa.Column(
            "discount_approval_threshold_fixed",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Fixed amount threshold in paisa (0 = disabled)",
        ),
    )


def downgrade() -> None:
    op.drop_column("restaurant_configs", "discount_approval_threshold_fixed")
    op.drop_column("restaurant_configs", "discount_approval_threshold_bps")
