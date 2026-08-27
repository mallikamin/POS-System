"""Order domain models: orders, items, item modifiers, status log.

All monetary amounts are stored in paisa (1 PKR = 100 paisa) as integers.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import BaseMixin


class Order(BaseMixin, Base):
    """A customer order.

    order_type: dine_in | takeaway | call_center | online
    status: draft | confirmed | in_kitchen | ready | served | completed | voided
    payment_status: unpaid | partial | paid | refunded

    `online` orders come from the public storefront and differ from the rest in
    three ways: nobody is logged in when they are created, the customer chooses
    collection or delivery, and the shop must explicitly accept or reject them
    before the kitchen sees anything. The `accepted_at` / `rejected_at` /
    `eta_minutes` fields below carry that gate.
    """

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "order_number", name="uq_order_tenant_number"),
        # The database, not the application, is what guarantees no two invoices
        # in a tenant ever share a number. NULLs are distinct in Postgres, so
        # unissued orders are unaffected by this.
        UniqueConstraint(
            "tenant_id", "tax_invoice_number", name="uq_order_tenant_tax_invoice_number"
        ),
        Index("ix_orders_tenant_status", "tenant_id", "status"),
        Index("ix_orders_tenant_created", "tenant_id", "created_at"),
        Index("ix_orders_created_by", "created_by"),
        Index("ix_orders_customer_phone", "customer_phone"),
    )

    order_number: Mapped[str] = mapped_column(String(20), nullable=False)
    order_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="dine_in | takeaway | call_center | online",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="draft",
        nullable=False,
        comment="draft | confirmed | in_kitchen | ready | served | completed | voided",
    )
    payment_status: Mapped[str] = mapped_column(
        String(20),
        default="unpaid",
        nullable=False,
        comment="unpaid | partial | paid | refunded",
    )

    table_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("tables.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    table_session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("table_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # WHERE this sale happened. Stock is deducted from this location and never
    # from any other, and revenue reports break down by it. Nullable so that
    # existing single-site tenants (chick-shack, demo-restaurant) are untouched;
    # when it is null the tenant's default location is assumed.
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # HOW the sale arrived, and therefore what commission it carries. Distinct
    # from `order_type`, which is a coarse operational category: two `online`
    # orders can come via Talabat (15%) and direct WhatsApp (0%) and have very
    # different net profit. See SalesChannel.
    sales_channel_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("sales_channels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Commission is SNAPSHOTTED onto the order at completion, not read live from
    # the channel. Rates get renegotiated; last month's profit must not silently
    # change when today's rate does.
    channel_commission_minor: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Channel commission charged on this order, in minor units",
    )

    # Reserved once, on first issue, and never recomputed. Previously the
    # number was derived from a live COUNT of the tenant's orders, so seven
    # different sales all read FZD-00007 and every number moved as new orders
    # arrived (F33). A tax invoice number has to identify one document
    # permanently, so it is stored the moment the document is first produced.
    # NULL means this order has never been issued as a tax invoice.
    tax_invoice_number: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        comment="Immutable tax invoice number, assigned at first issue",
    )

    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Where confirmations for THIS order go. Held on the order rather than only
    # on the linked customer so a later profile edit cannot rewrite history, and
    # because guests without a phone number are never linked to a customer row.
    customer_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    subtotal: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Subtotal in paisa",
    )
    tax_amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Tax in paisa",
    )
    discount_amount: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Discount in paisa",
    )
    total: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Grand total in paisa",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Online ordering -------------------------------------------------
    # All nullable: these are meaningless for dine-in/takeaway/call-center and
    # must stay null there rather than carrying a misleading default.
    service_type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="collection | delivery. Online orders only; null otherwise.",
    )
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_area: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Named delivery area the fee was derived from, e.g. 'Arrochar'",
    )
    delivery_fee: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Delivery fee in minor units. 0 for collection.",
    )
    service_fee: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Service fee in minor units, snapshotted from the tenant's "
        "config at order creation. Charged regardless of service type.",
    )
    tip: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Tip in minor units, chosen by the customer at checkout "
        "(OI-81). Included in `total`; excluded from tax and the delivery "
        "minimum. 0 = no tip.",
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Set when the shop accepts an online order. Kitchen fires on this.",
    )
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    eta_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Lead time promised to the customer on acceptance",
    )
    review_email_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Set when the 'how did we do' review-request email is sent. "
        "This is the CLAIM, not a log: the sweep takes an order by writing "
        "this column with a conditional UPDATE guarded on it still being "
        "NULL, so four uvicorn workers sweeping at once cannot email one "
        "customer twice. Same pattern as payment_authorized_at.",
    )

    # --- Stripe ------------------------------------------------------------
    # The shop charges on ACCEPTANCE, not on placement, so a card payment lives
    # in two steps: authorised at checkout, captured when the shop accepts (or
    # cancelled when it rejects). Both ids are kept because they answer
    # different questions -- the session is what the customer was sent to, the
    # payment intent is what actually holds the money and is the thing we
    # capture or cancel.
    # ⚠️ The customer's INTENT, recorded at creation. Do not infer "is this a
    # card order?" from `stripe_checkout_session_id` -- that field is set by a
    # SECOND request a fraction of a second later, and in the gap between the
    # two a card order is indistinguishable from cash on delivery. That gap is
    # OI-84: the order surfaced on the tablet unpaid, and `accept_order`'s money
    # guard (keyed on the session id) was skipped entirely for it.
    #
    # This is the field every "card or cash?" decision must read.
    intends_card_payment: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
        comment="Customer chose to pay by card at checkout. Set at creation, before Stripe exists.",
    )
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Stripe Checkout Session the customer was sent to, if paying by card",
    )
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="PaymentIntent holding the authorisation. Captured on accept, cancelled on reject.",
    )
    payment_authorized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment=(
            "When the card was authorised. The hold expires roughly 5 days later "
            "on Visa and 7 on Mastercard/Amex, so a pre-order cannot outlive it."
        ),
    )
    payment_captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the authorisation was actually taken, on acceptance",
    )

    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
        nullable=False,
    )
    waiter_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Waiter/server assigned to this order",
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Linked customer record",
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )

    # Relationships
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    status_logs: Mapped[list["OrderStatusLog"]] = relationship(
        "OrderStatusLog",
        back_populates="order",
        lazy="raise",
        cascade="all, delete-orphan",
        order_by="OrderStatusLog.created_at",
    )
    table: Mapped["Table | None"] = relationship("Table", lazy="selectin")
    table_session: Mapped["TableSession | None"] = relationship(
        "TableSession",
        back_populates="orders",
        lazy="selectin",
    )
    creator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
        lazy="selectin",
    )
    waiter: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[waiter_id],
        lazy="selectin",
    )
    customer: Mapped["Customer | None"] = relationship("Customer", lazy="selectin")


class OrderItem(BaseMixin, Base):
    """A line item within an order.

    name and unit_price are denormalized from menu_item for historical accuracy.
    status: pending | sent | preparing | ready | served
    """

    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("menu_items.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Unit price in paisa (base + modifiers)",
    )
    total: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="unit_price * quantity in paisa",
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        comment="pending | sent | preparing | ready | served",
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )

    # Relationships
    order: Mapped[Order] = relationship("Order", back_populates="items")
    menu_item: Mapped["MenuItem | None"] = relationship("MenuItem", lazy="raise")
    modifiers: Mapped[list["OrderItemModifier"]] = relationship(
        "OrderItemModifier",
        back_populates="order_item",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class OrderItemModifier(BaseMixin, Base):
    """A modifier applied to an order item.

    name and price_adjustment are denormalized for historical accuracy.
    """

    __tablename__ = "order_item_modifiers"

    order_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("order_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    modifier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("modifiers.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_adjustment: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Price adjustment in paisa",
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )

    # Relationships
    order_item: Mapped[OrderItem] = relationship(
        "OrderItem", back_populates="modifiers"
    )


class OrderStatusLog(BaseMixin, Base):
    """Audit trail for order status transitions."""

    __tablename__ = "order_status_log"

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Null for initial creation",
    )
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )

    # Relationships
    order: Mapped[Order] = relationship("Order", back_populates="status_logs")


# Avoid circular import issues — use string references above
from app.models.floor import Table  # noqa: E402, F401
from app.models.menu import MenuItem  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
from app.models.table_session import TableSession  # noqa: E402, F401
from app.models.customer import Customer  # noqa: E402, F401
