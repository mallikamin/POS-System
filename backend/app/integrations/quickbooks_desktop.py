"""QuickBooks Desktop integration adapter.

Uses QBWC (QuickBooks Web Connector) SOAP protocol to sync data with
QuickBooks Desktop via QBXML (QB's XML format).

Unlike QB Online (REST API), Desktop integration is asynchronous:
1. POS creates QBXML requests and queues them in qb_sync_queue
2. QBWC polls the POS server every 15 minutes
3. QBWC fetches pending requests, sends them to QB Desktop
4. QB Desktop processes requests and returns responses
5. QBWC sends responses back to POS
6. POS parser extracts TxnID/ListID and updates entity mappings

This adapter implements the IntegrationAdapter interface and provides
methods to create sync jobs for common POS operations.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.base import IntegrationAdapter
from app.models.menu import Category, MenuItem
from app.models.order import Order
from app.models.quickbooks import (
    QBConnection,
    QBEntityMapping,
    QBSyncJob,
    QBAccountMapping,
)
from app.services.quickbooks.qbxml.builders import (
    build_sales_receipt_add_rq,
    build_customer_add_rq,
    build_customer_mod_rq,
    build_item_non_inventory_add_rq,
    build_item_non_inventory_mod_rq,
    build_receive_payment_add_rq,
    build_credit_memo_add_rq,
)

logger = logging.getLogger(__name__)


class QBDesktopAdapter(IntegrationAdapter):
    """QuickBooks Desktop adapter via QBWC/QBXML.

    All operations are asynchronous - they queue QBXML requests for
    QBWC to fetch and send to QB Desktop. Results are processed when
    QBWC sends back the response.
    """

    def __init__(self, connection: QBConnection, db: AsyncSession):
        """Initialize Desktop adapter.

        Args:
            connection: QB Desktop connection record (connection_type='desktop')
            db: SQLAlchemy async session
        """
        if connection.connection_type != "desktop":
            raise ValueError(
                f"QBDesktopAdapter requires connection_type='desktop', got '{connection.connection_type}'"
            )

        self.connection = connection
        self.db = db
        self.tenant_id = connection.tenant_id

        logger.info(
            "Initialized QBDesktopAdapter for tenant %s, company %s",
            self.tenant_id,
            connection.company_name,
        )

    # =========================================================================
    # IntegrationAdapter Interface
    # =========================================================================

    async def connect(self, credentials: dict[str, Any]) -> bool:
        """Establish connection with QB Desktop (via QBWC).

        For Desktop, connection is always "active" as long as QBWC is
        configured and polling. This method validates credentials.

        Args:
            credentials: dict with qbwc_username, qbwc_password

        Returns:
            True if credentials are valid
        """
        # For Desktop, connection is passive - QBWC polls us
        # We just validate that credentials are set
        if not self.connection.qbwc_username:
            raise ValueError("QBWC username not configured")
        if not self.connection.qbwc_password_encrypted:
            raise ValueError("QBWC password not configured")

        logger.info(
            "QB Desktop connection validated for %s", self.connection.company_name
        )
        return True

    async def disconnect(self) -> bool:
        """Disconnect from QB Desktop.

        For Desktop, we just mark the connection as inactive.
        QBWC will stop receiving requests.
        """
        self.connection.is_active = False
        await self.db.commit()

        logger.info(
            "QB Desktop connection deactivated for %s", self.connection.company_name
        )
        return True

    async def health_check(self) -> dict[str, Any]:
        """Check QB Desktop integration health.

        Returns:
            dict with status, last_poll_time, pending_requests
        """
        # Count pending sync jobs
        pending_count_query = select(QBSyncJob.id).where(
            QBSyncJob.tenant_id == self.tenant_id,
            QBSyncJob.connection_id == self.connection.id,
            QBSyncJob.status == "pending",
        )
        pending_result = await self.db.execute(pending_count_query)
        pending_count = len(pending_result.all())

        # Check if QBWC has polled recently (last 30 min)
        last_poll = self.connection.last_qbwc_poll_at
        is_healthy = False
        if last_poll:
            time_since_poll = datetime.now(timezone.utc) - last_poll
            is_healthy = time_since_poll.total_seconds() < 1800  # 30 min

        return {
            "status": "connected" if is_healthy else "disconnected",
            "connection_type": "desktop",
            "company_name": self.connection.company_name,
            "last_poll_at": last_poll.isoformat() if last_poll else None,
            "pending_requests": pending_count,
            "qb_version": self.connection.qb_desktop_version,
        }

    async def get_status(self) -> str:
        """Get connection status.

        Returns:
            'connected' if QBWC polled recently, 'disconnected' otherwise
        """
        health = await self.health_check()
        return health["status"]

    # =========================================================================
    # Sync Operations (Queue QBXML Requests)
    # =========================================================================

    async def create_sales_receipt(
        self,
        order: Order,
        customer_name: str = "Walk-In Customer",
    ) -> dict[str, Any]:
        """Create a sales receipt in QB Desktop for a POS order.

        Args:
            order: POS Order instance
            customer_name: QB customer name (default: "Walk-In Customer")

        Returns:
            dict with sync_job_id, status='queued'
        """
        # Get account mappings
        deposit_account = await self._get_account_mapping("bank", "Cash Drawer")
        income_account = await self._get_account_mapping("income", "Food Sales")
        tax_account = await self._get_account_mapping("tax_payable", "Sales Tax Payable")

        # Build order data dict
        order_data = {
            "order_number": order.order_number,
            "order_type": order.order_type,
            "created_at": order.created_at,
            "items": [],
            "subtotal_paisa": order.subtotal,
            "tax_paisa": order.tax_amount,
            "total_paisa": order.total,
            "notes": order.notes or "",
        }

        # Add order items (need to fetch from relationship)
        # For now, simplified - in production, fetch order_items via selectinload
        # order_data["items"] = [
        #     {
        #         "name": item.name,
        #         "quantity": item.quantity,
        #         "price_paisa": item.price,
        #         "total_paisa": item.total,
        #     }
        #     for item in order.items
        # ]

        # Build QBXML
        qbxml = build_sales_receipt_add_rq(
            order_data=order_data,
            customer_name=customer_name,
            deposit_to_account=deposit_account,
            income_account=income_account,
            tax_account=tax_account if order.tax_amount > 0 else None,
        )

        # Queue sync job
        job = await self._enqueue_job(
            job_type="create_sales_receipt",
            entity_type="order",
            entity_id=order.id,
            request_xml=qbxml,
            priority=5,
        )

        logger.info(
            "Queued sales receipt for order %s (job %s)", order.order_number, job.id
        )

        return {
            "sync_job_id": str(job.id),
            "status": "queued",
            "order_number": order.order_number,
        }

    async def create_customer(
        self,
        customer_data: dict[str, Any],
        is_update: bool = False,
    ) -> dict[str, Any]:
        """Create or update a customer in QB Desktop.

        Args:
            customer_data: dict with name, phone, email, address
            is_update: True to update existing customer (requires qb_list_id)

        Returns:
            dict with sync_job_id, status='queued'
        """
        if is_update:
            # Check for existing mapping to get ListID
            list_id = customer_data.get("qb_list_id")
            if not list_id:
                raise ValueError("qb_list_id required for customer update")

            qbxml = build_customer_mod_rq(
                customer_data=customer_data,
                list_id=list_id,
            )
            job_type = "update_customer"
        else:
            qbxml = build_customer_add_rq(customer_data=customer_data)
            job_type = "create_customer"

        # Queue sync job
        job = await self._enqueue_job(
            job_type=job_type,
            entity_type="customer",
            entity_id=customer_data.get("pos_entity_id"),
            request_xml=qbxml,
            priority=7,
        )

        logger.info("Queued customer %s (job %s)", job_type, job.id)

        return {
            "sync_job_id": str(job.id),
            "status": "queued",
            "customer_name": customer_data.get("name"),
        }

    async def create_item(
        self,
        item_data: dict[str, Any],
        is_update: bool = False,
    ) -> dict[str, Any]:
        """Create or update a menu item in QB Desktop.

        Args:
            item_data: dict with name, description, price_paisa, income_account
            is_update: True to update existing item (requires qb_list_id)

        Returns:
            dict with sync_job_id, status='queued'
        """
        if is_update:
            list_id = item_data.get("qb_list_id")
            if not list_id:
                raise ValueError("qb_list_id required for item update")

            qbxml = build_item_non_inventory_mod_rq(
                item_data=item_data,
                list_id=list_id,
            )
            job_type = "update_item"
        else:
            qbxml = build_item_non_inventory_add_rq(item_data=item_data)
            job_type = "create_item"

        # Queue sync job
        job = await self._enqueue_job(
            job_type=job_type,
            entity_type="menu_item",
            entity_id=item_data.get("pos_entity_id"),
            request_xml=qbxml,
            priority=8,
        )

        logger.info("Queued item %s (job %s)", job_type, job.id)

        return {
            "sync_job_id": str(job.id),
            "status": "queued",
            "item_name": item_data.get("name"),
        }

    async def create_payment(
        self,
        payment_data: dict[str, Any],
        customer_name: str,
        payment_method_name: str = "Cash",
    ) -> dict[str, Any]:
        """Create a payment receipt in QB Desktop.

        Args:
            payment_data: dict with reference, amount, processed_at, note
            customer_name: QB customer name
            payment_method_name: QB payment method

        Returns:
            dict with sync_job_id, status='queued'
        """
        deposit_account = await self._get_account_mapping("bank", "Cash Drawer")

        qbxml = build_receive_payment_add_rq(
            payment_data=payment_data,
            customer_name=customer_name,
            payment_method_name=payment_method_name,
            deposit_to_account=deposit_account,
        )

        job = await self._enqueue_job(
            job_type="create_payment",
            entity_type="payment",
            entity_id=payment_data.get("pos_entity_id"),
            request_xml=qbxml,
            priority=5,
        )

        logger.info("Queued payment (job %s)", job.id)

        return {
            "sync_job_id": str(job.id),
            "status": "queued",
            "payment_reference": payment_data.get("reference"),
        }

    async def create_refund(
        self,
        refund_data: dict[str, Any],
        customer_name: str = "Walk-In Customer",
    ) -> dict[str, Any]:
        """Create a credit memo (refund) in QB Desktop.

        Args:
            refund_data: dict with order_number, items, amounts, reason
            customer_name: QB customer name

        Returns:
            dict with sync_job_id, status='queued'
        """
        income_account = await self._get_account_mapping("income", "Food Sales")
        tax_account = await self._get_account_mapping("tax_payable", "Sales Tax Payable")

        qbxml = build_credit_memo_add_rq(
            refund_data=refund_data,
            customer_name=customer_name,
            income_account=income_account,
            tax_account=tax_account if refund_data.get("tax_paisa", 0) > 0 else None,
        )

        job = await self._enqueue_job(
            job_type="create_refund",
            entity_type="order_refund",
            entity_id=refund_data.get("pos_entity_id"),
            request_xml=qbxml,
            priority=5,
        )

        logger.info("Queued refund (job %s)", job.id)

        return {
            "sync_job_id": str(job.id),
            "status": "queued",
            "order_number": refund_data.get("order_number"),
        }

    async def fetch_chart_of_accounts(self) -> dict[str, Any]:
        """Request Chart of Accounts from QB Desktop.

        Returns:
            dict with sync_job_id, status='queued'

        Note:
            Actual COA data will be available after QBWC processes this request
            and returns the response. Check job status or listen for completion.
        """
        # Build QBXML query for all accounts
        qbxml = """<?xml version="1.0" encoding="UTF-8"?>
<QBXML>
  <!-- Generated by Sitara POS - Fetch Chart of Accounts -->
  <QBXMLMsgsRq onError="stopOnError">
    <AccountQueryRq requestID="1">
      <!-- Fetch all accounts -->
    </AccountQueryRq>
  </QBXMLMsgsRq>
</QBXML>"""

        job = await self._enqueue_job(
            job_type="fetch_chart_of_accounts",
            entity_type="chart_of_accounts",
            entity_id=None,
            request_xml=qbxml,
            priority=10,
        )

        logger.info("Queued COA fetch (job %s)", job.id)

        return {
            "sync_job_id": str(job.id),
            "status": "queued",
        }

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _enqueue_job(
        self,
        job_type: str,
        entity_type: str,
        request_xml: str,
        entity_id: uuid.UUID | None = None,
        priority: int = 5,
    ) -> QBSyncJob:
        """Add a QBXML request to the sync queue.

        Args:
            job_type: Job type (create_sales_receipt, etc.)
            entity_type: Entity type (order, customer, etc.)
            request_xml: QBXML request string
            entity_id: POS entity ID (optional)
            priority: Job priority (0=critical, 5=normal, 10=bulk)

        Returns:
            Created QBSyncJob instance
        """
        # Generate idempotency key
        idempotency_key = None
        if entity_id:
            idempotency_key = f"{job_type}:{entity_type}:{entity_id}"

        # Check for duplicate
        if idempotency_key:
            existing = await self.db.execute(
                select(QBSyncJob.id).where(
                    QBSyncJob.tenant_id == self.tenant_id,
                    QBSyncJob.idempotency_key == idempotency_key,
                    QBSyncJob.status.in_(["pending", "processing"]),
                )
            )
            if existing.scalar_one_or_none():
                logger.warning(
                    "Duplicate sync job skipped: %s", idempotency_key
                )
                raise ValueError(f"Sync job already queued: {idempotency_key}")

        # Create job
        job = QBSyncJob(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            connection_id=self.connection.id,
            job_type=job_type,
            entity_type=entity_type,
            entity_id=entity_id,
            priority=priority,
            status="pending",
            request_xml=request_xml,
            idempotency_key=idempotency_key,
        )

        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        return job

    async def _get_account_mapping(
        self, mapping_type: str, default_name: str
    ) -> str:
        """Get QB account name from mapping, or return default.

        Args:
            mapping_type: Mapping type (income, bank, tax_payable, etc.)
            default_name: Default account name if no mapping exists

        Returns:
            QB account name
        """
        result = await self.db.execute(
            select(QBAccountMapping.qb_account_name).where(
                QBAccountMapping.tenant_id == self.tenant_id,
                QBAccountMapping.connection_id == self.connection.id,
                QBAccountMapping.mapping_type == mapping_type,
            )
        )
        mapping = result.scalar_one_or_none()

        return mapping if mapping else default_name
