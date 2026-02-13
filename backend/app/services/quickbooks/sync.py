"""QuickBooks sync orchestrator.

Converts POS entities to QuickBooks Online entities, manages the sync job
queue, and provides an audit trail for every API interaction.

All monetary amounts in the POS are stored as integer paisa (1 PKR = 100
paisa).  QuickBooks expects decimal strings, so every outbound amount goes
through ``paisa_to_decimal``.
"""

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import Date, and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.menu import Category, MenuItem
from app.models.order import Order, OrderItem, OrderItemModifier
from app.models.quickbooks import (
    QBAccountMapping,
    QBConnection,
    QBEntityMapping,
    QBSyncJob,
    QBSyncLog,
)
from app.services.quickbooks.client import QBClient, QBAPIError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Currency helpers
# ---------------------------------------------------------------------------

def paisa_to_decimal(paisa: int) -> str:
    """Convert paisa (integer) to a decimal string for QB.

    >>> paisa_to_decimal(15000)
    '150.00'
    >>> paisa_to_decimal(0)
    '0.00'
    >>> paisa_to_decimal(99)
    '0.99'
    """
    d = Decimal(paisa) / Decimal(100)
    return str(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ORDER_TYPE_LABELS: dict[str, str] = {
    "dine_in": "Dine-In",
    "takeaway": "Takeaway",
    "call_center": "Call Center",
}

_WALKIN_CUSTOMER_NAME = "Walk-In Customer"

# Pakistan tax identifiers
_FBR_GST_RATE = "17"  # percent
_PRA_PST_RATE = "16"  # percent

# Default payment methods to sync
_PAYMENT_METHODS = [
    "Cash",
    "Credit Card",
    "Debit Card",
    "JazzCash",
    "Easypaisa",
    "Foodpanda",
]

# Chart of Accounts template for Pakistani restaurants
_COA_TEMPLATE: list[dict] = [
    # Income
    {"name": "Food Sales", "type": "Income", "sub": "SalesOfProductIncome"},
    {"name": "Beverage Sales", "type": "Income", "sub": "SalesOfProductIncome"},
    {"name": "Delivery Revenue", "type": "Income", "sub": "ServiceFeeIncome"},
    {"name": "Tips Income", "type": "Income", "sub": "OtherPrimaryIncome"},
    # COGS
    {"name": "Cost of Food", "type": "Cost of Goods Sold", "sub": "SuppliesMaterialsCogs"},
    {"name": "Cost of Beverages", "type": "Cost of Goods Sold", "sub": "SuppliesMaterialsCogs"},
    # Expenses
    {"name": "Kitchen Supplies", "type": "Expense", "sub": "SuppliesMaterials"},
    {"name": "Packaging & Disposables", "type": "Expense", "sub": "SuppliesMaterials"},
    {"name": "Delivery Expense", "type": "Expense", "sub": "Travel"},
    {"name": "Foodpanda Commission", "type": "Expense", "sub": "CommissionsAndFees"},
    # Liability
    {"name": "FBR GST Payable", "type": "Other Current Liability", "sub": "GlobalTaxPayable"},
    {"name": "PRA PST Payable", "type": "Other Current Liability", "sub": "GlobalTaxPayable"},
    # Bank / Cash
    {"name": "Cash Drawer", "type": "Bank", "sub": "CashOnHand"},
    {"name": "Business Bank Account", "type": "Bank", "sub": "Checking"},
]


class SyncService:
    """Orchestrates POS -> QuickBooks data synchronisation."""

    def __init__(self, connection: QBConnection, db: AsyncSession):
        self.connection = connection
        self.db = db
        self.tenant_id = connection.tenant_id
        self.client = QBClient(connection, db)

    # =====================================================================
    # Sync Job Queue
    # =====================================================================

    async def enqueue_job(
        self,
        job_type: str,
        entity_type: str,
        entity_id: uuid.UUID | None = None,
        priority: int = 5,
        payload: dict | None = None,
    ) -> QBSyncJob | None:
        """Add a sync job to the persistent queue. Returns None if already queued."""
        idempotency_key: str | None = None
        if entity_id:
            idempotency_key = f"{job_type}:{entity_type}:{entity_id}"

        # Check for existing job with same idempotency key to avoid IntegrityError
        if idempotency_key:
            existing = await self.db.execute(
                select(QBSyncJob.id).where(
                    QBSyncJob.tenant_id == self.tenant_id,
                    QBSyncJob.idempotency_key == idempotency_key,
                )
            )
            if existing.scalar_one_or_none() is not None:
                logger.info(
                    "Skipped duplicate QB sync job type=%s entity=%s/%s (already queued)",
                    job_type, entity_type, entity_id,
                )
                return None

        job = QBSyncJob(
            tenant_id=self.tenant_id,
            connection_id=self.connection.id,
            job_type=job_type,
            entity_type=entity_type,
            entity_id=entity_id,
            priority=priority,
            status="pending",
            payload=payload,
            idempotency_key=idempotency_key,
            retry_count=0,
            max_retries=3,
        )
        self.db.add(job)
        await self.db.flush()
        logger.info(
            "Enqueued QB sync job %s  type=%s entity=%s/%s",
            job.id, job_type, entity_type, entity_id,
        )
        return job

    async def process_job(self, job: QBSyncJob) -> bool:
        """Process a single sync job.  Returns True on success."""
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        await self.db.flush()

        t0 = time.monotonic()
        try:
            result = await self._dispatch_job(job)
            elapsed = int((time.monotonic() - t0) * 1000)

            job.status = "completed"
            job.result = result
            job.completed_at = datetime.now(timezone.utc)
            job.processing_duration_ms = elapsed
            await self.db.flush()
            logger.info("Job %s completed in %d ms", job.id, elapsed)
            return True

        except QBAPIError as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            return await self._handle_job_failure(job, exc, elapsed)
        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            return await self._handle_job_failure(job, exc, elapsed)

    async def _handle_job_failure(
        self, job: QBSyncJob, exc: Exception, elapsed_ms: int,
    ) -> bool:
        job.retry_count += 1
        job.error_message = str(exc)[:2000]
        job.processing_duration_ms = elapsed_ms
        if isinstance(exc, QBAPIError):
            # error_detail is a JSON column (dict), not a string
            job.error_detail = {
                "detail": exc.detail,
                "qb_error_code": exc.qb_error_code,
                "status_code": exc.status_code,
            } if hasattr(exc, "detail") else None

        if job.retry_count >= job.max_retries:
            job.status = "dead_letter"
            logger.error(
                "Job %s exhausted retries (%d).  Moved to dead_letter: %s",
                job.id, job.max_retries, exc,
            )
        else:
            backoff_secs = (2 ** job.retry_count) * 30  # 60s, 120s, 240s ...
            job.status = "failed"
            job.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_secs)
            logger.warning(
                "Job %s failed (attempt %d/%d), retry in %ds: %s",
                job.id, job.retry_count, job.max_retries, backoff_secs, exc,
            )

        await self.db.flush()
        return False

    async def _dispatch_job(self, job: QBSyncJob) -> dict | None:
        """Route a job to its handler based on job_type."""
        jt = job.job_type

        # Transaction syncs
        if jt == "create_sales_receipt":
            # Use on_order_completed which pre-syncs items + tax codes
            await self.on_order_completed(job.entity_id)
            return {"status": "completed_via_orchestrator"}
        if jt == "create_invoice":
            order = await self._load_order(job.entity_id)
            return await self.sync_order_as_invoice(order)
        if jt == "create_credit_memo":
            order = await self._load_order(job.entity_id)
            return await self.sync_void_as_credit_memo(order)
        if jt == "create_refund_receipt":
            order = await self._load_order(job.entity_id)
            amount = (job.payload or {}).get("refund_amount_paisa", order.total)
            return await self.sync_refund(order, amount)
        if jt == "create_payment":
            order = await self._load_order(job.entity_id)
            p = job.payload or {}
            return await self.sync_payment_received(
                order,
                p.get("amount_paisa", order.total),
                p.get("payment_method", "Cash"),
                p["invoice_qb_id"],
            )
        if jt == "daily_summary":
            date = datetime.fromisoformat(job.payload["date"]) if job.payload else datetime.now(timezone.utc)
            return await self.create_daily_summary(date)
        if jt == "daily_deposit":
            p = job.payload or {}
            date = datetime.fromisoformat(p["date"]) if "date" in p else datetime.now(timezone.utc)
            return await self.create_daily_deposit(
                date, p.get("cash_amount_paisa", 0), p.get("card_amount_paisa", 0),
            )
        if jt == "create_estimate":
            order = await self._load_order(job.entity_id)
            return await self.sync_estimate(order)
        if jt == "create_bill":
            p = job.payload or {}
            return await self.sync_bill(
                p["vendor_name"], p["amount_paisa"], p.get("line_items", []), p.get("memo"),
            )
        if jt == "create_bill_payment":
            p = job.payload or {}
            return await self.sync_bill_payment(
                p["bill_qb_id"], p["amount_paisa"], p["payment_account_id"],
            )
        if jt == "create_purchase_order":
            p = job.payload or {}
            return await self.sync_purchase_order(
                p["vendor_name"], p.get("line_items", []), p.get("memo"),
            )
        if jt == "create_transfer":
            p = job.payload or {}
            return await self.sync_transfer(
                p["from_account_id"], p["to_account_id"], p["amount_paisa"], p.get("memo"),
            )
        if jt == "create_vendor_credit":
            p = job.payload or {}
            return await self.sync_vendor_credit(
                p["vendor_name"], p["amount_paisa"], p.get("line_items", []),
            )

        # Entity syncs
        if jt == "sync_menu_item":
            return await self.sync_menu_item(job.entity_id)  # type: ignore[arg-type]
        if jt == "sync_category":
            return await self.sync_category(job.entity_id)  # type: ignore[arg-type]
        if jt == "sync_customer":
            p = job.payload or {}
            qb_id = await self.sync_customer(p["name"], p.get("phone"), job.entity_id)
            return {"qb_customer_id": qb_id}
        if jt == "sync_tax_codes":
            return {"tax_codes": await self.sync_tax_codes()}
        if jt == "setup_tax_codes":
            return await self.setup_tax_code_mapping()
        if jt == "sync_tax_agencies":
            return {"agencies": await self.sync_tax_agencies()}
        if jt == "sync_payment_methods":
            return {"methods": await self.sync_payment_methods()}
        if jt == "sync_chart_of_accounts":
            return {"accounts": await self.sync_chart_of_accounts()}
        if jt == "sync_vendor":
            p = job.payload or {}
            qb_id = await self.sync_vendor(p["name"], job.entity_id, p.get("phone"))
            return {"qb_vendor_id": qb_id}
        if jt == "sync_class":
            p = job.payload or {}
            qb_id = await self.sync_class(p["name"], job.entity_id)
            return {"qb_class_id": qb_id}
        if jt == "sync_department":
            p = job.payload or {}
            qb_id = await self.sync_department(p["name"], job.entity_id)
            return {"qb_department_id": qb_id}
        if jt == "sync_employee":
            p = job.payload or {}
            qb_id = await self.sync_employee(p["name"], job.entity_id)
            return {"qb_employee_id": qb_id}
        if jt == "full_sync":
            return await self.run_full_sync(job.entity_id)

        raise ValueError(f"Unknown job_type: {jt}")

    async def process_pending_jobs(self, batch_size: int = 10) -> int:
        """Process pending jobs in priority order.  Returns count processed."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(QBSyncJob)
            .where(
                QBSyncJob.tenant_id == self.tenant_id,
                QBSyncJob.connection_id == self.connection.id,
                QBSyncJob.status.in_(["pending", "failed"]),
                # For failed jobs, only pick up if next_retry_at has passed
                (
                    (QBSyncJob.status == "pending")
                    | (
                        (QBSyncJob.status == "failed")
                        & (QBSyncJob.next_retry_at <= now)
                    )
                ),
            )
            .order_by(QBSyncJob.priority, QBSyncJob.created_at)
            .limit(batch_size)
        )
        result = await self.db.execute(stmt)
        jobs = list(result.scalars().all())

        processed = 0
        for job in jobs:
            await self.process_job(job)
            processed += 1

        return processed

    # =====================================================================
    # Audit Logging
    # =====================================================================

    async def _log_sync(
        self,
        sync_type: str,
        action: str,
        status: str,
        *,
        pos_entity_type: str | None = None,
        pos_entity_id: uuid.UUID | None = None,
        qb_entity_type: str | None = None,
        qb_entity_id: str | None = None,
        request_payload: dict | None = None,
        response_payload: dict | None = None,
        error_message: str | None = None,
        error_code: str | None = None,
        duration_ms: int | None = None,
        qb_doc_number: str | None = None,
        amount_paisa: int | None = None,
        batch_id: uuid.UUID | None = None,
        http_method: str | None = None,
        http_url: str | None = None,
        response_status_code: int | None = None,
    ) -> QBSyncLog:
        """Create an immutable audit log entry for a sync operation."""
        log = QBSyncLog(
            tenant_id=self.tenant_id,
            connection_id=self.connection.id,
            sync_type=sync_type,
            action=action,
            status=status,
            pos_entity_type=pos_entity_type,
            pos_entity_id=pos_entity_id,
            qb_entity_type=qb_entity_type,
            qb_entity_id=qb_entity_id,
            request_payload=request_payload,
            response_payload=response_payload,
            error_message=error_message[:2000] if error_message else None,
            error_code=error_code,
            duration_ms=duration_ms,
            qb_doc_number=qb_doc_number,
            amount_paisa=amount_paisa,
            batch_id=batch_id,
            http_method=http_method,
            http_url=http_url,
            response_status_code=response_status_code,
        )
        self.db.add(log)
        await self.db.flush()
        return log

    # =====================================================================
    # Entity Mapping Helpers
    # =====================================================================

    async def _get_entity_mapping(
        self, entity_type: str, pos_entity_id: uuid.UUID,
    ) -> QBEntityMapping | None:
        """Look up an existing POS <-> QB entity mapping."""
        result = await self.db.execute(
            select(QBEntityMapping).where(
                QBEntityMapping.tenant_id == self.tenant_id,
                QBEntityMapping.connection_id == self.connection.id,
                QBEntityMapping.entity_type == entity_type,
                QBEntityMapping.pos_entity_id == pos_entity_id,
            )
        )
        return result.scalar_one_or_none()

    async def _save_entity_mapping(
        self,
        entity_type: str,
        pos_entity_id: uuid.UUID,
        pos_entity_name: str,
        qb_entity_id: str,
        qb_entity_type: str,
        qb_entity_name: str,
        qb_entity_ref: dict | None = None,
    ) -> QBEntityMapping:
        """Create or update a POS <-> QB entity mapping."""
        existing = await self._get_entity_mapping(entity_type, pos_entity_id)
        now = datetime.now(timezone.utc)
        if existing:
            existing.qb_entity_id = qb_entity_id
            existing.qb_entity_type = qb_entity_type
            existing.qb_entity_name = qb_entity_name
            existing.qb_entity_ref = qb_entity_ref
            existing.last_synced_at = now
            await self.db.flush()
            return existing

        mapping = QBEntityMapping(
            tenant_id=self.tenant_id,
            connection_id=self.connection.id,
            entity_type=entity_type,
            pos_entity_id=pos_entity_id,
            pos_entity_name=pos_entity_name,
            qb_entity_id=qb_entity_id,
            qb_entity_type=qb_entity_type,
            qb_entity_name=qb_entity_name,
            qb_entity_ref=qb_entity_ref,
            sync_direction="pos_to_qb",
            last_synced_at=now,
        )
        self.db.add(mapping)
        await self.db.flush()
        return mapping

    # =====================================================================
    # Account Mapping Helpers
    # =====================================================================

    async def _get_account_mapping(
        self,
        mapping_type: str,
        pos_reference_id: uuid.UUID | None = None,
    ) -> QBAccountMapping | None:
        """Get account mapping.  Tries specific (with pos_reference_id) first,
        then falls back to the default for that mapping_type."""
        if pos_reference_id:
            result = await self.db.execute(
                select(QBAccountMapping).where(
                    QBAccountMapping.tenant_id == self.tenant_id,
                    QBAccountMapping.connection_id == self.connection.id,
                    QBAccountMapping.mapping_type == mapping_type,
                    QBAccountMapping.pos_reference_id == pos_reference_id,
                )
            )
            specific = result.scalar_one_or_none()
            if specific:
                return specific

        # Fall back to default
        result = await self.db.execute(
            select(QBAccountMapping).where(
                QBAccountMapping.tenant_id == self.tenant_id,
                QBAccountMapping.connection_id == self.connection.id,
                QBAccountMapping.mapping_type == mapping_type,
                QBAccountMapping.is_default == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    # =====================================================================
    # Internal data loaders
    # =====================================================================

    async def _load_order(self, order_id: uuid.UUID | None) -> Order:
        """Fetch an order with items + modifiers eagerly loaded."""
        if order_id is None:
            raise ValueError("order_id is required")
        result = await self.db.execute(
            select(Order)
            .options(
                selectinload(Order.items).selectinload(OrderItem.modifiers),
                selectinload(Order.items).selectinload(OrderItem.menu_item),
                selectinload(Order.table),
                selectinload(Order.creator),
            )
            .where(Order.id == order_id, Order.tenant_id == self.tenant_id)
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise ValueError(f"Order {order_id} not found for tenant {self.tenant_id}")
        return order

    # =====================================================================
    # Line-item builder (shared by Sales Receipt, Invoice, Estimate, etc.)
    # =====================================================================

    async def _build_line_items(self, order: Order) -> list[dict]:
        """Convert POS OrderItems to QB SalesItemLineDetail line items."""
        lines: list[dict] = []
        line_num = 1

        # Resolve tax code refs once (shared by all line items)
        tax_code_ref = await self._get_default_tax_code_ref()
        non_tax_ref = await self._get_non_taxable_code_ref()

        for item in order.items:
            # Resolve QB item ref via entity mapping
            item_mapping = await self._get_entity_mapping("menu_item", item.menu_item_id)
            item_ref: dict | None = None
            if item_mapping:
                item_ref = {
                    "value": item_mapping.qb_entity_id,
                    "name": item_mapping.qb_entity_name,
                }

            # Build description including modifiers
            description = item.name
            if item.modifiers:
                mod_names = [m.name for m in item.modifiers]
                description += f" ({', '.join(mod_names)})"
            if item.notes:
                description += f" -- {item.notes}"

            line: dict = {
                "Id": str(line_num),
                "LineNum": line_num,
                "Amount": paisa_to_decimal(item.total),
                "Description": description,
                "DetailType": "SalesItemLineDetail",
                "SalesItemLineDetail": {
                    "Qty": item.quantity,
                    "UnitPrice": paisa_to_decimal(item.unit_price),
                },
            }

            if item_ref:
                line["SalesItemLineDetail"]["ItemRef"] = item_ref

            # Resolve income account for this item's category
            category_id = getattr(item.menu_item, "category_id", None) if item.menu_item else None
            income_mapping = await self._get_account_mapping("income", category_id)
            if income_mapping:
                line["SalesItemLineDetail"]["ItemAccountRef"] = {
                    "value": income_mapping.qb_account_id,
                    "name": income_mapping.qb_account_name,
                }

            # Add tax code ref so QB calculates tax on this line
            if tax_code_ref:
                line["SalesItemLineDetail"]["TaxCodeRef"] = tax_code_ref

            lines.append(line)
            line_num += 1

        # Discount line (if any)
        if order.discount_amount and order.discount_amount > 0:
            discount_line: dict = {
                "Id": str(line_num),
                "LineNum": line_num,
                "Amount": paisa_to_decimal(order.discount_amount),
                "DetailType": "DiscountLineDetail",
                "DiscountLineDetail": {
                    "PercentBased": False,
                    "DiscountPercent": 0,
                },
            }
            lines.append(discount_line)

        return lines

    def _build_tax_detail(self, order: Order) -> dict:
        """Build TxnTaxDetail for a QB transaction from order tax amount.

        Note: For US QB companies, QB auto-calculates tax from its own rate
        tables.  TotalTax here is informational — QB will override it with
        the actual calculated amount.  To show correct tax in a US sandbox,
        configure a matching tax rate in QB Settings → Taxes.
        """
        return {
            "TotalTax": paisa_to_decimal(order.tax_amount),
        }

    async def _resolve_customer_ref(self, order: Order) -> dict:
        """Resolve or create a QB CustomerRef for the order."""
        name = order.customer_name or _WALKIN_CUSTOMER_NAME
        phone = order.customer_phone

        # Use a deterministic UUID for the walk-in customer
        if name == _WALKIN_CUSTOMER_NAME:
            walkin_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"walkin:{self.tenant_id}")
        else:
            walkin_id = uuid.uuid5(
                uuid.NAMESPACE_DNS, f"customer:{self.tenant_id}:{name}:{phone or ''}",
            )

        mapping = await self._get_entity_mapping("customer", walkin_id)
        if mapping:
            return {"value": mapping.qb_entity_id, "name": mapping.qb_entity_name}

        # Create / find in QB
        qb_customer_id = await self.sync_customer(name, phone, walkin_id)
        return {"value": qb_customer_id, "name": name}

    async def _resolve_payment_method_ref(self, payment_method: str = "Cash") -> dict | None:
        """Look up the QB PaymentMethodRef for a payment method name."""
        pm_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"pm:{self.tenant_id}:{payment_method}")
        mapping = await self._get_entity_mapping("payment_method", pm_id)
        if mapping:
            return {"value": mapping.qb_entity_id, "name": mapping.qb_entity_name}
        return None

    # =====================================================================
    # TRANSACTION SYNCS
    # =====================================================================

    # 1. Sales Receipt ------------------------------------------------

    async def sync_order_as_sales_receipt(self, order: Order) -> dict | None:
        """Convert a completed POS order to a QB Sales Receipt.

        Maps:
        - Order items -> Line items (SalesItemLineDetail)
        - Modifiers -> added to item description
        - Tax -> TxnTaxDetail
        - Payment method -> PaymentMethodRef
        - Customer -> CustomerRef (walk-in default if none)
        - Discount -> DiscountLineDetail
        - Order number -> DocNumber
        - Notes -> PrivateNote
        - Order type as CustomField / Memo
        """
        t0 = time.monotonic()
        order_label = _ORDER_TYPE_LABELS.get(order.order_type, order.order_type)

        try:
            # Build QB payload
            lines = await self._build_line_items(order)
            tax_detail = self._build_tax_detail(order)
            customer_ref = await self._resolve_customer_ref(order)
            payment_method_ref = await self._resolve_payment_method_ref()

            txn_date = order.created_at.strftime("%Y-%m-%d")

            payload: dict = {
                "DocNumber": order.order_number,
                "TxnDate": txn_date,
                "Line": lines,
                "TxnTaxDetail": tax_detail,
                "CustomerRef": customer_ref,
                "TotalAmt": paisa_to_decimal(order.total),
                "PrivateNote": (
                    f"{order_label} order {order.order_number}"
                    f"{(' - ' + order.notes) if order.notes else ''}"
                ),
                "CustomerMemo": {
                    "value": f"Thank you for dining with us! Order #{order.order_number}",
                },
                "PrintStatus": "NeedToPrint",
                "EmailStatus": "NotSet",
            }

            if payment_method_ref:
                payload["PaymentMethodRef"] = payment_method_ref

            # Include business address so QB US AST can calculate tax
            company_info = self.connection.company_info or {}
            company_addr = company_info.get("CompanyAddr") or company_info.get("LegalAddr")
            if company_addr:
                payload["ShipAddr"] = company_addr
            elif company_info.get("Country") == "US":
                # Fallback: use company address fields if available
                addr = {}
                for key in ("Line1", "City", "CountrySubDivisionCode", "PostalCode", "Country"):
                    if company_info.get(key):
                        addr[key] = company_info[key]
                if addr:
                    payload["ShipAddr"] = addr

            # Deposit-to account (cash drawer / bank)
            deposit_mapping = await self._get_account_mapping("bank")
            if deposit_mapping:
                payload["DepositToAccountRef"] = {
                    "value": deposit_mapping.qb_account_id,
                    "name": deposit_mapping.qb_account_name,
                }

            # Add table info for dine-in
            if order.order_type == "dine_in" and order.table:
                table_label = getattr(order.table, "label", None) or "Table"
                payload["PrivateNote"] += f" | Table: {table_label}"

            # Call QB API
            response = await self.client.post("salesreceipt", payload)
            elapsed = int((time.monotonic() - t0) * 1000)

            qb_id = response.get("SalesReceipt", {}).get("Id", "")
            doc_number = response.get("SalesReceipt", {}).get("DocNumber", order.order_number)

            # Save entity mapping (order -> SalesReceipt)
            await self._save_entity_mapping(
                entity_type="order",
                pos_entity_id=order.id,
                pos_entity_name=order.order_number,
                qb_entity_id=qb_id,
                qb_entity_type="SalesReceipt",
                qb_entity_name=doc_number,
                qb_entity_ref={"Id": qb_id, "DocNumber": doc_number},
            )

            await self._log_sync(
                sync_type="sales_receipt",
                action="create",
                status="success",
                pos_entity_type="order",
                pos_entity_id=order.id,
                qb_entity_type="SalesReceipt",
                qb_entity_id=qb_id,
                request_payload=payload,
                response_payload=response,
                duration_ms=elapsed,
                qb_doc_number=doc_number,
                amount_paisa=order.total,
                http_method="POST",
            )

            logger.info(
                "Synced order %s as SalesReceipt %s (QB ID %s)",
                order.order_number, doc_number, qb_id,
            )
            return response

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="sales_receipt",
                action="create",
                status="failed",
                pos_entity_type="order",
                pos_entity_id=order.id,
                error_message=str(exc),
                error_code=getattr(exc, "code", None),
                duration_ms=elapsed,
                amount_paisa=order.total,
                http_method="POST",
            )
            raise

    # 2. Invoice -------------------------------------------------------

    async def sync_order_as_invoice(self, order: Order) -> dict | None:
        """Convert a credit/corporate POS order to a QB Invoice."""
        t0 = time.monotonic()
        try:
            lines = await self._build_line_items(order)
            tax_detail = self._build_tax_detail(order)
            customer_ref = await self._resolve_customer_ref(order)
            txn_date = order.created_at.strftime("%Y-%m-%d")
            # Due in 30 days for corporate
            due_date = (order.created_at + timedelta(days=30)).strftime("%Y-%m-%d")
            order_label = _ORDER_TYPE_LABELS.get(order.order_type, order.order_type)

            payload: dict = {
                "DocNumber": order.order_number,
                "TxnDate": txn_date,
                "DueDate": due_date,
                "Line": lines,
                "TxnTaxDetail": tax_detail,
                "CustomerRef": customer_ref,
                "TotalAmt": paisa_to_decimal(order.total),
                "Balance": paisa_to_decimal(order.total),
                "PrivateNote": f"{order_label} order {order.order_number} (credit)",
                "PrintStatus": "NeedToPrint",
                "EmailStatus": "NotSet",
            }

            response = await self.client.post("invoice", payload)
            elapsed = int((time.monotonic() - t0) * 1000)

            qb_id = response.get("Invoice", {}).get("Id", "")
            doc_number = response.get("Invoice", {}).get("DocNumber", order.order_number)

            await self._save_entity_mapping(
                entity_type="order",
                pos_entity_id=order.id,
                pos_entity_name=order.order_number,
                qb_entity_id=qb_id,
                qb_entity_type="Invoice",
                qb_entity_name=doc_number,
                qb_entity_ref={"Id": qb_id, "DocNumber": doc_number},
            )

            await self._log_sync(
                sync_type="invoice",
                action="create",
                status="success",
                pos_entity_type="order",
                pos_entity_id=order.id,
                qb_entity_type="Invoice",
                qb_entity_id=qb_id,
                request_payload=payload,
                response_payload=response,
                duration_ms=elapsed,
                qb_doc_number=doc_number,
                amount_paisa=order.total,
                http_method="POST",
            )
            return response

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="invoice",
                action="create",
                status="failed",
                pos_entity_type="order",
                pos_entity_id=order.id,
                error_message=str(exc),
                duration_ms=elapsed,
                amount_paisa=order.total,
                http_method="POST",
            )
            raise

    # 3. Payment -------------------------------------------------------

    async def sync_payment_received(
        self,
        order: Order,
        amount_paisa: int,
        payment_method: str,
        invoice_qb_id: str,
    ) -> dict | None:
        """Record a payment against an existing QB Invoice."""
        t0 = time.monotonic()
        try:
            customer_ref = await self._resolve_customer_ref(order)
            txn_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            payload: dict = {
                "TxnDate": txn_date,
                "TotalAmt": paisa_to_decimal(amount_paisa),
                "CustomerRef": customer_ref,
                "Line": [
                    {
                        "Amount": paisa_to_decimal(amount_paisa),
                        "LinkedTxn": [
                            {
                                "TxnId": invoice_qb_id,
                                "TxnType": "Invoice",
                            }
                        ],
                    }
                ],
                "PrivateNote": f"Payment for order {order.order_number} via {payment_method}",
            }

            pm_ref = await self._resolve_payment_method_ref(payment_method)
            if pm_ref:
                payload["PaymentMethodRef"] = pm_ref

            deposit_mapping = await self._get_account_mapping("bank")
            if deposit_mapping:
                payload["DepositToAccountRef"] = {
                    "value": deposit_mapping.qb_account_id,
                    "name": deposit_mapping.qb_account_name,
                }

            response = await self.client.post("payment", payload)
            elapsed = int((time.monotonic() - t0) * 1000)

            qb_id = response.get("Payment", {}).get("Id", "")

            await self._log_sync(
                sync_type="payment",
                action="create",
                status="success",
                pos_entity_type="order",
                pos_entity_id=order.id,
                qb_entity_type="Payment",
                qb_entity_id=qb_id,
                request_payload=payload,
                response_payload=response,
                duration_ms=elapsed,
                amount_paisa=amount_paisa,
                http_method="POST",
            )
            return response

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="payment",
                action="create",
                status="failed",
                pos_entity_type="order",
                pos_entity_id=order.id,
                error_message=str(exc),
                duration_ms=elapsed,
                amount_paisa=amount_paisa,
                http_method="POST",
            )
            raise

    # 4. Credit Memo (void) --------------------------------------------

    async def sync_void_as_credit_memo(self, order: Order) -> dict | None:
        """Create a Credit Memo when a POS order is voided."""
        t0 = time.monotonic()
        try:
            # Find the original Sales Receipt / Invoice mapping
            original_mapping = await self._get_entity_mapping("order", order.id)

            lines = await self._build_line_items(order)
            tax_detail = self._build_tax_detail(order)
            customer_ref = await self._resolve_customer_ref(order)
            txn_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            payload: dict = {
                "DocNumber": f"VOID-{order.order_number}",
                "TxnDate": txn_date,
                "Line": lines,
                "TxnTaxDetail": tax_detail,
                "CustomerRef": customer_ref,
                "TotalAmt": paisa_to_decimal(order.total),
                "PrivateNote": (
                    f"Void of order {order.order_number}"
                    f"{(' (QB ref ' + original_mapping.qb_entity_id + ')') if original_mapping else ''}"
                ),
            }

            response = await self.client.post("creditmemo", payload)
            elapsed = int((time.monotonic() - t0) * 1000)

            qb_id = response.get("CreditMemo", {}).get("Id", "")

            await self._log_sync(
                sync_type="credit_memo",
                action="create",
                status="success",
                pos_entity_type="order",
                pos_entity_id=order.id,
                qb_entity_type="CreditMemo",
                qb_entity_id=qb_id,
                request_payload=payload,
                response_payload=response,
                duration_ms=elapsed,
                qb_doc_number=f"VOID-{order.order_number}",
                amount_paisa=order.total,
                http_method="POST",
            )
            return response

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="credit_memo",
                action="create",
                status="failed",
                pos_entity_type="order",
                pos_entity_id=order.id,
                error_message=str(exc),
                duration_ms=elapsed,
                amount_paisa=order.total,
                http_method="POST",
            )
            raise

    # 5. Refund Receipt ------------------------------------------------

    async def sync_refund(self, order: Order, refund_amount_paisa: int) -> dict | None:
        """Create a Refund Receipt in QB for a cash refund."""
        t0 = time.monotonic()
        try:
            customer_ref = await self._resolve_customer_ref(order)
            txn_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            # Proportional line items if partial refund
            if refund_amount_paisa >= order.total:
                lines = await self._build_line_items(order)
            else:
                # Single refund line — use default income account
                refund_line: dict = {
                    "Id": "1",
                    "LineNum": 1,
                    "Amount": paisa_to_decimal(refund_amount_paisa),
                    "Description": f"Refund for order {order.order_number}",
                    "DetailType": "SalesItemLineDetail",
                    "SalesItemLineDetail": {
                        "Qty": 1,
                        "UnitPrice": paisa_to_decimal(refund_amount_paisa),
                    },
                }
                income_mapping = await self._get_account_mapping("income")
                if income_mapping:
                    refund_line["SalesItemLineDetail"]["ItemAccountRef"] = {
                        "value": income_mapping.qb_account_id,
                        "name": income_mapping.qb_account_name,
                    }
                lines = [refund_line]

            payload: dict = {
                "DocNumber": f"REF-{order.order_number}",
                "TxnDate": txn_date,
                "Line": lines,
                "CustomerRef": customer_ref,
                "TotalAmt": paisa_to_decimal(refund_amount_paisa),
                "PrivateNote": f"Refund for order {order.order_number}",
            }

            deposit_mapping = await self._get_account_mapping("bank")
            if deposit_mapping:
                payload["DepositToAccountRef"] = {
                    "value": deposit_mapping.qb_account_id,
                    "name": deposit_mapping.qb_account_name,
                }

            response = await self.client.post("refundreceipt", payload)
            elapsed = int((time.monotonic() - t0) * 1000)

            qb_id = response.get("RefundReceipt", {}).get("Id", "")

            await self._log_sync(
                sync_type="refund_receipt",
                action="create",
                status="success",
                pos_entity_type="order",
                pos_entity_id=order.id,
                qb_entity_type="RefundReceipt",
                qb_entity_id=qb_id,
                request_payload=payload,
                response_payload=response,
                duration_ms=elapsed,
                qb_doc_number=f"REF-{order.order_number}",
                amount_paisa=refund_amount_paisa,
                http_method="POST",
            )
            return response

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="refund_receipt",
                action="create",
                status="failed",
                pos_entity_type="order",
                pos_entity_id=order.id,
                error_message=str(exc),
                duration_ms=elapsed,
                amount_paisa=refund_amount_paisa,
                http_method="POST",
            )
            raise

    # 6. Journal Entry (daily summary) ---------------------------------

    async def create_daily_summary(self, date: datetime) -> dict | None:
        """Create a double-entry Journal Entry summarising all orders for a date.

        Debits:
          - Cash/Bank accounts per payment method totals
        Credits:
          - Income accounts (per category aggregation)
          - Tax Payable accounts (FBR GST + PRA PST)
          - Discount adjustments (contra-revenue)

        The entry MUST balance: total debits == total credits.
        """
        t0 = time.monotonic()
        target_date = date.date() if isinstance(date, datetime) else date
        txn_date = target_date.isoformat()

        try:
            # Aggregate completed orders for the date
            order_result = await self.db.execute(
                select(Order)
                .options(selectinload(Order.items))
                .where(
                    Order.tenant_id == self.tenant_id,
                    Order.status == "completed",
                    func.cast(Order.created_at, Date) == target_date,
                )
            )
            orders = list(order_result.scalars().unique().all())

            if not orders:
                await self._log_sync(
                    sync_type="journal_entry",
                    action="create",
                    status="skipped",
                    qb_doc_number=f"DAILY-{txn_date}",
                    duration_ms=int((time.monotonic() - t0) * 1000),
                )
                logger.info("No completed orders for %s, skipping daily summary", txn_date)
                return None

            # Totals
            total_revenue = sum(o.subtotal for o in orders)
            total_tax = sum(o.tax_amount for o in orders)
            total_discount = sum(o.discount_amount for o in orders)
            total_collected = sum(o.total for o in orders)
            order_count = len(orders)

            # Build journal lines
            je_lines: list[dict] = []
            line_num = 0

            # DEBIT: Cash / Undeposited Funds (total collected)
            # For simplicity, all goes to one bank account
            bank_mapping = await self._get_account_mapping("bank")
            bank_acct_ref = (
                {"value": bank_mapping.qb_account_id, "name": bank_mapping.qb_account_name}
                if bank_mapping
                else {"value": "1", "name": "Undeposited Funds"}
            )

            line_num += 1
            je_lines.append({
                "Id": str(line_num),
                "LineNum": line_num,
                "Amount": paisa_to_decimal(total_collected),
                "Description": f"Daily sales collected ({order_count} orders) - {txn_date}",
                "DetailType": "JournalEntryLineDetail",
                "JournalEntryLineDetail": {
                    "PostingType": "Debit",
                    "AccountRef": bank_acct_ref,
                },
            })

            # CREDIT: Food / Beverage Sales (revenue)
            income_mapping = await self._get_account_mapping("income")
            income_acct_ref = (
                {"value": income_mapping.qb_account_id, "name": income_mapping.qb_account_name}
                if income_mapping
                else {"value": "2", "name": "Sales Revenue"}
            )

            net_revenue = total_revenue - total_discount
            if net_revenue > 0:
                line_num += 1
                je_lines.append({
                    "Id": str(line_num),
                    "LineNum": line_num,
                    "Amount": paisa_to_decimal(net_revenue),
                    "Description": f"Net food sales revenue - {txn_date}",
                    "DetailType": "JournalEntryLineDetail",
                    "JournalEntryLineDetail": {
                        "PostingType": "Credit",
                        "AccountRef": income_acct_ref,
                    },
                })

            # CREDIT: Tax Payable
            if total_tax > 0:
                tax_mapping = await self._get_account_mapping("tax_payable")
                tax_acct_ref = (
                    {"value": tax_mapping.qb_account_id, "name": tax_mapping.qb_account_name}
                    if tax_mapping
                    else {"value": "3", "name": "Sales Tax Payable"}
                )

                line_num += 1
                je_lines.append({
                    "Id": str(line_num),
                    "LineNum": line_num,
                    "Amount": paisa_to_decimal(total_tax),
                    "Description": f"Tax collected (FBR/PRA) - {txn_date}",
                    "DetailType": "JournalEntryLineDetail",
                    "JournalEntryLineDetail": {
                        "PostingType": "Credit",
                        "AccountRef": tax_acct_ref,
                    },
                })

            # DEBIT: Discount as contra-revenue (if any)
            # Discounts reduce what's collected but we already debited only
            # total_collected (which is net of discounts).  The credit side
            # uses net_revenue, so the entry already balances.  We log
            # discounts only in the PrivateNote for transparency.

            payload: dict = {
                "DocNumber": f"DAILY-{txn_date}",
                "TxnDate": txn_date,
                "Line": je_lines,
                "PrivateNote": (
                    f"POS daily summary for {txn_date}: "
                    f"{order_count} orders, "
                    f"Subtotal {paisa_to_decimal(total_revenue)} PKR, "
                    f"Discount {paisa_to_decimal(total_discount)} PKR, "
                    f"Tax {paisa_to_decimal(total_tax)} PKR, "
                    f"Collected {paisa_to_decimal(total_collected)} PKR"
                ),
                "Adjustment": False,
            }

            response = await self.client.post("journalentry", payload)
            elapsed = int((time.monotonic() - t0) * 1000)

            qb_id = response.get("JournalEntry", {}).get("Id", "")

            await self._log_sync(
                sync_type="journal_entry",
                action="create",
                status="success",
                qb_entity_type="JournalEntry",
                qb_entity_id=qb_id,
                request_payload=payload,
                response_payload=response,
                duration_ms=elapsed,
                qb_doc_number=f"DAILY-{txn_date}",
                amount_paisa=total_collected,
                http_method="POST",
            )

            logger.info(
                "Created daily summary JE for %s: %d orders, %s PKR",
                txn_date, order_count, paisa_to_decimal(total_collected),
            )
            return response

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="journal_entry",
                action="create",
                status="failed",
                error_message=str(exc),
                duration_ms=elapsed,
                qb_doc_number=f"DAILY-{txn_date}",
                http_method="POST",
            )
            raise

    # 7. Deposit -------------------------------------------------------

    async def create_daily_deposit(
        self,
        date: datetime,
        cash_amount_paisa: int,
        card_amount_paisa: int,
    ) -> dict | None:
        """Create a Deposit record for daily cash/card settlement to bank."""
        t0 = time.monotonic()
        target_date = date.date() if isinstance(date, datetime) else date
        txn_date = target_date.isoformat()
        total = cash_amount_paisa + card_amount_paisa

        if total <= 0:
            logger.info("No amounts to deposit for %s, skipping", txn_date)
            return None

        try:
            bank_mapping = await self._get_account_mapping("bank")
            bank_ref = (
                {"value": bank_mapping.qb_account_id, "name": bank_mapping.qb_account_name}
                if bank_mapping
                else {"value": "1", "name": "Business Bank Account"}
            )

            deposit_lines: list[dict] = []

            if cash_amount_paisa > 0:
                deposit_lines.append({
                    "Amount": paisa_to_decimal(cash_amount_paisa),
                    "DetailType": "DepositLineDetail",
                    "DepositLineDetail": {
                        "AccountRef": {"value": "1", "name": "Cash Drawer"},
                    },
                    "Description": f"Cash deposit - {txn_date}",
                })

            if card_amount_paisa > 0:
                deposit_lines.append({
                    "Amount": paisa_to_decimal(card_amount_paisa),
                    "DetailType": "DepositLineDetail",
                    "DepositLineDetail": {
                        "AccountRef": {"value": "1", "name": "Undeposited Funds"},
                    },
                    "Description": f"Card settlements deposit - {txn_date}",
                })

            payload: dict = {
                "TxnDate": txn_date,
                "DepositToAccountRef": bank_ref,
                "Line": deposit_lines,
                "TotalAmt": paisa_to_decimal(total),
                "PrivateNote": f"POS daily deposit for {txn_date}",
            }

            response = await self.client.post("deposit", payload)
            elapsed = int((time.monotonic() - t0) * 1000)

            qb_id = response.get("Deposit", {}).get("Id", "")

            await self._log_sync(
                sync_type="deposit",
                action="create",
                status="success",
                qb_entity_type="Deposit",
                qb_entity_id=qb_id,
                request_payload=payload,
                response_payload=response,
                duration_ms=elapsed,
                amount_paisa=total,
                http_method="POST",
            )
            return response

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="deposit",
                action="create",
                status="failed",
                error_message=str(exc),
                duration_ms=elapsed,
                amount_paisa=total,
                http_method="POST",
            )
            raise

    # 8. Estimate (catering quotes) ------------------------------------

    async def sync_estimate(self, order: Order) -> dict | None:
        """Create an Estimate in QB for a catering/event quote."""
        t0 = time.monotonic()
        try:
            lines = await self._build_line_items(order)
            tax_detail = self._build_tax_detail(order)
            customer_ref = await self._resolve_customer_ref(order)
            txn_date = order.created_at.strftime("%Y-%m-%d")
            expiry_date = (order.created_at + timedelta(days=14)).strftime("%Y-%m-%d")

            payload: dict = {
                "DocNumber": f"EST-{order.order_number}",
                "TxnDate": txn_date,
                "ExpirationDate": expiry_date,
                "Line": lines,
                "TxnTaxDetail": tax_detail,
                "CustomerRef": customer_ref,
                "TotalAmt": paisa_to_decimal(order.total),
                "PrivateNote": f"Catering estimate from POS order {order.order_number}",
                "PrintStatus": "NeedToPrint",
                "EmailStatus": "NotSet",
            }

            response = await self.client.post("estimate", payload)
            elapsed = int((time.monotonic() - t0) * 1000)

            qb_id = response.get("Estimate", {}).get("Id", "")

            await self._log_sync(
                sync_type="estimate",
                action="create",
                status="success",
                pos_entity_type="order",
                pos_entity_id=order.id,
                qb_entity_type="Estimate",
                qb_entity_id=qb_id,
                request_payload=payload,
                response_payload=response,
                duration_ms=elapsed,
                qb_doc_number=f"EST-{order.order_number}",
                amount_paisa=order.total,
                http_method="POST",
            )
            return response

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="estimate",
                action="create",
                status="failed",
                pos_entity_type="order",
                pos_entity_id=order.id,
                error_message=str(exc),
                duration_ms=elapsed,
                amount_paisa=order.total,
                http_method="POST",
            )
            raise

    # 9. Bill (supplier invoice) ---------------------------------------

    async def sync_bill(
        self,
        vendor_name: str,
        amount_paisa: int,
        line_items: list[dict],
        memo: str | None = None,
    ) -> dict | None:
        """Create a Bill (supplier invoice) in QB."""
        t0 = time.monotonic()
        try:
            # Resolve vendor
            vendor_qb_id = await self.sync_vendor(vendor_name)
            vendor_ref = {"value": vendor_qb_id, "name": vendor_name}
            txn_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            due_date = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")

            lines: list[dict] = []
            for idx, li in enumerate(line_items, 1):
                lines.append({
                    "Id": str(idx),
                    "LineNum": idx,
                    "Amount": paisa_to_decimal(li.get("amount_paisa", 0)),
                    "Description": li.get("description", ""),
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "AccountBasedExpenseLineDetail": {
                        "AccountRef": li.get("account_ref", {"value": "1", "name": "Expense"}),
                    },
                })

            if not lines:
                lines.append({
                    "Id": "1",
                    "LineNum": 1,
                    "Amount": paisa_to_decimal(amount_paisa),
                    "Description": memo or f"Bill from {vendor_name}",
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "AccountBasedExpenseLineDetail": {
                        "AccountRef": {"value": "1", "name": "Expense"},
                    },
                })

            payload: dict = {
                "VendorRef": vendor_ref,
                "TxnDate": txn_date,
                "DueDate": due_date,
                "Line": lines,
                "TotalAmt": paisa_to_decimal(amount_paisa),
                "PrivateNote": memo or f"Supplier bill from {vendor_name}",
            }

            response = await self.client.post("bill", payload)
            elapsed = int((time.monotonic() - t0) * 1000)

            qb_id = response.get("Bill", {}).get("Id", "")

            await self._log_sync(
                sync_type="bill",
                action="create",
                status="success",
                qb_entity_type="Bill",
                qb_entity_id=qb_id,
                request_payload=payload,
                response_payload=response,
                duration_ms=elapsed,
                amount_paisa=amount_paisa,
                http_method="POST",
            )
            return response

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="bill",
                action="create",
                status="failed",
                error_message=str(exc),
                duration_ms=elapsed,
                amount_paisa=amount_paisa,
                http_method="POST",
            )
            raise

    # 10. Bill Payment -------------------------------------------------

    async def sync_bill_payment(
        self,
        bill_qb_id: str,
        amount_paisa: int,
        payment_account_id: str,
    ) -> dict | None:
        """Record a payment against an existing QB Bill."""
        t0 = time.monotonic()
        try:
            # Read the bill to get VendorRef
            bill = await self.client.get("bill", bill_qb_id)
            vendor_ref = bill.get("Bill", {}).get("VendorRef", {})
            txn_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            payload: dict = {
                "VendorRef": vendor_ref,
                "TxnDate": txn_date,
                "TotalAmt": paisa_to_decimal(amount_paisa),
                "PayType": "Check",
                "CheckPayment": {
                    "BankAccountRef": {"value": payment_account_id},
                },
                "Line": [
                    {
                        "Amount": paisa_to_decimal(amount_paisa),
                        "LinkedTxn": [
                            {"TxnId": bill_qb_id, "TxnType": "Bill"},
                        ],
                    }
                ],
                "PrivateNote": f"Payment for bill {bill_qb_id}",
            }

            response = await self.client.post("billpayment", payload)
            elapsed = int((time.monotonic() - t0) * 1000)

            qb_id = response.get("BillPayment", {}).get("Id", "")

            await self._log_sync(
                sync_type="bill_payment",
                action="create",
                status="success",
                qb_entity_type="BillPayment",
                qb_entity_id=qb_id,
                request_payload=payload,
                response_payload=response,
                duration_ms=elapsed,
                amount_paisa=amount_paisa,
                http_method="POST",
            )
            return response

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="bill_payment",
                action="create",
                status="failed",
                error_message=str(exc),
                duration_ms=elapsed,
                amount_paisa=amount_paisa,
                http_method="POST",
            )
            raise

    # 11. Purchase Order -----------------------------------------------

    async def sync_purchase_order(
        self,
        vendor_name: str,
        line_items: list[dict],
        memo: str | None = None,
    ) -> dict | None:
        """Create a Purchase Order in QB."""
        t0 = time.monotonic()
        try:
            vendor_qb_id = await self.sync_vendor(vendor_name)
            vendor_ref = {"value": vendor_qb_id, "name": vendor_name}
            txn_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            lines: list[dict] = []
            total_paisa = 0
            for idx, li in enumerate(line_items, 1):
                item_amount = li.get("amount_paisa", 0)
                total_paisa += item_amount
                lines.append({
                    "Id": str(idx),
                    "LineNum": idx,
                    "Amount": paisa_to_decimal(item_amount),
                    "Description": li.get("description", ""),
                    "DetailType": "ItemBasedExpenseLineDetail",
                    "ItemBasedExpenseLineDetail": {
                        "Qty": li.get("quantity", 1),
                        "UnitPrice": paisa_to_decimal(li.get("unit_price_paisa", item_amount)),
                    },
                })

            payload: dict = {
                "VendorRef": vendor_ref,
                "TxnDate": txn_date,
                "Line": lines,
                "TotalAmt": paisa_to_decimal(total_paisa),
                "PrivateNote": memo or f"PO to {vendor_name}",
            }

            response = await self.client.post("purchaseorder", payload)
            elapsed = int((time.monotonic() - t0) * 1000)

            qb_id = response.get("PurchaseOrder", {}).get("Id", "")

            await self._log_sync(
                sync_type="purchase_order",
                action="create",
                status="success",
                qb_entity_type="PurchaseOrder",
                qb_entity_id=qb_id,
                request_payload=payload,
                response_payload=response,
                duration_ms=elapsed,
                amount_paisa=total_paisa,
                http_method="POST",
            )
            return response

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="purchase_order",
                action="create",
                status="failed",
                error_message=str(exc),
                duration_ms=elapsed,
                http_method="POST",
            )
            raise

    # 12. Transfer -----------------------------------------------------

    async def sync_transfer(
        self,
        from_account_id: str,
        to_account_id: str,
        amount_paisa: int,
        memo: str | None = None,
    ) -> dict | None:
        """Create a Transfer (e.g., cash drawer to bank) in QB."""
        t0 = time.monotonic()
        try:
            txn_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            payload: dict = {
                "TxnDate": txn_date,
                "Amount": paisa_to_decimal(amount_paisa),
                "FromAccountRef": {"value": from_account_id},
                "ToAccountRef": {"value": to_account_id},
                "PrivateNote": memo or "POS cash drawer transfer to bank",
            }

            response = await self.client.post("transfer", payload)
            elapsed = int((time.monotonic() - t0) * 1000)

            qb_id = response.get("Transfer", {}).get("Id", "")

            await self._log_sync(
                sync_type="transfer",
                action="create",
                status="success",
                qb_entity_type="Transfer",
                qb_entity_id=qb_id,
                request_payload=payload,
                response_payload=response,
                duration_ms=elapsed,
                amount_paisa=amount_paisa,
                http_method="POST",
            )
            return response

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="transfer",
                action="create",
                status="failed",
                error_message=str(exc),
                duration_ms=elapsed,
                amount_paisa=amount_paisa,
                http_method="POST",
            )
            raise

    # 13. Vendor Credit ------------------------------------------------

    async def sync_vendor_credit(
        self,
        vendor_name: str,
        amount_paisa: int,
        line_items: list[dict],
    ) -> dict | None:
        """Create a Vendor Credit (supplier returns/credits) in QB."""
        t0 = time.monotonic()
        try:
            vendor_qb_id = await self.sync_vendor(vendor_name)
            vendor_ref = {"value": vendor_qb_id, "name": vendor_name}
            txn_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            lines: list[dict] = []
            for idx, li in enumerate(line_items, 1):
                lines.append({
                    "Id": str(idx),
                    "LineNum": idx,
                    "Amount": paisa_to_decimal(li.get("amount_paisa", 0)),
                    "Description": li.get("description", ""),
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "AccountBasedExpenseLineDetail": {
                        "AccountRef": li.get("account_ref", {"value": "1", "name": "Expense"}),
                    },
                })

            if not lines:
                lines.append({
                    "Id": "1",
                    "LineNum": 1,
                    "Amount": paisa_to_decimal(amount_paisa),
                    "Description": f"Vendor credit from {vendor_name}",
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "AccountBasedExpenseLineDetail": {
                        "AccountRef": {"value": "1", "name": "Expense"},
                    },
                })

            payload: dict = {
                "VendorRef": vendor_ref,
                "TxnDate": txn_date,
                "Line": lines,
                "TotalAmt": paisa_to_decimal(amount_paisa),
                "PrivateNote": f"Vendor credit from {vendor_name}",
            }

            response = await self.client.post("vendorcredit", payload)
            elapsed = int((time.monotonic() - t0) * 1000)

            qb_id = response.get("VendorCredit", {}).get("Id", "")

            await self._log_sync(
                sync_type="vendor_credit",
                action="create",
                status="success",
                qb_entity_type="VendorCredit",
                qb_entity_id=qb_id,
                request_payload=payload,
                response_payload=response,
                duration_ms=elapsed,
                amount_paisa=amount_paisa,
                http_method="POST",
            )
            return response

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="vendor_credit",
                action="create",
                status="failed",
                error_message=str(exc),
                duration_ms=elapsed,
                amount_paisa=amount_paisa,
                http_method="POST",
            )
            raise

    # =====================================================================
    # ENTITY SYNCS
    # =====================================================================

    # 14. Menu Item -> QB Product/Service ------------------------------

    async def sync_menu_item(self, item_id: uuid.UUID) -> dict | None:
        """Sync a POS menu item to QB as a Product/Service (NonInventory)."""
        t0 = time.monotonic()
        try:
            result = await self.db.execute(
                select(MenuItem)
                .options(selectinload(MenuItem.category))
                .where(
                    MenuItem.id == item_id,
                    MenuItem.tenant_id == self.tenant_id,
                )
            )
            item = result.scalar_one_or_none()
            if item is None:
                raise ValueError(f"MenuItem {item_id} not found")

            # Check existing mapping
            existing = await self._get_entity_mapping("menu_item", item_id)

            # Resolve income account (try category-specific, then default)
            income_mapping = await self._get_account_mapping("income", item.category_id)
            income_ref = (
                {"value": income_mapping.qb_account_id, "name": income_mapping.qb_account_name}
                if income_mapping
                else None
            )

            qb_name = item.name
            # QB item names must be unique; prefix with category if needed
            if item.category:
                qb_name = f"{item.category.name}: {item.name}"

            payload: dict = {
                "Name": qb_name[:100],  # QB max 100 chars
                "Type": "NonInventory",
                "Description": item.description or item.name,
                "UnitPrice": paisa_to_decimal(item.price),
                "Active": item.is_available,
                "Taxable": True,
            }

            if income_ref:
                payload["IncomeAccountRef"] = income_ref

            # Resolve expense account for COGS
            cogs_mapping = await self._get_account_mapping("cogs")
            if cogs_mapping:
                payload["ExpenseAccountRef"] = {
                    "value": cogs_mapping.qb_account_id,
                    "name": cogs_mapping.qb_account_name,
                }

            if existing:
                # Update existing QB item
                payload["Id"] = existing.qb_entity_id
                payload["SyncToken"] = (existing.qb_entity_ref or {}).get("SyncToken", "0")
                payload["sparse"] = True
                response = await self.client.post("item", payload)
            else:
                response = await self.client.post("item", payload)

            elapsed = int((time.monotonic() - t0) * 1000)

            qb_item = response.get("Item", {})
            qb_id = qb_item.get("Id", "")
            sync_token = qb_item.get("SyncToken", "0")

            await self._save_entity_mapping(
                entity_type="menu_item",
                pos_entity_id=item_id,
                pos_entity_name=item.name,
                qb_entity_id=qb_id,
                qb_entity_type="Item",
                qb_entity_name=qb_name,
                qb_entity_ref={"Id": qb_id, "SyncToken": sync_token},
            )

            await self._log_sync(
                sync_type="item",
                action="update" if existing else "create",
                status="success",
                pos_entity_type="menu_item",
                pos_entity_id=item_id,
                qb_entity_type="Item",
                qb_entity_id=qb_id,
                request_payload=payload,
                response_payload=response,
                duration_ms=elapsed,
                http_method="POST",
            )
            return response

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="item",
                action="create",
                status="failed",
                pos_entity_type="menu_item",
                pos_entity_id=item_id,
                error_message=str(exc),
                duration_ms=elapsed,
                http_method="POST",
            )
            raise

    # 15. Category -> QB Item Category ---------------------------------

    async def sync_category(self, category_id: uuid.UUID) -> dict | None:
        """Sync a POS menu category as a QB Item Category (sub-type)."""
        t0 = time.monotonic()
        try:
            result = await self.db.execute(
                select(Category).where(
                    Category.id == category_id,
                    Category.tenant_id == self.tenant_id,
                )
            )
            cat = result.scalar_one_or_none()
            if cat is None:
                raise ValueError(f"Category {category_id} not found")

            existing = await self._get_entity_mapping("category", category_id)

            # QB doesn't have a native "Item Category" entity via REST for
            # all regions. We create it as a parent NonInventory item of Type
            # "Category" (QBO feature) or as a sub-account structure.
            # The most portable approach: use QB Item with SubItem=false.
            payload: dict = {
                "Name": cat.name[:100],
                "Type": "Category",
                "Active": cat.is_active,
            }

            if existing:
                payload["Id"] = existing.qb_entity_id
                payload["SyncToken"] = (existing.qb_entity_ref or {}).get("SyncToken", "0")
                payload["sparse"] = True

            response = await self.client.post("item", payload)
            elapsed = int((time.monotonic() - t0) * 1000)

            qb_item = response.get("Item", {})
            qb_id = qb_item.get("Id", "")
            sync_token = qb_item.get("SyncToken", "0")

            await self._save_entity_mapping(
                entity_type="category",
                pos_entity_id=category_id,
                pos_entity_name=cat.name,
                qb_entity_id=qb_id,
                qb_entity_type="Item",
                qb_entity_name=cat.name,
                qb_entity_ref={"Id": qb_id, "SyncToken": sync_token},
            )

            await self._log_sync(
                sync_type="category",
                action="update" if existing else "create",
                status="success",
                pos_entity_type="category",
                pos_entity_id=category_id,
                qb_entity_type="Item",
                qb_entity_id=qb_id,
                request_payload=payload,
                response_payload=response,
                duration_ms=elapsed,
                http_method="POST",
            )
            return response

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="category",
                action="create",
                status="failed",
                pos_entity_type="category",
                pos_entity_id=category_id,
                error_message=str(exc),
                duration_ms=elapsed,
                http_method="POST",
            )
            raise

    # 16. Customer -----------------------------------------------------

    async def sync_customer(
        self,
        name: str,
        phone: str | None = None,
        customer_id: uuid.UUID | None = None,
    ) -> str:
        """Sync or find a customer in QB.  Returns QB customer ID.

        Tries to find existing by DisplayName first, creates if not found.
        """
        t0 = time.monotonic()

        # Generate a deterministic ID if none given
        if customer_id is None:
            customer_id = uuid.uuid5(
                uuid.NAMESPACE_DNS, f"customer:{self.tenant_id}:{name}:{phone or ''}",
            )

        # Check local mapping first
        existing = await self._get_entity_mapping("customer", customer_id)
        if existing:
            return existing.qb_entity_id

        try:
            # Query QB for existing customer by name
            customers = await self.client.query(
                "Customer", where=f"DisplayName = '{name}'",
            )

            if customers:
                qb_customer = customers[0]
                qb_id = qb_customer["Id"]
                await self._save_entity_mapping(
                    entity_type="customer",
                    pos_entity_id=customer_id,
                    pos_entity_name=name,
                    qb_entity_id=qb_id,
                    qb_entity_type="Customer",
                    qb_entity_name=name,
                    qb_entity_ref={"Id": qb_id, "SyncToken": qb_customer.get("SyncToken", "0")},
                )
                elapsed = int((time.monotonic() - t0) * 1000)
                await self._log_sync(
                    sync_type="customer",
                    action="query",
                    status="success",
                    pos_entity_type="customer",
                    pos_entity_id=customer_id,
                    qb_entity_type="Customer",
                    qb_entity_id=qb_id,
                    duration_ms=elapsed,
                )
                return qb_id

            # Create new customer
            payload: dict = {
                "DisplayName": name,
                "CompanyName": name if name == _WALKIN_CUSTOMER_NAME else None,
                "Active": True,
            }

            if phone:
                payload["PrimaryPhone"] = {"FreeFormNumber": phone}

            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}

            response = await self.client.post("customer", payload)
            elapsed = int((time.monotonic() - t0) * 1000)

            qb_customer = response.get("Customer", {})
            qb_id = qb_customer.get("Id", "")

            await self._save_entity_mapping(
                entity_type="customer",
                pos_entity_id=customer_id,
                pos_entity_name=name,
                qb_entity_id=qb_id,
                qb_entity_type="Customer",
                qb_entity_name=name,
                qb_entity_ref={"Id": qb_id, "SyncToken": qb_customer.get("SyncToken", "0")},
            )

            await self._log_sync(
                sync_type="customer",
                action="create",
                status="success",
                pos_entity_type="customer",
                pos_entity_id=customer_id,
                qb_entity_type="Customer",
                qb_entity_id=qb_id,
                request_payload=payload,
                response_payload=response,
                duration_ms=elapsed,
                http_method="POST",
            )
            return qb_id

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="customer",
                action="create",
                status="failed",
                pos_entity_type="customer",
                pos_entity_id=customer_id,
                error_message=str(exc),
                duration_ms=elapsed,
                http_method="POST",
            )
            raise

    # 17-18. Tax Code + Tax Rate ---------------------------------------

    async def sync_tax_codes(self) -> list[dict]:
        """Read existing QB tax codes and return them for mapping.

        QB Online does not allow creating tax codes via API in most
        regions, so we query what exists and let the admin map them to
        FBR GST (17%) / PRA PST (16%) / Exempt.
        """
        t0 = time.monotonic()
        try:
            codes = await self.client.query("TaxCode", where="Active = true")
            elapsed = int((time.monotonic() - t0) * 1000)

            await self._log_sync(
                sync_type="tax_code",
                action="query",
                status="success",
                qb_entity_type="TaxCode",
                duration_ms=elapsed,
            )
            return codes

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="tax_code",
                action="query",
                status="failed",
                error_message=str(exc),
                duration_ms=elapsed,
            )
            raise

    # 18b. Tax Code Auto-Setup ----------------------------------------

    # Well-known deterministic UUIDs for tax code entity mappings
    _TAX_CODE_TAXABLE_POS_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "tax_code:taxable")
    _TAX_CODE_NON_TAXABLE_POS_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "tax_code:non_taxable")

    async def setup_tax_code_mapping(self) -> dict:
        """Query QB for tax codes and auto-map the default taxable / non-taxable.

        QB Online manages tax codes internally (cannot be created via API in
        most regions).  This method queries what exists, picks the taxable
        code and non-taxable code, and saves entity mappings so
        ``_build_line_items`` can add ``TaxCodeRef`` to every line.

        **US vs International**:
        - US companies: TaxCodeRef on line items must be ``"TAX"`` or ``"NON"``
          (string keywords), not the numeric TaxCode Id.
        - International companies: TaxCodeRef uses the numeric TaxCode Id
          (e.g., ``"2"``).

        We detect the company's country and store the correct value.

        Returns dict with ``taxable`` and ``non_taxable`` ref values.
        """
        # Check if already set up
        existing_taxable = await self._get_entity_mapping(
            "tax_code", self._TAX_CODE_TAXABLE_POS_ID,
        )
        existing_non = await self._get_entity_mapping(
            "tax_code", self._TAX_CODE_NON_TAXABLE_POS_ID,
        )
        if existing_taxable and existing_non:
            return {
                "taxable": existing_taxable.qb_entity_id,
                "non_taxable": existing_non.qb_entity_id,
            }

        codes = await self.sync_tax_codes()
        if not codes:
            logger.warning("No QB tax codes found — tax will not be mapped")
            return {}

        # Detect if this is a US company.
        # US companies: line-level TaxCodeRef must be "TAX" / "NON".
        # International: line-level TaxCodeRef uses numeric TaxCode Id.
        is_us = self._is_us_company()

        taxable_code: dict | None = None
        non_taxable_code: dict | None = None

        for code in codes:
            code_id = str(code.get("Id", ""))
            code_name = code.get("Name", "")
            # QB uses "NON" as the standard non-taxable code
            if code_id == "NON" or "non" in code_name.lower() or "exempt" in code_name.lower():
                non_taxable_code = code
            else:
                # Pick the first taxable code (there's usually only one default)
                if taxable_code is None:
                    taxable_code = code

        result: dict = {}

        if taxable_code and not existing_taxable:
            # For US: store "TAX"; for intl: store the numeric Id
            tc_ref_value = "TAX" if is_us else str(taxable_code.get("Id", ""))
            tc_name = taxable_code.get("Name", "Tax")
            await self._save_entity_mapping(
                entity_type="tax_code",
                pos_entity_id=self._TAX_CODE_TAXABLE_POS_ID,
                pos_entity_name="Default Taxable",
                qb_entity_id=tc_ref_value,
                qb_entity_type="TaxCode",
                qb_entity_name=tc_name,
                qb_entity_ref=taxable_code,
            )
            result["taxable"] = tc_ref_value
            logger.info(
                "Mapped default taxable tax code → %s (%s) [US=%s]",
                tc_ref_value, tc_name, is_us,
            )

        if non_taxable_code and not existing_non:
            nt_ref_value = "NON" if is_us else str(non_taxable_code.get("Id", ""))
            nt_name = non_taxable_code.get("Name", "Non-Taxable")
            await self._save_entity_mapping(
                entity_type="tax_code",
                pos_entity_id=self._TAX_CODE_NON_TAXABLE_POS_ID,
                pos_entity_name="Non-Taxable",
                qb_entity_id=nt_ref_value,
                qb_entity_type="TaxCode",
                qb_entity_name=nt_name,
                qb_entity_ref=non_taxable_code,
            )
            result["non_taxable"] = nt_ref_value
            logger.info(
                "Mapped non-taxable tax code → %s (%s) [US=%s]",
                nt_ref_value, nt_name, is_us,
            )
        elif not existing_non:
            # If no explicit non-taxable code found, use "NON" for US (always available)
            if is_us:
                await self._save_entity_mapping(
                    entity_type="tax_code",
                    pos_entity_id=self._TAX_CODE_NON_TAXABLE_POS_ID,
                    pos_entity_name="Non-Taxable",
                    qb_entity_id="NON",
                    qb_entity_type="TaxCode",
                    qb_entity_name="Non-Taxable",
                )
                result["non_taxable"] = "NON"

        return result

    def _is_us_company(self) -> bool:
        """Check if the connected QB company is US-based.

        US companies require ``"TAX"``/``"NON"`` for line-level TaxCodeRef,
        while international companies use numeric TaxCode Ids.
        """
        company_info = self.connection.company_info or {}
        country = company_info.get("Country", company_info.get("country", ""))
        # QB US sandbox returns "US"; production may return "US" or "USA"
        return country.upper() in ("US", "USA", "")

    async def _get_default_tax_code_ref(self) -> dict | None:
        """Return ``{"value": "<QB TaxCode Id>"}`` for the default taxable code."""
        mapping = await self._get_entity_mapping(
            "tax_code", self._TAX_CODE_TAXABLE_POS_ID,
        )
        if mapping:
            return {"value": mapping.qb_entity_id}
        return None

    async def _get_non_taxable_code_ref(self) -> dict | None:
        """Return ``{"value": "<QB TaxCode Id>"}`` for the non-taxable code."""
        mapping = await self._get_entity_mapping(
            "tax_code", self._TAX_CODE_NON_TAXABLE_POS_ID,
        )
        if mapping:
            return {"value": mapping.qb_entity_id}
        return None

    # 19. Tax Agency ---------------------------------------------------

    async def sync_tax_agencies(self) -> list[dict]:
        """Create or find FBR and PRA as vendors in QB for tax reporting."""
        agencies: list[dict] = []
        for agency_name in ["Federal Board of Revenue (FBR)", "Punjab Revenue Authority (PRA)"]:
            slug = "fbr" if "FBR" in agency_name else "pra"
            agency_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"tax_agency:{self.tenant_id}:{slug}")

            existing = await self._get_entity_mapping("tax_agency", agency_id)
            if existing:
                agencies.append({"name": agency_name, "qb_id": existing.qb_entity_id})
                continue

            t0 = time.monotonic()
            try:
                payload = {
                    "DisplayName": agency_name,
                    "Active": True,
                    "Vendor1099": False,
                }
                response = await self.client.post("vendor", payload)
                elapsed = int((time.monotonic() - t0) * 1000)

                qb_id = response.get("Vendor", {}).get("Id", "")

                await self._save_entity_mapping(
                    entity_type="tax_agency",
                    pos_entity_id=agency_id,
                    pos_entity_name=agency_name,
                    qb_entity_id=qb_id,
                    qb_entity_type="Vendor",
                    qb_entity_name=agency_name,
                )

                await self._log_sync(
                    sync_type="tax_agency",
                    action="create",
                    status="success",
                    qb_entity_type="Vendor",
                    qb_entity_id=qb_id,
                    request_payload=payload,
                    response_payload=response,
                    duration_ms=elapsed,
                    http_method="POST",
                )
                agencies.append({"name": agency_name, "qb_id": qb_id})

            except Exception as exc:
                elapsed = int((time.monotonic() - t0) * 1000)
                await self._log_sync(
                    sync_type="tax_agency",
                    action="create",
                    status="failed",
                    error_message=str(exc),
                    duration_ms=elapsed,
                    http_method="POST",
                )
                logger.warning("Failed to sync tax agency %s: %s", agency_name, exc)

        return agencies

    # 20. Payment Method -----------------------------------------------

    async def sync_payment_methods(self) -> list[dict]:
        """Sync payment methods to QB: Cash, Credit Card, etc."""
        synced: list[dict] = []

        for pm_name in _PAYMENT_METHODS:
            pm_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"pm:{self.tenant_id}:{pm_name}")
            existing = await self._get_entity_mapping("payment_method", pm_id)
            if existing:
                synced.append({"name": pm_name, "qb_id": existing.qb_entity_id})
                continue

            t0 = time.monotonic()
            try:
                # Query QB for existing payment method by name
                pms = await self.client.query(
                    "PaymentMethod", where=f"Name = '{pm_name}'",
                )

                if pms:
                    qb_id = pms[0]["Id"]
                else:
                    payload = {"Name": pm_name, "Active": True}
                    response = await self.client.post("paymentmethod", payload)
                    qb_id = response.get("PaymentMethod", {}).get("Id", "")

                elapsed = int((time.monotonic() - t0) * 1000)

                await self._save_entity_mapping(
                    entity_type="payment_method",
                    pos_entity_id=pm_id,
                    pos_entity_name=pm_name,
                    qb_entity_id=qb_id,
                    qb_entity_type="PaymentMethod",
                    qb_entity_name=pm_name,
                )

                await self._log_sync(
                    sync_type="payment_method",
                    action="create",
                    status="success",
                    qb_entity_type="PaymentMethod",
                    qb_entity_id=qb_id,
                    duration_ms=elapsed,
                    http_method="POST",
                )
                synced.append({"name": pm_name, "qb_id": qb_id})

            except Exception as exc:
                elapsed = int((time.monotonic() - t0) * 1000)
                await self._log_sync(
                    sync_type="payment_method",
                    action="create",
                    status="failed",
                    error_message=str(exc),
                    duration_ms=elapsed,
                    http_method="POST",
                )
                logger.warning("Failed to sync payment method %s: %s", pm_name, exc)

        return synced

    # 21. Chart of Accounts --------------------------------------------

    async def sync_chart_of_accounts(self) -> list[dict]:
        """Fetch the QB Chart of Accounts for the mapping UI."""
        t0 = time.monotonic()
        try:
            accounts = await self.client.query(
                "Account", where="Active = true", max_results=1000,
            )
            elapsed = int((time.monotonic() - t0) * 1000)

            await self._log_sync(
                sync_type="chart_of_accounts",
                action="query",
                status="success",
                qb_entity_type="Account",
                duration_ms=elapsed,
            )
            return accounts

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="chart_of_accounts",
                action="query",
                status="failed",
                error_message=str(exc),
                duration_ms=elapsed,
            )
            raise

    # 22. Vendor -------------------------------------------------------

    async def sync_vendor(
        self,
        name: str,
        vendor_id: uuid.UUID | None = None,
        phone: str | None = None,
    ) -> str:
        """Sync or find a vendor in QB.  Returns QB vendor ID."""
        if vendor_id is None:
            vendor_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"vendor:{self.tenant_id}:{name}")

        existing = await self._get_entity_mapping("vendor", vendor_id)
        if existing:
            return existing.qb_entity_id

        t0 = time.monotonic()
        try:
            # Query by name
            vendors = await self.client.query(
                "Vendor", where=f"DisplayName = '{name}'",
            )

            if vendors:
                qb_id = vendors[0]["Id"]
                sync_token = vendors[0].get("SyncToken", "0")
            else:
                payload: dict = {"DisplayName": name, "Active": True}
                if phone:
                    payload["PrimaryPhone"] = {"FreeFormNumber": phone}

                response = await self.client.post("vendor", payload)
                qb_vendor = response.get("Vendor", {})
                qb_id = qb_vendor.get("Id", "")
                sync_token = qb_vendor.get("SyncToken", "0")

            elapsed = int((time.monotonic() - t0) * 1000)

            await self._save_entity_mapping(
                entity_type="vendor",
                pos_entity_id=vendor_id,
                pos_entity_name=name,
                qb_entity_id=qb_id,
                qb_entity_type="Vendor",
                qb_entity_name=name,
                qb_entity_ref={"Id": qb_id, "SyncToken": sync_token},
            )

            await self._log_sync(
                sync_type="vendor",
                action="create",
                status="success",
                qb_entity_type="Vendor",
                qb_entity_id=qb_id,
                duration_ms=elapsed,
                http_method="POST",
            )
            return qb_id

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="vendor",
                action="create",
                status="failed",
                error_message=str(exc),
                duration_ms=elapsed,
                http_method="POST",
            )
            raise

    # 23. Class (branch / location) ------------------------------------

    async def sync_class(
        self, name: str, class_id: uuid.UUID | None = None,
    ) -> str:
        """Sync a restaurant branch/location as a QB Class."""
        if class_id is None:
            class_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"class:{self.tenant_id}:{name}")

        existing = await self._get_entity_mapping("class_ref", class_id)
        if existing:
            return existing.qb_entity_id

        t0 = time.monotonic()
        try:
            classes = await self.client.query(
                "Class", where=f"Name = '{name}'",
            )

            if classes:
                qb_id = classes[0]["Id"]
            else:
                response = await self.client.post("class", {"Name": name, "Active": True})
                qb_id = response.get("Class", {}).get("Id", "")

            elapsed = int((time.monotonic() - t0) * 1000)

            await self._save_entity_mapping(
                entity_type="class_ref",
                pos_entity_id=class_id,
                pos_entity_name=name,
                qb_entity_id=qb_id,
                qb_entity_type="Class",
                qb_entity_name=name,
            )

            await self._log_sync(
                sync_type="class",
                action="create",
                status="success",
                qb_entity_type="Class",
                qb_entity_id=qb_id,
                duration_ms=elapsed,
            )
            return qb_id

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="class",
                action="create",
                status="failed",
                error_message=str(exc),
                duration_ms=elapsed,
            )
            raise

    # 24. Department ---------------------------------------------------

    async def sync_department(
        self, name: str, dept_id: uuid.UUID | None = None,
    ) -> str:
        """Sync a department (Kitchen, Bar, FOH) as a QB Department."""
        if dept_id is None:
            dept_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"dept:{self.tenant_id}:{name}")

        existing = await self._get_entity_mapping("department", dept_id)
        if existing:
            return existing.qb_entity_id

        t0 = time.monotonic()
        try:
            depts = await self.client.query(
                "Department", where=f"Name = '{name}'",
            )

            if depts:
                qb_id = depts[0]["Id"]
            else:
                response = await self.client.post(
                    "department", {"Name": name, "Active": True},
                )
                qb_id = response.get("Department", {}).get("Id", "")

            elapsed = int((time.monotonic() - t0) * 1000)

            await self._save_entity_mapping(
                entity_type="department",
                pos_entity_id=dept_id,
                pos_entity_name=name,
                qb_entity_id=qb_id,
                qb_entity_type="Department",
                qb_entity_name=name,
            )

            await self._log_sync(
                sync_type="department",
                action="create",
                status="success",
                qb_entity_type="Department",
                qb_entity_id=qb_id,
                duration_ms=elapsed,
            )
            return qb_id

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="department",
                action="create",
                status="failed",
                error_message=str(exc),
                duration_ms=elapsed,
            )
            raise

    # 25. Employee -----------------------------------------------------

    async def sync_employee(
        self, name: str, employee_id: uuid.UUID | None = None,
    ) -> str:
        """Sync a staff member as a QB Employee reference."""
        if employee_id is None:
            employee_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"emp:{self.tenant_id}:{name}")

        existing = await self._get_entity_mapping("employee", employee_id)
        if existing:
            return existing.qb_entity_id

        t0 = time.monotonic()
        try:
            emps = await self.client.query(
                "Employee", where=f"DisplayName = '{name}'",
            )

            if emps:
                qb_id = emps[0]["Id"]
            else:
                # QB Employee requires GivenName + FamilyName
                parts = name.split(" ", 1)
                given = parts[0]
                family = parts[1] if len(parts) > 1 else given

                response = await self.client.post("employee", {
                    "GivenName": given,
                    "FamilyName": family,
                    "DisplayName": name,
                    "Active": True,
                })
                qb_id = response.get("Employee", {}).get("Id", "")

            elapsed = int((time.monotonic() - t0) * 1000)

            await self._save_entity_mapping(
                entity_type="employee",
                pos_entity_id=employee_id,
                pos_entity_name=name,
                qb_entity_id=qb_id,
                qb_entity_type="Employee",
                qb_entity_name=name,
            )

            await self._log_sync(
                sync_type="employee",
                action="create",
                status="success",
                qb_entity_type="Employee",
                qb_entity_id=qb_id,
                duration_ms=elapsed,
            )
            return qb_id

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_sync(
                sync_type="employee",
                action="create",
                status="failed",
                error_message=str(exc),
                duration_ms=elapsed,
            )
            raise

    # =====================================================================
    # ORCHESTRATION
    # =====================================================================

    async def on_order_completed(self, order_id: uuid.UUID) -> None:
        """Called when an order is completed/paid.  Triggers real-time sync.

        1. Load order with items + modifiers
        2. Ensure customer exists in QB (sync if named)
        3. Ensure menu items exist in QB (sync any missing)
        4. Create Sales Receipt (or Invoice for credit accounts)
        5. Log everything
        """
        logger.info("on_order_completed triggered for order %s", order_id)

        order = await self._load_order(order_id)

        # Step 0: Ensure tax code mappings exist (one-time setup)
        try:
            await self.setup_tax_code_mapping()
        except Exception:
            logger.warning(
                "Failed to setup tax code mapping for order %s, continuing",
                order.order_number, exc_info=True,
            )

        # Step 1: Sync customer
        try:
            await self._resolve_customer_ref(order)
        except Exception:
            logger.warning(
                "Failed to sync customer for order %s, continuing with receipt",
                order.order_number, exc_info=True,
            )

        # Step 2: Ensure all menu items are mapped
        for item in order.items:
            mapping = await self._get_entity_mapping("menu_item", item.menu_item_id)
            if not mapping:
                try:
                    await self.sync_menu_item(item.menu_item_id)
                except Exception:
                    logger.warning(
                        "Failed to sync menu item %s for order %s, continuing",
                        item.menu_item_id, order.order_number, exc_info=True,
                    )

        # Step 3: Create the financial transaction
        # Use SalesReceipt for completed orders (paid or unpaid — payment
        # module is not yet built, so most orders are "unpaid" by default).
        # Only use Invoice if explicitly marked as credit/corporate in future.
        if order.payment_status in ("paid", "unpaid"):
            await self.sync_order_as_sales_receipt(order)
        else:
            # Explicitly partial/refunded → Invoice for tracking
            await self.sync_order_as_invoice(order)

        # Update connection's last_sync timestamp
        self.connection.last_sync_at = datetime.now(timezone.utc)
        self.connection.last_sync_status = "success"
        await self.db.flush()

    async def on_order_voided(self, order_id: uuid.UUID) -> None:
        """Called when an order is voided.  Creates Credit Memo in QB."""
        logger.info("on_order_voided triggered for order %s", order_id)

        order = await self._load_order(order_id)

        # Only create credit memo if the original was synced
        original_mapping = await self._get_entity_mapping("order", order.id)
        if not original_mapping:
            logger.info(
                "Order %s was never synced to QB, skipping void sync",
                order.order_number,
            )
            return

        await self.sync_void_as_credit_memo(order)

        self.connection.last_sync_at = datetime.now(timezone.utc)
        self.connection.last_sync_status = "success"
        await self.db.flush()

    async def run_full_sync(self, batch_id: uuid.UUID | None = None) -> dict:
        """Full sync: entities first, then all unsynced completed orders.

        Returns summary dict with counts per entity type.
        """
        if batch_id is None:
            batch_id = uuid.uuid4()

        summary: dict[str, int] = {
            "categories": 0,
            "menu_items": 0,
            "customers": 0,
            "payment_methods": 0,
            "tax_codes": 0,
            "orders": 0,
            "errors": 0,
        }

        logger.info("Starting full sync (batch %s) for tenant %s", batch_id, self.tenant_id)

        # 1. Payment methods
        try:
            methods = await self.sync_payment_methods()
            summary["payment_methods"] = len(methods)
        except Exception:
            summary["errors"] += 1
            logger.error("Full sync: payment methods failed", exc_info=True)

        # 2. Tax codes (read-only)
        try:
            codes = await self.sync_tax_codes()
            summary["tax_codes"] = len(codes)
        except Exception:
            summary["errors"] += 1
            logger.error("Full sync: tax codes failed", exc_info=True)

        # 3. Categories
        cat_result = await self.db.execute(
            select(Category).where(
                Category.tenant_id == self.tenant_id,
                Category.is_active == True,  # noqa: E712
            )
        )
        categories = list(cat_result.scalars().all())
        for cat in categories:
            try:
                await self.sync_category(cat.id)
                summary["categories"] += 1
            except Exception:
                summary["errors"] += 1
                logger.warning("Full sync: category %s failed", cat.name, exc_info=True)

        # 4. Menu items
        item_result = await self.db.execute(
            select(MenuItem).where(
                MenuItem.tenant_id == self.tenant_id,
                MenuItem.is_available == True,  # noqa: E712
            )
        )
        items = list(item_result.scalars().all())
        for item in items:
            try:
                await self.sync_menu_item(item.id)
                summary["menu_items"] += 1
            except Exception:
                summary["errors"] += 1
                logger.warning("Full sync: item %s failed", item.name, exc_info=True)

        # 5. Completed orders not yet synced
        synced_order_ids_result = await self.db.execute(
            select(QBEntityMapping.pos_entity_id).where(
                QBEntityMapping.tenant_id == self.tenant_id,
                QBEntityMapping.connection_id == self.connection.id,
                QBEntityMapping.entity_type == "order",
            )
        )
        synced_ids = set(synced_order_ids_result.scalars().all())

        order_result = await self.db.execute(
            select(Order)
            .options(
                selectinload(Order.items).selectinload(OrderItem.modifiers),
                selectinload(Order.table),
                selectinload(Order.creator),
            )
            .where(
                Order.tenant_id == self.tenant_id,
                Order.status == "completed",
            )
            .order_by(Order.created_at)
        )
        orders = list(order_result.scalars().unique().all())

        for order in orders:
            if order.id in synced_ids:
                continue
            try:
                await self.sync_order_as_sales_receipt(order)
                summary["orders"] += 1
            except Exception:
                summary["errors"] += 1
                logger.warning(
                    "Full sync: order %s failed", order.order_number, exc_info=True,
                )

        # Update connection
        self.connection.last_sync_at = datetime.now(timezone.utc)
        self.connection.last_sync_status = "success" if summary["errors"] == 0 else "partial"
        await self.db.flush()

        await self._log_sync(
            sync_type="full_sync",
            action="create",
            status="success" if summary["errors"] == 0 else "partial",
            response_payload=summary,
            batch_id=batch_id,
        )

        logger.info("Full sync complete (batch %s): %s", batch_id, summary)
        return summary

    async def run_daily_close(self, date: datetime) -> dict:
        """End-of-day: create daily summary journal entry + bank deposit.

        Returns summary dict with journal entry and deposit results.
        """
        result: dict = {"journal_entry": None, "deposit": None, "errors": []}

        # 1. Journal Entry
        try:
            je = await self.create_daily_summary(date)
            result["journal_entry"] = (
                je.get("JournalEntry", {}).get("Id") if je else "skipped"
            )
        except Exception as exc:
            result["errors"].append(f"Journal entry: {exc}")
            logger.error("Daily close: journal entry failed", exc_info=True)

        # 2. Calculate totals for deposit
        target_date = date.date() if isinstance(date, datetime) else date
        total_result = await self.db.execute(
            select(func.sum(Order.total)).where(
                Order.tenant_id == self.tenant_id,
                Order.status == "completed",
                func.cast(Order.created_at, Date) == target_date,
            )
        )
        total_collected = total_result.scalar_one_or_none() or 0

        if total_collected > 0:
            # Simplified split: assume 70% cash, 30% card for now
            # A real implementation would query the payments table
            cash_est = int(total_collected * 0.7)
            card_est = total_collected - cash_est

            try:
                dep = await self.create_daily_deposit(date, cash_est, card_est)
                result["deposit"] = (
                    dep.get("Deposit", {}).get("Id") if dep else "skipped"
                )
            except Exception as exc:
                result["errors"].append(f"Deposit: {exc}")
                logger.error("Daily close: deposit failed", exc_info=True)

        self.connection.last_sync_at = datetime.now(timezone.utc)
        self.connection.last_sync_status = "success" if not result["errors"] else "partial"
        await self.db.flush()

        logger.info("Daily close for %s: %s", target_date, result)
        return result


# ---------------------------------------------------------------------------
# Preview / Simulation (standalone — no QBConnection required)
# ---------------------------------------------------------------------------

async def build_preview_sales_receipt(
    order: "Order",
    template_mappings: list[dict],
) -> dict:
    """Build a QB Sales Receipt payload using template mappings (no live QB).

    This mirrors ``SyncService.sync_order_as_sales_receipt`` but substitutes
    simulated account IDs derived from the template rather than querying the
    database for real QB account/entity mappings.

    Parameters
    ----------
    order:
        An Order ORM object with ``items`` and their ``modifiers`` eagerly loaded.
    template_mappings:
        List of mapping dicts from a template (each has mapping_type, name,
        account_type, account_sub_type, is_default, description).
    """
    # Index template mappings by type (pick the default for each type)
    defaults: dict[str, dict] = {}
    for mapping in template_mappings:
        mtype = mapping["mapping_type"]
        if mapping.get("is_default") and mtype not in defaults:
            defaults[mtype] = mapping
        # fallback: first mapping of that type if no default flagged
        if mtype not in defaults:
            defaults[mtype] = mapping

    def _sim_ref(mapping_type: str) -> dict | None:
        m = defaults.get(mapping_type)
        if not m:
            return None
        return {"value": f"SIM-{mapping_type}", "name": m["name"]}

    # Build line items
    lines: list[dict] = []
    line_num = 1
    for item in order.items:
        description = item.name
        if item.modifiers:
            mod_names = [m.name for m in item.modifiers]
            description += f" ({', '.join(mod_names)})"
        if item.notes:
            description += f" -- {item.notes}"

        line: dict = {
            "Id": str(line_num),
            "LineNum": line_num,
            "Amount": paisa_to_decimal(item.total),
            "Description": description,
            "DetailType": "SalesItemLineDetail",
            "SalesItemLineDetail": {
                "Qty": item.quantity,
                "UnitPrice": paisa_to_decimal(item.unit_price),
            },
        }
        income_ref = _sim_ref("income")
        if income_ref:
            line["SalesItemLineDetail"]["ItemAccountRef"] = income_ref
        lines.append(line)
        line_num += 1

    # Discount line
    if order.discount_amount and order.discount_amount > 0:
        lines.append({
            "Id": str(line_num),
            "LineNum": line_num,
            "Amount": paisa_to_decimal(order.discount_amount),
            "DetailType": "DiscountLineDetail",
            "DiscountLineDetail": {
                "PercentBased": False,
                "DiscountPercent": 0,
            },
        })

    order_label = _ORDER_TYPE_LABELS.get(order.order_type, order.order_type)
    txn_date = order.created_at.strftime("%Y-%m-%d")

    payload: dict = {
        "DocNumber": order.order_number,
        "TxnDate": txn_date,
        "Line": lines,
        "TxnTaxDetail": {
            "TotalTax": paisa_to_decimal(order.tax_amount),
        },
        "CustomerRef": {"value": "SIM-customer", "name": order.customer_name or "Walk-In Customer"},
        "TotalAmt": paisa_to_decimal(order.total),
        "PrivateNote": (
            f"{order_label} order {order.order_number}"
            f"{(' - ' + order.notes) if order.notes else ''}"
        ),
        "CustomerMemo": {
            "value": f"Thank you for dining with us! Order #{order.order_number}",
        },
        "PrintStatus": "NeedToPrint",
        "EmailStatus": "NotSet",
    }

    # Bank / deposit
    bank_ref = _sim_ref("bank")
    if bank_ref:
        payload["DepositToAccountRef"] = bank_ref

    # Payment method (simulate Cash)
    payload["PaymentMethodRef"] = {"value": "SIM-payment", "name": "Cash"}

    return payload
