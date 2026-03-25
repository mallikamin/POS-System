"""QuickBooks adapter factory.

Auto-detects connection type (Online vs Desktop) and returns the
appropriate adapter instance.

This allows the sync service and API endpoints to work with either
QB Online or QB Desktop without knowing which one is connected.
"""

import logging
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quickbooks import QBConnection
from app.integrations.base import IntegrationAdapter
from app.integrations.quickbooks_desktop import QBDesktopAdapter

logger = logging.getLogger(__name__)


async def get_qb_adapter(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID | None = None,
) -> IntegrationAdapter:
    """Get the appropriate QB adapter (Online or Desktop) for a tenant.

    Args:
        db: SQLAlchemy async session
        tenant_id: Tenant ID
        connection_id: Optional specific connection ID. If not provided,
                      uses the tenant's active connection.

    Returns:
        QBOnlineAdapter or QBDesktopAdapter instance

    Raises:
        ValueError: If no active QB connection found for tenant
    """
    # Fetch connection
    if connection_id:
        # Specific connection requested
        result = await db.execute(
            select(QBConnection).where(
                QBConnection.id == connection_id,
                QBConnection.tenant_id == tenant_id,
            )
        )
        connection = result.scalar_one_or_none()
        if not connection:
            raise ValueError(
                f"QB connection {connection_id} not found for tenant {tenant_id}"
            )
    else:
        # Use active connection for tenant
        result = await db.execute(
            select(QBConnection).where(
                QBConnection.tenant_id == tenant_id,
                QBConnection.is_active == True,
            )
        )
        connection = result.scalar_one_or_none()
        if not connection:
            raise ValueError(
                f"No active QB connection found for tenant {tenant_id}"
            )

    # Return appropriate adapter based on connection type
    if connection.connection_type == "desktop":
        logger.info(
            "Using QB Desktop adapter for tenant %s (company: %s)",
            tenant_id,
            connection.company_name,
        )
        return QBDesktopAdapter(connection, db)
    elif connection.connection_type == "online":
        # Import here to avoid circular dependency
        # NOTE: QBOnlineAdapter not yet refactored to use IntegrationAdapter interface
        # For now, we'll raise an error. In production, this should instantiate QBOnlineAdapter.
        logger.info(
            "Using QB Online adapter for tenant %s (company: %s)",
            tenant_id,
            connection.company_name,
        )
        # from app.integrations.quickbooks_online import QBOnlineAdapter
        # return QBOnlineAdapter(connection, db)
        raise NotImplementedError(
            "QB Online adapter not yet refactored to use IntegrationAdapter interface. "
            "Use the existing sync service for Online connections."
        )
    else:
        raise ValueError(
            f"Unknown connection type: {connection.connection_type}. "
            "Expected 'online' or 'desktop'."
        )


async def get_qb_connection(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID | None = None,
) -> QBConnection:
    """Get QB connection record for a tenant.

    Args:
        db: SQLAlchemy async session
        tenant_id: Tenant ID
        connection_id: Optional specific connection ID

    Returns:
        QBConnection instance

    Raises:
        ValueError: If no active QB connection found
    """
    if connection_id:
        result = await db.execute(
            select(QBConnection).where(
                QBConnection.id == connection_id,
                QBConnection.tenant_id == tenant_id,
            )
        )
    else:
        result = await db.execute(
            select(QBConnection).where(
                QBConnection.tenant_id == tenant_id,
                QBConnection.is_active == True,
            )
        )

    connection = result.scalar_one_or_none()
    if not connection:
        raise ValueError(
            f"No {'specified' if connection_id else 'active'} QB connection found for tenant {tenant_id}"
        )

    return connection
