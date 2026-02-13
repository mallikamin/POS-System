import uuid

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class PinLoginRequest(BaseModel):
    """Login using a numeric PIN (fast POS login for staff)."""

    pin: str = Field(..., min_length=4, max_length=6, pattern=r"^\d{4,6}$")
    tenant_id: uuid.UUID | None = Field(None, description="Tenant to authenticate against (auto-detected if omitted)")


class PasswordLoginRequest(BaseModel):
    """Login using email + password (back-office / admin login)."""

    email: EmailStr
    password: str = Field(..., min_length=1)
    tenant_id: uuid.UUID | None = Field(None, description="Tenant to authenticate against (auto-detected if omitted)")


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
