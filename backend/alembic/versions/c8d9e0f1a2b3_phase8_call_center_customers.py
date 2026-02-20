"""phase8_call_center_customers

Revision ID: c8d9e0f1a2b3
Revises: 4f7e5a9c1b21
Create Date: 2026-02-20 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "4f7e5a9c1b21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False, comment="Normalized phone (digits only)"),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("default_address", sa.Text(), nullable=True, comment="Primary delivery address"),
        sa.Column("notes", sa.Text(), nullable=True, comment="Internal notes"),
        sa.Column("order_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "phone", name="uq_customer_tenant_phone"),
    )
    op.create_index("ix_customers_tenant_phone", "customers", ["tenant_id", "phone"])
    op.create_index("ix_customers_tenant_name", "customers", ["tenant_id", "name"])

    # Optional: add pg_trgm GIN index for fast partial phone search in Postgres
    # op.execute(
    #     "CREATE INDEX ix_customers_phone_trgm ON customers "
    #     "USING gin (phone gin_trgm_ops)"
    # )


def downgrade() -> None:
    op.drop_index("ix_customers_tenant_name", table_name="customers")
    op.drop_index("ix_customers_tenant_phone", table_name="customers")
    op.drop_table("customers")
