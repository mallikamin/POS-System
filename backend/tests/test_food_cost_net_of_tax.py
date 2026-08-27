"""Food Cost % is a share of NET revenue, not of the tax-inclusive shelf price.

UAT finding F13, 2026-08-28. The Recipe Builder reported 13.58% for a AED 1.22
serving on a AED 9.00 croissant. That divides by the board price, which for a
tax-inclusive tenant contains 5% VAT collected for the FTA. The business keeps
AED 8.57, so the true figure is 14.27%: the screen understated food cost on
every costed item, and the error scales with the rate (20% for a UK tenant).

The same division sat on the API (`_enrich_recipe`) and on the screen. Both now
divide by `net_of_tax`, derived from `compute_tax`, so there is one owner of the
price/tax relationship and the two sides cannot drift apart (the F22 lesson).

The rate and the convention are the tenant's own `restaurant_configs` row,
editable in Admin > Settings; nothing here hardcodes 5%.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Ingredient
from app.models.menu import Category, MenuItem
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.inventory import RecipeCreate, RecipeItemCreate
from app.services import recipe_service
from app.services.order_service import compute_tax, net_of_tax


# ---------------------------------------------------------------------------
# The arithmetic
# ---------------------------------------------------------------------------


class TestNetOfTax:
    def test_inclusive_backs_the_tax_out(self):
        """AED 9.00 on the board at 5% inclusive is AED 8.57 of revenue."""
        assert net_of_tax(900, 500, prices_include_tax=True) == 857

    def test_exclusive_price_is_already_net(self):
        assert net_of_tax(900, 500, prices_include_tax=False) == 900

    def test_rate_zero_is_identity_under_both_conventions(self):
        """Chick Shack runs rate 0: nothing they see may change."""
        assert net_of_tax(900, 0, True) == 900
        assert net_of_tax(900, 0, False) == 900

    @pytest.mark.parametrize("amount", [1, 99, 100, 900, 2700, 10_000, 999_999])
    @pytest.mark.parametrize("rate_bps", [500, 1600, 2000])
    def test_net_plus_tax_is_the_price(self, amount, rate_bps):
        """The net figure is the same one the tax invoice prints: derived from
        `compute_tax`, not recomputed, so `net + tax == price` exactly."""
        tax, _ = compute_tax(amount, rate_bps, True)
        assert net_of_tax(amount, rate_bps, True) + tax == amount


# ---------------------------------------------------------------------------
# The API: the number the screen reads
# ---------------------------------------------------------------------------


async def _config(db: AsyncSession, tenant: Tenant, *, rate_bps: int, inclusive: bool) -> None:
    db.add(
        RestaurantConfig(
            tenant_id=tenant.id,
            currency="AED",
            timezone="Asia/Dubai",
            payment_flow="order_first",
            tax_inclusive=inclusive,
            default_tax_rate=rate_bps,
        )
    )
    await db.flush()


async def _costed_croissant(db: AsyncSession, tenant: Tenant, admin_user: User) -> uuid.UUID:
    """A AED 9.00 menu item whose recipe costs AED 1.22 a serving (the UAT case)."""
    cat = Category(tenant_id=tenant.id, name="Pastries", display_order=0, is_active=True)
    db.add(cat)
    await db.flush()
    item = MenuItem(
        tenant_id=tenant.id, category_id=cat.id, name="Butter Croissant",
        price=900, is_available=True,
    )
    dough = Ingredient(
        tenant_id=tenant.id, name="Croissant Dough", category="Produced", unit="kg",
        cost_per_unit=Decimal("1019"), is_active=True, is_produced=False,
    )
    db.add_all([item, dough])
    await db.flush()

    recipe = await recipe_service.create_recipe(
        db,
        tenant.id,
        RecipeCreate(
            menu_item_id=item.id,
            yield_servings=Decimal("1"),
            recipe_items=[
                RecipeItemCreate(
                    ingredient_id=dough.id, quantity=Decimal("0.12"), unit="kg",
                    waste_factor=Decimal("0"),
                )
            ],
        ),
        admin_user.id,
    )
    await db.flush()
    assert recipe.cost_per_serving == Decimal("122.28")
    return recipe.id


async def _get_recipe(client: AsyncClient, token: str, recipe_id: uuid.UUID) -> dict:
    r = await client.get(
        f"/api/v1/inventory/recipes/{recipe_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


async def test_inclusive_tenant_food_cost_is_against_net_price(
    db: AsyncSession, tenant: Tenant, admin_user: User, admin_token: str, client: AsyncClient
) -> None:
    """The F13 figure: 122.28 / 857, not 122.28 / 900."""
    await _config(db, tenant, rate_bps=500, inclusive=True)
    recipe_id = await _costed_croissant(db, tenant, admin_user)

    body = await _get_recipe(client, admin_token, recipe_id)

    assert body["menu_item_price"] == 900
    assert body["menu_item_net_price"] == 857
    assert body["food_cost_percentage"] == pytest.approx(122.28 / 857 * 100, abs=0.005)
    assert body["food_cost_percentage"] > 122.28 / 900 * 100, (
        "dividing by the VAT-inclusive price is the bug being fixed"
    )


async def test_exclusive_tenant_is_unchanged(
    db: AsyncSession, tenant: Tenant, admin_user: User, admin_token: str, client: AsyncClient
) -> None:
    await _config(db, tenant, rate_bps=500, inclusive=False)
    recipe_id = await _costed_croissant(db, tenant, admin_user)

    body = await _get_recipe(client, admin_token, recipe_id)

    assert body["menu_item_net_price"] == 900
    assert body["food_cost_percentage"] == pytest.approx(122.28 / 900 * 100, abs=0.005)


async def test_rate_zero_tenant_is_unchanged(
    db: AsyncSession, tenant: Tenant, admin_user: User, admin_token: str, client: AsyncClient
) -> None:
    """Chick Shack: `tax_inclusive` True with `default_tax_rate` 0. Byte-identical
    to the old division."""
    await _config(db, tenant, rate_bps=0, inclusive=True)
    recipe_id = await _costed_croissant(db, tenant, admin_user)

    body = await _get_recipe(client, admin_token, recipe_id)

    assert body["menu_item_net_price"] == 900
    assert body["food_cost_percentage"] == pytest.approx(122.28 / 900 * 100, abs=0.005)


async def test_list_endpoint_uses_the_same_divisor(
    db: AsyncSession, tenant: Tenant, admin_user: User, admin_token: str, client: AsyncClient
) -> None:
    """The list and the detail must agree, or the recipes table and the editor
    would show two food-cost figures for one recipe."""
    await _config(db, tenant, rate_bps=500, inclusive=True)
    recipe_id = await _costed_croissant(db, tenant, admin_user)

    r = await client.get(
        "/api/v1/inventory/recipes",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    rows = [row for row in r.json() if row["id"] == str(recipe_id)]
    assert len(rows) == 1
    detail = await _get_recipe(client, admin_token, recipe_id)
    assert rows[0]["menu_item_net_price"] == detail["menu_item_net_price"] == 857
    assert rows[0]["food_cost_percentage"] == detail["food_cost_percentage"]
