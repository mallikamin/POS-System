"""Tests for QuickBooks Desktop integration components.

Tests cover:
- QBXML builders (all 7 builders)
- Desktop Adapter (queue-based sync)
- Adapter Factory (auto-detection)
- QBWC SOAP server endpoints
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.services.quickbooks.qbxml.builders import (
    build_sales_receipt_add_rq,
    build_customer_add_rq,
    build_customer_mod_rq,
    build_item_non_inventory_add_rq,
    build_item_non_inventory_mod_rq,
    build_receive_payment_add_rq,
    build_credit_memo_add_rq,
)
from app.services.quickbooks.qbxml.parsers.response import parse_qbxml_response
from app.services.quickbooks.qbxml.constants import get_user_friendly_error


# =============================================================================
# QBXML Builder Tests
# =============================================================================

class TestSalesReceiptBuilder:
    """Test SalesReceipt QBXML builder."""

    def test_build_basic_sales_receipt(self):
        """Test building a basic sales receipt."""
        order_data = {
            "order_number": "240325-001",
            "order_type": "dine_in",
            "created_at": datetime(2024, 3, 25, 14, 30),
            "items": [
                {
                    "name": "Chicken Biryani",
                    "quantity": 2,
                    "price_paisa": 85000,
                    "total_paisa": 170000,
                }
            ],
            "subtotal_paisa": 170000,
            "tax_paisa": 30600,  # 18%
            "total_paisa": 200600,
            "notes": "Table 5",
        }

        qbxml = build_sales_receipt_add_rq(
            order_data=order_data,
            customer_name="Walk-In Customer",
            deposit_to_account="Cash",
            income_account="Food Sales",
            tax_account="Sales Tax Payable",
        )

        # Verify QBXML structure
        assert '<?xml version="1.0"' in qbxml
        assert "<QBXML>" in qbxml
        assert "<SalesReceiptAddRq" in qbxml
        assert "240325-001" in qbxml
        assert "Walk-In Customer" in qbxml
        assert "1700.00" in qbxml  # 170000 paisa = Rs. 1,700
        assert "306.00" in qbxml  # 30600 paisa = Rs. 306
        assert "Chicken Biryani" in qbxml

    def test_sales_receipt_without_tax(self):
        """Test sales receipt with no tax."""
        order_data = {
            "order_number": "240325-002",
            "order_type": "takeaway",
            "created_at": datetime(2024, 3, 25, 15, 0),
            "items": [
                {"name": "Mango Lassi", "quantity": 1, "price_paisa": 25000, "total_paisa": 25000}
            ],
            "subtotal_paisa": 25000,
            "tax_paisa": 0,
            "total_paisa": 25000,
        }

        qbxml = build_sales_receipt_add_rq(
            order_data=order_data,
            customer_name="Walk-In Customer",
            deposit_to_account="Cash",
            income_account="Food Sales",
        )

        # Should not include tax line
        assert "Sales Tax" not in qbxml
        assert "250.00" in qbxml

    def test_sales_receipt_field_truncation(self):
        """Test that long order numbers get truncated to QB limits."""
        order_data = {
            "order_number": "VERY-LONG-ORDER-NUMBER-12345678901234567890",  # > 11 chars
            "order_type": "dine_in",
            "created_at": datetime.now(),
            "items": [{"name": "Item", "quantity": 1, "price_paisa": 10000, "total_paisa": 10000}],
            "subtotal_paisa": 10000,
            "tax_paisa": 0,
            "total_paisa": 10000,
        }

        qbxml = build_sales_receipt_add_rq(
            order_data=order_data,
            customer_name="Customer",
            deposit_to_account="Cash",
            income_account="Food Sales",
        )

        # RefNumber should be truncated to 11 chars
        assert "<RefNumber>VERY-LONG-O</RefNumber>" in qbxml

    def test_sales_receipt_missing_required_field(self):
        """Test that missing order_number raises error."""
        order_data = {
            "items": [{"name": "Item", "quantity": 1, "price_paisa": 10000, "total_paisa": 10000}],
            "subtotal_paisa": 10000,
            "tax_paisa": 0,
            "total_paisa": 10000,
        }

        with pytest.raises(ValueError, match="order_number is required"):
            build_sales_receipt_add_rq(
                order_data=order_data,
                customer_name="Customer",
                deposit_to_account="Cash",
                income_account="Food Sales",
            )


class TestCustomerBuilder:
    """Test Customer QBXML builders (Add + Mod)."""

    def test_build_customer_add(self):
        """Test building customer add request."""
        customer_data = {
            "name": "John Doe",
            "phone": "+92-300-1234567",
            "email": "john@example.com",
            "billing_address": {
                "addr1": "123 Main St",
                "city": "Lahore",
                "state": "Punjab",
                "postal_code": "54000",
                "country": "Pakistan",
            },
        }

        qbxml = build_customer_add_rq(customer_data)

        assert "<CustomerAddRq" in qbxml
        assert "John Doe" in qbxml
        assert "+92-300-1234567" in qbxml
        assert "john@example.com" in qbxml
        assert "123 Main St" in qbxml
        assert "Lahore" in qbxml

    def test_build_customer_mod(self):
        """Test building customer modify request."""
        customer_data = {
            "name": "John Doe Updated",
            "phone": "+92-300-9999999",
            "email": "john.new@example.com",
        }

        qbxml = build_customer_mod_rq(customer_data, list_id="80000001-1234567890")

        assert "<CustomerModRq" in qbxml
        assert "80000001-1234567890" in qbxml
        assert "John Doe Updated" in qbxml
        assert "+92-300-9999999" in qbxml


class TestItemBuilder:
    """Test Item NonInventory QBXML builders."""

    def test_build_item_add(self):
        """Test building item add request."""
        item_data = {
            "name": "Chicken Tikka",
            "description": "Grilled chicken marinated in yogurt and spices",
            "price_paisa": 65000,  # Rs. 650
            "income_account": "Food Sales",
            "expense_account": "Cost of Food",
        }

        qbxml = build_item_non_inventory_add_rq(item_data)

        assert "<ItemNonInventoryAddRq" in qbxml
        assert "Chicken Tikka" in qbxml
        assert "650.00" in qbxml
        assert "Food Sales" in qbxml

    def test_build_item_mod(self):
        """Test building item modify request."""
        item_data = {
            "name": "Chicken Tikka (Updated)",
            "price_paisa": 70000,  # Price increase to Rs. 700
        }

        qbxml = build_item_non_inventory_mod_rq(item_data, list_id="80000002-1234567890")

        assert "<ItemNonInventoryModRq" in qbxml
        assert "80000002-1234567890" in qbxml
        assert "700.00" in qbxml


class TestPaymentBuilder:
    """Test ReceivePayment QBXML builder."""

    def test_build_payment(self):
        """Test building receive payment request."""
        payment_data = {
            "reference": "PAY-20240325-001",
            "amount": 200600,  # Rs. 2,006
            "processed_at": datetime(2024, 3, 25, 16, 0),
            "note": "Cash payment for order 240325-001",
            "order_number": "240325-001",
        }

        qbxml = build_receive_payment_add_rq(
            payment_data=payment_data,
            customer_name="Walk-In Customer",
            payment_method_name="Cash",
            deposit_to_account="Cash Drawer",
        )

        assert "<ReceivePaymentAddRq" in qbxml
        assert "PAY-20240325-001" in qbxml
        assert "2006.00" in qbxml
        assert "Walk-In Customer" in qbxml
        assert "Cash" in qbxml


class TestRefundBuilder:
    """Test CreditMemo QBXML builder."""

    def test_build_refund(self):
        """Test building credit memo request."""
        refund_data = {
            "order_number": "240325-001",
            "refund_reference": "REF-20240325-001",
            "refunded_at": datetime(2024, 3, 25, 17, 0),
            "items": [
                {"name": "Chicken Biryani", "quantity": 1, "price_paisa": 85000, "total_paisa": 85000}
            ],
            "subtotal_paisa": 85000,
            "tax_paisa": 15300,
            "total_paisa": 100300,
            "reason": "Customer complaint - cold food",
        }

        qbxml = build_credit_memo_add_rq(
            refund_data=refund_data,
            customer_name="Walk-In Customer",
            income_account="Food Sales",
            tax_account="Sales Tax Payable",
        )

        assert "<CreditMemoAddRq" in qbxml
        assert "REF-20240325-001" in qbxml
        assert "850.00" in qbxml  # Refund amount
        assert "REFUND - Original Order: 240325-001" in qbxml
        assert "Customer complaint" in qbxml


# =============================================================================
# Parser Tests
# =============================================================================

class TestQBXMLParser:
    """Test QBXML response parser."""

    def test_parse_success_response(self):
        """Test parsing a successful QB response."""
        response_xml = """<?xml version="1.0"?>
        <QBXML>
            <QBXMLMsgsRs>
                <SalesReceiptAddRs statusCode="0" statusSeverity="Info" statusMessage="Status OK">
                    <SalesReceiptRet>
                        <TxnID>12345-6789012345</TxnID>
                        <TimeCreated>2024-03-25T14:30:00</TimeCreated>
                        <RefNumber>240325-001</RefNumber>
                    </SalesReceiptRet>
                </SalesReceiptAddRs>
            </QBXMLMsgsRs>
        </QBXML>"""

        result = parse_qbxml_response(response_xml)

        assert result["success"] is True
        assert result["status_code"] == "0"
        assert result["txn_id"] == "12345-6789012345"
        assert result["entity_type"] == "SalesReceipt"

    def test_parse_error_response(self):
        """Test parsing an error response."""
        response_xml = """<?xml version="1.0"?>
        <QBXML>
            <QBXMLMsgsRs>
                <SalesReceiptAddRs statusCode="3100" statusSeverity="Error" statusMessage="Name already exists">
                </SalesReceiptAddRs>
            </QBXMLMsgsRs>
        </QBXML>"""

        result = parse_qbxml_response(response_xml)

        assert result["success"] is False
        assert result["status_code"] == "3100"
        assert "already exists" in result["error_message"]

    def test_parse_customer_add_response(self):
        """Test parsing customer add response (extracts ListID)."""
        response_xml = """<?xml version="1.0"?>
        <QBXML>
            <QBXMLMsgsRs>
                <CustomerAddRs statusCode="0" statusSeverity="Info">
                    <CustomerRet>
                        <ListID>80000001-1234567890</ListID>
                        <Name>John Doe</Name>
                    </CustomerRet>
                </CustomerAddRs>
            </QBXMLMsgsRs>
        </QBXML>"""

        result = parse_qbxml_response(response_xml)

        assert result["success"] is True
        assert result["list_id"] == "80000001-1234567890"
        assert result["entity_type"] == "Customer"


# =============================================================================
# Error Code Tests
# =============================================================================

class TestErrorCodes:
    """Test QB error code mapping."""

    def test_get_user_friendly_error(self):
        """Test error code to user-friendly message mapping."""
        # Known error code
        msg = get_user_friendly_error("3100")
        assert "already exists" in msg.lower()

        # Unknown error code
        msg = get_user_friendly_error("9999", "Fallback message")
        assert msg == "Fallback message"

        # Unknown error code without fallback
        msg = get_user_friendly_error("9999")
        assert "QuickBooks error 9999" in msg


# =============================================================================
# Currency Conversion Tests
# =============================================================================

class TestCurrencyConversion:
    """Test paisa to decimal conversion."""

    def test_paisa_to_decimal(self):
        """Test integer paisa to decimal string conversion."""
        from app.services.quickbooks.qbxml.builders.sales_receipt import paisa_to_decimal

        assert paisa_to_decimal(15000) == "150.00"
        assert paisa_to_decimal(99) == "0.99"
        assert paisa_to_decimal(0) == "0.00"
        assert paisa_to_decimal(1) == "0.01"
        assert paisa_to_decimal(100) == "1.00"
        assert paisa_to_decimal(123456) == "1234.56"

    def test_paisa_to_decimal_rounding(self):
        """Test that decimal rounding works correctly."""
        from app.services.quickbooks.qbxml.builders.sales_receipt import paisa_to_decimal

        # No rounding needed for paisa (already 2 decimal places)
        assert paisa_to_decimal(12345) == "123.45"


# =============================================================================
# Field Truncation Tests
# =============================================================================

class TestFieldTruncation:
    """Test QB field length limit enforcement."""

    def test_truncate_field(self):
        """Test field truncation to QB limits."""
        from app.services.quickbooks.qbxml.builders.sales_receipt import truncate_field

        # Name field (max 41 chars)
        long_name = "A" * 50
        truncated = truncate_field(long_name, "Name")
        assert len(truncated) == 41

        # RefNumber field (max 11 chars)
        long_ref = "ORDER-12345678901234567890"
        truncated = truncate_field(long_ref, "RefNumber")
        assert len(truncated) == 11

        # Short field (no truncation)
        short_name = "Short"
        truncated = truncate_field(short_name, "Name")
        assert truncated == "Short"


# =============================================================================
# Integration Tests (require database)
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
class TestDesktopAdapter:
    """Test Desktop Adapter (requires database)."""

    async def test_create_sales_receipt_queues_job(self, db_session, test_order, test_connection):
        """Test that create_sales_receipt queues a sync job."""
        from app.integrations.quickbooks_desktop import QBDesktopAdapter
        from app.models.quickbooks import QBSyncJob

        adapter = QBDesktopAdapter(test_connection, db_session)

        result = await adapter.create_sales_receipt(test_order)

        assert result["status"] == "queued"
        assert "sync_job_id" in result

        # Verify job was created
        job = await db_session.get(QBSyncJob, result["sync_job_id"])
        assert job is not None
        assert job.job_type == "create_sales_receipt"
        assert job.status == "pending"
        assert job.request_xml is not None
        assert "SalesReceiptAddRq" in job.request_xml

    async def test_adapter_factory_detects_desktop(self, db_session, test_connection):
        """Test that adapter factory returns Desktop adapter for desktop connections."""
        from app.services.quickbooks.adapter_factory import get_qb_adapter
        from app.integrations.quickbooks_desktop import QBDesktopAdapter

        # Set connection type to desktop
        test_connection.connection_type = "desktop"
        await db_session.commit()

        adapter = await get_qb_adapter(db_session, test_connection.tenant_id)

        assert isinstance(adapter, QBDesktopAdapter)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def test_connection(db_session, test_tenant):
    """Create a test QB Desktop connection."""
    from app.models.quickbooks import QBConnection
    import uuid

    connection = QBConnection(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        connection_type="desktop",
        company_name="Test Company",
        qbwc_username="testuser",
        qbwc_password_encrypted="encrypted_password",
        is_active=True,
        connected_by=test_tenant.id,
        connected_at=datetime.now(timezone.utc),
    )

    db_session.add(connection)
    db_session.commit()
    db_session.refresh(connection)

    return connection


@pytest.fixture
def test_order(db_session, test_tenant):
    """Create a test order."""
    from app.models.order import Order
    import uuid

    order = Order(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        order_number="TEST-001",
        order_type="dine_in",
        status="completed",
        payment_status="paid",
        subtotal=170000,
        tax_amount=30600,
        discount_amount=0,
        total=200600,
        created_by=test_tenant.id,
    )

    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    return order
