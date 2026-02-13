"""Pydantic schemas for the menu domain.

All prices are in paisa (integer). Frontend converts to PKR for display.
"""

import uuid

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Modifier
# ---------------------------------------------------------------------------

class ModifierCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    price_adjustment: int = Field(default=0, description="Price adjustment in paisa")
    display_order: int = Field(default=0)
    is_available: bool = Field(default=True)


class ModifierUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    price_adjustment: int | None = None
    display_order: int | None = None
    is_available: bool | None = None


class ModifierResponse(BaseModel):
    id: uuid.UUID
    name: str
    price_adjustment: int
    display_order: int
    is_available: bool
    group_id: uuid.UUID

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Modifier Group
# ---------------------------------------------------------------------------

class ModifierGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    display_order: int = Field(default=0)
    required: bool = Field(default=False)
    min_selections: int = Field(default=0, ge=0)
    max_selections: int = Field(default=1, ge=0, description="0 = unlimited")
    is_active: bool = Field(default=True)
    modifiers: list[ModifierCreate] = Field(
        default_factory=list,
        description="Optionally create modifiers inline with the group"
    )


class ModifierGroupUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    display_order: int | None = None
    required: bool | None = None
    min_selections: int | None = Field(None, ge=0)
    max_selections: int | None = Field(None, ge=0)
    is_active: bool | None = None


class ModifierGroupResponse(BaseModel):
    id: uuid.UUID
    name: str
    display_order: int
    required: bool
    min_selections: int
    max_selections: int
    is_active: bool
    modifiers: list[ModifierResponse] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    display_order: int = Field(default=0)
    is_active: bool = Field(default=True)
    icon: str | None = Field(None, max_length=50)


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    display_order: int | None = None
    is_active: bool | None = None
    icon: str | None = None


class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    display_order: int
    is_active: bool
    icon: str | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Menu Item
# ---------------------------------------------------------------------------

class MenuItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    price: int = Field(..., ge=0, description="Price in paisa")
    category_id: uuid.UUID
    image_url: str | None = Field(None, max_length=500)
    is_available: bool = Field(default=True)
    display_order: int = Field(default=0)
    preparation_time_minutes: int | None = Field(None, ge=0)
    modifier_group_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="Modifier groups to attach to this item"
    )


class MenuItemUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    price: int | None = Field(None, ge=0)
    category_id: uuid.UUID | None = None
    image_url: str | None = None
    is_available: bool | None = None
    display_order: int | None = None
    preparation_time_minutes: int | None = None
    modifier_group_ids: list[uuid.UUID] | None = Field(
        None, description="Replace all modifier group links"
    )


class MenuItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    price: int
    category_id: uuid.UUID
    image_url: str | None = None
    is_available: bool
    display_order: int
    preparation_time_minutes: int | None = None
    modifier_groups: list[ModifierGroupResponse] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Full Menu Tree (for POS frontend)
# ---------------------------------------------------------------------------

class CategoryWithItems(BaseModel):
    """Category including its menu items (each with modifier groups)."""

    id: uuid.UUID
    name: str
    description: str | None = None
    display_order: int
    is_active: bool
    icon: str | None = None
    items: list[MenuItemResponse] = []

    model_config = {"from_attributes": True}


class FullMenuResponse(BaseModel):
    """Complete menu tree returned by GET /menu/full."""

    categories: list[CategoryWithItems]
