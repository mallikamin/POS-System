"""Operating expenses: capture, categorise, attach the invoice (Martin M10).

Every endpoint is tenant-scoped through `current_user.tenant_id`. The tenant is
never read from the request body, so a caller cannot file an expense against
another restaurant or read one back from it.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.expense import (
    ExpenseAttachmentResponse,
    ExpenseCategoryCreate,
    ExpenseCategoryResponse,
    ExpenseCategoryUpdate,
    ExpenseCreate,
    ExpenseResponse,
    ExpenseSummaryResponse,
    ExpenseUpdate,
)
from app.services import expense_service, media_service
from app.services.expense_service import ExpenseError
from app.services.media_service import (
    ImageTooLarge,
    InvalidDocument,
    MAX_UPLOAD_BYTES,
)

router = APIRouter(prefix="/expenses", tags=["expenses"])

# Reading the books is a manager's job; changing them is an admin's. Same split
# the procurement and location routers use.
_read_dep = require_role("admin", "manager")
_write_dep = require_role("admin", "manager")


def _bad_request(exc: ExpenseError) -> HTTPException:
    """An ExpenseError is always the caller's problem, never a 500."""
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# CATEGORIES
#
# Declared before /{expense_id} so "categories" is never parsed as an id. The
# type annotation would reject it anyway, with a 422 instead of a 404, and a
# 422 on a perfectly good URL is the sort of thing that costs an hour.
# ---------------------------------------------------------------------------


@router.get("/categories", response_model=list[ExpenseCategoryResponse])
async def list_categories(
    include_inactive: bool = Query(False),
    current_user: User = Depends(_read_dep),
    db: AsyncSession = Depends(get_db),
) -> list[ExpenseCategoryResponse]:
    """The category list, seeded on first call for a tenant that has none."""
    rows = await expense_service.list_categories(
        db, current_user.tenant_id, include_inactive
    )
    # Committed because `list_categories` seeds the starter set on first call.
    # Without this the same ten rows are inserted and discarded on every page
    # load, and the screen shows categories that vanish on the next request.
    await db.commit()
    return [ExpenseCategoryResponse(**row) for row in rows]


@router.post(
    "/categories",
    response_model=ExpenseCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    data: ExpenseCategoryCreate,
    current_user: User = Depends(_write_dep),
    db: AsyncSession = Depends(get_db),
) -> ExpenseCategoryResponse:
    try:
        row = await expense_service.create_category(
            db, current_user.tenant_id, data.name, data.notes
        )
    except ExpenseError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return ExpenseCategoryResponse(
        id=row.id,
        name=row.name,
        sort_order=row.sort_order,
        is_active=row.is_active,
        notes=row.notes,
        expense_count=0,
    )


@router.patch("/categories/{category_id}", response_model=ExpenseCategoryResponse)
async def update_category(
    category_id: uuid.UUID,
    data: ExpenseCategoryUpdate,
    current_user: User = Depends(_write_dep),
    db: AsyncSession = Depends(get_db),
) -> ExpenseCategoryResponse:
    try:
        row = await expense_service.update_category(
            db,
            current_user.tenant_id,
            category_id,
            data.model_dump(exclude_unset=True),
        )
    except ExpenseError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    rows = await expense_service.list_categories(
        db, current_user.tenant_id, include_inactive=True
    )
    match = next((r for r in rows if r["id"] == row.id), None)
    if match is None:  # pragma: no cover - the row was just written
        raise HTTPException(status_code=500, detail="Category vanished after write.")
    return ExpenseCategoryResponse(**match)


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_category(
    category_id: uuid.UUID,
    current_user: User = Depends(_write_dep),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deactivate. The expenses already filed under it keep reading its name."""
    try:
        await expense_service.delete_category(db, current_user.tenant_id, category_id)
    except ExpenseError as exc:
        raise _bad_request(exc) from exc
    await db.commit()


# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=ExpenseSummaryResponse)
async def expense_summary(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    location_id: uuid.UUID | None = Query(None),
    current_user: User = Depends(_read_dep),
    db: AsyncSession = Depends(get_db),
) -> ExpenseSummaryResponse:
    """Totals for the period and a breakdown per category. Drafts excluded."""
    result = await expense_service.summary(
        db,
        current_user.tenant_id,
        date_from=date_from,
        date_to=date_to,
        location_id=location_id,
    )
    return ExpenseSummaryResponse(**result)


# ---------------------------------------------------------------------------
# EXPENSES
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ExpenseResponse])
async def list_expenses(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    location_id: uuid.UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    current_user: User = Depends(_read_dep),
    db: AsyncSession = Depends(get_db),
) -> list[ExpenseResponse]:
    rows = await expense_service.list_expenses(
        db,
        current_user.tenant_id,
        date_from=date_from,
        date_to=date_to,
        category_id=category_id,
        location_id=location_id,
        status=status_filter,
        search=search,
        limit=limit,
    )
    return [ExpenseResponse(**row) for row in rows]


@router.post(
    "", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED
)
async def create_expense(
    data: ExpenseCreate,
    current_user: User = Depends(_write_dep),
    db: AsyncSession = Depends(get_db),
) -> ExpenseResponse:
    try:
        expense = await expense_service.create_expense(
            db,
            current_user.tenant_id,
            data.model_dump(),
            recorded_by=current_user.id,
        )
    except ExpenseError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    row = await expense_service.get_expense(db, current_user.tenant_id, expense.id)
    return ExpenseResponse(**expense_service.serialise(row))


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: uuid.UUID,
    current_user: User = Depends(_read_dep),
    db: AsyncSession = Depends(get_db),
) -> ExpenseResponse:
    try:
        row = await expense_service.get_expense(db, current_user.tenant_id, expense_id)
    except ExpenseError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ExpenseResponse(**expense_service.serialise(row))


@router.patch("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: uuid.UUID,
    data: ExpenseUpdate,
    current_user: User = Depends(_write_dep),
    db: AsyncSession = Depends(get_db),
) -> ExpenseResponse:
    try:
        await expense_service.update_expense(
            db,
            current_user.tenant_id,
            expense_id,
            data.model_dump(exclude_unset=True),
        )
    except ExpenseError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    row = await expense_service.get_expense(db, current_user.tenant_id, expense_id)
    return ExpenseResponse(**expense_service.serialise(row))


@router.delete(
    "/{expense_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def delete_expense(
    expense_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove the expense and its attachments. Admin only."""
    try:
        await expense_service.delete_expense(db, current_user.tenant_id, expense_id)
    except ExpenseError as exc:
        raise _bad_request(exc) from exc
    await db.commit()


# ---------------------------------------------------------------------------
# ATTACHMENTS
# ---------------------------------------------------------------------------


@router.post(
    "/{expense_id}/attachments",
    response_model=ExpenseAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    expense_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(_write_dep),
    db: AsyncSession = Depends(get_db),
) -> ExpenseAttachmentResponse:
    """Pin a PDF or a photograph of the invoice to this expense."""
    # Read one byte past the cap so an oversize body is recognised without
    # first pulling all of it into memory.
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"An attachment must be {MAX_UPLOAD_BYTES // (1024 * 1024)} MB or smaller.",
        )

    # The expense is checked BEFORE the bytes are stored. Uploading to an id
    # that does not exist would otherwise leave an orphan media row nothing
    # points at and nothing ever deletes.
    try:
        await expense_service.get_expense(db, current_user.tenant_id, expense_id)
    except ExpenseError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        media = await media_service.store_document(
            db, current_user.tenant_id, data, original_filename=file.filename
        )
    except ImageTooLarge:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"An attachment must be {MAX_UPLOAD_BYTES // (1024 * 1024)} MB or smaller.",
        )
    except InvalidDocument as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"That file cannot be attached ({exc}). Use a PDF or a photo.",
        )

    row = await expense_service.add_attachment(
        db, current_user.tenant_id, expense_id, media, file.filename
    )
    await db.commit()
    return ExpenseAttachmentResponse(
        id=row.id,
        media_id=row.media_id,
        filename=row.filename,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        url=f"/api/v1/expenses/{expense_id}/attachments/{row.id}",
    )


@router.get("/{expense_id}/attachments/{attachment_id}")
async def download_attachment(
    expense_id: uuid.UUID,
    attachment_id: uuid.UUID,
    current_user: User = Depends(_read_dep),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Serve one attachment. Authenticated, unlike `/media/{id}`.

    🔴 `Content-Disposition: inline` with an explicit filename, and
    `X-Content-Type-Options: nosniff`. A PDF is stored byte-for-byte, so without
    nosniff a browser is free to sniff a crafted upload as HTML and run it on
    this origin, where the session cookie lives.
    """
    try:
        row = await expense_service.get_attachment(
            db, current_user.tenant_id, expense_id, attachment_id
        )
    except ExpenseError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    media = await media_service.get_media_bytes(db, row.media_id)
    if media is None:
        raise HTTPException(status_code=404, detail="The file is no longer stored.")

    safe_name = (row.filename or "attachment").replace('"', "")
    return Response(
        content=media.data,
        media_type=media.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe_name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=300",
        },
    )


@router.delete(
    "/{expense_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_attachment(
    expense_id: uuid.UUID,
    attachment_id: uuid.UUID,
    current_user: User = Depends(_write_dep),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await expense_service.remove_attachment(
            db, current_user.tenant_id, expense_id, attachment_id
        )
    except ExpenseError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
