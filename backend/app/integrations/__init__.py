"""External integration adapters.

Available adapters:
- FBR (Federal Board of Revenue) -- Pakistan federal tax
- PRA (Punjab Revenue Authority) -- Punjab provincial tax
- Foodpanda -- Delivery platform
- QuickBooks -- Accounting (implemented in app.services.quickbooks)
"""

from app.integrations.base import (
    DeliveryPlatformAdapter,
    IntegrationAdapter,
    TaxIntegrationAdapter,
)
from app.integrations.fbr import FBRAdapter
from app.integrations.foodpanda import FoodpandaAdapter
from app.integrations.pra import PRAAdapter

__all__ = [
    "IntegrationAdapter",
    "TaxIntegrationAdapter",
    "DeliveryPlatformAdapter",
    "FBRAdapter",
    "PRAAdapter",
    "FoodpandaAdapter",
]
