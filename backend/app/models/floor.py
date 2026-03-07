"""Floor plan domain models: floors and tables.

Table positions (pos_x, pos_y, width, height, rotation) are stored as
floats for sub-pixel precision in the drag-and-drop floor editor.
"""

import uuid

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import BaseMixin


class Floor(BaseMixin, Base):
    """A physical dining area / section (e.g. "Ground Floor", "Terrace")."""

    __tablename__ = "floors"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_floor_tenant_name"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )

    # Relationships
    tables: Mapped[list["Table"]] = relationship(
        "Table",
        back_populates="floor",
        lazy="selectin",
        order_by="Table.number",
    )


class Table(BaseMixin, Base):
    """An individual dining table within a floor.

    status tracks the current occupancy state:
      - available: empty, ready for seating
      - occupied: customers seated (linked to an active order in Phase 5)
      - reserved: reservation held
      - cleaning: recently vacated, being cleaned
    """

    __tablename__ = "tables"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "floor_id", "number", name="uq_table_tenant_floor_number"
        ),
    )

    floor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("floors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Optional display label (e.g. 'VIP-1')"
    )
    capacity: Mapped[int] = mapped_column(Integer, default=4, nullable=False)

    # Canvas position for floor editor (pixels / editor units)
    pos_x: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    pos_y: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    width: Mapped[float] = mapped_column(Float, default=80.0, nullable=False)
    height: Mapped[float] = mapped_column(Float, default=80.0, nullable=False)
    rotation: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False, comment="Rotation in degrees (0-360)"
    )
    shape: Mapped[str] = mapped_column(
        String(20),
        default="square",
        nullable=False,
        comment="square | round | rectangle",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="available",
        nullable=False,
        comment="available | occupied | reserved | cleaning",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )

    # Relationships
    floor: Mapped[Floor] = relationship("Floor", back_populates="tables")
