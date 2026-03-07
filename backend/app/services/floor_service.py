"""Floor service -- business logic for floors and tables."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.floor import Floor, Table
from app.models.order import Order
from app.models.table_session import TableSession
from app.schemas.floor import (
    FloorCreate,
    FloorUpdate,
    TableCreate,
    TableUpdate,
    BulkTablePositionUpdate,
)


# ---------------------------------------------------------------------------
# Floors
# ---------------------------------------------------------------------------


async def list_floors(
    db: AsyncSession, tenant_id: uuid.UUID, active_only: bool = False
) -> list[Floor]:
    stmt = (
        select(Floor)
        .options(selectinload(Floor.tables))
        .where(Floor.tenant_id == tenant_id)
        .order_by(Floor.display_order, Floor.name)
    )
    if active_only:
        stmt = stmt.where(Floor.is_active == True)  # noqa: E712
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def get_floor(
    db: AsyncSession, floor_id: uuid.UUID, tenant_id: uuid.UUID
) -> Floor | None:
    result = await db.execute(
        select(Floor)
        .options(selectinload(Floor.tables))
        .where(Floor.id == floor_id, Floor.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def create_floor(
    db: AsyncSession, tenant_id: uuid.UUID, data: FloorCreate
) -> Floor:
    floor = Floor(
        tenant_id=tenant_id,
        name=data.name,
        display_order=data.display_order,
        is_active=data.is_active,
    )
    db.add(floor)
    await db.flush()
    # Reload with tables relationship
    return await get_floor(db, floor.id, tenant_id)  # type: ignore[return-value]


async def update_floor(db: AsyncSession, floor: Floor, data: FloorUpdate) -> Floor:
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(floor, field, value)
    await db.flush()
    return floor


async def delete_floor(db: AsyncSession, floor: Floor) -> None:
    await db.delete(floor)
    await db.flush()


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


async def list_tables(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    floor_id: uuid.UUID | None = None,
    active_only: bool = False,
) -> list[Table]:
    stmt = select(Table).where(Table.tenant_id == tenant_id).order_by(Table.number)
    if floor_id is not None:
        stmt = stmt.where(Table.floor_id == floor_id)
    if active_only:
        stmt = stmt.where(Table.is_active == True)  # noqa: E712
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_table(
    db: AsyncSession, table_id: uuid.UUID, tenant_id: uuid.UUID
) -> Table | None:
    result = await db.execute(
        select(Table).where(Table.id == table_id, Table.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def create_table(
    db: AsyncSession, tenant_id: uuid.UUID, data: TableCreate
) -> Table:
    table = Table(
        tenant_id=tenant_id,
        floor_id=data.floor_id,
        number=data.number,
        label=data.label,
        capacity=data.capacity,
        pos_x=data.pos_x,
        pos_y=data.pos_y,
        width=data.width,
        height=data.height,
        rotation=data.rotation,
        shape=data.shape,
        is_active=data.is_active,
    )
    db.add(table)
    await db.flush()
    return table


async def update_table(db: AsyncSession, table: Table, data: TableUpdate) -> Table:
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(table, field, value)
    await db.flush()
    return table


async def delete_table(db: AsyncSession, table: Table) -> None:
    await db.delete(table)
    await db.flush()


async def bulk_update_positions(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: BulkTablePositionUpdate,
) -> list[Table]:
    """Batch update table positions from the floor editor drag-and-drop."""
    table_ids = [t.id for t in data.tables]
    result = await db.execute(
        select(Table).where(
            Table.id.in_(table_ids),
            Table.tenant_id == tenant_id,
        )
    )
    tables_by_id = {t.id: t for t in result.scalars().all()}

    updated: list[Table] = []
    for pos in data.tables:
        table = tables_by_id.get(pos.id)
        if table is None:
            continue
        table.pos_x = pos.pos_x
        table.pos_y = pos.pos_y
        table.width = pos.width
        table.height = pos.height
        table.rotation = pos.rotation
        updated.append(table)

    await db.flush()
    return updated


async def reconcile_table_occupancy(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> None:
    """Normalize occupied/available table states from live operational data.

    Keeps manual states (`reserved`, `cleaning`) untouched.
    A table should be occupied if it has:
    - an open table session, or
    - non-voided dine-in orders still not fully settled.
    """
    tables_result = await db.execute(
        select(Table).where(Table.tenant_id == tenant_id, Table.is_active == True)  # noqa: E712
    )
    tables = list(tables_result.scalars().all())
    if not tables:
        return

    # A table is occupied when it has unsettled orders: non-voided,
    # non-completed orders that are NOT fully paid/refunded.
    # Once payment is settled the table turns available regardless of
    # the order's kitchen pipeline status.

    open_session_result = await db.execute(
        select(TableSession.table_id)
        .join(
            Order,
            (Order.table_session_id == TableSession.id)
            & (Order.tenant_id == tenant_id),
        )
        .where(
            TableSession.tenant_id == tenant_id,
            TableSession.status == "open",
            Order.status.notin_(["voided", "completed"]),
            Order.payment_status.notin_(["paid", "refunded"]),
            TableSession.table_id.is_not(None),
        )
        .distinct()
    )
    open_session_tables = {
        row[0] for row in open_session_result.all() if row[0] is not None
    }

    active_order_result = await db.execute(
        select(Order.table_id).where(
            Order.tenant_id == tenant_id,
            Order.order_type == "dine_in",
            Order.status.notin_(["voided", "completed"]),
            Order.payment_status.notin_(["paid", "refunded"]),
            Order.table_id.is_not(None),
        )
    )
    active_order_tables = {
        row[0] for row in active_order_result.all() if row[0] is not None
    }

    should_be_occupied = open_session_tables | active_order_tables

    changed = False
    for table in tables:
        if table.status in {"reserved", "cleaning"}:
            continue
        if table.id in should_be_occupied:
            if table.status != "occupied":
                table.status = "occupied"
                changed = True
        elif table.status == "occupied":
            table.status = "available"
            changed = True

    if changed:
        await db.flush()
