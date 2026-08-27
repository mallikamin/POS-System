"""Reserved, immutable tax invoice numbers (F33).

The number was previously derived from a live COUNT of the tenant's orders, so
it was neither unique nor stable. Measured on production before this migration,
across twelve completed orders for one tenant:

    260827-001/002/003  -> INV-00012   (all three)
    FZ-0001 .. FZ-0007  -> FZD-00007   (all seven)
    FZ-0008, FZ-0009    -> FZW-00002   (both)
    distinct invoice numbers: 3 for 12 orders

Seven separate sales shared one document number, and every number moved upward
as new orders arrived. A UAE tax invoice must carry a sequential number that
uniquely identifies the document, so the number now has to be reserved at first
issue and stored.

Additive and safe by construction:

* `orders.tax_invoice_number` is NULLABLE with no server default, so every
  existing row reads NULL, meaning "never issued as a tax invoice" -- which is
  true of every order in the system today, because no number was ever stored.
* The unique constraint is on `(tenant_id, tax_invoice_number)`. NULLs are
  distinct in Postgres, so unissued orders never collide with one another.
* `tax_invoice_sequences` is a new empty table. A series is created lazily on
  its first issue.

DELIBERATELY NOT BACKFILLED. Assigning a number to an order that was never
issued as an invoice would be inventing a document that does not exist, and it
would write to 233 rows of a live trading tenant for no benefit -- they have a
zero VAT rate and have never opened the A4 invoice. Numbers are handed out on
first issue, which is what an invoice sequence actually does.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5d6e7f8a9b0"
down_revision: str | None = "b4c5d6e7f8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "tax_invoice_number",
            sa.String(length=40),
            nullable=True,
            comment="Immutable tax invoice number, assigned at first issue",
        ),
    )
    op.create_unique_constraint(
        "uq_order_tenant_tax_invoice_number",
        "orders",
        ["tenant_id", "tax_invoice_number"],
    )

    op.create_table(
        "tax_invoice_sequences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("prefix", sa.String(length=10), nullable=False),
        sa.Column("next_value", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "prefix", name="uq_tax_invoice_seq_tenant_prefix"
        ),
    )
    op.create_index(
        "ix_tax_invoice_sequences_tenant_id",
        "tax_invoice_sequences",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_tax_invoice_sequences_tenant_id", "tax_invoice_sequences")
    op.drop_table("tax_invoice_sequences")
    op.drop_constraint("uq_order_tenant_tax_invoice_number", "orders", type_="unique")
    op.drop_column("orders", "tax_invoice_number")
