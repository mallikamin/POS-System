"""Staff management endpoints -- list, create, update, reset credentials."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.database import get_db
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.staff import (
    PasswordReset,
    PermissionResponse,
    PinReset,
    RoleCreate,
    RoleDetailResponse,
    RoleUpdate,
    StaffCreate,
    StaffResponse,
    StaffUpdate,
)
from app.services import staff_service
from app.services import audit_service

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get(
    "",
    response_model=PaginatedResponse[StaffResponse],
    dependencies=[Depends(require_role("admin"))],
)
async def list_staff(
    search: str | None = Query(None, description="Search by name or email"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[StaffResponse]:
    users, total = await staff_service.list_staff(
        db, current_user.tenant_id, search=search, page=page, page_size=page_size
    )
    return PaginatedResponse.create(
        items=[StaffResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/roles",
    response_model=list[RoleDetailResponse],
    dependencies=[Depends(require_role("admin"))],
)
async def list_roles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RoleDetailResponse]:
    roles = await staff_service.list_roles(db, current_user.tenant_id)
    return [RoleDetailResponse.model_validate(r) for r in roles]


@router.get(
    "/roles/{role_id}",
    response_model=RoleDetailResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def get_role(
    role_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RoleDetailResponse:
    role = await staff_service.get_role(db, current_user.tenant_id, role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    return RoleDetailResponse.model_validate(role)


@router.post(
    "/roles",
    response_model=RoleDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin"))],
)
async def create_role(
    data: RoleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RoleDetailResponse:
    try:
        role = await staff_service.create_role(db, current_user.tenant_id, data)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    await db.commit()
    return RoleDetailResponse.model_validate(role)


@router.patch(
    "/roles/{role_id}",
    response_model=RoleDetailResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def update_role(
    role_id: uuid.UUID,
    data: RoleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RoleDetailResponse:
    try:
        role = await staff_service.update_role(
            db, current_user.tenant_id, role_id, data
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    await db.commit()
    return RoleDetailResponse.model_validate(role)


@router.get(
    "/permissions",
    response_model=list[PermissionResponse],
    dependencies=[Depends(require_role("admin"))],
)
async def list_permissions(
    db: AsyncSession = Depends(get_db),
) -> list[PermissionResponse]:
    perms = await staff_service.list_permissions(db)
    return [PermissionResponse.model_validate(p) for p in perms]


@router.get("/waiters")
async def list_waiters(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List active staff eligible for waiter assignment (excludes kitchen-only)."""
    users = await staff_service.list_eligible_waiters(db, current_user.tenant_id)
    return [{"id": str(u.id), "name": u.full_name, "role": u.role.name} for u in users]


@router.get(
    "/{user_id}",
    response_model=StaffResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def get_staff_member(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StaffResponse:
    user = await staff_service.get_staff_member(db, current_user.tenant_id, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff member not found")
    return StaffResponse.model_validate(user)


@router.post(
    "",
    response_model=StaffResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin"))],
)
async def create_staff(
    data: StaffCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StaffResponse:
    try:
        user = await staff_service.create_staff(db, current_user.tenant_id, data)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    await audit_service.log_action(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        entity_type="user",
        entity_id=user.id,
        action="create",
        detail=f"Staff created: {data.email}",
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email or PIN already in use (concurrent create)")
    await db.refresh(user)
    return StaffResponse.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=StaffResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def update_staff(
    user_id: uuid.UUID,
    data: StaffUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StaffResponse:
    try:
        user = await staff_service.update_staff(
            db, current_user.tenant_id, user_id, data
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    await audit_service.log_action(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        entity_type="user",
        entity_id=user_id,
        action="update",
        detail=f"Staff updated: {data.model_dump(exclude_unset=True)}",
    )
    await db.commit()
    await db.refresh(user)
    return StaffResponse.model_validate(user)


@router.patch(
    "/{user_id}/reset-password",
    response_model=StaffResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def reset_password(
    user_id: uuid.UUID,
    data: PasswordReset,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StaffResponse:
    try:
        user = await staff_service.reset_password(
            db, current_user.tenant_id, user_id, data.new_password
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    await audit_service.log_action(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        entity_type="user",
        entity_id=user_id,
        action="reset_password",
        detail=f"Password reset for user {user_id}",
    )
    await db.commit()
    await db.refresh(user)
    return StaffResponse.model_validate(user)


@router.patch(
    "/{user_id}/reset-pin",
    response_model=StaffResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def reset_pin(
    user_id: uuid.UUID,
    data: PinReset,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StaffResponse:
    try:
        user = await staff_service.reset_pin(
            db, current_user.tenant_id, user_id, data.new_pin
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    await audit_service.log_action(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        entity_type="user",
        entity_id=user_id,
        action="reset_pin",
        detail=f"PIN reset for user {user_id}",
    )
    await db.commit()
    await db.refresh(user)
    return StaffResponse.model_validate(user)
