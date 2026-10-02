"""D-101: a table stays occupied until every order on its open session is paid AND
completed, the same rule that closes the session (D-79).

Before: the floor plan freed a table as soon as its orders were paid, while the
session stayed open, so the next party's order joined the previous party's bill.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floor import Floor, Table
from app.models.order import Order
from app.models.table_session import TableSession


@pytest_asyncio.fixture
async def seated(db: AsyncSession, tenant, admin_user):
    f = Floor(tenant_id=tenant.id, name="Hall", display_order=1, is_active=True)
    db.add(f)
    await db.flush()
    t = Table(tenant_id=tenant.id, floor_id=f.id, number=5, capacity=4,
              shape="square", status="occupied", is_active=True)
    db.add(t)
    await db.flush()
    s = TableSession(tenant_id=tenant.id, table_id=t.id, status="open", opened_by=admin_user.id)
    db.add(s)
    await db.flush()
    o = Order(tenant_id=tenant.id, order_number="D101-001", order_type="dine_in",
              status="in_kitchen", payment_status="paid", subtotal=10000, tax_amount=1600,
              discount_amount=0, total=11600, table_id=t.id, table_session_id=s.id,
              created_by=admin_user.id)
    db.add(o)
    await db.flush()
    await db.commit()
    return t, o


async def _table_status(client: AsyncClient, token: str, table_id) -> str:
    r = await client.get("/api/v1/floors/status-board", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    for floor in r.json()["floors"]:
        for t in floor["tables"]:
            if t["id"] == str(table_id):
                return t["status"]
    raise AssertionError("table not on the board")


@pytest.mark.asyncio
async def test_paid_but_still_in_kitchen_keeps_table_occupied(client, admin_token, seated):
    table, _ = seated
    assert await _table_status(client, admin_token, table.id) == "occupied"


@pytest.mark.asyncio
async def test_paid_and_completed_frees_table(client, admin_token, db, seated):
    table, order = seated
    order.status = "completed"
    await db.commit()
    assert await _table_status(client, admin_token, table.id) == "available"


@pytest.mark.asyncio
async def test_completed_but_unpaid_keeps_table_occupied(client, admin_token, db, seated):
    table, order = seated
    order.status = "completed"
    order.payment_status = "unpaid"
    await db.commit()
    assert await _table_status(client, admin_token, table.id) == "occupied"
