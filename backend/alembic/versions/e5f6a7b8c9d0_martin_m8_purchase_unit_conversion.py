"""Martin M8: two units and a conversion on bought ingredients.

Martin Zubeldia (FZ LLC), 2026-09-04:

    "Ingredients bought Need to have 2 units and a conversion. The unit you
     buy, the unit you store) use in recipes ... I buy tomato cans..so in the
     purchase order I will request 2 cans. But in my recipes I use grams"

`ingredients.unit` keeps its meaning: the stocking unit, the one recipes spend
and stock on hand counts. Three columns are added beside it for what the
supplier sells.

**This migration moves no existing data.** Every row lands on
`purchase_unit = NULL` and `units_per_purchase_unit = 1`, which is exactly the
behaviour before the change: bought in the unit it is stocked in. Costs,
recipes, stock levels and open purchase orders are untouched.

The two snapshot columns on `purchase_order_items` and `goods_receipt_lines`
default to 1 for the same reason. A purchase order raised before today
described whole units, and it must keep describing whole units after it.

Revision ID: e5f6a7b8c9d0
Revises: d2e3f4a5b6c7
Create Date: 2026-09-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- ingredients: what we buy, beside what we store -------------------
    op.add_column(
        "ingredients",
        sa.Column("purchase_unit", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "ingredients",
        sa.Column(
            "units_per_purchase_unit",
            sa.Numeric(12, 4),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "ingredients",
        sa.Column(
            "purchase_cost_minor",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        "ck_ingredient_purchase_conversion_positive",
        "ingredients",
        "units_per_purchase_unit > 0",
    )

    # An ingredient bought and stocked in the same unit is priced per that
    # unit, so seeding the purchase price from the existing cost keeps the
    # two in agreement from the first render of the new form. Produced
    # ingredients keep 0: they are not bought at all.
    op.execute(
        """
        UPDATE ingredients
           SET purchase_cost_minor = cost_per_unit
         WHERE is_produced = false
        """
    )

    # ---- cost rates get two more decimal places ---------------------------
    # A rate is not a price. 8.50 AED for a 400 g can is 2.125 fils a gram,
    # and at two decimal places that rounds to 2.13, restating the can at
    # 8.52. Widening the scale is lossless in Postgres -- every stored value
    # is representable in the wider type, so no row changes and no data is
    # rewritten. Money actually charged keeps two places.
    op.alter_column(
        "ingredients",
        "cost_per_unit",
        existing_type=sa.Numeric(10, 2),
        type_=sa.Numeric(12, 4),
        existing_nullable=False,
    )
    op.alter_column(
        "recipe_items",
        "cost_per_unit_snapshot",
        existing_type=sa.Numeric(10, 2),
        type_=sa.Numeric(12, 4),
        existing_nullable=False,
    )
    op.alter_column(
        "inventory_transactions",
        "unit_cost",
        existing_type=sa.Numeric(10, 2),
        type_=sa.Numeric(12, 4),
        existing_nullable=False,
    )
    op.alter_column(
        "inventory_transactions",
        "total_cost",
        existing_type=sa.Numeric(10, 2),
        type_=sa.Numeric(12, 2),
        existing_nullable=False,
    )

    # ---- procurement lines: snapshot the conversion -----------------------
    op.add_column(
        "purchase_order_items",
        sa.Column(
            "units_per_purchase_unit",
            sa.Numeric(12, 4),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "goods_receipt_lines",
        sa.Column(
            "units_per_purchase_unit",
            sa.Numeric(12, 4),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    # Narrowing IS lossy -- Postgres rounds every rate back to two places and
    # the fractions are gone for good. Kept only so the chain is reversible;
    # take a dump first, as `data-integrity.md` requires of any downgrade.
    op.alter_column(
        "inventory_transactions",
        "total_cost",
        existing_type=sa.Numeric(12, 2),
        type_=sa.Numeric(10, 2),
        existing_nullable=False,
    )
    op.alter_column(
        "inventory_transactions",
        "unit_cost",
        existing_type=sa.Numeric(12, 4),
        type_=sa.Numeric(10, 2),
        existing_nullable=False,
    )
    op.alter_column(
        "recipe_items",
        "cost_per_unit_snapshot",
        existing_type=sa.Numeric(12, 4),
        type_=sa.Numeric(10, 2),
        existing_nullable=False,
    )
    op.alter_column(
        "ingredients",
        "cost_per_unit",
        existing_type=sa.Numeric(12, 4),
        type_=sa.Numeric(10, 2),
        existing_nullable=False,
    )
    op.drop_column("goods_receipt_lines", "units_per_purchase_unit")
    op.drop_column("purchase_order_items", "units_per_purchase_unit")
    op.drop_constraint(
        "ck_ingredient_purchase_conversion_positive", "ingredients", type_="check"
    )
    op.drop_column("ingredients", "purchase_cost_minor")
    op.drop_column("ingredients", "units_per_purchase_unit")
    op.drop_column("ingredients", "purchase_unit")
