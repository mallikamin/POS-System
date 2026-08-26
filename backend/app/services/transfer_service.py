"""Moving stock between locations.

Deliberately two-phase. `send` takes the stock out of the source immediately;
`receive` puts it into the destination only when someone confirms it arrived.

The alternative -- one instantaneous move -- is simpler and wrong: goods in a
van would be counted as available at the destination before they got there, and
a short delivery would silently vanish instead of showing up as a difference
between what was sent and what was received.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import Ingredient
from app.models.location import StockTransfer, StockTransferItem
from app.services import stock_service
from app.services.stock_service import StockError


async def _next_transfer_number(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    """Sequential per tenant, date-stamped: TRF-260826-003."""
    today = datetime.now(timezone.utc)
    prefix = f"TRF-{today:%y%m%d}-"
    result = await db.execute(
        select(func.count(StockTransfer.id)).where(
            StockTransfer.tenant_id == tenant_id,
            StockTransfer.transfer_number.like(f"{prefix}%"),
        )
    )
    return f"{prefix}{result.scalar_one() + 1:03d}"


async def create_transfer(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    from_location_id: uuid.UUID,
    to_location_id: uuid.UUID,
    lines: list[dict],
    created_by: uuid.UUID | None = None,
    notes: str | None = None,
) -> StockTransfer:
    """Draft a transfer. Nothing moves until it is sent.

    `lines` is [{"ingredient_id": UUID, "quantity": Decimal}, ...].
    """
    if from_location_id == to_location_id:
        raise StockError("A transfer needs two different locations.")
    if not lines:
        raise StockError("A transfer needs at least one item.")

    # Both must exist and belong to this tenant. resolve_location raises if not.
    await stock_service.resolve_location(db, tenant_id, from_location_id)
    await stock_service.resolve_location(db, tenant_id, to_location_id)

    transfer = StockTransfer(
        tenant_id=tenant_id,
        transfer_number=await _next_transfer_number(db, tenant_id),
        from_location_id=from_location_id,
        to_location_id=to_location_id,
        status="draft",
        created_by=created_by,
        notes=notes,
    )
    db.add(transfer)
    # Flush before adding children that reference transfer.id -- the async
    # flush-before-FK rule this codebase has been bitten by before.
    await db.flush()

    for line in lines:
        quantity = Decimal(str(line["quantity"]))
        if quantity <= 0:
            raise StockError("Transfer quantities must be greater than zero.")

        ingredient = (
            await db.execute(
                select(Ingredient).where(
                    Ingredient.id == line["ingredient_id"],
                    Ingredient.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if ingredient is None:
            raise StockError("No such ingredient for this restaurant.")

        db.add(
            StockTransferItem(
                tenant_id=tenant_id,
                transfer_id=transfer.id,
                ingredient_id=ingredient.id,
                quantity_sent=quantity,
                unit=ingredient.unit,
                unit_cost=ingredient.cost_per_unit,
            )
        )

    await db.flush()
    return await get_transfer(db, tenant_id, transfer.id)


async def get_transfer(
    db: AsyncSession, tenant_id: uuid.UUID, transfer_id: uuid.UUID
) -> StockTransfer:
    result = await db.execute(
        select(StockTransfer)
        .where(StockTransfer.id == transfer_id, StockTransfer.tenant_id == tenant_id)
        .options(
            selectinload(StockTransfer.items).selectinload(StockTransferItem.ingredient),
            selectinload(StockTransfer.from_location),
            selectinload(StockTransfer.to_location),
        )
    )
    transfer = result.scalar_one_or_none()
    if transfer is None:
        raise StockError("No such transfer for this restaurant.")
    return transfer


async def send_transfer(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    transfer_id: uuid.UUID,
    performed_by: uuid.UUID | None = None,
) -> StockTransfer:
    """Take the stock out of the source location. Destination unchanged."""
    transfer = await get_transfer(db, tenant_id, transfer_id)
    if transfer.status != "draft":
        raise StockError(
            f"Only a draft transfer can be sent; this one is {transfer.status}."
        )

    for item in transfer.items:
        await stock_service.move_stock(
            db,
            tenant_id=tenant_id,
            ingredient_id=item.ingredient_id,
            quantity_delta=-Decimal(str(item.quantity_sent)),
            transaction_type="transfer_out",
            location_id=transfer.from_location_id,
            unit_cost=item.unit_cost,
            performed_by=performed_by,
            reference_number=transfer.transfer_number,
            notes=f"Sent to {transfer.to_location.name}",
        )

    transfer.status = "in_transit"
    transfer.sent_at = datetime.now(timezone.utc)
    await db.flush()
    return await get_transfer(db, tenant_id, transfer_id)


async def receive_transfer(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    transfer_id: uuid.UUID,
    received: dict[uuid.UUID, Decimal] | None = None,
    performed_by: uuid.UUID | None = None,
) -> StockTransfer:
    """Confirm arrival and add stock to the destination.

    `received` optionally maps transfer-item id -> quantity actually received,
    for a short delivery. Anything not named is assumed to have arrived in full.
    A shortfall is left visible as sent-vs-received on the line rather than
    being written off silently; the missing stock simply never arrives anywhere,
    which is the truth.
    """
    transfer = await get_transfer(db, tenant_id, transfer_id)
    if transfer.status != "in_transit":
        raise StockError(
            f"Only a transfer in transit can be received; this one is "
            f"{transfer.status}."
        )

    received = received or {}

    for item in transfer.items:
        qty = Decimal(str(received.get(item.id, item.quantity_sent)))
        if qty < 0:
            raise StockError("Received quantity cannot be negative.")
        if qty > Decimal(str(item.quantity_sent)):
            raise StockError(
                "Received quantity cannot exceed the quantity sent."
            )
        item.quantity_received = qty
        if qty > 0:
            await stock_service.move_stock(
                db,
                tenant_id=tenant_id,
                ingredient_id=item.ingredient_id,
                quantity_delta=qty,
                transaction_type="transfer_in",
                location_id=transfer.to_location_id,
                unit_cost=item.unit_cost,
                performed_by=performed_by,
                reference_number=transfer.transfer_number,
                notes=f"Received from {transfer.from_location.name}",
            )

    transfer.status = "received"
    transfer.received_at = datetime.now(timezone.utc)
    transfer.received_by = performed_by
    await db.flush()
    return await get_transfer(db, tenant_id, transfer_id)


async def cancel_transfer(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    transfer_id: uuid.UUID,
    performed_by: uuid.UUID | None = None,
) -> StockTransfer:
    """Cancel a transfer. If it was already sent, the stock goes back."""
    transfer = await get_transfer(db, tenant_id, transfer_id)
    if transfer.status == "received":
        raise StockError(
            "A received transfer cannot be cancelled; reverse it with a new "
            "transfer in the other direction so both movements stay on record."
        )
    if transfer.status == "cancelled":
        return transfer

    if transfer.status == "in_transit":
        for item in transfer.items:
            await stock_service.move_stock(
                db,
                tenant_id=tenant_id,
                ingredient_id=item.ingredient_id,
                quantity_delta=Decimal(str(item.quantity_sent)),
                transaction_type="transfer_in",
                location_id=transfer.from_location_id,
                unit_cost=item.unit_cost,
                performed_by=performed_by,
                reference_number=transfer.transfer_number,
                notes="Transfer cancelled, stock returned",
            )

    transfer.status = "cancelled"
    await db.flush()
    return await get_transfer(db, tenant_id, transfer_id)


async def list_transfers(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    status: str | None = None,
    location_id: uuid.UUID | None = None,
) -> list[StockTransfer]:
    stmt = (
        select(StockTransfer)
        .where(StockTransfer.tenant_id == tenant_id)
        .options(
            selectinload(StockTransfer.items).selectinload(StockTransferItem.ingredient),
            selectinload(StockTransfer.from_location),
            selectinload(StockTransfer.to_location),
        )
        .order_by(StockTransfer.created_at.desc())
    )
    if status:
        stmt = stmt.where(StockTransfer.status == status)
    if location_id:
        stmt = stmt.where(
            (StockTransfer.from_location_id == location_id)
            | (StockTransfer.to_location_id == location_id)
        )
    return list((await db.execute(stmt)).scalars().all())
