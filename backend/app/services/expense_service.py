"""Operating expenses: capture, categorise, attach the invoice, total it up.

Martin's M10. See `app/models/expense.py` for why this module never touches
stock and why money here is in minor units.

Everything is tenant-scoped through the `tenant_id` argument, which comes from
the caller's token and is never accepted from the request body.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.expense import (
    DEFAULT_EXPENSE_CATEGORIES,
    EXPENSE_COUNTED_STATUSES,
    EXPENSE_STATUSES,
    Expense,
    ExpenseAttachment,
    ExpenseCategory,
)
from app.models.location import Location
from app.models.media import MediaFile


class ExpenseError(ValueError):
    """An expense action that cannot be performed as asked.

    Always the caller's problem, never a 500. The API layer turns it into a 400,
    exactly as `StockError` and `ProcurementError` are handled.
    """


# ---------------------------------------------------------------------------
# CATEGORIES
# ---------------------------------------------------------------------------


async def ensure_default_categories(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[ExpenseCategory]:
    """Give a tenant the starter set, once.

    Called lazily from `list_categories` rather than from tenant creation, so a
    tenant that predates this module gets its categories the first time anybody
    opens the screen. Idempotent: it only inserts names that are missing, so
    a category the operator deleted does not come back on the next page load
    -- deletion is a deactivation, and the row still exists to be skipped.
    """
    existing = {
        name
        for (name,) in (
            await db.execute(
                select(ExpenseCategory.name).where(
                    ExpenseCategory.tenant_id == tenant_id
                )
            )
        ).all()
    }
    created: list[ExpenseCategory] = []
    for index, name in enumerate(DEFAULT_EXPENSE_CATEGORIES):
        if name in existing:
            continue
        row = ExpenseCategory(tenant_id=tenant_id, name=name, sort_order=index)
        db.add(row)
        created.append(row)
    if created:
        await db.flush()
    return created


async def list_categories(
    db: AsyncSession, tenant_id: uuid.UUID, include_inactive: bool = False
) -> list[dict]:
    """The category list, each with how many expenses it carries.

    The count is what makes deactivation safe to offer: a category with 40
    expenses behind it must not look like a free thing to delete.
    """
    await ensure_default_categories(db, tenant_id)

    counts = {
        category_id: count
        for category_id, count in (
            await db.execute(
                select(Expense.category_id, func.count(Expense.id))
                .where(Expense.tenant_id == tenant_id)
                .group_by(Expense.category_id)
            )
        ).all()
    }

    stmt = select(ExpenseCategory).where(ExpenseCategory.tenant_id == tenant_id)
    if not include_inactive:
        stmt = stmt.where(ExpenseCategory.is_active == True)  # noqa: E712
    stmt = stmt.order_by(ExpenseCategory.sort_order, ExpenseCategory.name)

    rows = list((await db.execute(stmt)).scalars().all())
    return [
        {
            "id": row.id,
            "name": row.name,
            "sort_order": row.sort_order,
            "is_active": row.is_active,
            "notes": row.notes,
            "expense_count": counts.get(row.id, 0),
        }
        for row in rows
    ]


async def get_category(
    db: AsyncSession, tenant_id: uuid.UUID, category_id: uuid.UUID
) -> ExpenseCategory:
    row = (
        await db.execute(
            select(ExpenseCategory).where(
                ExpenseCategory.id == category_id,
                ExpenseCategory.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise ExpenseError("No such expense category for this restaurant.")
    return row


async def create_category(
    db: AsyncSession, tenant_id: uuid.UUID, name: str, notes: str | None = None
) -> ExpenseCategory:
    clean = (name or "").strip()
    if not clean:
        raise ExpenseError("A category needs a name.")

    clash = (
        await db.execute(
            select(ExpenseCategory).where(
                ExpenseCategory.tenant_id == tenant_id,
                func.lower(ExpenseCategory.name) == clean.lower(),
            )
        )
    ).scalar_one_or_none()
    if clash is not None:
        # Reactivating beats erroring: "Rent already exists but you deleted it"
        # is a worse answer than simply making it true again.
        if not clash.is_active:
            clash.is_active = True
            await db.flush()
            return clash
        raise ExpenseError(f"A category called {clash.name!r} already exists.")

    highest = (
        await db.execute(
            select(func.coalesce(func.max(ExpenseCategory.sort_order), 0)).where(
                ExpenseCategory.tenant_id == tenant_id
            )
        )
    ).scalar_one()
    row = ExpenseCategory(
        tenant_id=tenant_id,
        name=clean,
        notes=notes,
        sort_order=int(highest) + 1,
    )
    db.add(row)
    await db.flush()
    return row


async def update_category(
    db: AsyncSession, tenant_id: uuid.UUID, category_id: uuid.UUID, data: dict
) -> ExpenseCategory:
    row = await get_category(db, tenant_id, category_id)

    if "name" in data and data["name"] is not None:
        clean = str(data["name"]).strip()
        if not clean:
            raise ExpenseError("A category needs a name.")
        clash = (
            await db.execute(
                select(ExpenseCategory).where(
                    ExpenseCategory.tenant_id == tenant_id,
                    ExpenseCategory.id != category_id,
                    func.lower(ExpenseCategory.name) == clean.lower(),
                )
            )
        ).scalar_one_or_none()
        if clash is not None:
            raise ExpenseError(f"A category called {clash.name!r} already exists.")
        row.name = clean

    for field in ("sort_order", "is_active", "notes"):
        if field in data and data[field] is not None:
            setattr(row, field, data[field])

    await db.flush()
    return row


async def delete_category(
    db: AsyncSession, tenant_id: uuid.UUID, category_id: uuid.UUID
) -> ExpenseCategory:
    """Deactivate rather than delete.

    An expense filed last March under a category deleted in September must keep
    reading "Rent" on the report that covers March. Hard deletion would null the
    FK and silently rewrite history as "Uncategorised".
    """
    row = await get_category(db, tenant_id, category_id)
    row.is_active = False
    await db.flush()
    return row


# ---------------------------------------------------------------------------
# EXPENSES
# ---------------------------------------------------------------------------


def serialise(expense: Expense) -> dict:
    """Flatten one expense for the wire, resolving the names the UI needs.

    Every relationship read here is eager-loaded by the queries below. A lazy
    load on an async session raises MissingGreenlet, which is how the recipe
    routes broke on 2026-09-01.
    """
    return {
        "id": expense.id,
        "expense_date": expense.expense_date,
        "payee": expense.payee,
        "description": expense.description,
        "reference_number": expense.reference_number,
        "amount_minor": expense.amount_minor,
        "tax_minor": expense.tax_minor,
        # Explicit rather than left to the client: the net is the number an
        # accountant reads, and computing it in three different screens is how
        # three different answers appear.
        "net_minor": Decimal(str(expense.amount_minor))
        - Decimal(str(expense.tax_minor)),
        "status": expense.status,
        "payment_method": expense.payment_method,
        "paid_on": expense.paid_on,
        "notes": expense.notes,
        "category_id": expense.category_id,
        "category_name": expense.category.name if expense.category else None,
        "location_id": expense.location_id,
        "location_name": expense.location.name if expense.location else None,
        "recorded_by": expense.recorded_by,
        "recorded_by_name": (
            expense.recorder.full_name if expense.recorder is not None else None
        ),
        "created_at": expense.created_at,
        "attachments": [
            {
                "id": a.id,
                "media_id": a.media_id,
                "filename": a.filename,
                "content_type": a.content_type,
                "size_bytes": a.size_bytes,
                # Relative, and routed through the expenses router rather than
                # /media/{id}: an expense invoice is a salary or a rent bill,
                # and /media is deliberately unauthenticated so an <img> tag
                # can fetch a menu photograph. This one needs a token.
                "url": f"/api/v1/expenses/{a.expense_id}/attachments/{a.id}",
            }
            for a in expense.attachments
        ],
    }


_LOADS = (
    selectinload(Expense.category),
    selectinload(Expense.location),
    selectinload(Expense.recorder),
    selectinload(Expense.attachments),
)


async def list_expenses(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    status: str | None = None,
    search: str | None = None,
    limit: int = 200,
) -> list[dict]:
    stmt = select(Expense).where(Expense.tenant_id == tenant_id)
    if date_from is not None:
        stmt = stmt.where(Expense.expense_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Expense.expense_date <= date_to)
    if category_id is not None:
        stmt = stmt.where(Expense.category_id == category_id)
    if location_id is not None:
        stmt = stmt.where(Expense.location_id == location_id)
    if status:
        stmt = stmt.where(Expense.status == status)
    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            func.lower(Expense.payee).like(needle)
            | func.lower(func.coalesce(Expense.reference_number, "")).like(needle)
            | func.lower(func.coalesce(Expense.description, "")).like(needle)
        )
    stmt = (
        stmt.options(*_LOADS)
        .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [serialise(row) for row in rows]


async def get_expense(
    db: AsyncSession, tenant_id: uuid.UUID, expense_id: uuid.UUID
) -> Expense:
    row = (
        await db.execute(
            select(Expense)
            .where(Expense.id == expense_id, Expense.tenant_id == tenant_id)
            .options(*_LOADS)
        )
    ).scalar_one_or_none()
    if row is None:
        raise ExpenseError("No such expense for this restaurant.")
    return row


async def _validate(
    db: AsyncSession, tenant_id: uuid.UUID, data: dict
) -> None:
    """Check every foreign key and every enum before anything is written.

    Foreign keys are checked against the tenant, not just against the table:
    without the tenant clause a caller could file their expense under another
    restaurant's category and read its name back on their own screen.
    """
    status = data.get("status")
    if status is not None and status not in EXPENSE_STATUSES:
        raise ExpenseError(
            f"{status!r} is not an expense status. Use one of: "
            + ", ".join(EXPENSE_STATUSES)
        )

    category_id = data.get("category_id")
    if category_id is not None:
        await get_category(db, tenant_id, category_id)

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
            raise ExpenseError("No such location for this restaurant.")

    amount = data.get("amount_minor")
    tax = data.get("tax_minor")
    if amount is not None and Decimal(str(amount)) < 0:
        raise ExpenseError("An expense amount cannot be negative.")
    if tax is not None and Decimal(str(tax)) < 0:
        raise ExpenseError("A tax amount cannot be negative.")
    if amount is not None and tax is not None and Decimal(str(tax)) > Decimal(str(amount)):
        raise ExpenseError(
            "The VAT cannot be more than the invoice total. The total includes "
            "the VAT, it is not added on top."
        )


async def create_expense(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: dict,
    recorded_by: uuid.UUID | None = None,
) -> Expense:
    payee = (data.get("payee") or "").strip()
    if not payee:
        raise ExpenseError("An expense needs to say who was paid.")
    await _validate(db, tenant_id, data)

    fields = {k: v for k, v in data.items() if k != "payee"}
    expense = Expense(
        tenant_id=tenant_id, payee=payee, recorded_by=recorded_by, **fields
    )
    _apply_paid_on(expense)
    db.add(expense)
    await db.flush()
    return await get_expense(db, tenant_id, expense.id)


async def update_expense(
    db: AsyncSession, tenant_id: uuid.UUID, expense_id: uuid.UUID, data: dict
) -> Expense:
    expense = await get_expense(db, tenant_id, expense_id)

    # Validate against the state the row will be IN, not the state it is in.
    # Sending only `tax_minor` has to be checked against the stored amount, and
    # checking the patch alone would let a 500 AED VAT onto a 100 AED invoice.
    merged = {
        "status": data.get("status", expense.status),
        "category_id": data.get("category_id", expense.category_id),
        "location_id": data.get("location_id", expense.location_id),
        "amount_minor": data.get("amount_minor", expense.amount_minor),
        "tax_minor": data.get("tax_minor", expense.tax_minor),
    }
    await _validate(db, tenant_id, merged)

    if "payee" in data:
        clean = (data["payee"] or "").strip()
        if not clean:
            raise ExpenseError("An expense needs to say who was paid.")
        expense.payee = clean

    for field, value in data.items():
        if field == "payee":
            continue
        setattr(expense, field, value)

    _apply_paid_on(expense)
    await db.flush()
    return await get_expense(db, tenant_id, expense_id)


def _apply_paid_on(expense: Expense) -> None:
    """Keep `paid_on` honest against `status`.

    Marking an expense paid without saying when defaults to its own date, which
    is nearly always right for rent and salaries. Marking it back to unpaid
    clears the date, because a payment date on an unpaid bill is a lie the
    cash-flow report would repeat.
    """
    if expense.status == "paid":
        if expense.paid_on is None:
            expense.paid_on = expense.expense_date
    else:
        expense.paid_on = None


async def delete_expense(
    db: AsyncSession, tenant_id: uuid.UUID, expense_id: uuid.UUID
) -> None:
    """Hard delete, attachments and all.

    Safe here, unlike a supplier or a category: nothing references an expense,
    it carries no stock movement, and a mistyped invoice that cannot be removed
    would sit in the totals forever. The attachment rows go with it by cascade;
    the media rows are removed explicitly because nothing else points at them.
    """
    expense = await get_expense(db, tenant_id, expense_id)
    media_ids = [a.media_id for a in expense.attachments]
    await db.delete(expense)
    await db.flush()
    for media_id in media_ids:
        media = (
            await db.execute(select(MediaFile).where(MediaFile.id == media_id))
        ).scalar_one_or_none()
        if media is not None:
            await db.delete(media)
    if media_ids:
        await db.flush()


# ---------------------------------------------------------------------------
# ATTACHMENTS
# ---------------------------------------------------------------------------


async def add_attachment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    expense_id: uuid.UUID,
    media: MediaFile,
    filename: str | None,
) -> ExpenseAttachment:
    expense = await get_expense(db, tenant_id, expense_id)
    row = ExpenseAttachment(
        tenant_id=tenant_id,
        expense_id=expense.id,
        media_id=media.id,
        filename=(filename or "")[:255] or None,
        content_type=media.content_type,
        size_bytes=media.size_bytes,
    )
    db.add(row)
    await db.flush()
    return row


async def get_attachment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    expense_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> ExpenseAttachment:
    """Fetch one attachment, scoped to BOTH the tenant and its expense.

    Both clauses matter. The tenant clause stops another restaurant's invoice
    being read; the expense clause stops an attachment id from one expense being
    served under another's URL, which is what makes the path itself trustworthy.
    """
    row = (
        await db.execute(
            select(ExpenseAttachment).where(
                ExpenseAttachment.id == attachment_id,
                ExpenseAttachment.expense_id == expense_id,
                ExpenseAttachment.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise ExpenseError("No such attachment on this expense.")
    return row


async def remove_attachment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    expense_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> None:
    row = await get_attachment(db, tenant_id, expense_id, attachment_id)
    media_id = row.media_id
    await db.delete(row)
    await db.flush()
    media = (
        await db.execute(select(MediaFile).where(MediaFile.id == media_id))
    ).scalar_one_or_none()
    if media is not None:
        await db.delete(media)
        await db.flush()


# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------


async def summary(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    location_id: uuid.UUID | None = None,
) -> dict:
    """Totals for the period, and a breakdown per category.

    🔴 `draft` expenses are excluded from every number here. A half-entered
    invoice is not money owed, and letting it into the total would make the
    screen disagree with the accounts for reasons nobody could see.
    """
    base = select(Expense).where(
        Expense.tenant_id == tenant_id,
        Expense.status.in_(EXPENSE_COUNTED_STATUSES),
    )
    if date_from is not None:
        base = base.where(Expense.expense_date >= date_from)
    if date_to is not None:
        base = base.where(Expense.expense_date <= date_to)
    if location_id is not None:
        base = base.where(Expense.location_id == location_id)

    subq = base.subquery()

    totals = (
        await db.execute(
            select(
                func.coalesce(func.sum(subq.c.amount_minor), 0),
                func.coalesce(func.sum(subq.c.tax_minor), 0),
                func.count(subq.c.id),
            )
        )
    ).one()
    total_minor, tax_total_minor, count = totals

    unpaid = (
        await db.execute(
            select(func.coalesce(func.sum(subq.c.amount_minor), 0)).where(
                subq.c.status == "unpaid"
            )
        )
    ).scalar_one()

    per_category = (
        await db.execute(
            select(
                subq.c.category_id,
                func.coalesce(func.sum(subq.c.amount_minor), 0),
                func.count(subq.c.id),
            ).group_by(subq.c.category_id)
        )
    ).all()

    names = {
        row.id: row.name
        for row in (
            await db.execute(
                select(ExpenseCategory).where(ExpenseCategory.tenant_id == tenant_id)
            )
        )
        .scalars()
        .all()
    }

    breakdown = sorted(
        (
            {
                "category_id": category_id,
                "category_name": names.get(category_id, "Uncategorised"),
                "total_minor": Decimal(str(total)),
                "expense_count": int(rows),
            }
            for category_id, total, rows in per_category
        ),
        key=lambda row: row["total_minor"],
        reverse=True,
    )

    return {
        "date_from": date_from,
        "date_to": date_to,
        "location_id": location_id,
        "total_minor": Decimal(str(total_minor)),
        "tax_total_minor": Decimal(str(tax_total_minor)),
        "net_minor": Decimal(str(total_minor)) - Decimal(str(tax_total_minor)),
        "unpaid_minor": Decimal(str(unpaid)),
        "expense_count": int(count),
        "by_category": breakdown,
    }
