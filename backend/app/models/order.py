"""Order domain models: orders, items, item modifiers, status log.

All monetary amounts are stored in paisa (1 PKR = 100 paisa) as integers.
"""

import uuid

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import BaseMixin


class Order(BaseMixin, Base):
    """A customer order.

    order_type: dine_in | takeaway | call_center
    status: draft | confirmed | in_kitchen | ready | served | completed | voided
    payment_status: unpaid | partial | paid | refunded
    """

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "order_number", name="uq_order_tenant_number"),
        Index("ix_orders_tenant_status", "tenant_id", "status"),
        Index("ix_orders_tenant_created", "tenant_id", "created_at"),
        Index("ix_orders_created_by", "created_by"),
        Index("ix_orders_customer_phone", "customer_phone"),
    )

    order_number: Mapped[str] = mapped_column(String(20), nullable=False)
    order_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="dine_in | takeaway | call_center",
    )
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False,
        comment="draft | confirmed | in_kitchen | ready | served | completed | voided",
    )
    payment_status: Mapped[str] = mapped_column(
        String(20), default="unpaid", nullable=False,
        comment="unpaid | partial | paid | refunded",
    )

    table_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tables.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    subtotal: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Subtotal in paisa",
    )
    tax_amount: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Tax in paisa",
    )
    discount_amount: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="Discount in paisa",
    )
    total: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Grand total in paisa",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True,
    )

    # Relationships
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", lazy="selectin",
        cascade="all, delete-orphan",
    )
    status_logs: Mapped[list["OrderStatusLog"]] = relationship(
        "OrderStatusLog", back_populates="order", lazy="raise",
        cascade="all, delete-orphan",
        order_by="OrderStatusLog.created_at",
    )
    table: Mapped["Table | None"] = relationship("Table", lazy="selectin")
    creator: Mapped["User"] = relationship("User", lazy="selectin")


class OrderItem(BaseMixin, Base):
    """A line item within an order.

    name and unit_price are denormalized from menu_item for historical accuracy.
    status: pending | sent | preparing | ready | served
    """

    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("menu_items.id"), nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Unit price in paisa (base + modifiers)",
    )
    total: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="unit_price * quantity in paisa",
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False,
        comment="pending | sent | preparing | ready | served",
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True,
    )

    # Relationships
    order: Mapped[Order] = relationship("Order", back_populates="items")
    menu_item: Mapped["MenuItem | None"] = relationship("MenuItem", lazy="raise")
    modifiers: Mapped[list["OrderItemModifier"]] = relationship(
        "OrderItemModifier", back_populates="order_item", lazy="selectin",
        cascade="all, delete-orphan",
    )


class OrderItemModifier(BaseMixin, Base):
    """A modifier applied to an order item.

    name and price_adjustment are denormalized for historical accuracy.
    """

    __tablename__ = "order_item_modifiers"

    order_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    modifier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("modifiers.id"), nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_adjustment: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="Price adjustment in paisa",
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True,
    )

    # Relationships
    order_item: Mapped[OrderItem] = relationship("OrderItem", back_populates="modifiers")


class OrderStatusLog(BaseMixin, Base):
    """Audit trail for order status transitions."""

    __tablename__ = "order_status_log"

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    from_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="Null for initial creation",
    )
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False,
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True,
    )

    # Relationships
    order: Mapped[Order] = relationship("Order", back_populates="status_logs")


# Avoid circular import issues — use string references above
from app.models.floor import Table  # noqa: E402, F401
from app.models.menu import MenuItem  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
