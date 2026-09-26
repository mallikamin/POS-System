"""Other income: record, categorise, list (Danny's D-63).

See `app/models/other_income.py` for the design. Built on the same rules as
`expense_service`: every foreign key is checked against the tenant, categories
are deactivated rather than deleted, and relationships are eager-loaded because
a lazy load on an async session raises MissingGreenlet.

Everything is tenant-scoped through the `tenant_id` argument, which comes from
the caller's token and is never accepted from the request body.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.location import Location
from app.models.other_income import (
    DEFAULT_INCOME_CATEGORIES,
    INCOME_METHODS,
    IncomeCategory,
    OpeningBalance,
    OtherIncome,
)


class IncomeError(ValueError):
    """An income action that cannot be performed as asked. Always a 400."""


# Columns that cannot be null: a PATCH may change them but never clear them.
_REQUIRED = ("received_on", "payer", "amount_minor", "method")


# ---------------------------------------------------------------------------
# CATEGORIES
# ---------------------------------------------------------------------------


async def ensure_default_categories(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Give a tenant the starter set, once. Only missing names are inserted, so
    a category the operator deactivated does not come back."""
    existing = {
        name
        for (name,) in (
            await db.execute(
                select(IncomeCategory.name).where(IncomeCategory.tenant_id == tenant_id)
            )
        ).all()
    }
    added = False
    for index, name in enumerate(DEFAULT_INCOME_CATEGORIES):
        if name not in existing:
            db.add(IncomeCategory(tenant_id=tenant_id, name=name, sort_order=index))
            added = True
    if added:
        await db.flush()


async def list_categories(db: AsyncSession, tenant_id: uuid.UUID) -> list[dict]:
    await ensure_default_categories(db, tenant_id)
    counts = dict(
        (
            await db.execute(
                select(OtherIncome.category_id, func.count(OtherIncome.id))
                .where(OtherIncome.tenant_id == tenant_id)
                .group_by(OtherIncome.category_id)
            )
        ).all()
    )
    rows = (
        await db.execute(
            select(IncomeCategory)
            .where(
                IncomeCategory.tenant_id == tenant_id,
                IncomeCategory.is_active == True,  # noqa: E712
            )
            .order_by(IncomeCategory.sort_order, IncomeCategory.name)
        )
    ).scalars()
    return [
        {
            "id": row.id,
            "name": row.name,
            "sort_order": row.sort_order,
            "is_active": row.is_active,
            "income_count": counts.get(row.id, 0),
        }
        for row in rows
    ]


async def create_category(
    db: AsyncSession, tenant_id: uuid.UUID, name: str
) -> IncomeCategory:
    clean = (name or "").strip()
    if not clean:
        raise IncomeError("A category needs a name.")
    clash = (
        await db.execute(
            select(IncomeCategory).where(
                IncomeCategory.tenant_id == tenant_id,
                func.lower(IncomeCategory.name) == clean.lower(),
            )
        )
    ).scalar_one_or_none()
    if clash is not None:
        if not clash.is_active:
            clash.is_active = True
            await db.flush()
            return clash
        raise IncomeError(f"A category called {clash.name!r} already exists.")

    highest = (
        await db.execute(
            select(func.coalesce(func.max(IncomeCategory.sort_order), 0)).where(
                IncomeCategory.tenant_id == tenant_id
            )
        )
    ).scalar_one()
    row = IncomeCategory(tenant_id=tenant_id, name=clean, sort_order=int(highest) + 1)
    db.add(row)
    await db.flush()
    return row


# ---------------------------------------------------------------------------
# INCOME
# ---------------------------------------------------------------------------


_LOADS = (
    selectinload(OtherIncome.category),
    selectinload(OtherIncome.location),
    selectinload(OtherIncome.recorder),
)


def serialise(row: OtherIncome) -> dict:
    return {
        "id": row.id,
        "received_on": row.received_on,
        "payer": row.payer,
        "amount_minor": row.amount_minor,
        "method": row.method,
        "category_id": row.category_id,
        "category_name": row.category.name if row.category else None,
        "location_id": row.location_id,
        "location_name": row.location.name if row.location else None,
        "description": row.description,
        "reference_number": row.reference_number,
        "notes": row.notes,
        "recorded_by_name": row.recorder.full_name if row.recorder else None,
        "created_at": row.created_at,
    }


async def list_income(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: uuid.UUID | None = None,
    method: str | None = None,
    limit: int = 200,
) -> list[dict]:
    stmt = select(OtherIncome).where(OtherIncome.tenant_id == tenant_id)
    if date_from is not None:
        stmt = stmt.where(OtherIncome.received_on >= date_from)
    if date_to is not None:
        stmt = stmt.where(OtherIncome.received_on <= date_to)
    if category_id is not None:
        stmt = stmt.where(OtherIncome.category_id == category_id)
    if method:
        stmt = stmt.where(OtherIncome.method == method)
    stmt = (
        stmt.options(*_LOADS)
        .order_by(OtherIncome.received_on.desc(), OtherIncome.created_at.desc())
        .limit(limit)
    )
    return [serialise(row) for row in (await db.execute(stmt)).scalars()]


async def get_income(
    db: AsyncSession, tenant_id: uuid.UUID, income_id: uuid.UUID
) -> OtherIncome:
    row = (
        await db.execute(
            select(OtherIncome)
            .where(OtherIncome.id == income_id, OtherIncome.tenant_id == tenant_id)
            .options(*_LOADS)
        )
    ).scalar_one_or_none()
    if row is None:
        raise IncomeError("No such income record for this restaurant.")
    return row


async def _validate(db: AsyncSession, tenant_id: uuid.UUID, data: dict) -> None:
    """Every foreign key checked against the tenant, not just the table:
    otherwise a caller could file income under another restaurant's category
    and read its name back."""
    for field in _REQUIRED:
        if field in data and data[field] is None:
            raise IncomeError(f"{field} cannot be empty.")
    if "payer" in data and not str(data["payer"]).strip():
        raise IncomeError("Say who the money came from.")
    if data.get("method") is not None and data["method"] not in INCOME_METHODS:
        raise IncomeError("Method must be cash or bank.")
    if data.get("amount_minor") is not None and data["amount_minor"] <= 0:
        raise IncomeError("An income amount must be more than zero.")

    category_id = data.get("category_id")
    if category_id is not None:
        found = (
            await db.execute(
                select(IncomeCategory.id).where(
                    IncomeCategory.id == category_id,
                    IncomeCategory.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if found is None:
            raise IncomeError("No such income category for this restaurant.")

    location_id = data.get("location_id")
    if location_id is not None:
        found = (
            await db.execute(
                select(Location.id).where(
                    Location.id == location_id, Location.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none()
        if found is None:
            raise IncomeError("No such location for this restaurant.")


async def create_income(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: dict,
    recorded_by: uuid.UUID | None = None,
) -> OtherIncome:
    await _validate(db, tenant_id, data)
    data = {**data, "payer": data["payer"].strip()}
    row = OtherIncome(tenant_id=tenant_id, recorded_by=recorded_by, **data)
    db.add(row)
    await db.flush()
    return await get_income(db, tenant_id, row.id)


async def update_income(
    db: AsyncSession, tenant_id: uuid.UUID, income_id: uuid.UUID, data: dict
) -> OtherIncome:
    row = await get_income(db, tenant_id, income_id)
    await _validate(db, tenant_id, data)
    for field, value in data.items():
        setattr(row, field, value.strip() if field == "payer" else value)
    await db.flush()
    # Re-read: the relationships above were loaded for the OLD category.
    db.expunge(row)
    return await get_income(db, tenant_id, income_id)


async def delete_income(
    db: AsyncSession, tenant_id: uuid.UUID, income_id: uuid.UUID
) -> None:
    """Hard delete: nothing references an income row, and a mistyped one that
    cannot be removed would sit in the cash position forever."""
    row = await get_income(db, tenant_id, income_id)
    await db.delete(row)
    await db.flush()


async def cash_received_total(
    db: AsyncSession, tenant_id: uuid.UUID, date_from: date, date_to: date
) -> int:
    """Cash income received on local dates [date_from, date_to], inclusive.
    Used to roll the opening cash balance forward (D-62)."""
    if date_to < date_from:
        return 0
    total = (
        await db.execute(
            select(func.coalesce(func.sum(OtherIncome.amount_minor), 0)).where(
                OtherIncome.tenant_id == tenant_id,
                OtherIncome.received_on >= date_from,
                OtherIncome.received_on <= date_to,
                OtherIncome.method == "cash",
            )
        )
    ).scalar_one()
    return int(total)


# ---------------------------------------------------------------------------
# OPENING BALANCE (D-62)
# ---------------------------------------------------------------------------


async def get_opening_balance(
    db: AsyncSession, tenant_id: uuid.UUID
) -> OpeningBalance | None:
    return (
        await db.execute(
            select(OpeningBalance)
            .where(OpeningBalance.tenant_id == tenant_id)
            .options(selectinload(OpeningBalance.recorder))
        )
    ).scalar_one_or_none()


async def set_opening_balance(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    as_of: date,
    cash_minor: int,
    notes: str | None,
    recorded_by: uuid.UUID | None,
) -> OpeningBalance:
    """Create or correct the tenant's one opening balance."""
    if cash_minor < 0:
        raise IncomeError("Opening cash cannot be negative.")
    row = await get_opening_balance(db, tenant_id)
    if row is None:
        row = OpeningBalance(tenant_id=tenant_id)
        db.add(row)
    row.as_of = as_of
    row.cash_minor = cash_minor
    row.notes = notes
    row.recorded_by = recorded_by
    await db.flush()
    db.expunge(row)
    return await get_opening_balance(db, tenant_id)  # type: ignore[return-value]


def serialise_opening(row: OpeningBalance) -> dict:
    return {
        "as_of": row.as_of,
        "cash_minor": row.cash_minor,
        "notes": row.notes,
        "recorded_by_name": row.recorder.full_name if row.recorder else None,
        "updated_at": row.updated_at or row.created_at,
    }


async def cash_received(
    db: AsyncSession, tenant_id: uuid.UUID, on: date
) -> list[dict]:
    """The day's CASH income, for the day summary cash position. Bank receipts
    are excluded: they never passed through the till."""
    rows = (
        await db.execute(
            select(OtherIncome)
            .where(
                OtherIncome.tenant_id == tenant_id,
                OtherIncome.received_on == on,
                OtherIncome.method == "cash",
            )
            .options(selectinload(OtherIncome.category))
            .order_by(OtherIncome.created_at)
        )
    ).scalars()
    return [
        {
            "payer": row.payer,
            "category_name": row.category.name if row.category else None,
            "amount": row.amount_minor,
        }
        for row in rows
    ]
