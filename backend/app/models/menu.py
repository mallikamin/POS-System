"""Menu domain models: categories, items, modifier groups, modifiers.

All prices are stored in paisa (1 PKR = 100 paisa) as integers.
"""

import uuid

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import BaseMixin


class Category(BaseMixin, Base):
    """Menu category (e.g. BBQ, Karahi, Biryani, Drinks)."""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_category_tenant_name"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    icon: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Lucide icon name or emoji"
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )

    # Relationships
    items: Mapped[list["MenuItem"]] = relationship(
        "MenuItem", back_populates="category", lazy="selectin"
    )


class MenuItem(BaseMixin, Base):
    """Individual menu item (e.g. Chicken Biryani, Butter Naan).

    price is stored in paisa (integer).
    """

    __tablename__ = "menu_items"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "category_id", "name", name="uq_item_tenant_cat_name"
        ),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Price in paisa (100 = 1 PKR)"
    )
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    preparation_time_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Estimated prep time in minutes"
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    category: Mapped[Category] = relationship("Category", back_populates="items")
    modifier_groups: Mapped[list["ModifierGroup"]] = relationship(
        "ModifierGroup",
        secondary="menu_item_modifier_groups",
        back_populates="menu_items",
        lazy="selectin",
    )
    recipe: Mapped["Recipe"] = relationship(
        "Recipe", back_populates="menu_item", uselist=False
    )


class ModifierGroup(BaseMixin, Base):
    """Group of modifiers (e.g. Spice Level, Size, Extra Toppings).

    min_selections / max_selections define how many choices the customer must make.
    required = True means at least min_selections must be chosen.
    """

    __tablename__ = "modifier_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_modgroup_tenant_name"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_selections: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_selections: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, comment="0 = unlimited"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )

    # Relationships
    modifiers: Mapped[list["Modifier"]] = relationship(
        "Modifier",
        back_populates="group",
        lazy="selectin",
        order_by="Modifier.display_order",
    )
    menu_items: Mapped[list[MenuItem]] = relationship(
        "MenuItem",
        secondary="menu_item_modifier_groups",
        back_populates="modifier_groups",
        lazy="raise",  # Use explicit selectinload() in queries; prevents circular eager load
    )


class Modifier(BaseMixin, Base):
    """Individual modifier option (e.g. Mild, Medium, Hot; Regular, Large).

    price_adjustment is in paisa — added to the item price.
    """

    __tablename__ = "modifiers"
    __table_args__ = (
        UniqueConstraint("group_id", "name", name="uq_modifier_group_name"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_adjustment: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Price adjustment in paisa (can be 0, positive, or negative)",
    )
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("modifier_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    group: Mapped[ModifierGroup] = relationship(
        "ModifierGroup", back_populates="modifiers"
    )


class MenuItemModifierGroup(BaseMixin, Base):
    """Association table linking menu items to modifier groups (M2M)."""

    __tablename__ = "menu_item_modifier_groups"
    __table_args__ = (
        UniqueConstraint("menu_item_id", "modifier_group_id", name="uq_item_modgroup"),
    )

    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False
    )
    modifier_group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("modifier_groups.id", ondelete="CASCADE"), nullable=False
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
