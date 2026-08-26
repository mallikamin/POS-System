"""Turning recipes into stock movements.

Two things live here, because they are the same idea pointed in opposite
directions: explode a recipe into its ingredients, then move stock.

  * `run_production` -- a batch is made. Raw ingredients are consumed and the
    produced ingredient is added. This is Martin's Section 4: "Convert raw
    materials into produced inventory. Automatically deduct ingredients consumed
    during production. Add produced quantity to inventory."
  * `consume_for_order` -- a sale happens. Every sold menu item's recipe is
    exploded and its ingredients deducted from the location that sold it. This
    is Section 2: "Automatic inventory deduction upon sale."

Both go through `stock_service.move_stock`, so neither can update a balance
without also writing the movement that explains it.

Production chains
-----------------
Producing a croissant consumes dough, which is itself produced from flour and
butter. `run_production` deliberately consumes the *dough* and does not
cascade into producing more dough automatically -- if dough has run out, that
should surface as a negative dough balance for a human to act on, not as a
silent chain of implied production runs nobody asked for. Cost, by contrast,
*does* roll up the whole chain automatically (recipe_service).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import Recipe
from app.models.order import Order, OrderItem
from app.services import stock_service
from app.services.stock_service import StockError


async def _load_recipe(
    db: AsyncSession, tenant_id: uuid.UUID, recipe_id: uuid.UUID
) -> Recipe:
    result = await db.execute(
        select(Recipe)
        .where(Recipe.id == recipe_id, Recipe.tenant_id == tenant_id)
        # menu_item is eager-loaded too: _recipe_label reads it, and a lazy load
        # on an async session raises MissingGreenlet.
        .options(
            selectinload(Recipe.recipe_items),
            selectinload(Recipe.produces_ingredient),
            selectinload(Recipe.menu_item),
        )
    )
    recipe = result.scalar_one_or_none()
    if recipe is None:
        raise StockError("No such recipe for this restaurant.")
    return recipe


def _recipe_label(recipe: Recipe) -> str:
    """A human name for a recipe.

    `Recipe` deliberately has no `name` column -- it is identified by whatever it
    produces. Resolve that here rather than at every call site, and fall back to
    the id so a log line is never blank.
    """
    if recipe.produces_ingredient is not None:
        return recipe.produces_ingredient.name
    if recipe.menu_item is not None:
        return recipe.menu_item.name
    return f"recipe {recipe.id}"


def _consumed_quantity(quantity: Decimal, waste_factor: Decimal, batches: Decimal) -> Decimal:
    """Ingredient actually used, including the recipe's waste allowance.

    A 5% waste factor means 5% more is consumed than ends up in the product --
    the same rule the costing engine already applies, so cost and consumption
    cannot disagree.
    """
    factor = Decimal("1") + (Decimal(str(waste_factor)) / Decimal("100"))
    return (Decimal(str(quantity)) * factor * batches).quantize(Decimal("0.001"))


async def run_production(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    recipe_id: uuid.UUID,
    batches: Decimal,
    location_id: uuid.UUID | None = None,
    performed_by: uuid.UUID | None = None,
    reference_number: str | None = None,
) -> dict:
    """Make `batches` of a sub-recipe: consume the inputs, add the output.

    Only valid for a recipe that produces an ingredient. A recipe that produces
    a sellable menu item is not "produced into stock" -- it is made to order and
    consumed by `consume_for_order`.
    """
    batches = Decimal(str(batches))
    if batches <= 0:
        raise StockError("Batches must be greater than zero.")

    recipe = await _load_recipe(db, tenant_id, recipe_id)

    if recipe.produces_ingredient_id is None:
        raise StockError(
            "This recipe produces a menu item, not an ingredient, so it cannot "
            "be produced into stock. Sell it instead."
        )
    if not recipe.recipe_items:
        raise StockError("This recipe has no ingredients, so nothing can be produced.")

    location = await stock_service.resolve_location(db, tenant_id, location_id)
    label = _recipe_label(recipe)
    ref = reference_number or f"PROD-{datetime.now(timezone.utc):%Y%m%d%H%M%S}"

    consumed: list[dict] = []
    for item in recipe.recipe_items:
        used = _consumed_quantity(item.quantity, item.waste_factor, batches)
        if used <= 0:
            continue
        await stock_service.move_stock(
            db,
            tenant_id=tenant_id,
            ingredient_id=item.ingredient_id,
            quantity_delta=-used,
            transaction_type="consumption",
            location_id=location.id,
            performed_by=performed_by,
            reference_number=ref,
            notes=f"Consumed producing {batches} x {label}",
        )
        consumed.append({"ingredient_id": item.ingredient_id, "quantity": used})

    produced_qty = (Decimal(str(recipe.yield_servings)) * batches).quantize(
        Decimal("0.001")
    )
    await stock_service.move_stock(
        db,
        tenant_id=tenant_id,
        ingredient_id=recipe.produces_ingredient_id,
        quantity_delta=produced_qty,
        transaction_type="production",
        location_id=location.id,
        unit_cost=recipe.cost_per_serving,
        performed_by=performed_by,
        reference_number=ref,
        notes=f"Produced {batches} x {label}",
    )

    return {
        "reference_number": ref,
        "recipe_id": recipe.id,
        "recipe_name": label,
        "location_id": location.id,
        "location_name": location.name,
        "batches": batches,
        "produced_ingredient_id": recipe.produces_ingredient_id,
        "produced_quantity": produced_qty,
        "unit_cost": recipe.cost_per_serving,
        "consumed": consumed,
    }


async def consume_for_order(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    performed_by: uuid.UUID | None = None,
) -> dict:
    """Deduct the ingredients behind every line of a completed order.

    Idempotency matters here: an order that is completed, re-synced or retried
    must not deduct twice. Any existing `consumption` transaction already
    referencing this order means the work is done, and the call is a no-op.
    """
    from app.models.inventory import InventoryTransaction  # local: avoids a cycle

    already = await db.execute(
        select(InventoryTransaction.id)
        .where(
            InventoryTransaction.order_id == order_id,
            InventoryTransaction.transaction_type == "consumption",
        )
        .limit(1)
    )
    if already.scalar_one_or_none() is not None:
        return {"order_id": order_id, "skipped": True, "reason": "already deducted"}

    result = await db.execute(
        select(Order)
        .where(Order.id == order_id, Order.tenant_id == tenant_id)
        .options(selectinload(Order.items))
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise StockError("No such order for this restaurant.")

    location = await stock_service.resolve_location(db, tenant_id, order.location_id)

    deducted: list[dict] = []
    missing_recipe: list[uuid.UUID] = []

    for line in order.items:
        if line.menu_item_id is None:
            continue
        recipe_result = await db.execute(
            select(Recipe)
            .where(
                Recipe.tenant_id == tenant_id,
                Recipe.menu_item_id == line.menu_item_id,
                Recipe.is_active == True,  # noqa: E712
            )
            .options(
                selectinload(Recipe.recipe_items),
                selectinload(Recipe.produces_ingredient),
                selectinload(Recipe.menu_item),
            )
        )
        recipe = recipe_result.scalar_one_or_none()
        if recipe is None:
            # A sellable item with no recipe is normal (a canned drink is bought
            # and sold, not made). Recorded, not treated as an error.
            missing_recipe.append(line.menu_item_id)
            continue

        qty = Decimal(str(line.quantity))
        for item in recipe.recipe_items:
            used = _consumed_quantity(item.quantity, item.waste_factor, qty)
            if used <= 0:
                continue
            await stock_service.move_stock(
                db,
                tenant_id=tenant_id,
                ingredient_id=item.ingredient_id,
                quantity_delta=-used,
                transaction_type="consumption",
                location_id=location.id,
                order_id=order_id,
                performed_by=performed_by,
                reference_number=order.order_number,
                notes=f"Sold {qty} x {_recipe_label(recipe)}",
            )
            deducted.append({"ingredient_id": item.ingredient_id, "quantity": used})

    return {
        "order_id": order_id,
        "skipped": False,
        "location_id": location.id,
        "lines_deducted": len(deducted),
        "menu_items_without_recipe": missing_recipe,
    }
