"""Authentication service -- handles login, token creation, and token rotation."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.user import RefreshToken, User
from app.schemas.auth import TokenResponse
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    hash_token,
    verify_password,
    verify_token,
)


async def authenticate_by_password(
    db: AsyncSession,
    email: str,
    password: str,
    tenant_id: uuid.UUID,
) -> User:
    """Authenticate a user by email + password within a specific tenant.

    Returns the user on success, raises ValueError on failure.
    """
    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(
            User.email == email,
            User.tenant_id == tenant_id,
            User.is_active == True,  # noqa: E712
        )
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.hashed_password):
        raise ValueError("Invalid email or password")

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()
    return user


async def authenticate_by_pin(
    db: AsyncSession,
    pin: str,
    tenant_id: uuid.UUID,
) -> User:
    """Authenticate a user by PIN within a specific tenant.

    PINs are bcrypt-hashed, so we must load all active users for the tenant
    and iterate to find a match. bcrypt.verify is run in a thread pool to
    avoid blocking the async event loop. Acceptable for POS staff counts
    (typically < 50 per restaurant).
    """
    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(
            User.tenant_id == tenant_id,
            User.is_active == True,  # noqa: E712
            User.pin_code.isnot(None),
        )
    )
    users = result.scalars().all()

    loop = asyncio.get_running_loop()
    for user in users:
        # Run bcrypt in thread pool so we don't block the event loop
        match = await loop.run_in_executor(
            None, verify_password, pin, user.pin_code
        )
        if match:
            user.last_login_at = datetime.now(timezone.utc)
            await db.flush()
            return user

    raise ValueError("Invalid PIN")


async def create_tokens(db: AsyncSession, user: User) -> TokenResponse:
    """Generate an access + refresh token pair and persist the refresh token.

    The refresh token is stored as a SHA-256 hash to limit exposure if the DB
    is compromised.  The raw JWT is returned to the client.
    """
    token_data = {
        "sub": str(user.id),
        "tenant_id": str(user.tenant_id),
        "role": user.role.name,
    }

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Store SHA-256 hash of the refresh token — never store raw JWT
    db_refresh = RefreshToken(
        token=hash_token(refresh_token),
        user_id=user.id,
        tenant_id=user.tenant_id,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        is_revoked=False,
    )
    db.add(db_refresh)
    await db.flush()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


async def refresh_tokens(db: AsyncSession, refresh_token_str: str) -> TokenResponse:
    """Validate a refresh token, revoke it, and issue a new token pair.

    Implements token rotation: each refresh token can only be used once.
    """
    # Decode the JWT to extract user info
    try:
        payload = verify_token(refresh_token_str)
    except Exception:
        raise ValueError("Invalid or expired refresh token")

    if payload.get("type") != "refresh":
        raise ValueError("Token is not a refresh token")

    # Look up the persisted refresh token by SHA-256 hash
    token_hash = hash_token(refresh_token_str)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token == token_hash,
            RefreshToken.is_revoked == False,  # noqa: E712
        )
    )
    db_token = result.scalar_one_or_none()

    if db_token is None:
        raise ValueError("Refresh token not found or already revoked")

    if db_token.expires_at < datetime.now(timezone.utc):
        raise ValueError("Refresh token has expired")

    # Revoke the old token
    db_token.is_revoked = True
    await db.flush()

    # Fetch the user to build new tokens
    user_result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == db_token.user_id)
    )
    user = user_result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise ValueError("User not found or deactivated")

    return await create_tokens(db, user)


async def revoke_refresh_token(
    db: AsyncSession, refresh_token_str: str, user_id: uuid.UUID | None = None
) -> None:
    """Mark a refresh token as revoked (used during logout).

    If user_id is provided, verify the token belongs to that user to prevent
    cross-user revocation attacks (Fix #9/#10).
    """
    token_hash = hash_token(refresh_token_str)
    conditions = [
        RefreshToken.token == token_hash,
        RefreshToken.is_revoked == False,  # noqa: E712
    ]
    if user_id is not None:
        conditions.append(RefreshToken.user_id == user_id)

    result = await db.execute(select(RefreshToken).where(*conditions))
    db_token = result.scalar_one_or_none()

    if db_token is not None:
        db_token.is_revoked = True
        await db.flush()
