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
    VerifyPasswordRequest,
    VerifyPasswordResponse,
)
from app.schemas.common import MessageResponse
from app.utils.security import verify_password
from app.services.auth_service import (
    authenticate_by_password,
    authenticate_by_pin,
    create_tokens,
    create_verify_token,
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


async def _tenant_for_login(
    db: AsyncSession,
    tenant_id: uuid.UUID | None,
    tenant_slug: str | None,
) -> uuid.UUID | None:
    """Which restaurant is this login for? `None` means "cannot tell".

    Order of preference:
      1. An explicit `tenant_id`.
      2. An explicit `tenant_slug` -- the one a human can actually type.
      3. The only active tenant, if there is exactly one.

    Returning `None` rather than guessing is the entire point. Single-tenant
    deployments (the existing POS demo, whose frontend sends no tenant at all)
    keep working through rule 3, and multi-tenant ones are forced to say which
    restaurant they mean instead of being silently assigned an arbitrary one.
    """
    if tenant_id is not None:
        return tenant_id

    if tenant_slug:
        result = await db.execute(
            select(Tenant.id).where(
                Tenant.slug == tenant_slug,
                Tenant.is_active == True,  # noqa: E712
            )
        )
        # An unknown slug returns None, which surfaces as a generic auth
        # failure. It must not 404: that would let anyone enumerate which
        # restaurants exist on this server.
        return result.scalar_one_or_none()

    result = await db.execute(
        select(Tenant.id).where(Tenant.is_active == True)  # noqa: E712
    )
    tenant_ids = list(result.scalars().all())
    return tenant_ids[0] if len(tenant_ids) == 1 else None


@router.post("/login", response_model=AuthResponse)
async def login_with_password(
    body: PasswordLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Authenticate with email + password and receive tokens."""
    # An explicit tenant (by id or slug) scopes the lookup. Unlike the PIN
    # route this one may still fall back to searching every active tenant:
    # email plus password is a strong enough key that a cross-tenant collision
    # needs the same address AND the same password, whereas a PIN collision
    # needs only four matching digits.
    explicit_tenant = None
    if body.tenant_id or body.tenant_slug:
        explicit_tenant = await _tenant_for_login(db, body.tenant_id, body.tenant_slug)
        if explicit_tenant is None:
            # Unknown slug. Same generic answer as bad credentials, so this
            # cannot be used to discover which restaurants exist.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

    if explicit_tenant is not None:
        try:
            user = await authenticate_by_password(
                db, body.email, body.password, explicit_tenant
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
                headers={"WWW-Authenticate": "Bearer"},
            )
    else:
        # No tenant specified -- search ALL active tenants for matching credentials
        result = await db.execute(
            select(Tenant.id).where(Tenant.is_active == True)  # noqa: E712
        )
        tenant_ids = list(result.scalars().all())

        if not tenant_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active tenant found. Run the seed script first.",
            )

        user = None
        for tid in tenant_ids:
            try:
                user = await authenticate_by_password(db, body.email, body.password, tid)
                break
            except ValueError:
                continue

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
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
    # ⚠️ A PIN is ONLY unique within one restaurant, so this route must never
    # search across tenants.
    #
    # It used to. It looped every active tenant and returned the first user
    # whose PIN matched, which is not a failed login but the WRONG login: the
    # demo tenant seeds PINs 1234 / 5678 / 9012, so a new shop issued 1234
    # would have been dropped inside another restaurant's data, holding a valid
    # token for it. Four digits is a space of 10,000 and real PINs cluster on
    # memorable numbers, so that was likely rather than theoretical.
    named_a_tenant = bool(body.tenant_id or body.tenant_slug)
    tenant_id = await _tenant_for_login(db, body.tenant_id, body.tenant_slug)

    if tenant_id is None:
        if named_a_tenant:
            # The caller named a restaurant and it did not resolve. Answer
            # exactly as for a bad PIN -- a distinct status here would let
            # anyone enumerate which restaurants exist on this server by
            # watching 400 turn into 401.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid PIN",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Which restaurant? This server hosts several, and a PIN is only "
                "unique within one. Send tenant_slug with the PIN."
            ),
        )

    try:
        user = await authenticate_by_pin(db, body.pin, tenant_id)
    except ValueError:
        # Deliberately generic: never reveal whether the PIN was wrong or the
        # restaurant was.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid PIN",
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


@router.post("/verify-password", response_model=VerifyPasswordResponse)
async def verify_password_endpoint(
    body: VerifyPasswordRequest,
    current_user: User = Depends(get_current_user),
) -> VerifyPasswordResponse:
    """Re-authenticate with password for sensitive actions (void, refund).

    Returns a short-lived auth_token that must be passed to the sensitive endpoint.
    """
    if not verify_password(body.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )
    token = create_verify_token(str(current_user.id))
    return VerifyPasswordResponse(auth_token=token)
