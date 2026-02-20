"""Payment domain models: payment methods, payments, and cash drawer sessions."""

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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import BaseMixin


class PaymentMethod(BaseMixin, Base):
    """Tenant-scoped payment method configuration."""

    __tablename__ = "payment_methods"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_payment_method_tenant_code"),
        Index("ix_payment_methods_tenant_active", "tenant_id", "is_active"),
    )

    code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="cash | card | mobile_wallet | bank_transfer",
    )
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    requires_reference: Mapped[bool] = mapped_column(default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="method")


class Payment(BaseMixin, Base):
    """Individual payment or refund transaction against an order."""

    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_tenant_order", "tenant_id", "order_id"),
        Index("ix_payments_tenant_created", "tenant_id", "created_at"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    method_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("payment_methods.id"), nullable=False, index=True
    )
    parent_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("payments.id", ondelete="SET NULL"), nullable=True, index=True
    )

    kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default="payment", comment="payment | refund"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="completed", comment="pending | completed | failed"
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False, comment="Amount in paisa")
    tendered_amount: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Cash tendered amount in paisa"
    )
    change_amount: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Cash change returned in paisa"
    )
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    order: Mapped["Order"] = relationship("Order", lazy="selectin")
    method: Mapped[PaymentMethod] = relationship("PaymentMethod", back_populates="payments", lazy="selectin")
    processor: Mapped["User"] = relationship("User", lazy="selectin")
    parent_payment: Mapped["Payment | None"] = relationship(
        "Payment", remote_side="Payment.id", lazy="selectin"
    )


class CashDrawerSession(BaseMixin, Base):
    """Open/close lifecycle for cashier cash drawer sessions."""

    __tablename__ = "cash_drawer_sessions"
    __table_args__ = (
        Index("ix_cash_drawer_tenant_status", "tenant_id", "status"),
        Index("ix_cash_drawer_tenant_opened", "tenant_id", "opened_at"),
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open", comment="open | closed"
    )
    opened_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    opening_float: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Opening float in paisa"
    )
    closed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closing_balance_expected: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="System expected closing balance in paisa"
    )
    closing_balance_counted: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Cashier counted closing balance in paisa"
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    opener: Mapped["User"] = relationship("User", foreign_keys=[opened_by], lazy="selectin")
    closer: Mapped["User | None"] = relationship("User", foreign_keys=[closed_by], lazy="selectin")


from app.models.order import Order  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
