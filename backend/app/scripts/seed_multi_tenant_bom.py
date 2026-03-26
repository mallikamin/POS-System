"""Enhanced seed script for two-tenant POS System with BOM data.

Tenants:
1. YK Online Restaurant (QB Online enabled)
2. YK Desktop Restaurant (QB Desktop + BOM enabled)

BOM data seeded only for YK Desktop tenant.

Run with:
    python -m app.scripts.seed_multi_tenant_bom

Idempotent: checks for existing data before inserting.
"""

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.tenant import Tenant
from app.models.user import Permission, Role, RolePermission, User
from app.models.restaurant_config import RestaurantConfig
from app.models.menu import MenuItem
from app.models.inventory import Ingredient, Recipe, RecipeItem
from app.utils.security import hash_password

# Import existing seed data
from app.scripts.seed import (
    ALL_PERMISSIONS,
    ROLE_DEFINITIONS,
    MENU_CATEGORIES,
    MENU_ITEMS,
    MODIFIER_GROUPS,
    CATEGORY_MODIFIER_LINKS,
    FLOOR_SEED,
    seed_modifier_groups,
    seed_menu,
    seed_floors,
)


# =============================================================================
# TWO-TENANT STRUCTURE
# =============================================================================

TENANTS = [
    {
        "slug": "yk-online",
        "name": "YK Online Restaurant",
        "is_qb_online": True,
        "is_qb_desktop": False,
        "has_bom": False,
    },
    {
        "slug": "yk-desktop",
        "name": "YK Desktop Restaurant",
        "is_qb_online": False,
        "is_qb_desktop": True,
        "has_bom": True,
    },
]

# Seed users for each tenant (admin + cashier only for simplicity)
TENANT_USERS = [
    {
        "email": "admin@ykonline.com",
        "full_name": "YK Online Admin",
        "password": "admin123",
        "pin": "1111",
        "role_name": "admin",
    },
    {
        "email": "cashier@ykonline.com",
        "full_name": "YK Online Cashier",
        "password": "cashier123",
        "pin": "2222",
        "role_name": "cashier",
    },
    {
        "email": "admin@ykdesktop.com",
        "full_name": "YK Desktop Admin",
        "password": "admin123",
        "pin": "3333",
        "role_name": "admin",
    },
    {
        "email": "cashier@ykdesktop.com",
        "full_name": "YK Desktop Cashier",
        "password": "cashier123",
        "pin": "4444",
        "role_name": "cashier",
    },
    {
        "email": "youniskamran@ykdesktop.com",
        "full_name": "Younis Kamran",
        "password": "yk123",
        "pin": "9999",
        "role_name": "admin",
    },
]


# =============================================================================
# BOM SAMPLE DATA (Pakistani Restaurant - Realistic Prices)
# All prices in paisa (100 paisa = 1 PKR)
# Market prices as of March 2026 (Lahore wholesale rates)
# =============================================================================

# Ingredients with realistic Pakistani market prices
BOM_INGREDIENTS = [
    # Proteins
    {
        "name": "Chicken (with bone)",
        "category": "Protein",
        "unit": "kg",
        "cost_per_unit": 65000,  # Rs. 650/kg
        "supplier_name": "Al-Karim Poultry",
        "supplier_contact": "042-35123456",
        "reorder_point": 20.0,
        "reorder_quantity": 50.0,
        "current_stock": 45.0,
        "notes": "Broiler chicken, fresh daily delivery",
    },
    {
        "name": "Chicken (boneless)",
        "category": "Protein",
        "unit": "kg",
        "cost_per_unit": 95000,  # Rs. 950/kg
        "supplier_name": "Al-Karim Poultry",
        "supplier_contact": "042-35123456",
        "reorder_point": 15.0,
        "reorder_quantity": 30.0,
        "current_stock": 25.0,
        "notes": "Breast + thigh meat, cleaned",
    },
    {
        "name": "Mutton",
        "category": "Protein",
        "unit": "kg",
        "cost_per_unit": 180000,  # Rs. 1,800/kg
        "supplier_name": "Qureshi Meat Shop",
        "supplier_contact": "042-35987654",
        "reorder_point": 10.0,
        "reorder_quantity": 20.0,
        "current_stock": 12.0,
        "notes": "Bone-in mutton, fresh",
    },
    {
        "name": "Beef (boneless)",
        "category": "Protein",
        "unit": "kg",
        "cost_per_unit": 120000,  # Rs. 1,200/kg
        "supplier_name": "Qureshi Meat Shop",
        "supplier_contact": "042-35987654",
        "reorder_point": 15.0,
        "reorder_quantity": 30.0,
        "current_stock": 18.0,
        "notes": "For nihari, haleem, kebabs",
    },
    # Grains & Flour
    {
        "name": "Basmati Rice (Super Kernel)",
        "category": "Grains",
        "unit": "kg",
        "cost_per_unit": 18000,  # Rs. 180/kg
        "supplier_name": "Grain Market Lahore",
        "supplier_contact": "042-37654321",
        "reorder_point": 50.0,
        "reorder_quantity": 100.0,
        "current_stock": 75.0,
        "notes": "1121 Super Kernel Basmati",
    },
    {
        "name": "Wheat Flour",
        "category": "Grains",
        "unit": "kg",
        "cost_per_unit": 8000,  # Rs. 80/kg
        "supplier_name": "Grain Market Lahore",
        "supplier_contact": "042-37654321",
        "reorder_point": 40.0,
        "reorder_quantity": 100.0,
        "current_stock": 60.0,
        "notes": "For naan, roti",
    },
    # Dairy
    {
        "name": "Yogurt",
        "category": "Dairy",
        "unit": "kg",
        "cost_per_unit": 22000,  # Rs. 220/kg
        "supplier_name": "Haleeb Dairy Distributor",
        "supplier_contact": "042-35111222",
        "reorder_point": 10.0,
        "reorder_quantity": 20.0,
        "current_stock": 15.0,
        "notes": "Full cream yogurt",
    },
    {
        "name": "Ghee (Pure Desi)",
        "category": "Dairy",
        "unit": "kg",
        "cost_per_unit": 140000,  # Rs. 1,400/kg
        "supplier_name": "Shangrila Ghee",
        "supplier_contact": "042-35222333",
        "reorder_point": 5.0,
        "reorder_quantity": 10.0,
        "current_stock": 8.0,
        "notes": "For biryani, halwa",
    },
    # Oils & Fats
    {
        "name": "Cooking Oil",
        "category": "Oil",
        "unit": "L",
        "cost_per_unit": 42000,  # Rs. 420/L
        "supplier_name": "Dalda Distributor",
        "supplier_contact": "042-35333444",
        "reorder_point": 20.0,
        "reorder_quantity": 40.0,
        "current_stock": 30.0,
        "notes": "Canola oil",
    },
    # Vegetables
    {
        "name": "Onions",
        "category": "Vegetables",
        "unit": "kg",
        "cost_per_unit": 8000,  # Rs. 80/kg
        "supplier_name": "Sabzi Mandi Badami Bagh",
        "supplier_contact": "042-37888999",
        "reorder_point": 30.0,
        "reorder_quantity": 50.0,
        "current_stock": 40.0,
        "notes": "Fresh daily",
    },
    {
        "name": "Tomatoes",
        "category": "Vegetables",
        "unit": "kg",
        "cost_per_unit": 10000,  # Rs. 100/kg
        "supplier_name": "Sabzi Mandi Badami Bagh",
        "supplier_contact": "042-37888999",
        "reorder_point": 25.0,
        "reorder_quantity": 50.0,
        "current_stock": 35.0,
        "notes": "Fresh daily",
    },
    {
        "name": "Ginger",
        "category": "Vegetables",
        "unit": "kg",
        "cost_per_unit": 50000,  # Rs. 500/kg
        "supplier_name": "Sabzi Mandi Badami Bagh",
        "supplier_contact": "042-37888999",
        "reorder_point": 5.0,
        "reorder_quantity": 10.0,
        "current_stock": 7.0,
    },
    {
        "name": "Garlic",
        "category": "Vegetables",
        "unit": "kg",
        "cost_per_unit": 35000,  # Rs. 350/kg
        "supplier_name": "Sabzi Mandi Badami Bagh",
        "supplier_contact": "042-37888999",
        "reorder_point": 5.0,
        "reorder_quantity": 10.0,
        "current_stock": 6.0,
    },
    {
        "name": "Green Chilies",
        "category": "Vegetables",
        "unit": "kg",
        "cost_per_unit": 20000,  # Rs. 200/kg
        "supplier_name": "Sabzi Mandi Badami Bagh",
        "supplier_contact": "042-37888999",
        "reorder_point": 3.0,
        "reorder_quantity": 5.0,
        "current_stock": 4.0,
    },
    # Spices (pre-mixed masalas)
    {
        "name": "Biryani Masala",
        "category": "Spices",
        "unit": "kg",
        "cost_per_unit": 80000,  # Rs. 800/kg
        "supplier_name": "Shan Foods",
        "supplier_contact": "042-35444555",
        "reorder_point": 5.0,
        "reorder_quantity": 10.0,
        "current_stock": 8.0,
        "notes": "Shan brand",
    },
    {
        "name": "Karahi Masala",
        "category": "Spices",
        "unit": "kg",
        "cost_per_unit": 75000,  # Rs. 750/kg
        "supplier_name": "Shan Foods",
        "supplier_contact": "042-35444555",
        "reorder_point": 5.0,
        "reorder_quantity": 10.0,
        "current_stock": 7.0,
        "notes": "Shan brand",
    },
    {
        "name": "Nihari Masala",
        "category": "Spices",
        "unit": "kg",
        "cost_per_unit": 90000,  # Rs. 900/kg
        "supplier_name": "Shan Foods",
        "supplier_contact": "042-35444555",
        "reorder_point": 3.0,
        "reorder_quantity": 5.0,
        "current_stock": 4.0,
        "notes": "Shan brand",
    },
    {
        "name": "BBQ Masala (Tikka/Seekh)",
        "category": "Spices",
        "unit": "kg",
        "cost_per_unit": 85000,  # Rs. 850/kg
        "supplier_name": "Shan Foods",
        "supplier_contact": "042-35444555",
        "reorder_point": 5.0,
        "reorder_quantity": 10.0,
        "current_stock": 6.0,
        "notes": "Shan brand",
    },
    # Miscellaneous
    {
        "name": "Salt",
        "category": "Spices",
        "unit": "kg",
        "cost_per_unit": 5000,  # Rs. 50/kg
        "supplier_name": "K&N Distributor",
        "supplier_contact": "042-35555666",
        "reorder_point": 10.0,
        "reorder_quantity": 20.0,
        "current_stock": 15.0,
    },
]


# Recipes for popular dishes (realistic portions + waste factors)
# Maps menu_item_name → recipe definition
BOM_RECIPES = {
    "Chicken Biryani": {
        "yield_servings": 1,
        "prep_time_minutes": 15,
        "cook_time_minutes": 35,
        "instructions": "1. Marinate chicken with yogurt and biryani masala for 30 min\n2. Par-boil rice until 70% cooked\n3. Layer rice and chicken in pot\n4. Dum cook on low heat for 20 minutes\n5. Garnish with fried onions and serve hot",
        "notes": "Signature dish - maintain consistency",
        "items": [
            ("Chicken (with bone)", 0.5, "kg", 10.0),  # 500g, 10% waste (bones)
            ("Basmati Rice (Super Kernel)", 0.25, "kg", 5.0),  # 250g, 5% waste (rinsing)
            ("Yogurt", 0.1, "kg", 0.0),
            ("Onions", 0.15, "kg", 15.0),  # 150g, 15% waste (peeling)
            ("Tomatoes", 0.1, "kg", 10.0),
            ("Ginger", 0.02, "kg", 5.0),
            ("Garlic", 0.015, "kg", 10.0),
            ("Biryani Masala", 0.03, "kg", 0.0),
            ("Ghee (Pure Desi)", 0.05, "kg", 0.0),
            ("Salt", 0.01, "kg", 0.0),
        ],
    },
    "Mutton Karahi": {
        "yield_servings": 1,
        "prep_time_minutes": 10,
        "cook_time_minutes": 45,
        "instructions": "1. Heat oil in karahi (wok)\n2. Add mutton and brown on high heat\n3. Add tomatoes, ginger, garlic, green chilies\n4. Cook until mutton is tender (30-40 min)\n5. Add karahi masala, simmer 5 minutes\n6. Garnish with coriander and ginger julienne",
        "notes": "Full serving = 1kg mutton, adjust proportionally for half",
        "items": [
            ("Mutton", 1.0, "kg", 5.0),  # Bone-in, minimal waste
            ("Tomatoes", 0.4, "kg", 10.0),
            ("Onions", 0.2, "kg", 15.0),
            ("Ginger", 0.08, "kg", 5.0),
            ("Garlic", 0.06, "kg", 10.0),
            ("Green Chilies", 0.05, "kg", 5.0),
            ("Karahi Masala", 0.04, "kg", 0.0),
            ("Cooking Oil", 0.15, "L", 0.0),
            ("Salt", 0.015, "kg", 0.0),
        ],
    },
    "Chicken Tikka": {
        "yield_servings": 1,
        "prep_time_minutes": 120,  # Includes 2hr marination
        "cook_time_minutes": 20,
        "instructions": "1. Cut chicken into 2-inch cubes\n2. Marinate with yogurt, BBQ masala, oil for 2 hours\n3. Skewer and grill on charcoal for 15-20 minutes\n4. Baste with oil during grilling\n5. Serve with lemon wedges and mint chutney",
        "notes": "Use boneless chicken for tender texture",
        "items": [
            ("Chicken (boneless)", 0.65, "kg", 5.0),  # 650g (makes ~6 pieces)
            ("Yogurt", 0.15, "kg", 0.0),
            ("BBQ Masala (Tikka/Seekh)", 0.04, "kg", 0.0),
            ("Ginger", 0.02, "kg", 5.0),
            ("Garlic", 0.015, "kg", 10.0),
            ("Cooking Oil", 0.05, "L", 0.0),
            ("Salt", 0.008, "kg", 0.0),
        ],
    },
    "Seekh Kebab": {
        "yield_servings": 1,
        "prep_time_minutes": 15,
        "cook_time_minutes": 18,
        "instructions": "1. Mince beef with onions, ginger, garlic\n2. Add BBQ masala, salt, green chilies\n3. Knead mixture until sticky\n4. Form onto skewers\n5. Grill on charcoal for 15-18 minutes, turning frequently\n6. Serve hot with naan and chutney",
        "notes": "Makes 5-6 seekh kebabs per portion",
        "items": [
            ("Beef (boneless)", 0.55, "kg", 0.0),  # Minced, no waste
            ("Onions", 0.15, "kg", 15.0),
            ("Ginger", 0.025, "kg", 5.0),
            ("Garlic", 0.02, "kg", 10.0),
            ("Green Chilies", 0.03, "kg", 5.0),
            ("BBQ Masala (Tikka/Seekh)", 0.035, "kg", 0.0),
            ("Salt", 0.01, "kg", 0.0),
        ],
    },
    "Nihari": {
        "yield_servings": 1,
        "prep_time_minutes": 15,
        "cook_time_minutes": 240,  # 4 hours slow cooking
        "instructions": "1. Sear beef in oil until browned\n2. Add water, bring to boil\n3. Add nihari masala, ginger, garlic\n4. Slow cook on low heat for 4 hours until tender\n5. Mix wheat flour with water, add to thicken gravy\n6. Garnish with ginger julienne, green chilies, lemon",
        "notes": "Traditional breakfast dish - prep night before",
        "items": [
            ("Beef (boneless)", 0.9, "kg", 0.0),
            ("Onions", 0.2, "kg", 15.0),
            ("Ginger", 0.08, "kg", 5.0),
            ("Garlic", 0.06, "kg", 10.0),
            ("Nihari Masala", 0.06, "kg", 0.0),
            ("Wheat Flour", 0.05, "kg", 0.0),  # For thickening
            ("Ghee (Pure Desi)", 0.08, "kg", 0.0),
            ("Salt", 0.015, "kg", 0.0),
        ],
    },
    "Chicken Karahi": {
        "yield_servings": 1,
        "prep_time_minutes": 10,
        "cook_time_minutes": 30,
        "instructions": "1. Heat oil in karahi\n2. Add chicken and cook until color changes\n3. Add tomatoes, ginger, garlic, green chilies\n4. Cook until chicken is tender (20-25 min)\n5. Add karahi masala, simmer 5 minutes\n6. Garnish and serve",
        "notes": "Popular dish - ensure spice level consistency",
        "items": [
            ("Chicken (with bone)", 1.0, "kg", 10.0),
            ("Tomatoes", 0.35, "kg", 10.0),
            ("Onions", 0.15, "kg", 15.0),
            ("Ginger", 0.06, "kg", 5.0),
            ("Garlic", 0.05, "kg", 10.0),
            ("Green Chilies", 0.04, "kg", 5.0),
            ("Karahi Masala", 0.035, "kg", 0.0),
            ("Cooking Oil", 0.12, "L", 0.0),
            ("Salt", 0.012, "kg", 0.0),
        ],
    },
}


# =============================================================================
# SEEDING FUNCTIONS
# =============================================================================


async def seed_multi_tenant(db: AsyncSession) -> dict[str, Tenant]:
    """Seed two tenants (YK Online + YK Desktop)."""
    tenant_map: dict[str, Tenant] = {}

    for tdef in TENANTS:
        result = await db.execute(select(Tenant).where(Tenant.slug == tdef["slug"]))
        tenant = result.scalar_one_or_none()

        if tenant is not None:
            print(f"  Tenant '{tenant.name}' already exists, skipping.")
            tenant_map[tdef["slug"]] = tenant
            continue

        tenant_id = uuid.uuid4()
        tenant = Tenant(
            id=tenant_id,
            tenant_id=tenant_id,
            name=tdef["name"],
            slug=tdef["slug"],
            is_active=True,
        )
        db.add(tenant)
        await db.flush()
        print(f"  Created tenant '{tenant.name}' (id={tenant.id})")
        tenant_map[tdef["slug"]] = tenant

    return tenant_map


async def seed_configs(db: AsyncSession, tenant_map: dict[str, Tenant]) -> None:
    """Seed restaurant configs for both tenants."""
    for slug, tenant in tenant_map.items():
        result = await db.execute(
            select(RestaurantConfig).where(RestaurantConfig.tenant_id == tenant.id)
        )
        config = result.scalar_one_or_none()

        if config is not None:
            print(f"  Config for '{tenant.name}' already exists, skipping.")
            continue

        config = RestaurantConfig(
            tenant_id=tenant.id,
            payment_flow="order_first",
            currency="PKR",
            timezone="Asia/Karachi",
            tax_inclusive=True,
            default_tax_rate=1600,  # 16%
            cash_tax_rate_bps=1600,
            card_tax_rate_bps=500,
            receipt_header=tenant.name,
            receipt_footer="Thank you for your business!",
        )
        db.add(config)
        await db.flush()
        print(f"  Created config for '{tenant.name}'")


async def seed_permissions_roles_users(
    db: AsyncSession, tenant: Tenant, tenant_slug: str
) -> None:
    """Seed permissions, roles, and users for a tenant."""
    # Permissions
    perm_map: dict[str, Permission] = {}
    for code, description in ALL_PERMISSIONS:
        result = await db.execute(
            select(Permission).where(
                Permission.code == code, Permission.tenant_id == tenant.id
            )
        )
        perm = result.scalar_one_or_none()
        if perm is None:
            perm = Permission(
                tenant_id=tenant.id,
                code=code,
                description=description,
            )
            db.add(perm)
            await db.flush()
        perm_map[code] = perm

    # Roles
    role_map: dict[str, Role] = {}
    for role_name, role_def in ROLE_DEFINITIONS.items():
        result = await db.execute(
            select(Role).where(Role.name == role_name, Role.tenant_id == tenant.id)
        )
        role = result.scalar_one_or_none()
        if role is None:
            role = Role(
                tenant_id=tenant.id,
                name=role_name,
                description=role_def["description"],
                is_active=True,
            )
            db.add(role)
            await db.flush()

        # Sync permissions
        desired_perm_ids = {
            perm_map[perm_code].id for perm_code in role_def["permissions"]
        }
        existing_role_perms = (
            await db.execute(
                select(RolePermission).where(RolePermission.role_id == role.id)
            )
        ).scalars().all()
        existing_perm_ids = {rp.permission_id for rp in existing_role_perms}

        for perm_code in role_def["permissions"]:
            perm = perm_map[perm_code]
            if perm.id not in existing_perm_ids:
                rp = RolePermission(
                    tenant_id=tenant.id,
                    role_id=role.id,
                    permission_id=perm.id,
                )
                db.add(rp)
                await db.flush()

        role_map[role_name] = role

    # Users (filter by tenant)
    users_for_tenant = [
        u
        for u in TENANT_USERS
        if (tenant_slug == "yk-online" and "ykonline" in u["email"])
        or (tenant_slug == "yk-desktop" and "ykdesktop" in u["email"])
    ]

    for user_def in users_for_tenant:
        result = await db.execute(
            select(User).where(
                User.email == user_def["email"],
                User.tenant_id == tenant.id,
            )
        )
        user = result.scalar_one_or_none()
        if user is not None:
            continue

        role = role_map[user_def["role_name"]]
        user = User(
            tenant_id=tenant.id,
            email=user_def["email"],
            full_name=user_def["full_name"],
            hashed_password=hash_password(user_def["password"]),
            pin_code=hash_password(user_def["pin"]),
            role_id=role.id,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        print(f"    Created user '{user_def['email']}' with PIN {user_def['pin']}")


async def seed_bom_data(db: AsyncSession, tenant: Tenant) -> None:
    """Seed BOM ingredients and recipes for YK Desktop tenant."""
    print(f"  Seeding BOM data for '{tenant.name}'...")

    # Check if ingredients already exist
    result = await db.execute(
        select(Ingredient).where(Ingredient.tenant_id == tenant.id).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        print("    Ingredients already exist, skipping BOM seed.")
        return

    # Seed ingredients
    ingredient_map: dict[str, Ingredient] = {}
    for idef in BOM_INGREDIENTS:
        ingredient = Ingredient(
            tenant_id=tenant.id,
            name=idef["name"],
            category=idef["category"],
            unit=idef["unit"],
            cost_per_unit=idef["cost_per_unit"],
            supplier_name=idef.get("supplier_name"),
            supplier_contact=idef.get("supplier_contact"),
            reorder_point=idef["reorder_point"],
            reorder_quantity=idef["reorder_quantity"],
            current_stock=idef["current_stock"],
            is_active=True,
            notes=idef.get("notes"),
        )
        db.add(ingredient)
        ingredient_map[idef["name"]] = ingredient

    await db.flush()
    print(f"    Created {len(BOM_INGREDIENTS)} ingredients")

    # Fetch menu items for recipe linking
    result = await db.execute(select(MenuItem).where(MenuItem.tenant_id == tenant.id))
    menu_items_map: dict[str, MenuItem] = {mi.name: mi for mi in result.scalars().all()}

    # Seed recipes
    recipes_created = 0
    for menu_item_name, rdef in BOM_RECIPES.items():
        menu_item = menu_items_map.get(menu_item_name)
        if menu_item is None:
            print(f"    WARNING: Menu item '{menu_item_name}' not found, skipping recipe.")
            continue

        # Check if recipe already exists
        result = await db.execute(
            select(Recipe).where(
                Recipe.menu_item_id == menu_item.id,
                Recipe.tenant_id == tenant.id,
                Recipe.is_active == True,
            )
        )
        if result.scalar_one_or_none() is not None:
            continue

        # Create recipe
        recipe = Recipe(
            tenant_id=tenant.id,
            menu_item_id=menu_item.id,
            yield_servings=rdef["yield_servings"],
            prep_time_minutes=rdef.get("prep_time_minutes"),
            cook_time_minutes=rdef.get("cook_time_minutes"),
            instructions=rdef.get("instructions"),
            notes=rdef.get("notes"),
            version=1,
            is_active=True,
            effective_date=datetime.now(timezone.utc),
        )
        db.add(recipe)
        await db.flush()

        # Create recipe items and calculate costs
        total_cost = 0
        for ingredient_name, quantity, unit, waste_factor in rdef["items"]:
            ingredient = ingredient_map.get(ingredient_name)
            if ingredient is None:
                print(
                    f"      WARNING: Ingredient '{ingredient_name}' not found for '{menu_item_name}'"
                )
                continue

            # Calculate item cost with waste factor
            adjusted_qty = quantity * (1 + waste_factor / 100)
            item_cost = round(adjusted_qty * ingredient.cost_per_unit)
            total_cost += item_cost

            recipe_item = RecipeItem(
                tenant_id=tenant.id,
                recipe_id=recipe.id,
                ingredient_id=ingredient.id,
                quantity=quantity,
                unit=unit,
                waste_factor=waste_factor,
                cost_per_unit_snapshot=ingredient.cost_per_unit,
                total_cost=item_cost,
            )
            db.add(recipe_item)

        # Update recipe with calculated costs
        recipe.total_ingredient_cost = total_cost
        recipe.cost_per_serving = round(total_cost / recipe.yield_servings)

        # Calculate food cost percentage
        if menu_item.price > 0:
            recipe.food_cost_percentage = round(
                (recipe.cost_per_serving / menu_item.price) * 100, 2
            )
        else:
            recipe.food_cost_percentage = 0.0

        await db.flush()
        recipes_created += 1

        print(
            f"    ✓ Recipe: {menu_item_name} | Cost: Rs.{recipe.cost_per_serving/100:.2f} | Food %: {recipe.food_cost_percentage:.1f}%"
        )

    print(f"    Created {recipes_created} recipes with cost calculations")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


async def main() -> None:
    """Run the full multi-tenant + BOM seed process."""
    print("=" * 70)
    print("POS System -- Multi-Tenant Seed with BOM Data")
    print("=" * 70)

    async with async_session_factory() as db:
        try:
            print("\n[1/7] Seeding tenants (YK Online + YK Desktop)...")
            tenant_map = await seed_multi_tenant(db)

            print("\n[2/7] Seeding restaurant configs...")
            await seed_configs(db, tenant_map)

            # Seed permissions, roles, users for each tenant
            for slug, tenant in tenant_map.items():
                print(f"\n[3/7] Seeding permissions, roles, users for '{tenant.name}'...")
                await seed_permissions_roles_users(db, tenant, slug)

            # Seed menu for each tenant
            for slug, tenant in tenant_map.items():
                print(f"\n[4/7] Seeding menu for '{tenant.name}'...")
                modifier_group_map = await seed_modifier_groups(db, tenant)
                await seed_menu(db, tenant, modifier_group_map)

            # Seed floors for each tenant
            for slug, tenant in tenant_map.items():
                print(f"\n[5/7] Seeding floors & tables for '{tenant.name}'...")
                await seed_floors(db, tenant)

            # Seed BOM data ONLY for YK Desktop tenant
            print("\n[6/7] Seeding BOM data (ingredients + recipes)...")
            yk_desktop_tenant = tenant_map.get("yk-desktop")
            if yk_desktop_tenant:
                await seed_bom_data(db, yk_desktop_tenant)
            else:
                print("  WARNING: YK Desktop tenant not found, skipping BOM seed.")

            await db.commit()
            print("\n[7/7] Seed completed successfully!")

            # Print login credentials summary
            print("\n" + "=" * 70)
            print("LOGIN CREDENTIALS SUMMARY")
            print("=" * 70)
            print("\n📍 YK Online Restaurant (QB Online):")
            print("   Admin:   admin@ykonline.com    | PIN: 1111 | Pass: admin123")
            print("   Cashier: cashier@ykonline.com  | PIN: 2222 | Pass: cashier123")
            print("\n📍 YK Desktop Restaurant (QB Desktop + BOM):")
            print("   Admin:   admin@ykdesktop.com   | PIN: 3333 | Pass: admin123")
            print("   Cashier: cashier@ykdesktop.com | PIN: 4444 | Pass: cashier123")
            print("   Younis:  youniskamran@ykdesktop.com | PIN: 9999 | Pass: yk123")
            print("\n💡 BOM Module:")
            print("   - Ingredients: /admin/ingredients (19 Pakistani ingredients seeded)")
            print("   - Recipes:     /admin/recipes (6 recipes with cost calculations)")
            print("\n" + "=" * 70)

        except Exception:
            await db.rollback()
            print("\n❌ Seed failed, transaction rolled back.")
            raise
        finally:
            await db.close()


if __name__ == "__main__":
    asyncio.run(main())
