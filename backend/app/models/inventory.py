"""Inventory & BOM (Bill of Materials) models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import BaseMixin

if TYPE_CHECKING:
    from app.models.menu import MenuItem
    from app.models.tenant import Tenant
    from app.models.user import User


# ---------------------------------------------------------------------------
# INGREDIENTS
# ---------------------------------------------------------------------------


class Ingredient(BaseMixin, Base):
    """Raw material or ingredient used in recipes.

    Examples: Chicken (kg), Basmati Rice (kg), Cooking Oil (L), Onions (kg)
    """

    __tablename__ = "ingredients"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_ingredient_tenant_name"),
        Index("ix_ingredient_tenant_category", "tenant_id", "category"),
        Index("ix_ingredient_tenant_active", "tenant_id", "is_active"),
    )

    # Identity
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )

    # Core fields
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(
        String(100), nullable=False, default="General"
    )  # Protein, Grain, Spice, Oil, Dairy, Vegetable, etc.
    unit: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # kg, g, L, ml, pieces, etc.
    cost_per_unit: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )  # Cost in paisa
    supplier_name: Mapped[str | None] = mapped_column(String(200))
    supplier_contact: Mapped[str | None] = mapped_column(String(100))

    # Stock tracking
    current_stock: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=0
    )  # Current quantity on hand
    reorder_point: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=0
    )  # Alert when stock falls below this
    reorder_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=0
    )  # Default order quantity

    # Metadata
    is_active: Mapped[bool] = mapped_column(default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    # Same shape as MenuItem.image_url. Set from the admin form via an upload
    # to /media/images; read by every screen that names an ingredient (recipes,
    # stock on hand, purchase orders, supplier catalogue) so one photograph
    # follows the ingredient everywhere.
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Production
    is_produced: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # True when this ingredient is made in-house via a Recipe (its
    # produces_ingredient_id points here) rather than purchased. When true,
    # cost_per_unit is a rollup kept in sync from that recipe's
    # cost_per_serving, not entered by hand -- see
    # recipe_service.sync_produced_ingredient_cost().

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    recipe_items: Mapped[list["RecipeItem"]] = relationship(
        "RecipeItem", back_populates="ingredient"
    )
    transactions: Mapped[list["InventoryTransaction"]] = relationship(
        "InventoryTransaction", back_populates="ingredient"
    )
    production_recipe: Mapped["Recipe | None"] = relationship(
        "Recipe",
        back_populates="produces_ingredient",
        uselist=False,
        foreign_keys="Recipe.produces_ingredient_id",
    )


# ---------------------------------------------------------------------------
# RECIPES
# ---------------------------------------------------------------------------


class Recipe(BaseMixin, Base):
    """Recipe template for a menu item.

    Each recipe defines the ingredients and quantities needed to make 1 serving.
    """

    __tablename__ = "recipes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "menu_item_id", name="uq_recipe_tenant_item"),
        UniqueConstraint(
            "tenant_id",
            "produces_ingredient_id",
            name="uq_recipe_tenant_produces_ingredient",
        ),
        Index("ix_recipe_tenant_active", "tenant_id", "is_active"),
        CheckConstraint(
            "(menu_item_id IS NOT NULL) != (produces_ingredient_id IS NOT NULL)",
            name="ck_recipe_exactly_one_target",
        ),
    )

    # Identity
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    # A recipe produces exactly one of these two things (enforced by the
    # check constraint above):
    #   - menu_item_id: a sellable final product (existing behaviour)
    #   - produces_ingredient_id: an in-house-made sub-recipe/intermediate
    #     (dough, sauce, stuffing) that other recipes then consume as a
    #     RecipeItem, enabling raw -> sub-recipe -> intermediate -> final
    #     production chains. See Ingredient.is_produced.
    menu_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("menu_items.id"), nullable=True
    )
    produces_ingredient_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ingredients.id"), nullable=True
    )

    # Recipe metadata
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    yield_servings: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=1
    )  # How many servings this recipe makes
    prep_time_minutes: Mapped[int | None] = mapped_column(Integer)
    cook_time_minutes: Mapped[int | None] = mapped_column(Integer)

    # Cost tracking (calculated fields)
    total_ingredient_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )  # Sum of all recipe items cost
    cost_per_serving: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )  # total_cost / yield_servings

    # Versioning
    is_active: Mapped[bool] = mapped_column(
        default=True
    )  # Only one active recipe per menu item
    effective_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))

    # Instructions
    instructions: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    menu_item: Mapped["MenuItem | None"] = relationship(
        "MenuItem", back_populates="recipe"
    )
    produces_ingredient: Mapped["Ingredient | None"] = relationship(
        "Ingredient",
        back_populates="production_recipe",
        foreign_keys=[produces_ingredient_id],
    )
    creator: Mapped["User"] = relationship("User")
    recipe_items: Mapped[list["RecipeItem"]] = relationship(
        "RecipeItem", back_populates="recipe", cascade="all, delete-orphan"
    )


class RecipeItem(BaseMixin, Base):
    """Individual ingredient line in a recipe."""

    __tablename__ = "recipe_items"
    __table_args__ = (
        UniqueConstraint(
            "recipe_id", "ingredient_id", name="uq_recipeitem_recipe_ingredient"
        ),
        Index("ix_recipeitem_recipe", "recipe_id"),
    )

    # Links
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingredients.id"), nullable=False
    )

    # Quantity
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False
    )  # Amount of this ingredient
    unit: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # Should match ingredient.unit
    waste_factor: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=0
    )  # Waste % (5 = 5% waste)

    # Cost (denormalized for history)
    cost_per_unit_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )  # quantity * cost_per_unit * (1 + waste_factor/100)

    # Metadata
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    recipe: Mapped["Recipe"] = relationship("Recipe", back_populates="recipe_items")
    ingredient: Mapped["Ingredient"] = relationship(
        "Ingredient", back_populates="recipe_items"
    )


# ---------------------------------------------------------------------------
# INVENTORY TRANSACTIONS
# ---------------------------------------------------------------------------


class InventoryTransaction(BaseMixin, Base):
    """Log of all stock movements.

    Types: purchase, consumption (auto from orders), waste, adjustment, transfer
    """

    __tablename__ = "inventory_transactions"
    __table_args__ = (
        Index("ix_invtx_tenant_date", "tenant_id", "transaction_date"),
        Index("ix_invtx_ingredient", "ingredient_id"),
        Index("ix_invtx_type", "transaction_type"),
    )

    # Identity
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingredients.id"), nullable=False
    )
    # WHERE the movement happened. Nullable for rows written before locations
    # existed and for single-site tenants; when set, `balance_after` is that
    # location's balance, not the tenant-wide one.
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("locations.id", ondelete="SET NULL"), index=True
    )

    # Transaction details
    transaction_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # purchase | consumption | production | waste | adjustment |
    # transfer_out | transfer_in
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False
    )  # Positive = increase, Negative = decrease
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )  # Cost at time of transaction
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )  # quantity * unit_cost

    # Balance after transaction
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)

    # References
    # DateTime(timezone=True) is NOT optional: the default above is tz-aware, and
    # without it asyncpg raises "can't subtract offset-naive and offset-aware
    # datetimes" on every write. The SQLite test suite does not enforce this, so
    # it only ever surfaces against real Postgres -- same root cause as the
    # Recipe.effective_date bug fixed on 2026-08-26.
    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("orders.id")
    )  # If consumption from order
    performed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    reference_number: Mapped[str | None] = mapped_column(
        String(100)
    )  # PO number, adjustment ref, etc.

    # Metadata
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    ingredient: Mapped["Ingredient"] = relationship(
        "Ingredient", back_populates="transactions"
    )
    performer: Mapped["User"] = relationship("User")


# ---------------------------------------------------------------------------
# STOCK COUNTS
# ---------------------------------------------------------------------------


class StockCount(BaseMixin, Base):
    """Physical stock count record.

    Used for variance analysis: compare theoretical stock vs actual count.
    """

    __tablename__ = "stock_counts"
    __table_args__ = (
        Index("ix_stockcount_tenant_date", "tenant_id", "count_date"),
        Index("ix_stockcount_tenant_status", "tenant_id", "status"),
    )

    # Identity
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )

    # Count metadata
    count_date: Mapped[datetime] = mapped_column(
        Date, nullable=False, default=lambda: datetime.now(timezone.utc).date()
    )
    count_number: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # e.g., "CNT-2026-03-001"
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="draft"
    )  # draft | completed | reviewed

    # Personnel
    counted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Summary
    total_variance_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )  # Total cost impact of variances
    total_items_counted: Mapped[int] = mapped_column(Integer, default=0)
    items_with_variance: Mapped[int] = mapped_column(Integer, default=0)

    # Data
    count_data: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )  # {ingredient_id: {expected: X, actual: Y, variance: Z, cost_impact: W}}

    # Metadata
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    counter: Mapped["User"] = relationship(
        "User", foreign_keys=[counted_by], back_populates=None
    )
    reviewer: Mapped["User"] = relationship(
        "User", foreign_keys=[reviewed_by], back_populates=None
    )
