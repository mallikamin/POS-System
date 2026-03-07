"""Discount domain models: configurable discount types and applied order discounts.

All monetary amounts are stored in paisa (1 PKR = 100 paisa) as integers.
"""

import uuid

from sqlalchemy import (
    Boolean,
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


class DiscountType(BaseMixin, Base):
    """Tenant-scoped catalog of discount types.

    kind: percent | fixed
    value: percentage in basis points (e.g. 1000 = 10%) or fixed amount in paisa
    """

    __tablename__ = "discount_types"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_discount_type_tenant_code"),
        Index("ix_discount_types_tenant_active", "tenant_id", "is_active"),
    )

    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="e.g. bank_promo, esr, customer, manual",
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="percent | fixed",
    )
    value: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Percent in basis points or fixed amount in paisa",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )


class OrderDiscount(BaseMixin, Base):
    """A discount applied to an order (or table session).

    source_type: matches the discount_type.code or 'manual'
    amount: the actual discount in paisa (always positive)
    """

    __tablename__ = "order_discounts"
    __table_args__ = (
        Index("ix_order_discounts_order", "order_id"),
        Index("ix_order_discounts_session", "table_session_id"),
    )

    order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    table_session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("table_sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    discount_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("discount_types.id", ondelete="SET NULL"),
        nullable=True,
    )
    label: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Display label e.g. 'Bank Promo 10%'",
    )
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="e.g. bank_promo, esr, customer, manual",
    )
    amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Discount amount in paisa (positive = discount)",
    )
    percent_bps: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Original percent in basis points (0 for fixed discounts)",
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_by: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
        nullable=False,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )

    # Relationships
    discount_type: Mapped["DiscountType | None"] = relationship(
        "DiscountType",
        lazy="selectin",
    )
    applier: Mapped["User"] = relationship("User", lazy="selectin")


from app.models.user import User  # noqa: E402, F401
