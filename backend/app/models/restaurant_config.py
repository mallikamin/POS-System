import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import BaseMixin


class RestaurantConfig(BaseMixin, Base):
    """Per-tenant restaurant configuration (one-to-one with Tenant).

    Monetary precision note:
        default_tax_rate is stored in basis points (1/100 of a percent).
        For example, 16.00% is stored as 1600.
    """

    __tablename__ = "restaurant_configs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    payment_flow: Mapped[str] = mapped_column(
        String(50), default="order_first", nullable=False
    )
    currency: Mapped[str] = mapped_column(String(10), default="PKR", nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(50), default="Asia/Karachi", nullable=False
    )
    tax_inclusive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_tax_rate: Mapped[int] = mapped_column(
        Integer,
        default=1600,
        nullable=False,
        comment="Tax rate in basis points (1600 = 16.00%)",
    )
    cash_tax_rate_bps: Mapped[int] = mapped_column(
        Integer,
        default=1600,
        nullable=False,
        comment="Tax rate for cash payments in basis points (1600 = 16%)",
    )
    card_tax_rate_bps: Mapped[int] = mapped_column(
        Integer,
        default=500,
        nullable=False,
        comment="Tax rate for card payments in basis points (500 = 5%)",
    )
    receipt_header: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    receipt_footer: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Martin (FZ LLC, 2026-09-02): "option to either print a vertical receipt
    # or an A4 format". `thermal` is the 80mm roll every tenant printed on
    # before this existed; `a4` lays the same receipt out on a full page.
    # Presentation only: the receipt data is identical either way.
    receipt_format: Mapped[str] = mapped_column(
        String(10), nullable=False, default="thermal", server_default="thermal"
    )
    # Display name for the walk-in channel. The order_type stays `takeaway`
    # (reports, kitchen tickets and the state machine key on it); only the tile
    # and the header badge read differently. NULL means "Takeaway".
    takeaway_label: Mapped[str | None] = mapped_column(String(40), nullable=True)

    delivery_minimum: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Minimum basket for delivery in minor units. 0 = no minimum.",
    )

    service_fee: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Flat service fee in minor units, added to every online "
        "order regardless of payment method. 0 = disabled.",
    )

    online_ordering_paused: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="When true the storefront stops taking online orders "
        "(collection and delivery both) and tells customers to phone the shop. "
        "Enforced server-side in create_public_order, not just in the UI.",
    )

    google_review_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="This tenant's Google 'write a review' link. A review link "
        "belongs to one restaurant's Business Profile, so it is per-tenant and "
        "never hardcoded in the email service. NULL switches the "
        "review-request email off for this tenant, which is how the feature "
        "ships inert.",
    )

    online_ordering_only: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True for a shop that takes orders ONLY from its website "
        "(e.g. Chick Shack): the POS lands on the online-orders queue and "
        "hides the dine-in/takeaway/call-center channels. Per-tenant on "
        "purpose — the core POS keeps all channels for everyone else.",
    )

    # Discount approval thresholds — if either is exceeded, manager verify required
    discount_approval_threshold_bps: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Percent threshold in basis points (0 = disabled). "
        "E.g. 1500 means discounts > 15% need manager approval.",
    )
    discount_approval_threshold_fixed: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Fixed amount threshold in paisa (0 = disabled). "
        "E.g. 50000 means discounts > Rs 500 need manager approval.",
    )

    # Relationships
    # Comma-separated UI module slugs this tenant should NOT be shown, e.g.
    # "dine-in,quickbooks-online,quickbooks-desktop".
    #
    # ⚠️ **PRESENTATION ONLY. This is NOT an entitlement or a security boundary,
    # and must never be described as one.** It hides navigation entries and
    # dashboard cards so a client is not shown modules they do not use. The
    # endpoints behind them remain reachable, because every admin route in this
    # system is gated by ROLE and nothing else. The real per-tenant module gate
    # is OI-93 and it does not exist yet. Hiding a nav item is a filter; a filter
    # is not an invariant.
    #
    # Empty means hide nothing, which is exactly today's behaviour for every
    # existing tenant. That is deliberate: adding this column changes nothing for
    # anybody until a slug is written into it, so Chick Shack's screens are
    # untouched by its existence.
    hidden_ui_modules: Mapped[str] = mapped_column(
        String(500), nullable=False, default="", server_default=""
    )

    # Optional visual identity for this tenant, e.g. "desert-salt".
    #
    # NULL for every existing tenant, and NULL is the whole safety argument: the
    # frontend stamps no attribute, the `:root` defaults in index.css apply, and
    # the screens render exactly as they did before theming existed. A tenant is
    # restyled only by writing a name into this column, so Chick Shack cannot be
    # affected by the feature's existence -- only by someone deliberately
    # setting its theme, which nothing does.
    #
    # Presentation only. It must never gate behaviour or entitlements; an
    # unrecognised value falls back to the standard look rather than erroring.
    theme: Mapped[str | None] = mapped_column(
        String(40), nullable=True, default=None
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="config")


# Import for relationship resolution
from app.models.tenant import Tenant  # noqa: E402, F401
