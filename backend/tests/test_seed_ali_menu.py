"""Ali Fish & Chips menu: the JSON, the seeder, and pricing through the server.

The prices below are typed independently off the March 2025 printed menu
(`_context/clients/ali-fish-chips-uk/refs/2025-03_ali-fish-chips-official-menu-A3.pdf`)
and checked through `_price_basket`, the same function that prices a real
storefront order. If the JSON and the print disagree, this fails.
"""

from __future__ import annotations

import copy

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu import Category, MenuItem, Modifier, ModifierGroup
from app.models.tenant import Tenant
from app.schemas.public_order import PublicOrderCreate
from app.scripts.seed_ali_fish_chips import (
    MenuDataError,
    load_menu,
    seed_menu,
    validate_menu,
    variant_group_name,
)
from app.services.public_order_service import PublicOrderError, _price_basket

MENU = load_menu()


# ---------------------------------------------------------------------------
# The JSON on its own
# ---------------------------------------------------------------------------


def test_every_printed_number_is_present_once_per_item() -> None:
    numbers = {e["number"] for e in MENU["items"] if e["number"] is not None}
    assert numbers == set(range(1, 196))
    # 195 numbered dishes; fresh pizzas 168-175 are split one row per size
    # (+16), plus 9 unnumbered items (4 set meals, 2 boxes, tea time, kids, dip).
    assert len(MENU["items"]) == 220


def test_every_price_is_a_positive_integer_in_pence() -> None:
    for entry in MENU["items"]:
        for var in entry["variants"]:
            assert isinstance(var["price"], int) and not isinstance(var["price"], bool)
            assert var["price"] > 0, entry["name"]
        for group in entry.get("modifierGroups") or []:
            for opt in group["options"]:
                assert isinstance(opt["priceDelta"], int) and opt["priceDelta"] >= 0


def test_required_groups_are_satisfiable() -> None:
    for entry in MENU["items"]:
        for group in entry.get("modifierGroups") or []:
            if group["min"] > 0:
                assert group["min"] >= 1
                assert len(group["options"]) >= group["min"], group["name"]


def test_validator_passes_the_real_file() -> None:
    validate_menu(MENU)


def test_validator_refuses_a_conflicting_shared_group() -> None:
    bad = copy.deepcopy(MENU)
    korma = next(e for e in bad["items"] if e["name"] == "72. Kashmir Korma")
    korma["modifierGroups"][0]["options"][0]["priceDelta"] = 999
    with pytest.raises(MenuDataError, match="defined twice"):
        validate_menu(bad)


def test_validator_refuses_a_zero_price() -> None:
    bad = copy.deepcopy(MENU)
    bad["items"][0]["variants"][0]["price"] = 0
    with pytest.raises(MenuDataError, match="positive integer"):
        validate_menu(bad)


def test_corrected_typos_are_not_copied_from_the_print() -> None:
    text = str(MENU)
    for typo in ["Fred rice", "Plan Burger", "Itailan", "spicy Iamb", "sweetcom",
                 "Mambag", "Cryinder", "Rhana", "Potiancapl", "Rosneth", "Helensbrough"]:
        assert typo not in text, typo


# ---------------------------------------------------------------------------
# Seeded into the test database, priced through the server
# ---------------------------------------------------------------------------


async def _seed(db: AsyncSession, tenant: Tenant) -> dict[str, int]:
    counts = await seed_menu(db, tenant, MENU)
    await db.commit()
    return counts


async def _modifier_id(db, tenant, group_name: str, option: str):
    return (
        await db.execute(
            select(Modifier.id)
            .join(ModifierGroup, Modifier.group_id == ModifierGroup.id)
            .where(
                Modifier.tenant_id == tenant.id,
                ModifierGroup.name == group_name,
                Modifier.name == option,
            )
        )
    ).scalar_one()


async def _price(db, tenant, item_name: str, picks: list[tuple[str, str]], qty: int = 1):
    """Price one line. A pick whose group is None means the item's own size group."""
    item_id = (
        await db.execute(
            select(MenuItem.id).where(
                MenuItem.tenant_id == tenant.id, MenuItem.name == item_name
            )
        )
    ).scalar_one()
    mod_ids = []
    for group, option in picks:
        gname = group if group is not None else variant_group_name(item_name)
        mod_ids.append(await _modifier_id(db, tenant, gname, option))
    order = PublicOrderCreate(
        service_type="collection",
        customer_name="Test",
        customer_phone="07909313456",
        items=[{"menu_item_id": str(item_id), "quantity": qty,
                "modifier_ids": [str(m) for m in mod_ids]}],
    )
    lines, subtotal = await _price_basket(db, tenant.id, order)
    return subtotal


async def test_seed_counts_and_idempotency(db: AsyncSession, tenant: Tenant) -> None:
    first = await _seed(db, tenant)
    assert first["items"] == 220
    assert first["categories"] == 25

    async def _counts():
        out = []
        for model in (Category, MenuItem, ModifierGroup, Modifier):
            out.append((await db.execute(
                select(func.count()).select_from(model).where(model.tenant_id == tenant.id)
            )).scalar_one())
        return tuple(out)

    before = await _counts()
    await _seed(db, tenant)
    assert await _counts() == before


async def test_refuses_a_tenant_with_someone_elses_menu(db: AsyncSession, tenant: Tenant) -> None:
    cat = Category(tenant_id=tenant.id, name="Peri Peri", display_order=1)
    db.add(cat)
    await db.flush()
    db.add(MenuItem(tenant_id=tenant.id, category_id=cat.id, name="Half Chicken", price=999))
    await db.flush()
    with pytest.raises(MenuDataError, match="Wrong tenant"):
        await seed_menu(db, tenant, MENU)


SIZE = None  # the item's own " -- Choice" group
TRAD = "Traditional dish: choose your filling"
KORMA = "Korma: choose your meat"
CHEF = "Chef's special: choose your filling"
SAUCE = "Change the curry sauce (£2.00 extra)"

# (item name, picks, expected pence) -- typed off the PDF, not off the JSON.
PRINT_PRICES = [
    ("1. Fish (Haddock)", [(SIZE, "Single")], 850),
    ("1. Fish (Haddock)", [(SIZE, "Supper")], 1295),
    ("4. Scampi (Whole Tail)", [(SIZE, "Supper")], 1095),
    ("17. Pizza Crunch", [(SIZE, "Supper")], 895),
    ("20. 1/4lb Plain Burger", [(SIZE, "Single")], 495),
    ("25. Yankee Doodle", [(SIZE, "Supper")], 850),
    ("29. Garlic Bread (5 slices)", [], 450),
    ("37. Roll & Chips", [], 390),
    ("44. Garlic Mushrooms", [], 750),
    ("49. Prawn Poori", [], 895),
    ("53. Lamb Tikka", [], 1095),
    ("60. Seekh Kebab", [], 1200),
    ("61. Mixed Tandoori", [(SAUCE, "Korma Sauce")], 1995 + 200),
    ("66. Aloo Saag", [(SIZE, "Side dish")], 650),
    ("70. Saag Paneer", [(SIZE, "Main")], 950),
    ("71. Korma", [(KORMA, "Lamb")], 1095),
    ("71. Korma", [(KORMA, "Mixed Meat")], 995),
    ("76. King Prawn Korma", [], 1595),
    ("85. Chicken Biryani", [], 1050),
    ("87. King Prawn Biryani", [(SAUCE, "Bhoona Sauce")], 1595 + 200),
    ("88. Curry", [(TRAD, "Mixed Veg")], 895),
    ("89. Bhoona", [(TRAD, "Chicken")], 1095),
    ("93. Madras", [(TRAD, "King Prawn")], 1595),
    ("94. Saag", [(TRAD, "Mixed Meat")], 950),
    ("95. Tikka Masala", [(CHEF, "Chicken")], 1195),
    ("110. Jalfrezi", [(CHEF, "King Prawn")], 1595),
    ("118. Murgh Samundri", [(CHEF, "Mix Veg")], 995),
    ("116. Balti", [(CHEF, "Mixed Meat")], 1095),
    ("122. Garlic & Green Chilli Nan", [], 520),
    ("124. Chapati", [], 120),
    ("132. Special Fried Rice", [], 495),
    ("136. Curry Sauce", [], 650),
    ("141. Mango Chutney", [], 190),
    ("147. Tub of Chippy Curry Sauce", [], 290),
    ("149. Donner Kebab", [(SIZE, "Regular pitta")], 950),
    ("152. Lamb Tikka Kebab", [(SIZE, "Large king nan"),
                               ("Kebab extras", "Separate salad"),
                               ("Kebab extras", "Separate sauce")], 1395 + 80 + 100),
    ("155. Salad Kebab", [(SIZE, "Large king nan")], 650),
    ("158. Chips, Kebab Meat & Cheese", [], 995),
    ("163. Mixed (Donner & Chicken Tikka)", [], 1095),
    ("167. Mixed (Donner & Chicken Tikka) Wrap with Chips", [], 1095),
    ('168. Cheese Pizza 10"', [], 795),
    ('168. Cheese Pizza 14"', [], 1195),
    ('171. Pepperoni Pizza 12"', [('Extra toppings (12")', "Mushroom")], 1095 + 250),
    ('175. Tuna Pizza 14"', [('Extra toppings (14")', "Onion"),
                             ('Extra toppings (14")', "Sweetcorn")], 1395 + 700),
    ('172. Chicken Tikka Pizza 10"', [('Extra toppings (10")', "Ham")], 995 + 200),
    ("176. Turkish Style", [(SIZE, '10"')], 1195),
    ("188. Italian Obsession", [(SIZE, '14"')], 1795),
    ("189. Vegetarian Calzone", [(SIZE, "Small")], 1295),
    ("194. Korma Calzone", [(SIZE, "Large"), ("Calzone: choose your meat", "Prawn")], 1395),
    ("Super Grill Box", [], 1595),
    ("Munchy Box", [(SIZE, '12"')], 1495),
    ("Munchy Box", [(SIZE, '14"')], 1895),
    ("Tea Time Special for Two", [("Tea Time curry 1", "Lamb Korma"),
                                  ("Tea Time curry 2", "Lamb Korma")], 1895),
    ("Kids Meal", [("Kids meal: choose one", "Fish Fingers & Chips")], 595),
    ("Dip", [("Choose your dip", "Pakora Sauce")], 100),
]


async def test_printed_prices_through_price_basket(db: AsyncSession, tenant: Tenant) -> None:
    await _seed(db, tenant)
    wrong = []
    for name, picks, expected in PRINT_PRICES:
        got = await _price(db, tenant, name, picks)
        if got != expected:
            wrong.append((name, picks, expected, got))
    assert not wrong, wrong


def _set_meal_picks(n: int, dishes: list[str], meats: list[str]):
    picks = []
    for i in range(1, n + 1):
        picks.append((f"Curry {i}: choose dish", dishes[i - 1]))
        picks.append((f"Curry {i}: choose meat", meats[i - 1]))
    return picks


async def test_set_meal_for_two_allows_the_same_curry_twice(db: AsyncSession, tenant: Tenant) -> None:
    await _seed(db, tenant)
    picks = _set_meal_picks(2, ["95. Tikka Masala", "95. Tikka Masala"],
                            ["Chicken", "Chicken"])
    assert await _price(db, tenant, "Set Meal for Two", picks, qty=2) == 2895 * 2


async def test_set_meal_for_four_prices_with_sides(db: AsyncSession, tenant: Tenant) -> None:
    await _seed(db, tenant)
    picks = _set_meal_picks(4, ["89. Bhoona", "71. Korma", "110. Jalfrezi", "93. Madras"],
                            ["Lamb", "Chicken", "Prawn", "Mixed Vegetable"])
    picks += [(f"Set meal for four: rice or nan {i}", side)
              for i, side in enumerate(["Nan Bread", "Nan Bread", "Fried Rice", "Garlic Nan"], 1)]
    assert len(picks) == 12  # well under the 25-modifier line cap
    assert await _price(db, tenant, "Set Meal for Four", picks) == 4695


async def test_set_meal_for_one_and_three(db: AsyncSession, tenant: Tenant) -> None:
    await _seed(db, tenant)
    one = _set_meal_picks(1, ["88. Curry"], ["Chicken"]) + [
        ("Set meal for one: nan or rice", "Rice")]
    assert await _price(db, tenant, "Set Meal for One", one) == 1795
    three = _set_meal_picks(3, ["88. Curry"] * 3, ["Lamb"] * 3) + [
        ("Set meal for three: nan or rice", "3 Nan Bread")]
    assert await _price(db, tenant, "Set Meal for Three", three) == 3995


async def test_set_meal_missing_a_curry_is_refused(db: AsyncSession, tenant: Tenant) -> None:
    await _seed(db, tenant)
    picks = _set_meal_picks(1, ["95. Tikka Masala"], ["Chicken"])
    with pytest.raises(PublicOrderError, match="Curry 2"):
        await _price(db, tenant, "Set Meal for Two", picks)


async def test_protein_is_required_on_a_traditional_dish(db: AsyncSession, tenant: Tenant) -> None:
    await _seed(db, tenant)
    with pytest.raises(PublicOrderError, match="at least 1"):
        await _price(db, tenant, "89. Bhoona", [])


async def test_two_sizes_at_once_are_refused(db: AsyncSession, tenant: Tenant) -> None:
    await _seed(db, tenant)
    with pytest.raises(PublicOrderError, match="at most 1"):
        await _price(db, tenant, "1. Fish (Haddock)", [(SIZE, "Single"), (SIZE, "Supper")])


async def test_a_10_inch_topping_cannot_go_on_a_14_inch_pizza(db: AsyncSession, tenant: Tenant) -> None:
    await _seed(db, tenant)
    with pytest.raises(PublicOrderError, match="not a valid option"):
        await _price(db, tenant, '168. Cheese Pizza 14"', [('Extra toppings (10")', "Ham")])
