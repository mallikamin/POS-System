"""Customer enhancements: alt contact, address/city split, risk flag, stats

Revision ID: g3h4i5j6k7l8
Revises: f2a3b4c5d6e7
Create Date: 2026-02-26
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "g3h4i5j6k7l8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("alt_contact", sa.String(50), nullable=True))
    op.add_column("customers", sa.Column("city", sa.String(100), nullable=True))
    op.add_column("customers", sa.Column("alt_address", sa.Text(), nullable=True))
    op.add_column("customers", sa.Column("alt_city", sa.String(100), nullable=True))
    op.add_column(
        "customers",
        sa.Column("total_spent", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "customers",
        sa.Column("last_order_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("risk_flag", sa.String(20), nullable=False, server_default="normal"),
    )


def downgrade() -> None:
    op.drop_column("customers", "risk_flag")
    op.drop_column("customers", "last_order_at")
    op.drop_column("customers", "total_spent")
    op.drop_column("customers", "alt_city")
    op.drop_column("customers", "alt_address")
    op.drop_column("customers", "city")
    op.drop_column("customers", "alt_contact")
