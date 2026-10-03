"""Danny's D-99: visit-based loyalty (a stamp card).

A visit is one PAID bill, claimed once, however it is claimed: the cashier
typing the customer's phone, the customer scanning the QR on the bill or
receipt, or scanning it off the counter display. The database enforces one
visit per bill (see the constraint), so the cashier and a scan racing each
other cannot count a bill twice.

Progress is derived, never stored: visits so far, rewards earned =
visits // visits_required, rewards available = earned - redemptions.
"""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import BaseMixin


class LoyaltyVisit(BaseMixin, Base):
    __tablename__ = "loyalty_visits"
    __table_args__ = (
        # One visit per bill.
        UniqueConstraint("order_id", name="uq_loyalty_visit_order"),
        # Visits per customer per day are an owner setting
        # (restaurant_configs.loyalty_max_visits_per_day), enforced in
        # loyalty_service under a customer row lock, not by a constraint.
        Index("ix_loyalty_visits_tenant_customer_date", "tenant_id", "customer_id", "visit_date"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("orders.id"), nullable=False)
    visit_date: Mapped[date] = mapped_column(Date, nullable=False,
                                             comment="The restaurant's local date of the visit")
    source: Mapped[str] = mapped_column(String(10), nullable=False,
                                        comment="cashier | qr")


class LoyaltyRedemption(BaseMixin, Base):
    __tablename__ = "loyalty_redemptions"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_loyalty_redemption_order"),
        Index("ix_loyalty_redemptions_tenant_customer", "tenant_id", "customer_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("orders.id"), nullable=False)
    order_discount_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("order_discounts.id", ondelete="SET NULL"), nullable=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False,
                                        comment="Reward value in minor units")
    redeemed_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)


class LoyaltyWalletPass(BaseMixin, Base):
    """A guest's loyalty card in a phone wallet (Google Wallet today).

    A row means a save link was handed out, so the card may be on a phone:
    each counted visit pushes the new count to it. Google answers 404 for a
    card the guest never saved, which costs nothing.
    """

    __tablename__ = "loyalty_wallet_passes"
    __table_args__ = (
        UniqueConstraint("customer_id", "platform", name="uq_loyalty_wallet_pass_customer_platform"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(10), nullable=False, comment="google")
    object_id: Mapped[str] = mapped_column(String(120), nullable=False,
                                           comment="The card's id at the wallet provider")
