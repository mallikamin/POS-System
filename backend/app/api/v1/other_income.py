"""Other income: money in that is not a sale (Danny's D-63).

Every endpoint is tenant-scoped through `current_user.tenant_id`; the tenant
is never read from the request body. Same role split as the expenses router:
the books are an admin's and a manager's.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.models.user import User
from app.schemas.other_income import (
    IncomeCategoryCreate,
    IncomeCategoryResponse,
    IncomeMethod,
    OpeningBalanceResponse,
    OpeningBalanceSet,
    OtherIncomeCreate,
    OtherIncomeResponse,
    OtherIncomeUpdate,
)
from app.services import other_income_service
from app.services.other_income_service import IncomeError

router = APIRouter(prefix="/other-income", tags=["other-income"])
# D-62, beside the income it is rolled forward with in the day summary.
opening_router = APIRouter(prefix="/opening-balance", tags=["other-income"])

_books = require_role("admin", "manager")


def _bad_request(exc: IncomeError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# Declared before /{income_id} so "categories" is never parsed as an id.
@router.get("/categories", response_model=list[IncomeCategoryResponse])
async def list_categories(
    current_user: User = Depends(_books),
    db: AsyncSession = Depends(get_db),
) -> list[IncomeCategoryResponse]:
    rows = await other_income_service.list_categories(db, current_user.tenant_id)
    # Committed because the first call seeds the starter set.
    await db.commit()
    return [IncomeCategoryResponse(**row) for row in rows]


@router.post(
    "/categories",
    response_model=IncomeCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    data: IncomeCategoryCreate,
    current_user: User = Depends(_books),
    db: AsyncSession = Depends(get_db),
) -> IncomeCategoryResponse:
    try:
        row = await other_income_service.create_category(
            db, current_user.tenant_id, data.name
        )
    except IncomeError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    rows = await other_income_service.list_categories(db, current_user.tenant_id)
    match = next((r for r in rows if r["id"] == row.id), None)
    if match is None:  # pragma: no cover - the row was just written
        raise HTTPException(status_code=500, detail="Category vanished after write.")
    return IncomeCategoryResponse(**match)


@router.get("", response_model=list[OtherIncomeResponse])
async def list_income(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    method: IncomeMethod | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    current_user: User = Depends(_books),
    db: AsyncSession = Depends(get_db),
) -> list[OtherIncomeResponse]:
    rows = await other_income_service.list_income(
        db,
        current_user.tenant_id,
        date_from=date_from,
        date_to=date_to,
        category_id=category_id,
        method=method,
        limit=limit,
    )
    return [OtherIncomeResponse(**row) for row in rows]


@router.post(
    "", response_model=OtherIncomeResponse, status_code=status.HTTP_201_CREATED
)
async def create_income(
    data: OtherIncomeCreate,
    current_user: User = Depends(_books),
    db: AsyncSession = Depends(get_db),
) -> OtherIncomeResponse:
    try:
        row = await other_income_service.create_income(
            db, current_user.tenant_id, data.model_dump(), recorded_by=current_user.id
        )
    except IncomeError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    row = await other_income_service.get_income(db, current_user.tenant_id, row.id)
    return OtherIncomeResponse(**other_income_service.serialise(row))


@router.patch("/{income_id}", response_model=OtherIncomeResponse)
async def update_income(
    income_id: uuid.UUID,
    data: OtherIncomeUpdate,
    current_user: User = Depends(_books),
    db: AsyncSession = Depends(get_db),
) -> OtherIncomeResponse:
    try:
        await other_income_service.update_income(
            db, current_user.tenant_id, income_id, data.model_dump(exclude_unset=True)
        )
    except IncomeError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    row = await other_income_service.get_income(db, current_user.tenant_id, income_id)
    return OtherIncomeResponse(**other_income_service.serialise(row))


@router.delete(
    "/{income_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def delete_income(
    income_id: uuid.UUID,
    current_user: User = Depends(_books),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await other_income_service.delete_income(db, current_user.tenant_id, income_id)
    except IncomeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()


# ---------------------------------------------------------------------------
# OPENING BALANCE (D-62)
# ---------------------------------------------------------------------------


@opening_router.get("", response_model=OpeningBalanceResponse | None)
async def get_opening_balance(
    current_user: User = Depends(_books),
    db: AsyncSession = Depends(get_db),
) -> OpeningBalanceResponse | None:
    """The tenant's opening cash balance, or null when none is recorded."""
    row = await other_income_service.get_opening_balance(db, current_user.tenant_id)
    if row is None:
        return None
    return OpeningBalanceResponse(**other_income_service.serialise_opening(row))


@opening_router.put("", response_model=OpeningBalanceResponse)
async def set_opening_balance(
    data: OpeningBalanceSet,
    current_user: User = Depends(_books),
    db: AsyncSession = Depends(get_db),
) -> OpeningBalanceResponse:
    try:
        await other_income_service.set_opening_balance(
            db,
            current_user.tenant_id,
            as_of=data.as_of,
            cash_minor=data.cash_minor,
            notes=data.notes,
            recorded_by=current_user.id,
        )
    except IncomeError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    row = await other_income_service.get_opening_balance(db, current_user.tenant_id)
    if row is None:  # pragma: no cover - the row was just written
        raise HTTPException(status_code=500, detail="Opening balance vanished after write.")
    return OpeningBalanceResponse(**other_income_service.serialise_opening(row))