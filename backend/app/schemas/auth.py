import uuid

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class PinLoginRequest(BaseModel):
    """Login using a numeric PIN (fast POS login for staff).

    ⚠️ **A PIN is only unique inside one restaurant.** Four digits is a space of
    10,000 and real POS PINs cluster hard on memorable numbers, so across a
    handful of tenants a collision is likely rather than theoretical. Identify
    the restaurant with `tenant_slug` (or `tenant_id`). It may only be omitted
    when the deployment has exactly one active tenant.
    """

    pin: str = Field(..., min_length=4, max_length=6, pattern=r"^\d{4,6}$")
    tenant_id: uuid.UUID | None = Field(
        None, description="Tenant to authenticate against, by id"
    )
    tenant_slug: str | None = Field(
        None,
        max_length=255,
        description="Tenant to authenticate against, by slug -- e.g. 'chick-shack'. "
        "Preferred over tenant_id: a person can type it and read it back.",
    )


class PasswordLoginRequest(BaseModel):
    """Login using email + password (back-office / admin login)."""

    email: EmailStr
    password: str = Field(..., min_length=1)
    tenant_id: uuid.UUID | None = Field(
        None, description="Tenant to authenticate against, by id"
    )
    tenant_slug: str | None = Field(
        None,
        max_length=255,
        description="Tenant to authenticate against, by slug. Optional: email "
        "plus password is already a strong enough key to search on.",
    )


class VerifyPasswordRequest(BaseModel):
    """Re-authenticate with password for sensitive actions (void, refund)."""

    password: str = Field(..., min_length=1)


class VerifyPasswordResponse(BaseModel):
    """Short-lived token confirming re-authentication."""

    auth_token: str
    expires_in: int = 300  # seconds


class RefreshRequest(BaseModel):
    """Exchange a refresh token for a new token pair."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Revoke a refresh token on logout."""

    refresh_token: str


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class PermissionResponse(BaseModel):
    """Single permission returned inside a role."""

    code: str
    description: str | None = None

    model_config = {"from_attributes": True}


class RoleResponse(BaseModel):
    """Role with its associated permissions."""

    id: uuid.UUID
    name: str
    permissions: list[PermissionResponse] = []

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    """Public representation of a user (no secrets)."""

    id: uuid.UUID
    email: str
    full_name: str
    role: RoleResponse
    is_active: bool
    tenant_id: uuid.UUID

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """JWT token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    """Combined user profile + tokens returned after login."""

    user: UserResponse
    tokens: TokenResponse
