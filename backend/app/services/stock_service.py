"""Per-location stock movement -- the single chokepoint for changing stock.

Every increase or decrease in stock, whatever caused it (a sale, a production
run, a goods receipt, a transfer, a manual correction), goes through
`move_stock`. Nothing else writes `location_stock.quantity` or creates an
`InventoryTransaction`.

That is the whole point. The balance and the movement log are two views of the
same fact, and the only way to keep them honest is to make it impossible to
write one without the other. Anything that updates a balance directly will
eventually disagree with its own history, and then neither number can be
trusted.

Design decisions worth knowing
------------------------------
* **Going negative is allowed, and recorded.** Refusing to sell because the
  ingredient master says zero would stop a real till over a bookkeeping
  discrepancy. Kitchens lose stock to waste and mis-counts constantly. The
  truthful record is a negative balance that someone reconciles, not a blocked
  sale. `low_stock` reporting surfaces it.
* **`Ingredient.current_stock` is maintained as the tenant-wide rollup** so
  every existing read of it keeps working. It is derived from the per-location
  rows, never authoritative.
* Quantities are `Decimal`, never float. Costs are `Decimal` to match the
  inventory module; order money stays integer minor units elsewhere.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.inventory import Ingredient, InventoryTransaction
from app.models.location import Location, LocationStock
from app.models.user import User

# Movement types. `consumption` is a sale; `production` is a recipe run adding
# its output; `transfer_out`/`transfer_in` are the two halves of a transfer.
TRANSACTION_TYPES = (
    "purchase",
    "consumption",
    "production",
    "waste",
    "adjustment",
    "transfer_out",
    "transfer_in",
)


class StockError(ValueError):
    """A stock movement that cannot be performed as asked."""


async def resolve_location(
    db: AsyncSession, tenant_id: uuid.UUID, location_id: uuid.UUID | None
) -> Location:
    """Return the named location, or the tenant's default when none is given.

    Callers that predate locations (the existing POS, the storefront) pass
    nothing, and must keep working. Those tenants get their default location.
    """
    if location_id is not None:
        result = await db.execute(
            select(Location).where(
                Location.id == location_id, Location.tenant_id == tenant_id
            )
        )
        location = result.scalar_one_or_none()
        if location is None:
            raise StockError("No such location for this restaurant.")
        return location

    result = await db.execute(
        select(Location)
        .where(
            Location.tenant_id == tenant_id,
            Location.is_default == True,  # noqa: E712
            Location.is_active == True,  # noqa: E712
        )
        .limit(1)
    )
    location = result.scalar_one_or_none()
    if location is not None:
        return location

    # No default flagged: fall back to the only active location, if there is
    # exactly one. Refusing to guess between several is deliberate -- silently
    # deducting from the wrong site is worse than an error.
    result = await db.execute(
        select(Location).where(
            Location.tenant_id == tenant_id,
            Location.is_active == True,  # noqa: E712
        )
    )
    locations = list(result.scalars().all())
    if len(locations) == 1:
        return locations[0]
    if not locations:
        raise StockError("This restaurant has no active location configured.")
    raise StockError(
        "More than one location exists and none is marked default; "
        "the location must be specified explicitly."
    )


async def get_or_create_stock_row(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    location_id: uuid.UUID,
    ingredient_id: uuid.UUID,
) -> LocationStock:
    """The (location, ingredient) balance row, created at zero on first touch.

    Created lazily so adding a location does not have to fan out a row for every
    ingredient in the master.
    """
    result = await db.execute(
        select(LocationStock).where(
            LocationStock.location_id == location_id,
            LocationStock.ingredient_id == ingredient_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = LocationStock(
            tenant_id=tenant_id,
            location_id=location_id,
            ingredient_id=ingredient_id,
            quantity=Decimal("0"),
        )
        db.add(row)
        await db.flush()
    return row


async def _resync_ingredient_total(
    db: AsyncSession, ingredient: Ingredient
) -> None:
    """Recompute the tenant-wide rollup from the per-location rows."""
    result = await db.execute(
        select(func.coalesce(func.sum(LocationStock.quantity), 0)).where(
            LocationStock.ingredient_id == ingredient.id
        )
    )
    ingredient.current_stock = Decimal(str(result.scalar_one()))
    await db.flush()


async def move_stock(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    ingredient_id: uuid.UUID,
    quantity_delta: Decimal,
    transaction_type: str,
    location_id: uuid.UUID | None = None,
    unit_cost: Decimal | None = None,
    order_id: uuid.UUID | None = None,
    performed_by: uuid.UUID | None = None,
    reference_number: str | None = None,
    notes: str | None = None,
) -> InventoryTransaction:
    """Apply one stock movement and log it. The only way stock ever changes.

    `quantity_delta` is signed: positive adds, negative removes.
    """
    if transaction_type not in TRANSACTION_TYPES:
        raise StockError(f"Unknown transaction type {transaction_type!r}.")
    if quantity_delta == 0:
        raise StockError("A stock movement of zero is not a movement.")

    location = await resolve_location(db, tenant_id, location_id)

    result = await db.execute(
        select(Ingredient).where(
            Ingredient.id == ingredient_id, Ingredient.tenant_id == tenant_id
        )
    )
    ingredient = result.scalar_one_or_none()
    if ingredient is None:
        raise StockError("No such ingredient for this restaurant.")

    row = await get_or_create_stock_row(db, tenant_id, location.id, ingredient_id)

    delta = Decimal(str(quantity_delta))
    row.quantity = Decimal(str(row.quantity)) + delta

    cost = Decimal(str(unit_cost)) if unit_cost is not None else Decimal(
        str(ingredient.cost_per_unit)
    )

    txn = InventoryTransaction(
        tenant_id=tenant_id,
        ingredient_id=ingredient_id,
        location_id=location.id,
        transaction_type=transaction_type,
        quantity=delta,
        unit=ingredient.unit,
        unit_cost=cost,
        total_cost=(cost * abs(delta)).quantize(Decimal("0.01")),
        # The balance AT THIS LOCATION after the move, not the tenant total.
        # A per-location log whose running balance was tenant-wide would be
        # unreadable.
        balance_after=row.quantity,
        order_id=order_id,
        performed_by=performed_by,
        reference_number=reference_number,
        notes=notes,
    )
    db.add(txn)
    await db.flush()

    await _resync_ingredient_total(db, ingredient)
    return txn


async def get_stock_movements(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    ingredient_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """The movement history: every change to stock, and why it happened.

    🔴 **Why this exists.** `move_stock` has written an `InventoryTransaction`
    for every stock change since the module shipped, and the adjustment endpoint
    has always demanded a mandatory reason. None of it was readable: there was no
    endpoint and no screen, so the reason a human typed went into the database
    and was never seen again. Found in UAT on 2026-08-27, when the client
    walkthrough told the reader to "look at the movement history for that item"
    and there was no such thing.

    That mattered more than a missing screen. "Stock never changes without an
    explanation" is the claim this module is sold on, and a claim the customer
    cannot inspect is a claim they have to take on trust.

    Ordered newest first, and by `id` as a tiebreak: several movements can share
    a `transaction_date` to the microsecond (a production run consumes its inputs
    and adds its output in one transaction), and without a stable second key the
    page order wobbles between requests.

    Joins are LEFT for `location` and `performed_by` on purpose: `location_id` is
    null for rows written before locations existed, and `performed_by` is null for
    anything the system did on its own, such as consumption from an online order.
    An inner join would silently hide exactly those rows, which is the failure
    mode a history screen must never have.
    """
    performer = aliased(User)
    stmt = (
        select(InventoryTransaction, Ingredient, Location, performer)
        .join(Ingredient, Ingredient.id == InventoryTransaction.ingredient_id)
        .outerjoin(Location, Location.id == InventoryTransaction.location_id)
        .outerjoin(performer, performer.id == InventoryTransaction.performed_by)
        .where(InventoryTransaction.tenant_id == tenant_id)
    )
    if ingredient_id is not None:
        stmt = stmt.where(InventoryTransaction.ingredient_id == ingredient_id)
    if location_id is not None:
        stmt = stmt.where(InventoryTransaction.location_id == location_id)

    stmt = stmt.order_by(
        InventoryTransaction.transaction_date.desc(),
        InventoryTransaction.id.desc(),
    ).limit(limit).offset(offset)

    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": txn.id,
            "ingredient_id": txn.ingredient_id,
            "ingredient_name": ingredient.name,
            "location_id": txn.location_id,
            "location_name": location.name if location is not None else None,
            "transaction_type": txn.transaction_type,
            "quantity": txn.quantity,
            "unit": txn.unit,
            "balance_after": txn.balance_after,
            "unit_cost": txn.unit_cost,
            "total_cost": txn.total_cost,
            "transaction_date": txn.transaction_date,
            # The two columns that make this a record rather than a number.
            "performed_by_name": (
                performed.full_name if performed is not None else None
            ),
            "notes": txn.notes,
            "reference_number": txn.reference_number,
            "order_id": txn.order_id,
        }
        for txn, ingredient, location, performed in rows
    ]


async def get_location_stock(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    location_id: uuid.UUID | None = None,
    low_only: bool = False,
) -> list[dict]:
    """Stock position, per location. `low_only` filters to at-or-below reorder.

    Returns plain dicts rather than ORM rows because every caller (the API, the
    low-stock report, the AI purchase suggester) wants the ingredient's name and
    unit alongside the quantity, and doing that here avoids three different
    lazy-load bugs later.
    """
    stmt = (
        select(LocationStock, Ingredient, Location)
        .join(Ingredient, Ingredient.id == LocationStock.ingredient_id)
        .join(Location, Location.id == LocationStock.location_id)
        .where(LocationStock.tenant_id == tenant_id)
    )
    if location_id is not None:
        stmt = stmt.where(LocationStock.location_id == location_id)
    if low_only:
        stmt = stmt.where(
            LocationStock.quantity <= LocationStock.reorder_point,
            LocationStock.reorder_point > 0,
        )
    stmt = stmt.order_by(Location.name, Ingredient.name)

    rows = (await db.execute(stmt)).all()
    return [
        {
            "location_id": stock.location_id,
            "location_name": location.name,
            "ingredient_id": stock.ingredient_id,
            "ingredient_name": ingredient.name,
            "ingredient_image_url": ingredient.image_url,
            "unit": ingredient.unit,
            "quantity": stock.quantity,
            "reorder_point": stock.reorder_point,
            "reorder_quantity": stock.reorder_quantity,
            "cost_per_unit": ingredient.cost_per_unit,
            "is_produced": ingredient.is_produced,
            "is_low": (
                stock.reorder_point > 0 and stock.quantity <= stock.reorder_point
            ),
        }
        for stock, ingredient, location in rows
    ]
