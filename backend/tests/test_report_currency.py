"""Every report export must label money in the TENANT's currency.

The defect this pins: `/reports/sales-summary/csv` hardcoded "(PKR)" on all
13 money rows, so Chick Shack (GBP) downloaded a sheet reading
`Total Revenue (PKR),371.07` for money that was taken in pounds. The
neighbouring online reports (OI-58) already did this correctly via
`public_order_service.get_currency`, which is why
`prepaid_vs_cod_*.csv` from the same page and the same date range said GBP.

Both directions are asserted deliberately. A test that only checks "GBP
appears" would still pass if the label were hardcoded the other way, and a
test that only checks the GBP tenant would not catch a change that broke
every existing PKR tenant.
"""

from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant

pytestmark = pytest.mark.asyncio

# Every money row the sales-summary CSV emits. If a row is added to the
# exporter without a currency label, this list is what catches it.
MONEY_ROWS = [
    "Total Revenue",
    "Total Discount",
    "Net Revenue",
    "Avg Order Value",
    "Total Tax",
    "Cash Revenue",
    "Card Revenue",
    "Other Revenue",
    "Dine-In Revenue",
    "Takeaway Revenue",
    "Call Center Revenue",
    "Online Revenue",
]


async def _set_currency(db: AsyncSession, tenant: Tenant, currency: str) -> None:
    db.add(RestaurantConfig(tenant_id=tenant.id, currency=currency))
    await db.commit()


async def _fetch_csv(client: AsyncClient, token: str) -> str:
    today = date.today().isoformat()
    resp = await client.get(
        "/api/v1/reports/sales-summary/csv",
        params={"date_from": today, "date_to": today},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    return resp.text


async def test_sales_summary_csv_labels_money_in_gbp_for_a_gbp_tenant(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_token: str,
):
    await _set_currency(db, tenant, "GBP")
    text = await _fetch_csv(client, admin_token)

    for row in MONEY_ROWS:
        assert f"{row} (GBP)" in text, f"{row!r} not labelled GBP"
    # The whole point: not a single PKR label survives for a GBP shop.
    assert "PKR" not in text


async def test_sales_summary_csv_still_labels_pkr_for_a_pkr_tenant(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_token: str,
):
    await _set_currency(db, tenant, "PKR")
    text = await _fetch_csv(client, admin_token)

    for row in MONEY_ROWS:
        assert f"{row} (PKR)" in text, f"{row!r} not labelled PKR"
    assert "GBP" not in text


async def test_sales_summary_csv_falls_back_to_pkr_with_no_config_row(
    client: AsyncClient,
    tenant: Tenant,
    admin_token: str,
):
    # No RestaurantConfig at all: `get_currency` returns its "PKR" fallback
    # rather than raising or emitting an empty "()" label.
    text = await _fetch_csv(client, admin_token)

    assert "Total Revenue (PKR)" in text
    assert "()" not in text


async def test_non_money_rows_carry_no_currency_label(
    client: AsyncClient,
    db: AsyncSession,
    tenant: Tenant,
    admin_token: str,
):
    # Order COUNTS are not money. Labelling them with a currency was never
    # the bug, and fixing the money rows must not start doing it.
    await _set_currency(db, tenant, "GBP")
    text = await _fetch_csv(client, admin_token)

    for row in (
        "Total Orders",
        "Dine-In Orders",
        "Takeaway Orders",
        "Call Center Orders",
        "Online Orders",
    ):
        assert f"{row}\n" in text or f"{row}," in text
        assert f"{row} (" not in text
