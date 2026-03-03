"""Table session model for dine-in session consolidation.

A table session groups multiple dine-in orders for the same table into
a single billing session. The session stays open until all orders are
settled and the table is released.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import BaseMixin


class TableSession(BaseMixin, Base):
    """An open-to-close session for a dine-in table.

    status: open | closed
    """

    __tablename__ = "table_sessions"
    __table_args__ = (
        Index("ix_table_sessions_tenant_status", "tenant_id", "status"),
        Index("ix_table_sessions_table_status", "table_id", "status"),
    )

    table_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tables.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), default="open", nullable=False,
        comment="open | closed",
    )
    opened_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False,
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    closed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True,
    )

    # Relationships
    table: Mapped["Table"] = relationship("Table", lazy="selectin")
    opener: Mapped["User"] = relationship("User", foreign_keys=[opened_by], lazy="selectin")
    closer: Mapped["User | None"] = relationship("User", foreign_keys=[closed_by], lazy="selectin")
    orders: Mapped[list["Order"]] = relationship(
        "Order", back_populates="table_session", lazy="selectin",
    )


from app.models.floor import Table  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
from app.models.order import Order  # noqa: E402, F401
