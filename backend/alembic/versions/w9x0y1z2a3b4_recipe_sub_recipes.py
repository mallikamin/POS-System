"""Multi-layer recipes: a recipe can produce an ingredient, not just a menu item.

Revision ID: w9x0y1z2a3b4
Revises: v8w9x0y1z2a3
Create Date: 2026-08-26

Why this exists
----------------
FZ LLC (UAE bakery/restaurant lead, `_context/clients/fz-llc-uae/`) needs raw
ingredients -> sub-recipe (dough, sauce, stuffing) -> intermediate -> final
menu item production chains, not just a single ingredient list per menu item.

`recipes.menu_item_id` was NOT NULL, so a recipe could only ever produce a
sellable menu item. This adds `produces_ingredient_id` as an alternative
target: a recipe can now produce an `Ingredient` instead, which other recipes
then consume as an ordinary `RecipeItem` line. Exactly one of the two targets
must be set (enforced by `ck_recipe_exactly_one_target`), so every existing
recipe row (all of which have `menu_item_id` set, `produces_ingredient_id`
NULL) already satisfies the new constraint with no backfill needed.

`ingredients.is_produced` is a plain informational flag (purchased vs.
made in-house); it does not change how cost_per_unit is stored, only who
is expected to keep it in sync (recipe_service.sync_produced_ingredient_cost
for produced ingredients, manual entry for purchased ones).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "w9x0y1z2a3b4"
down_revision: str | None = "v8w9x0y1z2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ingredients",
        sa.Column(
            "is_produced",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Made in-house via a Recipe, not purchased.",
        ),
    )

    op.alter_column(
        "recipes",
        "menu_item_id",
        existing_type=postgresql.UUID(),
        nullable=True,
    )
    op.add_column(
        "recipes",
        sa.Column(
            "produces_ingredient_id",
            postgresql.UUID(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_recipe_produces_ingredient",
        "recipes",
        "ingredients",
        ["produces_ingredient_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_recipe_tenant_produces_ingredient",
        "recipes",
        ["tenant_id", "produces_ingredient_id"],
    )
    op.create_check_constraint(
        "ck_recipe_exactly_one_target",
        "recipes",
        "(menu_item_id IS NOT NULL) != (produces_ingredient_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_recipe_exactly_one_target", "recipes", type_="check")
    op.drop_constraint(
        "uq_recipe_tenant_produces_ingredient", "recipes", type_="unique"
    )
    op.drop_constraint(
        "fk_recipe_produces_ingredient", "recipes", type_="foreignkey"
    )
    op.drop_column("recipes", "produces_ingredient_id")
    op.alter_column(
        "recipes",
        "menu_item_id",
        existing_type=postgresql.UUID(),
        nullable=False,
    )
    op.drop_column("ingredients", "is_produced")
