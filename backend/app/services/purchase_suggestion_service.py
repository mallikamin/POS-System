"""What to order this week, worked out from the production target.

Martin's Section 5.2: *"specify target production amounts for the week, and the
AI suggests what and how much to order based on existing inventory and
recipes."*

🔴 The single most important decision in this file: **the quantities are
computed, not generated.** A language model never invents a number that lands
on a purchase order. The chain from "500 croissants" to "order 62.5 kg of
flour" is arithmetic over the recipe tree, and arithmetic is something a
computer should do exactly, repeatably, and auditably. The optional AI layer
(`purchase_advisor`) reads the finished plan and adds judgement -- risks,
priorities, a sentence a human can act on -- and it cannot change a quantity.

This is the playbook's first move, "don't call the model", applied to the part
that has to be right. It also means the whole feature works on a server with no
API key at all.

How the explosion works
-----------------------
A target is a recipe and how many times to run it. Each recipe line is either:

  * a **raw** ingredient  -> add `quantity x (1 + waste%)` x batches to the
    requirement, or
  * a **produced** ingredient (a sub-recipe: dough, sauce, stuffing) -> do NOT
    order it. Recurse into the recipe that makes it, scaled by how much is
    needed, and order ITS inputs instead.

That recursion is the whole point of the multi-layer production chain: you buy
flour and butter, not croissant dough.

Then, per raw ingredient:

    shortfall = required - on_hand_at_this_location - already_on_order

`already_on_order` matters. Without it, running the suggestion twice in one
morning orders everything twice.
"""

from __future__ import annotations

import uuid
from decimal import ROUND_CEILING, Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import Ingredient, Recipe, RecipeItem
from app.models.menu import MenuItem, Modifier
from app.services import purchase_order_service, stock_service, supplier_service
from app.services.supplier_service import ProcurementError

if TYPE_CHECKING:
    from app.models.procurement import SupplierItem

_QTY = Decimal("0.001")
_CENT = Decimal("0.01")
_HUNDRED = Decimal("100")


def _qty(value) -> Decimal:
    return Decimal(str(value)).quantize(_QTY)


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(_CENT)


class SuggestionError(ProcurementError):
    """The suggestion cannot be produced as asked."""


# ---------------------------------------------------------------------------
# RECIPE EXPLOSION
# ---------------------------------------------------------------------------


async def _load_recipes(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Every active recipe for the tenant, indexed for the walk.

    Loaded once, up front. Walking the tree with a query per node would issue
    one round trip per branch and, worse, risk a lazy load inside the recursion
    -- the `MissingGreenlet` trap this codebase has been bitten by before.
    """
    recipes = list(
        (
            await db.execute(
                select(Recipe)
                .where(
                    Recipe.tenant_id == tenant_id,
                    Recipe.is_active == True,  # noqa: E712
                )
                .options(selectinload(Recipe.recipe_items))
            )
        )
        .scalars()
        .all()
    )
    ingredients = {
        i.id: i
        for i in (
            await db.execute(
                select(Ingredient).where(Ingredient.tenant_id == tenant_id)
            )
        )
        .scalars()
        .all()
    }
    menu_items = {
        m.id: m
        for m in (
            await db.execute(select(MenuItem).where(MenuItem.tenant_id == tenant_id))
        )
        .scalars()
        .all()
    }
    # Add-on recipes are plannable targets like any other: a week's worth of
    # extra-cheese portions consumes real cheese sauce (OI-99).
    modifiers = {
        m.id: m
        for m in (
            await db.execute(select(Modifier).where(Modifier.tenant_id == tenant_id))
        )
        .scalars()
        .all()
    }
    return {
        "by_id": {r.id: r for r in recipes},
        # Which recipe MAKES this ingredient, for the sub-recipe recursion.
        "by_produced_ingredient": {
            r.produces_ingredient_id: r
            for r in recipes
            if r.produces_ingredient_id is not None
        },
        "ingredients": ingredients,
        "menu_items": menu_items,
        "modifiers": modifiers,
    }


def _recipe_label(recipe: Recipe, index: dict) -> str:
    """A recipe has no name column; it is named by what it produces."""
    if recipe.menu_item_id:
        item = index["menu_items"].get(recipe.menu_item_id)
        return item.name if item else "Menu item"
    if recipe.produces_ingredient_id:
        ingredient = index["ingredients"].get(recipe.produces_ingredient_id)
        return ingredient.name if ingredient else "Sub-recipe"
    if recipe.modifier_id:
        modifier = index["modifiers"].get(recipe.modifier_id)
        return f"{modifier.name} (add-on)" if modifier else "Add-on"
    return "Recipe"  # pragma: no cover -- the check constraint forbids this


def explode_requirement(
    recipe: Recipe,
    batches: Decimal,
    index: dict,
    raw_totals: dict[uuid.UUID, Decimal],
    production_plan: dict[uuid.UUID, Decimal],
    path: tuple[uuid.UUID, ...] = (),
) -> None:
    """Walk one recipe down to raw ingredients, accumulating what is needed.

    `raw_totals` collects purchasable quantities; `production_plan` collects how
    much of each in-house sub-recipe has to be MADE. Both are accumulated across
    every target, so two products sharing a dough add up rather than each
    ordering their own flour.

    A cycle in the recipe tree (A's sub-recipe eventually consumes A) would
    recurse forever. It is refused with the chain named, because the honest
    answer to a circular bill of materials is "this is not orderable", not a
    silently truncated number.
    """
    if recipe.id in path:
        raise SuggestionError(
            f"{_recipe_label(recipe, index)} is part of a circular recipe chain, "
            "so its requirement cannot be worked out. Fix the recipe first."
        )
    path = path + (recipe.id,)

    for line in recipe.recipe_items:
        waste_multiplier = Decimal("1") + (
            Decimal(str(line.waste_factor or 0)) / _HUNDRED
        )
        needed = Decimal(str(line.quantity)) * waste_multiplier * batches

        ingredient = index["ingredients"].get(line.ingredient_id)
        if ingredient is None:  # pragma: no cover -- FK guarantees it
            continue

        if not ingredient.is_produced:
            raw_totals[ingredient.id] = raw_totals.get(
                ingredient.id, Decimal("0")
            ) + needed
            continue

        # Made in-house. Do not order it: make it, and order what it is made of.
        production_plan[ingredient.id] = (
            production_plan.get(ingredient.id, Decimal("0")) + needed
        )
        sub_recipe = index["by_produced_ingredient"].get(ingredient.id)
        if sub_recipe is None:
            # Flagged as produced but nothing makes it. Treat it as raw rather
            # than silently dropping the requirement -- a missing recipe is a
            # data problem the buyer should see, not a zero.
            raw_totals[ingredient.id] = raw_totals.get(
                ingredient.id, Decimal("0")
            ) + needed
            continue

        sub_yield = Decimal(str(sub_recipe.yield_servings or 1))
        if sub_yield <= 0:  # pragma: no cover -- guarded at recipe creation
            raise SuggestionError(
                f"{_recipe_label(sub_recipe, index)} has a yield of zero, so how "
                "much to make cannot be worked out."
            )
        explode_requirement(
            sub_recipe, needed / sub_yield, index, raw_totals, production_plan, path
        )


# ---------------------------------------------------------------------------
# THE SUGGESTION
# ---------------------------------------------------------------------------


def _round_to_pack(quantity: Decimal, catalogue: "SupplierItem | None") -> Decimal:
    """Round an order up to whole packs, and up to the minimum order quantity.

    Always UP. Rounding a shortfall down would order less than the production
    plan needs, which is the one direction that stops the kitchen.

    `quantity` arrives in PURCHASE units and `pack_size` and
    `minimum_order_quantity` are read in the same units, because a supplier
    quotes its pack and its minimum in whatever it sells -- six cans to a tray,
    minimum two trays. For an ingredient bought in its stocking unit that is
    the same number it always was, so nothing existing changes meaning.
    """
    if catalogue is None:
        return _qty(quantity)

    pack = Decimal(str(catalogue.pack_size or 0))
    if pack > 0:
        packs = (quantity / pack).to_integral_value(rounding="ROUND_CEILING")
        quantity = packs * pack

    moq = Decimal(str(catalogue.minimum_order_quantity or 0))
    if moq > 0 and quantity < moq:
        quantity = moq

    return _qty(quantity)


async def build_suggestion(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    location_id: uuid.UUID | None,
    targets: list[dict],
) -> dict:
    """Work out what to buy for a week's production. No model involved.

    `targets` is [{"recipe_id": UUID, "batches": Decimal}, ...] -- how many times
    to run each recipe. The result groups the shortfall by preferred supplier,
    ready to become one purchase order each.
    """
    if not targets:
        raise SuggestionError("Set a production target first.")

    location = await stock_service.resolve_location(db, tenant_id, location_id)
    index = await _load_recipes(db, tenant_id)

    raw_totals: dict[uuid.UUID, Decimal] = {}
    production_plan: dict[uuid.UUID, Decimal] = {}
    target_rows: list[dict] = []

    for target in targets:
        recipe = index["by_id"].get(target["recipe_id"])
        if recipe is None:
            raise SuggestionError("No such active recipe for this restaurant.")
        batches = Decimal(str(target["batches"]))
        if batches <= 0:
            raise SuggestionError("A production target must be greater than zero.")
        explode_requirement(recipe, batches, index, raw_totals, production_plan)
        target_rows.append(
            {
                "recipe_id": recipe.id,
                "recipe_name": _recipe_label(recipe, index),
                "batches": _qty(batches),
                "yield_servings": _qty(recipe.yield_servings or 1),
                "produces": (
                    "menu_item"
                    if recipe.menu_item_id
                    else "modifier"
                    if recipe.modifier_id
                    else "ingredient"
                ),
            }
        )

    # What is already here, and what is already coming.
    stock_rows = await stock_service.get_location_stock(db, tenant_id, location.id)
    on_hand = {
        row["ingredient_id"]: Decimal(str(row["quantity"])) for row in stock_rows
    }
    on_order = await purchase_order_service.outstanding_quantities(
        db, tenant_id, location.id
    )

    lines: list[dict] = []
    for ingredient_id, required in raw_totals.items():
        ingredient = index["ingredients"].get(ingredient_id)
        if ingredient is None:  # pragma: no cover
            continue

        have = on_hand.get(ingredient_id, Decimal("0"))
        coming = on_order.get(ingredient_id, Decimal("0"))
        shortfall = Decimal(str(required)) - have - coming

        catalogue = await supplier_service.preferred_supplier_for(
            db, tenant_id, ingredient_id
        )

        # Martin M8. Everything above this line is in STOCKING units, because
        # that is what recipes spend and what stock counts. Everything below it
        # is in PURCHASE units, because that is what a purchase order says and
        # what the supplier charges for. This is the crossing point, and both
        # the quantity and the price have to be on the same side of it.
        #
        # You cannot buy two thirds of a tomato can, so the shortfall is
        # rounded UP to a whole purchase unit before pack sizes and minimum
        # order quantities are applied on top -- 900 g short of a 400 g can is
        # three cans, not 2.25.
        order_unit, conversion = purchase_order_service.purchase_unit_of(ingredient)
        if shortfall > 0:
            in_purchase_units = shortfall / conversion
            if conversion != 1:
                in_purchase_units = in_purchase_units.to_integral_value(
                    rounding=ROUND_CEILING
                )
            suggested = _round_to_pack(in_purchase_units, catalogue)
        else:
            suggested = Decimal("0")

        # Both the catalogue price and the ingredient's own purchase price are
        # per purchase unit, so the estimate multiplies like with like.
        unit_price = (
            Decimal(str(catalogue.last_price_minor))
            if catalogue is not None and Decimal(str(catalogue.last_price_minor)) > 0
            else Decimal(
                str(
                    ingredient.purchase_cost_minor
                    if ingredient.purchase_unit
                    else ingredient.cost_per_unit
                )
            )
        )

        lines.append(
            {
                "ingredient_id": ingredient_id,
                "ingredient_name": ingredient.name,
                # The stocking unit, which is what `required`, `on_hand`,
                # `on_order` and `shortfall` are all counted in.
                "unit": ingredient.unit,
                # The purchase unit, which is what `suggested_quantity` and
                # `unit_price_minor` are counted in. Equal to `unit` unless
                # the ingredient is bought in something else.
                "purchase_unit": order_unit,
                "units_per_purchase_unit": conversion,
                "required": _qty(required),
                "on_hand": _qty(have),
                "on_order": _qty(coming),
                "shortfall": _qty(max(Decimal("0"), shortfall)),
                "suggested_quantity": suggested,
                "unit_price_minor": _money(unit_price),
                "estimated_cost_minor": _money(suggested * unit_price),
                "supplier_id": catalogue.supplier_id if catalogue else None,
                "supplier_name": (
                    catalogue.supplier.name
                    if catalogue is not None and catalogue.supplier is not None
                    else None
                ),
                "lead_time_days": (
                    catalogue.lead_time_days
                    if catalogue is not None and catalogue.lead_time_days is not None
                    else (
                        catalogue.supplier.lead_time_days
                        if catalogue is not None and catalogue.supplier is not None
                        else None
                    )
                ),
                "pack_size": _qty(catalogue.pack_size) if catalogue else _qty(0),
                # Named explicitly rather than left as a null supplier for the
                # reader to interpret. "Nobody sells us this" is an action.
                "has_supplier": catalogue is not None,
            }
        )

    lines.sort(key=lambda row: (row["supplier_name"] or "zzz", row["ingredient_name"]))

    to_order = [row for row in lines if row["suggested_quantity"] > 0]
    unsourced = [row for row in to_order if not row["has_supplier"]]

    # Group into one basket per supplier: that is one purchase order each.
    baskets: dict[str, dict] = {}
    for row in to_order:
        if not row["has_supplier"]:
            continue
        key = str(row["supplier_id"])
        basket = baskets.setdefault(
            key,
            {
                "supplier_id": row["supplier_id"],
                "supplier_name": row["supplier_name"],
                "lead_time_days": row["lead_time_days"],
                "lines": [],
                "estimated_total_minor": Decimal("0"),
            },
        )
        basket["lines"].append(row)
        basket["estimated_total_minor"] = _money(
            Decimal(str(basket["estimated_total_minor"]))
            + Decimal(str(row["estimated_cost_minor"]))
        )

    production_rows = [
        {
            "ingredient_id": ingredient_id,
            "ingredient_name": index["ingredients"][ingredient_id].name,
            "unit": index["ingredients"][ingredient_id].unit,
            "quantity_to_make": _qty(quantity),
        }
        for ingredient_id, quantity in production_plan.items()
        if ingredient_id in index["ingredients"]
    ]
    production_rows.sort(key=lambda row: row["ingredient_name"])

    return {
        "location_id": location.id,
        "location_name": location.name,
        "targets": target_rows,
        "production_plan": production_rows,
        "lines": lines,
        "baskets": sorted(baskets.values(), key=lambda b: b["supplier_name"] or ""),
        "unsourced": unsourced,
        "estimated_total_minor": _money(
            sum(
                (Decimal(str(row["estimated_cost_minor"])) for row in to_order),
                Decimal("0"),
            )
        ),
        "advice": None,
    }
