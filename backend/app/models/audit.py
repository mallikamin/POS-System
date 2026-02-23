"""Audit log model for tracking user actions across the system."""

import uuid

from sqlalchemy import ForeignKey, Index, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import BaseMixin


class AuditLog(BaseMixin, Base):
    """Records significant user actions for compliance and debugging.

    Captures who did what, when, and what changed.
    """

    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True, index=True
    )
    user_name: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True
    )
    action: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    changes: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True
    )
    detail: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    __table_args__ = (
        Index("ix_audit_logs_tenant_entity", "tenant_id", "entity_type", "created_at"),
    )
