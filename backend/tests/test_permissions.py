"""Tests for the require_permission dependency and manager role."""

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.models.user import Permission, Role, RolePermission, User
from tests.conftest import make_token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestRequirePermissionDependency:
    """Test that require_permission correctly checks user permissions."""

    async def test_admin_role_still_works(
        self, client: AsyncClient, admin_token: str,
    ):
        """Admin role check still works (backward compatibility)."""
        resp = await client.get(
            "/api/v1/staff",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200

    async def test_cashier_blocked_from_admin_endpoint(
        self, client: AsyncClient, cashier_token: str,
    ):
        """Cashier cannot access admin-only endpoints."""
        resp = await client.get(
            "/api/v1/staff",
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 403

    async def test_manager_role_fixture_works(
        self, client: AsyncClient, manager_token: str,
    ):
        """Manager role fixture creates a valid token."""
        resp = await client.get(
            "/api/v1/auth/me",
            headers=_auth(manager_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"]["name"] == "manager"


class TestManagerRolePermissions:
    """Test that manager role with permissions works correctly."""

    @pytest_asyncio.fixture
    async def manager_with_perms(
        self, db: AsyncSession, tenant: Tenant, manager_role: Role, manager_user: User,
    ) -> User:
        """Give manager role the discount.apply permission."""
        perm = Permission(
            tenant_id=tenant.id,
            code="discount.apply",
            description="Apply discounts",
        )
        db.add(perm)
        await db.flush()
        rp = RolePermission(
            tenant_id=tenant.id, role_id=manager_role.id, permission_id=perm.id,
        )
        db.add(rp)
        await db.flush()
        await db.commit()
        return manager_user

    async def test_permission_loaded_on_role(
        self, db: AsyncSession, manager_with_perms: User,
    ):
        """Verify the permission is correctly associated with the role."""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        result = await db.execute(
            select(Role)
            .options(selectinload(Role.permissions))
            .where(Role.id == manager_with_perms.role_id)
        )
        role = result.scalar_one()
        perm_codes = {p.code for p in role.permissions}
        assert "discount.apply" in perm_codes
