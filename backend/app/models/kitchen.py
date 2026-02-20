"""Kitchen domain models: stations, tickets, and ticket items.

Stations define physical or logical kitchen areas (e.g. Grill, Fryer, Drinks).
Tickets are per-station per-order work units routed when an order hits the kitchen.
Ticket items link individual order items to a ticket.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import BaseMixin


class KitchenStation(BaseMixin, Base):
    """A kitchen station (e.g. Grill, Fryer, Beverage, Dessert).

    Stations can be linked to categories or individual menu items
    for automatic ticket routing (future enhancement). For now,
    all order items go to a single default station or are
    manually assigned.
    """

    __tablename__ = "kitchen_stations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_station_tenant_name"),
        Index("ix_kitchen_stations_tenant_active", "tenant_id", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    tickets: Mapped[list["KitchenTicket"]] = relationship(
        "KitchenTicket", back_populates="station", lazy="raise",
    )


class KitchenTicket(BaseMixin, Base):
    """A kitchen ticket — one per station per order.

    status: new -> preparing -> ready -> served
    When all tickets for an order are served, the order can transition to 'served'.
    """

    __tablename__ = "kitchen_tickets"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "order_id", "station_id",
            name="uq_ticket_tenant_order_station",
        ),
        Index("ix_kitchen_tickets_tenant_status", "tenant_id", "status"),
        Index("ix_kitchen_tickets_station_status", "station_id", "status"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    station_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("kitchen_stations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), default="new", nullable=False,
        comment="new | preparing | ready | served",
    )
    priority: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Higher = more urgent. 0 = normal.",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When prep started (status -> preparing)",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When item(s) ready (status -> ready)",
    )
    served_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When picked up / served (status -> served)",
    )

    # Relationships
    station: Mapped[KitchenStation] = relationship(
        "KitchenStation", back_populates="tickets", lazy="selectin",
    )
    order: Mapped["Order"] = relationship("Order", lazy="selectin")
    items: Mapped[list["KitchenTicketItem"]] = relationship(
        "KitchenTicketItem", back_populates="ticket", lazy="selectin",
        cascade="all, delete-orphan",
    )


class KitchenTicketItem(BaseMixin, Base):
    """Links an order item to a kitchen ticket.

    Allows tracking which specific items are on which ticket,
    supporting split routing across stations.
    """

    __tablename__ = "kitchen_ticket_items"
    __table_args__ = (
        UniqueConstraint(
            "ticket_id", "order_item_id",
            name="uq_ticket_item_ticket_order_item",
        ),
    )

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("kitchen_tickets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("order_items.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Quantity of this item on this ticket",
    )

    # Relationships
    ticket: Mapped[KitchenTicket] = relationship(
        "KitchenTicket", back_populates="items",
    )
    order_item: Mapped["OrderItem"] = relationship("OrderItem", lazy="selectin")


# Avoid circular imports
from app.models.order import Order, OrderItem  # noqa: E402, F401
