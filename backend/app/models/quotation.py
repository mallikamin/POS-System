"""Back-office quotations: a price offered before there is an order.

Martin's Section 2: *"Capacity to issue quotations directly from the back
office."* For a business selling B2B out of a production site, this is how the
conversation starts -- a caterer asks what 400 croissants would cost, and the
answer has to be a document with a number and an expiry date on it, not a
WhatsApp message.

Why this is not just a draft order
----------------------------------
A quotation and an order are different things and conflating them loses
information a business needs:

* A quotation **expires**. A price offered in August is not binding in
  November, and `valid_until` is the whole reason a customer can rely on it
  until then.
* A quotation can be **declined**, and that is a real, reportable outcome. A
  draft order that never became an order is indistinguishable from one somebody
  abandoned halfway through typing.
* A quotation must **not** touch stock, the kitchen, or the day's takings. A
  draft order sitting in the orders table is one careless status change away
  from all three.

So it is its own table, and `convert_to_order` is an explicit, one-way step
that records which order came from which quotation.

Money
-----
🔴 Sales-side money, so INTEGER minor units, matching `orders.total` and the
tax invoice -- NOT the `Numeric` convention the inventory and procurement
modules use for costs. Both conventions exist in this schema on purpose; the
one that applies is the one used by the neighbouring table.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
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
    from app.models.customer import Customer
    from app.models.location import Location
    from app.models.menu import MenuItem
    from app.models.order import Order
    from app.models.tenant import Tenant
    from app.models.user import User


# `expired` is derived from `valid_until` at read time rather than stored: a
# quotation does not expire because a job ran, it expires because the date
# passed. Storing it would need a scheduler and would be wrong between runs.
QUOTATION_STATUSES = ("draft", "sent", "accepted", "declined", "converted")


class Quotation(BaseMixin, Base):
    """A priced offer, valid until a date."""

    __tablename__ = "quotations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "quote_number", name="uq_quotation_tenant_number"
        ),
        Index("ix_quotation_tenant_status", "tenant_id", "status"),
        CheckConstraint(
            "status IN ('draft', 'sent', 'accepted', 'declined', 'converted')",
            name="ck_quotation_status",
        ),
        CheckConstraint(
            "tax_rate_bps >= 0 AND tax_rate_bps <= 10000",
            name="ck_quotation_tax_range",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    quote_number: Mapped[str] = mapped_column(String(40), nullable=False)

    # Which site is quoting. Carries the legal identity that goes on the
    # document, exactly as it does for a tax invoice.
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("locations.id", ondelete="SET NULL")
    )

    # The customer, either linked or typed. A quotation frequently goes to
    # somebody who is not in the system yet -- refusing to quote until they
    # are would be the tail wagging the dog.
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="SET NULL")
    )
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_phone: Mapped[str | None] = mapped_column(String(50))
    customer_email: Mapped[str | None] = mapped_column(String(255))
    customer_address: Mapped[str | None] = mapped_column(Text)
    customer_trn: Mapped[str | None] = mapped_column(
        String(50)
    )  # A B2B customer's own tax registration number, printed on the document

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)

    # VAT-INCLUSIVE prices, like everywhere else on the sales side. The
    # document backs the VAT out for display; it is never added on top.
    tax_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # INTEGER MINOR UNITS. Derived from the lines, never assigned by hand.
    subtotal_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discount_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    notes: Mapped[str | None] = mapped_column(Text)
    terms: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_to_email: Mapped[str | None] = mapped_column(String(255))
    email_send_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_email_error: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decline_reason: Mapped[str | None] = mapped_column(Text)

    # Set once, when the quotation becomes real business. One-way on purpose:
    # the link is how "what did we quote for this order?" is answered later.
    converted_order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="SET NULL")
    )
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped["Tenant"] = relationship("Tenant")
    location: Mapped["Location | None"] = relationship("Location")
    customer: Mapped["Customer | None"] = relationship("Customer")
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by])
    converted_order: Mapped["Order | None"] = relationship(
        "Order", foreign_keys=[converted_order_id]
    )
    items: Mapped[list["QuotationItem"]] = relationship(
        "QuotationItem", back_populates="quotation", cascade="all, delete-orphan"
    )


class QuotationItem(BaseMixin, Base):
    """One priced line on a quotation.

    The item name and price are SNAPSHOTTED rather than read live from the menu.
    A quotation is an offer at a price; if the menu price changes next week, the
    document the customer is holding must still say what it said when it was
    sent. That is the same reasoning `OrderItem` already applies.
    """

    __tablename__ = "quotation_items"
    __table_args__ = (
        Index("ix_quotation_item_quotation", "quotation_id"),
        CheckConstraint("quantity > 0", name="ck_quotation_item_qty_positive"),
        CheckConstraint(
            "unit_price_minor >= 0", name="ck_quotation_item_price_positive"
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    quotation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False
    )
    # Nullable: a quotation may legitimately include something that is not a
    # menu item at all ("delivery to Abu Dhabi", "branded packaging").
    menu_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("menu_items.id", ondelete="SET NULL")
    )

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    line_total_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    quotation: Mapped["Quotation"] = relationship("Quotation", back_populates="items")
    menu_item: Mapped["MenuItem | None"] = relationship("MenuItem")
