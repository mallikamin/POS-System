"""Abstract base class for all external integration adapters."""

from abc import ABC, abstractmethod
from typing import Any


class IntegrationAdapter(ABC):
    """Base class for external service integrations.

    All integrations (tax authorities, delivery platforms, accounting)
    must implement this interface for consistent lifecycle management.
    """

    @abstractmethod
    async def connect(self, credentials: dict[str, Any]) -> bool:
        """Establish connection with the external service."""
        ...

    @abstractmethod
    async def disconnect(self) -> bool:
        """Gracefully disconnect from the external service."""
        ...

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Check if the integration is healthy and responsive."""
        ...

    @abstractmethod
    async def get_status(self) -> str:
        """Return current connection status: connected | disconnected | error."""
        ...


class TaxIntegrationAdapter(IntegrationAdapter):
    """Abstract base for tax authority integrations (FBR, PRA)."""

    @abstractmethod
    async def submit_invoice(self, order_data: dict[str, Any]) -> dict[str, Any]:
        """Submit a sales invoice to the tax authority.

        Args:
            order_data: Order details including items, tax amounts, customer info.

        Returns:
            dict with invoice_id, fiscal_number, qr_code_url, status.
        """
        ...

    @abstractmethod
    async def verify_invoice(self, invoice_id: str) -> dict[str, Any]:
        """Verify an invoice's status with the tax authority.

        Args:
            invoice_id: The tax authority's invoice reference.

        Returns:
            dict with status (verified|pending|rejected), details.
        """
        ...

    @abstractmethod
    async def cancel_invoice(self, invoice_id: str, reason: str) -> bool:
        """Request cancellation of a submitted invoice."""
        ...


class DeliveryPlatformAdapter(IntegrationAdapter):
    """Abstract base for delivery platform integrations (Foodpanda, etc)."""

    @abstractmethod
    async def accept_order(self, external_order_id: str) -> dict[str, Any]:
        """Accept an incoming order from the delivery platform."""
        ...

    @abstractmethod
    async def reject_order(self, external_order_id: str, reason: str) -> bool:
        """Reject an incoming order from the delivery platform."""
        ...

    @abstractmethod
    async def update_order_status(self, external_order_id: str, status: str) -> bool:
        """Update order status on the delivery platform."""
        ...

    @abstractmethod
    async def sync_menu(self, menu_items: list[dict[str, Any]]) -> dict[str, Any]:
        """Push menu updates to the delivery platform."""
        ...

    @abstractmethod
    async def get_rider_location(self, order_id: str) -> dict[str, Any] | None:
        """Get real-time rider GPS location for a delivery order."""
        ...
