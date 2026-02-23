"""Seed script for POS System — creates demo tenant, auth data, and menu.

Run with:
    python -m app.scripts.seed

Idempotent: checks for existing data before inserting.
"""

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.tenant import Tenant
from app.models.user import Permission, Role, RolePermission, User
from app.models.restaurant_config import RestaurantConfig
from app.models.menu import Category, MenuItem, ModifierGroup, Modifier, MenuItemModifierGroup
from app.models.floor import Floor, Table
from app.models.order import Order, OrderItem, OrderItemModifier, OrderStatusLog
from app.models.payment import CashDrawerSession, Payment, PaymentMethod
from app.utils.security import hash_password


# ---------------------------------------------------------------------------
# Phase 2: Seed data definitions
# ---------------------------------------------------------------------------

DEMO_TENANT_SLUG = "demo-restaurant"

ALL_PERMISSIONS = [
    ("order.create", "Create new orders"),
    ("order.view", "View orders"),
    ("order.edit", "Edit existing orders"),
    ("order.void", "Void / cancel orders"),
    ("menu.view", "View menu items"),
    ("menu.edit", "Edit menu items"),
    ("kitchen.view", "View kitchen display"),
    ("kitchen.manage", "Manage kitchen operations"),
    ("payment.collect", "Collect payments"),
    ("payment.refund", "Issue refunds"),
    ("report.view", "View reports"),
    ("report.export", "Export reports"),
    ("staff.manage", "Manage staff accounts"),
    ("settings.manage", "Manage restaurant settings"),
    ("floor.edit", "Edit floor plan / table layout"),
]

ROLE_DEFINITIONS: dict[str, dict] = {
    "admin": {
        "description": "Full access to all features",
        "permissions": [code for code, _ in ALL_PERMISSIONS],
    },
    "cashier": {
        "description": "Front-of-house staff handling orders and payments",
        "permissions": [
            "order.create",
            "order.view",
            "order.edit",
            "order.void",
            "payment.collect",
            "menu.view",
            "kitchen.view",
        ],
    },
    "kitchen": {
        "description": "Kitchen staff viewing and managing orders",
        "permissions": [
            "kitchen.view",
            "kitchen.manage",
            "order.view",
        ],
    },
}

SEED_USERS = [
    {
        "email": "admin@demo.com",
        "full_name": "Admin User",
        "password": "admin123",
        "pin": "1234",
        "role_name": "admin",
    },
    {
        "email": "cashier@demo.com",
        "full_name": "Cashier User",
        "password": "cashier123",
        "pin": "5678",
        "role_name": "cashier",
    },
    {
        "email": "kitchen@demo.com",
        "full_name": "Kitchen User",
        "password": "kitchen123",
        "pin": "9012",
        "role_name": "kitchen",
    },
    {
        "email": "youniskamran@demo.com",
        "full_name": "Younis Kamran",
        "password": "yk123",
        "pin": "1111",
        "role_name": "admin",
    },
]


# ---------------------------------------------------------------------------
# Phase 3: Menu seed data (Pakistani restaurant)
# All prices in paisa (100 paisa = 1 PKR)
# ---------------------------------------------------------------------------

MENU_CATEGORIES = [
    {"name": "BBQ & Grill", "icon": "flame", "display_order": 1,
     "description": "Charcoal grilled meats and tikkas"},
    {"name": "Karahi", "icon": "soup", "display_order": 2,
     "description": "Traditional karahi dishes cooked in iron woks"},
    {"name": "Biryani & Rice", "icon": "utensils-crossed", "display_order": 3,
     "description": "Aromatic rice dishes and biryanis"},
    {"name": "Naan & Roti", "icon": "croissant", "display_order": 4,
     "description": "Freshly baked breads from the tandoor"},
    {"name": "Curries", "icon": "cooking-pot", "display_order": 5,
     "description": "Traditional curry dishes"},
    {"name": "Appetizers", "icon": "salad", "display_order": 6,
     "description": "Starters and snacks"},
    {"name": "Drinks", "icon": "cup-soda", "display_order": 7,
     "description": "Hot and cold beverages"},
    {"name": "Desserts", "icon": "cake-slice", "display_order": 8,
     "description": "Sweet treats and traditional desserts"},
]

# category_name -> list of items
MENU_ITEMS: dict[str, list[dict]] = {
    "BBQ & Grill": [
        {"name": "Chicken Tikka", "price": 65000, "display_order": 1,
         "description": "Boneless chicken marinated in spices, grilled on charcoal", "prep_time": 20,
         "image_url": "https://images.unsplash.com/photo-1599487488170-d11ec9c172f0?w=400&h=300&fit=crop"},
        {"name": "Seekh Kebab", "price": 55000, "display_order": 2,
         "description": "Minced beef kebabs cooked on skewers", "prep_time": 18,
         "image_url": "https://images.unsplash.com/photo-1603496987351-f84a3ba5ec85?w=400&h=300&fit=crop"},
        {"name": "Malai Boti", "price": 75000, "display_order": 3,
         "description": "Creamy marinated chicken pieces, charcoal grilled", "prep_time": 20,
         "image_url": "https://images.unsplash.com/photo-1610057099443-fde6c99db9e1?w=400&h=300&fit=crop"},
        {"name": "Lamb Chops", "price": 120000, "display_order": 4,
         "description": "Tender lamb chops marinated and grilled to perfection", "prep_time": 25,
         "image_url": "https://images.unsplash.com/photo-1514516345957-556ca7d90a29?w=400&h=300&fit=crop"},
        {"name": "Reshmi Kebab", "price": 60000, "display_order": 5,
         "description": "Silky smooth chicken kebabs with cream", "prep_time": 18,
         "image_url": "https://images.unsplash.com/photo-1567188040759-fb8a883dc6d8?w=400&h=300&fit=crop"},
        {"name": "Mixed Grill Platter", "price": 180000, "display_order": 6,
         "description": "Assorted BBQ: tikka, seekh kebab, malai boti, chops", "prep_time": 30,
         "image_url": "https://images.unsplash.com/photo-1544025162-d76694265947?w=400&h=300&fit=crop"},
    ],
    "Karahi": [
        {"name": "Chicken Karahi", "price": 130000, "display_order": 1,
         "description": "Classic chicken karahi with tomatoes, green chilies, ginger", "prep_time": 25,
         "image_url": "https://images.unsplash.com/photo-1631452180519-c014fe946bc7?w=400&h=300&fit=crop"},
        {"name": "Mutton Karahi", "price": 180000, "display_order": 2,
         "description": "Traditional mutton karahi slow-cooked in spices", "prep_time": 35,
         "image_url": "https://images.unsplash.com/photo-1545247181-516773cae754?w=400&h=300&fit=crop"},
        {"name": "Prawn Karahi", "price": 160000, "display_order": 3,
         "description": "Fresh prawns cooked in karahi style", "prep_time": 20,
         "image_url": "https://images.unsplash.com/photo-1625398407796-82650a8c135f?w=400&h=300&fit=crop"},
        {"name": "Namkeen Gosht", "price": 170000, "display_order": 4,
         "description": "Salt-and-pepper style dry meat karahi", "prep_time": 30,
         "image_url": "https://images.unsplash.com/photo-1574653853027-5382a3d23a15?w=400&h=300&fit=crop"},
    ],
    "Biryani & Rice": [
        {"name": "Chicken Biryani", "price": 35000, "display_order": 1,
         "description": "Aromatic basmati rice layered with spiced chicken", "prep_time": 25,
         "image_url": "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=400&h=300&fit=crop"},
        {"name": "Mutton Biryani", "price": 45000, "display_order": 2,
         "description": "Premium mutton biryani with saffron rice", "prep_time": 30,
         "image_url": "https://images.unsplash.com/photo-1642821373181-696a54913e93?w=400&h=300&fit=crop"},
        {"name": "Sindhi Biryani", "price": 40000, "display_order": 3,
         "description": "Spicy Sindhi-style biryani with potatoes and plums", "prep_time": 25,
         "image_url": "https://images.unsplash.com/photo-1589302168068-964664d93dc0?w=400&h=300&fit=crop"},
        {"name": "Pulao", "price": 30000, "display_order": 4,
         "description": "Lightly spiced rice with meat", "prep_time": 20,
         "image_url": "https://images.unsplash.com/photo-1596797038530-2c107229654b?w=400&h=300&fit=crop"},
        {"name": "Plain Rice", "price": 15000, "display_order": 5,
         "description": "Steamed basmati rice", "prep_time": 10,
         "image_url": "https://images.unsplash.com/photo-1516684732162-798a0062be99?w=400&h=300&fit=crop"},
    ],
    "Naan & Roti": [
        {"name": "Plain Naan", "price": 5000, "display_order": 1,
         "description": "Fresh tandoori naan", "prep_time": 5,
         "image_url": "https://images.unsplash.com/photo-1565557623262-b51c2513a641?w=400&h=300&fit=crop"},
        {"name": "Butter Naan", "price": 7000, "display_order": 2,
         "description": "Naan brushed with butter", "prep_time": 5,
         "image_url": "https://images.unsplash.com/photo-1600628421060-939639517883?w=400&h=300&fit=crop"},
        {"name": "Garlic Naan", "price": 8000, "display_order": 3,
         "description": "Naan topped with garlic and herbs", "prep_time": 5,
         "image_url": "https://images.unsplash.com/photo-1585937421612-70a008356fbe?w=400&h=300&fit=crop"},
        {"name": "Cheese Naan", "price": 12000, "display_order": 4,
         "description": "Naan stuffed with melted cheese", "prep_time": 7,
         "image_url": "https://images.unsplash.com/photo-1601050690597-df0568f70950?w=400&h=300&fit=crop"},
        {"name": "Roghni Naan", "price": 6000, "display_order": 5,
         "description": "Soft naan with egg wash and sesame seeds", "prep_time": 5,
         "image_url": "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=400&h=300&fit=crop"},
        {"name": "Tandoori Roti", "price": 3000, "display_order": 6,
         "description": "Whole wheat bread from the tandoor", "prep_time": 5,
         "image_url": "https://images.unsplash.com/photo-1604152135912-04a022e23696?w=400&h=300&fit=crop"},
    ],
    "Curries": [
        {"name": "Chicken Handi", "price": 85000, "display_order": 1,
         "description": "Creamy chicken curry cooked in a clay pot", "prep_time": 25,
         "image_url": "https://images.unsplash.com/photo-1603894584373-5ac82b2ae398?w=400&h=300&fit=crop"},
        {"name": "Daal Makhani", "price": 45000, "display_order": 2,
         "description": "Rich black lentils slow-cooked with butter and cream", "prep_time": 20,
         "image_url": "https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&h=300&fit=crop"},
        {"name": "Palak Paneer", "price": 50000, "display_order": 3,
         "description": "Spinach curry with cottage cheese cubes", "prep_time": 20,
         "image_url": "https://images.unsplash.com/photo-1601050690597-df0568f70950?w=400&h=300&fit=crop"},
        {"name": "Nihari", "price": 90000, "display_order": 4,
         "description": "Slow-cooked beef stew, Mughlai style", "prep_time": 40,
         "image_url": "https://images.unsplash.com/photo-1585937421612-70a008356fbe?w=400&h=300&fit=crop"},
        {"name": "Haleem", "price": 70000, "display_order": 5,
         "description": "Thick meat and lentil stew with wheat", "prep_time": 35,
         "image_url": "https://images.unsplash.com/photo-1574653853027-5382a3d23a15?w=400&h=300&fit=crop"},
    ],
    "Appetizers": [
        {"name": "Samosa (2 pcs)", "price": 15000, "display_order": 1,
         "description": "Crispy pastry filled with spiced potatoes and peas", "prep_time": 10,
         "image_url": "https://images.unsplash.com/photo-1601050690597-df0568f70950?w=400&h=300&fit=crop"},
        {"name": "Chicken Pakora", "price": 25000, "display_order": 2,
         "description": "Spiced chicken fritters, deep fried", "prep_time": 12,
         "image_url": "https://images.unsplash.com/photo-1567188040759-fb8a883dc6d8?w=400&h=300&fit=crop"},
        {"name": "Fish Pakora", "price": 30000, "display_order": 3,
         "description": "Battered fish pieces, deep fried", "prep_time": 12,
         "image_url": "https://images.unsplash.com/photo-1626645738196-c2a7c87a8f58?w=400&h=300&fit=crop"},
        {"name": "Dahi Bhalla", "price": 20000, "display_order": 4,
         "description": "Lentil dumplings in yogurt with chutneys", "prep_time": 8,
         "image_url": "https://images.unsplash.com/photo-1606491956689-2ea866880049?w=400&h=300&fit=crop"},
        {"name": "Chana Chaat", "price": 18000, "display_order": 5,
         "description": "Spiced chickpea salad with chutneys", "prep_time": 8,
         "image_url": "https://images.unsplash.com/photo-1626776876729-bab4369a5a5a?w=400&h=300&fit=crop"},
    ],
    "Drinks": [
        {"name": "Lassi (Sweet)", "price": 15000, "display_order": 1,
         "description": "Creamy yogurt drink, sweetened", "prep_time": 3,
         "image_url": "https://images.unsplash.com/photo-1587049352846-4a222e784d38?w=400&h=300&fit=crop"},
        {"name": "Lassi (Salt)", "price": 15000, "display_order": 2,
         "description": "Creamy yogurt drink, salted", "prep_time": 3,
         "image_url": "https://images.unsplash.com/photo-1587049352846-4a222e784d38?w=400&h=300&fit=crop"},
        {"name": "Fresh Lime Water", "price": 10000, "display_order": 3,
         "description": "Fresh squeezed lime with water", "prep_time": 3,
         "image_url": "https://images.unsplash.com/photo-1523371683773-affcb3f1e8f9?w=400&h=300&fit=crop"},
        {"name": "Doodh Patti Chai", "price": 8000, "display_order": 4,
         "description": "Traditional milk tea", "prep_time": 5,
         "image_url": "https://images.unsplash.com/photo-1571934811356-5cc061b6821f?w=400&h=300&fit=crop"},
        {"name": "Kashmiri Chai", "price": 12000, "display_order": 5,
         "description": "Pink tea with cardamom and nuts", "prep_time": 8,
         "image_url": "https://images.unsplash.com/photo-1571934811356-5cc061b6821f?w=400&h=300&fit=crop"},
        {"name": "Cold Drink (Can)", "price": 10000, "display_order": 6,
         "description": "Coca-Cola / Pepsi / 7UP", "prep_time": 1,
         "image_url": "https://images.unsplash.com/photo-1629203851122-3726ecdf080e?w=400&h=300&fit=crop"},
        {"name": "Mineral Water", "price": 5000, "display_order": 7,
         "description": "500ml bottled water", "prep_time": 1,
         "image_url": "https://images.unsplash.com/photo-1548839140-29a749e1cf4d?w=400&h=300&fit=crop"},
    ],
    "Desserts": [
        {"name": "Gulab Jamun (2 pcs)", "price": 15000, "display_order": 1,
         "description": "Deep-fried milk dumplings in sugar syrup", "prep_time": 5,
         "image_url": "https://images.unsplash.com/photo-1666190406021-2c0f07c79c15?w=400&h=300&fit=crop"},
        {"name": "Kheer", "price": 18000, "display_order": 2,
         "description": "Rice pudding with cardamom and nuts", "prep_time": 5,
         "image_url": "https://images.unsplash.com/photo-1631452180519-c014fe946bc7?w=400&h=300&fit=crop"},
        {"name": "Gajar Ka Halwa", "price": 20000, "display_order": 3,
         "description": "Sweet carrot pudding with nuts", "prep_time": 5,
         "image_url": "https://images.unsplash.com/photo-1645177628172-a94c1f96e6db?w=400&h=300&fit=crop"},
        {"name": "Firni", "price": 15000, "display_order": 4,
         "description": "Ground rice pudding set in clay pots", "prep_time": 5,
         "image_url": "https://images.unsplash.com/photo-1488477181946-6428a0291777?w=400&h=300&fit=crop"},
    ],
}

MODIFIER_GROUPS = [
    {
        "name": "Spice Level",
        "display_order": 1,
        "required": True,
        "min_selections": 1,
        "max_selections": 1,
        "modifiers": [
            {"name": "Mild", "price_adjustment": 0, "display_order": 1},
            {"name": "Medium", "price_adjustment": 0, "display_order": 2},
            {"name": "Hot", "price_adjustment": 0, "display_order": 3},
            {"name": "Extra Hot", "price_adjustment": 0, "display_order": 4},
        ],
    },
    {
        "name": "Serving Size",
        "display_order": 2,
        "required": True,
        "min_selections": 1,
        "max_selections": 1,
        "modifiers": [
            {"name": "Half", "price_adjustment": -40000, "display_order": 1},
            {"name": "Full", "price_adjustment": 0, "display_order": 2},
        ],
    },
    {
        "name": "Extras",
        "display_order": 3,
        "required": False,
        "min_selections": 0,
        "max_selections": 0,  # unlimited
        "modifiers": [
            {"name": "Extra Raita", "price_adjustment": 5000, "display_order": 1},
            {"name": "Extra Salad", "price_adjustment": 5000, "display_order": 2},
            {"name": "Extra Naan", "price_adjustment": 5000, "display_order": 3},
            {"name": "Extra Chutney", "price_adjustment": 3000, "display_order": 4},
        ],
    },
    {
        "name": "Drink Size",
        "display_order": 4,
        "required": True,
        "min_selections": 1,
        "max_selections": 1,
        "modifiers": [
            {"name": "Regular", "price_adjustment": 0, "display_order": 1},
            {"name": "Large", "price_adjustment": 5000, "display_order": 2},
        ],
    },
]

# Which categories get which modifier groups
CATEGORY_MODIFIER_LINKS: dict[str, list[str]] = {
    "BBQ & Grill": ["Spice Level", "Extras"],
    "Karahi": ["Spice Level", "Serving Size", "Extras"],
    "Biryani & Rice": ["Spice Level", "Extras"],
    "Curries": ["Spice Level", "Serving Size", "Extras"],
    "Appetizers": ["Spice Level"],
    "Drinks": ["Drink Size"],
}


# ---------------------------------------------------------------------------
# Phase 2: Seed logic
# ---------------------------------------------------------------------------

async def seed_tenant(db: AsyncSession) -> Tenant:
    result = await db.execute(
        select(Tenant).where(Tenant.slug == DEMO_TENANT_SLUG)
    )
    tenant = result.scalar_one_or_none()
    if tenant is not None:
        print(f"  Tenant '{tenant.name}' already exists, skipping.")
        return tenant

    tenant_id = uuid.uuid4()
    tenant = Tenant(
        id=tenant_id,
        tenant_id=tenant_id,
        name="Demo Restaurant",
        slug=DEMO_TENANT_SLUG,
        is_active=True,
    )
    db.add(tenant)
    await db.flush()
    print(f"  Created tenant '{tenant.name}' (id={tenant.id})")
    return tenant


async def seed_config(db: AsyncSession, tenant: Tenant) -> RestaurantConfig:
    result = await db.execute(
        select(RestaurantConfig).where(RestaurantConfig.tenant_id == tenant.id)
    )
    config = result.scalar_one_or_none()
    if config is not None:
        print("  Restaurant config already exists, skipping.")
        return config

    config = RestaurantConfig(
        tenant_id=tenant.id,
        payment_flow="order_first",
        currency="PKR",
        timezone="Asia/Karachi",
        tax_inclusive=True,
        default_tax_rate=1600,
        receipt_header="Demo Restaurant",
        receipt_footer="Thank you for dining with us!",
    )
    db.add(config)
    await db.flush()
    print("  Created restaurant config.")
    return config


async def seed_permissions(db: AsyncSession, tenant: Tenant) -> dict[str, Permission]:
    perm_map: dict[str, Permission] = {}
    for code, description in ALL_PERMISSIONS:
        result = await db.execute(
            select(Permission).where(Permission.code == code)
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
            print(f"  Created permission '{code}'")
        perm_map[code] = perm
    return perm_map


async def seed_roles(
    db: AsyncSession, tenant: Tenant, perm_map: dict[str, Permission],
) -> dict[str, Role]:
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
            print(f"  Created role '{role_name}'")

        for perm_code in role_def["permissions"]:
            perm = perm_map[perm_code]
            existing = await db.execute(
                select(RolePermission).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == perm.id,
                )
            )
            if existing.scalar_one_or_none() is None:
                rp = RolePermission(
                    tenant_id=tenant.id,
                    role_id=role.id,
                    permission_id=perm.id,
                )
                db.add(rp)
                await db.flush()

        role_map[role_name] = role
    return role_map


async def seed_users(
    db: AsyncSession, tenant: Tenant, role_map: dict[str, Role],
) -> None:
    for user_def in SEED_USERS:
        result = await db.execute(
            select(User).where(
                User.email == user_def["email"],
                User.tenant_id == tenant.id,
            )
        )
        user = result.scalar_one_or_none()
        if user is not None:
            print(f"  User '{user_def['email']}' already exists, skipping.")
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
        print(f"  Created user '{user_def['email']}' with role '{user_def['role_name']}'")


# ---------------------------------------------------------------------------
# Phase 3: Menu seed logic
# ---------------------------------------------------------------------------

async def seed_modifier_groups(
    db: AsyncSession, tenant: Tenant
) -> dict[str, ModifierGroup]:
    """Create modifier groups and their modifiers, returning name -> ModifierGroup map."""
    group_map: dict[str, ModifierGroup] = {}

    for gdef in MODIFIER_GROUPS:
        result = await db.execute(
            select(ModifierGroup).where(
                ModifierGroup.name == gdef["name"],
                ModifierGroup.tenant_id == tenant.id,
            )
        )
        group = result.scalar_one_or_none()
        if group is None:
            group = ModifierGroup(
                tenant_id=tenant.id,
                name=gdef["name"],
                display_order=gdef["display_order"],
                required=gdef["required"],
                min_selections=gdef["min_selections"],
                max_selections=gdef["max_selections"],
                is_active=True,
            )
            db.add(group)
            await db.flush()
            print(f"  Created modifier group '{gdef['name']}'")

            for mdef in gdef["modifiers"]:
                mod = Modifier(
                    tenant_id=tenant.id,
                    group_id=group.id,
                    name=mdef["name"],
                    price_adjustment=mdef["price_adjustment"],
                    display_order=mdef["display_order"],
                    is_available=True,
                )
                db.add(mod)
            await db.flush()
        else:
            print(f"  Modifier group '{gdef['name']}' already exists, skipping.")

        group_map[gdef["name"]] = group

    return group_map


async def seed_menu(
    db: AsyncSession,
    tenant: Tenant,
    modifier_group_map: dict[str, ModifierGroup],
) -> None:
    """Create categories, menu items, and link modifier groups to items."""
    cat_map: dict[str, Category] = {}

    # Create categories
    for cdef in MENU_CATEGORIES:
        result = await db.execute(
            select(Category).where(
                Category.name == cdef["name"],
                Category.tenant_id == tenant.id,
            )
        )
        cat = result.scalar_one_or_none()
        if cat is None:
            cat = Category(
                tenant_id=tenant.id,
                name=cdef["name"],
                description=cdef["description"],
                display_order=cdef["display_order"],
                icon=cdef["icon"],
                is_active=True,
            )
            db.add(cat)
            await db.flush()
            print(f"  Created category '{cdef['name']}'")
        else:
            print(f"  Category '{cdef['name']}' already exists, skipping.")
        cat_map[cdef["name"]] = cat

    # Create menu items
    items_created = 0
    for cat_name, items_list in MENU_ITEMS.items():
        cat = cat_map[cat_name]
        modifier_group_names = CATEGORY_MODIFIER_LINKS.get(cat_name, [])

        for idef in items_list:
            result = await db.execute(
                select(MenuItem).where(
                    MenuItem.name == idef["name"],
                    MenuItem.category_id == cat.id,
                    MenuItem.tenant_id == tenant.id,
                )
            )
            item = result.scalar_one_or_none()
            if item is not None:
                continue

            item = MenuItem(
                tenant_id=tenant.id,
                category_id=cat.id,
                name=idef["name"],
                description=idef.get("description"),
                price=idef["price"],
                display_order=idef["display_order"],
                preparation_time_minutes=idef.get("prep_time"),
                image_url=idef.get("image_url"),
                is_available=True,
            )
            db.add(item)
            await db.flush()

            # Link modifier groups for this category to each item
            for mg_name in modifier_group_names:
                mg = modifier_group_map.get(mg_name)
                if mg is None:
                    continue
                link = MenuItemModifierGroup(
                    tenant_id=tenant.id,
                    menu_item_id=item.id,
                    modifier_group_id=mg.id,
                )
                db.add(link)

            await db.flush()
            items_created += 1

    print(f"  Created {items_created} menu items (skipped existing).")


# ---------------------------------------------------------------------------
# Phase 4: Floor plan seed data
# ---------------------------------------------------------------------------

FLOOR_SEED = [
    {
        "name": "Ground Floor",
        "display_order": 1,
        "tables": [
            {"number": 1, "capacity": 2, "shape": "round",     "pos_x": 60,  "pos_y": 60,  "width": 70,  "height": 70},
            {"number": 2, "capacity": 2, "shape": "round",     "pos_x": 180, "pos_y": 60,  "width": 70,  "height": 70},
            {"number": 3, "capacity": 4, "shape": "square",    "pos_x": 320, "pos_y": 60,  "width": 90,  "height": 90},
            {"number": 4, "capacity": 4, "shape": "square",    "pos_x": 460, "pos_y": 60,  "width": 90,  "height": 90},
            {"number": 5, "capacity": 6, "shape": "rectangle", "pos_x": 60,  "pos_y": 220, "width": 140, "height": 80},
            {"number": 6, "capacity": 6, "shape": "rectangle", "pos_x": 260, "pos_y": 220, "width": 140, "height": 80},
            {"number": 7, "capacity": 8, "shape": "rectangle", "pos_x": 460, "pos_y": 220, "width": 160, "height": 90},
            {"number": 8, "capacity": 4, "shape": "square",    "pos_x": 60,  "pos_y": 380, "width": 90,  "height": 90},
            {"number": 9, "capacity": 4, "shape": "square",    "pos_x": 200, "pos_y": 380, "width": 90,  "height": 90},
            {"number": 10, "capacity": 2, "shape": "round",    "pos_x": 360, "pos_y": 380, "width": 70,  "height": 70},
        ],
    },
    {
        "name": "Terrace",
        "display_order": 2,
        "tables": [
            {"number": 11, "capacity": 4, "shape": "square",    "pos_x": 80,  "pos_y": 80,  "width": 90,  "height": 90},
            {"number": 12, "capacity": 4, "shape": "square",    "pos_x": 240, "pos_y": 80,  "width": 90,  "height": 90},
            {"number": 13, "capacity": 6, "shape": "rectangle", "pos_x": 400, "pos_y": 80,  "width": 140, "height": 80},
            {"number": 14, "capacity": 2, "shape": "round",     "pos_x": 80,  "pos_y": 240, "width": 70,  "height": 70},
            {"number": 15, "capacity": 2, "shape": "round",     "pos_x": 200, "pos_y": 240, "width": 70,  "height": 70},
            {"number": 16, "capacity": 8, "shape": "rectangle", "pos_x": 340, "pos_y": 240, "width": 180, "height": 90, "label": "VIP-1"},
        ],
    },
]


async def seed_floors(db: AsyncSession, tenant: Tenant) -> None:
    """Create floors and tables for the demo restaurant."""
    floors_created = 0
    tables_created = 0

    for fdef in FLOOR_SEED:
        result = await db.execute(
            select(Floor).where(
                Floor.name == fdef["name"],
                Floor.tenant_id == tenant.id,
            )
        )
        floor = result.scalar_one_or_none()
        if floor is None:
            floor = Floor(
                tenant_id=tenant.id,
                name=fdef["name"],
                display_order=fdef["display_order"],
                is_active=True,
            )
            db.add(floor)
            await db.flush()
            floors_created += 1
            print(f"  Created floor '{fdef['name']}'")
        else:
            print(f"  Floor '{fdef['name']}' already exists, skipping.")

        for tdef in fdef["tables"]:
            result = await db.execute(
                select(Table).where(
                    Table.number == tdef["number"],
                    Table.floor_id == floor.id,
                    Table.tenant_id == tenant.id,
                )
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                continue

            table = Table(
                tenant_id=tenant.id,
                floor_id=floor.id,
                number=tdef["number"],
                label=tdef.get("label"),
                capacity=tdef["capacity"],
                shape=tdef["shape"],
                pos_x=tdef["pos_x"],
                pos_y=tdef["pos_y"],
                width=tdef["width"],
                height=tdef["height"],
                is_active=True,
            )
            db.add(table)
            tables_created += 1

        await db.flush()

    print(f"  Created {floors_created} floors, {tables_created} tables (skipped existing).")


# ---------------------------------------------------------------------------
# Phase 5: Order seed data
# ---------------------------------------------------------------------------

# order_number, order_type, status, table_number (or None), customer_name,
# items: list of (menu_item_name, qty, modifier_names)
SEED_ORDERS = [
    # 3 dine-in orders
    {
        "order_number": "260210-001",
        "order_type": "dine_in",
        "status": "in_kitchen",
        "table_number": 3,
        "items": [
            ("Chicken Tikka", 2, ["Medium"]),
            ("Butter Naan", 4, []),
            ("Lassi (Sweet)", 2, ["Regular"]),
        ],
    },
    {
        "order_number": "260210-002",
        "order_type": "dine_in",
        "status": "ready",
        "table_number": 5,
        "items": [
            ("Chicken Karahi", 1, ["Hot", "Full"]),
            ("Plain Naan", 6, []),
            ("Cold Drink (Can)", 3, ["Regular"]),
            ("Dahi Bhalla", 1, ["Mild"]),
        ],
    },
    {
        "order_number": "260210-003",
        "order_type": "dine_in",
        "status": "served",
        "table_number": 7,
        "items": [
            ("Mixed Grill Platter", 1, ["Medium"]),
            ("Mutton Karahi", 1, ["Hot", "Full"]),
            ("Garlic Naan", 4, []),
            ("Doodh Patti Chai", 4, ["Regular"]),
        ],
    },
    # 3 takeaway orders
    {
        "order_number": "260210-004",
        "order_type": "takeaway",
        "status": "in_kitchen",
        "table_number": None,
        "items": [
            ("Chicken Biryani", 3, ["Medium"]),
            ("Samosa (2 pcs)", 2, ["Mild"]),
        ],
    },
    {
        "order_number": "260210-005",
        "order_type": "takeaway",
        "status": "ready",
        "table_number": None,
        "items": [
            ("Seekh Kebab", 4, ["Hot"]),
            ("Tandoori Roti", 8, []),
            ("Chana Chaat", 2, ["Medium"]),
        ],
    },
    {
        "order_number": "260210-006",
        "order_type": "takeaway",
        "status": "completed",
        "table_number": None,
        "items": [
            ("Malai Boti", 2, ["Mild"]),
            ("Cheese Naan", 2, []),
        ],
    },
    # 2 call center orders
    {
        "order_number": "260210-007",
        "order_type": "call_center",
        "status": "in_kitchen",
        "table_number": None,
        "customer_name": "Ahmed Khan",
        "customer_phone": "03001234567",
        "items": [
            ("Mutton Biryani", 2, ["Medium"]),
            ("Chicken Pakora", 1, ["Hot"]),
            ("Fresh Lime Water", 2, ["Regular"]),
        ],
    },
    {
        "order_number": "260210-008",
        "order_type": "call_center",
        "status": "completed",
        "table_number": None,
        "customer_name": "Sara Ali",
        "customer_phone": "03219876543",
        "items": [
            ("Nihari", 1, ["Medium", "Full"]),
            ("Roghni Naan", 4, []),
            ("Kashmiri Chai", 2, ["Large"]),
        ],
    },
    # Extra variety
    {
        "order_number": "260210-009",
        "order_type": "dine_in",
        "status": "completed",
        "table_number": 1,
        "items": [
            ("Daal Makhani", 1, ["Mild", "Full"]),
            ("Plain Rice", 1, ["Mild"]),
            ("Gulab Jamun (2 pcs)", 2, []),
        ],
    },
    {
        "order_number": "260210-010",
        "order_type": "takeaway",
        "status": "confirmed",
        "table_number": None,
        "items": [
            ("Lamb Chops", 2, ["Medium"]),
            ("Garlic Naan", 2, []),
            ("Kheer", 2, []),
        ],
    },
]

# State machine path to reach each status
STATUS_PATH: dict[str, list[str]] = {
    "confirmed": ["confirmed"],
    "in_kitchen": ["confirmed", "in_kitchen"],
    "ready": ["confirmed", "in_kitchen", "ready"],
    "served": ["confirmed", "in_kitchen", "ready", "served"],
    "completed": ["confirmed", "in_kitchen", "ready", "served", "completed"],
}


async def seed_orders(db: AsyncSession, tenant: Tenant) -> None:
    """Create sample orders with items, modifiers, and status logs."""
    from datetime import datetime, timedelta, timezone

    # Check if orders already exist
    result = await db.execute(
        select(Order).where(Order.tenant_id == tenant.id).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        print("  Orders already exist, skipping.")
        return

    # Get admin user for created_by
    result = await db.execute(
        select(User).where(User.email == "admin@demo.com", User.tenant_id == tenant.id)
    )
    admin = result.scalar_one_or_none()
    if admin is None:
        print("  Admin user not found, skipping orders.")
        return

    # Get restaurant config for tax rate
    result = await db.execute(
        select(RestaurantConfig).where(RestaurantConfig.tenant_id == tenant.id)
    )
    config = result.scalar_one_or_none()
    tax_rate_bps = config.default_tax_rate if config else 1600  # 16% default

    # Build lookup maps
    result = await db.execute(
        select(MenuItem).where(MenuItem.tenant_id == tenant.id)
    )
    menu_items_map: dict[str, MenuItem] = {mi.name: mi for mi in result.scalars().all()}

    result = await db.execute(
        select(Modifier).where(Modifier.tenant_id == tenant.id)
    )
    modifiers_map: dict[str, Modifier] = {m.name: m for m in result.scalars().all()}

    result = await db.execute(
        select(Table).where(Table.tenant_id == tenant.id)
    )
    tables_map: dict[int, Table] = {t.number: t for t in result.scalars().all()}

    orders_created = 0
    base_time = datetime.now(timezone.utc) - timedelta(hours=2)

    for idx, odef in enumerate(SEED_ORDERS):
        order_time = base_time + timedelta(minutes=idx * 12)

        # Resolve table
        table_id = None
        table_num = odef.get("table_number")
        if table_num is not None:
            table = tables_map.get(table_num)
            if table:
                table_id = table.id

        # Build order items and calculate totals
        order_items: list[OrderItem] = []
        subtotal = 0

        for item_name, qty, mod_names in odef["items"]:
            mi = menu_items_map.get(item_name)
            if mi is None:
                continue

            # Calculate unit price with modifiers
            base_price = mi.price
            item_modifiers: list[OrderItemModifier] = []
            for mname in mod_names:
                mod = modifiers_map.get(mname)
                if mod:
                    base_price += mod.price_adjustment
                    item_modifiers.append(OrderItemModifier(
                        tenant_id=tenant.id,
                        modifier_id=mod.id,
                        name=mod.name,
                        price_adjustment=mod.price_adjustment,
                    ))

            unit_price = max(0, base_price)
            line_total = unit_price * qty
            subtotal += line_total

            oi = OrderItem(
                tenant_id=tenant.id,
                menu_item_id=mi.id,
                name=mi.name,
                quantity=qty,
                unit_price=unit_price,
                total=line_total,
                status="pending",
                modifiers=item_modifiers,
            )
            order_items.append(oi)

        if not order_items:
            continue

        # Tax calculation
        tax_amount = round(subtotal * tax_rate_bps / 10_000)
        total = subtotal + tax_amount

        order = Order(
            tenant_id=tenant.id,
            order_number=odef["order_number"],
            order_type=odef["order_type"],
            status=odef["status"],
            payment_status="paid" if odef["status"] == "completed" else "unpaid",
            table_id=table_id,
            customer_name=odef.get("customer_name"),
            customer_phone=odef.get("customer_phone"),
            subtotal=subtotal,
            tax_amount=tax_amount,
            discount_amount=0,
            total=total,
            created_by=admin.id,
            items=order_items,
        )
        db.add(order)
        await db.flush()

        # Create status log entries for the transition path
        status_path = STATUS_PATH.get(odef["status"], ["confirmed"])
        prev_status = None
        for step_idx, step_status in enumerate(status_path):
            log = OrderStatusLog(
                tenant_id=tenant.id,
                order_id=order.id,
                from_status=prev_status,
                to_status=step_status,
                changed_by=admin.id,
            )
            db.add(log)
            prev_status = step_status

        # Mark dine-in tables as occupied (if order is active)
        if (odef["order_type"] == "dine_in"
                and table_num is not None
                and odef["status"] not in ("completed", "voided")):
            table = tables_map.get(table_num)
            if table:
                table.status = "occupied"

        await db.flush()
        orders_created += 1

    print(f"  Created {orders_created} sample orders with items and status logs.")


# ---------------------------------------------------------------------------
# Phase 9: Seed payments + cash drawer for demo
# ---------------------------------------------------------------------------

async def seed_payments(db: AsyncSession, tenant: Tenant) -> None:
    """Create payment methods, payments for completed orders, and a cash drawer session."""
    from datetime import datetime, timedelta, timezone

    # Check if payments already exist
    existing = await db.execute(
        select(Payment).where(Payment.tenant_id == tenant.id).limit(1)
    )
    if existing.scalar_one_or_none():
        print("  Payments already seeded, skipping.")
        return

    # Ensure payment methods exist
    methods_result = await db.execute(
        select(PaymentMethod).where(PaymentMethod.tenant_id == tenant.id)
    )
    existing_methods = {m.code: m for m in methods_result.scalars().all()}

    default_methods = [
        ("cash", "Cash", False, 1),
        ("card", "Card", True, 2),
        ("mobile_wallet", "Mobile Wallet", True, 3),
        ("bank_transfer", "Bank Transfer", True, 4),
    ]

    for code, display_name, requires_ref, sort_order in default_methods:
        if code not in existing_methods:
            method = PaymentMethod(
                tenant_id=tenant.id,
                code=code,
                display_name=display_name,
                is_active=True,
                requires_reference=requires_ref,
                sort_order=sort_order,
            )
            db.add(method)
            existing_methods[code] = method

    await db.flush()

    # Re-fetch methods to get IDs
    methods_result = await db.execute(
        select(PaymentMethod).where(PaymentMethod.tenant_id == tenant.id)
    )
    methods = {m.code: m for m in methods_result.scalars().all()}

    cash_method = methods.get("cash")
    card_method = methods.get("card")
    if not cash_method or not card_method:
        print("  Payment methods not found, skipping payments.")
        return

    # Get admin user
    admin_result = await db.execute(
        select(User).where(User.tenant_id == tenant.id, User.email == "admin@demo.com")
    )
    admin = admin_result.scalar_one_or_none()
    if not admin:
        print("  Admin user not found, skipping payments.")
        return

    # Get completed orders
    completed_result = await db.execute(
        select(Order).where(
            Order.tenant_id == tenant.id,
            Order.status == "completed",
        )
    )
    completed_orders = list(completed_result.scalars().all())

    # Create payments for completed orders (alternate cash/card)
    payments_created = 0
    for i, order in enumerate(completed_orders):
        method = cash_method if i % 2 == 0 else card_method
        tendered = None
        change = 0
        ref = None

        if method.code == "cash":
            # Round up to nearest 100 PKR for cash
            tendered_rupees = ((order.total // 100) // 100 + 1) * 100
            tendered = tendered_rupees * 100  # back to paisa
            change = tendered - order.total
        else:
            ref = f"TXN-{240223000 + i}"

        payment = Payment(
            tenant_id=tenant.id,
            order_id=order.id,
            method_id=method.id,
            kind="payment",
            status="completed",
            amount=order.total,
            tendered_amount=tendered,
            change_amount=change,
            reference=ref,
            processed_by=admin.id,
        )
        db.add(payment)
        payments_created += 1

    await db.flush()

    # Create a cash drawer session
    now = datetime.now(timezone.utc)
    session_open = now - timedelta(hours=8)

    # Calculate expected cash balance
    cash_in = sum(
        o.total for i, o in enumerate(completed_orders)
        if i % 2 == 0  # cash payments
    )
    cash_change = sum(
        (((o.total // 100) // 100 + 1) * 100 * 100 - o.total)
        for i, o in enumerate(completed_orders)
        if i % 2 == 0
    )
    opening_float = 500000  # Rs. 5,000
    expected_balance = opening_float + cash_in - cash_change

    # Small variance for demo realism
    counted = expected_balance - 5000  # Rs. 50 short

    drawer = CashDrawerSession(
        tenant_id=tenant.id,
        status="closed",
        opened_by=admin.id,
        opened_at=session_open,
        opening_float=opening_float,
        closed_by=admin.id,
        closed_at=now - timedelta(minutes=30),
        closing_balance_expected=expected_balance,
        closing_balance_counted=counted,
        note="End of shift — slight cash variance",
    )
    db.add(drawer)
    await db.flush()

    print(f"  Created {payments_created} payments + 1 cash drawer session.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    """Run the full seed process inside a single transaction."""
    print("=" * 60)
    print("POS System -- Seed Script (Phase 2 + 3 + 4 + 5 + 7)")
    print("=" * 60)

    async with async_session_factory() as db:
        try:
            print("\n[1/10] Seeding tenant...")
            tenant = await seed_tenant(db)

            print("\n[2/10] Seeding restaurant config...")
            await seed_config(db, tenant)

            print("\n[3/10] Seeding permissions...")
            perm_map = await seed_permissions(db, tenant)

            print("\n[4/10] Seeding roles...")
            role_map = await seed_roles(db, tenant, perm_map)

            print("\n[5/10] Seeding users...")
            await seed_users(db, tenant, role_map)

            print("\n[6/10] Seeding modifier groups...")
            modifier_group_map = await seed_modifier_groups(db, tenant)

            print("\n[7/10] Seeding menu (categories + items)...")
            await seed_menu(db, tenant, modifier_group_map)

            print("\n[8/10] Seeding floors & tables...")
            await seed_floors(db, tenant)

            print("\n[9/10] Seeding sample orders...")
            await seed_orders(db, tenant)

            print("\n[10/10] Seeding payments & cash drawer...")
            await seed_payments(db, tenant)

            await db.commit()
            print("\nSeed completed successfully!")

        except Exception:
            await db.rollback()
            print("\nSeed failed, transaction rolled back.")
            raise
        finally:
            await db.close()

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
