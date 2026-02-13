"""Authentication endpoints -- login, logout, token refresh, profile."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    LogoutRequest,
    PasswordLoginRequest,
    PinLoginRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.common import MessageResponse
from app.services.auth_service import (
    authenticate_by_password,
    authenticate_by_pin,
    create_tokens,
    refresh_tokens,
    revoke_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _resolve_tenant_id(
    db: AsyncSession, tenant_id: uuid.UUID | None
) -> uuid.UUID:
    """Return the given tenant_id, or auto-detect the single active tenant."""
    if tenant_id is not None:
        return tenant_id
    result = await db.execute(
        select(Tenant.id).where(Tenant.is_active == True).limit(1)  # noqa: E712
    )
    tid = result.scalar_one_or_none()
    if tid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active tenant found. Run the seed script first.",
        )
    return tid


@router.post("/login", response_model=AuthResponse)
async def login_with_password(
    body: PasswordLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Authenticate with email + password and receive tokens."""
    tenant_id = await _resolve_tenant_id(db, body.tenant_id)
    try:
        user = await authenticate_by_password(
            db, body.email, body.password, tenant_id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    tokens = await create_tokens(db, user)
    return AuthResponse(
        user=UserResponse.model_validate(user),
        tokens=tokens,
    )


@router.post("/login/pin", response_model=AuthResponse)
async def login_with_pin(
    body: PinLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Authenticate with a numeric PIN (fast POS login)."""
    tenant_id = await _resolve_tenant_id(db, body.tenant_id)
    try:
        user = await authenticate_by_pin(db, body.pin, tenant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    tokens = await create_tokens(db, user)
    return AuthResponse(
        user=UserResponse.model_validate(user),
        tokens=tokens,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a valid refresh token for a new access + refresh token pair."""
    try:
        return await refresh_tokens(db, body.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    body: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """Revoke the provided refresh token (logout).

    Passes current_user.id to prevent cross-user revocation attacks.
    """
    await revoke_refresh_token(db, body.refresh_token, user_id=current_user.id)
    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the profile of the currently authenticated user."""
    return UserResponse.model_validate(current_user)
