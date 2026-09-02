import uuid

from pydantic import BaseModel


class TenantResponse(BaseModel):
    """Public representation of a tenant / restaurant."""

    id: uuid.UUID
    name: str
    slug: str
    is_active: bool

    model_config = {"from_attributes": True}


class RestaurantConfigResponse(BaseModel):
    """Restaurant configuration for the authenticated tenant."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    restaurant_name: str | None = None
    # The signed-in session's own tenant slug, straight from the tenant record.
    #
    # Added 2026-08-27 because the frontend had no authoritative answer to "which
    # shop am I actually signed in to". It was inferring it from a localStorage
    # value that any URL could overwrite, which is how the switch-account screen
    # ended up showing one tenant's slug inside another tenant's session. A value
    # that comes back with the session cannot be contradicted by a query string.
    tenant_slug: str | None = None
    payment_flow: str
    currency: str
    timezone: str
    tax_inclusive: bool
    default_tax_rate: int
    cash_tax_rate_bps: int = 1600
    card_tax_rate_bps: int = 500
    receipt_header: str | None = None
    receipt_footer: str | None = None
    # 'thermal' (80mm roll) or 'a4'. Presentation only.
    receipt_format: str = "thermal"
    # Display name for the walk-in channel; None means "Takeaway".
    takeaway_label: str | None = None
    discount_approval_threshold_bps: int = 0
    discount_approval_threshold_fixed: int = 0
    online_ordering_only: bool = False
    # Comma-separated UI module slugs to hide from this tenant. Presentation
    # only, never an entitlement -- see the model docstring and OI-93.
    hidden_ui_modules: str = ""
    # Optional per-tenant palette name. None means the standard look.
    theme: str | None = None

    model_config = {"from_attributes": True}
