"""Pydantic schemas for BOM & Inventory."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import (
    BaseModel,
    Field,
    PlainSerializer,
    field_validator,
    model_validator,
)

# ---------------------------------------------------------------------------
# Decimal on the wire
# ---------------------------------------------------------------------------
# Pydantic v2 serialises `Decimal` to a JSON **string**, not a number. Every
# frontend call site in this domain declares these fields as `number` and does
# arithmetic on them, so the contract and the payload disagreed. It surfaced in
# UAT (F14): `/admin/ingredients` died outright on
# `current_stock.toFixed is not a function`, and the same landmine sat under
# `reorder_point`, `shortage`, every variance figure and every recipe cost.
#
# `Num` serialises as a JSON number while leaving VALIDATION untouched -- inbound
# parsing still goes through Decimal, so request precision is unchanged and no
# money is ever computed in float on the server. Only the outbound
# representation moves, and it moves to what the client already assumed.
Num = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float, when_used="json"),
]


# ---------------------------------------------------------------------------
# INGREDIENT SCHEMAS
# ---------------------------------------------------------------------------


class IngredientBase(BaseModel):
    name: str = Field(..., max_length=200)
    category: str = Field(default="General", max_length=100)
    unit: str = Field(
        ...,
        max_length=50,
        description="The STOCKING unit: what recipes spend and stock counts. g, kg, L, pieces.",
    )
    cost_per_unit: Num = Field(
        default=0,
        ge=0,
        description=(
            "Minor units per one stocking unit. Read-only whenever purchase_unit "
            "is set: the server derives it from purchase_cost_minor and the "
            "conversion, and ignores whatever is sent."
        ),
    )
    # Martin (FZ LLC, 2026-09-04, item M8): "2 units and a conversion. The unit
    # you buy, the unit you store) use in recipes". Leave purchase_unit unset
    # for an ingredient bought in the unit it is stocked in, which is the
    # behaviour every ingredient had before this.
    purchase_unit: str | None = Field(
        None,
        max_length=50,
        description="What the supplier sells, e.g. 'can'. Blank means same as unit.",
    )
    units_per_purchase_unit: Num = Field(
        default=1,
        gt=0,
        description="Stocking units in one purchase unit, e.g. 400 g per can.",
    )
    purchase_cost_minor: Num = Field(
        default=0,
        ge=0,
        description="Minor units per purchase unit, e.g. 850 = 8.50 AED per can.",
    )
    supplier_name: str | None = Field(None, max_length=200)
    supplier_contact: str | None = Field(None, max_length=100)
    reorder_point: Num = Field(default=0, ge=0)
    reorder_quantity: Num = Field(default=0, ge=0)
    is_active: bool = True
    notes: str | None = None
    image_url: str | None = Field(None, max_length=500)


class IngredientCreate(IngredientBase):
    # Martin (FZ LLC, 2026-09-02): "there is no difference between bought items
    # ... and ingredients manufactured by us, where the price needs to be
    # calculated by the system". A made-in-house ingredient can now be declared
    # as such at creation, before its recipe exists. While it is produced, its
    # cost is owned by the recipe engine, so any cost sent here is ignored.
    is_produced: bool = False


class IngredientUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    category: str | None = Field(None, max_length=100)
    unit: str | None = Field(None, max_length=50)
    cost_per_unit: Num | None = Field(None, ge=0)
    purchase_unit: str | None = Field(None, max_length=50)
    units_per_purchase_unit: Num | None = Field(None, gt=0)
    purchase_cost_minor: Num | None = Field(None, ge=0)
    supplier_name: str | None = Field(None, max_length=200)
    supplier_contact: str | None = Field(None, max_length=100)
    reorder_point: Num | None = Field(None, ge=0)
    reorder_quantity: Num | None = Field(None, ge=0)
    is_active: bool | None = None
    is_produced: bool | None = None
    notes: str | None = None
    image_url: str | None = Field(None, max_length=500)


class IngredientResponse(IngredientBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    current_stock: Num
    is_produced: bool
    # The active recipe that makes this ingredient, when there is one. A
    # produced ingredient with no recipe yet is the "No recipe" state the
    # Ingredients screen signposts.
    production_recipe_id: uuid.UUID | None = None
    production_recipe_name: str | None = None
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# RECIPE ITEM SCHEMAS (sub-schema for recipes)
# ---------------------------------------------------------------------------


class RecipeItemBase(BaseModel):
    ingredient_id: uuid.UUID
    quantity: Num = Field(..., gt=0, description="Amount of ingredient")
    unit: str = Field(..., max_length=50)
    waste_factor: Num = Field(
        default=0, ge=0, le=100, description="Waste percentage (0-100)"
    )
    notes: str | None = None


class RecipeItemCreate(RecipeItemBase):
    pass


class RecipeItemUpdate(BaseModel):
    quantity: Num | None = Field(None, gt=0)
    unit: str | None = Field(None, max_length=50)
    waste_factor: Num | None = Field(None, ge=0, le=100)
    notes: str | None = None


class RecipeItemResponse(RecipeItemBase):
    id: uuid.UUID
    recipe_id: uuid.UUID
    cost_per_unit_snapshot: Num
    total_cost: Num
    ingredient_name: str | None = None  # Joined from ingredient

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# RECIPE SCHEMAS
# ---------------------------------------------------------------------------


class RecipeBase(BaseModel):
    """A recipe is attached to exactly one target, never two, never none:

      * `menu_item_id` -- a sellable final product,
      * `produces_ingredient_id` -- an in-house sub-recipe/intermediate like
        dough, sauce, or stuffing that other recipes then consume as an
        ingredient,
      * `modifier_id` -- a paid add-on chosen at the till (extra cheese, an
        extra shot), consumed and costed on top of the line it is added to.
    """

    menu_item_id: uuid.UUID | None = None
    produces_ingredient_id: uuid.UUID | None = None
    modifier_id: uuid.UUID | None = None
    yield_servings: Num = Field(
        default=1,
        gt=0,
        description="Number of servings (menu item) or yield quantity in "
        "the produced ingredient's own unit (sub-recipe), e.g. 5 for a "
        "batch that yields 5 kg of dough.",
    )
    prep_time_minutes: int | None = Field(None, ge=0)
    cook_time_minutes: int | None = Field(None, ge=0)
    instructions: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _exactly_one_target(self) -> "RecipeBase":
        targets = (
            self.menu_item_id,
            self.produces_ingredient_id,
            self.modifier_id,
        )
        if sum(1 for target in targets if target is not None) != 1:
            raise ValueError(
                "Exactly one of menu_item_id, produces_ingredient_id or "
                "modifier_id must be set."
            )
        return self


class RecipeCreate(RecipeBase):
    recipe_items: list[RecipeItemCreate] = Field(default_factory=list)


class RecipeUpdate(BaseModel):
    yield_servings: Num | None = Field(None, gt=0)
    prep_time_minutes: int | None = Field(None, ge=0)
    cook_time_minutes: int | None = Field(None, ge=0)
    instructions: str | None = None
    notes: str | None = None
    recipe_items: list[RecipeItemCreate] | None = None  # Full replacement


class RecipeResponse(RecipeBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    version: int
    total_ingredient_cost: Num
    cost_per_serving: Num
    is_active: bool
    effective_date: datetime
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime | None
    recipe_items: list[RecipeItemResponse] = []

    # Calculated fields
    menu_item_name: str | None = None
    menu_item_price: int | None = None  # minor units, as on the menu board
    # The menu price with the tenant's tax backed out when prices are
    # tax-inclusive; equal to `menu_item_price` otherwise. This is the divisor
    # of `food_cost_percentage`, stated so the basis is never ambiguous.
    menu_item_net_price: int | None = None
    # Set instead of menu_item_name when this is a sub-recipe. Without it the
    # UI has an id and no way to label a dough or sauce recipe.
    produces_ingredient_name: str | None = None
    # Set instead of both when the recipe belongs to an add-on. The price is
    # the modifier's own `price_adjustment`, which is what the customer pays
    # for it on top of the line, so the same food-cost arithmetic applies.
    modifier_name: str | None = None
    modifier_group_name: str | None = None
    modifier_price: int | None = None
    food_cost_percentage: Num | None = None  # cost_per_serving / net price

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# INVENTORY TRANSACTION SCHEMAS
# ---------------------------------------------------------------------------


class InventoryTransactionBase(BaseModel):
    ingredient_id: uuid.UUID
    transaction_type: str = Field(
        ..., description="purchase | consumption | waste | adjustment | transfer"
    )
    quantity: Num = Field(..., description="Positive = increase, Negative = decrease")
    unit: str = Field(..., max_length=50)
    unit_cost: Num = Field(default=0, ge=0)
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
    total_cost: Num
    balance_after: Num
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

    expected: Num
    actual: Num
    variance: Num
    variance_percentage: Num
    cost_impact: Num  # paisa


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
    total_variance_cost: Num
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
    ingredient_price_changes: dict[str, Num] = Field(
        ..., description="Map of ingredient_id -> new cost_per_unit"
    )


class RecipeCostSimulationResult(BaseModel):
    original_total_cost: Num
    new_total_cost: Num
    cost_difference: Num
    percentage_change: Num
    original_cost_per_serving: Num
    new_cost_per_serving: Num
    affected_ingredients: list[dict]


class StockAlertResponse(BaseModel):
    """Ingredient below reorder point."""

    ingredient_id: uuid.UUID
    ingredient_name: str
    current_stock: Num
    reorder_point: Num
    reorder_quantity: Num
    shortage: Num
    unit: str
    supplier_name: str | None
    supplier_contact: str | None
