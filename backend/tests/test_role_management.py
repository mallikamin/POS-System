"""Tests for Slice 5: role management CRUD + discount permission gates.

Covers:
- CRUD for roles (list, get, create, update)
- Permission assignment persists
- require_permission("discount.apply") allows manager with perm, blocks cashier
- Discount type CRUD requires discount.manage permission
"""

import uuid

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Permission, Role, RolePermission, User
from tests.conftest import make_token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def discount_permissions(db: AsyncSession, tenant) -> dict[str, Permission]:
    """Create discount.apply and discount.manage permissions."""
    apply_perm = Permission(
        tenant_id=tenant.id, code="discount.apply", description="Apply discounts",
    )
    manage_perm = Permission(
        tenant_id=tenant.id, code="discount.manage", description="Manage discount types",
    )
    db.add(apply_perm)
    db.add(manage_perm)
    await db.flush()
    await db.commit()
    return {"apply": apply_perm, "manage": manage_perm}


@pytest_asyncio.fixture
async def manager_with_discount_perms(
    db: AsyncSession, tenant, manager_role: Role, manager_user: User,
    discount_permissions: dict[str, Permission],
) -> User:
    """Grant manager role both discount.apply and discount.manage permissions."""
    for perm in discount_permissions.values():
        db.add(RolePermission(
            tenant_id=tenant.id, role_id=manager_role.id, permission_id=perm.id,
        ))
    await db.flush()
    await db.commit()
    return manager_user


class TestRoleCRUD:
    """Test role CRUD endpoints."""

    async def test_list_roles(
        self, client: AsyncClient, admin_token: str,
        admin_role: Role, cashier_role: Role,
    ):
        resp = await client.get("/api/v1/staff/roles", headers=_auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        names = {r["name"] for r in data}
        assert "admin" in names
        assert "cashier" in names

    async def test_create_role(
        self, client: AsyncClient, admin_token: str, admin_role: Role,
    ):
        resp = await client.post(
            "/api/v1/staff/roles",
            json={"name": "supervisor", "description": "Floor supervisor"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "supervisor"
        assert body["description"] == "Floor supervisor"
        assert body["is_active"] is True

    async def test_create_duplicate_role_rejected(
        self, client: AsyncClient, admin_token: str, admin_role: Role,
    ):
        resp = await client.post(
            "/api/v1/staff/roles",
            json={"name": "admin"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 409

    async def test_get_role(
        self, client: AsyncClient, admin_token: str, admin_role: Role,
    ):
        resp = await client.get(
            f"/api/v1/staff/roles/{admin_role.id}",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "admin"

    async def test_update_role(
        self, client: AsyncClient, admin_token: str, cashier_role: Role,
    ):
        resp = await client.patch(
            f"/api/v1/staff/roles/{cashier_role.id}",
            json={"description": "Updated description"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated description"

    async def test_create_role_with_permissions(
        self, client: AsyncClient, admin_token: str,
        admin_role: Role, discount_permissions: dict[str, Permission],
    ):
        perm_ids = [str(p.id) for p in discount_permissions.values()]
        resp = await client.post(
            "/api/v1/staff/roles",
            json={"name": "discount_admin", "permission_ids": perm_ids},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        perm_codes = {p["code"] for p in body["permissions"]}
        assert "discount.apply" in perm_codes
        assert "discount.manage" in perm_codes

    async def test_update_role_permissions(
        self, client: AsyncClient, admin_token: str,
        cashier_role: Role, discount_permissions: dict[str, Permission],
    ):
        # Add apply permission
        apply_id = str(discount_permissions["apply"].id)
        resp = await client.patch(
            f"/api/v1/staff/roles/{cashier_role.id}",
            json={"permission_ids": [apply_id]},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        perm_codes = {p["code"] for p in resp.json()["permissions"]}
        assert "discount.apply" in perm_codes
        assert "discount.manage" not in perm_codes

    async def test_cashier_cannot_access_role_crud(
        self, client: AsyncClient, cashier_token: str,
    ):
        resp = await client.get("/api/v1/staff/roles", headers=_auth(cashier_token))
        assert resp.status_code == 403

    async def test_list_permissions(
        self, client: AsyncClient, admin_token: str,
        admin_role: Role, discount_permissions: dict[str, Permission],
    ):
        resp = await client.get(
            "/api/v1/staff/permissions", headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        codes = {p["code"] for p in resp.json()}
        assert "discount.apply" in codes
        assert "discount.manage" in codes


class TestDiscountPermissionGates:
    """Test that discount endpoints are gated by permission."""

    async def test_manager_with_permission_can_apply(
        self, client: AsyncClient,
        manager_with_discount_perms: User,
    ):
        """Manager with discount.apply permission can access the endpoint."""
        token = make_token(manager_with_discount_perms)
        # We just verify the permission check passes (400 = bad request is fine,
        # 403 = permission denied would be a failure)
        resp = await client.post(
            "/api/v1/discounts/apply",
            json={"order_id": str(uuid.uuid4()), "amount": 100, "source_type": "manual", "label": "Test"},
            headers=_auth(token),
        )
        # Should NOT be 403 (permission denied)
        assert resp.status_code != 403

    async def test_cashier_without_permission_blocked(
        self, client: AsyncClient, cashier_token: str,
    ):
        """Cashier without discount.apply permission gets 403."""
        resp = await client.post(
            "/api/v1/discounts/apply",
            json={"order_id": str(uuid.uuid4()), "amount": 100, "source_type": "manual", "label": "Test"},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 403
        assert "discount.apply" in resp.json()["detail"]

    async def test_cashier_blocked_from_discount_type_crud(
        self, client: AsyncClient, cashier_token: str,
    ):
        """Cashier without discount.manage cannot create discount types."""
        resp = await client.post(
            "/api/v1/discounts/types",
            json={"name": "Staff Meal", "discount_mode": "percentage", "value": 5000},
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 403
        assert "discount.manage" in resp.json()["detail"]
