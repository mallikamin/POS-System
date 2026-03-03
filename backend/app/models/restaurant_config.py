import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import BaseMixin


class RestaurantConfig(BaseMixin, Base):
    """Per-tenant restaurant configuration (one-to-one with Tenant).

    Monetary precision note:
        default_tax_rate is stored in basis points (1/100 of a percent).
        For example, 16.00% is stored as 1600.
    """

    __tablename__ = "restaurant_configs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    payment_flow: Mapped[str] = mapped_column(
        String(50), default="order_first", nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(10), default="PKR", nullable=False
    )
    timezone: Mapped[str] = mapped_column(
        String(50), default="Asia/Karachi", nullable=False
    )
    tax_inclusive: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    default_tax_rate: Mapped[int] = mapped_column(
        Integer, default=1600, nullable=False, comment="Tax rate in basis points (1600 = 16.00%)"
    )
    cash_tax_rate_bps: Mapped[int] = mapped_column(
        Integer, default=1600, nullable=False, comment="Tax rate for cash payments in basis points (1600 = 16%)"
    )
    card_tax_rate_bps: Mapped[int] = mapped_column(
        Integer, default=500, nullable=False, comment="Tax rate for card payments in basis points (500 = 5%)"
    )
    receipt_header: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )
    receipt_footer: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )

    # Discount approval thresholds — if either is exceeded, manager verify required
    discount_approval_threshold_bps: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Percent threshold in basis points (0 = disabled). "
                "E.g. 1500 means discounts > 15% need manager approval.",
    )
    discount_approval_threshold_fixed: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Fixed amount threshold in paisa (0 = disabled). "
                "E.g. 50000 means discounts > Rs 500 need manager approval.",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="config")


# Import for relationship resolution
from app.models.tenant import Tenant  # noqa: E402, F401
