"""Seed the FZ LLC (Martin Zubeldia, UAE) demo tenant.

Why this exists
----------------
FZ LLC is a UAE bakery/cafe lead (`_context/clients/fz-llc-uae/`), delivery
and collection only -- Martin's own words: "I don't have tables, so it's
delivery-only, my restaurant" -- selling via call center and third-party
delivery apps. His stated core workflow is a multi-layer production chain:
"we produce dough, we produce sauces, we produce stuffings, and then we
produce final items." This seed is the first concrete demo of that chain,
built on the new `produces_ingredient_id` sub-recipe capability
(migration `w9x0y1z2a3b4`).

This is a DEMO tenant for a prospective client, not a real restaurant's
data -- prices and quantities are reasonable placeholders, not Martin's
actual menu (we don't have it yet).

No floors/tables are seeded on purpose: no dine-in.

Usage
-----
    docker exec pos-system-backend-1 python -m app.scripts.seed_fz_llc

Idempotent: safe to re-run, skips anything that already exists.
"""

import asyncio
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.tenant import Tenant
from app.models.restaurant_config import RestaurantConfig
from app.models.user import Permission, Role, RolePermission, User
from app.models.menu import (
    Category,
    MenuItem,
    MenuItemModifierGroup,
    Modifier,
    ModifierGroup,
)
from app.models.inventory import Ingredient, Recipe
from app.models.location import Location, SalesChannel, StockTransfer
from app.models.order import Order, OrderItem
from app.schemas.inventory import RecipeCreate, RecipeItemCreate
from app.services import (
    location_service,
    production_service,
    recipe_service,
    stock_service,
    transfer_service,
)
from app.utils.security import hash_password
from app.scripts.seed import ALL_PERMISSIONS, ROLE_DEFINITIONS
from app.scripts.system_admin import ensure_system_admin

TENANT_SLUG = "martin-fz"
TENANT_NAME = "FZ LLC Bakery & Cafe (Demo)"

# ---------------------------------------------------------------------------
# THE TWO LOCATIONS
# ---------------------------------------------------------------------------
# Straight from the 2026-08-26 call, not invented: Martin runs exactly two
# sites, and they behave differently. Location 1 produces and sells B2B on A4
# VAT tax invoices; Location 2 is delivery only and prints thermal tickets.
LOCATIONS = [
    {
        "name": "Production & Wholesale",
        "code": "PROD",
        "location_type": "production",
        "legal_name": "FZ LLC",
        "tax_registration_number": "100123456700003",
        "address_line1": "Warehouse 12, Al Quoz Industrial Area 3",
        "city": "Dubai",
        "country": "United Arab Emirates",
        "phone": "+971 4 000 0000",
        "email": "wholesale@fzllc-demo.com",
        "invoice_format": "a4_tax_invoice",
        "invoice_prefix": "FZW",
        "is_default": True,
        "notes": "Recipes and sub-recipes are produced here. Sells B2B on A4 tax invoices.",
    },
    {
        "name": "Delivery Kitchen",
        "code": "DEL",
        "location_type": "delivery",
        "legal_name": "FZ LLC",
        "tax_registration_number": "100123456700003",
        "address_line1": "Shop 4, Jumeirah Beach Road",
        "city": "Dubai",
        "country": "United Arab Emirates",
        "phone": "+971 4 000 0001",
        "email": "delivery@fzllc-demo.com",
        "invoice_format": "thermal_ticket",
        "invoice_prefix": "FZD",
        "is_default": False,
        "notes": "Delivery only. Call centre, third-party apps and e-commerce. No dine-in.",
    },
]

# ---------------------------------------------------------------------------
# SALES CHANNELS AND WHAT THEY COST
# ---------------------------------------------------------------------------
# Commission in basis points (1500 = 15.00%). These are REPRESENTATIVE demo
# rates for the UAE aggregators, not quoted contract terms -- Martin sets his
# real ones in the admin screen. Uber Eats is deliberately absent: it exited
# the UAE in 2020 and folded into Careem.
SALES_CHANNELS = [
    {"name": "Talabat", "code": "talabat", "commission_bps": 1500, "fixed_fee_minor": 0,
     "notes": "Representative aggregator rate. Confirm the real contract rate."},
    {"name": "Careem Now", "code": "careem", "commission_bps": 1500, "fixed_fee_minor": 0,
     "notes": "Representative aggregator rate. Confirm the real contract rate."},
    {"name": "noon Food", "code": "noon", "commission_bps": 1200, "fixed_fee_minor": 0,
     "notes": "Representative aggregator rate. Confirm the real contract rate."},
    {"name": "Website (card)", "code": "website", "commission_bps": 250, "fixed_fee_minor": 100,
     "notes": "Payment processing only, no aggregator commission."},
    {"name": "WhatsApp / Direct", "code": "direct", "commission_bps": 0, "fixed_fee_minor": 0,
     "notes": "Cash on delivery. No commission at all, which is the point of the report."},
    {"name": "B2B Wholesale", "code": "b2b", "commission_bps": 0, "fixed_fee_minor": 0,
     "notes": "Direct wholesale invoicing from the production site."},
]

# Opening stock, per location code, so both sites are genuinely live rather
# than one being an empty shell in the demo.
OPENING_STOCK = {
    # The production site carries the full raw larder: it is where recipes run.
    "PROD": {
        "Flour": Decimal("120"),
        "Butter": Decimal("40"),
        "Yeast": Decimal("5"),
        "Salt": Decimal("10"),
        "Sugar": Decimal("50"),
        "Milk": Decimal("60"),
        "Mozzarella Cheese": Decimal("25"),
        "Chicken Breast": Decimal("35"),
        "Onion": Decimal("30"),
        "Garlic": Decimal("6"),
        "Olive Oil": Decimal("14"),
        "Espresso Beans": Decimal("12"),
    },
    # The delivery kitchen only finishes and serves, so it holds a short list.
    # Espresso Beans is deliberately seeded BELOW its reorder point so the
    # low-stock alert has something real to show in the demo.
    "DEL": {
        "Milk": Decimal("25"),
        "Espresso Beans": Decimal("1.5"),
        "Mozzarella Cheese": Decimal("6"),
    },
}

ADMIN_USER = {
    "email": "admin@fzllc-demo.com",
    "full_name": "Martin Zubeldia (Demo)",
    "password": "FzDemo2026!",
    "pin": "2608",
    "role_name": "admin",
}

# Malik's own login is universal across every client tenant -- see
# app/scripts/system_admin.py. Not redefined here on purpose.

# ---------------------------------------------------------------------------
# MENU
# ---------------------------------------------------------------------------

CATEGORIES = ["Pastries", "Rolls & Sandwiches", "Beverages"]

# name -> (category, price in fils, description)
MENU_ITEMS: dict[str, tuple[str, int, str]] = {
    "Butter Croissant": ("Pastries", 900, "Classic all-butter croissant"),
    "Chicken & Cheese Croissant": (
        "Pastries",
        1600,
        "Croissant filled with chicken stuffing and cheese sauce",
    ),
    "Chicken Cheese Roll": (
        "Rolls & Sandwiches",
        1800,
        "Rolled dough filled with chicken stuffing and cheese sauce",
    ),
    "Cappuccino": ("Beverages", 1400, "Espresso with steamed milk"),
}

# ---------------------------------------------------------------------------
# ADD-ONS (modifiers). An add-on with a recipe consumes stock and carries cost
# exactly like a menu item does; one without a recipe is just a price change.
# Martin asked for this in UAT (OI-99).
#   group -> [(name, price in fils, [(ingredient, qty, unit, waste%)])]
# ---------------------------------------------------------------------------

ADDON_GROUP = "Extras"

ADDONS = [
    {
        "name": "Extra Cheese Sauce",
        "price": 200,
        "items": [("Cheese Sauce", Decimal("0.03"), "kg", Decimal("0"))],
        "applies_to": ["Chicken & Cheese Croissant", "Chicken Cheese Roll"],
    },
    {
        "name": "Extra Chicken Stuffing",
        "price": 400,
        "items": [("Chicken Stuffing", Decimal("0.04"), "kg", Decimal("0"))],
        "applies_to": ["Chicken & Cheese Croissant", "Chicken Cheese Roll"],
    },
]


# ---------------------------------------------------------------------------
# RAW INGREDIENTS (purchased). cost_per_unit in fils (1 AED = 100 fils).
# ---------------------------------------------------------------------------

RAW_INGREDIENTS = [
    {"name": "Flour", "category": "Bakery", "unit": "kg", "cost_per_unit": 350,
     "current_stock": 80, "reorder_point": 20, "reorder_quantity": 50},
    {"name": "Butter", "category": "Dairy", "unit": "kg", "cost_per_unit": 2800,
     "current_stock": 30, "reorder_point": 8, "reorder_quantity": 20},
    {"name": "Yeast", "category": "Bakery", "unit": "kg", "cost_per_unit": 4500,
     "current_stock": 3, "reorder_point": 1, "reorder_quantity": 3},
    {"name": "Salt", "category": "Pantry", "unit": "kg", "cost_per_unit": 150,
     "current_stock": 10, "reorder_point": 2, "reorder_quantity": 5},
    {"name": "Sugar", "category": "Pantry", "unit": "kg", "cost_per_unit": 400,
     "current_stock": 20, "reorder_point": 5, "reorder_quantity": 15},
    {"name": "Milk", "category": "Dairy", "unit": "L", "cost_per_unit": 550,
     "current_stock": 40, "reorder_point": 10, "reorder_quantity": 30},
    {"name": "Mozzarella Cheese", "category": "Dairy", "unit": "kg", "cost_per_unit": 3200,
     "current_stock": 15, "reorder_point": 4, "reorder_quantity": 10},
    {"name": "Chicken Breast", "category": "Protein", "unit": "kg", "cost_per_unit": 2400,
     "current_stock": 25, "reorder_point": 6, "reorder_quantity": 15},
    {"name": "Onion", "category": "Produce", "unit": "kg", "cost_per_unit": 300,
     "current_stock": 20, "reorder_point": 5, "reorder_quantity": 15},
    {"name": "Garlic", "category": "Produce", "unit": "kg", "cost_per_unit": 900,
     "current_stock": 5, "reorder_point": 1, "reorder_quantity": 3},
    {"name": "Olive Oil", "category": "Pantry", "unit": "L", "cost_per_unit": 1800,
     "current_stock": 10, "reorder_point": 2, "reorder_quantity": 6},
    {"name": "Espresso Beans", "category": "Beverage", "unit": "kg", "cost_per_unit": 6500,
     "current_stock": 8, "reorder_point": 2, "reorder_quantity": 5},
]

# ---------------------------------------------------------------------------
# SUB-RECIPES (produced ingredients). Each entry:
#   ingredient name/unit -> the intermediate this batch produces
#   yield_qty -> how much of that unit one batch makes
#   items -> [(raw ingredient name, quantity, unit, waste_factor_pct)]
# ---------------------------------------------------------------------------

SUB_RECIPES = [
    {
        "produces": "Croissant Dough",
        "unit": "kg",
        "yield_qty": Decimal("5"),
        "prep_time_minutes": 40,
        "cook_time_minutes": 0,
        "instructions": "Laminate butter into flour/yeast/milk dough, "
        "fold and rest overnight.",
        "items": [
            ("Flour", Decimal("2.5"), "kg", Decimal("2")),
            ("Butter", Decimal("1.2"), "kg", Decimal("0")),
            ("Yeast", Decimal("0.05"), "kg", Decimal("0")),
            ("Salt", Decimal("0.04"), "kg", Decimal("0")),
            ("Sugar", Decimal("0.15"), "kg", Decimal("0")),
            ("Milk", Decimal("1.0"), "L", Decimal("0")),
        ],
    },
    {
        "produces": "Chicken Stuffing",
        "unit": "kg",
        "yield_qty": Decimal("3"),
        "prep_time_minutes": 15,
        "cook_time_minutes": 20,
        "instructions": "Saute onion and garlic, add diced chicken, "
        "cook through, cool before filling.",
        "items": [
            ("Chicken Breast", Decimal("2.0"), "kg", Decimal("8")),
            ("Onion", Decimal("0.4"), "kg", Decimal("10")),
            ("Garlic", Decimal("0.08"), "kg", Decimal("5")),
            ("Olive Oil", Decimal("0.15"), "L", Decimal("0")),
            ("Salt", Decimal("0.03"), "kg", Decimal("0")),
        ],
    },
    {
        "produces": "Cheese Sauce",
        "unit": "kg",
        "yield_qty": Decimal("2"),
        "prep_time_minutes": 10,
        "cook_time_minutes": 15,
        "instructions": "Butter + flour roux, whisk in milk, melt in "
        "cheese until smooth.",
        "items": [
            ("Butter", Decimal("0.2"), "kg", Decimal("0")),
            ("Flour", Decimal("0.2"), "kg", Decimal("0")),
            ("Milk", Decimal("1.0"), "L", Decimal("0")),
            ("Mozzarella Cheese", Decimal("0.5"), "kg", Decimal("0")),
        ],
    },
]

# ---------------------------------------------------------------------------
# FINAL RECIPES. Consume raw AND produced ingredients by name.
# ---------------------------------------------------------------------------

FINAL_RECIPES = {
    "Butter Croissant": {
        "yield_servings": Decimal("1"),
        "prep_time_minutes": 5,
        "cook_time_minutes": 18,
        "instructions": "Shape dough, proof, egg wash, bake at 190C.",
        "items": [("Croissant Dough", Decimal("0.12"), "kg", Decimal("0"))],
    },
    "Chicken & Cheese Croissant": {
        "yield_servings": Decimal("1"),
        "prep_time_minutes": 8,
        "cook_time_minutes": 18,
        "instructions": "Fill dough with chicken stuffing and cheese "
        "sauce, shape, proof, bake at 190C.",
        "items": [
            ("Croissant Dough", Decimal("0.15"), "kg", Decimal("0")),
            ("Chicken Stuffing", Decimal("0.08"), "kg", Decimal("0")),
            ("Cheese Sauce", Decimal("0.03"), "kg", Decimal("0")),
        ],
    },
    "Chicken Cheese Roll": {
        "yield_servings": Decimal("1"),
        "prep_time_minutes": 8,
        "cook_time_minutes": 20,
        "instructions": "Roll dough around chicken stuffing and cheese "
        "sauce, bake at 190C.",
        "items": [
            ("Croissant Dough", Decimal("0.15"), "kg", Decimal("0")),
            ("Chicken Stuffing", Decimal("0.10"), "kg", Decimal("0")),
            ("Cheese Sauce", Decimal("0.02"), "kg", Decimal("0")),
        ],
    },
    "Cappuccino": {
        "yield_servings": Decimal("1"),
        "prep_time_minutes": 3,
        "cook_time_minutes": 0,
        "instructions": "Pull espresso shot, steam and pour milk.",
        "items": [
            ("Espresso Beans", Decimal("0.018"), "kg", Decimal("0")),
            ("Milk", Decimal("0.15"), "L", Decimal("0")),
        ],
    },
}


async def get_or_create_tenant(db: AsyncSession) -> Tenant:
    result = await db.execute(select(Tenant).where(Tenant.slug == TENANT_SLUG))
    tenant = result.scalar_one_or_none()
    if tenant is not None:
        print(f"Tenant '{TENANT_SLUG}' already exists (id={tenant.id}).")
        return tenant

    tenant_id = uuid.uuid4()
    tenant = Tenant(id=tenant_id, tenant_id=tenant_id, name=TENANT_NAME, slug=TENANT_SLUG, is_active=True)
    db.add(tenant)
    await db.flush()
    print(f"Created tenant '{TENANT_NAME}' (slug={TENANT_SLUG}, id={tenant.id})")
    return tenant


async def get_or_create_config(db: AsyncSession, tenant: Tenant) -> None:
    result = await db.execute(select(RestaurantConfig).where(RestaurantConfig.tenant_id == tenant.id))
    if result.scalar_one_or_none() is not None:
        print("  Config already exists, skipping.")
        return

    config = RestaurantConfig(
        tenant_id=tenant.id,
        payment_flow="order_first",
        currency="AED",
        timezone="Asia/Dubai",
        tax_inclusive=True,
        default_tax_rate=500,  # UAE VAT 5%
        cash_tax_rate_bps=500,
        card_tax_rate_bps=500,
        receipt_header=TENANT_NAME,
        receipt_footer="Thank you for your order!",
    )
    db.add(config)
    await db.flush()
    print("  Created restaurant config (AED, 5% VAT, no dine-in seeded).")


async def get_or_create_users(db: AsyncSession, tenant: Tenant) -> User:
    # Permission.code is globally unique (see the model docstring), not
    # scoped per tenant -- look it up by code alone and reuse it, don't
    # filter by tenant_id or a second tenant re-seeding the same code
    # collides with the unique constraint.
    perm_map: dict[str, Permission] = {}
    for code, description in ALL_PERMISSIONS:
        result = await db.execute(select(Permission).where(Permission.code == code))
        perm = result.scalar_one_or_none()
        if perm is None:
            perm = Permission(tenant_id=tenant.id, code=code, description=description)
            db.add(perm)
            await db.flush()
        perm_map[code] = perm

    role_map: dict[str, Role] = {}
    for role_name, role_def in ROLE_DEFINITIONS.items():
        result = await db.execute(select(Role).where(Role.name == role_name, Role.tenant_id == tenant.id))
        role = result.scalar_one_or_none()
        if role is None:
            role = Role(tenant_id=tenant.id, name=role_name, description=role_def["description"], is_active=True)
            db.add(role)
            await db.flush()

        existing_perm_ids = {
            rp.permission_id
            for rp in (await db.execute(select(RolePermission).where(RolePermission.role_id == role.id))).scalars().all()
        }
        for perm_code in role_def["permissions"]:
            perm = perm_map[perm_code]
            if perm.id not in existing_perm_ids:
                db.add(RolePermission(tenant_id=tenant.id, role_id=role.id, permission_id=perm.id))
        await db.flush()
        role_map[role_name] = role

    result = await db.execute(
        select(User).where(User.email == ADMIN_USER["email"], User.tenant_id == tenant.id)
    )
    admin = result.scalar_one_or_none()
    if admin is None:
        admin = User(
            tenant_id=tenant.id,
            email=ADMIN_USER["email"],
            full_name=ADMIN_USER["full_name"],
            hashed_password=hash_password(ADMIN_USER["password"]),
            pin_code=hash_password(ADMIN_USER["pin"]),
            role_id=role_map[ADMIN_USER["role_name"]].id,
            is_active=True,
        )
        db.add(admin)
        await db.flush()
        print(f"  Created admin user '{ADMIN_USER['email']}' (PIN {ADMIN_USER['pin']}).")
    else:
        print(f"  Admin user '{ADMIN_USER['email']}' already exists.")

    await ensure_system_admin(db, tenant, role_map["admin"])

    return admin


async def get_or_create_menu(db: AsyncSession, tenant: Tenant) -> None:
    cat_map: dict[str, Category] = {}
    for order, cat_name in enumerate(CATEGORIES):
        result = await db.execute(select(Category).where(Category.name == cat_name, Category.tenant_id == tenant.id))
        cat = result.scalar_one_or_none()
        if cat is None:
            cat = Category(tenant_id=tenant.id, name=cat_name, description=None, display_order=order, is_active=True)
            db.add(cat)
            await db.flush()
        cat_map[cat_name] = cat

    order = 0
    for name, (cat_name, price, description) in MENU_ITEMS.items():
        result = await db.execute(
            select(MenuItem).where(MenuItem.name == name, MenuItem.tenant_id == tenant.id)
        )
        if result.scalar_one_or_none() is not None:
            order += 1
            continue
        db.add(
            MenuItem(
                tenant_id=tenant.id,
                category_id=cat_map[cat_name].id,
                name=name,
                description=description,
                price=price,
                display_order=order,
                is_available=True,
            )
        )
        order += 1
    await db.flush()
    print(f"  Menu: {len(CATEGORIES)} categories, {len(MENU_ITEMS)} items (created or already present).")


async def get_or_create_raw_ingredients(db: AsyncSession, tenant: Tenant) -> dict[str, Ingredient]:
    ing_map: dict[str, Ingredient] = {}
    for idef in RAW_INGREDIENTS:
        result = await db.execute(
            select(Ingredient).where(Ingredient.name == idef["name"], Ingredient.tenant_id == tenant.id)
        )
        ing = result.scalar_one_or_none()
        if ing is None:
            ing = Ingredient(tenant_id=tenant.id, is_produced=False, **idef)
            db.add(ing)
            await db.flush()
        ing_map[idef["name"]] = ing
    print(f"  Raw ingredients: {len(RAW_INGREDIENTS)} (created or already present).")
    return ing_map


async def get_or_create_sub_recipes(
    db: AsyncSession, tenant: Tenant, admin: User, ing_map: dict[str, Ingredient]
) -> None:
    for sdef in SUB_RECIPES:
        result = await db.execute(
            select(Ingredient).where(Ingredient.name == sdef["produces"], Ingredient.tenant_id == tenant.id)
        )
        produced = result.scalar_one_or_none()
        if produced is None:
            produced = Ingredient(
                tenant_id=tenant.id,
                name=sdef["produces"],
                category="Produced",
                unit=sdef["unit"],
                cost_per_unit=0,
                current_stock=0,
                reorder_point=0,
                reorder_quantity=0,
                is_active=True,
                is_produced=True,
            )
            db.add(produced)
            await db.flush()
        ing_map[sdef["produces"]] = produced

        if produced.cost_per_unit > 0:
            print(f"  Sub-recipe for '{sdef['produces']}' already costed, skipping.")
            continue

        recipe_items = [
            RecipeItemCreate(
                ingredient_id=ing_map[raw_name].id, quantity=qty, unit=unit, waste_factor=waste
            )
            for raw_name, qty, unit, waste in sdef["items"]
        ]
        recipe = await recipe_service.create_recipe(
            db,
            tenant.id,
            RecipeCreate(
                produces_ingredient_id=produced.id,
                yield_servings=sdef["yield_qty"],
                prep_time_minutes=sdef["prep_time_minutes"],
                cook_time_minutes=sdef["cook_time_minutes"],
                instructions=sdef["instructions"],
                recipe_items=recipe_items,
            ),
            admin.id,
        )
        print(
            f"  Sub-recipe '{sdef['produces']}': batch cost {recipe.total_ingredient_cost/100:.2f} AED "
            f"-> {recipe.cost_per_serving/100:.2f} AED/{sdef['unit']}"
        )


async def get_or_create_final_recipes(
    db: AsyncSession, tenant: Tenant, admin: User, ing_map: dict[str, Ingredient]
) -> None:
    result = await db.execute(select(MenuItem).where(MenuItem.tenant_id == tenant.id))
    menu_map = {mi.name: mi for mi in result.scalars().all()}

    for item_name, rdef in FINAL_RECIPES.items():
        menu_item = menu_map.get(item_name)
        if menu_item is None:
            print(f"  WARNING: menu item '{item_name}' not found, skipping recipe.")
            continue

        existing = await recipe_service.get_recipe_by_menu_item(db, tenant.id, menu_item.id)
        if existing is not None:
            print(f"  Recipe for '{item_name}' already exists, skipping.")
            continue

        recipe_items = [
            RecipeItemCreate(ingredient_id=ing_map[ing_name].id, quantity=qty, unit=unit, waste_factor=waste)
            for ing_name, qty, unit, waste in rdef["items"]
        ]
        recipe = await recipe_service.create_recipe(
            db,
            tenant.id,
            RecipeCreate(
                menu_item_id=menu_item.id,
                yield_servings=rdef["yield_servings"],
                prep_time_minutes=rdef["prep_time_minutes"],
                cook_time_minutes=rdef["cook_time_minutes"],
                instructions=rdef["instructions"],
                recipe_items=recipe_items,
            ),
            admin.id,
        )
        food_cost_pct = (recipe.cost_per_serving / menu_item.price * 100) if menu_item.price else Decimal(0)
        print(
            f"  Recipe '{item_name}': cost {recipe.cost_per_serving/100:.2f} AED, "
            f"price {menu_item.price/100:.2f} AED, food cost {food_cost_pct:.1f}%"
        )


async def get_or_create_locations(
    db: AsyncSession, tenant: Tenant
) -> dict[str, Location]:
    """The two sites from Martin's call. Keyed by code so callers read clearly."""
    out: dict[str, Location] = {}
    for spec in LOCATIONS:
        existing = (
            await db.execute(
                select(Location).where(
                    Location.tenant_id == tenant.id, Location.code == spec["code"]
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = await location_service.create_location(db, tenant.id, dict(spec))
            print(f"  Location '{spec['name']}' ({spec['code']}) created.")
        else:
            print(f"  Location '{spec['name']}' ({spec['code']}) already present.")
        out[spec["code"]] = existing
    return out


async def get_or_create_channels(
    db: AsyncSession, tenant: Tenant
) -> dict[str, SalesChannel]:
    out: dict[str, SalesChannel] = {}
    for spec in SALES_CHANNELS:
        existing = (
            await db.execute(
                select(SalesChannel).where(
                    SalesChannel.tenant_id == tenant.id,
                    SalesChannel.code == spec["code"],
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = await location_service.create_channel(db, tenant.id, dict(spec))
            print(
                f"  Channel '{spec['name']}' at {spec['commission_bps'] / 100:.2f}% created."
            )
        out[spec["code"]] = existing
    return out


async def seed_opening_stock(
    db: AsyncSession,
    tenant: Tenant,
    locations: dict[str, Location],
    ing_map: dict[str, Ingredient],
    admin: User,
) -> None:
    """Put real quantities at both sites.

    Idempotent by checking for an existing opening-balance movement rather than
    a quantity: re-running must not keep adding stock.
    """
    for code, items in OPENING_STOCK.items():
        location = locations[code]
        for name, quantity in items.items():
            ingredient = ing_map.get(name)
            if ingredient is None:
                print(f"  ! opening stock skipped, no ingredient named '{name}'")
                continue

            row = await stock_service.get_or_create_stock_row(
                db, tenant.id, location.id, ingredient.id
            )
            if Decimal(str(row.quantity)) != Decimal("0"):
                continue  # Already stocked. Do not top up on a re-run.

            await stock_service.move_stock(
                db,
                tenant_id=tenant.id,
                ingredient_id=ingredient.id,
                quantity_delta=quantity,
                transaction_type="purchase",
                location_id=location.id,
                performed_by=admin.id,
                reference_number="OPENING",
                notes="Opening balance",
            )
            # Reorder levels per location, so the low-stock report is meaningful.
            # Round to a whole unit, floor of 1. A reorder point is a number a
            # human would choose; "4.167 L" on screen reads as an unfinished
            # system, not a clever one. Raised in UAT 2026-08-27.
            row.reorder_point = max(
                Decimal("1"), (quantity / Decimal("6")).quantize(Decimal("1"))
            )
            row.reorder_quantity = quantity
        print(f"  Opening stock set at {location.name}.")

    # Espresso Beans at the delivery kitchen is deliberately below its reorder
    # point so the low-stock alert has a genuine row to show.
    beans = ing_map.get("Espresso Beans")
    if beans is not None:
        row = await stock_service.get_or_create_stock_row(
            db, tenant.id, locations["DEL"].id, beans.id
        )
        row.reorder_point = Decimal("4")
        row.reorder_quantity = Decimal("10")
    await db.flush()


async def seed_production_and_transfer(
    db: AsyncSession,
    tenant: Tenant,
    locations: dict[str, Location],
    ing_map: dict[str, Ingredient],
    admin: User,
) -> None:
    """Run one real batch and move some of it to the delivery kitchen.

    This is the part Martin actually asked to see: raw materials converted into
    produced inventory, then moved between his two sites. Doing it through the
    real services means the demo data is produced the same way his would be.
    """
    sub_recipes = (
        await db.execute(
            select(Recipe).where(
                Recipe.tenant_id == tenant.id,
                Recipe.produces_ingredient_id.isnot(None),
            )
        )
    ).scalars().all()

    for recipe in sub_recipes:
        produced = (
            await db.execute(
                select(Ingredient).where(Ingredient.id == recipe.produces_ingredient_id)
            )
        ).scalar_one()
        row = await stock_service.get_or_create_stock_row(
            db, tenant.id, locations["PROD"].id, produced.id
        )
        if Decimal(str(row.quantity)) > 0:
            continue  # Already produced on a previous run.
        result = await production_service.run_production(
            db,
            tenant_id=tenant.id,
            recipe_id=recipe.id,
            batches=Decimal("3"),
            location_id=locations["PROD"].id,
            performed_by=admin.id,
        )
        print(
            f"  Produced {result['produced_quantity']} of {result['recipe_name']} "
            f"at {result['location_name']}."
        )

    existing_transfer = (
        await db.execute(
            select(StockTransfer.id).where(StockTransfer.tenant_id == tenant.id)
        )
    ).first()
    if existing_transfer is not None:
        return

    milk = ing_map.get("Milk")
    cheese = ing_map.get("Mozzarella Cheese")
    lines = [
        {"ingredient_id": ing.id, "quantity": qty}
        for ing, qty in ((milk, Decimal("10")), (cheese, Decimal("4")))
        if ing is not None
    ]
    if not lines:
        return

    transfer = await transfer_service.create_transfer(
        db,
        tenant_id=tenant.id,
        from_location_id=locations["PROD"].id,
        to_location_id=locations["DEL"].id,
        lines=lines,
        created_by=admin.id,
        notes="Daily top-up to the delivery kitchen",
    )
    await transfer_service.send_transfer(
        db, tenant_id=tenant.id, transfer_id=transfer.id, performed_by=admin.id
    )
    await transfer_service.receive_transfer(
        db, tenant_id=tenant.id, transfer_id=transfer.id, performed_by=admin.id
    )
    print(f"  Transfer {transfer.transfer_number} sent and received.")


async def seed_demo_orders(
    db: AsyncSession,
    tenant: Tenant,
    locations: dict[str, Location],
    channels: dict[str, SalesChannel],
    admin: User,
) -> None:
    """A spread of completed sales so the profitability report is not empty.

    The channels are chosen to make the client's own point visible at a glance:
    the same basket earns materially less through a 15% aggregator than it does
    direct, which is exactly what he said off-the-shelf reporting hides.
    """
    existing = (
        await db.execute(
            select(Order.id).where(Order.tenant_id == tenant.id).limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        print("  Demo orders already present, skipped.")
        return

    menu_items = list(
        (
            await db.execute(select(MenuItem).where(MenuItem.tenant_id == tenant.id))
        ).scalars().all()
    )
    if not menu_items:
        return

    # (channel code, location code, [(menu item index, qty), ...])
    basket_plan = [
        ("talabat", "DEL", [(0, 4), (1, 2)]),
        ("talabat", "DEL", [(2, 3)]),
        ("careem", "DEL", [(1, 3), (3, 2)]),
        ("noon", "DEL", [(0, 6)]),
        ("website", "DEL", [(2, 2), (3, 1)]),
        ("direct", "DEL", [(0, 3), (2, 2)]),
        ("direct", "DEL", [(1, 5)]),
        ("b2b", "PROD", [(0, 40)]),
        ("b2b", "PROD", [(1, 25), (2, 20)]),
    ]

    created = 0
    for index, (channel_code, location_code, lines) in enumerate(basket_plan, start=1):
        channel = channels.get(channel_code)
        location = locations[location_code]

        picked = [
            (menu_items[i % len(menu_items)], qty) for i, qty in lines
        ]
        subtotal = sum(item.price * qty for item, qty in picked)

        order = Order(
            tenant_id=tenant.id,
            order_number=f"FZ-{index:04d}",
            order_type="online" if location_code == "DEL" else "takeaway",
            status="completed",
            payment_status="paid",
            subtotal=subtotal,
            tax_amount=0,  # VAT-inclusive pricing, no separate line.
            discount_amount=0,
            total=subtotal,
            created_by=admin.id,
            location_id=location.id,
            sales_channel_id=channel.id if channel else None,
        )
        db.add(order)
        await db.flush()

        for item, qty in picked:
            db.add(
                OrderItem(
                    tenant_id=tenant.id,
                    order_id=order.id,
                    menu_item_id=item.id,
                    name=item.name,
                    quantity=qty,
                    unit_price=item.price,
                    total=item.price * qty,
                )
            )
        await db.flush()

        # Freeze the commission exactly as a real completion would.
        await location_service.snapshot_commission(db, tenant.id, order)
        created += 1

    print(f"  {created} demo orders created across {len(channels)} channels.")


async def get_or_create_addons(
    db: AsyncSession, tenant: Tenant, admin: User, ing_map: dict[str, Ingredient]
) -> None:
    """Create the Extras group, its add-ons, and the recipe behind each one.

    The recipe is the point. Before OI-99 an add-on could be sold but not
    described, so extra cheese was revenue with no cost and no stock movement.
    """
    result = await db.execute(
        select(ModifierGroup).where(
            ModifierGroup.tenant_id == tenant.id, ModifierGroup.name == ADDON_GROUP
        )
    )
    group = result.scalar_one_or_none()
    if group is None:
        group = ModifierGroup(
            tenant_id=tenant.id,
            name=ADDON_GROUP,
            display_order=1,
            required=False,
            min_selections=0,
            max_selections=0,  # 0 = unlimited
        )
        db.add(group)
        await db.flush()
        print(f"  Modifier group '{ADDON_GROUP}' created.")

    menu_map = {
        mi.name: mi
        for mi in (
            await db.execute(select(MenuItem).where(MenuItem.tenant_id == tenant.id))
        ).scalars().all()
    }

    for index, addon in enumerate(ADDONS):
        result = await db.execute(
            select(Modifier).where(
                Modifier.group_id == group.id, Modifier.name == addon["name"]
            )
        )
        modifier = result.scalar_one_or_none()
        if modifier is None:
            modifier = Modifier(
                tenant_id=tenant.id,
                group_id=group.id,
                name=addon["name"],
                price_adjustment=addon["price"],
                display_order=index,
            )
            db.add(modifier)
            await db.flush()

        # Attach the group to the items it belongs on, so it is offered at the
        # till rather than existing only in the admin screens.
        for item_name in addon["applies_to"]:
            menu_item = menu_map.get(item_name)
            if menu_item is None:
                continue
            link = (
                await db.execute(
                    select(MenuItemModifierGroup).where(
                        MenuItemModifierGroup.menu_item_id == menu_item.id,
                        MenuItemModifierGroup.modifier_group_id == group.id,
                    )
                )
            ).scalar_one_or_none()
            if link is None:
                db.add(
                    MenuItemModifierGroup(
                        tenant_id=tenant.id,
                        menu_item_id=menu_item.id,
                        modifier_group_id=group.id,
                    )
                )
                await db.flush()

        existing = (
            await db.execute(
                select(Recipe).where(
                    Recipe.tenant_id == tenant.id,
                    Recipe.modifier_id == modifier.id,
                    Recipe.is_active == True,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            print(f"  Add-on recipe for '{addon['name']}' already exists, skipping.")
            continue

        missing = [n for n, *_ in addon["items"] if n not in ing_map]
        if missing:
            print(f"  WARNING: {missing} not found, skipping '{addon['name']}' recipe.")
            continue

        recipe = await recipe_service.create_recipe(
            db,
            tenant.id,
            RecipeCreate(
                modifier_id=modifier.id,
                yield_servings=Decimal("1"),
                recipe_items=[
                    RecipeItemCreate(
                        ingredient_id=ing_map[name].id,
                        quantity=qty,
                        unit=unit,
                        waste_factor=waste,
                    )
                    for name, qty, unit, waste in addon["items"]
                ],
            ),
            admin.id,
        )
        print(
            f"  Add-on '{addon['name']}': charged {addon['price']/100:.2f} AED, "
            f"costs {recipe.cost_per_serving/100:.2f} AED"
        )


async def seed() -> None:
    async with async_session_factory() as db:
        tenant = await get_or_create_tenant(db)
        await get_or_create_config(db, tenant)
        admin = await get_or_create_users(db, tenant)
        await get_or_create_menu(db, tenant)
        ing_map = await get_or_create_raw_ingredients(db, tenant)
        await get_or_create_sub_recipes(db, tenant, admin, ing_map)
        await get_or_create_final_recipes(db, tenant, admin, ing_map)

        locations = await get_or_create_locations(db, tenant)
        channels = await get_or_create_channels(db, tenant)
        # Re-read EVERY ingredient, not just the raw list: the sub-recipes above
        # created produced ingredients (dough, stuffing, sauce) that the
        # production and transfer steps need to look up by name.
        ing_map = {
            ing.name: ing
            for ing in (
                await db.execute(
                    select(Ingredient).where(Ingredient.tenant_id == tenant.id)
                )
            ).scalars().all()
        }
        # After the ingredient re-read: an add-on recipe consumes produced
        # ingredients (cheese sauce, chicken stuffing), which only exist by now.
        await get_or_create_addons(db, tenant, admin, ing_map)
        await seed_opening_stock(db, tenant, locations, ing_map, admin)
        await seed_production_and_transfer(db, tenant, locations, ing_map, admin)
        await seed_demo_orders(db, tenant, locations, channels, admin)

        await db.commit()
        print(
            f"\nDone. Login: shop='{TENANT_SLUG}', email='{ADMIN_USER['email']}', "
            f"password='{ADMIN_USER['password']}', PIN='{ADMIN_USER['pin']}'."
        )


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
