"""Physical locations, per-location stock, inter-location transfers, and the
sales channels a sale can arrive through.

Why this exists
---------------
Until now a tenant was implicitly one place: `Ingredient.current_stock` was a
single tenant-wide number, and an order had no idea where it happened. FZ LLC
(Martin Zubeldia, UAE) runs **two** locations and the difference is not
cosmetic:

  * **Location 1 - production / wholesale.** Recipes and sub-recipes are made
    here and sold B2B. Needs a proper **A4 VAT tax invoice** carrying the full
    legal company name and tax registration number -- explicitly *not* a
    thermal ticket.
  * **Location 2 - delivery only.** Sells through the call centre, third-party
    delivery apps and e-commerce.

Stock moves between the two, a sale must deduct from **the location that sold
it**, and profitability has to be reported per location and per channel.

Design notes
------------
* Per-location stock lives in its own `location_stock` row rather than as a
  column on `Ingredient`. The ingredient master stays one row per tenant (one
  definition of "Flour"), while the quantity of it is a fact about a *place*.
  `Ingredient.current_stock` is kept as the tenant-wide rollup so nothing that
  already reads it breaks.
* Percentages are stored as **basis points** (integer, 1500 = 15.00%), matching
  `restaurant_configs.cash_tax_rate_bps` and the discount thresholds. Money and
  quantities use `Numeric`, matching the inventory module. No floats anywhere.
* Every table is tenant-scoped, like everything else in this schema.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
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
    from app.models.inventory import Ingredient
    from app.models.tenant import Tenant
    from app.models.user import User


# ---------------------------------------------------------------------------
# LOCATIONS
# ---------------------------------------------------------------------------

# What a location is FOR. This drives real behaviour, not just a label:
# `production` runs recipes and issues A4 tax invoices; `delivery` sells through
# channels and prints tickets. `retail` is the ordinary counter case.
LOCATION_TYPES = ("production", "delivery", "retail")

# How this location bills a customer. Location 1 must be able to issue a
# VAT-compliant A4 document; Location 2 prints the existing thermal ticket.
INVOICE_FORMATS = ("a4_tax_invoice", "thermal_ticket")


class Location(BaseMixin, Base):
    """A physical place that holds stock and sells.

    Also carries the legal identity used on its invoices, because in the UAE a
    tax invoice must show the issuing entity's full legal name and Tax
    Registration Number -- and a tenant may bill under a different entity per
    site.
    """

    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_location_tenant_code"),
        Index("ix_location_tenant_active", "tenant_id", "is_active"),
        CheckConstraint(
            "location_type IN ('production', 'delivery', 'retail')",
            name="ck_location_type",
        ),
        CheckConstraint(
            "invoice_format IN ('a4_tax_invoice', 'thermal_ticket')",
            name="ck_location_invoice_format",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )

    # Identity
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # Short handle used on transfer/invoice numbers, e.g. "PROD", "DEL"
    location_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="retail"
    )

    # Legal identity for tax invoices (Martin's Section 2: "mandatory fields for
    # VAT and the full company name"). Nullable because a delivery-only site
    # printing tickets does not need them.
    legal_name: Mapped[str | None] = mapped_column(String(300))
    tax_registration_number: Mapped[str | None] = mapped_column(
        String(50)
    )  # UAE TRN, or the local equivalent
    address_line1: Mapped[str | None] = mapped_column(String(300))
    address_line2: Mapped[str | None] = mapped_column(String(300))
    city: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))

    # Billing behaviour
    invoice_format: Mapped[str] = mapped_column(
        String(30), nullable=False, default="thermal_ticket"
    )
    invoice_prefix: Mapped[str] = mapped_column(
        String(10), nullable=False, default="INV"
    )

    # Flags
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # Where a sale lands when the caller names no location, so existing
    # single-site tenants keep working untouched.
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    stock: Mapped[list["LocationStock"]] = relationship(
        "LocationStock", back_populates="location", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# PER-LOCATION STOCK
# ---------------------------------------------------------------------------


class LocationStock(BaseMixin, Base):
    """How much of one ingredient is held at one location.

    One row per (location, ingredient). The row is created lazily the first time
    that ingredient moves at that location, so adding a location does not have
    to fan out across the whole ingredient master.
    """

    __tablename__ = "location_stock"
    __table_args__ = (
        UniqueConstraint(
            "location_id", "ingredient_id", name="uq_location_stock_loc_ingredient"
        ),
        Index("ix_location_stock_tenant", "tenant_id", "location_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=0
    )
    # Reorder thresholds are per-location on purpose: a production site and a
    # delivery site do not want to be warned at the same level.
    reorder_point: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=0
    )
    reorder_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=0
    )

    location: Mapped["Location"] = relationship("Location", back_populates="stock")
    ingredient: Mapped["Ingredient"] = relationship("Ingredient")


# ---------------------------------------------------------------------------
# SALES CHANNELS
# ---------------------------------------------------------------------------


class SalesChannel(BaseMixin, Base):
    """A route a sale arrives through, and what that route costs us.

    Martin's Section 8, his stated key customisation: net profit must be
    `selling price - product cost - channel commission`, not merely
    `selling price - product cost`. Talabat/Careem/noon take a percentage;
    a direct WhatsApp order may take only a payment-processing fee.
    """

    __tablename__ = "sales_channels"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_sales_channel_tenant_code"),
        Index("ix_sales_channel_tenant_active", "tenant_id", "is_active"),
        CheckConstraint(
            "commission_bps >= 0 AND commission_bps <= 10000",
            name="ck_sales_channel_commission_range",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)

    # Basis points: 1500 = 15.00%. Integer maths, no float drift on money.
    commission_bps: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    # Some channels charge a flat per-order fee as well as (or instead of) a
    # percentage. Stored in minor units, like every other money field here.
    fixed_fee_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Martin (FZ LLC, 2026-09-02) wanted Deliveroo / Careem / Keeta / Noon as
    # entry points on the POS beside pick up and call centre. They are sales
    # channels, not order types, so this flag puts a channel on the channel
    # selector as its own tile. Off for a channel whose orders never start at
    # the till (the website channel: those arrive through the storefront).
    pos_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    notes: Mapped[str | None] = mapped_column(Text)

    tenant: Mapped["Tenant"] = relationship("Tenant")


# ---------------------------------------------------------------------------
# STOCK TRANSFERS BETWEEN LOCATIONS
# ---------------------------------------------------------------------------

TRANSFER_STATUSES = ("draft", "in_transit", "received", "cancelled")


class StockTransfer(BaseMixin, Base):
    """A movement of stock from one location to another.

    Deliberately two-phase (`send` then `receive`) rather than instantaneous.
    Stock leaves the source when it is sent and only arrives at the destination
    when someone confirms receipt, so goods in a van are not counted as
    available in two places at once -- and a short delivery is visible as a
    difference between quantity sent and quantity received.
    """

    __tablename__ = "stock_transfers"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "transfer_number", name="uq_transfer_tenant_number"
        ),
        Index("ix_transfer_tenant_status", "tenant_id", "status"),
        CheckConstraint(
            "from_location_id <> to_location_id", name="ck_transfer_distinct_locations"
        ),
        CheckConstraint(
            "status IN ('draft', 'in_transit', 'received', 'cancelled')",
            name="ck_transfer_status",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    transfer_number: Mapped[str] = mapped_column(String(40), nullable=False)

    from_location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("locations.id"), nullable=False
    )
    to_location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("locations.id"), nullable=False
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    notes: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))

    from_location: Mapped["Location"] = relationship(
        "Location", foreign_keys=[from_location_id]
    )
    to_location: Mapped["Location"] = relationship(
        "Location", foreign_keys=[to_location_id]
    )
    items: Mapped[list["StockTransferItem"]] = relationship(
        "StockTransferItem",
        back_populates="transfer",
        cascade="all, delete-orphan",
    )
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by])


class StockTransferItem(BaseMixin, Base):
    """One ingredient line on a transfer."""

    __tablename__ = "stock_transfer_items"
    __table_args__ = (
        Index("ix_transfer_item_transfer", "transfer_id"),
        CheckConstraint("quantity_sent > 0", name="ck_transfer_item_qty_positive"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    transfer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("stock_transfers.id", ondelete="CASCADE"), nullable=False
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingredients.id"), nullable=False
    )

    quantity_sent: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    # Null until receipt is confirmed. When it differs from quantity_sent the
    # shortfall is real and visible rather than silently absorbed.
    quantity_received: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )

    transfer: Mapped["StockTransfer"] = relationship(
        "StockTransfer", back_populates="items"
    )
    ingredient: Mapped["Ingredient"] = relationship("Ingredient")


# ---------------------------------------------------------------------------
# TAX INVOICE NUMBERING
# ---------------------------------------------------------------------------


class TaxInvoiceSequence(BaseMixin, Base):
    """The next tax invoice number to hand out, per document series.

    Exists because the previous scheme derived the number from a live COUNT of
    the tenant's orders (F33): seven different sales all read `FZD-00007`, and
    every number moved as new orders arrived. A tax invoice number must
    identify one document permanently, so it has to be reserved, not computed.

    Keyed on the PREFIX rather than the location id, because the prefix is what
    a reader sees and what an accountant reconciles. Two sites deliberately
    sharing a prefix are declaring one document series and should share one
    run of numbers; a site with its own prefix gets its own run. Keying on
    location_id instead would silently issue two documents numbered `FZW-00007`
    the day someone gave a second site the same prefix.

    Numbers are consumed on issue and never returned. A gap therefore means a
    document was produced and then the order was voided, which is a normal and
    auditable thing for an invoice sequence to show.
    """

    __tablename__ = "tax_invoice_sequences"
    __table_args__ = (
        UniqueConstraint("tenant_id", "prefix", name="uq_tax_invoice_seq_tenant_prefix"),
    )

    prefix: Mapped[str] = mapped_column(String(10), nullable=False)
    next_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
