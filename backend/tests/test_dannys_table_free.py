"""Danny's D-79 (2026-09-27): paying up front must not free the table.

Browser: T1's order was paid at 03:35 while still in the kitchen, and the
dashboard read 0% table utilisation because the payment had closed the table
session and set the table "available". A table now frees only when every order
on it is paid AND completed (a paid order completes when it is served).

Driven through the routes the screens use: session pay, order status.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floor import Floor, Table
from app.models.order import Order
from app.models.payment import PaymentMethod
from app.models.table_session import TableSession

pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def seated(db: AsyncSession, tenant, admin_user):
    """T1 occupied, an open session, one Rs 50 order already in the kitchen."""
    floor = Floor(tenant_id=tenant.id, name="Hall 1", display_order=1, is_active=True)
    db.add(floor)
    await db.flush()
    table = Table(
        tenant_id=tenant.id, floor_id=floor.id, number=1,
        capacity=4, shape="square", status="occupied",
    )
    db.add(table)
    await db.flush()
    session = TableSession(
        tenant_id=tenant.id, table_id=table.id, status="open", opened_by=admin_user.id
    )
    db.add(session)
    await db.flush()
    order = Order(
        tenant_id=tenant.id,
        order_number="260927-001",
        order_type="dine_in",
        status="in_kitchen",
        payment_status="unpaid",
        subtotal=4310,
        tax_amount=690,
        discount_amount=0,
        total=5000,
        table_id=table.id,
        table_session_id=session.id,
        created_by=admin_user.id,
    )
    db.add(order)
    db.add(
        PaymentMethod(
            tenant_id=tenant.id, code="cash", display_name="Cash",
            is_active=True, sort_order=1, requires_reference=False,
        )
    )
    await db.commit()
    return table, session, order


async def _state(db: AsyncSession, table: Table, session: TableSession) -> tuple[str, str]:
    await db.refresh(table)
    await db.refresh(session)
    return table.status, session.status


async def _pay(client: AsyncClient, token: str, session: TableSession) -> None:
    preview = await client.get(
        f"/api/v1/payments/table-sessions/{session.id}/payment-preview", headers=_auth(token)
    )
    assert preview.status_code == 200, preview.text
    paid = await client.post(
        f"/api/v1/payments/table-sessions/{session.id}/pay",
        headers=_auth(token),
        json={"method_code": "cash", "amount": preview.json()["cash_total"], "tendered_amount": 10000},
    )
    assert paid.status_code == 201, paid.text
    assert paid.json()["payment_status"] == "paid"


async def _move(client: AsyncClient, token: str, order: Order, status: str) -> dict:
    r = await client.patch(
        f"/api/v1/orders/{order.id}/status", headers=_auth(token), json={"status": status}
    )
    assert r.status_code == 200, r.text
    return r.json()


async def test_paying_up_front_keeps_the_table_until_the_food_is_served(
    client: AsyncClient, db: AsyncSession, admin_token: str, seated
) -> None:
    table, session, order = seated
    await _pay(client, admin_token, session)
    assert await _state(db, table, session) == ("occupied", "open")

    await _move(client, admin_token, order, "ready")
    assert await _state(db, table, session) == ("occupied", "open")

    served = await _move(client, admin_token, order, "served")
    assert served["status"] == "completed"  # paid + served completes it
    assert await _state(db, table, session) == ("available", "closed")


async def test_paying_after_the_meal_frees_the_table_at_once(
    client: AsyncClient, db: AsyncSession, admin_token: str, seated
) -> None:
    """The usual dine-in order: served first, then the bill. Unchanged."""
    table, session, order = seated
    await _move(client, admin_token, order, "ready")
    await _move(client, admin_token, order, "served")
    assert await _state(db, table, session) == ("occupied", "open")

    await _pay(client, admin_token, session)
    assert await _state(db, table, session) == ("available", "closed")
