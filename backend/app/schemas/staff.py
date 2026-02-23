"""Staff management request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class StaffCreate(BaseModel):
    """Create a new staff member."""

    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=6, max_length=128)
    pin_code: str | None = Field(None, min_length=4, max_length=6, pattern=r"^\d{4,6}$")
    role_id: uuid.UUID


class StaffUpdate(BaseModel):
    """Update an existing staff member (all fields optional)."""

    full_name: str | None = Field(None, min_length=1, max_length=200)
    email: EmailStr | None = None
    role_id: uuid.UUID | None = None
    is_active: bool | None = None


class PasswordReset(BaseModel):
    """Admin-initiated password reset."""

    new_password: str = Field(..., min_length=6, max_length=128)


class PinReset(BaseModel):
    """Admin-initiated PIN reset."""

    new_pin: str = Field(..., min_length=4, max_length=6, pattern=r"^\d{4,6}$")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class StaffRoleResponse(BaseModel):
    """Minimal role info embedded in staff response."""

    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class StaffResponse(BaseModel):
    """Public representation of a staff member."""

    id: uuid.UUID
    email: str
    full_name: str
    role: StaffRoleResponse
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
