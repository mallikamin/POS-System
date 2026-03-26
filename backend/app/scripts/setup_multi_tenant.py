"""Multi-tenant setup script: Creates Cosa Nostra tenant, moves Italian menu to it,
seeds Pakistani menu for YK Demo tenant, and renames demo tenant.

Run with:
    python -m app.scripts.setup_multi_tenant

Safety guarantees:
    - NO data deletion. All operations are INSERT or UPDATE only.
    - Idempotent: checks for existing records before creating.
    - Single transaction: all-or-nothing commit.
"""

import asyncio
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.tenant import Tenant
from app.models.user import Role, RolePermission, User
from app.models.restaurant_config import RestaurantConfig
from app.models.menu import (
    Category,
    MenuItem,
    ModifierGroup,
    Modifier,
    MenuItemModifierGroup,
)
from app.utils.security import hash_password


# ---------------------------------------------------------------------------
# Pakistani menu data (exact copy from seed.py with Jalebi added)
# All prices in paisa (100 paisa = 1 PKR)
# ---------------------------------------------------------------------------

PK_MENU_CATEGORIES = [
    {
        "name": "BBQ & Grill",
        "icon": "flame",
        "display_order": 1,
        "description": "Charcoal grilled meats and tikkas",
    },
    {
        "name": "Karahi",
        "icon": "soup",
        "display_order": 2,
        "description": "Traditional karahi dishes cooked in iron woks",
    },
    {
        "name": "Biryani & Rice",
        "icon": "utensils-crossed",
        "display_order": 3,
        "description": "Aromatic rice dishes and biryanis",
    },
    {
        "name": "Naan & Roti",
        "icon": "croissant",
        "display_order": 4,
        "description": "Freshly baked breads from the tandoor",
    },
    {
        "name": "Curries",
        "icon": "cooking-pot",
        "display_order": 5,
        "description": "Traditional curry dishes",
    },
    {
        "name": "Appetizers",
        "icon": "salad",
        "display_order": 6,
        "description": "Starters and snacks",
    },
    {
        "name": "Drinks",
        "icon": "cup-soda",
        "display_order": 7,
        "description": "Hot and cold beverages",
    },
    {
        "name": "Desserts",
        "icon": "cake-slice",
        "display_order": 8,
        "description": "Sweet treats and traditional desserts",
    },
]

PK_MENU_ITEMS: dict[str, list[dict]] = {
    "BBQ & Grill": [
        {
            "name": "Chicken Tikka",
            "price": 65000,
            "display_order": 1,
            "description": "Boneless chicken marinated in spices, grilled on charcoal",
            "prep_time": 20,
            "image_url": "https://images.unsplash.com/photo-1599487488170-d11ec9c172f0?w=400&h=300&fit=crop",
        },
        {
            "name": "Seekh Kebab",
            "price": 55000,
            "display_order": 2,
            "description": "Minced beef kebabs cooked on skewers",
            "prep_time": 18,
            "image_url": "https://images.unsplash.com/photo-1603496987351-f84a3ba5ec85?w=400&h=300&fit=crop",
        },
        {
            "name": "Malai Boti",
            "price": 75000,
            "display_order": 3,
            "description": "Creamy marinated chicken pieces, charcoal grilled",
            "prep_time": 20,
            "image_url": "https://images.unsplash.com/photo-1610057099443-fde6c99db9e1?w=400&h=300&fit=crop",
        },
        {
            "name": "Lamb Chops",
            "price": 120000,
            "display_order": 4,
            "description": "Tender lamb chops marinated and grilled to perfection",
            "prep_time": 25,
            "image_url": "https://images.unsplash.com/photo-1514516345957-556ca7d90a29?w=400&h=300&fit=crop",
        },
        {
            "name": "Reshmi Kebab",
            "price": 60000,
            "display_order": 5,
            "description": "Silky smooth chicken kebabs with cream",
            "prep_time": 18,
            "image_url": "https://images.unsplash.com/photo-1567188040759-fb8a883dc6d8?w=400&h=300&fit=crop",
        },
        {
            "name": "Mixed Grill Platter",
            "price": 180000,
            "display_order": 6,
            "description": "Assorted BBQ: tikka, seekh kebab, malai boti, chops",
            "prep_time": 30,
            "image_url": "https://images.unsplash.com/photo-1544025162-d76694265947?w=400&h=300&fit=crop",
        },
    ],
    "Karahi": [
        {
            "name": "Chicken Karahi",
            "price": 130000,
            "display_order": 1,
            "description": "Classic chicken karahi with tomatoes, green chilies, ginger",
            "prep_time": 25,
            "image_url": "https://images.unsplash.com/photo-1631452180519-c014fe946bc7?w=400&h=300&fit=crop",
        },
        {
            "name": "Mutton Karahi",
            "price": 180000,
            "display_order": 2,
            "description": "Traditional mutton karahi slow-cooked in spices",
            "prep_time": 35,
            "image_url": "https://images.unsplash.com/photo-1545247181-516773cae754?w=400&h=300&fit=crop",
        },
        {
            "name": "Prawn Karahi",
            "price": 160000,
            "display_order": 3,
            "description": "Fresh prawns cooked in karahi style",
            "prep_time": 20,
            "image_url": "https://images.unsplash.com/photo-1625398407796-82650a8c135f?w=400&h=300&fit=crop",
        },
        {
            "name": "Namkeen Gosht",
            "price": 170000,
            "display_order": 4,
            "description": "Salt-and-pepper style dry meat karahi",
            "prep_time": 30,
            "image_url": "https://images.unsplash.com/photo-1574653853027-5382a3d23a15?w=400&h=300&fit=crop",
        },
    ],
    "Biryani & Rice": [
        {
            "name": "Chicken Biryani",
            "price": 35000,
            "display_order": 1,
            "description": "Aromatic basmati rice layered with spiced chicken",
            "prep_time": 25,
            "image_url": "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=400&h=300&fit=crop",
        },
        {
            "name": "Mutton Biryani",
            "price": 45000,
            "display_order": 2,
            "description": "Premium mutton biryani with saffron rice",
            "prep_time": 30,
            "image_url": "https://images.unsplash.com/photo-1642821373181-696a54913e93?w=400&h=300&fit=crop",
        },
        {
            "name": "Sindhi Biryani",
            "price": 40000,
            "display_order": 3,
            "description": "Spicy Sindhi-style biryani with potatoes and plums",
            "prep_time": 25,
            "image_url": "https://images.unsplash.com/photo-1589302168068-964664d93dc0?w=400&h=300&fit=crop",
        },
        {
            "name": "Pulao",
            "price": 30000,
            "display_order": 4,
            "description": "Lightly spiced rice with meat",
            "prep_time": 20,
            "image_url": "https://images.unsplash.com/photo-1596797038530-2c107229654b?w=400&h=300&fit=crop",
        },
        {
            "name": "Plain Rice",
            "price": 15000,
            "display_order": 5,
            "description": "Steamed basmati rice",
            "prep_time": 10,
            "image_url": "https://images.unsplash.com/photo-1516684732162-798a0062be99?w=400&h=300&fit=crop",
        },
    ],
    "Naan & Roti": [
        {
            "name": "Plain Naan",
            "price": 5000,
            "display_order": 1,
            "description": "Fresh tandoori naan",
            "prep_time": 5,
            "image_url": "https://images.unsplash.com/photo-1565557623262-b51c2513a641?w=400&h=300&fit=crop",
        },
        {
            "name": "Butter Naan",
            "price": 7000,
            "display_order": 2,
            "description": "Naan brushed with butter",
            "prep_time": 5,
            "image_url": "https://images.unsplash.com/photo-1600628421060-939639517883?w=400&h=300&fit=crop",
        },
        {
            "name": "Garlic Naan",
            "price": 8000,
            "display_order": 3,
            "description": "Naan topped with garlic and herbs",
            "prep_time": 5,
            "image_url": "https://images.unsplash.com/photo-1585937421612-70a008356fbe?w=400&h=300&fit=crop",
        },
        {
            "name": "Cheese Naan",
            "price": 12000,
            "display_order": 4,
            "description": "Naan stuffed with melted cheese",
            "prep_time": 7,
            "image_url": "https://images.unsplash.com/photo-1601050690597-df0568f70950?w=400&h=300&fit=crop",
        },
        {
            "name": "Roghni Naan",
            "price": 6000,
            "display_order": 5,
            "description": "Soft naan with egg wash and sesame seeds",
            "prep_time": 5,
            "image_url": "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=400&h=300&fit=crop",
        },
        {
            "name": "Tandoori Roti",
            "price": 3000,
            "display_order": 6,
            "description": "Whole wheat bread from the tandoor",
            "prep_time": 5,
            "image_url": "https://images.unsplash.com/photo-1604152135912-04a022e23696?w=400&h=300&fit=crop",
        },
    ],
    "Curries": [
        {
            "name": "Chicken Handi",
            "price": 85000,
            "display_order": 1,
            "description": "Creamy chicken curry cooked in a clay pot",
            "prep_time": 25,
            "image_url": "https://images.unsplash.com/photo-1603894584373-5ac82b2ae398?w=400&h=300&fit=crop",
        },
        {
            "name": "Daal Makhani",
            "price": 45000,
            "display_order": 2,
            "description": "Rich black lentils slow-cooked with butter and cream",
            "prep_time": 20,
            "image_url": "https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&h=300&fit=crop",
        },
        {
            "name": "Palak Paneer",
            "price": 50000,
            "display_order": 3,
            "description": "Spinach curry with cottage cheese cubes",
            "prep_time": 20,
            "image_url": "https://images.unsplash.com/photo-1601050690597-df0568f70950?w=400&h=300&fit=crop",
        },
        {
            "name": "Nihari",
            "price": 90000,
            "display_order": 4,
            "description": "Slow-cooked beef stew, Mughlai style",
            "prep_time": 40,
            "image_url": "https://images.unsplash.com/photo-1585937421612-70a008356fbe?w=400&h=300&fit=crop",
        },
        {
            "name": "Haleem",
            "price": 70000,
            "display_order": 5,
            "description": "Thick meat and lentil stew with wheat",
            "prep_time": 35,
            "image_url": "https://images.unsplash.com/photo-1574653853027-5382a3d23a15?w=400&h=300&fit=crop",
        },
    ],
    "Appetizers": [
        {
            "name": "Samosa (2 pcs)",
            "price": 15000,
            "display_order": 1,
            "description": "Crispy pastry filled with spiced potatoes and peas",
            "prep_time": 10,
            "image_url": "https://images.unsplash.com/photo-1601050690597-df0568f70950?w=400&h=300&fit=crop",
        },
        {
            "name": "Chicken Pakora",
            "price": 25000,
            "display_order": 2,
            "description": "Spiced chicken fritters, deep fried",
            "prep_time": 12,
            "image_url": "https://images.unsplash.com/photo-1567188040759-fb8a883dc6d8?w=400&h=300&fit=crop",
        },
        {
            "name": "Fish Pakora",
            "price": 30000,
            "display_order": 3,
            "description": "Battered fish pieces, deep fried",
            "prep_time": 12,
            "image_url": "https://images.unsplash.com/photo-1626645738196-c2a7c87a8f58?w=400&h=300&fit=crop",
        },
        {
            "name": "Dahi Bhalla",
            "price": 20000,
            "display_order": 4,
            "description": "Lentil dumplings in yogurt with chutneys",
            "prep_time": 8,
            "image_url": "https://images.unsplash.com/photo-1606491956689-2ea866880049?w=400&h=300&fit=crop",
        },
        {
            "name": "Chana Chaat",
            "price": 18000,
            "display_order": 5,
            "description": "Spiced chickpea salad with chutneys",
            "prep_time": 8,
            "image_url": "https://images.unsplash.com/photo-1626776876729-bab4369a5a5a?w=400&h=300&fit=crop",
        },
    ],
    "Drinks": [
        {
            "name": "Lassi (Sweet)",
            "price": 15000,
            "display_order": 1,
            "description": "Creamy yogurt drink, sweetened",
            "prep_time": 3,
            "image_url": "https://images.unsplash.com/photo-1587049352846-4a222e784d38?w=400&h=300&fit=crop",
        },
        {
            "name": "Lassi (Salt)",
            "price": 15000,
            "display_order": 2,
            "description": "Creamy yogurt drink, salted",
            "prep_time": 3,
            "image_url": "https://images.unsplash.com/photo-1587049352846-4a222e784d38?w=400&h=300&fit=crop",
        },
        {
            "name": "Fresh Lime Water",
            "price": 10000,
            "display_order": 3,
            "description": "Fresh squeezed lime with water",
            "prep_time": 3,
            "image_url": "https://images.unsplash.com/photo-1523371683773-affcb3f1e8f9?w=400&h=300&fit=crop",
        },
        {
            "name": "Doodh Patti Chai",
            "price": 8000,
            "display_order": 4,
            "description": "Traditional milk tea",
            "prep_time": 5,
            "image_url": "https://images.unsplash.com/photo-1571934811356-5cc061b6821f?w=400&h=300&fit=crop",
        },
        {
            "name": "Kashmiri Chai",
            "price": 12000,
            "display_order": 5,
            "description": "Pink tea with cardamom and nuts",
            "prep_time": 8,
            "image_url": "https://images.unsplash.com/photo-1571934811356-5cc061b6821f?w=400&h=300&fit=crop",
        },
        {
            "name": "Cold Drink (Can)",
            "price": 10000,
            "display_order": 6,
            "description": "Coca-Cola / Pepsi / 7UP",
            "prep_time": 1,
            "image_url": "https://images.unsplash.com/photo-1629203851122-3726ecdf080e?w=400&h=300&fit=crop",
        },
        {
            "name": "Mineral Water",
            "price": 5000,
            "display_order": 7,
            "description": "500ml bottled water",
            "prep_time": 1,
            "image_url": "https://images.unsplash.com/photo-1548839140-29a749e1cf4d?w=400&h=300&fit=crop",
        },
    ],
    "Desserts": [
        {
            "name": "Gulab Jamun (2 pcs)",
            "price": 15000,
            "display_order": 1,
            "description": "Deep-fried milk dumplings in sugar syrup",
            "prep_time": 5,
            "image_url": "https://images.unsplash.com/photo-1666190406021-2c0f07c79c15?w=400&h=300&fit=crop",
        },
        {
            "name": "Kheer",
            "price": 18000,
            "display_order": 2,
            "description": "Rice pudding with cardamom and nuts",
            "prep_time": 5,
            "image_url": "https://images.unsplash.com/photo-1631452180519-c014fe946bc7?w=400&h=300&fit=crop",
        },
        {
            "name": "Gajar Ka Halwa",
            "price": 20000,
            "display_order": 3,
            "description": "Sweet carrot pudding with nuts",
            "prep_time": 5,
            "image_url": "https://images.unsplash.com/photo-1645177628172-a94c1f96e6db?w=400&h=300&fit=crop",
        },
        {
            "name": "Firni",
            "price": 15000,
            "display_order": 4,
            "description": "Ground rice pudding set in clay pots",
            "prep_time": 5,
            "image_url": "https://images.unsplash.com/photo-1488477181946-6428a0291777?w=400&h=300&fit=crop",
        },
        {
            "name": "Jalebi (200g)",
            "price": 12000,
            "display_order": 5,
            "description": "Crispy deep-fried swirls soaked in saffron syrup",
            "prep_time": 5,
            "image_url": "https://images.unsplash.com/photo-1666190406021-2c0f07c79c15?w=400&h=300&fit=crop",
        },
    ],
}

PK_MODIFIER_GROUPS = [
    {
        "name": "Spice Level",
        "display_order": 1,
        "required": True,
        "min_selections": 1,
        "max_selections": 1,
        "modifiers": [
            {"name": "Mild", "price_adjustment": 0, "display_order": 1},
            {"name": "Medium", "price_adjustment": 0, "display_order": 2},
            {"name": "Spicy", "price_adjustment": 0, "display_order": 3},
            {"name": "Extra Spicy", "price_adjustment": 0, "display_order": 4},
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
            {"name": "Extra Chutney", "price_adjustment": 3000, "display_order": 2},
            {"name": "Extra Naan", "price_adjustment": 5000, "display_order": 3},
            {"name": "Extra Salad", "price_adjustment": 8000, "display_order": 4},
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

# Modifier group -> category linkage for Pakistani menu
# Per user spec:
#   Spice Level -> BBQ & Grill, Karahi, Curries
#   Serving Size -> Karahi, Biryani & Rice
#   Extras -> BBQ & Grill, Karahi, Curries, Biryani & Rice
#   Drink Size -> Drinks (except Cold Drink (Can) and Mineral Water)
PK_CATEGORY_MODIFIER_LINKS: dict[str, list[str]] = {
    "BBQ & Grill": ["Spice Level", "Extras"],
    "Karahi": ["Spice Level", "Serving Size", "Extras"],
    "Biryani & Rice": ["Serving Size", "Extras"],
    "Curries": ["Spice Level", "Extras"],
}

# Drink items that should NOT get the Drink Size modifier
DRINKS_NO_SIZE = {"Cold Drink (Can)", "Mineral Water"}


# ---------------------------------------------------------------------------
# STEP 1: Create Cosa Nostra tenant + config + admin user
# ---------------------------------------------------------------------------


async def step1_create_cosa_nostra(db: AsyncSession) -> uuid.UUID:
    """Create Cosa Nostra tenant, config, and admin user.
    Returns the Cosa Nostra tenant_id.
    """
    print("\n" + "=" * 60)
    print("STEP 1: Create Cosa Nostra tenant")
    print("=" * 60)

    # Check if Cosa Nostra tenant already exists
    result = await db.execute(
        select(Tenant).where(Tenant.name == "Cosa Nostra")
    )
    cosa_tenant = result.scalar_one_or_none()

    if cosa_tenant is not None:
        print(f"  Cosa Nostra tenant already exists (id={cosa_tenant.id}), skipping creation.")
        cosa_id = cosa_tenant.id
    else:
        # Create tenant
        cosa_id = uuid.uuid4()
        cosa_tenant = Tenant(
            id=cosa_id,
            tenant_id=cosa_id,  # Self-referencing FK
            name="Cosa Nostra",
            slug="cosa-nostra",
            is_active=True,
        )
        db.add(cosa_tenant)
        await db.flush()
        print(f"  Created tenant 'Cosa Nostra' (id={cosa_id})")

    # Create restaurant config (idempotent)
    result = await db.execute(
        select(RestaurantConfig).where(RestaurantConfig.tenant_id == cosa_id)
    )
    if result.scalar_one_or_none() is None:
        config = RestaurantConfig(
            tenant_id=cosa_id,
            payment_flow="order_first",
            currency="PKR",
            timezone="Asia/Karachi",
            tax_inclusive=True,
            default_tax_rate=1600,
            cash_tax_rate_bps=1600,
            card_tax_rate_bps=500,
            receipt_header="Cosa Nostra",
            receipt_footer="Thank you for dining with us!",
        )
        db.add(config)
        await db.flush()
        print("  Created restaurant config for Cosa Nostra.")
    else:
        print("  Restaurant config already exists, skipping.")

    # Look up or create admin role for Cosa Nostra tenant
    result = await db.execute(
        select(Role).where(Role.name == "admin", Role.tenant_id == cosa_id)
    )
    admin_role = result.scalar_one_or_none()

    if admin_role is None:
        # Find an existing admin role from any tenant to copy permissions from
        result = await db.execute(
            select(Role).where(Role.name == "admin").limit(1)
        )
        source_role = result.scalar_one_or_none()

        if source_role is None:
            raise RuntimeError(
                "No 'admin' role found in the database. Run seed.py first."
            )

        admin_role = Role(
            tenant_id=cosa_id,
            name="admin",
            description="Full access to all features",
            is_active=True,
        )
        db.add(admin_role)
        await db.flush()
        print(f"  Created 'admin' role for Cosa Nostra (id={admin_role.id})")

        # Copy role_permissions from the source admin role
        from sqlalchemy.orm import selectinload

        result = await db.execute(
            select(Role)
            .where(Role.id == source_role.id)
            .options(selectinload(Role.permissions))
        )
        source_role_loaded = result.scalar_one()

        for perm in source_role_loaded.permissions:
            rp = RolePermission(
                tenant_id=cosa_id,
                role_id=admin_role.id,
                permission_id=perm.id,
            )
            db.add(rp)
        await db.flush()
        print(
            f"  Copied {len(source_role_loaded.permissions)} permissions "
            f"to Cosa Nostra admin role."
        )
    else:
        print(f"  Admin role already exists for Cosa Nostra (id={admin_role.id})")

    # Create admin user (idempotent)
    result = await db.execute(
        select(User).where(
            User.email == "admin@cosanostra.com",
            User.tenant_id == cosa_id,
        )
    )
    if result.scalar_one_or_none() is None:
        admin_user = User(
            tenant_id=cosa_id,
            email="admin@cosanostra.com",
            full_name="Cosa Nostra Admin",
            hashed_password=hash_password("cosanostra123"),
            pin_code=hash_password("4321"),
            role_id=admin_role.id,
            is_active=True,
        )
        db.add(admin_user)
        await db.flush()
        print("  Created admin user: admin@cosanostra.com (PIN: 4321)")
    else:
        print("  Admin user admin@cosanostra.com already exists, skipping.")

    return cosa_id


# ---------------------------------------------------------------------------
# STEP 2: Move Italian menu to Cosa Nostra tenant
# ---------------------------------------------------------------------------


async def step2_move_italian_menu(
    db: AsyncSession,
    demo_tenant_id: uuid.UUID,
    cosa_tenant_id: uuid.UUID,
) -> None:
    """Move all menu data from demo tenant to Cosa Nostra tenant."""
    print("\n" + "=" * 60)
    print("STEP 2: Move Italian menu to Cosa Nostra tenant")
    print("=" * 60)

    # Count what we are moving
    result = await db.execute(
        select(Category).where(Category.tenant_id == demo_tenant_id)
    )
    categories = result.scalars().all()
    print(f"  Found {len(categories)} categories to move.")

    result = await db.execute(
        select(MenuItem).where(MenuItem.tenant_id == demo_tenant_id)
    )
    items = result.scalars().all()
    print(f"  Found {len(items)} menu items to move.")

    result = await db.execute(
        select(ModifierGroup).where(ModifierGroup.tenant_id == demo_tenant_id)
    )
    mod_groups = result.scalars().all()
    print(f"  Found {len(mod_groups)} modifier groups to move.")

    result = await db.execute(
        select(Modifier).where(Modifier.tenant_id == demo_tenant_id)
    )
    modifiers = result.scalars().all()
    print(f"  Found {len(modifiers)} modifiers to move.")

    if len(categories) == 0 and len(items) == 0:
        print("  No menu data to move. Skipping Step 2.")
        return

    # UPDATE categories
    await db.execute(
        update(Category)
        .where(Category.tenant_id == demo_tenant_id)
        .values(tenant_id=cosa_tenant_id)
    )
    print(f"  Moved {len(categories)} categories to Cosa Nostra.")

    # UPDATE menu_items
    await db.execute(
        update(MenuItem)
        .where(MenuItem.tenant_id == demo_tenant_id)
        .values(tenant_id=cosa_tenant_id)
    )
    print(f"  Moved {len(items)} menu items to Cosa Nostra.")

    # UPDATE modifier_groups
    await db.execute(
        update(ModifierGroup)
        .where(ModifierGroup.tenant_id == demo_tenant_id)
        .values(tenant_id=cosa_tenant_id)
    )
    print(f"  Moved {len(mod_groups)} modifier groups to Cosa Nostra.")

    # UPDATE modifiers
    await db.execute(
        update(Modifier)
        .where(Modifier.tenant_id == demo_tenant_id)
        .values(tenant_id=cosa_tenant_id)
    )
    print(f"  Moved {len(modifiers)} modifiers to Cosa Nostra.")

    # UPDATE menu_item_modifier_groups for items that were moved
    item_ids = [item.id for item in items]
    if item_ids:
        await db.execute(
            update(MenuItemModifierGroup)
            .where(MenuItemModifierGroup.menu_item_id.in_(item_ids))
            .values(tenant_id=cosa_tenant_id)
        )
        result = await db.execute(
            select(MenuItemModifierGroup).where(
                MenuItemModifierGroup.menu_item_id.in_(item_ids)
            )
        )
        link_count = len(result.scalars().all())
        print(f"  Moved {link_count} menu_item_modifier_group links to Cosa Nostra.")

    await db.flush()
    print("  Step 2 complete.")


# ---------------------------------------------------------------------------
# STEP 3: Insert Pakistani menu for YK Demo tenant
# ---------------------------------------------------------------------------


async def step3_insert_pakistani_menu(
    db: AsyncSession,
    demo_tenant_id: uuid.UUID,
) -> None:
    """Seed the full Pakistani menu for the YK Demo tenant."""
    print("\n" + "=" * 60)
    print("STEP 3: Insert Pakistani menu for YK Demo tenant")
    print("=" * 60)

    # Check if categories already exist for this tenant (safety: skip on re-run)
    result = await db.execute(
        select(Category).where(Category.tenant_id == demo_tenant_id).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        print("  Categories already exist for demo tenant. Skipping menu seeding.")
        print("  (This prevents duplicate inserts on re-run.)")
        return

    # --- Create modifier groups first ---
    mg_map: dict[str, ModifierGroup] = {}

    for gdef in PK_MODIFIER_GROUPS:
        result = await db.execute(
            select(ModifierGroup).where(
                ModifierGroup.name == gdef["name"],
                ModifierGroup.tenant_id == demo_tenant_id,
            )
        )
        group = result.scalar_one_or_none()
        if group is None:
            group = ModifierGroup(
                tenant_id=demo_tenant_id,
                name=gdef["name"],
                display_order=gdef["display_order"],
                required=gdef["required"],
                min_selections=gdef["min_selections"],
                max_selections=gdef["max_selections"],
                is_active=True,
            )
            db.add(group)
            await db.flush()
            print(f"  Created modifier group: {gdef['name']}")

            for mdef in gdef["modifiers"]:
                mod = Modifier(
                    tenant_id=demo_tenant_id,
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

        mg_map[gdef["name"]] = group

    # --- Create categories ---
    cat_map: dict[str, Category] = {}

    for cdef in PK_MENU_CATEGORIES:
        result = await db.execute(
            select(Category).where(
                Category.name == cdef["name"],
                Category.tenant_id == demo_tenant_id,
            )
        )
        cat = result.scalar_one_or_none()
        if cat is None:
            cat = Category(
                tenant_id=demo_tenant_id,
                name=cdef["name"],
                description=cdef["description"],
                display_order=cdef["display_order"],
                icon=cdef["icon"],
                is_active=True,
            )
            db.add(cat)
            await db.flush()
            print(f"  Created category: {cdef['name']}")
        else:
            print(f"  Category '{cdef['name']}' already exists, skipping.")
        cat_map[cdef["name"]] = cat

    # --- Create menu items + link modifier groups ---
    items_created = 0
    links_created = 0

    for cat_name, items_list in PK_MENU_ITEMS.items():
        cat = cat_map.get(cat_name)
        if cat is None:
            print(f"  WARNING: Category '{cat_name}' not found in map, skipping items.")
            continue

        # Category-level modifier groups
        category_mg_names = PK_CATEGORY_MODIFIER_LINKS.get(cat_name, [])

        for idef in items_list:
            result = await db.execute(
                select(MenuItem).where(
                    MenuItem.name == idef["name"],
                    MenuItem.category_id == cat.id,
                    MenuItem.tenant_id == demo_tenant_id,
                )
            )
            if result.scalar_one_or_none() is not None:
                continue

            item = MenuItem(
                tenant_id=demo_tenant_id,
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
            items_created += 1

            # Link category-level modifier groups
            for mg_name in category_mg_names:
                mg = mg_map.get(mg_name)
                if mg is None:
                    continue
                link = MenuItemModifierGroup(
                    tenant_id=demo_tenant_id,
                    menu_item_id=item.id,
                    modifier_group_id=mg.id,
                )
                db.add(link)
                links_created += 1

            # Drinks: add Drink Size for all except Cold Drink (Can) and Mineral Water
            if cat_name == "Drinks" and idef["name"] not in DRINKS_NO_SIZE:
                mg = mg_map.get("Drink Size")
                if mg is not None:
                    link = MenuItemModifierGroup(
                        tenant_id=demo_tenant_id,
                        menu_item_id=item.id,
                        modifier_group_id=mg.id,
                    )
                    db.add(link)
                    links_created += 1

            await db.flush()

    print(f"  Created {items_created} menu items.")
    print(f"  Created {links_created} modifier group links.")

    total_expected = sum(len(v) for v in PK_MENU_ITEMS.values())
    print(f"  Expected {total_expected} items total, created {items_created}.")
    print("  Step 3 complete.")


# ---------------------------------------------------------------------------
# STEP 4: Rename demo tenant to "YK Demo Restaurant"
# ---------------------------------------------------------------------------


async def step4_rename_demo_tenant(
    db: AsyncSession,
    demo_tenant_id: uuid.UUID,
) -> None:
    """Rename the demo tenant and update its receipt header."""
    print("\n" + "=" * 60)
    print("STEP 4: Rename demo tenant to 'YK Demo Restaurant'")
    print("=" * 60)

    await db.execute(
        update(Tenant)
        .where(Tenant.id == demo_tenant_id)
        .values(name="YK Demo Restaurant")
    )
    print("  Updated tenant name to 'YK Demo Restaurant'.")

    await db.execute(
        update(RestaurantConfig)
        .where(RestaurantConfig.tenant_id == demo_tenant_id)
        .values(receipt_header="YK Demo Restaurant")
    )
    print("  Updated receipt_header to 'YK Demo Restaurant'.")

    await db.flush()
    print("  Step 4 complete.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    """Run the full multi-tenant setup in a single transaction."""
    print("=" * 60)
    print("POS System -- Multi-Tenant Setup Script")
    print("=" * 60)
    print("Safety: NO data deletion. INSERT/UPDATE only. Single transaction.")

    async with async_session_factory() as db:
        try:
            # Find existing demo tenant
            result = await db.execute(
                select(Tenant).where(Tenant.slug == "demo-restaurant")
            )
            demo_tenant = result.scalar_one_or_none()

            if demo_tenant is None:
                print("\nFATAL: Demo tenant (slug='demo-restaurant') not found.")
                print("Run seed.py first: python -m app.scripts.seed")
                return

            demo_tenant_id = demo_tenant.id
            print(f"\nFound demo tenant: '{demo_tenant.name}' (id={demo_tenant_id})")

            # STEP 1: Create Cosa Nostra tenant
            cosa_tenant_id = await step1_create_cosa_nostra(db)

            # STEP 2: Move Italian menu to Cosa Nostra
            await step2_move_italian_menu(db, demo_tenant_id, cosa_tenant_id)

            # STEP 3: Insert Pakistani menu for YK Demo tenant
            await step3_insert_pakistani_menu(db, demo_tenant_id)

            # STEP 4: Rename demo tenant
            await step4_rename_demo_tenant(db, demo_tenant_id)

            # Commit everything in one transaction
            await db.commit()

            print("\n" + "=" * 60)
            print("ALL STEPS COMPLETED SUCCESSFULLY")
            print("=" * 60)
            print(f"  Cosa Nostra tenant ID: {cosa_tenant_id}")
            print(f"  YK Demo tenant ID:     {demo_tenant_id}")
            print(
                "  Cosa Nostra admin:     admin@cosanostra.com / "
                "cosanostra123 / PIN 4321"
            )
            print("=" * 60)

        except Exception:
            await db.rollback()
            print("\nFAILED -- transaction rolled back. No changes were made.")
            raise
        finally:
            await db.close()


if __name__ == "__main__":
    asyncio.run(main())
