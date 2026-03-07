"""Customer domain model for call-center and delivery channels.

Stores customer contact details and delivery addresses.
Phone numbers are stored in a normalized format for search (digits only).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import BaseMixin


class Customer(BaseMixin, Base):
    """A customer record, primarily used by the call-center channel.

    phone is the primary lookup key (partial match via pg_trgm in production,
    LIKE fallback in SQLite for tests).
    """

    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "phone", name="uq_customer_tenant_phone"),
        Index("ix_customers_tenant_phone", "tenant_id", "phone"),
        Index("ix_customers_tenant_name", "tenant_id", "name"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Normalized phone (digits only, e.g. 03001234567)",
    )
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    alt_contact: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Alternative contact phone for delivery rider",
    )
    default_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Primary delivery address (free-text)",
    )
    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="City for primary address (delivery zone routing)",
    )
    alt_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Alternative delivery address (e.g. office)",
    )
    alt_city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="City for alternative address",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Internal notes about customer preferences / allergies",
    )
    order_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Denormalized order count for quick display",
    )
    total_spent: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Denormalized total spent in paisa (completed orders only)",
    )
    last_order_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of most recent order",
    )
    risk_flag: Mapped[str] = mapped_column(
        String(20),
        default="normal",
        nullable=False,
        comment="Risk level: normal, high, blocked",
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
