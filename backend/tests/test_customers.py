"""Tests for customer endpoints (Phase 8 — Call Center).

Covers: search by phone, create, update, get, order history,
tenant isolation, and validation errors.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.order import Order
from app.models.user import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# Fixtures (customer-specific)
# =========================================================================

@pytest.fixture
def customer_data() -> dict:
    return {
        "name": "Ahmad Khan",
        "phone": "03001234567",
        "email": "ahmad@example.com",
        "alt_contact": "03009999888",
        "default_address": "House 42, Street 7, F-8/3",
        "city": "Islamabad",
        "alt_address": "Office #5, Blue Area",
        "alt_city": "Islamabad",
        "notes": "Prefers extra raita",
    }


# =========================================================================
# 1. Create Customer
# =========================================================================
class TestCreateCustomer:
    """POST /api/v1/customers"""

    async def test_create_success(
        self, client: AsyncClient, cashier_token: str, customer_data: dict
    ):
        resp = await client.post(
            "/api/v1/customers", json=customer_data, headers=_auth(cashier_token)
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Ahmad Khan"
        assert body["phone"] == "03001234567"
        assert body["email"] == "ahmad@example.com"
        assert body["alt_contact"] == "03009999888"
        assert body["default_address"] == "House 42, Street 7, F-8/3"
        assert body["city"] == "Islamabad"
        assert body["alt_address"] == "Office #5, Blue Area"
        assert body["alt_city"] == "Islamabad"
        assert body["order_count"] == 0
        assert body["total_spent"] == 0
        assert body["risk_flag"] == "normal"
        assert body["last_order_at"] is None
        assert body["id"] is not None

    async def test_create_minimal(self, client: AsyncClient, cashier_token: str):
        resp = await client.post(
            "/api/v1/customers",
            json={"name": "Ali", "phone": "03009876543"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Ali"
        assert body["email"] is None
        assert body["default_address"] is None

    async def test_duplicate_phone_409(
        self, client: AsyncClient, cashier_token: str, customer_data: dict
    ):
        await client.post(
            "/api/v1/customers", json=customer_data, headers=_auth(cashier_token)
        )
        resp = await client.post(
            "/api/v1/customers", json=customer_data, headers=_auth(cashier_token)
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()

    async def test_invalid_phone_format_422(
        self, client: AsyncClient, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/customers",
            json={"name": "Test", "phone": "0300-123-4567"},  # has dashes
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 422

    async def test_phone_too_short_422(
        self, client: AsyncClient, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/customers",
            json={"name": "Test", "phone": "12345"},  # < 7 digits
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 422

    async def test_missing_name_422(self, client: AsyncClient, cashier_token: str):
        resp = await client.post(
            "/api/v1/customers",
            json={"phone": "03001234567"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 422

    async def test_no_auth_401(self, client: AsyncClient, customer_data: dict):
        resp = await client.post("/api/v1/customers", json=customer_data)
        assert resp.status_code == 401


# =========================================================================
# 2. Get Customer
# =========================================================================
class TestGetCustomer:
    """GET /api/v1/customers/{customer_id}"""

    async def test_get_success(
        self, client: AsyncClient, cashier_token: str, customer_data: dict
    ):
        create_resp = await client.post(
            "/api/v1/customers", json=customer_data, headers=_auth(cashier_token)
        )
        cid = create_resp.json()["id"]
        resp = await client.get(
            f"/api/v1/customers/{cid}", headers=_auth(cashier_token)
        )
        assert resp.status_code == 200
        assert resp.json()["phone"] == "03001234567"

    async def test_not_found_404(self, client: AsyncClient, cashier_token: str):
        resp = await client.get(
            f"/api/v1/customers/{uuid.uuid4()}", headers=_auth(cashier_token)
        )
        assert resp.status_code == 404


# =========================================================================
# 3. Update Customer
# =========================================================================
class TestUpdateCustomer:
    """PATCH /api/v1/customers/{customer_id}"""

    async def test_update_name(
        self, client: AsyncClient, cashier_token: str, customer_data: dict
    ):
        create_resp = await client.post(
            "/api/v1/customers", json=customer_data, headers=_auth(cashier_token)
        )
        cid = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/v1/customers/{cid}",
            json={"name": "Ahmad Ali Khan"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Ahmad Ali Khan"
        assert resp.json()["phone"] == "03001234567"  # unchanged

    async def test_update_phone(
        self, client: AsyncClient, cashier_token: str, customer_data: dict
    ):
        create_resp = await client.post(
            "/api/v1/customers", json=customer_data, headers=_auth(cashier_token)
        )
        cid = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/v1/customers/{cid}",
            json={"phone": "03219876543"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        assert resp.json()["phone"] == "03219876543"

    async def test_update_phone_to_existing_409(
        self, client: AsyncClient, cashier_token: str
    ):
        await client.post(
            "/api/v1/customers",
            json={"name": "A", "phone": "03001111111"},
            headers=_auth(cashier_token),
        )
        create_b = await client.post(
            "/api/v1/customers",
            json={"name": "B", "phone": "03002222222"},
            headers=_auth(cashier_token),
        )
        cid_b = create_b.json()["id"]
        resp = await client.patch(
            f"/api/v1/customers/{cid_b}",
            json={"phone": "03001111111"},  # already taken
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 409

    async def test_update_nonexistent_404(
        self, client: AsyncClient, cashier_token: str
    ):
        resp = await client.patch(
            f"/api/v1/customers/{uuid.uuid4()}",
            json={"name": "Ghost"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 404

    async def test_partial_update_preserves_other_fields(
        self, client: AsyncClient, cashier_token: str, customer_data: dict
    ):
        create_resp = await client.post(
            "/api/v1/customers", json=customer_data, headers=_auth(cashier_token)
        )
        cid = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/v1/customers/{cid}",
            json={"notes": "No onions"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["notes"] == "No onions"
        assert body["name"] == "Ahmad Khan"
        assert body["email"] == "ahmad@example.com"


# =========================================================================
# 4. Search by Phone
# =========================================================================
class TestSearchByPhone:
    """GET /api/v1/customers/search?phone=..."""

    async def _seed_customers(self, client: AsyncClient, token: str):
        customers = [
            {"name": "Ahmad", "phone": "03001234567"},
            {"name": "Bilal", "phone": "03009876543"},
            {"name": "Careem", "phone": "03211234567"},
        ]
        for c in customers:
            await client.post(
                "/api/v1/customers", json=c, headers=_auth(token)
            )

    async def test_search_exact(
        self, client: AsyncClient, cashier_token: str
    ):
        await self._seed_customers(client, cashier_token)
        resp = await client.get(
            "/api/v1/customers/search?phone=03001234567",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert results[0]["name"] == "Ahmad"

    async def test_search_partial_prefix(
        self, client: AsyncClient, cashier_token: str
    ):
        await self._seed_customers(client, cashier_token)
        resp = await client.get(
            "/api/v1/customers/search?phone=0300",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 2  # Ahmad + Bilal

    async def test_search_partial_suffix(
        self, client: AsyncClient, cashier_token: str
    ):
        await self._seed_customers(client, cashier_token)
        resp = await client.get(
            "/api/v1/customers/search?phone=1234567",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 2  # Ahmad + Careem (both contain 1234567)

    async def test_search_no_match(
        self, client: AsyncClient, cashier_token: str
    ):
        await self._seed_customers(client, cashier_token)
        resp = await client.get(
            "/api/v1/customers/search?phone=9999999",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_search_strips_non_digits(
        self, client: AsyncClient, cashier_token: str
    ):
        """Non-digit characters in the query are stripped."""
        await self._seed_customers(client, cashier_token)
        resp = await client.get(
            "/api/v1/customers/search?phone=0300-123",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) >= 1  # At least Ahmad

    async def test_search_with_limit(
        self, client: AsyncClient, cashier_token: str
    ):
        await self._seed_customers(client, cashier_token)
        resp = await client.get(
            "/api/v1/customers/search?phone=03&limit=1",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_search_no_auth_401(self, client: AsyncClient):
        resp = await client.get("/api/v1/customers/search?phone=0300")
        assert resp.status_code == 401


# =========================================================================
# 5. Order History
# =========================================================================
class TestOrderHistory:
    """GET /api/v1/customers/{customer_id}/orders"""

    async def test_order_history_with_orders(
        self, client: AsyncClient, cashier_token: str, db: AsyncSession,
        tenant, admin_user: User,
    ):
        # Create customer
        create_resp = await client.post(
            "/api/v1/customers",
            json={"name": "History Test", "phone": "03005551234"},
            headers=_auth(cashier_token),
        )
        cid = create_resp.json()["id"]

        # Create orders matching the customer phone
        for i, num in enumerate(["H250101-001", "H250101-002"]):
            o = Order(
                tenant_id=tenant.id,
                order_number=num,
                order_type="call_center",
                status="completed",
                payment_status="paid",
                subtotal=5000,
                tax_amount=800,
                discount_amount=0,
                total=5800,
                created_by=admin_user.id,
                customer_phone="03005551234",
                customer_name="History Test",
            )
            db.add(o)
        await db.flush()
        await db.commit()

        resp = await client.get(
            f"/api/v1/customers/{cid}/orders",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        orders = resp.json()
        assert len(orders) == 2
        assert orders[0]["order_type"] == "call_center"
        assert "items_count" in orders[0]

    async def test_order_history_empty(
        self, client: AsyncClient, cashier_token: str
    ):
        create_resp = await client.post(
            "/api/v1/customers",
            json={"name": "No Orders", "phone": "03007770000"},
            headers=_auth(cashier_token),
        )
        cid = create_resp.json()["id"]
        resp = await client.get(
            f"/api/v1/customers/{cid}/orders",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_order_history_nonexistent_customer_404(
        self, client: AsyncClient, cashier_token: str
    ):
        resp = await client.get(
            f"/api/v1/customers/{uuid.uuid4()}/orders",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 404


# =========================================================================
# 6. Tenant Isolation
# =========================================================================
class TestTenantIsolation:

    async def test_search_isolated(
        self, client: AsyncClient, cashier_token: str, other_tenant_token: str
    ):
        """Customers created by tenant A are not visible to tenant B."""
        await client.post(
            "/api/v1/customers",
            json={"name": "Tenant A", "phone": "03001111111"},
            headers=_auth(cashier_token),
        )
        resp = await client.get(
            "/api/v1/customers/search?phone=03001111111",
            headers=_auth(other_tenant_token),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_cross_tenant_404(
        self, client: AsyncClient, cashier_token: str, other_tenant_token: str
    ):
        create_resp = await client.post(
            "/api/v1/customers",
            json={"name": "Tenant A", "phone": "03002222222"},
            headers=_auth(cashier_token),
        )
        cid = create_resp.json()["id"]
        resp = await client.get(
            f"/api/v1/customers/{cid}",
            headers=_auth(other_tenant_token),
        )
        assert resp.status_code == 404

    async def test_update_cross_tenant_404(
        self, client: AsyncClient, cashier_token: str, other_tenant_token: str
    ):
        create_resp = await client.post(
            "/api/v1/customers",
            json={"name": "Tenant A", "phone": "03003333333"},
            headers=_auth(cashier_token),
        )
        cid = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/v1/customers/{cid}",
            json={"name": "Hacked"},
            headers=_auth(other_tenant_token),
        )
        assert resp.status_code == 404


# =========================================================================
# 7. Enhanced Customer Fields
# =========================================================================
class TestEnhancedFields:
    """Tests for new customer fields: alt_contact, city, alt_address, alt_city,
    total_spent, last_order_at, risk_flag."""

    async def test_create_with_all_new_fields(
        self, client: AsyncClient, cashier_token: str
    ):
        resp = await client.post(
            "/api/v1/customers",
            json={
                "name": "Full Fields",
                "phone": "03004445556",
                "alt_contact": "03119998887",
                "default_address": "House 1, Street 2",
                "city": "Lahore",
                "alt_address": "Office #3",
                "alt_city": "Karachi",
            },
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["alt_contact"] == "03119998887"
        assert body["city"] == "Lahore"
        assert body["alt_address"] == "Office #3"
        assert body["alt_city"] == "Karachi"
        assert body["risk_flag"] == "normal"
        assert body["total_spent"] == 0

    async def test_update_alt_contact(
        self, client: AsyncClient, cashier_token: str
    ):
        create_resp = await client.post(
            "/api/v1/customers",
            json={"name": "Alt Test", "phone": "03006667778"},
            headers=_auth(cashier_token),
        )
        cid = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/v1/customers/{cid}",
            json={"alt_contact": "03117776665"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        assert resp.json()["alt_contact"] == "03117776665"

    async def test_update_risk_flag(
        self, client: AsyncClient, cashier_token: str
    ):
        create_resp = await client.post(
            "/api/v1/customers",
            json={"name": "Risk Test", "phone": "03008889990"},
            headers=_auth(cashier_token),
        )
        cid = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/v1/customers/{cid}",
            json={"risk_flag": "high"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 200
        assert resp.json()["risk_flag"] == "high"

    async def test_invalid_risk_flag_422(
        self, client: AsyncClient, cashier_token: str
    ):
        create_resp = await client.post(
            "/api/v1/customers",
            json={"name": "Risk Invalid", "phone": "03001112223"},
            headers=_auth(cashier_token),
        )
        cid = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/v1/customers/{cid}",
            json={"risk_flag": "invalid_value"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 422

    async def test_response_includes_new_fields(
        self, client: AsyncClient, cashier_token: str
    ):
        create_resp = await client.post(
            "/api/v1/customers",
            json={"name": "Fields Check", "phone": "03002223334"},
            headers=_auth(cashier_token),
        )
        body = create_resp.json()
        # All new fields should be present in response
        assert "alt_contact" in body
        assert "city" in body
        assert "alt_address" in body
        assert "alt_city" in body
        assert "total_spent" in body
        assert "last_order_at" in body
        assert "risk_flag" in body
