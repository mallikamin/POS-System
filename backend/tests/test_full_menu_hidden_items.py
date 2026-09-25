"""The POS menu with a hidden dish in it.

`/menu/full` leaves unavailable dishes out. It used to do that by reassigning
`category.items`, which SQLAlchemy reads as "these dishes left the category":
the request's commit then wrote `category_id = NULL` for every hidden dish, the
NOT NULL constraint refused it, and the whole POS menu answered 500. Found on
Danny's production tenant, 2026-09-25, the first tenant with a hidden dish.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu import Category, MenuItem
from app.models.tenant import Tenant

pytestmark = pytest.mark.asyncio


async def test_hidden_dish_is_left_out_and_left_alone(
    client, db: AsyncSession, tenant: Tenant, admin_token: str
):
    cat = Category(tenant_id=tenant.id, name="Pakistani", display_order=1, is_active=True)
    db.add(cat)
    await db.flush()
    on_sale = MenuItem(tenant_id=tenant.id, category_id=cat.id, name="Chicken Karahi", price=188900)
    hidden = MenuItem(
        tenant_id=tenant.id, category_id=cat.id, name="Chicken Karahi (Half)",
        price=188900, is_available=False,
    )
    db.add_all([on_sale, hidden])
    await db.commit()
    cat_id, hidden_id = cat.id, hidden.id

    headers = {"Authorization": f"Bearer {admin_token}"}
    for _ in range(2):  # a second call must not find anything changed by the first
        resp = await client.get("/api/v1/menu/full", headers=headers)
        assert resp.status_code == 200, resp.text
        names = [i["name"] for c in resp.json()["categories"] for i in c["items"]]
        assert names == ["Chicken Karahi"]

    db.expire_all()
    row = (
        await db.execute(select(MenuItem.category_id).where(MenuItem.id == hidden_id))
    ).scalar_one()
    assert row == cat_id, "the hidden dish must keep its category"
