"""The stock movement ledger, and the fact that it can now be read.

🔴 WHY THIS FILE EXISTS. `move_stock` has written an `InventoryTransaction` for
every stock change since the inventory module shipped, and the adjust endpoint
has always demanded a mandatory reason. None of it was readable: there was no
endpoint and no screen, so the reason a human typed went into the database and
was never seen again. Found in UAT on 2026-08-27, when the client walkthrough
told the reader to "look at the movement history for that item" and no such
thing existed.

The claim this module is sold on is "stock never changes without an
explanation". These tests are what make that claim inspectable rather than
something a customer has to take on trust, so they check the two columns that
turn a number into a record -- who did it and why -- and not merely that rows
come back.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Ingredient
from app.models.location import Location
from app.models.tenant import Tenant
from app.models.user import User
from app.services import stock_service

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def site(db: AsyncSession, tenant: Tenant) -> Location:
    loc = Location(
        tenant_id=tenant.id,
        name="Production & Wholesale",
        code="PROD",
        location_type="production",
        is_default=True,
    )
    db.add(loc)
    await db.flush()
    return loc


@pytest_asyncio.fixture
async def other_site(db: AsyncSession, tenant: Tenant) -> Location:
    loc = Location(
        tenant_id=tenant.id,
        name="Delivery Kitchen",
        code="DEL",
        location_type="delivery",
    )
    db.add(loc)
    await db.flush()
    return loc


@pytest_asyncio.fixture
async def flour(db: AsyncSession, tenant: Tenant) -> Ingredient:
    ing = Ingredient(
        tenant_id=tenant.id,
        name="Flour",
        unit="kg",
        cost_per_unit=Decimal("3.50"),
    )
    db.add(ing)
    await db.flush()
    return ing


async def test_a_manual_adjustment_is_readable_afterwards(
    db: AsyncSession,
    tenant: Tenant,
    site: Location,
    flour: Ingredient,
    admin_user: User,
):
    """The whole point. Reason in, reason out, with a name attached.

    Before this endpoint existed, everything up to the write worked and the
    reason was simply unreachable. A test that only asserted the row was written
    would have passed the entire time the feature was invisible.
    """
    await stock_service.move_stock(
        db,
        tenant_id=tenant.id,
        ingredient_id=flour.id,
        quantity_delta=Decimal("-2"),
        transaction_type="adjustment",
        location_id=site.id,
        performed_by=admin_user.id,
        notes="damaged sack",
    )
    await db.flush()

    rows = await stock_service.get_stock_movements(db, tenant.id)

    assert len(rows) == 1, "the movement was written but did not come back"
    row = rows[0]
    assert row["notes"] == "damaged sack"
    assert row["performed_by_name"] == admin_user.full_name
    assert row["quantity"] == Decimal("-2")
    assert row["transaction_type"] == "adjustment"
    assert row["ingredient_name"] == "Flour"
    assert row["location_name"] == "Production & Wholesale"
    assert row["unit"] == "kg"


async def test_newest_first(
    db: AsyncSession, tenant: Tenant, site: Location, flour: Ingredient
):
    """A history that is not in order is not a history."""
    for i in range(3):
        await stock_service.move_stock(
            db,
            tenant_id=tenant.id,
            ingredient_id=flour.id,
            quantity_delta=Decimal("1"),
            transaction_type="purchase",
            location_id=site.id,
            notes=f"delivery {i}",
        )
        await db.flush()

    rows = await stock_service.get_stock_movements(db, tenant.id)
    assert [r["notes"] for r in rows] == ["delivery 2", "delivery 1", "delivery 0"]


async def test_filtering_by_location_keeps_the_balance_column_meaningful(
    db: AsyncSession,
    tenant: Tenant,
    site: Location,
    other_site: Location,
    flour: Ingredient,
):
    """`balance_after` is per location, so two sites must not share a list.

    Mixing them produces a running balance that jumps between two unrelated
    numbers, which is worse than showing nothing.
    """
    await stock_service.move_stock(
        db,
        tenant_id=tenant.id,
        ingredient_id=flour.id,
        quantity_delta=Decimal("10"),
        transaction_type="purchase",
        location_id=site.id,
        notes="to production",
    )
    await stock_service.move_stock(
        db,
        tenant_id=tenant.id,
        ingredient_id=flour.id,
        quantity_delta=Decimal("4"),
        transaction_type="purchase",
        location_id=other_site.id,
        notes="to delivery",
    )
    await db.flush()

    assert len(await stock_service.get_stock_movements(db, tenant.id)) == 2

    only_prod = await stock_service.get_stock_movements(
        db, tenant.id, location_id=site.id
    )
    assert [r["notes"] for r in only_prod] == ["to production"]
    assert only_prod[0]["balance_after"] == Decimal("10")

    only_del = await stock_service.get_stock_movements(
        db, tenant.id, location_id=other_site.id
    )
    assert [r["notes"] for r in only_del] == ["to delivery"]
    assert only_del[0]["balance_after"] == Decimal("4")


async def test_a_movement_with_no_human_behind_it_is_still_returned(
    db: AsyncSession, tenant: Tenant, site: Location, flour: Ingredient
):
    """🔴 The join must be LEFT, and this is the test that proves it.

    Consumption from an online order has no `performed_by`: the system did it.
    An inner join on the user table would silently drop exactly those rows, so
    the history would show every manual correction and none of the sales -- a
    ledger that hides the commonest movement in the system while looking
    complete. Same failure family as a filter that quietly truncates.
    """
    await stock_service.move_stock(
        db,
        tenant_id=tenant.id,
        ingredient_id=flour.id,
        quantity_delta=Decimal("-1"),
        transaction_type="consumption",
        location_id=site.id,
        performed_by=None,
        notes=None,
    )
    await db.flush()

    rows = await stock_service.get_stock_movements(db, tenant.id)
    assert len(rows) == 1, "a system-performed movement was dropped from the history"
    assert rows[0]["performed_by_name"] is None
    assert rows[0]["transaction_type"] == "consumption"


async def test_one_tenants_movements_are_invisible_to_another(
    db: AsyncSession, tenant: Tenant, site: Location, flour: Ingredient
):
    """Tenant isolation on a brand-new read path.

    Every new endpoint is a new chance to forget the tenant filter, and this one
    reads a table that holds every restaurant's stock history in one place.
    """
    await stock_service.move_stock(
        db,
        tenant_id=tenant.id,
        ingredient_id=flour.id,
        quantity_delta=Decimal("5"),
        transaction_type="purchase",
        location_id=site.id,
        notes="ours",
    )
    await db.flush()

    other = Tenant(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        name="Someone Else",
        slug="someone-else",
        is_active=True,
    )
    db.add(other)
    await db.flush()

    assert await stock_service.get_stock_movements(db, tenant.id) != []
    assert await stock_service.get_stock_movements(db, other.id) == []


async def test_limit_and_offset_page_without_repeating_a_row(
    db: AsyncSession, tenant: Tenant, site: Location, flour: Ingredient
):
    """Paging must not overlap or skip.

    Several movements can share a `transaction_date` to the microsecond -- a
    production run consumes its inputs and adds its output in one go -- so the
    ordering needs a stable tiebreak or pages silently duplicate and drop rows.
    """
    for i in range(5):
        await stock_service.move_stock(
            db,
            tenant_id=tenant.id,
            ingredient_id=flour.id,
            quantity_delta=Decimal("1"),
            transaction_type="purchase",
            location_id=site.id,
            notes=f"m{i}",
        )
    await db.flush()

    first = await stock_service.get_stock_movements(db, tenant.id, limit=2, offset=0)
    second = await stock_service.get_stock_movements(db, tenant.id, limit=2, offset=2)
    third = await stock_service.get_stock_movements(db, tenant.id, limit=2, offset=4)

    ids = [r["id"] for r in first + second + third]
    assert len(ids) == 5
    assert len(set(ids)) == 5, "paging returned the same movement twice"


async def test_the_endpoint_is_reachable_and_tenant_scoped(
    client, db: AsyncSession, tenant: Tenant, site: Location, flour: Ingredient,
    admin_token: str,
):
    """Through the API, not just the service.

    The gap this file exists for was never in the service layer -- it was that
    no route called it. A service-only test would have passed throughout.
    """
    await stock_service.move_stock(
        db,
        tenant_id=tenant.id,
        ingredient_id=flour.id,
        quantity_delta=Decimal("-3"),
        transaction_type="waste",
        location_id=site.id,
        notes="dropped it",
    )
    await db.commit()

    resp = await client.get(
        "/api/v1/locations/stock/movements",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["notes"] == "dropped it"
    assert body[0]["transaction_type"] == "waste"


async def test_the_endpoint_requires_authentication(client):
    """Unauthenticated callers get 401, not a stock history."""
    resp = await client.get("/api/v1/locations/stock/movements")
    assert resp.status_code == 401
