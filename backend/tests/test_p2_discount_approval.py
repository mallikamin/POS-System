"""P2-Slice 3: Discount Approval Workflow tests.

Verifies that discounts exceeding the configured threshold require
a valid manager verify-password token to be applied.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discount import DiscountType
from app.models.order import Order
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.models.user import User
from app.services.auth_service import create_verify_token


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def config(db: AsyncSession, tenant: Tenant) -> RestaurantConfig:
    """RestaurantConfig with approval thresholds set."""
    cfg = RestaurantConfig(
        tenant_id=tenant.id,
        # 15% threshold in basis points
        discount_approval_threshold_bps=1500,
        # Rs 500 threshold in paisa
        discount_approval_threshold_fixed=50000,
    )
    db.add(cfg)
    await db.flush()
    return cfg


@pytest_asyncio.fixture
async def config_disabled(db: AsyncSession, tenant: Tenant) -> RestaurantConfig:
    """RestaurantConfig with approval thresholds disabled (0)."""
    cfg = RestaurantConfig(
        tenant_id=tenant.id,
        discount_approval_threshold_bps=0,
        discount_approval_threshold_fixed=0,
    )
    db.add(cfg)
    await db.flush()
    return cfg


@pytest_asyncio.fixture
async def test_order(db: AsyncSession, tenant: Tenant, admin_user: User) -> Order:
    """A confirmed order with subtotal=100_00 (Rs 100)."""
    o = Order(
        tenant_id=tenant.id,
        order_number="T260303-050",
        order_type="takeaway",
        status="confirmed",
        payment_status="unpaid",
        subtotal=10000,
        tax_amount=1600,
        discount_amount=0,
        total=11600,
        created_by=admin_user.id,
    )
    db.add(o)
    await db.flush()
    await db.commit()
    return o


# ── Tests: below threshold (no approval needed) ─────────────────────


class TestBelowThreshold:
    """Discounts below both thresholds should apply without token."""

    @pytest.mark.asyncio
    async def test_small_discount_applies_without_token(
        self,
        client: AsyncClient,
        admin_token: str,
        config: RestaurantConfig,
        test_order: Order,
    ):
        """A Rs 10 (1000 paisa) discount = 10% on Rs 100 subtotal, below 15% threshold."""
        resp = await client.post(
            "/api/v1/discounts/apply",
            json={
                "order_id": str(test_order.id),
                "label": "Small Discount",
                "source_type": "manual",
                "amount": 1000,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["amount"] == 1000

    @pytest.mark.asyncio
    async def test_threshold_disabled_any_discount_ok(
        self,
        client: AsyncClient,
        admin_token: str,
        config_disabled: RestaurantConfig,
        test_order: Order,
    ):
        """When thresholds are 0 (disabled), even large discounts apply freely."""
        resp = await client.post(
            "/api/v1/discounts/apply",
            json={
                "order_id": str(test_order.id),
                "label": "Big Discount",
                "source_type": "manual",
                "amount": 9000,  # 90% of subtotal — would exceed any threshold
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["amount"] == 9000


# ── Tests: above threshold (approval required) ──────────────────────


class TestAboveThreshold:
    """Discounts above thresholds require manager verify token."""

    @pytest.mark.asyncio
    async def test_exceeds_percent_threshold_requires_token(
        self,
        client: AsyncClient,
        admin_token: str,
        config: RestaurantConfig,
        test_order: Order,
    ):
        """Rs 20 on Rs 100 subtotal = 20% > 15% threshold → approval_required."""
        resp = await client.post(
            "/api/v1/discounts/apply",
            json={
                "order_id": str(test_order.id),
                "label": "Big Percent",
                "source_type": "manual",
                "amount": 2000,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "approval_required"

    @pytest.mark.asyncio
    async def test_exceeds_fixed_threshold_requires_token(
        self,
        client: AsyncClient,
        admin_token: str,
        config: RestaurantConfig,
        test_order: Order,
        db: AsyncSession,
    ):
        """Need an order with bigger subtotal to test fixed threshold."""
        # Create a large order (subtotal = Rs 10000 = 1000000 paisa)
        big_order = Order(
            tenant_id=test_order.tenant_id,
            order_number="T260303-051",
            order_type="takeaway",
            status="confirmed",
            payment_status="unpaid",
            subtotal=1000000,
            tax_amount=160000,
            discount_amount=0,
            total=1160000,
            created_by=test_order.created_by,
        )
        db.add(big_order)
        await db.commit()

        # Rs 600 = 60000 paisa > 50000 fixed threshold
        # but 6% < 15% percent threshold — tests fixed threshold independently
        resp = await client.post(
            "/api/v1/discounts/apply",
            json={
                "order_id": str(big_order.id),
                "label": "Large Fixed",
                "source_type": "manual",
                "amount": 60000,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "approval_required"

    @pytest.mark.asyncio
    async def test_valid_manager_token_allows_discount(
        self,
        client: AsyncClient,
        admin_token: str,
        admin_user: User,
        config: RestaurantConfig,
        test_order: Order,
    ):
        """With a valid verify token, discount above threshold is accepted."""
        verify_token = create_verify_token(str(admin_user.id))
        resp = await client.post(
            "/api/v1/discounts/apply",
            json={
                "order_id": str(test_order.id),
                "label": "Approved Discount",
                "source_type": "manual",
                "amount": 2000,
                "manager_verify_token": verify_token,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["amount"] == 2000

    @pytest.mark.asyncio
    async def test_invalid_manager_token_rejected(
        self,
        client: AsyncClient,
        admin_token: str,
        config: RestaurantConfig,
        test_order: Order,
    ):
        """An invalid/expired token is rejected."""
        resp = await client.post(
            "/api/v1/discounts/apply",
            json={
                "order_id": str(test_order.id),
                "label": "Bad Token",
                "source_type": "manual",
                "amount": 2000,
                "manager_verify_token": "invalid-token-here",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400
        assert "Invalid or expired" in resp.json()["detail"]


# ── Tests: config update ─────────────────────────────────────────────


class TestConfigThresholdUpdate:
    """Admin can update discount approval thresholds via config PATCH."""

    @pytest.mark.asyncio
    async def test_update_thresholds(
        self,
        client: AsyncClient,
        admin_token: str,
        config: RestaurantConfig,
    ):
        """PATCH config with new threshold values."""
        resp = await client.patch(
            "/api/v1/config/restaurant",
            json={
                "discount_approval_threshold_bps": 2000,
                "discount_approval_threshold_fixed": 100000,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["discount_approval_threshold_bps"] == 2000
        assert data["discount_approval_threshold_fixed"] == 100000

    @pytest.mark.asyncio
    async def test_threshold_fields_in_get_config(
        self,
        client: AsyncClient,
        admin_token: str,
        config: RestaurantConfig,
    ):
        """GET config response includes threshold fields."""
        resp = await client.get(
            "/api/v1/config/restaurant",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "discount_approval_threshold_bps" in data
        assert "discount_approval_threshold_fixed" in data
        assert data["discount_approval_threshold_bps"] == 1500
        assert data["discount_approval_threshold_fixed"] == 50000
