"""Pydantic schemas for BOM & Inventory."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# INGREDIENT SCHEMAS
# ---------------------------------------------------------------------------


class IngredientBase(BaseModel):
    name: str = Field(..., max_length=200)
    category: str = Field(default="General", max_length=100)
    unit: str = Field(..., max_length=50, description="kg, L, pieces, etc.")
    cost_per_unit: Decimal = Field(default=0, ge=0, description="Cost in paisa")
    supplier_name: str | None = Field(None, max_length=200)
    supplier_contact: str | None = Field(None, max_length=100)
    reorder_point: Decimal = Field(default=0, ge=0)
    reorder_quantity: Decimal = Field(default=0, ge=0)
    is_active: bool = True
    notes: str | None = None


class IngredientCreate(IngredientBase):
    pass


class IngredientUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    category: str | None = Field(None, max_length=100)
    unit: str | None = Field(None, max_length=50)
    cost_per_unit: Decimal | None = Field(None, ge=0)
    supplier_name: str | None = Field(None, max_length=200)
    supplier_contact: str | None = Field(None, max_length=100)
    reorder_point: Decimal | None = Field(None, ge=0)
    reorder_quantity: Decimal | None = Field(None, ge=0)
    is_active: bool | None = None
    notes: str | None = None


class IngredientResponse(IngredientBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    current_stock: Decimal
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# RECIPE ITEM SCHEMAS (sub-schema for recipes)
# ---------------------------------------------------------------------------


class RecipeItemBase(BaseModel):
    ingredient_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0, description="Amount of ingredient")
    unit: str = Field(..., max_length=50)
    waste_factor: Decimal = Field(
        default=0, ge=0, le=100, description="Waste percentage (0-100)"
    )
    notes: str | None = None


class RecipeItemCreate(RecipeItemBase):
    pass


class RecipeItemUpdate(BaseModel):
    quantity: Decimal | None = Field(None, gt=0)
    unit: str | None = Field(None, max_length=50)
    waste_factor: Decimal | None = Field(None, ge=0, le=100)
    notes: str | None = None


class RecipeItemResponse(RecipeItemBase):
    id: uuid.UUID
    recipe_id: uuid.UUID
    cost_per_unit_snapshot: Decimal
    total_cost: Decimal
    ingredient_name: str | None = None  # Joined from ingredient

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# RECIPE SCHEMAS
# ---------------------------------------------------------------------------


class RecipeBase(BaseModel):
    menu_item_id: uuid.UUID
    yield_servings: Decimal = Field(default=1, gt=0, description="Number of servings")
    prep_time_minutes: int | None = Field(None, ge=0)
    cook_time_minutes: int | None = Field(None, ge=0)
    instructions: str | None = None
    notes: str | None = None


class RecipeCreate(RecipeBase):
    recipe_items: list[RecipeItemCreate] = Field(default_factory=list)


class RecipeUpdate(BaseModel):
    yield_servings: Decimal | None = Field(None, gt=0)
    prep_time_minutes: int | None = Field(None, ge=0)
    cook_time_minutes: int | None = Field(None, ge=0)
    instructions: str | None = None
    notes: str | None = None
    recipe_items: list[RecipeItemCreate] | None = None  # Full replacement


class RecipeResponse(RecipeBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    version: int
    total_ingredient_cost: Decimal
    cost_per_serving: Decimal
    is_active: bool
    effective_date: datetime
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime | None
    recipe_items: list[RecipeItemResponse] = []

    # Calculated fields
    menu_item_name: str | None = None
    menu_item_price: int | None = None  # paisa
    food_cost_percentage: Decimal | None = None  # calculated

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# INVENTORY TRANSACTION SCHEMAS
# ---------------------------------------------------------------------------


class InventoryTransactionBase(BaseModel):
    ingredient_id: uuid.UUID
    transaction_type: str = Field(
        ..., description="purchase | consumption | waste | adjustment | transfer"
    )
    quantity: Decimal = Field(..., description="Positive = increase, Negative = decrease")
    unit: str = Field(..., max_length=50)
    unit_cost: Decimal = Field(default=0, ge=0)
    reference_number: str | None = Field(None, max_length=100)
    notes: str | None = None

    @field_validator("transaction_type")
    @classmethod
    def validate_transaction_type(cls, v: str) -> str:
        allowed = {"purchase", "consumption", "waste", "adjustment", "transfer"}
        if v not in allowed:
            raise ValueError(f"transaction_type must be one of {allowed}")
        return v


class InventoryTransactionCreate(InventoryTransactionBase):
    pass


class InventoryTransactionResponse(InventoryTransactionBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    total_cost: Decimal
    balance_after: Decimal
    transaction_date: datetime
    order_id: uuid.UUID | None
    performed_by: uuid.UUID | None
    created_at: datetime
    ingredient_name: str | None = None  # Joined

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# STOCK COUNT SCHEMAS
# ---------------------------------------------------------------------------


class StockCountItemData(BaseModel):
    """Individual ingredient count data within a stock count."""

    expected: Decimal
    actual: Decimal
    variance: Decimal
    variance_percentage: Decimal
    cost_impact: Decimal  # paisa


class StockCountBase(BaseModel):
    count_date: date
    notes: str | None = None


class StockCountCreate(StockCountBase):
    count_data: dict[str, StockCountItemData] = Field(
        ..., description="Map of ingredient_id -> count data"
    )


class StockCountUpdate(BaseModel):
    status: str | None = Field(None, description="draft | completed | reviewed")
    reviewed_by: uuid.UUID | None = None
    notes: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None:
            allowed = {"draft", "completed", "reviewed"}
            if v not in allowed:
                raise ValueError(f"status must be one of {allowed}")
        return v


class StockCountResponse(StockCountBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    count_number: str
    status: str
    counted_by: uuid.UUID | None
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    total_variance_cost: Decimal
    total_items_counted: int
    items_with_variance: int
    count_data: dict
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# UTILITY SCHEMAS
# ---------------------------------------------------------------------------


class RecipeCostSimulation(BaseModel):
    """Simulate recipe cost with ingredient price changes."""

    recipe_id: uuid.UUID
    ingredient_price_changes: dict[str, Decimal] = Field(
        ..., description="Map of ingredient_id -> new cost_per_unit"
    )


class RecipeCostSimulationResult(BaseModel):
    original_total_cost: Decimal
    new_total_cost: Decimal
    cost_difference: Decimal
    percentage_change: Decimal
    original_cost_per_serving: Decimal
    new_cost_per_serving: Decimal
    affected_ingredients: list[dict]


class StockAlertResponse(BaseModel):
    """Ingredient below reorder point."""

    ingredient_id: uuid.UUID
    ingredient_name: str
    current_stock: Decimal
    reorder_point: Decimal
    reorder_quantity: Decimal
    shortage: Decimal
    unit: str
    supplier_name: str | None
    supplier_contact: str | None
