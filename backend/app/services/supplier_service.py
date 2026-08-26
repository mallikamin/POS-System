"""Supplier master: who we buy from, and what each of them sells us.

Kept separate from the purchase-order workflow on purpose. A supplier record
outlives every PO placed with it, and the catalogue (`SupplierItem`) is read by
things that never create a PO at all: the ordering suggestion, the price
history, the receiving screen's price defaults.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import Ingredient
from app.models.procurement import PurchaseOrder, Supplier, SupplierItem


class ProcurementError(ValueError):
    """A procurement action that cannot be performed as asked.

    Always the caller's problem, never a 500. The API layer turns it into a
    400 (or a 404 for a lookup), exactly as `StockError` is handled.
    """


# ---------------------------------------------------------------------------
# SUPPLIERS
# ---------------------------------------------------------------------------


async def list_suppliers(
    db: AsyncSession, tenant_id: uuid.UUID, include_inactive: bool = False
) -> list[Supplier]:
    stmt = select(Supplier).where(Supplier.tenant_id == tenant_id)
    if not include_inactive:
        stmt = stmt.where(Supplier.is_active == True)  # noqa: E712
    stmt = stmt.order_by(Supplier.name)
    return list((await db.execute(stmt)).scalars().all())


async def get_supplier(
    db: AsyncSession, tenant_id: uuid.UUID, supplier_id: uuid.UUID
) -> Supplier:
    supplier = (
        await db.execute(
            select(Supplier).where(
                Supplier.id == supplier_id, Supplier.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if supplier is None:
        raise ProcurementError("No such supplier for this restaurant.")
    return supplier


async def create_supplier(
    db: AsyncSession, tenant_id: uuid.UUID, data: dict
) -> Supplier:
    code = (data.get("code") or "").strip().upper()
    if not code:
        raise ProcurementError("A supplier needs a short code.")

    clash = (
        await db.execute(
            select(Supplier).where(
                Supplier.tenant_id == tenant_id, Supplier.code == code
            )
        )
    ).scalar_one_or_none()
    if clash is not None:
        raise ProcurementError(f"A supplier with code {code!r} already exists.")

    supplier = Supplier(tenant_id=tenant_id, **{**data, "code": code})
    db.add(supplier)
    await db.flush()
    return supplier


async def update_supplier(
    db: AsyncSession, tenant_id: uuid.UUID, supplier_id: uuid.UUID, data: dict
) -> Supplier:
    supplier = await get_supplier(db, tenant_id, supplier_id)
    for field, value in data.items():
        setattr(supplier, field, value)
    await db.flush()
    return supplier


async def deactivate_supplier(
    db: AsyncSession, tenant_id: uuid.UUID, supplier_id: uuid.UUID
) -> Supplier:
    """Deactivate rather than delete.

    A supplier with purchase history cannot be removed without orphaning the
    POs that reference it, and that history is the point of keeping the record.
    """
    supplier = await get_supplier(db, tenant_id, supplier_id)
    supplier.is_active = False
    await db.flush()
    return supplier


# ---------------------------------------------------------------------------
# SUPPLIER CATALOGUE
# ---------------------------------------------------------------------------


async def list_supplier_items(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    supplier_id: uuid.UUID | None = None,
    ingredient_id: uuid.UUID | None = None,
    include_inactive: bool = False,
) -> list[dict]:
    """The catalogue, joined to ingredient and supplier names.

    Returns dicts rather than ORM rows because every caller wants the names
    alongside, and resolving them here avoids a lazy-load bug in each one.
    """
    stmt = (
        select(SupplierItem, Ingredient, Supplier)
        .join(Ingredient, Ingredient.id == SupplierItem.ingredient_id)
        .join(Supplier, Supplier.id == SupplierItem.supplier_id)
        .where(SupplierItem.tenant_id == tenant_id)
    )
    if supplier_id is not None:
        stmt = stmt.where(SupplierItem.supplier_id == supplier_id)
    if ingredient_id is not None:
        stmt = stmt.where(SupplierItem.ingredient_id == ingredient_id)
    if not include_inactive:
        stmt = stmt.where(SupplierItem.is_active == True)  # noqa: E712
    stmt = stmt.order_by(Supplier.name, Ingredient.name)

    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": item.id,
            "supplier_id": item.supplier_id,
            "supplier_name": supplier.name,
            "ingredient_id": item.ingredient_id,
            "ingredient_name": ingredient.name,
            "unit": ingredient.unit,
            "supplier_sku": item.supplier_sku,
            "supplier_item_name": item.supplier_item_name,
            "last_price_minor": item.last_price_minor,
            "last_purchased_at": item.last_purchased_at,
            "pack_size": item.pack_size,
            "minimum_order_quantity": item.minimum_order_quantity,
            "lead_time_days": (
                item.lead_time_days
                if item.lead_time_days is not None
                else supplier.lead_time_days
            ),
            "is_preferred": item.is_preferred,
            "is_active": item.is_active,
            "notes": item.notes,
        }
        for item, ingredient, supplier in rows
    ]


async def get_supplier_item(
    db: AsyncSession, tenant_id: uuid.UUID, item_id: uuid.UUID
) -> SupplierItem:
    item = (
        await db.execute(
            select(SupplierItem).where(
                SupplierItem.id == item_id, SupplierItem.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise ProcurementError("No such supplier item for this restaurant.")
    return item


async def upsert_supplier_item(
    db: AsyncSession, tenant_id: uuid.UUID, supplier_id: uuid.UUID, data: dict
) -> SupplierItem:
    """Add an ingredient to a supplier's catalogue, or update the existing link.

    Upsert rather than create-only because "supplier X also sells flour" is
    something a user asserts repeatedly, and a duplicate-key error is a worse
    answer than simply making it true.
    """
    await get_supplier(db, tenant_id, supplier_id)

    ingredient_id = data["ingredient_id"]
    ingredient = (
        await db.execute(
            select(Ingredient).where(
                Ingredient.id == ingredient_id, Ingredient.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if ingredient is None:
        raise ProcurementError("No such ingredient for this restaurant.")
    if ingredient.is_produced:
        raise ProcurementError(
            f"{ingredient.name} is made in-house from a recipe, so it cannot be "
            "bought from a supplier. Order its raw ingredients instead."
        )

    existing = (
        await db.execute(
            select(SupplierItem).where(
                SupplierItem.supplier_id == supplier_id,
                SupplierItem.ingredient_id == ingredient_id,
            )
        )
    ).scalar_one_or_none()

    fields = {k: v for k, v in data.items() if k != "ingredient_id"}
    if existing is not None:
        for field, value in fields.items():
            setattr(existing, field, value)
        item = existing
    else:
        item = SupplierItem(
            tenant_id=tenant_id,
            supplier_id=supplier_id,
            ingredient_id=ingredient_id,
            **fields,
        )
        db.add(item)

    await db.flush()
    if item.is_preferred:
        await _clear_other_preferred(db, tenant_id, ingredient_id, item.id)
    return item


async def _clear_other_preferred(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    ingredient_id: uuid.UUID,
    keep_item_id: uuid.UUID,
) -> None:
    """Exactly one preferred supplier per ingredient.

    Enforced here rather than by a partial unique index so it works identically
    on SQLite (tests) and Postgres (production). Two "preferred" suppliers for
    the same ingredient would make the ordering suggestion pick arbitrarily.
    """
    rows = (
        await db.execute(
            select(SupplierItem).where(
                SupplierItem.tenant_id == tenant_id,
                SupplierItem.ingredient_id == ingredient_id,
                SupplierItem.id != keep_item_id,
                SupplierItem.is_preferred == True,  # noqa: E712
            )
        )
    ).scalars().all()
    for row in rows:
        row.is_preferred = False
    if rows:
        await db.flush()


async def remove_supplier_item(
    db: AsyncSession, tenant_id: uuid.UUID, item_id: uuid.UUID
) -> None:
    """Drop an ingredient from a supplier's catalogue.

    Safe to hard-delete: purchase-order lines reference the ingredient
    directly, never this link, so no history is lost.
    """
    item = await get_supplier_item(db, tenant_id, item_id)
    await db.delete(item)
    await db.flush()


async def preferred_supplier_for(
    db: AsyncSession, tenant_id: uuid.UUID, ingredient_id: uuid.UUID
) -> SupplierItem | None:
    """Which supplier to order this ingredient from, if any is known.

    Preference order: the row flagged preferred, then the cheapest active row,
    then nothing. "Cheapest" is a defensible default; guessing silently between
    equals is not, so the flag exists to let a human settle it.
    """
    rows = list(
        (
            await db.execute(
                select(SupplierItem)
                .join(Supplier, Supplier.id == SupplierItem.supplier_id)
                .where(
                    SupplierItem.tenant_id == tenant_id,
                    SupplierItem.ingredient_id == ingredient_id,
                    SupplierItem.is_active == True,  # noqa: E712
                    Supplier.is_active == True,  # noqa: E712
                )
                .options(selectinload(SupplierItem.supplier))
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return None
    preferred = [r for r in rows if r.is_preferred]
    if preferred:
        return preferred[0]
    return min(rows, key=lambda r: Decimal(str(r.last_price_minor)))


async def record_purchase_price(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    supplier_id: uuid.UUID,
    ingredient_id: uuid.UUID,
    unit_price_minor: Decimal,
) -> None:
    """Remember what we last actually paid this supplier for this ingredient.

    Called on goods receipt, not on PO creation: what was quoted and what was
    charged are not always the same number, and the useful one is the second.
    Creates the catalogue row if the buyer ordered something not yet listed.
    """
    price = Decimal(str(unit_price_minor))
    if price < 0:
        raise ProcurementError("A purchase price cannot be negative.")

    item = (
        await db.execute(
            select(SupplierItem).where(
                SupplierItem.supplier_id == supplier_id,
                SupplierItem.ingredient_id == ingredient_id,
            )
        )
    ).scalar_one_or_none()

    if item is None:
        item = SupplierItem(
            tenant_id=tenant_id,
            supplier_id=supplier_id,
            ingredient_id=ingredient_id,
        )
        db.add(item)

    item.last_price_minor = price
    item.last_purchased_at = datetime.now(timezone.utc)
    await db.flush()


async def supplier_purchase_history(
    db: AsyncSession, tenant_id: uuid.UUID, supplier_id: uuid.UUID, limit: int = 100
) -> list[dict]:
    """Every PO placed with this supplier, newest first (Martin's Section 5.1)."""
    await get_supplier(db, tenant_id, supplier_id)
    rows = (
        await db.execute(
            select(PurchaseOrder)
            .where(
                PurchaseOrder.tenant_id == tenant_id,
                PurchaseOrder.supplier_id == supplier_id,
            )
            .options(selectinload(PurchaseOrder.location))
            .order_by(PurchaseOrder.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    return [
        {
            "id": po.id,
            "po_number": po.po_number,
            "status": po.status,
            "location_id": po.location_id,
            "location_name": po.location.name,
            "expected_date": po.expected_date,
            "total_minor": po.total_minor,
            "sent_at": po.sent_at,
            "fully_received_at": po.fully_received_at,
            "created_at": po.created_at,
        }
        for po in rows
    ]


async def supplier_spend_totals(
    db: AsyncSession, tenant_id: uuid.UUID
) -> dict[uuid.UUID, dict]:
    """Order count and total spend per supplier, for the list screen.

    Cancelled and draft POs are excluded: neither represents money committed.
    """
    rows = (
        await db.execute(
            select(
                PurchaseOrder.supplier_id,
                func.count(PurchaseOrder.id),
                func.coalesce(func.sum(PurchaseOrder.total_minor), 0),
            )
            .where(
                PurchaseOrder.tenant_id == tenant_id,
                PurchaseOrder.status.notin_(["draft", "cancelled"]),
            )
            .group_by(PurchaseOrder.supplier_id)
        )
    ).all()
    return {
        supplier_id: {"order_count": count, "total_spend_minor": Decimal(str(total))}
        for supplier_id, count, total in rows
    }
