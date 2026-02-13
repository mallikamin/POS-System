"""Async HTTP client for QuickBooks Online REST API v3.

Wraps httpx to provide typed, entity-unwrapped access to every QB endpoint
the POS system needs.  All calls go through ``_request()`` which handles
auth headers, minor-version pinning, structured error parsing, and logging.

Usage::

    client = QBClient(connection, db)
    receipt = await client.create_sales_receipt(receipt_data)
    items   = await client.query("Item", where="Type = 'Service'")
"""

import logging
import time
import uuid
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.quickbooks import QBConnection
from app.services.quickbooks.oauth import ensure_valid_token

logger = logging.getLogger(__name__)

QB_API_MINOR_VERSION = 73
_REQUEST_TIMEOUT = 30.0  # seconds


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class QBAPIError(Exception):
    """Raised when the QuickBooks API returns an error response.

    Attributes:
        status_code: HTTP status code from QB.
        qb_error_code: QuickBooks-specific error code string (e.g. "6240").
        message: Human-readable error summary.
        detail: Extended detail string from QB, when available.
        raw: Full parsed JSON body so callers can inspect ``Fault``.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 0,
        qb_error_code: str = "",
        detail: str = "",
        raw: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self.qb_error_code = qb_error_code
        self.message = message
        self.detail = detail
        self.raw = raw or {}
        super().__init__(self._format())

    def _format(self) -> str:
        parts = [f"QB API Error {self.status_code}"]
        if self.qb_error_code:
            parts[0] += f" (code {self.qb_error_code})"
        parts.append(f": {self.message}")
        if self.detail:
            parts.append(f" -- {self.detail}")
        return "".join(parts)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class QBClient:
    """Async client for QuickBooks Online API v3.

    One instance per request/job -- holds a ``QBConnection`` and a DB session
    so it can transparently refresh OAuth tokens via ``ensure_valid_token()``.

    Usage::

        client = QBClient(connection, db)
        receipt = await client.create_sales_receipt(data)
    """

    def __init__(self, connection: QBConnection, db: AsyncSession) -> None:
        self.connection = connection
        self.db = db
        self.realm_id: str = connection.realm_id
        self.base_url: str = (
            f"{settings.qb_base_url}/v3/company/{connection.realm_id}"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_headers(self) -> dict[str, str]:
        """Return auth headers with a valid (possibly refreshed) access token."""
        token = await ensure_valid_token(self.connection, self.db)
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        data: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Make an authenticated request to the QuickBooks API.

        * Injects ``minorversion`` query param on every call.
        * Parses QB ``Fault`` envelope into a structured ``QBAPIError``.
        * Logs request/response at DEBUG level for diagnostics.

        Returns the parsed JSON body as a dict.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = await self._get_headers()

        merged_params = {"minorversion": str(QB_API_MINOR_VERSION)}
        if params:
            merged_params.update(params)

        request_id = uuid.uuid4().hex[:12]
        logger.debug(
            "[%s] QB %s %s params=%s body_keys=%s",
            request_id,
            method.upper(),
            url,
            merged_params,
            list(data.keys()) if data else None,
        )

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as http:
            response = await http.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=data,
                params=merged_params,
            )
        elapsed_ms = int((time.monotonic() - start) * 1000)

        logger.debug(
            "[%s] QB response %d (%dms) content_length=%d",
            request_id,
            response.status_code,
            elapsed_ms,
            len(response.content),
        )

        # -- Parse body (QB always returns JSON, even on errors) ----------
        try:
            body: dict = response.json()
        except Exception:
            # Non-JSON body -- unusual, but possible on 5xx gateway errors.
            if response.is_success:
                return {}
            raise QBAPIError(
                f"Non-JSON response from QuickBooks ({response.status_code})",
                status_code=response.status_code,
                detail=response.text[:500],
            )

        # -- Handle QB Fault envelope -------------------------------------
        if "Fault" in body:
            fault = body["Fault"]
            errors = fault.get("Error", [])
            first = errors[0] if errors else {}
            qb_code = first.get("code", "")
            message = first.get("Message", "Unknown QuickBooks error")
            detail = first.get("Detail", "")

            logger.warning(
                "[%s] QB Fault code=%s message=%s detail=%s",
                request_id,
                qb_code,
                message,
                detail,
            )
            raise QBAPIError(
                message,
                status_code=response.status_code,
                qb_error_code=qb_code,
                detail=detail,
                raw=body,
            )

        # -- Handle non-Fault HTTP errors (rare but possible) -------------
        if not response.is_success:
            raise QBAPIError(
                f"HTTP {response.status_code} from QuickBooks",
                status_code=response.status_code,
                detail=response.text[:500],
                raw=body,
            )

        return body

    # Convenience wrappers for CRUD verbs ---------------------------------

    async def _get(self, endpoint: str, **kwargs: Any) -> dict:
        return await self._request("GET", endpoint, **kwargs)

    async def _post(self, endpoint: str, data: dict, **kwargs: Any) -> dict:
        return await self._request("POST", endpoint, data=data, **kwargs)

    # ------------------------------------------------------------------
    # Generic public methods (used by SyncService and MappingService)
    # ------------------------------------------------------------------

    async def post(self, endpoint: str, data: dict, **kwargs: Any) -> dict:
        """Public POST — returns the full raw QB response body.

        Unlike the typed convenience methods (create_sales_receipt, etc.)
        this does NOT unwrap the entity from its wrapper key, so callers
        can inspect the full response (e.g. ``response["SalesReceipt"]``).
        """
        return await self._post(endpoint, data, **kwargs)

    async def create(self, entity: str, data: dict, **kwargs: Any) -> dict:
        """Create any QB entity by endpoint name. Returns raw response."""
        return await self._post(entity, data, **kwargs)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def query(
        self,
        entity: str,
        where: str | None = None,
        order_by: str | None = None,
        start_position: int = 1,
        max_results: int = 1000,
    ) -> list[dict]:
        """Execute a QB query (SQL-like syntax).

        Example::

            items = await client.query(
                "Item",
                where="Type = 'Service'",
                order_by="Name",
            )

        Returns a (possibly empty) list of entity dicts.
        """
        stmt = f"SELECT * FROM {entity}"
        if where:
            stmt += f" WHERE {where}"
        if order_by:
            stmt += f" ORDERBY {order_by}"
        stmt += f" STARTPOSITION {start_position} MAXRESULTS {max_results}"

        body = await self._get("query", params={"query": stmt})
        qr: dict = body.get("QueryResponse", {})
        return qr.get(entity, [])

    # ------------------------------------------------------------------
    # Chart of Accounts
    # ------------------------------------------------------------------

    async def get_accounts(self) -> list[dict]:
        """Fetch all accounts from the Chart of Accounts."""
        return await self.query("Account")

    async def create_account(
        self,
        name: str,
        account_type: str,
        account_sub_type: str | None = None,
        description: str | None = None,
    ) -> dict:
        """Create a new account in the Chart of Accounts."""
        payload: dict[str, Any] = {
            "Name": name,
            "AccountType": account_type,
        }
        if account_sub_type:
            payload["AccountSubType"] = account_sub_type
        if description:
            payload["Description"] = description

        body = await self._post("account", data=payload)
        return body.get("Account", body)

    async def get_account(self, account_id: str) -> dict:
        """Get a specific account by its QuickBooks ID."""
        body = await self._get(f"account/{account_id}")
        return body.get("Account", body)

    # ------------------------------------------------------------------
    # Customers
    # ------------------------------------------------------------------

    async def create_customer(
        self,
        display_name: str,
        phone: str | None = None,
        email: str | None = None,
        notes: str | None = None,
    ) -> dict:
        """Create a new customer."""
        payload: dict[str, Any] = {"DisplayName": display_name}
        if phone:
            payload["PrimaryPhone"] = {"FreeFormNumber": phone}
        if email:
            payload["PrimaryEmailAddr"] = {"Address": email}
        if notes:
            payload["Notes"] = notes

        body = await self._post("customer", data=payload)
        return body.get("Customer", body)

    async def get_customer(self, customer_id: str) -> dict:
        """Get a customer by QuickBooks ID."""
        body = await self._get(f"customer/{customer_id}")
        return body.get("Customer", body)

    async def find_customer(self, display_name: str) -> dict | None:
        """Find a customer by exact display name. Returns ``None`` if not found."""
        escaped = display_name.replace("'", "\\'")
        results = await self.query(
            "Customer", where=f"DisplayName = '{escaped}'"
        )
        return results[0] if results else None

    # ------------------------------------------------------------------
    # Items (Products / Services)
    # ------------------------------------------------------------------

    async def create_item(
        self,
        name: str,
        item_type: str = "Service",
        unit_price: float = 0,
        income_account_id: str | None = None,
        description: str | None = None,
        sku: str | None = None,
    ) -> dict:
        """Create a new Item (product or service) in QuickBooks."""
        payload: dict[str, Any] = {
            "Name": name,
            "Type": item_type,
            "UnitPrice": unit_price,
        }
        if income_account_id:
            payload["IncomeAccountRef"] = {"value": income_account_id}
        if description:
            payload["Description"] = description
        if sku:
            payload["Sku"] = sku

        body = await self._post("item", data=payload)
        return body.get("Item", body)

    async def update_item(
        self, item_id: str, sync_token: str, **updates: Any
    ) -> dict:
        """Update an existing item.

        ``sync_token`` is required by QB for optimistic concurrency control.
        ``**updates`` should be QB-field-cased keys (e.g. ``Name``, ``UnitPrice``).
        """
        payload: dict[str, Any] = {
            "Id": item_id,
            "SyncToken": sync_token,
            **updates,
        }
        body = await self._post("item", data=payload)
        return body.get("Item", body)

    async def get_item(self, item_id: str) -> dict:
        """Get an item by QuickBooks ID."""
        body = await self._get(f"item/{item_id}")
        return body.get("Item", body)

    async def find_item(self, name: str) -> dict | None:
        """Find an item by exact name. Returns ``None`` if not found."""
        escaped = name.replace("'", "\\'")
        results = await self.query("Item", where=f"Name = '{escaped}'")
        return results[0] if results else None

    # ------------------------------------------------------------------
    # Tax Codes
    # ------------------------------------------------------------------

    async def get_tax_codes(self) -> list[dict]:
        """Fetch all tax codes."""
        return await self.query("TaxCode")

    async def get_tax_code(self, tax_code_id: str) -> dict:
        """Get a specific tax code by QuickBooks ID."""
        body = await self._get(f"taxcode/{tax_code_id}")
        return body.get("TaxCode", body)

    # ------------------------------------------------------------------
    # Payment Methods
    # ------------------------------------------------------------------

    async def get_payment_methods(self) -> list[dict]:
        """Fetch all payment methods."""
        return await self.query("PaymentMethod")

    async def create_payment_method(
        self, name: str, payment_type: str = "NON_CREDIT_CARD"
    ) -> dict:
        """Create a new payment method."""
        payload: dict[str, Any] = {"Name": name, "Type": payment_type}
        body = await self._post("paymentmethod", data=payload)
        return body.get("PaymentMethod", body)

    # ------------------------------------------------------------------
    # Sales Receipt (cash / immediate orders)
    # ------------------------------------------------------------------

    async def create_sales_receipt(self, data: dict) -> dict:
        """Create a Sales Receipt. ``data`` must follow the QB SalesReceipt schema."""
        body = await self._post("salesreceipt", data=data)
        return body.get("SalesReceipt", body)

    async def void_sales_receipt(
        self, receipt_id: str, sync_token: str
    ) -> dict:
        """Void a Sales Receipt (irreversible)."""
        payload: dict[str, Any] = {
            "Id": receipt_id,
            "SyncToken": sync_token,
        }
        body = await self._post(
            "salesreceipt",
            data=payload,
            params={"operation": "void"},
        )
        return body.get("SalesReceipt", body)

    async def get_sales_receipt(self, receipt_id: str) -> dict:
        """Get a Sales Receipt by QuickBooks ID."""
        body = await self._get(f"salesreceipt/{receipt_id}")
        return body.get("SalesReceipt", body)

    # ------------------------------------------------------------------
    # Invoice (credit / account orders)
    # ------------------------------------------------------------------

    async def create_invoice(self, data: dict) -> dict:
        """Create an Invoice."""
        body = await self._post("invoice", data=data)
        return body.get("Invoice", body)

    async def void_invoice(self, invoice_id: str, sync_token: str) -> dict:
        """Void an Invoice."""
        payload: dict[str, Any] = {
            "Id": invoice_id,
            "SyncToken": sync_token,
        }
        body = await self._post(
            "invoice",
            data=payload,
            params={"operation": "void"},
        )
        return body.get("Invoice", body)

    async def get_invoice(self, invoice_id: str) -> dict:
        """Get an Invoice by QuickBooks ID."""
        body = await self._get(f"invoice/{invoice_id}")
        return body.get("Invoice", body)

    # ------------------------------------------------------------------
    # Payment (against invoices)
    # ------------------------------------------------------------------

    async def create_payment(self, data: dict) -> dict:
        """Create a Payment (applied against one or more invoices)."""
        body = await self._post("payment", data=data)
        return body.get("Payment", body)

    async def get_payment(self, payment_id: str) -> dict:
        """Get a Payment by QuickBooks ID."""
        body = await self._get(f"payment/{payment_id}")
        return body.get("Payment", body)

    # ------------------------------------------------------------------
    # Credit Memo (voids / credits)
    # ------------------------------------------------------------------

    async def create_credit_memo(self, data: dict) -> dict:
        """Create a Credit Memo."""
        body = await self._post("creditmemo", data=data)
        return body.get("CreditMemo", body)

    async def get_credit_memo(self, memo_id: str) -> dict:
        """Get a Credit Memo by QuickBooks ID."""
        body = await self._get(f"creditmemo/{memo_id}")
        return body.get("CreditMemo", body)

    # ------------------------------------------------------------------
    # Refund Receipt
    # ------------------------------------------------------------------

    async def create_refund_receipt(self, data: dict) -> dict:
        """Create a Refund Receipt."""
        body = await self._post("refundreceipt", data=data)
        return body.get("RefundReceipt", body)

    async def get_refund_receipt(self, receipt_id: str) -> dict:
        """Get a Refund Receipt by QuickBooks ID."""
        body = await self._get(f"refundreceipt/{receipt_id}")
        return body.get("RefundReceipt", body)

    # ------------------------------------------------------------------
    # Journal Entry (daily summaries)
    # ------------------------------------------------------------------

    async def create_journal_entry(self, data: dict) -> dict:
        """Create a Journal Entry (e.g. daily POS summary)."""
        body = await self._post("journalentry", data=data)
        return body.get("JournalEntry", body)

    async def get_journal_entry(self, entry_id: str) -> dict:
        """Get a Journal Entry by QuickBooks ID."""
        body = await self._get(f"journalentry/{entry_id}")
        return body.get("JournalEntry", body)

    # ------------------------------------------------------------------
    # Deposit
    # ------------------------------------------------------------------

    async def create_deposit(self, data: dict) -> dict:
        """Create a Deposit."""
        body = await self._post("deposit", data=data)
        return body.get("Deposit", body)

    async def get_deposit(self, deposit_id: str) -> dict:
        """Get a Deposit by QuickBooks ID."""
        body = await self._get(f"deposit/{deposit_id}")
        return body.get("Deposit", body)

    # ------------------------------------------------------------------
    # Estimate (catering quotes)
    # ------------------------------------------------------------------

    async def create_estimate(self, data: dict) -> dict:
        """Create an Estimate (e.g. catering quote)."""
        body = await self._post("estimate", data=data)
        return body.get("Estimate", body)

    async def get_estimate(self, estimate_id: str) -> dict:
        """Get an Estimate by QuickBooks ID."""
        body = await self._get(f"estimate/{estimate_id}")
        return body.get("Estimate", body)

    # ------------------------------------------------------------------
    # Bill (supplier invoices)
    # ------------------------------------------------------------------

    async def create_bill(self, data: dict) -> dict:
        """Create a Bill (accounts payable)."""
        body = await self._post("bill", data=data)
        return body.get("Bill", body)

    async def get_bill(self, bill_id: str) -> dict:
        """Get a Bill by QuickBooks ID."""
        body = await self._get(f"bill/{bill_id}")
        return body.get("Bill", body)

    # ------------------------------------------------------------------
    # Bill Payment
    # ------------------------------------------------------------------

    async def create_bill_payment(self, data: dict) -> dict:
        """Create a Bill Payment."""
        body = await self._post("billpayment", data=data)
        return body.get("BillPayment", body)

    # ------------------------------------------------------------------
    # Purchase Order
    # ------------------------------------------------------------------

    async def create_purchase_order(self, data: dict) -> dict:
        """Create a Purchase Order."""
        body = await self._post("purchaseorder", data=data)
        return body.get("PurchaseOrder", body)

    async def get_purchase_order(self, po_id: str) -> dict:
        """Get a Purchase Order by QuickBooks ID."""
        body = await self._get(f"purchaseorder/{po_id}")
        return body.get("PurchaseOrder", body)

    # ------------------------------------------------------------------
    # Transfer
    # ------------------------------------------------------------------

    async def create_transfer(self, data: dict) -> dict:
        """Create a Transfer between bank accounts."""
        body = await self._post("transfer", data=data)
        return body.get("Transfer", body)

    # ------------------------------------------------------------------
    # Vendor
    # ------------------------------------------------------------------

    async def create_vendor(
        self,
        display_name: str,
        phone: str | None = None,
        email: str | None = None,
    ) -> dict:
        """Create a new Vendor."""
        payload: dict[str, Any] = {"DisplayName": display_name}
        if phone:
            payload["PrimaryPhone"] = {"FreeFormNumber": phone}
        if email:
            payload["PrimaryEmailAddr"] = {"Address": email}

        body = await self._post("vendor", data=payload)
        return body.get("Vendor", body)

    async def find_vendor(self, display_name: str) -> dict | None:
        """Find a vendor by exact display name. Returns ``None`` if not found."""
        escaped = display_name.replace("'", "\\'")
        results = await self.query(
            "Vendor", where=f"DisplayName = '{escaped}'"
        )
        return results[0] if results else None

    # ------------------------------------------------------------------
    # Vendor Credit
    # ------------------------------------------------------------------

    async def create_vendor_credit(self, data: dict) -> dict:
        """Create a Vendor Credit."""
        body = await self._post("vendorcredit", data=data)
        return body.get("VendorCredit", body)

    # ------------------------------------------------------------------
    # Company Info
    # ------------------------------------------------------------------

    async def get_company_info(self) -> dict:
        """Fetch company info (name, country, currency, fiscal year).

        QB wraps this as ``{"CompanyInfo": {...}}`` with the realm_id
        as the resource path.
        """
        body = await self._get(f"companyinfo/{self.realm_id}")
        return body.get("CompanyInfo", body)

    # ------------------------------------------------------------------
    # Class (location / branch tracking)
    # ------------------------------------------------------------------

    async def create_class(
        self, name: str, parent_id: str | None = None
    ) -> dict:
        """Create a Class (used for location/branch tracking in reports)."""
        payload: dict[str, Any] = {"Name": name}
        if parent_id:
            payload["ParentRef"] = {"value": parent_id}

        body = await self._post("class", data=payload)
        return body.get("Class", body)

    async def get_classes(self) -> list[dict]:
        """Fetch all classes."""
        return await self.query("Class")

    # ------------------------------------------------------------------
    # Department
    # ------------------------------------------------------------------

    async def create_department(
        self, name: str, parent_id: str | None = None
    ) -> dict:
        """Create a Department."""
        payload: dict[str, Any] = {"Name": name}
        if parent_id:
            payload["ParentRef"] = {"value": parent_id}

        body = await self._post("department", data=payload)
        return body.get("Department", body)

    async def get_departments(self) -> list[dict]:
        """Fetch all departments."""
        return await self.query("Department")
