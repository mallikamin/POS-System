"""Delivery areas and their fees.

Deliberately a table rather than a config blob or a constant in code.

The fee MUST be derived server-side: the public order endpoint accepts an area
code from the browser and looks the fee up here. If the browser sent the fee,
a customer could order a 15.00 delivery for 3.00.

Modelled by NAMED AREA rather than postcode on purpose. Chick Shack's printed
menu prices delivery by village -- Garelochhead 3.00 through to Arrochar 15.00 --
and nearly all of those villages sit inside the SAME G84 outward code. A
postcode-prefix rule would quote 3.00 for a 15.00 run. It is also how the shop
and its drivers already think about it.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import BaseMixin


class DeliveryArea(BaseMixin, Base):
    """One named area the shop delivers to, with its flat fee."""

    __tablename__ = "delivery_areas"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_delivery_area_tenant_code"),
    )

    code: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        comment="Stable slug the storefront sends, e.g. 'garelochhead'",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="As printed on the menu, e.g. 'Kilcreggan & Cove'",
    )
    fee: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Flat delivery fee in minor units (pence/paisa)",
    )
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
