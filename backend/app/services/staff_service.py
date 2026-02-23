"""Staff management service -- CRUD operations for user accounts."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import Role, User
from app.schemas.staff import StaffCreate, StaffUpdate
from app.utils.security import hash_password


async def list_staff(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[User], int]:
    """List staff members with optional search. Returns (users, total_count)."""
    base = select(User).where(User.tenant_id == tenant_id)

    if search:
        pattern = f"%{search}%"
        base = base.where(
            or_(
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
            )
        )

    # Count
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Paginated results
    q = (
        base.options(selectinload(User.role))
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    users = list(result.scalars().all())

    return users, total


async def get_staff_member(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> User | None:
    """Get a single staff member by ID."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == user_id, User.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def create_staff(
    db: AsyncSession, tenant_id: uuid.UUID, data: StaffCreate
) -> User:
    """Create a new staff member."""
    # Check email uniqueness within tenant
    existing = await db.execute(
        select(User).where(User.tenant_id == tenant_id, User.email == data.email)
    )
    if existing.scalar_one_or_none():
        raise ValueError(f"Email '{data.email}' is already in use")

    # Verify role exists in tenant
    role = await db.execute(
        select(Role).where(Role.id == data.role_id, Role.tenant_id == tenant_id)
    )
    if not role.scalar_one_or_none():
        raise ValueError("Role not found")

    hashed_pw = hash_password(data.password)
    hashed_pin = hash_password(data.pin_code) if data.pin_code else None

    user = User(
        tenant_id=tenant_id,
        email=data.email,
        full_name=data.full_name,
        hashed_password=hashed_pw,
        pin_code=hashed_pin,
        role_id=data.role_id,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Re-fetch with role loaded
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user.id)
    )
    return result.scalar_one()


async def update_staff(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    data: StaffUpdate,
) -> User:
    """Update a staff member's profile."""
    user = await get_staff_member(db, tenant_id, user_id)
    if not user:
        raise ValueError("Staff member not found")

    if data.email is not None and data.email != user.email:
        existing = await db.execute(
            select(User).where(
                User.tenant_id == tenant_id,
                User.email == data.email,
                User.id != user_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Email '{data.email}' is already in use")
        user.email = data.email

    if data.full_name is not None:
        user.full_name = data.full_name

    if data.role_id is not None:
        role = await db.execute(
            select(Role).where(Role.id == data.role_id, Role.tenant_id == tenant_id)
        )
        if not role.scalar_one_or_none():
            raise ValueError("Role not found")
        user.role_id = data.role_id

    if data.is_active is not None:
        user.is_active = data.is_active

    await db.flush()

    # Re-fetch
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user.id)
    )
    return result.scalar_one()


async def reset_password(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    new_password: str,
) -> User:
    """Reset a staff member's password."""
    user = await get_staff_member(db, tenant_id, user_id)
    if not user:
        raise ValueError("Staff member not found")

    user.hashed_password = hash_password(new_password)
    await db.flush()
    return user


async def reset_pin(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    new_pin: str,
) -> User:
    """Reset a staff member's PIN code."""
    user = await get_staff_member(db, tenant_id, user_id)
    if not user:
        raise ValueError("Staff member not found")

    user.pin_code = hash_password(new_pin)
    await db.flush()
    return user


async def list_roles(db: AsyncSession, tenant_id: uuid.UUID) -> list[Role]:
    """List available roles for the tenant."""
    result = await db.execute(
        select(Role)
        .where(Role.tenant_id == tenant_id, Role.is_active == True)  # noqa: E712
        .order_by(Role.name)
    )
    return list(result.scalars().all())
