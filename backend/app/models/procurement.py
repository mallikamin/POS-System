"""Suppliers and the purchase-order workflow.

Martin's Section 5, end to end:

    Select Location -> Select Supplier -> Select Items -> Create PO
        -> Send PO by email -> Receive Goods -> Update Inventory

Design notes
------------
* **A supplier is tenant-scoped; the items it sells are a separate table.**
  `SupplierItem` is the join between a supplier and an ingredient, and it is
  where the supplier's own SKU, pack size, lead time and last paid price live.
  Putting the price on the join rather than on the ingredient is the whole
  point: two suppliers sell the same flour at two different prices, and the
  ingredient master must not have to pick one.

* 🔴 **Money here is in MINOR UNITS stored as `Numeric`, matching
  `Ingredient.cost_per_unit` and `Recipe.cost_per_serving`.** A value of
  `200` is 2.00 AED, not 200 AED. This convention is inherited from the
  inventory module and is deliberately named in every field (`*_minor`) after
  a real bug on 2026-08-26 where a service multiplied `cost_per_serving` by 100
  to "convert to minor units" and overstated cost 100x. The unit test agreed
  with the bug. Do not add a `* 100` anywhere in this module.

* **Quantities are `Numeric`, never float**, like the rest of inventory.

* **Receiving is repeatable and partial.** A PO can be received in several
  deliveries; `quantity_received` accumulates. The status moves
  `sent -> partially_received -> received` on its own from the line totals, so
  it can never disagree with the lines it is derived from.

* **Nothing in this module writes stock directly.** Every goods receipt goes
  through `stock_service.move_stock`, the single chokepoint, so the balance and
  the movement log cannot drift apart.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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
    from app.models.location import Location
    from app.models.tenant import Tenant
    from app.models.user import User


# A PO's life. `partially_received` exists because a supplier who ships 8 of the
# 10 sacks you ordered has neither fulfilled nor failed the order, and flattening
# that to one of the two loses the fact that 2 are still owed.
PO_STATUSES = ("draft", "sent", "partially_received", "received", "cancelled")

# Statuses from which goods can still be booked in.
PO_RECEIVABLE_STATUSES = ("sent", "partially_received")


# ---------------------------------------------------------------------------
# SUPPLIERS
# ---------------------------------------------------------------------------


class Supplier(BaseMixin, Base):
    """A company we buy from."""

    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_supplier_tenant_code"),
        Index("ix_supplier_tenant_active", "tenant_id", "is_active"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # Short handle used on PO numbers, e.g. "ALMAYA"

    # Contact. `email` is not merely informational: it is where a PO is sent,
    # and sending is refused without it rather than silently doing nothing.
    contact_name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))

    address_line1: Mapped[str | None] = mapped_column(String(300))
    address_line2: Mapped[str | None] = mapped_column(String(300))
    city: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(120))

    # Commercial terms, free text on purpose. "30 days EOM" and "cash on
    # delivery" are both real answers and neither is an enum.
    payment_terms: Mapped[str | None] = mapped_column(String(200))
    tax_registration_number: Mapped[str | None] = mapped_column(String(50))
    # Typical days from order to delivery. Feeds the AI ordering suggestion:
    # what to order depends on how long it takes to arrive.
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    tenant: Mapped["Tenant"] = relationship("Tenant")
    items: Mapped[list["SupplierItem"]] = relationship(
        "SupplierItem", back_populates="supplier", cascade="all, delete-orphan"
    )


class SupplierItem(BaseMixin, Base):
    """One ingredient, as sold by one supplier.

    Carries the supplier's own catalogue number, the pack it ships in, and the
    price last actually paid. The price lives here rather than on the
    ingredient because the same ingredient has a different price from every
    supplier, and the ingredient master must hold one definition of "Flour",
    not one supplier's opinion of it.
    """

    __tablename__ = "supplier_items"
    __table_args__ = (
        UniqueConstraint(
            "supplier_id", "ingredient_id", name="uq_supplier_item_supplier_ingredient"
        ),
        Index("ix_supplier_item_tenant", "tenant_id", "ingredient_id"),
        CheckConstraint("last_price_minor >= 0", name="ck_supplier_item_price_positive"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False
    )

    supplier_sku: Mapped[str | None] = mapped_column(String(100))
    # What the supplier calls it, when that differs from our ingredient name.
    # Printed on the PO next to our name so the warehouse can match it.
    supplier_item_name: Mapped[str | None] = mapped_column(String(300))

    # MINOR UNITS. 250 = 2.50 AED per `unit` of the ingredient. See module docstring.
    last_price_minor: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    last_purchased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # How the supplier ships it, e.g. 25 (kg) per sack. Used to round an order
    # up to whole packs; 0 means "no pack size, order any quantity".
    pack_size: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=0
    )
    minimum_order_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=0
    )
    lead_time_days: Mapped[int | None] = mapped_column(Integer)

    # When several suppliers sell the same ingredient, this is the one the
    # ordering suggestion picks by default.
    is_preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="items")
    ingredient: Mapped["Ingredient"] = relationship("Ingredient")


# ---------------------------------------------------------------------------
# PURCHASE ORDERS
# ---------------------------------------------------------------------------


class PurchaseOrder(BaseMixin, Base):
    """An order placed with a supplier, for delivery to one location.

    The location is not decoration: goods received against this PO are booked
    into that location's stock, and a two-site operator ordering flour for the
    production kitchen must not have it land in the delivery kitchen.
    """

    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "po_number", name="uq_po_tenant_number"),
        Index("ix_po_tenant_status", "tenant_id", "status"),
        Index("ix_po_tenant_supplier", "tenant_id", "supplier_id"),
        CheckConstraint(
            "status IN ('draft', 'sent', 'partially_received', 'received', "
            "'cancelled')",
            name="ck_po_status",
        ),
        CheckConstraint(
            "tax_bps >= 0 AND tax_bps <= 10000", name="ck_po_tax_range"
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    po_number: Mapped[str] = mapped_column(String(40), nullable=False)

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("suppliers.id"), nullable=False
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("locations.id"), nullable=False
    )

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    expected_date: Mapped[date | None] = mapped_column(Date)

    # VAT applied to the whole order, in basis points (500 = 5.00%), matching
    # every other percentage in this schema. Purchases are quoted NET of VAT by
    # UAE suppliers, so here tax is ADDED on top -- the opposite of the sales
    # side, where shelf prices already include it. That asymmetry is real, not
    # an inconsistency.
    tax_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Denormalised totals, MINOR UNITS. Recomputed from the lines by
    # `purchase_order_service.recalculate_totals` on every change, never
    # written by hand, so they cannot disagree with the lines.
    subtotal_minor: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    tax_minor: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    total_minor: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )

    # "Additional comments" to the supplier (Martin, FZ LLC 2026-09-02): printed
    # on the document under the delivery instructions. It was internal-only
    # before, and never printed, which is what he was missing.
    notes: Mapped[str | None] = mapped_column(Text)
    # Free-text instructions printed on the document itself, e.g. "deliver
    # before 9am". Kept apart from `notes` so each reads as its own section.
    delivery_instructions: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The address the PO actually went to, snapshotted. If the supplier's
    # contact email changes later, the record of where this one was sent must
    # not change with it.
    sent_to_email: Mapped[str | None] = mapped_column(String(255))
    # How many times it has been emailed. A resend is legitimate (suppliers
    # lose emails) and should be visible rather than hidden.
    email_send_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_email_error: Mapped[str | None] = mapped_column(Text)

    fully_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped["Tenant"] = relationship("Tenant")
    supplier: Mapped["Supplier"] = relationship("Supplier")
    location: Mapped["Location"] = relationship("Location")
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by])
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        "PurchaseOrderItem",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
    )
    receipts: Mapped[list["GoodsReceipt"]] = relationship(
        "GoodsReceipt",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
    )


class PurchaseOrderItem(BaseMixin, Base):
    """One ingredient line on a purchase order."""

    __tablename__ = "purchase_order_items"
    __table_args__ = (
        UniqueConstraint(
            "purchase_order_id", "ingredient_id", name="uq_po_item_po_ingredient"
        ),
        Index("ix_po_item_po", "purchase_order_id"),
        CheckConstraint("quantity_ordered > 0", name="ck_po_item_qty_positive"),
        CheckConstraint("unit_price_minor >= 0", name="ck_po_item_price_positive"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingredients.id"), nullable=False
    )

    quantity_ordered: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    # Accumulates across several deliveries. Starts at zero rather than null so
    # "how much is still owed" is always `ordered - received` with no null test.
    quantity_received: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=0
    )
    unit: Mapped[str] = mapped_column(String(50), nullable=False)

    # MINOR UNITS per `unit`. See the module docstring; no `* 100` anywhere.
    unit_price_minor: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    line_total_minor: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )

    supplier_sku: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)

    purchase_order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder", back_populates="items"
    )
    ingredient: Mapped["Ingredient"] = relationship("Ingredient")


# ---------------------------------------------------------------------------
# GOODS RECEIPTS
# ---------------------------------------------------------------------------


class GoodsReceipt(BaseMixin, Base):
    """One delivery booked in against a purchase order.

    A separate record rather than just bumping `quantity_received`, because a
    PO received in three deliveries has three real events with three dates, and
    an invoice query six weeks later ("which delivery was the short one?")
    cannot be answered from a single running total.

    This is also where OCR-assisted receiving lands: `source` records whether a
    human typed the quantities or an extracted document proposed them, and
    `document_reference` holds the supplier's own delivery-note number.
    """

    __tablename__ = "goods_receipts"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "receipt_number", name="uq_goods_receipt_tenant_number"
        ),
        Index("ix_goods_receipt_po", "purchase_order_id"),
        CheckConstraint(
            "source IN ('manual', 'ocr')", name="ck_goods_receipt_source"
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    receipt_number: Mapped[str] = mapped_column(String(40), nullable=False)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False
    )

    # 'manual' or 'ocr'. An OCR-proposed receipt is still confirmed by a human
    # before it books stock -- the flag records where the numbers came from,
    # not who is accountable for them.
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    document_reference: Mapped[str | None] = mapped_column(
        String(120)
    )  # The supplier's delivery note / invoice number
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    received_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)

    purchase_order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder", back_populates="receipts"
    )
    lines: Mapped[list["GoodsReceiptLine"]] = relationship(
        "GoodsReceiptLine", back_populates="receipt", cascade="all, delete-orphan"
    )
    receiver: Mapped["User | None"] = relationship("User", foreign_keys=[received_by])


class GoodsReceiptLine(BaseMixin, Base):
    """One ingredient quantity booked in by one receipt."""

    __tablename__ = "goods_receipt_lines"
    __table_args__ = (
        Index("ix_goods_receipt_line_receipt", "receipt_id"),
        CheckConstraint(
            "quantity_received > 0", name="ck_goods_receipt_line_qty_positive"
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("goods_receipts.id", ondelete="CASCADE"), nullable=False
    )
    purchase_order_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("purchase_order_items.id", ondelete="CASCADE"), nullable=False
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingredients.id"), nullable=False
    )

    quantity_received: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    # What was actually charged on this delivery, which is not always what the
    # PO said. MINOR UNITS.
    unit_price_minor: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )

    receipt: Mapped["GoodsReceipt"] = relationship(
        "GoodsReceipt", back_populates="lines"
    )
    ingredient: Mapped["Ingredient"] = relationship("Ingredient")
