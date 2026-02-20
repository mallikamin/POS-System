"""Customer domain model for call-center and delivery channels.

Stores customer contact details and delivery addresses.
Phone numbers are stored in a normalized format for search (digits only).
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
        String(20), nullable=False,
        comment="Normalized phone (digits only, e.g. 03001234567)",
    )
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    default_address: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Primary delivery address (free-text)",
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Internal notes about customer preferences / allergies",
    )
    order_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Denormalized order count for quick display",
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True,
    )
