"""Add payment-mode tax rate columns to restaurant_configs

Revision ID: h4i5j6k7l8m9
Revises: g3h4i5j6k7l8
Create Date: 2026-03-03
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "h4i5j6k7l8m9"
down_revision: Union[str, None] = "g3h4i5j6k7l8"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "restaurant_configs",
        sa.Column(
            "cash_tax_rate_bps",
            sa.Integer(),
            nullable=False,
            server_default="1600",
            comment="Tax rate for cash payments in basis points (1600 = 16%)",
        ),
    )
    op.add_column(
        "restaurant_configs",
        sa.Column(
            "card_tax_rate_bps",
            sa.Integer(),
            nullable=False,
            server_default="500",
            comment="Tax rate for card payments in basis points (500 = 5%)",
        ),
    )


def downgrade() -> None:
    op.drop_column("restaurant_configs", "card_tax_rate_bps")
    op.drop_column("restaurant_configs", "cash_tax_rate_bps")
