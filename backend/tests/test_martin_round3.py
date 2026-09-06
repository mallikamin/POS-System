"""Martin's round-3 feedback (FZ LLC, 2026-09-06), proven through the routes.

Four build items:

    M9  "There is no production menu where I can produce subrecipes (example,
         producing tomato sauce or dough or anything) and then this will be
         added as stock (+ sauce) and at same time the ingredient reduced
         (-tomato raw item)"

    M10 "There is no expenses menu to attach the invoices of my expenses (not
         the ones from suppliers which are already in the receiving of
         ingredients, but other expenses such as rent, salaries etc...)"

    M11 "Ingredients. Theres a fixed set of Categories. Don't see a menu or
         drop-down menu where I can add a category"

    M13 "Need to have option here to either send to kitchen / then ready / then
         dispatched as it is now. And at that time is deducted from inventory
         OR directly print and deducted from stock"

Every test drives HTTP rather than the service layer, for the reason written at
the top of `test_martin_round1.py`: a green service test says nothing about the
route in front of it, and the two bugs UAT found on 2026-09-01 both lived in
the route.

His own example is the spine of the M9 tests -- tomato sauce made from tomatoes
-- so a failure reads as "the sauce case broke", not as an abstraction.

WARNING: these run on SQLite. It does not enforce `Numeric` precision or CHECK
constraints the way Postgres does, so a green run here does NOT prove the
migration's check constraints or the numeric widths landed. That is checked
against a real Postgres after the migration runs, the way
`recipe-module-tz-bug-and-test-gap` in memory says.
"""

from __future__ import annotations

import io

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant

pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def config(db: AsyncSession, tenant: Tenant) -> RestaurantConfig:
    """A UAE-shaped tenant: AED, 5% VAT inside the shelf price, order-first."""
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


async def _site(client: AsyncClient, headers) -> str:
    created = await client.post(
        "/api/v1/locations",
        json={
            "name": "Production Kitchen",
            "code": "PROD",
            "location_type": "production",
            "is_default": True,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def _ingredient(client: AsyncClient, headers, **kwargs) -> dict:
    payload = {
        "name": "Tomatoes",
        "category": "Vegetable",
        "unit": "g",
        "cost_per_unit": 0.02,
        **kwargs,
    }
    created = await client.post(
        "/api/v1/inventory/ingredients", json=payload, headers=headers
    )
    assert created.status_code == 201, created.text
    return created.json()


# ===========================================================================
# M11 -- ingredient categories
# ===========================================================================


async def test_the_category_list_starts_from_what_the_data_already_contains(
    client: AsyncClient, admin_token: str, config
) -> None:
    """Martin's real complaint: no list anywhere, so the set looked closed.

    Creating an ingredient under a category nobody created must put that
    category on the list, or the dropdown opens empty on a tenant with forty
    ingredients.
    """
    headers = _auth(admin_token)
    await _ingredient(client, headers, name="Tomatoes", category="Vegetable")
    await _ingredient(client, headers, name="Flour", category="Dry Goods")

    listed = await client.get("/api/v1/inventory/ingredient-categories", headers=headers)
    assert listed.status_code == 200, listed.text
    names = {row["name"]: row["ingredient_count"] for row in listed.json()}
    assert names["Vegetable"] == 1
    assert names["Dry Goods"] == 1


async def test_a_category_can_be_added_before_anything_uses_it(
    client: AsyncClient, admin_token: str, config
) -> None:
    """The literal ask: a place to add a category."""
    headers = _auth(admin_token)
    created = await client.post(
        "/api/v1/inventory/ingredient-categories",
        json={"name": "Packaging"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["name"] == "Packaging"
    assert created.json()["ingredient_count"] == 0

    listed = await client.get("/api/v1/inventory/ingredient-categories", headers=headers)
    assert "Packaging" in {row["name"] for row in listed.json()}


async def test_case_differences_do_not_fork_a_category(
    client: AsyncClient, admin_token: str, config
) -> None:
    """🔴 The whole point of the table.

    A free-text box across forty ingredients produces "Dairy" and "dairy" as two
    categories. Saving under the second must file under the first, and the
    STORED spelling wins.
    """
    headers = _auth(admin_token)
    await _ingredient(client, headers, name="Milk", category="Dairy")
    cheese = await _ingredient(client, headers, name="Cheese", category="dairy")

    assert cheese["category"] == "Dairy"

    listed = await client.get("/api/v1/inventory/ingredient-categories", headers=headers)
    rows = [row for row in listed.json() if row["name"].lower() == "dairy"]
    assert len(rows) == 1, rows
    assert rows[0]["name"] == "Dairy"
    assert rows[0]["ingredient_count"] == 2


async def test_renaming_a_category_moves_the_ingredients_with_it(
    client: AsyncClient, admin_token: str, config
) -> None:
    """🔴 Both halves or neither.

    Renaming only the master row would leave every ingredient filed under a
    category that no longer exists -- exactly the drift the table was added to
    prevent.
    """
    headers = _auth(admin_token)
    ing = await _ingredient(client, headers, name="Tomatoes", category="Vegtable")

    listed = await client.get("/api/v1/inventory/ingredient-categories", headers=headers)
    category_id = next(
        row["id"] for row in listed.json() if row["name"] == "Vegtable"
    )

    renamed = await client.patch(
        f"/api/v1/inventory/ingredient-categories/{category_id}",
        json={"name": "Vegetables"},
        headers=headers,
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["ingredient_count"] == 1  # one ingredient moved

    after = await client.get(
        f"/api/v1/inventory/ingredients/{ing['id']}", headers=headers
    )
    assert after.json()["category"] == "Vegetables"


async def test_a_category_in_use_cannot_be_deleted(
    client: AsyncClient, admin_token: str, config
) -> None:
    """Refusing beats silently moving 12 ingredients to General."""
    headers = _auth(admin_token)
    await _ingredient(client, headers, name="Tomatoes", category="Vegetable")

    listed = await client.get("/api/v1/inventory/ingredient-categories", headers=headers)
    category_id = next(
        row["id"] for row in listed.json() if row["name"] == "Vegetable"
    )

    refused = await client.delete(
        f"/api/v1/inventory/ingredient-categories/{category_id}", headers=headers
    )
    assert refused.status_code == 400
    assert "1 ingredient" in refused.json()["detail"]


async def test_an_unused_category_can_be_deleted(
    client: AsyncClient, admin_token: str, config
) -> None:
    headers = _auth(admin_token)
    created = await client.post(
        "/api/v1/inventory/ingredient-categories",
        json={"name": "Packaging"},
        headers=headers,
    )
    gone = await client.delete(
        f"/api/v1/inventory/ingredient-categories/{created.json()['id']}",
        headers=headers,
    )
    assert gone.status_code == 204

    listed = await client.get("/api/v1/inventory/ingredient-categories", headers=headers)
    assert "Packaging" not in {row["name"] for row in listed.json()}


# ===========================================================================
# M9 -- production
# ===========================================================================


async def _sauce_recipe(client: AsyncClient, headers) -> tuple[str, str, str]:
    """Martin's example: tomato sauce made from tomatoes.

    Returns (recipe_id, tomatoes_id, sauce_id).
    """
    tomatoes = await _ingredient(
        client, headers, name="Tomatoes", category="Vegetable", unit="g",
        cost_per_unit=0.02,
    )
    sauce = await _ingredient(
        client,
        headers,
        name="Tomato Sauce",
        category="Prepared",
        unit="g",
        is_produced=True,
    )
    recipe = await client.post(
        "/api/v1/inventory/recipes",
        json={
            "produces_ingredient_id": sauce["id"],
            "yield_servings": 800,
            "recipe_items": [
                {"ingredient_id": tomatoes["id"], "quantity": 1000, "unit": "g"}
            ],
        },
        headers=headers,
    )
    assert recipe.status_code == 201, recipe.text
    return recipe.json()["id"], tomatoes["id"], sauce["id"]


async def test_the_preview_says_what_goes_in_and_what_comes_out(
    client: AsyncClient, admin_token: str, config
) -> None:
    """Martin thinks "make 1600 g of sauce", not "run the recipe twice".

    The preview is what turns the batch count into something he can check
    before he presses the button.
    """
    headers = _auth(admin_token)
    site = await _site(client, headers)
    recipe_id, tomatoes_id, sauce_id = await _sauce_recipe(client, headers)

    preview = await client.post(
        "/api/v1/locations/production/preview",
        json={"recipe_id": recipe_id, "batches": 2, "location_id": site},
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()

    assert body["produced_ingredient_name"] == "Tomato Sauce"
    assert body["produced_quantity"] == 1600  # 800 per batch, twice
    assert len(body["consumes"]) == 1
    line = body["consumes"][0]
    assert line["ingredient_name"] == "Tomatoes"
    assert line["quantity"] == 2000
    assert line["available"] == 0
    assert line["shortfall"] == 2000
    assert body["has_shortfall"] is True


async def test_the_preview_moves_no_stock(
    client: AsyncClient, admin_token: str, config, db: AsyncSession
) -> None:
    """🔴 A preview that writes is not a preview.

    Checked against the movement log rather than a balance, because a balance
    can be right while an unexplained row sits beside it.
    """
    from app.models.inventory import InventoryTransaction

    headers = _auth(admin_token)
    site = await _site(client, headers)
    recipe_id, _, _ = await _sauce_recipe(client, headers)

    await client.post(
        "/api/v1/locations/production/preview",
        json={"recipe_id": recipe_id, "batches": 5, "location_id": site},
        headers=headers,
    )

    rows = (await db.execute(select(InventoryTransaction))).scalars().all()
    assert rows == []


async def test_running_production_adds_the_sauce_and_takes_the_tomatoes(
    client: AsyncClient, admin_token: str, config
) -> None:
    """Martin's sentence, end to end: "+ sauce" and "- tomato raw item"."""
    headers = _auth(admin_token)
    site = await _site(client, headers)
    recipe_id, tomatoes_id, sauce_id = await _sauce_recipe(client, headers)

    # Put 5 kg of tomatoes on the shelf first, so the deduction is visible as a
    # fall from a real number rather than as a negative balance.
    stocked = await client.post(
        "/api/v1/locations/stock/adjust",
        json={
            "location_id": site,
            "ingredient_id": tomatoes_id,
            "quantity_delta": 5000,
            "reason": "Opening stock",
        },
        headers=headers,
    )
    assert stocked.status_code == 200, stocked.text

    run = await client.post(
        "/api/v1/locations/production/run",
        json={"recipe_id": recipe_id, "batches": 2, "location_id": site},
        headers=headers,
    )
    assert run.status_code == 200, run.text
    assert run.json()["produced_quantity"] == 1600

    rows = await client.get(
        "/api/v1/locations/stock/position",
        params={"location_id": site},
        headers=headers,
    )
    assert rows.status_code == 200, rows.text
    by_name = {row["ingredient_name"]: row["quantity"] for row in rows.json()}
    assert by_name["Tomatoes"] == 3000  # 5000 in, 2000 eaten
    assert by_name["Tomato Sauce"] == 1600


async def test_the_run_shows_up_in_the_history_with_what_it_ate(
    client: AsyncClient, admin_token: str, config
) -> None:
    """M9's second gap: a run left two movements and nothing listed them.

    "What did we make yesterday" had no answer at all before this.
    """
    headers = _auth(admin_token)
    site = await _site(client, headers)
    recipe_id, _, _ = await _sauce_recipe(client, headers)

    await client.post(
        "/api/v1/locations/production/run",
        json={"recipe_id": recipe_id, "batches": 1, "location_id": site},
        headers=headers,
    )

    history = await client.get("/api/v1/locations/production/runs", headers=headers)
    assert history.status_code == 200, history.text
    runs = history.json()
    assert len(runs) == 1

    run = runs[0]
    assert run["produced_ingredient_name"] == "Tomato Sauce"
    assert run["quantity"] == 800
    assert run["location_name"] == "Production Kitchen"
    assert len(run["consumed"]) == 1
    # Stored negative because it left the shelf; shown positive, because
    # "consumed -1000 g" reads as a return.
    assert run["consumed"][0]["ingredient_name"] == "Tomatoes"
    assert run["consumed"][0]["quantity"] == 1000


async def test_a_menu_item_recipe_cannot_be_produced_into_stock(
    client: AsyncClient, admin_token: str, config
) -> None:
    """A burger is made to order and sold, not produced onto a shelf."""
    headers = _auth(admin_token)
    site = await _site(client, headers)

    category = await client.post(
        "/api/v1/menu/categories",
        json={"name": "Mains", "display_order": 1},
        headers=headers,
    )
    item = await client.post(
        "/api/v1/menu/items",
        json={
            "category_id": category.json()["id"],
            "name": "Burger",
            "price": 2500,
        },
        headers=headers,
    )
    tomatoes = await _ingredient(client, headers, name="Tomatoes")
    recipe = await client.post(
        "/api/v1/inventory/recipes",
        json={
            "menu_item_id": item.json()["id"],
            "yield_servings": 1,
            "recipe_items": [
                {"ingredient_id": tomatoes["id"], "quantity": 50, "unit": "g"}
            ],
        },
        headers=headers,
    )

    refused = await client.post(
        "/api/v1/locations/production/preview",
        json={"recipe_id": recipe.json()["id"], "batches": 1, "location_id": site},
        headers=headers,
    )
    assert refused.status_code == 400


# ===========================================================================
# M10 -- expenses
# ===========================================================================


async def test_a_tenant_gets_a_starter_set_of_categories(
    client: AsyncClient, admin_token: str, config
) -> None:
    headers = _auth(admin_token)
    listed = await client.get("/api/v1/expenses/categories", headers=headers)
    assert listed.status_code == 200, listed.text
    names = {row["name"] for row in listed.json()}
    assert "Rent" in names
    assert "Salaries & Wages" in names


async def test_the_starter_set_is_not_inserted_twice(
    client: AsyncClient, admin_token: str, config
) -> None:
    """🔴 The seed is lazy, so it runs on every page load.

    Without the commit in the route it re-inserts and discards ten rows each
    time; without the "only what is missing" guard it would duplicate them.
    """
    headers = _auth(admin_token)
    first = await client.get("/api/v1/expenses/categories", headers=headers)
    second = await client.get("/api/v1/expenses/categories", headers=headers)
    assert len(first.json()) == len(second.json())
    names = [row["name"] for row in second.json()]
    assert len(names) == len(set(names))


async def test_rent_is_recorded_with_its_vat_carved_out(
    client: AsyncClient, admin_token: str, config
) -> None:
    """`amount_minor` is the whole invoice; `tax_minor` is the VAT inside it."""
    headers = _auth(admin_token)
    categories = await client.get("/api/v1/expenses/categories", headers=headers)
    rent = next(row for row in categories.json() if row["name"] == "Rent")

    created = await client.post(
        "/api/v1/expenses",
        json={
            "expense_date": "2026-09-01",
            "payee": "Al Barsha Properties",
            "category_id": rent["id"],
            "amount_minor": 10500,
            "tax_minor": 500,
            "reference_number": "INV-2026-09",
            "status": "unpaid",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["amount_minor"] == 10500
    assert body["tax_minor"] == 500
    assert body["net_minor"] == 10000
    assert body["category_name"] == "Rent"
    assert body["recorded_by_name"] is not None


async def test_vat_larger_than_the_invoice_is_refused(
    client: AsyncClient, admin_token: str, config
) -> None:
    """The commonest data-entry slip: net in the total box, gross in the tax."""
    headers = _auth(admin_token)
    refused = await client.post(
        "/api/v1/expenses",
        json={
            "expense_date": "2026-09-01",
            "payee": "Landlord",
            "amount_minor": 100,
            "tax_minor": 500,
        },
        headers=headers,
    )
    assert refused.status_code == 400
    assert "VAT cannot be more" in refused.json()["detail"]


async def test_a_patch_that_sends_only_the_tax_is_checked_against_the_stored_total(
    client: AsyncClient, admin_token: str, config
) -> None:
    """🔴 Validate the state the row will be IN, not the patch alone.

    Checking the patch on its own would let a 500 VAT onto a 100 invoice, and
    the CHECK constraint would then fail as a 500 rather than a 400.
    """
    headers = _auth(admin_token)
    created = await client.post(
        "/api/v1/expenses",
        json={
            "expense_date": "2026-09-01",
            "payee": "Landlord",
            "amount_minor": 10000,
            "tax_minor": 0,
        },
        headers=headers,
    )
    refused = await client.patch(
        f"/api/v1/expenses/{created.json()['id']}",
        json={"tax_minor": 50000},
        headers=headers,
    )
    assert refused.status_code == 400


async def test_marking_an_expense_paid_dates_it(
    client: AsyncClient, admin_token: str, config
) -> None:
    """And marking it back to unpaid clears the date, rather than lying."""
    headers = _auth(admin_token)
    created = await client.post(
        "/api/v1/expenses",
        json={
            "expense_date": "2026-09-01",
            "payee": "DEWA",
            "amount_minor": 42000,
            "status": "unpaid",
        },
        headers=headers,
    )
    expense_id = created.json()["id"]

    paid = await client.patch(
        f"/api/v1/expenses/{expense_id}", json={"status": "paid"}, headers=headers
    )
    assert paid.json()["paid_on"] == "2026-09-01"

    back = await client.patch(
        f"/api/v1/expenses/{expense_id}", json={"status": "unpaid"}, headers=headers
    )
    assert back.json()["paid_on"] is None


async def test_the_summary_excludes_drafts(
    client: AsyncClient, admin_token: str, config
) -> None:
    """🔴 A half-entered invoice is not money owed.

    Letting it into the total would make the screen disagree with the accounts
    for a reason nobody could see.
    """
    headers = _auth(admin_token)
    for status_value, amount in (("paid", 10000), ("unpaid", 5000), ("draft", 99900)):
        await client.post(
            "/api/v1/expenses",
            json={
                "expense_date": "2026-09-01",
                "payee": "Someone",
                "amount_minor": amount,
                "status": status_value,
            },
            headers=headers,
        )

    summary = await client.get("/api/v1/expenses/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["total_minor"] == 15000
    assert body["unpaid_minor"] == 5000
    assert body["expense_count"] == 2


async def test_an_invoice_pdf_can_be_attached_and_read_back(
    client: AsyncClient, admin_token: str, config
) -> None:
    """Martin's literal ask: "attach the invoices of my expenses"."""
    headers = _auth(admin_token)
    created = await client.post(
        "/api/v1/expenses",
        json={
            "expense_date": "2026-09-01",
            "payee": "Al Barsha Properties",
            "amount_minor": 10500,
        },
        headers=headers,
    )
    expense_id = created.json()["id"]

    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n"
    uploaded = await client.post(
        f"/api/v1/expenses/{expense_id}/attachments",
        files={"file": ("september-rent.pdf", io.BytesIO(pdf), "application/pdf")},
        headers=headers,
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["content_type"] == "application/pdf"

    fetched = await client.get(uploaded.json()["url"], headers=headers)
    assert fetched.status_code == 200
    assert fetched.content == pdf
    # nosniff, because a PDF is stored byte-for-byte and this origin holds the
    # session.
    assert fetched.headers["x-content-type-options"] == "nosniff"

    detail = await client.get(f"/api/v1/expenses/{expense_id}", headers=headers)
    assert len(detail.json()["attachments"]) == 1


async def test_the_type_is_decided_by_the_content_not_the_filename(
    client: AsyncClient, admin_token: str, config
) -> None:
    """🔴 Both the filename and the browser's Content-Type are caller-supplied."""
    headers = _auth(admin_token)
    created = await client.post(
        "/api/v1/expenses",
        json={"expense_date": "2026-09-01", "payee": "X", "amount_minor": 100},
        headers=headers,
    )
    refused = await client.post(
        f"/api/v1/expenses/{created.json()['id']}/attachments",
        files={
            "file": (
                "invoice.pdf",
                io.BytesIO(b"<html><script>alert(1)</script></html>"),
                "application/pdf",
            )
        },
        headers=headers,
    )
    assert refused.status_code == 400
    assert "PDF or a photo" in refused.json()["detail"]


async def test_an_expense_cannot_be_read_from_another_restaurant(
    client: AsyncClient, admin_token: str, other_tenant_token: str, config
) -> None:
    headers = _auth(admin_token)
    created = await client.post(
        "/api/v1/expenses",
        json={"expense_date": "2026-09-01", "payee": "Landlord", "amount_minor": 100},
        headers=headers,
    )
    stolen = await client.get(
        f"/api/v1/expenses/{created.json()['id']}", headers=_auth(other_tenant_token)
    )
    assert stolen.status_code == 404


# ===========================================================================
# M13 -- send to kitchen, or print and deduct now
# ===========================================================================


async def _sellable_burger(client: AsyncClient, headers) -> tuple[str, str]:
    """A burger with a recipe, so a sale has stock to deduct.

    Returns (menu_item_id, tomatoes_id).
    """
    category = await client.post(
        "/api/v1/menu/categories",
        json={"name": "Mains", "display_order": 1},
        headers=headers,
    )
    item = await client.post(
        "/api/v1/menu/items",
        json={"category_id": category.json()["id"], "name": "Burger", "price": 2000},
        headers=headers,
    )
    tomatoes = await _ingredient(client, headers, name="Tomatoes", unit="g")
    await client.post(
        "/api/v1/inventory/recipes",
        json={
            "menu_item_id": item.json()["id"],
            "yield_servings": 1,
            "recipe_items": [
                {"ingredient_id": tomatoes["id"], "quantity": 50, "unit": "g"}
            ],
        },
        headers=headers,
    )
    return item.json()["id"], tomatoes["id"]


async def test_the_default_is_unchanged_send_to_kitchen(
    client: AsyncClient, admin_token: str, config
) -> None:
    """🔴 Every existing client sends no `fulfilment_mode` at all.

    Their orders must land exactly where they always did: in_kitchen.
    """
    headers = _auth(admin_token)
    await _site(client, headers)
    item_id, _ = await _sellable_burger(client, headers)

    created = await client.post(
        "/api/v1/orders",
        json={
            "order_type": "takeaway",
            "items": [
                {
                    "menu_item_id": item_id,
                    "name": "Burger",
                    "quantity": 1,
                    "unit_price": 2000,
                }
            ],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "in_kitchen"


async def test_a_direct_sale_is_completed_and_deducts_stock_at_once(
    client: AsyncClient, admin_token: str, config
) -> None:
    """Martin's B2B line: "directly print and deducted from stock"."""
    headers = _auth(admin_token)
    site = await _site(client, headers)
    item_id, tomatoes_id = await _sellable_burger(client, headers)

    await client.post(
        "/api/v1/locations/stock/adjust",
        json={
            "location_id": site,
            "ingredient_id": tomatoes_id,
            "quantity_delta": 500,
            "reason": "Opening stock",
        },
        headers=headers,
    )

    created = await client.post(
        "/api/v1/orders",
        json={
            "order_type": "takeaway",
            "fulfilment_mode": "direct",
            "location_id": site,
            "items": [
                {
                    "menu_item_id": item_id,
                    "name": "Burger",
                    "quantity": 2,
                    "unit_price": 2000,
                }
            ],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "completed"

    rows = await client.get(
        "/api/v1/locations/stock/position",
        params={"location_id": site},
        headers=headers,
    )
    assert rows.status_code == 200, rows.text
    by_name = {row["ingredient_name"]: row["quantity"] for row in rows.json()}
    assert by_name["Tomatoes"] == 400  # 500 in, 2 burgers x 50 g out


async def test_a_direct_sale_writes_no_kitchen_ticket(
    client: AsyncClient, admin_token: str, config, db: AsyncSession
) -> None:
    """The point of the mode: a wholesale line never passes a kitchen."""
    from app.models.kitchen import KitchenTicket

    headers = _auth(admin_token)
    site = await _site(client, headers)
    item_id, _ = await _sellable_burger(client, headers)

    await client.post(
        "/api/v1/orders",
        json={
            "order_type": "takeaway",
            "fulfilment_mode": "direct",
            "location_id": site,
            "items": [
                {
                    "menu_item_id": item_id,
                    "name": "Burger",
                    "quantity": 1,
                    "unit_price": 2000,
                }
            ],
        },
        headers=headers,
    )
    tickets = (await db.execute(select(KitchenTicket))).scalars().all()
    assert tickets == []


async def test_a_direct_sale_is_refused_when_payment_comes_first(
    client: AsyncClient, admin_token: str, db: AsyncSession, tenant: Tenant
) -> None:
    """🔴 Refused, not quietly reinterpreted.

    In pay-first mode `payment_service` is what releases an order. Completing it
    here would book the stock against a sale nobody has paid for.
    """
    cfg = RestaurantConfig(
        tenant_id=tenant.id,
        currency="AED",
        payment_flow="pay_first",
        tax_inclusive=True,
        default_tax_rate=500,
    )
    db.add(cfg)
    await db.flush()
    await db.commit()

    headers = _auth(admin_token)
    await _site(client, headers)
    item_id, _ = await _sellable_burger(client, headers)

    refused = await client.post(
        "/api/v1/orders",
        json={
            "order_type": "takeaway",
            "fulfilment_mode": "direct",
            "items": [
                {
                    "menu_item_id": item_id,
                    "name": "Burger",
                    "quantity": 1,
                    "unit_price": 2000,
                }
            ],
        },
        headers=headers,
    )
    assert refused.status_code == 400
    assert "payment" in refused.json()["detail"].lower()
