"""Danny's go-live figures (2026-09-26), proven through the routes.

    D-61 "When Danny's starts, the owner must enter opening stock for every item
         in one go and carry on."
    D-63 "Record money in that is not a sale (e.g. scrap sale, rent received,
         event deposit), per day, with category and cash/bank."

Every test drives HTTP, not the service: a green service test says nothing
about the route in front of it (ERROR_LOG, 2026-09-01).

WARNING: these run on SQLite, which keeps server-default timestamps as
second-resolution text. Anything that compares a stored timestamp to a bound
one is checked with a positive control, so an empty result cannot pass by
accident (ERROR_LOG, 2026-08-01 and D-67).
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _site(client: AsyncClient, headers) -> str:
    created = await client.post(
        "/api/v1/locations",
        json={
            "name": "Main Kitchen",
            "code": "MAIN",
            "location_type": "production",
            "is_default": True,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def _ingredient(client: AsyncClient, headers, **kwargs) -> dict:
    payload = {
        "name": "Chicken (Karahi Cut)",
        "category": "Meat",
        "unit": "kg",
        "cost_per_unit": 90000,  # Rs 900 per kg, in paisa
        **kwargs,
    }
    created = await client.post(
        "/api/v1/inventory/ingredients", json=payload, headers=headers
    )
    assert created.status_code == 201, created.text
    return created.json()


async def _position(client: AsyncClient, headers, site: str) -> dict[str, float]:
    rows = await client.get(
        "/api/v1/locations/stock/position",
        params={"location_id": site},
        headers=headers,
    )
    assert rows.status_code == 200, rows.text
    return {row["ingredient_name"]: row["quantity"] for row in rows.json()}


async def test_opening_count_puts_the_counted_stock_on_the_shelf(
    client: AsyncClient, admin_token: str
) -> None:
    """Two ingredients with no stock row yet: one save, both on the shelf."""
    headers = _auth(admin_token)
    site = await _site(client, headers)
    chicken = await _ingredient(client, headers)
    tomato = await _ingredient(client, headers, name="Tomato", cost_per_unit=20000)

    saved = await client.post(
        "/api/v1/locations/stock/opening-count",
        json={
            "location_id": site,
            "lines": [
                {"ingredient_id": chicken["id"], "counted_quantity": 12.5},
                {"ingredient_id": tomato["id"], "counted_quantity": 4},
            ],
        },
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["lines_counted"] == 2
    assert body["movements"] == 2
    assert body["costs_updated"] == 0
    # 12.5 kg x Rs 900 + 4 kg x Rs 200, in paisa.
    assert body["stock_value"] == 1_125_000 + 80_000
    assert body["reference_number"].startswith("OPENING-")

    assert await _position(client, headers, site) == {
        "Chicken (Karahi Cut)": 12.5,
        "Tomato": 4,
    }

    history = await client.get(
        "/api/v1/locations/stock/movements",
        params={"ingredient_id": chicken["id"], "location_id": site},
        headers=headers,
    )
    moves = history.json()
    assert [(m["transaction_type"], m["quantity"]) for m in moves] == [("opening", 12.5)]


async def test_saving_the_same_count_again_moves_nothing(
    client: AsyncClient, admin_token: str
) -> None:
    """The count is what is on the shelf, not a change: a second save of the
    same figures must not double the stock, and a corrected figure books only
    the difference."""
    headers = _auth(admin_token)
    site = await _site(client, headers)
    chicken = await _ingredient(client, headers)
    body = {
        "location_id": site,
        "lines": [{"ingredient_id": chicken["id"], "counted_quantity": 10}],
    }

    first = await client.post("/api/v1/locations/stock/opening-count", json=body, headers=headers)
    again = await client.post("/api/v1/locations/stock/opening-count", json=body, headers=headers)
    assert first.json()["movements"] == 1
    assert again.status_code == 200, again.text
    assert again.json()["movements"] == 0
    assert (await _position(client, headers, site))["Chicken (Karahi Cut)"] == 10

    body["lines"][0]["counted_quantity"] = 9.5
    fixed = await client.post("/api/v1/locations/stock/opening-count", json=body, headers=headers)
    assert fixed.json()["movements"] == 1
    assert (await _position(client, headers, site))["Chicken (Karahi Cut)"] == 9.5

    history = await client.get(
        "/api/v1/locations/stock/movements",
        params={"ingredient_id": chicken["id"], "location_id": site},
        headers=headers,
    )
    assert sorted(m["quantity"] for m in history.json()) == [-0.5, 10]


async def test_a_cost_on_the_count_becomes_the_ingredient_cost(
    client: AsyncClient, admin_token: str
) -> None:
    headers = _auth(admin_token)
    site = await _site(client, headers)
    chicken = await _ingredient(client, headers)

    saved = await client.post(
        "/api/v1/locations/stock/opening-count",
        json={
            "location_id": site,
            "lines": [
                {"ingredient_id": chicken["id"], "counted_quantity": 2, "unit_cost": 95000}
            ],
        },
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["costs_updated"] == 1
    assert saved.json()["stock_value"] == 190_000

    fetched = await client.get(f"/api/v1/inventory/ingredients/{chicken['id']}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    assert float(fetched.json()["cost_per_unit"]) == 95000


async def test_a_cost_is_not_taken_for_an_ingredient_bought_by_the_can(
    client: AsyncClient, admin_token: str
) -> None:
    """Its cost per unit is derived from the purchase price; overwriting one
    without the other would leave the ingredient with two prices."""
    headers = _auth(admin_token)
    site = await _site(client, headers)
    tomato = await _ingredient(
        client,
        headers,
        name="Tinned Tomato",
        unit="g",
        purchase_unit="can",
        units_per_purchase_unit=400,
        purchase_cost_minor=40000,
    )
    before = float(tomato["cost_per_unit"])

    saved = await client.post(
        "/api/v1/locations/stock/opening-count",
        json={
            "location_id": site,
            "lines": [
                {"ingredient_id": tomato["id"], "counted_quantity": 800, "unit_cost": 999}
            ],
        },
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["costs_updated"] == 0
    fetched = await client.get(f"/api/v1/inventory/ingredients/{tomato['id']}", headers=headers)
    assert float(fetched.json()["cost_per_unit"]) == before


async def test_an_ingredient_can_only_be_counted_once_per_save(
    client: AsyncClient, admin_token: str
) -> None:
    headers = _auth(admin_token)
    site = await _site(client, headers)
    chicken = await _ingredient(client, headers)
    line = {"ingredient_id": chicken["id"], "counted_quantity": 1}

    resp = await client.post(
        "/api/v1/locations/stock/opening-count",
        json={"location_id": site, "lines": [line, line]},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_another_restaurants_ingredient_is_refused(
    client: AsyncClient, admin_token: str, other_tenant_token: str
) -> None:
    """Tenant scope: an id from another restaurant moves nothing anywhere."""
    headers = _auth(admin_token)
    site = await _site(client, headers)
    foreign = await _ingredient(client, _auth(other_tenant_token), name="Foreign")

    resp = await client.post(
        "/api/v1/locations/stock/opening-count",
        json={
            "location_id": site,
            "lines": [{"ingredient_id": foreign["id"], "counted_quantity": 3}],
        },
        headers=headers,
    )
    assert resp.status_code == 400, resp.text
    assert await _position(client, headers, site) == {}


async def test_a_cashier_cannot_book_opening_stock(
    client: AsyncClient, admin_token: str, cashier_token: str
) -> None:
    headers = _auth(admin_token)
    site = await _site(client, headers)
    chicken = await _ingredient(client, headers)

    resp = await client.post(
        "/api/v1/locations/stock/opening-count",
        json={
            "location_id": site,
            "lines": [{"ingredient_id": chicken["id"], "counted_quantity": 3}],
        },
        headers=_auth(cashier_token),
    )
    assert resp.status_code == 403


async def test_opening_stock_is_not_usage_on_the_day_summary(
    client: AsyncClient, admin_token: str
) -> None:
    """The shelf being filled is not food used. Positive control: a manual
    adjustment on the same day DOES appear, so an empty list cannot pass just
    because the SQLite date window matched nothing."""
    headers = _auth(admin_token)
    site = await _site(client, headers)
    chicken = await _ingredient(client, headers)
    tomato = await _ingredient(client, headers, name="Tomato", cost_per_unit=20000)

    counted = await client.post(
        "/api/v1/locations/stock/opening-count",
        json={
            "location_id": site,
            "lines": [{"ingredient_id": chicken["id"], "counted_quantity": 20}],
        },
        headers=headers,
    )
    assert counted.status_code == 200, counted.text
    adjusted = await client.post(
        "/api/v1/locations/stock/adjust",
        json={
            "location_id": site,
            "ingredient_id": tomato["id"],
            "quantity_delta": -1,
            "reason": "Dropped a crate",
        },
        headers=headers,
    )
    assert adjusted.status_code == 200, adjusted.text

    report = await client.get(
        "/api/v1/reports/z-report",
        # No config row: the test tenant's day is the UTC day.
        params={"date": datetime.now(timezone.utc).date().isoformat()},
        headers=headers,
    )
    assert report.status_code == 200, report.text
    names = {r["ingredient_name"] for r in report.json()["inventory_used"]["rows"]}
    assert names == {"Tomato"}


# ===========================================================================
# D-63 -- other income
# ===========================================================================


def _today() -> str:
    # No config row: the test tenant's day is the UTC day.
    return datetime.now(timezone.utc).date().isoformat()


async def _income(client: AsyncClient, headers, **kwargs):
    payload = {
        "received_on": _today(),
        "payer": "Kabari (scrap dealer)",
        "amount_minor": 350000,
        "method": "cash",
        **kwargs,
    }
    return await client.post("/api/v1/other-income", json=payload, headers=headers)


async def test_income_categories_start_with_the_three_examples(
    client: AsyncClient, admin_token: str
) -> None:
    headers = _auth(admin_token)
    first = await client.get("/api/v1/other-income/categories", headers=headers)
    again = await client.get("/api/v1/other-income/categories", headers=headers)
    assert first.status_code == 200, first.text
    names = [row["name"] for row in first.json()]
    assert names == ["Scrap Sale", "Rent Received", "Event Deposit", "Other"]
    assert [row["name"] for row in again.json()] == names  # seeded once


async def test_income_is_recorded_and_listed_with_its_category(
    client: AsyncClient, admin_token: str
) -> None:
    headers = _auth(admin_token)
    cats = (await client.get("/api/v1/other-income/categories", headers=headers)).json()
    scrap = next(c for c in cats if c["name"] == "Scrap Sale")

    created = await _income(client, headers, category_id=scrap["id"])
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["category_name"] == "Scrap Sale"
    assert body["amount_minor"] == 350000
    assert body["method"] == "cash"
    assert body["recorded_by_name"]

    await _income(client, headers, payer="Upstairs tenant", amount_minor=2_000_000, method="bank")
    listed = await client.get("/api/v1/other-income", headers=headers)
    assert {r["payer"] for r in listed.json()} == {"Kabari (scrap dealer)", "Upstairs tenant"}
    banked = await client.get("/api/v1/other-income", params={"method": "bank"}, headers=headers)
    assert [r["payer"] for r in banked.json()] == ["Upstairs tenant"]

    cats = (await client.get("/api/v1/other-income/categories", headers=headers)).json()
    assert next(c for c in cats if c["name"] == "Scrap Sale")["income_count"] == 1


async def test_income_input_is_checked(
    client: AsyncClient, admin_token: str, other_tenant_token: str
) -> None:
    headers = _auth(admin_token)
    assert (await _income(client, headers, method="card")).status_code == 422
    assert (await _income(client, headers, amount_minor=0)).status_code == 422

    foreign = (
        await client.get("/api/v1/other-income/categories", headers=_auth(other_tenant_token))
    ).json()[0]
    refused = await _income(client, headers, category_id=foreign["id"])
    assert refused.status_code == 400, refused.text


async def test_income_can_be_corrected_and_removed(
    client: AsyncClient, admin_token: str
) -> None:
    headers = _auth(admin_token)
    cats = (await client.get("/api/v1/other-income/categories", headers=headers)).json()
    rent = next(c for c in cats if c["name"] == "Rent Received")
    income_id = (await _income(client, headers)).json()["id"]

    fixed = await client.patch(
        f"/api/v1/other-income/{income_id}",
        json={"amount_minor": 300000, "category_id": rent["id"], "method": "bank"},
        headers=headers,
    )
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["amount_minor"] == 300000
    assert fixed.json()["category_name"] == "Rent Received"
    assert fixed.json()["method"] == "bank"

    cleared = await client.patch(
        f"/api/v1/other-income/{income_id}", json={"payer": None}, headers=headers
    )
    assert cleared.status_code == 400, cleared.text

    gone = await client.delete(f"/api/v1/other-income/{income_id}", headers=headers)
    assert gone.status_code == 204
    assert (await client.get("/api/v1/other-income", headers=headers)).json() == []
    again = await client.delete(f"/api/v1/other-income/{income_id}", headers=headers)
    assert again.status_code == 404


async def test_income_is_the_restaurants_own(
    client: AsyncClient, admin_token: str, cashier_token: str, other_tenant_token: str
) -> None:
    headers = _auth(admin_token)
    income_id = (await _income(client, headers)).json()["id"]

    assert (await client.get("/api/v1/other-income", headers=_auth(cashier_token))).status_code == 403
    theirs = await client.get("/api/v1/other-income", headers=_auth(other_tenant_token))
    assert theirs.status_code == 200
    assert theirs.json() == []
    poke = await client.patch(
        f"/api/v1/other-income/{income_id}",
        json={"amount_minor": 1},
        headers=_auth(other_tenant_token),
    )
    assert poke.status_code == 400


async def test_cash_income_enters_the_day_cash_position_and_bank_does_not(
    client: AsyncClient, admin_token: str
) -> None:
    """Rs 3,500 scrap in cash and Rs 20,000 rent to the bank, drawer opened
    with Rs 5,000: the day holds Rs 3,500 more cash and the drawer should
    hold Rs 8,500. The bank receipt never passed through the till."""
    headers = _auth(admin_token)
    opened = await client.post(
        "/api/v1/payments/drawer/open", json={"opening_float": 500000}, headers=headers
    )
    assert opened.status_code in (200, 201), opened.text
    await _income(client, headers)
    await _income(client, headers, payer="Upstairs tenant", amount_minor=2_000_000, method="bank")

    report = await client.get(
        "/api/v1/reports/z-report", params={"date": _today()}, headers=headers
    )
    assert report.status_code == 200, report.text
    cash = report.json()["cash_position"]
    assert cash["other_cash_in"] == 350000
    assert [line["payer"] for line in cash["other_cash_income"]] == ["Kabari (scrap dealer)"]
    assert cash["net_cash"] == 350000
    assert len(cash["drawers"]) == 1
    assert cash["drawers"][0]["other_cash_in"] == 350000
    assert cash["drawers"][0]["expected_in_drawer"] == 850000

# ===========================================================================
# D-62 -- opening cash balance, rolled forward on the day summary
# ===========================================================================


def _utc_day(offset: int) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=offset)).isoformat()


async def test_opening_balance_is_one_record_that_can_be_corrected(
    client: AsyncClient, admin_token: str, cashier_token: str
) -> None:
    headers = _auth(admin_token)
    none_yet = await client.get("/api/v1/opening-balance", headers=headers)
    assert none_yet.status_code == 200
    assert none_yet.json() is None

    first = await client.put(
        "/api/v1/opening-balance",
        json={"as_of": _utc_day(0), "cash_minor": 1_000_000},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    fixed = await client.put(
        "/api/v1/opening-balance",
        json={"as_of": _utc_day(-1), "cash_minor": 900_000, "notes": "Recounted"},
        headers=headers,
    )
    assert fixed.status_code == 200, fixed.text
    got = (await client.get("/api/v1/opening-balance", headers=headers)).json()
    assert (got["as_of"], got["cash_minor"], got["notes"]) == (_utc_day(-1), 900_000, "Recounted")
    assert got["recorded_by_name"]

    negative = await client.put(
        "/api/v1/opening-balance",
        json={"as_of": _utc_day(0), "cash_minor": -1},
        headers=headers,
    )
    assert negative.status_code == 422
    cashier = await client.put(
        "/api/v1/opening-balance",
        json={"as_of": _utc_day(0), "cash_minor": 1},
        headers=_auth(cashier_token),
    )
    assert cashier.status_code == 403


async def test_cash_in_hand_rolls_forward_from_the_opening_balance(
    client: AsyncClient, db, admin_token: str, order
) -> None:
    """Opening Rs 10,000 at the start of yesterday. Yesterday: Rs 500 scrap
    in cash, Rs 200 electrician paid in cash, Rs 100 cash sale. Today: Rs 300
    rent received in cash.

        yesterday  start 1,000,000   end 1,000,000 + 50,000 - 20,000 + 10,000
        today      start 1,040,000   end 1,040,000 + 30,000

    The Rs 100 sale is a real payment backdated to yesterday noon, so the
    payment leg of the roll-forward is exercised, not just the dated rows."""
    from app.models.payment import Payment
    from sqlalchemy import select

    headers = _auth(admin_token)
    yday, today = _utc_day(-1), _utc_day(0)
    await client.put(
        "/api/v1/opening-balance",
        json={"as_of": yday, "cash_minor": 1_000_000},
        headers=headers,
    )
    await _income(client, headers, received_on=yday, amount_minor=50_000)
    await _income(client, headers, received_on=today, payer="Upstairs tenant", amount_minor=30_000)
    await _income(client, headers, received_on=yday, payer="Bank rent", amount_minor=999_999, method="bank")
    spent = await client.post(
        "/api/v1/expenses",
        json={
            "expense_date": yday,
            "payee": "Electrician",
            "amount_minor": 20_000,
            "status": "paid",
            "payment_method": "Cash",
            "paid_on": yday,
        },
        headers=headers,
    )
    assert spent.status_code == 201, spent.text
    paid = await client.post(
        "/api/v1/payments",
        json={
            "order_id": str(order.id),
            "method_code": "cash",
            "amount": 10_000,
            "tendered_amount": 10_000,
        },
        headers=headers,
    )
    assert paid.status_code == 201, paid.text
    payment = (await db.execute(select(Payment))).scalar_one()
    payment.created_at = datetime.combine(
        datetime.now(timezone.utc).date() - timedelta(days=1), time(12, 0)
    )
    await db.commit()

    def cash_in_hand(day: str) -> dict | None:
        return day_reports[day]["cash_position"]["cash_in_hand"]

    day_reports = {}
    for day in (_utc_day(-2), yday, today):
        r = await client.get("/api/v1/reports/z-report", params={"date": day}, headers=headers)
        assert r.status_code == 200, r.text
        day_reports[day] = r.json()

    assert cash_in_hand(_utc_day(-2)) is None
    # Positive control: the backdated sale is on yesterday's report.
    assert day_reports[yday]["cash_position"]["cash_taken"] == 10_000
    assert cash_in_hand(yday)["start_of_day"] == 1_000_000
    assert cash_in_hand(yday)["end_of_day"] == 1_040_000
    assert cash_in_hand(today)["start_of_day"] == 1_040_000
    assert cash_in_hand(today)["end_of_day"] == 1_070_000