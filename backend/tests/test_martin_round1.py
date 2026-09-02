"""Martin's round-1 feedback (FZ LLC, 2026-09-02), proven through the routes.

Every test here goes through HTTP, not the service layer, because the last
batch shipped with 17 green service tests and a route that returned 400 to
every client (ERROR_LOG 2026-09-01). The seven items:

  M1  bought vs made-in-house ingredients: a produced ingredient's cost is
      the recipe engine's and cannot be typed over; the list says which
      recipe owns it.
  M2  purchase order "additional comments" print on the supplier document.
  M3  receipt format (thermal / a4) is a tenant setting and rides on the
      receipt payload.
  M4  sales channels can be POS-visible, and an order carries its channel's
      name back to the till.
  M5  a delivery fee / service charge can be added at the till, sits outside
      the tax, and survives a payment-mode re-total.
  M6  a customer can be a company with a TRN, and the back office can list
      and search customers.
  M7  is a frontend-only fix (admin drawer on a phone); nothing to test here.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu import Category, MenuItem
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


@pytest_asyncio.fixture
async def croissant(db: AsyncSession, tenant: Tenant) -> MenuItem:
    category = Category(tenant_id=tenant.id, name="Pastries", display_order=1)
    db.add(category)
    await db.flush()
    item = MenuItem(
        tenant_id=tenant.id, category_id=category.id, name="Croissant", price=900
    )
    db.add(item)
    await db.flush()
    await db.commit()
    return item


# ---------------------------------------------------------------------------
# M1  Ingredients: bought vs made in-house
# ---------------------------------------------------------------------------


async def test_produced_ingredient_cost_belongs_to_the_recipe(
    client: AsyncClient, admin_token: str, tenant: Tenant, config: RestaurantConfig
):
    headers = _auth(admin_token)

    # A bought ingredient: the cost typed in is the cost.
    flour = await client.post(
        "/api/v1/inventory/ingredients",
        json={"name": "Flour", "unit": "kg", "cost_per_unit": 350},
        headers=headers,
    )
    assert flour.status_code == 201, flour.text
    assert flour.json()["is_produced"] is False
    assert flour.json()["cost_per_unit"] == 350.0

    # A made-in-house ingredient: declared as such before any recipe exists,
    # and whatever cost was sent is ignored because nothing has calculated it.
    dough = await client.post(
        "/api/v1/inventory/ingredients",
        json={"name": "Croissant Dough", "unit": "kg", "cost_per_unit": 999,
              "is_produced": True},
        headers=headers,
    )
    assert dough.status_code == 201, dough.text
    body = dough.json()
    assert body["is_produced"] is True
    assert body["cost_per_unit"] == 0.0
    assert body["production_recipe_name"] is None  # "No recipe yet"

    # Typing a cost over a produced ingredient is dropped, not applied.
    patched = await client.patch(
        f"/api/v1/inventory/ingredients/{body['id']}",
        json={"cost_per_unit": 1234, "notes": "hand-typed"},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["cost_per_unit"] == 0.0
    assert patched.json()["notes"] == "hand-typed"

    # Build the recipe that makes it: 2.5 kg flour -> 5 kg dough.
    recipe = await client.post(
        "/api/v1/inventory/recipes",
        json={
            "produces_ingredient_id": body["id"],
            "yield_servings": 5,
            "recipe_items": [
                {"ingredient_id": flour.json()["id"], "quantity": 2.5, "unit": "kg"}
            ],
        },
        headers=headers,
    )
    assert recipe.status_code == 201, recipe.text

    # Now the list names the owning recipe and carries the calculated cost:
    # 2.5 * 350 / 5 = 175 per kg.
    listed = await client.get("/api/v1/inventory/ingredients", headers=headers)
    assert listed.status_code == 200
    rows = {r["name"]: r for r in listed.json()}
    assert rows["Croissant Dough"]["cost_per_unit"] == 175.0
    assert rows["Croissant Dough"]["production_recipe_name"] == "Croissant Dough v1"
    assert rows["Croissant Dough"]["production_recipe_id"] == recipe.json()["id"]
    assert rows["Flour"]["production_recipe_name"] is None

    # And it cannot be flipped back to "bought" while the recipe is active.
    flip = await client.patch(
        f"/api/v1/inventory/ingredients/{body['id']}",
        json={"is_produced": False},
        headers=headers,
    )
    assert flip.status_code == 400
    assert "Delete that recipe" in flip.json()["detail"]

    # A bought ingredient's cost is still editable, as before.
    flour_patch = await client.patch(
        f"/api/v1/inventory/ingredients/{flour.json()['id']}",
        json={"cost_per_unit": 400},
        headers=headers,
    )
    assert flour_patch.status_code == 200
    assert flour_patch.json()["cost_per_unit"] == 400.0


# ---------------------------------------------------------------------------
# M2  Purchase order additional comments
# ---------------------------------------------------------------------------


async def test_purchase_order_additional_comments_print_on_the_document(
    client: AsyncClient, admin_token: str, tenant: Tenant, config: RestaurantConfig
):
    headers = _auth(admin_token)

    supplier = await client.post(
        "/api/v1/procurement/suppliers",
        json={"name": "Al Maya", "code": "ALMAYA", "email": "orders@almaya.test"},
        headers=headers,
    )
    assert supplier.status_code == 201, supplier.text
    site = await client.post(
        "/api/v1/locations",
        json={"name": "Production Kitchen", "code": "PROD",
              "location_type": "production", "is_default": True},
        headers=headers,
    )
    assert site.status_code == 201, site.text
    flour = await client.post(
        "/api/v1/inventory/ingredients",
        json={"name": "Flour", "unit": "kg", "cost_per_unit": 350},
        headers=headers,
    )
    assert flour.status_code == 201

    po = await client.post(
        "/api/v1/procurement/purchase-orders",
        json={
            "supplier_id": supplier.json()["id"],
            "location_id": site.json()["id"],
            "lines": [{"ingredient_id": flour.json()["id"], "quantity_ordered": 25}],
            "delivery_instructions": "Deliver before 9am",
            "notes": "Please invoice in two parts & quote PO number.",
        },
        headers=headers,
    )
    assert po.status_code == 201, po.text
    assert po.json()["notes"] == "Please invoice in two parts & quote PO number."

    document = await client.get(
        f"/api/v1/procurement/purchase-orders/{po.json()['id']}/document",
        headers=headers,
    )
    assert document.status_code == 200
    html = document.text
    assert "Delivery instructions" in html
    assert "Deliver before 9am" in html
    assert "Additional comments" in html
    # Escaped on the way out, like every other free-text field on the page.
    assert "Please invoice in two parts &amp; quote PO number." in html


# ---------------------------------------------------------------------------
# M3  Receipt format
# ---------------------------------------------------------------------------


async def test_receipt_format_is_a_tenant_setting(
    client: AsyncClient, admin_token: str, config: RestaurantConfig
):
    headers = _auth(admin_token)

    before = await client.get("/api/v1/config/restaurant", headers=headers)
    assert before.status_code == 200
    assert before.json()["receipt_format"] == "thermal"
    assert before.json()["takeaway_label"] is None

    saved = await client.patch(
        "/api/v1/config/restaurant",
        json={"receipt_format": "a4", "takeaway_label": "  Pick up "},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["receipt_format"] == "a4"
    assert saved.json()["takeaway_label"] == "Pick up"

    # Anything but the two formats is refused at the edge.
    bad = await client.patch(
        "/api/v1/config/restaurant", json={"receipt_format": "letter"}, headers=headers
    )
    assert bad.status_code == 422

    # Empty label clears it back to the default.
    cleared = await client.patch(
        "/api/v1/config/restaurant", json={"takeaway_label": ""}, headers=headers
    )
    assert cleared.status_code == 200
    assert cleared.json()["takeaway_label"] is None
    assert cleared.json()["receipt_format"] == "a4"


# ---------------------------------------------------------------------------
# M4 + M5  Channels on the till, charges on the order
# ---------------------------------------------------------------------------


async def test_sales_channel_pos_visibility(
    client: AsyncClient, admin_token: str, config: RestaurantConfig
):
    headers = _auth(admin_token)
    created = await client.post(
        "/api/v1/locations/channels",
        json={"name": "Deliveroo", "code": "deliveroo", "commission_bps": 3000},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["pos_visible"] is True

    hidden = await client.patch(
        f"/api/v1/locations/channels/{created.json()['id']}",
        json={"pos_visible": False},
        headers=headers,
    )
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["pos_visible"] is False

    listed = await client.get("/api/v1/locations/channels/all", headers=headers)
    assert listed.status_code == 200
    assert [c["pos_visible"] for c in listed.json() if c["code"] == "deliveroo"] == [False]


async def test_charges_ride_outside_the_tax_and_survive_a_retotal(
    client: AsyncClient,
    admin_token: str,
    config: RestaurantConfig,
    croissant: MenuItem,
):
    headers = _auth(admin_token)

    channel = await client.post(
        "/api/v1/locations/channels",
        json={"name": "Careem Now", "code": "careem", "commission_bps": 1500},
        headers=headers,
    )
    assert channel.status_code == 201, channel.text

    # Three croissants at AED 9.00 (VAT inside), plus AED 10.00 delivery and
    # AED 2.50 service charge added at the till.
    created = await client.post(
        "/api/v1/orders",
        json={
            "order_type": "takeaway",
            "items": [
                {
                    "menu_item_id": str(croissant.id),
                    "name": "Croissant",
                    "quantity": 3,
                    "unit_price": 900,
                    "modifiers": [],
                }
            ],
            "sales_channel_id": channel.json()["id"],
            "delivery_fee": 1000,
            "service_fee": 250,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    order = created.json()
    assert order["subtotal"] == 2700
    # 5% inside 27.00: net 25.71, VAT 1.29. The fees carry no VAT.
    assert order["tax_amount"] == 129
    assert order["delivery_fee"] == 1000
    assert order["service_fee"] == 250
    assert order["total"] == 2700 + 1000 + 250
    assert order["sales_channel_name"] == "Careem Now"

    # The list view names the channel too, so the till can show "Careem Now"
    # instead of "Takeaway" on the order card.
    listed = await client.get("/api/v1/orders", headers=headers)
    assert listed.status_code == 200
    row = next(o for o in listed.json()["items"] if o["id"] == order["id"])
    assert row["sales_channel_name"] == "Careem Now"
    assert row["total"] == 3950

    # The payment preview keeps the fees on both method totals.
    preview = await client.get(
        f"/api/v1/orders/{order['id']}/payment-preview", headers=headers
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["cash_total"] == 3950
    assert preview.json()["card_total"] == 3950
    assert preview.json()["delivery_fee"] == 1000

    # The receipt shows the fee lines, so the visible lines add up to the total.
    receipt = await client.get(f"/api/v1/receipts/orders/{order['id']}", headers=headers)
    assert receipt.status_code == 200, receipt.text
    r = receipt.json()
    assert r["delivery_fee"] == 1000
    assert r["service_fee"] == 250
    assert r["receipt_format"] == "thermal"
    assert r["subtotal"] + r["delivery_fee"] + r["service_fee"] - r["discount_amount"] == r["total"]

    # Paying in cash re-totals the order under the cash rate. The fees must
    # still be there afterwards, and the amount due is the full 39.50.
    paid = await client.post(
        "/api/v1/payments",
        json={"order_id": order["id"], "method_code": "cash", "amount": 3950,
              "tendered_amount": 4000},
        headers=headers,
    )
    assert paid.status_code in (200, 201), paid.text
    assert paid.json()["order_total"] == 3950
    assert paid.json()["payment_status"] == "paid"


async def test_orders_without_charges_are_byte_identical(
    client: AsyncClient, admin_token: str, config: RestaurantConfig, croissant: MenuItem
):
    """Every existing client sends no fee fields. Nothing changes for them."""
    headers = _auth(admin_token)
    created = await client.post(
        "/api/v1/orders",
        json={
            "order_type": "takeaway",
            "items": [
                {"menu_item_id": str(croissant.id), "name": "Croissant",
                 "quantity": 1, "unit_price": 900, "modifiers": []}
            ],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["total"] == 900
    assert body["delivery_fee"] == 0
    assert body["service_fee"] == 0
    assert body["sales_channel_name"] is None


async def test_negative_charge_is_refused(
    client: AsyncClient, admin_token: str, config: RestaurantConfig, croissant: MenuItem
):
    created = await client.post(
        "/api/v1/orders",
        json={
            "order_type": "takeaway",
            "items": [
                {"menu_item_id": str(croissant.id), "name": "Croissant",
                 "quantity": 1, "unit_price": 900, "modifiers": []}
            ],
            "delivery_fee": -100,
        },
        headers=_auth(admin_token),
    )
    assert created.status_code == 422


# ---------------------------------------------------------------------------
# M6  Customers with a TRN, listable from the back office
# ---------------------------------------------------------------------------


async def test_customer_company_and_trn_and_back_office_list(
    client: AsyncClient, admin_token: str, config: RestaurantConfig
):
    headers = _auth(admin_token)

    walkin = await client.post(
        "/api/v1/customers",
        json={"name": "Walk-in Customer", "phone": "0000000000"},
        headers=headers,
    )
    assert walkin.status_code == 201
    person = await client.post(
        "/api/v1/customers",
        json={"name": "Aisha", "phone": "0501234567"},
        headers=headers,
    )
    assert person.status_code == 201
    company = await client.post(
        "/api/v1/customers",
        json={
            "name": "Martin Zubeldia",
            "phone": "0559876543",
            "company_name": "FZ LLC",
            "trn": "100123456700003",
            "email": "martin@fz.test",
        },
        headers=headers,
    )
    assert company.status_code == 201, company.text
    assert company.json()["company_name"] == "FZ LLC"
    assert company.json()["trn"] == "100123456700003"

    # The list never shows the walk-in placeholder.
    listed = await client.get("/api/v1/customers", headers=headers)
    assert listed.status_code == 200, listed.text
    names = [c["name"] for c in listed.json()["items"]]
    assert names == ["Aisha", "Martin Zubeldia"]
    assert listed.json()["total"] == 2

    # Search matches company name, TRN and phone digits, case-insensitively.
    for needle in ("fz llc", "1001234567", "055 987"):
        found = await client.get("/api/v1/customers", params={"q": needle}, headers=headers)
        assert found.status_code == 200
        assert [c["name"] for c in found.json()["items"]] == ["Martin Zubeldia"], needle

    # The TRN can be corrected later.
    fixed = await client.patch(
        f"/api/v1/customers/{company.json()['id']}",
        json={"trn": "100123456700004"},
        headers=headers,
    )
    assert fixed.status_code == 200
    assert fixed.json()["trn"] == "100123456700004"


async def test_customer_list_is_tenant_scoped(
    client: AsyncClient, admin_token: str, other_tenant_token: str, config: RestaurantConfig
):
    mine = await client.post(
        "/api/v1/customers",
        json={"name": "Mine", "phone": "0501111111"},
        headers=_auth(admin_token),
    )
    assert mine.status_code == 201
    theirs = await client.get("/api/v1/customers", headers=_auth(other_tenant_token))
    assert theirs.status_code == 200
    assert theirs.json()["items"] == []


async def test_tax_invoice_names_the_company_and_its_trn(
    client: AsyncClient, admin_token: str, config: RestaurantConfig, croissant: MenuItem
):
    """A sale to a business customer is invoiced to the company, with its TRN."""
    headers = _auth(admin_token)
    company = await client.post(
        "/api/v1/customers",
        json={"name": "Martin Zubeldia", "phone": "0559876543",
              "company_name": "FZ LLC", "trn": "100123456700003",
              "default_address": "Al Quoz Industrial 3", "city": "Dubai"},
        headers=headers,
    )
    assert company.status_code == 201
    created = await client.post(
        "/api/v1/orders",
        json={
            "order_type": "call_center",
            "customer_name": "Martin Zubeldia",
            "customer_phone": "0559876543",
            "items": [
                {"menu_item_id": str(croissant.id), "name": "Croissant",
                 "quantity": 2, "unit_price": 900, "modifiers": []}
            ],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    invoice = await client.get(
        f"/api/v1/receipts/orders/{created.json()['id']}/tax-invoice", headers=headers
    )
    assert invoice.status_code == 200, invoice.text
    recipient = invoice.json()["recipient"]
    assert recipient["name"] == "FZ LLC"
    assert recipient["trn"] == "100123456700003"
    assert recipient["address_line1"] == "Al Quoz Industrial 3"
    assert recipient["city"] == "Dubai"


async def test_unknown_customer_field_is_harmless(
    client: AsyncClient, admin_token: str, config: RestaurantConfig
):
    """Sanity: the id in the URL still has to belong to this tenant."""
    missing = await client.patch(
        f"/api/v1/customers/{uuid.uuid4()}", json={"trn": "x"}, headers=_auth(admin_token)
    )
    assert missing.status_code == 404
