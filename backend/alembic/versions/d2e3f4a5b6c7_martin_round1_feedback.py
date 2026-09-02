"""Martin's round-1 feedback (FZ LLC, 2026-09-02): four small columns.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-09-03

⚠️ Parented on `c1d2e3f4a5b6` (recipe modifier target), which is production's
head. The Meta pixel migration `b0c1d2e3f4a5` is still uncommitted and
undeployed; its local copy has been re-parented onto THIS revision so the
working tree keeps a single head. Whoever ships Meta keeps that parent.

What Martin asked for, and what each column answers:

* ``restaurant_configs.receipt_format`` -- "option to either print a vertical
  receipt or an A4 format". ``thermal`` (80mm roll, today's behaviour) or
  ``a4``. Presentation only; the receipt data is identical either way.
* ``restaurant_configs.takeaway_label`` -- "there is only option for take away
  or call center. there should be pick up / ...". The walk-in channel keeps its
  ``takeaway`` order_type (reports, kitchen tickets and the state machine all
  key on it) but the tile and header can read "Pick up" for a tenant that
  says pick up. NULL keeps "Takeaway" for everyone else.
* ``sales_channels.pos_visible`` -- Deliveroo / Careem / Keeta / Noon are
  sales channels (they carry a commission, which is the whole point of the
  profitability report), not order types. This flag puts a channel on the
  POS channel selector as its own tile. Defaults true so Martin's existing
  aggregator channels appear at once; the website channel is switched off
  because those orders arrive through the storefront, not the till.
* ``customers.company_name`` and ``customers.trn`` -- "crm options (where i
  can add customer name/phone/contact details/ trn if it is a company)". The
  TRN is what turns a receipt to a company into a tax invoice the buyer can
  reclaim VAT against.

All additive: nullable or server-defaulted, no backfill beyond the two
tenant-specific data rows, so no existing tenant's behaviour changes until
someone edits a setting.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "restaurant_configs",
        sa.Column(
            "receipt_format",
            sa.String(length=10),
            nullable=False,
            server_default="thermal",
            comment="How the browser receipt prints: 'thermal' (80mm roll) "
            "or 'a4'. Presentation only.",
        ),
    )
    op.add_column(
        "restaurant_configs",
        sa.Column(
            "takeaway_label",
            sa.String(length=40),
            nullable=True,
            comment="Display name for the walk-in (takeaway) channel, e.g. "
            "'Pick up'. NULL means 'Takeaway'. The order_type stays 'takeaway'.",
        ),
    )
    op.add_column(
        "sales_channels",
        sa.Column(
            "pos_visible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
            comment="Show this channel as its own tile on the POS channel "
            "selector. Off for channels whose orders never start at the till.",
        ),
    )
    op.add_column(
        "customers",
        sa.Column(
            "company_name",
            sa.String(length=255),
            nullable=True,
            comment="Legal/trading name when the customer is a business.",
        ),
    )
    op.add_column(
        "customers",
        sa.Column(
            "trn",
            sa.String(length=50),
            nullable=True,
            comment="Customer's Tax Registration Number (UAE TRN or local "
            "equivalent), printed on tax invoices issued to them.",
        ),
    )

    # Tenant-specific data, both scoped by slug / code so nobody else moves.
    op.execute(
        """
        UPDATE restaurant_configs
        SET takeaway_label = 'Pick up'
        WHERE tenant_id IN (SELECT id FROM tenants WHERE slug = 'martin-fz')
        """
    )
    op.execute(
        """
        UPDATE sales_channels
        SET pos_visible = false
        WHERE code = 'website'
        """
    )


def downgrade() -> None:
    op.drop_column("customers", "trn")
    op.drop_column("customers", "company_name")
    op.drop_column("sales_channels", "pos_visible")
    op.drop_column("restaurant_configs", "takeaway_label")
    op.drop_column("restaurant_configs", "receipt_format")
