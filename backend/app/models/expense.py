"""Operating expenses: the costs that never pass through stock.

Martin Zubeldia (FZ LLC), 2026-09-06, item M10:

> "There is no expenses menu to attach the invoices of my expenses (not the ones
>  from suppliers which are already in the receiving of ingredients, but other
>  expenses such as rent, salaries etc...)"

He drew the boundary himself and it is the right one. Money paid to a supplier
for ingredients already has a home -- purchase order, goods receipt, stock
movement, cost per unit -- and duplicating it here would double-count the food
cost in every report that adds the two together. **Nothing in this module
touches stock**, and that is deliberate rather than unfinished: an expense is a
cash fact, not an inventory fact.

Design notes
------------
* 🔴 **Money is in MINOR UNITS stored as `Numeric`**, the same convention as the
  procurement and inventory modules: a value of `200` is 2.00 AED, not 200 AED.
  Every field is named `*_minor` so the mistake that overstated cost 100x on
  2026-08-26 cannot be repeated silently. Do not add a `* 100` in this module.

* **`amount_minor` is the whole invoice, tax included.** `tax_minor` is the
  portion of it that is VAT. Storing the total and carving the tax out of it,
  rather than storing net and adding tax on, is what a UAE invoice actually
  shows and what the recoverable-input-VAT figure is read from. A tenant that
  is not VAT registered leaves `tax_minor` at zero and nothing else changes.

* **The category is a real row, not a string.** Free text would let "Rent",
  "rent" and "Rnet" all become categories, and the whole point of the screen is
  a total per category that a human can trust.

* **Attachments are a child table, not a column.** One expense routinely has an
  invoice AND a payment confirmation, and discovering that after the fact would
  cost a migration. The bytes themselves live in `media_files` (see
  `app/models/media.py` for why they are in Postgres and not on disk).

* **`status` is not derived.** `unpaid -> paid` is a decision a human makes when
  the money leaves, and there is no bank feed here to infer it from.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
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
    from app.models.media import MediaFile
    from app.models.tenant import Tenant
    from app.models.user import User


# An expense's life. `draft` exists so a half-entered invoice can be saved
# without it counting toward a total anybody reads.
EXPENSE_STATUSES = ("draft", "unpaid", "paid")

# Statuses that represent real money owed or spent, and therefore belong in
# every total. `draft` is deliberately excluded.
EXPENSE_COUNTED_STATUSES = ("unpaid", "paid")

# Seeded for a new tenant, and for every existing one by the migration. They are
# ordinary rows afterwards: renameable, deactivatable, and joined by whatever
# else the operator adds.
DEFAULT_EXPENSE_CATEGORIES = (
    "Rent",
    "Salaries & Wages",
    "Utilities",
    "Marketing",
    "Repairs & Maintenance",
    "Licences & Government Fees",
    "Transport & Delivery",
    "Professional Fees",
    "Insurance",
    "Other",
)


class ExpenseCategory(BaseMixin, Base):
    """A bucket an expense is counted under. Tenant-scoped, editable."""

    __tablename__ = "expense_categories"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_expense_category_tenant_name"),
        Index("ix_expense_category_tenant_active", "tenant_id", "is_active"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    tenant: Mapped["Tenant"] = relationship("Tenant")
    expenses: Mapped[list["Expense"]] = relationship(
        "Expense", back_populates="category"
    )


class Expense(BaseMixin, Base):
    """One invoice or bill that is not a purchase of stock."""

    __tablename__ = "expenses"
    __table_args__ = (
        Index("ix_expense_tenant_date", "tenant_id", "expense_date"),
        Index("ix_expense_tenant_status", "tenant_id", "status"),
        Index("ix_expense_tenant_category", "tenant_id", "category_id"),
        CheckConstraint("amount_minor >= 0", name="ck_expense_amount_not_negative"),
        CheckConstraint("tax_minor >= 0", name="ck_expense_tax_not_negative"),
        # The VAT cannot be more than the invoice it was carved out of. Cheap to
        # state here, and it catches the commonest data-entry slip -- typing the
        # net amount in the total box and the gross in the tax box.
        CheckConstraint("tax_minor <= amount_minor", name="ck_expense_tax_within_total"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    # Which site the cost belongs to. Nullable on purpose: rent for the head
    # office and an annual trade licence belong to the business, not to a
    # branch, and forcing a location on them would distort per-site profit.
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("locations.id", ondelete="SET NULL"), index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("expense_categories.id", ondelete="SET NULL"), index=True
    )

    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Who was paid. Free text rather than a supplier FK: the landlord, the
    # electricity authority and an employee are not suppliers of ingredients and
    # do not belong in the procurement master.
    payee: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # The counterparty's own invoice number, for matching against their books.
    reference_number: Mapped[str | None] = mapped_column(String(100))

    # Total of the invoice, VAT included. Minor units.
    amount_minor: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    # The VAT portion inside `amount_minor`. Minor units. Zero when the tenant
    # is not registered or the supply is exempt.
    tax_minor: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unpaid")
    payment_method: Mapped[str | None] = mapped_column(String(50))
    paid_on: Mapped[date | None] = mapped_column(Date)

    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )

    tenant: Mapped["Tenant"] = relationship("Tenant")
    location: Mapped["Location | None"] = relationship("Location")
    category: Mapped["ExpenseCategory | None"] = relationship(
        "ExpenseCategory", back_populates="expenses"
    )
    recorder: Mapped["User | None"] = relationship("User")
    attachments: Mapped[list["ExpenseAttachment"]] = relationship(
        "ExpenseAttachment",
        back_populates="expense",
        cascade="all, delete-orphan",
        order_by="ExpenseAttachment.created_at",
    )


class ExpenseAttachment(BaseMixin, Base):
    """A file pinned to an expense: the invoice, or the proof of payment.

    The row carries the filename and size so the list can be rendered without
    touching the payload column at all; the bytes stay in `media_files`.
    """

    __tablename__ = "expense_attachments"
    __table_args__ = (
        Index("ix_expense_attachment_expense", "expense_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    expense_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("media_files.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    expense: Mapped["Expense"] = relationship("Expense", back_populates="attachments")
    media: Mapped["MediaFile"] = relationship("MediaFile")
