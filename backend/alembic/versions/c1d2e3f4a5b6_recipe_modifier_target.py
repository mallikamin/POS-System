"""A recipe can be attached to a modifier (OI-99)

Revision ID: c1d2e3f4a5b6
Revises: a9b0c1d2e3f4
Create Date: 2026-09-01

⚠️ Parented on `a9b0c1d2e3f4` (ads consent), NOT on the Meta pixel migration
`b0c1d2e3f4a5`, which is written but uncommitted and deliberately undeployed
(no pixel id, no access token). Production's head was `a9b0c1d2e3f4` when this
was written, verified on the box, so parenting on the Meta revision would have
left alembic unable to locate the parent and the backend unable to start.
**Whoever ships the Meta pixel work must re-parent `b0c1d2e3f4a5` onto this
revision.**

Martin Zubeldia (FZ LLC) found this in his own UAT: a recipe could only be
attached to a menu item or to the ingredient it produces. There was no way to
say what a paid add-on is made of, so an add-on moved no stock and carried no
cost, which overstated the margin on every modified line.

`modifier_id` becomes a third permitted target. The old check constraint was an
XOR of two columns; it is replaced by a "exactly one of three is not null"
count, which every existing row already satisfies (all live recipes have
`menu_item_id` or `produces_ingredient_id` set, never both, never neither), so
there is no backfill.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "a9b0c1d2e3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ONE_OF_THREE = (
    "(CASE WHEN menu_item_id IS NOT NULL THEN 1 ELSE 0 END"
    " + CASE WHEN produces_ingredient_id IS NOT NULL THEN 1 ELSE 0 END"
    " + CASE WHEN modifier_id IS NOT NULL THEN 1 ELSE 0 END) = 1"
)

_ONE_OF_TWO = "(menu_item_id IS NOT NULL) != (produces_ingredient_id IS NOT NULL)"


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column("modifier_id", postgresql.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_recipe_modifier",
        "recipes",
        "modifiers",
        ["modifier_id"],
        ["id"],
    )

    # ------------------------------------------------------------------
    # Also fixed here, because the new column would have inherited it.
    #
    # `uq_recipe_tenant_item` and `uq_recipe_tenant_produces_ingredient` were
    # plain UNIQUE(tenant_id, target) with no `is_active` predicate. Saving an
    # edit deactivates the old recipe and inserts a new one, so version 2
    # always collided with version 1 and NO recipe could be edited at all --
    # verified against the real Postgres schema, not inferred:
    #
    #   ERROR: duplicate key value violates unique constraint
    #          "uq_recipe_tenant_item"
    #
    # Replaced by partial unique indexes enforcing what the code always
    # intended and `Recipe.is_active` always claimed: one ACTIVE recipe per
    # target, with the deactivated versions kept as history. Strictly more
    # permissive, so no existing row can fail to migrate.
    # ------------------------------------------------------------------
    op.drop_constraint("uq_recipe_tenant_item", "recipes", type_="unique")
    op.drop_constraint(
        "uq_recipe_tenant_produces_ingredient", "recipes", type_="unique"
    )
    op.create_index(
        "uq_recipe_active_menu_item",
        "recipes",
        ["tenant_id", "menu_item_id"],
        unique=True,
        postgresql_where=sa.text("is_active AND menu_item_id IS NOT NULL"),
    )
    op.create_index(
        "uq_recipe_active_produces_ingredient",
        "recipes",
        ["tenant_id", "produces_ingredient_id"],
        unique=True,
        postgresql_where=sa.text("is_active AND produces_ingredient_id IS NOT NULL"),
    )
    op.create_index(
        "uq_recipe_active_modifier",
        "recipes",
        ["tenant_id", "modifier_id"],
        unique=True,
        postgresql_where=sa.text("is_active AND modifier_id IS NOT NULL"),
    )

    # Widen the target rule before any row can use the new column.
    op.drop_constraint("ck_recipe_exactly_one_target", "recipes", type_="check")
    op.create_check_constraint(
        "ck_recipe_exactly_one_target",
        "recipes",
        _ONE_OF_THREE,
    )


def downgrade() -> None:
    # Modifier recipes cannot survive the narrower constraint. Deactivating
    # them rather than deleting keeps the cost history readable, but they must
    # also lose the column, so the rows are removed outright: on a downgrade the
    # data has nowhere to live. Deliberate and irreversible, which is why this
    # is a downgrade and not a normal operation.
    op.execute("DELETE FROM recipe_items WHERE recipe_id IN "
               "(SELECT id FROM recipes WHERE modifier_id IS NOT NULL)")
    op.execute("DELETE FROM recipes WHERE modifier_id IS NOT NULL")

    op.drop_constraint("ck_recipe_exactly_one_target", "recipes", type_="check")
    op.create_check_constraint(
        "ck_recipe_exactly_one_target",
        "recipes",
        _ONE_OF_TWO,
    )

    # Restoring the old unique constraints can only succeed if no target has
    # more than one version, which is the state the broken constraints forced
    # anyway. Superseded versions are dropped so the downgrade is not blocked
    # by history the old schema had no way to hold.
    op.drop_index("uq_recipe_active_modifier", table_name="recipes")
    op.drop_index("uq_recipe_active_produces_ingredient", table_name="recipes")
    op.drop_index("uq_recipe_active_menu_item", table_name="recipes")
    op.execute(
        "DELETE FROM recipe_items WHERE recipe_id IN "
        "(SELECT id FROM recipes WHERE NOT is_active)"
    )
    op.execute("DELETE FROM recipes WHERE NOT is_active")
    op.create_unique_constraint(
        "uq_recipe_tenant_item", "recipes", ["tenant_id", "menu_item_id"]
    )
    op.create_unique_constraint(
        "uq_recipe_tenant_produces_ingredient",
        "recipes",
        ["tenant_id", "produces_ingredient_id"],
    )

    op.drop_constraint("fk_recipe_modifier", "recipes", type_="foreignkey")
    op.drop_column("recipes", "modifier_id")
