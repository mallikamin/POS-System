"""Table session service — open/close/bill for dine-in consolidation."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.discount import OrderDiscount
from app.models.floor import Table
from app.models.order import Order
from app.models.payment import Payment
from app.models.table_session import TableSession


# ---------------------------------------------------------------------------
# Open session (idempotent — returns existing open session if present)
# ---------------------------------------------------------------------------

async def open_session(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    table_id: uuid.UUID,
    notes: str | None = None,
    waiter_id: uuid.UUID | None = None,
) -> TableSession:
    """Open a new table session or return the existing open one."""
    existing = await get_active_session_by_table(db, tenant_id, table_id)
    if existing is not None:
        return existing

    # Verify table exists
    table = await _get_table_or_raise(db, table_id, tenant_id)

    session = TableSession(
        tenant_id=tenant_id,
        table_id=table_id,
        status="open",
        opened_by=user_id,
        assigned_waiter_id=waiter_id,
        notes=notes,
    )
    db.add(session)
    await db.flush()

    # Mark table as occupied
    table.status = "occupied"
    await db.flush()

    return await get_session(db, session.id, tenant_id)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Get session
# ---------------------------------------------------------------------------

async def get_session(
    db: AsyncSession, session_id: uuid.UUID, tenant_id: uuid.UUID
) -> TableSession | None:
    result = await db.execute(
        select(TableSession)
        .options(
            selectinload(TableSession.table),
            selectinload(TableSession.orders),
        )
        .where(TableSession.id == session_id, TableSession.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def get_active_session_by_table(
    db: AsyncSession, tenant_id: uuid.UUID, table_id: uuid.UUID
) -> TableSession | None:
    result = await db.execute(
        select(TableSession)
        .options(
            selectinload(TableSession.table),
            selectinload(TableSession.orders),
        )
        .where(
            TableSession.tenant_id == tenant_id,
            TableSession.table_id == table_id,
            TableSession.status == "open",
        )
        .order_by(TableSession.opened_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Close session
# ---------------------------------------------------------------------------

async def close_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    notes: str | None = None,
) -> TableSession:
    session = await get_session(db, session_id, tenant_id)
    if session is None:
        raise ValueError("Table session not found")
    if session.status == "closed":
        raise ValueError("Session is already closed")

    session.status = "closed"
    session.closed_by = user_id
    session.closed_at = datetime.now(timezone.utc)
    if notes is not None:
        session.notes = notes

    # Free the table
    table = await _get_table_or_raise(db, session.table_id, tenant_id)
    table.status = "available"

    await db.flush()

    # Re-fetch with relationships
    session_id_val = session.id
    db.expunge(session)
    return await get_session(db, session_id_val, tenant_id)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Bill summary
# ---------------------------------------------------------------------------

async def get_bill_summary(
    db: AsyncSession, session_id: uuid.UUID, tenant_id: uuid.UUID
) -> dict:
    """Compute consolidated bill for all non-voided orders in the session."""
    session = await get_session(db, session_id, tenant_id)
    if session is None:
        raise ValueError("Table session not found")

    billable_orders = [
        o for o in session.orders if o.status != "voided"
    ]

    subtotal = sum(o.subtotal for o in billable_orders)
    tax_amount = sum(o.tax_amount for o in billable_orders)
    discount_amount = sum(o.discount_amount for o in billable_orders)
    total = sum(o.total for o in billable_orders)

    # Sum payments across all session orders
    order_ids = [o.id for o in billable_orders]
    paid_amount = 0
    if order_ids:
        result = await db.execute(
            select(Payment).where(
                Payment.tenant_id == tenant_id,
                Payment.order_id.in_(order_ids),
                Payment.status == "completed",
            )
        )
        payments = list(result.scalars().all())
        paid_amount = sum(
            p.amount if p.kind == "payment" else -p.amount
            for p in payments
        )

    # Also include session-level discounts
    session_disc_result = await db.execute(
        select(OrderDiscount.amount).where(
            OrderDiscount.tenant_id == tenant_id,
            OrderDiscount.table_session_id == session_id,
        )
    )
    session_discount = sum(row[0] for row in session_disc_result.all())
    discount_amount += session_discount

    due_amount = max(total - discount_amount - paid_amount, 0)

    return {
        "session_id": session.id,
        "table_id": session.table_id,
        "table_number": session.table.number if session.table else None,
        "table_label": session.table.label if session.table else None,
        "status": session.status,
        "subtotal": subtotal,
        "tax_amount": tax_amount,
        "discount_amount": discount_amount,
        "total": total,
        "paid_amount": paid_amount,
        "due_amount": due_amount,
        "order_count": len(billable_orders),
        "orders": billable_orders,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_table_or_raise(
    db: AsyncSession, table_id: uuid.UUID, tenant_id: uuid.UUID
) -> Table:
    result = await db.execute(
        select(Table).where(Table.id == table_id, Table.tenant_id == tenant_id)
    )
    table = result.scalar_one_or_none()
    if table is None:
        raise ValueError("Table not found")
    return table
