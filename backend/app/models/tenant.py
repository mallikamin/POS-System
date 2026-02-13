import uuid

from sqlalchemy import Boolean, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import BaseMixin


class Tenant(BaseMixin, Base):
    """Multi-tenant restaurant entity.

    The tenant_id column (inherited from BaseMixin) is self-referencing:
    it points back to this tenant's own id, enabling consistent
    tenant-scoped queries across all models.
    """

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Self-referencing FK so tenant_id always points to tenants.id
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )

    # Relationships
    config: Mapped["RestaurantConfig"] = relationship(
        "RestaurantConfig", back_populates="tenant", uselist=False, lazy="selectin"
    )
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="tenant", lazy="raise"
    )
    roles: Mapped[list["Role"]] = relationship(
        "Role", back_populates="tenant", lazy="raise"
    )


# Avoid circular import issues -- these are only used for type hints
# in relationship() strings, so SQLAlchemy resolves them at runtime.
from app.models.restaurant_config import RestaurantConfig  # noqa: E402, F401
from app.models.user import Role, User  # noqa: E402, F401
