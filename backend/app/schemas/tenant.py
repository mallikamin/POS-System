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
    payment_flow: str
    currency: str
    timezone: str
    tax_inclusive: bool
    default_tax_rate: int
    cash_tax_rate_bps: int = 1600
    card_tax_rate_bps: int = 500
    receipt_header: str | None = None
    receipt_footer: str | None = None

    model_config = {"from_attributes": True}
