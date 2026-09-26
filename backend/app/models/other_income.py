"""Other income: money in that is not a sale (Danny's D-63).

Malik, 2026-09-26: record money received that is not a sale, e.g. a scrap
sale, rent received or an event deposit, per day, with a category and whether
it came in as cash or into the bank. It must feed the day summary's cash
position, which until now could only see sales, refunds and cash expenses.

Design notes
------------
* **The mirror of `app/models/expense.py`**, cut to what income needs: a
  category master (so totals per category can be trusted), a date, who paid,
  an amount, and how it arrived. No VAT split, no attachments, no status: money
  received is received, there is no "unpaid" income to track here.

* **Money is INTEGER minor units** (`amount_minor`), like a `Payment`, because
  the one place this is added up, the day summary cash position, adds it to
  integer payment sums. 350000 is Rs 3,500.

* **`method` is `cash` or `bank`, enforced.** The Expenses screen's free-text
  payment method forced the cash position to guess with a substring match on
  "cash"; income does not repeat that. Only `cash` rows enter the cash
  position; `bank` rows are recorded and listed but never counted as cash.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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

if TYPE_CHECKING:
    from app.models.location import Location
    from app.models.tenant import Tenant
    from app.models.user import User


INCOME_METHODS = ("cash", "bank")

# Seeded lazily on first open, like the expense categories. Malik's three
# examples plus a catch-all.
DEFAULT_INCOME_CATEGORIES = (
    "Scrap Sale",
    "Rent Received",
    "Event Deposit",
    "Other",
)


class IncomeCategory(BaseMixin, Base):
    """A bucket other income is counted under. Tenant-scoped, editable."""

    __tablename__ = "income_categories"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_income_category_tenant_name"),
        Index("ix_income_category_tenant_active", "tenant_id", "is_active"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    tenant: Mapped["Tenant"] = relationship("Tenant")


class OpeningBalance(BaseMixin, Base):
    """The cash the business held on the day it started using the system
    (Danny's D-62). One row per tenant.

    Cash only. D-62 asked for bank "if tracked", and nothing here tracks the
    bank: the POS never learns when card takings land, so a rolled-forward
    bank figure would drift from the statement from day one.

    The day summary rolls this forward: cash in hand at the start of a day is
    `cash_minor` plus every day's net cash from `as_of` up to that day.
    """

    __tablename__ = "opening_balances"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_opening_balance_tenant"),
        CheckConstraint("cash_minor >= 0", name="ck_opening_balance_cash_not_negative"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    # The first day the balance applies to: cash in hand at the START of it.
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    cash_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )

    tenant: Mapped["Tenant"] = relationship("Tenant")
    recorder: Mapped["User | None"] = relationship("User")


class OtherIncome(BaseMixin, Base):
    """One receipt of money that is not a sale."""

    __tablename__ = "other_income"
    __table_args__ = (
        Index("ix_other_income_tenant_date", "tenant_id", "received_on"),
        CheckConstraint("amount_minor > 0", name="ck_other_income_amount_positive"),
        CheckConstraint(
            "method IN ('cash', 'bank')", name="ck_other_income_method"
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("locations.id", ondelete="SET NULL"), index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("income_categories.id", ondelete="SET NULL"), index=True
    )

    received_on: Mapped[date] = mapped_column(Date, nullable=False)
    # Who paid: the scrap dealer, the tenant renting the upstairs room.
    payer: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    reference_number: Mapped[str | None] = mapped_column(String(100))
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False, default="cash")
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )

    tenant: Mapped["Tenant"] = relationship("Tenant")
    location: Mapped["Location | None"] = relationship("Location")
    category: Mapped["IncomeCategory | None"] = relationship("IncomeCategory")
    recorder: Mapped["User | None"] = relationship("User")
