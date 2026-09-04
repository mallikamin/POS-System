"""Martin's round-2 feedback (FZ LLC, 2026-09-04), proven through the routes.

    "Ingredients bought Need to have 2 units and a conversion. The unit you
     buy, the unit you store) use in recipes ... I buy tomato cans..so in the
     purchase order I will request 2 cans. But in my recipes I use grams"

One item, M8. Every test drives HTTP rather than the service layer, for the
reason written at the top of `test_martin_round1.py`: a green service test says
nothing about the route in front of it.

His own example is the spine of this file and it is used with his own numbers
throughout -- a tomato can holding 400 g and costing 8.50 AED -- so that a
failure here reads as "the tomato case broke" rather than as an abstraction.

WARNING: these run on SQLite, which does not enforce `Numeric` precision, so a test
passing here does NOT prove the four-decimal-place widening landed on Postgres.
That has to be checked against the real database after the migration runs, the
way `recipe-module-tz-bug-and-test-gap` in memory says.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant

pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def config(db: AsyncSession, tenant: Tenant) -> RestaurantConfig:
    """A UAE-shaped tenant: AED, 5% VAT inside the shelf price."""
    cfg = RestaurantConfig(
        tenant_id=tenant.id,
        currency="AED",
        timezone="Asia/Dubai",
        payment_flow="order_first",
        tax_inclusive=True,
        default_tax_rate=500,
        cash_tax_rate_bps=500,
        card_tax_rate_bps=500,
    )
    db.add(cfg)
    await db.flush()
    await db.commit()
    return cfg


async def _supplier_and_site(client: AsyncClient, headers) -> tuple[str, str]:
    supplier = await client.post(
        "/api/v1/procurement/suppliers",
        json={"name": "Al Maya", "code": "ALMAYA", "email": "orders@almaya.test"},
        headers=headers,
    )
    assert supplier.status_code == 201, supplier.text
    site = await client.post(
        "/api/v1/locations",
        json={
            "name": "Production Kitchen",
            "code": "PROD",
            "location_type": "production",
            "is_default": True,
        },
        headers=headers,
    )
    assert site.status_code == 201, site.text
    return supplier.json()["id"], site.json()["id"]


async def _tomatoes(client: AsyncClient, headers) -> dict:
    """Martin's tomatoes: bought by the can, cooked by the gram."""
    created = await client.post(
        "/api/v1/inventory/ingredients",
        json={
            "name": "Chopped Tomatoes",
            "unit": "g",
            "purchase_unit": "can",
            "units_per_purchase_unit": 400,
            "purchase_cost_minor": 850,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    return created.json()


# ---------------------------------------------------------------------------
# M8  The ingredient itself
# ---------------------------------------------------------------------------


async def test_a_bought_ingredient_carries_a_purchase_unit_and_a_conversion(
    client: AsyncClient, admin_token: str, tenant: Tenant, config: RestaurantConfig
):
    headers = _auth(admin_token)
    body = await _tomatoes(client, headers)

    assert body["unit"] == "g", "the stocking unit is what recipes spend"
    assert body["purchase_unit"] == "can"
    assert float(body["units_per_purchase_unit"]) == 400.0
    assert float(body["purchase_cost_minor"]) == 850.0

    # 8.50 AED a can, 400 g in a can, so 2.125 fils a gram. The exact value,
    # not 2.13: rounding a rate at the point of division is what put a 0.24%
    # error into every recipe that used it.
    assert float(body["cost_per_unit"]) == pytest.approx(2.125)


async def test_the_cost_per_gram_is_derived_not_typed(
    client: AsyncClient, admin_token: str, tenant: Tenant, config: RestaurantConfig
):
    headers = _auth(admin_token)
    body = await _tomatoes(client, headers)

    # Typing over the derived rate is ignored, the same way a produced
    # ingredient's rollup is (M1). The price of a can is the input.
    patched = await client.patch(
        f"/api/v1/inventory/ingredients/{body['id']}",
        json={"cost_per_unit": 99},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert float(patched.json()["cost_per_unit"]) == pytest.approx(2.125)

    # Changing the can price moves the cost of a gram with it.
    repriced = await client.patch(
        f"/api/v1/inventory/ingredients/{body['id']}",
        json={"purchase_cost_minor": 1000},
        headers=headers,
    )
    assert repriced.status_code == 200, repriced.text
    assert float(repriced.json()["cost_per_unit"]) == pytest.approx(2.5)

    # So does changing the can size.
    resized = await client.patch(
        f"/api/v1/inventory/ingredients/{body['id']}",
        json={"units_per_purchase_unit": 500},
        headers=headers,
    )
    assert resized.status_code == 200, resized.text
    assert float(resized.json()["cost_per_unit"]) == pytest.approx(2.0)


async def test_an_ingredient_without_a_purchase_unit_behaves_exactly_as_before(
    client: AsyncClient, admin_token: str, tenant: Tenant, config: RestaurantConfig
):
    """The regression guard. Every ingredient that existed before M8 is this."""
    headers = _auth(admin_token)
    flour = await client.post(
        "/api/v1/inventory/ingredients",
        json={"name": "Flour", "unit": "kg", "cost_per_unit": 350},
        headers=headers,
    )
    assert flour.status_code == 201, flour.text
    body = flour.json()
    assert body["purchase_unit"] is None
    assert float(body["units_per_purchase_unit"]) == 1.0
    assert float(body["cost_per_unit"]) == 350.0
    # The purchase price shadows the typed cost, so switching a purchase unit
    # on later starts from a sane number rather than from zero.
    assert float(body["purchase_cost_minor"]) == 350.0

    # And the cost is still freely editable, which M1 established.
    patched = await client.patch(
        f"/api/v1/inventory/ingredients/{body['id']}",
        json={"cost_per_unit": 400},
        headers=headers,
    )
    assert patched.status_code == 200
    assert float(patched.json()["cost_per_unit"]) == 400.0


async def test_a_zero_conversion_is_refused(
    client: AsyncClient, admin_token: str, tenant: Tenant, config: RestaurantConfig
):
    """Nothing holds zero grams, and dividing by it takes the module down."""
    headers = _auth(admin_token)
    bad = await client.post(
        "/api/v1/inventory/ingredients",
        json={
            "name": "Broken Tomatoes",
            "unit": "g",
            "purchase_unit": "can",
            "units_per_purchase_unit": 0,
            "purchase_cost_minor": 850,
        },
        headers=headers,
    )
    assert bad.status_code == 422, bad.text


async def test_a_made_in_house_ingredient_has_no_purchase_unit(
    client: AsyncClient, admin_token: str, tenant: Tenant, config: RestaurantConfig
):
    """M1 and M8 meeting: what we make is not what we buy."""
    headers = _auth(admin_token)
    dough = await client.post(
        "/api/v1/inventory/ingredients",
        json={
            "name": "Croissant Dough",
            "unit": "kg",
            "is_produced": True,
            "purchase_unit": "sack",
            "units_per_purchase_unit": 25,
            "purchase_cost_minor": 9999,
        },
        headers=headers,
    )
    assert dough.status_code == 201, dough.text
    body = dough.json()
    assert body["is_produced"] is True
    assert body["purchase_unit"] is None
    assert float(body["units_per_purchase_unit"]) == 1.0
    assert float(body["cost_per_unit"]) == 0.0


# ---------------------------------------------------------------------------
# M8  The purchase order: "I will request 2 cans"
# ---------------------------------------------------------------------------


async def test_a_purchase_order_is_written_in_cans(
    client: AsyncClient, admin_token: str, tenant: Tenant, config: RestaurantConfig
):
    headers = _auth(admin_token)
    supplier_id, site_id = await _supplier_and_site(client, headers)
    tomatoes = await _tomatoes(client, headers)

    po = await client.post(
        "/api/v1/procurement/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "location_id": site_id,
            "lines": [{"ingredient_id": tomatoes["id"], "quantity_ordered": 2}],
        },
        headers=headers,
    )
    assert po.status_code == 201, po.text
    line = po.json()["items"][0]

    assert line["unit"] == "can", "Martin orders cans, not grams"
    assert float(line["quantity_ordered"]) == 2.0
    assert line["stock_unit"] == "g"
    assert float(line["units_per_purchase_unit"]) == 400.0
    # Priced per can, so the order is worth 17.00 AED and not 2 x 2.125 fils.
    assert float(line["unit_price_minor"]) == 850.0
    assert float(line["line_total_minor"]) == 1700.0


async def test_the_supplier_document_asks_for_cans_and_shows_the_weight(
    client: AsyncClient, admin_token: str, tenant: Tenant, config: RestaurantConfig
):
    headers = _auth(admin_token)
    supplier_id, site_id = await _supplier_and_site(client, headers)
    tomatoes = await _tomatoes(client, headers)

    po = await client.post(
        "/api/v1/procurement/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "location_id": site_id,
            "lines": [{"ingredient_id": tomatoes["id"], "quantity_ordered": 2}],
        },
        headers=headers,
    )
    assert po.status_code == 201, po.text

    document = await client.get(
        f"/api/v1/procurement/purchase-orders/{po.json()['id']}/document",
        headers=headers,
    )
    assert document.status_code == 200, document.text
    rendered = document.text  # the endpoint serves the rendered page, not JSON

    assert "2 can" in rendered, "the supplier is asked for cans"
    # And whoever checks the delivery in can see the weight without arithmetic.
    assert "800 g" in rendered


# ---------------------------------------------------------------------------
# M8  The goods receipt: cans in, grams on the shelf
# ---------------------------------------------------------------------------


async def test_receiving_two_cans_books_eight_hundred_grams_of_stock(
    client: AsyncClient, admin_token: str, tenant: Tenant, config: RestaurantConfig
):
    """The crossing point. Both numbers cross the conversion, or neither."""
    headers = _auth(admin_token)
    supplier_id, site_id = await _supplier_and_site(client, headers)
    tomatoes = await _tomatoes(client, headers)

    po = await client.post(
        "/api/v1/procurement/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "location_id": site_id,
            "lines": [{"ingredient_id": tomatoes["id"], "quantity_ordered": 2}],
        },
        headers=headers,
    )
    assert po.status_code == 201, po.text
    po_id = po.json()["id"]
    line_id = po.json()["items"][0]["id"]

    sent = await client.post(
        f"/api/v1/procurement/purchase-orders/{po_id}/send", headers=headers
    )
    assert sent.status_code == 200, sent.text

    received = await client.post(
        f"/api/v1/procurement/purchase-orders/{po_id}/receive",
        json={
            "lines": [
                {"purchase_order_item_id": line_id, "quantity_received": 2}
            ]
        },
        headers=headers,
    )
    assert received.status_code == 200, received.text

    # The receipt itself reports the conversion it used. This assertion exists
    # because the first cut of the route builder forgot to pass this field and
    # the schema's `= 1` default filled it in, so every receipt reported a
    # conversion of 1 while the database held 400. Green tests, wrong wire.
    receipt_line = received.json()["receipt"]["lines"][0]
    assert float(receipt_line["units_per_purchase_unit"]) == 400.0
    assert receipt_line["unit"] == "can"
    assert float(receipt_line["quantity_received"]) == 2.0

    # The PO is settled in cans: two ordered, two received, none outstanding.
    reloaded = await client.get(
        f"/api/v1/procurement/purchase-orders/{po_id}", headers=headers
    )
    assert reloaded.status_code == 200
    settled = reloaded.json()["items"][0]
    assert float(settled["quantity_received"]) == 2.0
    assert float(settled["quantity_outstanding"]) == 0.0
    assert reloaded.json()["status"] == "received"

    # The shelf is counted in grams: 2 cans x 400 g.
    ingredient = await client.get(
        f"/api/v1/inventory/ingredients/{tomatoes['id']}", headers=headers
    )
    assert ingredient.status_code == 200, ingredient.text
    assert float(ingredient.json()["current_stock"]) == 800.0

    # And the cost per gram did not become the cost per can. This is the
    # failure that would double-count food cost by 400x and still look
    # plausible on a screen, so it is asserted explicitly.
    assert float(ingredient.json()["purchase_cost_minor"]) == 850.0
    assert float(ingredient.json()["cost_per_unit"]) == pytest.approx(2.125)


async def test_a_price_change_on_delivery_reprices_the_gram_not_just_the_can(
    client: AsyncClient, admin_token: str, tenant: Tenant, config: RestaurantConfig
):
    headers = _auth(admin_token)
    supplier_id, site_id = await _supplier_and_site(client, headers)
    tomatoes = await _tomatoes(client, headers)

    po = await client.post(
        "/api/v1/procurement/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "location_id": site_id,
            "lines": [{"ingredient_id": tomatoes["id"], "quantity_ordered": 3}],
        },
        headers=headers,
    )
    assert po.status_code == 201, po.text
    po_id = po.json()["id"]
    line_id = po.json()["items"][0]["id"]
    await client.post(
        f"/api/v1/procurement/purchase-orders/{po_id}/send", headers=headers
    )

    # The van turns up and the cans now cost 10.00 each, not 8.50.
    received = await client.post(
        f"/api/v1/procurement/purchase-orders/{po_id}/receive",
        json={
            "lines": [
                {
                    "purchase_order_item_id": line_id,
                    "quantity_received": 3,
                    "unit_price_minor": 1000,
                }
            ]
        },
        headers=headers,
    )
    assert received.status_code == 200, received.text

    ingredient = await client.get(
        f"/api/v1/inventory/ingredients/{tomatoes['id']}", headers=headers
    )
    assert float(ingredient.json()["current_stock"]) == 1200.0
    assert float(ingredient.json()["purchase_cost_minor"]) == 1000.0
    assert float(ingredient.json()["cost_per_unit"]) == pytest.approx(2.5)


async def test_receiving_an_unconverted_ingredient_is_unchanged(
    client: AsyncClient, admin_token: str, tenant: Tenant, config: RestaurantConfig
):
    """The regression guard for the receiving path: 25 kg in, 25 kg on hand."""
    headers = _auth(admin_token)
    supplier_id, site_id = await _supplier_and_site(client, headers)
    flour = await client.post(
        "/api/v1/inventory/ingredients",
        json={"name": "Flour", "unit": "kg", "cost_per_unit": 350},
        headers=headers,
    )
    assert flour.status_code == 201

    po = await client.post(
        "/api/v1/procurement/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "location_id": site_id,
            "lines": [{"ingredient_id": flour.json()["id"], "quantity_ordered": 25}],
        },
        headers=headers,
    )
    assert po.status_code == 201, po.text
    po_id = po.json()["id"]
    line = po.json()["items"][0]
    assert line["unit"] == "kg"
    assert float(line["units_per_purchase_unit"]) == 1.0
    assert float(line["unit_price_minor"]) == 350.0

    await client.post(
        f"/api/v1/procurement/purchase-orders/{po_id}/send", headers=headers
    )
    received = await client.post(
        f"/api/v1/procurement/purchase-orders/{po_id}/receive",
        json={
            "lines": [
                {"purchase_order_item_id": line["id"], "quantity_received": 25}
            ]
        },
        headers=headers,
    )
    assert received.status_code == 200, received.text

    ingredient = await client.get(
        f"/api/v1/inventory/ingredients/{flour.json()['id']}", headers=headers
    )
    assert float(ingredient.json()["current_stock"]) == 25.0
    assert float(ingredient.json()["cost_per_unit"]) == 350.0


# ---------------------------------------------------------------------------
# M8  Recipes still spend grams
# ---------------------------------------------------------------------------


async def test_a_recipe_spends_grams_and_costs_them_at_the_gram_rate(
    client: AsyncClient, admin_token: str, tenant: Tenant, config: RestaurantConfig
):
    """"But in my recipes I use grams." The end of Martin's sentence."""
    headers = _auth(admin_token)
    tomatoes = await _tomatoes(client, headers)

    sauce = await client.post(
        "/api/v1/inventory/ingredients",
        json={"name": "Tomato Sauce", "unit": "kg", "is_produced": True},
        headers=headers,
    )
    assert sauce.status_code == 201, sauce.text

    # 200 g of tomatoes, yielding 1 batch. 200 x 2.125 = 425 fils.
    recipe = await client.post(
        "/api/v1/inventory/recipes",
        json={
            "produces_ingredient_id": sauce.json()["id"],
            "yield_servings": 1,
            "recipe_items": [
                {"ingredient_id": tomatoes["id"], "quantity": 200, "unit": "g"}
            ],
        },
        headers=headers,
    )
    assert recipe.status_code == 201, recipe.text
    item = recipe.json()["recipe_items"][0]

    assert item["unit"] == "g", "the recipe is written in the stocking unit"
    assert float(item["cost_per_unit_snapshot"]) == pytest.approx(2.125)
    # 425, not 200 x 850 = 170000. The whole point of the conversion.
    assert float(item["total_cost"]) == pytest.approx(425.0)
    assert float(recipe.json()["cost_per_serving"]) == pytest.approx(425.0)

