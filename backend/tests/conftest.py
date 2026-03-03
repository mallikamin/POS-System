"""Shared test fixtures for POS backend tests.

Uses an in-memory SQLite database (async). Skips QuickBooks tables that use
Postgres-specific types (JSONB).

Env vars are set BEFORE app imports so pydantic-settings picks them up
instead of reading .env (which may point to a real Postgres instance).
"""

# ── Env overrides (MUST come before any app imports) ───────────────────
# These ensure pydantic-settings picks up safe values instead of reading
# .env, which may point to a real Postgres / production setup.
# NOTE: DATABASE_URL is NOT overridden — the app's engine is created lazily
# and never used in tests (get_db is overridden below).
import os

# ENVIRONMENT and SECRET_KEY use force-set (not setdefault) to prevent the
# production guard in config.py from calling sys.exit(1) during test runs.
os.environ["ENVIRONMENT"] = "testing"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("QB_CLIENT_ID", "")
os.environ.setdefault("QB_CLIENT_SECRET", "")

# ── Standard imports ───────────────────────────────────────────────────
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.tenant import Tenant
from app.models.restaurant_config import RestaurantConfig
from app.models.user import Permission, Role, RolePermission, User, RefreshToken
from app.models.floor import Floor, Table
from app.models.menu import Category, MenuItem, ModifierGroup, Modifier, MenuItemModifierGroup
from app.models.order import Order, OrderItem, OrderItemModifier, OrderStatusLog
from app.models.payment import PaymentMethod, Payment, CashDrawerSession
from app.models.customer import Customer
from app.models.kitchen import KitchenStation, KitchenTicket, KitchenTicketItem
from app.models.table_session import TableSession
from app.models.discount import DiscountType, OrderDiscount
from app.utils.security import create_access_token, hash_password

# ── In-memory async SQLite engine ──────────────────────────────────────
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

# Tables that use Postgres-specific types (JSONB) — skip for SQLite tests.
_SKIP_TABLE_NAMES = {
    "qb_connections",
    "qb_account_mappings",
    "qb_entity_mappings",
    "qb_sync_queue",
    "qb_sync_log",
    "qb_coa_snapshots",
    "audit_logs",
}

_TABLES_NEEDED = [
    tbl
    for tbl in Base.metadata.sorted_tables
    if tbl.name not in _SKIP_TABLE_NAMES
]


# ── DB setup / teardown ───────────────────────────────────────────────
@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create tables before each test, drop after."""
    async with engine.begin() as conn:
        for tbl in _TABLES_NEEDED:
            await conn.run_sync(tbl.create, checkfirst=True)
    yield
    async with engine.begin() as conn:
        for tbl in reversed(_TABLES_NEEDED):
            await conn.run_sync(tbl.drop, checkfirst=True)


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


# ── Override FastAPI dependency ────────────────────────────────────────
@pytest_asyncio.fixture(autouse=True)
async def override_get_db():
    """Replace the real get_db with our test session."""

    async def _override() -> AsyncGenerator[AsyncSession, None]:
        async with TestingSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.clear()


# ── Tenant A (primary) ────────────────────────────────────────────────
TENANT_ID = uuid.uuid4()


@pytest_asyncio.fixture
async def tenant(db: AsyncSession) -> Tenant:
    t = Tenant(id=TENANT_ID, tenant_id=TENANT_ID, name="Test Restaurant", slug="test-restaurant", is_active=True)
    db.add(t)
    await db.flush()
    return t


# ── Roles ──────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def admin_role(db: AsyncSession, tenant: Tenant) -> Role:
    role = Role(tenant_id=tenant.id, name="admin", description="Admin role")
    db.add(role)
    await db.flush()
    return role


@pytest_asyncio.fixture
async def cashier_role(db: AsyncSession, tenant: Tenant) -> Role:
    role = Role(tenant_id=tenant.id, name="cashier", description="Cashier role")
    db.add(role)
    await db.flush()
    return role


@pytest_asyncio.fixture
async def kitchen_role(db: AsyncSession, tenant: Tenant) -> Role:
    role = Role(tenant_id=tenant.id, name="kitchen", description="Kitchen role")
    db.add(role)
    await db.flush()
    return role


# ── Users ──────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def admin_user(db: AsyncSession, tenant: Tenant, admin_role: Role) -> User:
    user = User(
        tenant_id=tenant.id, email="admin@test.com", full_name="Admin User",
        hashed_password=hash_password("admin123"), role_id=admin_role.id, is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def cashier_user(db: AsyncSession, tenant: Tenant, cashier_role: Role) -> User:
    user = User(
        tenant_id=tenant.id, email="cashier@test.com", full_name="Cashier User",
        hashed_password=hash_password("cashier123"), role_id=cashier_role.id, is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def kitchen_user(db: AsyncSession, tenant: Tenant, kitchen_role: Role) -> User:
    user = User(
        tenant_id=tenant.id, email="kitchen@test.com", full_name="Kitchen User",
        hashed_password=hash_password("kitchen123"), role_id=kitchen_role.id, is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


# ── Floor + Table ──────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def floor(db: AsyncSession, tenant: Tenant) -> Floor:
    f = Floor(tenant_id=tenant.id, name="Ground Floor", display_order=1, is_active=True)
    db.add(f)
    await db.flush()
    return f


@pytest_asyncio.fixture
async def table(db: AsyncSession, tenant: Tenant, floor: Floor) -> Table:
    t = Table(
        tenant_id=tenant.id, floor_id=floor.id, number=1,
        capacity=4, shape="square", status="available",
    )
    db.add(t)
    await db.flush()
    await db.commit()
    return t


# ── Order (needed by payment tests) ───────────────────────────────────
@pytest_asyncio.fixture
async def order(db: AsyncSession, tenant: Tenant, admin_user: User) -> Order:
    """A confirmed order with total = 100_00 paisa (Rs 100)."""
    o = Order(
        tenant_id=tenant.id,
        order_number="T250101-001",
        order_type="takeaway",
        status="confirmed",
        payment_status="unpaid",
        subtotal=8621,
        tax_amount=1379,
        discount_amount=0,
        total=10000,
        created_by=admin_user.id,
    )
    db.add(o)
    await db.flush()
    await db.commit()
    return o


@pytest_asyncio.fixture
async def small_order(db: AsyncSession, tenant: Tenant, admin_user: User) -> Order:
    """A smaller order, total = 30_00 paisa (Rs 30)."""
    o = Order(
        tenant_id=tenant.id,
        order_number="T250101-002",
        order_type="takeaway",
        status="confirmed",
        payment_status="unpaid",
        subtotal=2586,
        tax_amount=414,
        discount_amount=0,
        total=3000,
        created_by=admin_user.id,
    )
    db.add(o)
    await db.flush()
    await db.commit()
    return o


# ── Auth helpers ───────────────────────────────────────────────────────
def make_token(user: User) -> str:
    """Create a valid access token for the given user."""
    return create_access_token({"sub": str(user.id), "tenant_id": str(user.tenant_id)})


@pytest_asyncio.fixture
async def admin_token(admin_user: User) -> str:
    return make_token(admin_user)


@pytest_asyncio.fixture
async def cashier_token(cashier_user: User) -> str:
    return make_token(cashier_user)


@pytest_asyncio.fixture
async def kitchen_token(kitchen_user: User) -> str:
    return make_token(kitchen_user)


# ── HTTP client ────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── Tenant B (cross-tenant isolation) ─────────────────────────────────
OTHER_TENANT_ID = uuid.uuid4()


@pytest_asyncio.fixture
async def other_tenant(db: AsyncSession) -> Tenant:
    t = Tenant(id=OTHER_TENANT_ID, tenant_id=OTHER_TENANT_ID, name="Other Restaurant", slug="other-restaurant", is_active=True)
    db.add(t)
    await db.flush()
    return t


@pytest_asyncio.fixture
async def other_tenant_role(db: AsyncSession, other_tenant: Tenant) -> Role:
    role = Role(tenant_id=other_tenant.id, name="admin", description="Admin role")
    db.add(role)
    await db.flush()
    return role


@pytest_asyncio.fixture
async def other_tenant_user(db: AsyncSession, other_tenant: Tenant, other_tenant_role: Role) -> User:
    user = User(
        tenant_id=other_tenant.id, email="admin@other.com", full_name="Other Admin",
        hashed_password=hash_password("admin123"), role_id=other_tenant_role.id, is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def other_tenant_token(other_tenant_user: User) -> str:
    return make_token(other_tenant_user)


@pytest_asyncio.fixture
async def other_tenant_order(db: AsyncSession, other_tenant: Tenant, other_tenant_user: User) -> Order:
    """Order belonging to tenant B."""
    o = Order(
        tenant_id=other_tenant.id,
        order_number="O250101-001",
        order_type="takeaway",
        status="confirmed",
        payment_status="unpaid",
        subtotal=4310,
        tax_amount=690,
        discount_amount=0,
        total=5000,
        created_by=other_tenant_user.id,
    )
    db.add(o)
    await db.flush()
    await db.commit()
    return o
