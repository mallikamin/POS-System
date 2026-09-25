"""A retired ingredient leaves the Stock screen.

Danny's buys everything, so its in-house items (Karahi Masala Base and six
others) were retired on 2026-09-25. Their stock rows still held old balances
and stayed on the Stock screen and in the low-stock list.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Ingredient
from app.models.location import Location
from app.models.tenant import Tenant
from app.services import stock_service

pytestmark = pytest.mark.asyncio


async def test_retired_ingredient_is_not_listed(db: AsyncSession, tenant: Tenant):
    site = Location(
        tenant_id=tenant.id, name="Restaurant", code="MAIN", location_type="retail",
        invoice_format="thermal_ticket", is_default=True,
    )
    rice = Ingredient(tenant_id=tenant.id, name="Basmati Rice", unit="kg", cost_per_unit=Decimal("380"))
    base = Ingredient(tenant_id=tenant.id, name="Karahi Masala Base", unit="kg",
                      cost_per_unit=Decimal("400"), is_produced=True)
    db.add_all([site, rice, base])
    await db.flush()
    for ing in (rice, base):
        await stock_service.move_stock(
            db, tenant_id=tenant.id, ingredient_id=ing.id, quantity_delta=Decimal("5"),
            transaction_type="purchase", location_id=site.id,
        )
    base.is_active = False
    await db.flush()

    names = [r["ingredient_name"] for r in await stock_service.get_location_stock(db, tenant.id)]
    assert names == ["Basmati Rice"]
