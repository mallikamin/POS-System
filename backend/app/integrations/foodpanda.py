"""Foodpanda integration stub.

Foodpanda is the dominant food delivery platform in Pakistan.
Integration allows automatic order acceptance, menu sync, and
real-time status updates.

Production implementation will use:
- Foodpanda Partner API (REST)
- Webhook for incoming orders
- Menu management API for availability/pricing
- Order status push API
"""

from typing import Any

from app.integrations.base import DeliveryPlatformAdapter


class FoodpandaAdapter(DeliveryPlatformAdapter):
    """Foodpanda Pakistan delivery platform integration.

    Enables:
    - Auto-accept/reject incoming Foodpanda orders
    - Push order status updates (preparing -> ready -> picked up)
    - Sync menu items, prices, and availability
    - Track rider GPS location for delivery orders
    """

    def __init__(self) -> None:
        self._connected = False
        self._vendor_id: str | None = None

    async def connect(self, credentials: dict[str, Any]) -> bool:
        raise NotImplementedError(
            "Foodpanda integration not yet implemented. "
            "Requires Foodpanda Partner API credentials."
        )

    async def disconnect(self) -> bool:
        raise NotImplementedError("Foodpanda integration not yet implemented.")

    async def health_check(self) -> dict[str, Any]:
        raise NotImplementedError("Foodpanda integration not yet implemented.")

    async def get_status(self) -> str:
        return "disconnected"

    async def accept_order(self, external_order_id: str) -> dict[str, Any]:
        raise NotImplementedError("Foodpanda order acceptance not yet implemented.")

    async def reject_order(self, external_order_id: str, reason: str) -> bool:
        raise NotImplementedError("Foodpanda order rejection not yet implemented.")

    async def update_order_status(self, external_order_id: str, status: str) -> bool:
        raise NotImplementedError("Foodpanda status update not yet implemented.")

    async def sync_menu(self, menu_items: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError("Foodpanda menu sync not yet implemented.")

    async def get_rider_location(self, order_id: str) -> dict[str, Any] | None:
        raise NotImplementedError("Foodpanda rider tracking not yet implemented.")
