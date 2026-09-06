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
    if recipe.modifier is not None:
        # Marked as an add-on in the movement history, because "Cheese Sauce"
        # alone would read as a production run rather than a sale.
        return f"{recipe.modifier.name} (add-on)"
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
        what = (
            "is for an add-on"
            if recipe.modifier_id is not None
            else "produces a menu item"
        )
        raise StockError(
            f"This recipe {what}, not an ingredient, so it cannot be produced "
            "into stock. Sell it instead."
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


async def preview_production(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    recipe_id: uuid.UUID,
    batches: Decimal,
    location_id: uuid.UUID | None = None,
) -> dict:
    """What a run WOULD do, without doing it.

    Martin's M9 complaint was that he could not find production at all, and the
    dialog he could not find asked for "batches" -- a chef thinks "make 5 kg of
    sauce", not "run the recipe 2.5 times". Showing the exact grams in and grams
    out before the button is pressed is what turns the number into something he
    can check.

    🔴 The arithmetic is `_consumed_quantity` and `yield_servings * batches`,
    the same two lines `run_production` uses. Re-deriving it in TypeScript would
    give the preview and the run two chances to disagree, and the one that moved
    stock would win silently.

    Nothing is written. `shortfall` is advisory: a run is still allowed to take
    a balance negative, because a kitchen that has already made the sauce needs
    the system to say so rather than refuse it.
    """
    batches = Decimal(str(batches))
    if batches <= 0:
        raise StockError("Batches must be greater than zero.")

    recipe = await _load_recipe(db, tenant_id, recipe_id)
    if recipe.produces_ingredient_id is None:
        raise StockError(
            "This recipe does not produce an ingredient, so it cannot be "
            "produced into stock."
        )
    if not recipe.recipe_items:
        raise StockError("This recipe has no ingredients, so nothing can be produced.")

    location = await stock_service.resolve_location(db, tenant_id, location_id)

    from app.models.inventory import Ingredient  # local: avoids a cycle

    ingredient_ids = [item.ingredient_id for item in recipe.recipe_items]
    ingredient_ids.append(recipe.produces_ingredient_id)
    rows = (
        await db.execute(
            select(Ingredient).where(
                Ingredient.tenant_id == tenant_id, Ingredient.id.in_(ingredient_ids)
            )
        )
    ).scalars().all()
    by_id = {row.id: row for row in rows}

    on_hand = await stock_service.stock_on_hand(
        db, tenant_id, location.id, ingredient_ids
    )

    consumes: list[dict] = []
    for item in recipe.recipe_items:
        used = _consumed_quantity(item.quantity, item.waste_factor, batches)
        ingredient = by_id.get(item.ingredient_id)
        available = on_hand.get(item.ingredient_id, Decimal("0"))
        consumes.append(
            {
                "ingredient_id": item.ingredient_id,
                "ingredient_name": ingredient.name if ingredient else "Unknown",
                "unit": ingredient.unit if ingredient else "",
                "quantity": used,
                "available": available,
                "shortfall": max(Decimal("0"), used - available),
            }
        )

    produced = by_id.get(recipe.produces_ingredient_id)
    produced_qty = (Decimal(str(recipe.yield_servings)) * batches).quantize(
        Decimal("0.001")
    )

    return {
        "recipe_id": recipe.id,
        "recipe_name": _recipe_label(recipe),
        "location_id": location.id,
        "location_name": location.name,
        "batches": batches,
        "yield_per_batch": Decimal(str(recipe.yield_servings)),
        "produced_ingredient_id": recipe.produces_ingredient_id,
        "produced_ingredient_name": produced.name if produced else "Unknown",
        "produced_unit": produced.unit if produced else "",
        "produced_quantity": produced_qty,
        "unit_cost": recipe.cost_per_serving,
        "total_cost": (
            Decimal(str(recipe.cost_per_serving)) * produced_qty
        ).quantize(Decimal("0.01")),
        "consumes": consumes,
        "has_shortfall": any(line["shortfall"] > 0 for line in consumes),
    }


async def list_production_runs(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    location_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[dict]:
    """What was made, newest first, with what each run ate.

    🔴 There is no `production_runs` table and this deliberately does not add
    one. A run already writes one `production` movement and one `consumption`
    movement per input, all sharing a `PROD-...` reference, and those rows are
    the movements that actually changed the balances. A header table beside them
    would be a second version of the same fact, free to disagree with the first.

    So the header is reconstructed: every `production` movement is a run, and
    the consumption rows carrying its reference are its inputs.
    """
    from app.models.inventory import Ingredient, InventoryTransaction
    from app.models.location import Location
    from app.models.user import User

    stmt = (
        select(InventoryTransaction, Ingredient, Location, User)
        .join(Ingredient, Ingredient.id == InventoryTransaction.ingredient_id)
        .outerjoin(Location, Location.id == InventoryTransaction.location_id)
        .outerjoin(User, User.id == InventoryTransaction.performed_by)
        .where(
            InventoryTransaction.tenant_id == tenant_id,
            InventoryTransaction.transaction_type == "production",
        )
    )
    if location_id is not None:
        stmt = stmt.where(InventoryTransaction.location_id == location_id)
    stmt = stmt.order_by(InventoryTransaction.transaction_date.desc()).limit(limit)

    headers = (await db.execute(stmt)).all()
    if not headers:
        return []

    refs = [tx.reference_number for tx, _, _, _ in headers if tx.reference_number]
    inputs: dict[str, list[dict]] = {}
    if refs:
        input_rows = (
            await db.execute(
                select(InventoryTransaction, Ingredient)
                .join(Ingredient, Ingredient.id == InventoryTransaction.ingredient_id)
                .where(
                    InventoryTransaction.tenant_id == tenant_id,
                    InventoryTransaction.transaction_type == "consumption",
                    InventoryTransaction.reference_number.in_(refs),
                )
                .order_by(Ingredient.name)
            )
        ).all()
        for tx, ingredient in input_rows:
            inputs.setdefault(tx.reference_number or "", []).append(
                {
                    "ingredient_id": ingredient.id,
                    "ingredient_name": ingredient.name,
                    "unit": ingredient.unit,
                    # Stored negative, because it left the shelf. Shown positive,
                    # because "consumed -1.2 kg" reads as a return.
                    "quantity": abs(Decimal(str(tx.quantity))),
                    "total_cost": tx.total_cost,
                }
            )

    return [
        {
            "reference_number": tx.reference_number,
            "produced_at": tx.transaction_date,
            "produced_ingredient_id": ingredient.id,
            "produced_ingredient_name": ingredient.name,
            "unit": tx.unit,
            "quantity": tx.quantity,
            "unit_cost": tx.unit_cost,
            "total_cost": tx.total_cost,
            "balance_after": tx.balance_after,
            "location_id": tx.location_id,
            "location_name": location.name if location is not None else None,
            "performed_by_name": user.full_name if user is not None else None,
            "notes": tx.notes,
            "consumed": inputs.get(tx.reference_number or "", []),
        }
        for tx, ingredient, location, user in headers
    ]


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
        # `.modifiers` is chained: the add-ons on a line are consumed too
        # (OI-99), and a lazy load there raises MissingGreenlet.
        .options(selectinload(Order.items).selectinload(OrderItem.modifiers))
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise StockError("No such order for this restaurant.")

    location = await stock_service.resolve_location(db, tenant_id, order.location_id)

    deducted: list[dict] = []
    missing_recipe: list[uuid.UUID] = []

    async def _deduct(recipe: Recipe, qty: Decimal) -> None:
        """Explode one recipe `qty` times and write the movements."""
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

    for line in order.items:
        if line.menu_item_id is None:
            continue
        qty = Decimal(str(line.quantity))

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
                selectinload(Recipe.modifier),
            )
        )
        recipe = recipe_result.scalar_one_or_none()
        if recipe is None:
            # A sellable item with no recipe is normal (a canned drink is bought
            # and sold, not made). Recorded, not treated as an error.
            missing_recipe.append(line.menu_item_id)
        else:
            await _deduct(recipe, qty)

        # OI-99. An add-on the customer paid for is made of something too.
        # Deducted at the LINE's quantity, because `order_item_modifiers` holds
        # one row per chosen modifier per line, not per unit: two croissants
        # with extra cheese is one modifier row and two portions of cheese.
        #
        # Deliberately outside the `recipe is None` branch above: an item with
        # no recipe of its own can still carry an add-on that has one, and
        # skipping those was the first version of this bug.
        for chosen in line.modifiers:
            mod_result = await db.execute(
                select(Recipe)
                .where(
                    Recipe.tenant_id == tenant_id,
                    Recipe.modifier_id == chosen.modifier_id,
                    Recipe.is_active == True,  # noqa: E712
                )
                .options(
                    selectinload(Recipe.recipe_items),
                    selectinload(Recipe.produces_ingredient),
                    selectinload(Recipe.menu_item),
                    selectinload(Recipe.modifier),
                )
            )
            mod_recipe = mod_result.scalar_one_or_none()
            if mod_recipe is None:
                # Normal: most modifiers (Mild/Medium/Hot, Regular/Large) change
                # no ingredients at all. Not recorded as a missing recipe, which
                # is reserved for sellable items.
                continue
            await _deduct(mod_recipe, qty)

    return {
        "order_id": order_id,
        "skipped": False,
        "location_id": location.id,
        "lines_deducted": len(deducted),
        "menu_items_without_recipe": missing_recipe,
    }
