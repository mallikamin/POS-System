"""Every model call this system makes, with its tokens and its cost.

Why this table exists before either AI feature does
---------------------------------------------------
You cannot optimise what you cannot measure, and the most expensive AI bug is
the one nobody can see. The `api-cost-playbook` skill puts instrumentation at
step 1 of its checklist for a reason: on the project it was distilled from, the
first usage figures undercounted by ~83% because only one of the call paths was
logged.

So: one row per model call, written by the single client wrapper that every
feature must go through. Nothing calls Anthropic without landing here.

The row also carries the four token classes separately, because they are priced
very differently -- a cache read is roughly a tenth of an uncached input token,
and a cache write is more than one. A single "tokens" number would hide exactly
the thing worth watching.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import BaseMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class AIUsageLog(BaseMixin, Base):
    """One model call: what it was for, what it cost, whether it worked."""

    __tablename__ = "ai_usage_log"
    __table_args__ = (
        # The daily cap query is (tenant, day), so that is the index.
        Index("ix_ai_usage_tenant_day", "tenant_id", "usage_date"),
        Index("ix_ai_usage_kind", "tenant_id", "kind"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )

    # What the call was FOR. The playbook's F2 tripwire pins the set of call
    # sites; this is how a new one shows up in the data rather than hiding in
    # an aggregate.
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(60), nullable=False)

    # Stored as a UTC date rather than derived from `created_at` at query time,
    # so the daily cap cannot drift with the server's timezone.
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)

    # The four token classes, priced differently. Kept apart on purpose.
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_creation_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Estimated, in USD, from the rate table in `ai_client`. Explicitly an
    # estimate: the console is the authority and this is reconciled against it,
    # never quoted as the invoice.
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=0
    )

    latency_ms: Mapped[int | None] = mapped_column(Integer)
    succeeded: Mapped[bool] = mapped_column(default=True, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)

    requested_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    called_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    tenant: Mapped["Tenant"] = relationship("Tenant")
