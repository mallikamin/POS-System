"""Seed the Danny's Restaurant Faisalabad demo tenant.

Why this exists
----------------
Danny's (`_context/clients/dannys-faisalabad/`) is a prospective client, a
full-service restaurant on Canal Expressway, Faisalabad. Their interest is the
complete module, inventory and recipe management above all. This seed shows
that chain end to end on their own menu:

    supplier -> purchase order -> goods receipt -> raw stock
    -> sub-recipe production (karahi base, naan dough, marinades, sauces)
    -> menu recipe -> sale -> automatic stock deduction -> low-stock alert

Menu names and prices are taken from Danny's own published menu (Instagram
story, 2026-09). A representative subset, not the whole card. Recipes, ingredient
costs and quantities are reasonable Faisalabad placeholders, NOT Danny's real
recipes or costs. Food images are public Unsplash photos, not Danny's own.

Usage
-----
    docker exec pos-system-backend-1 python -m app.scripts.seed_dannys

Idempotent: safe to re-run, skips anything that already exists.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.floor import Floor, Table
from app.models.inventory import Ingredient, Recipe
from app.models.kitchen import KitchenStation
from app.models.location import Location, SalesChannel
from app.models.menu import Category, MenuItem
from app.models.order import Order, OrderItem
from app.models.payment import Payment, PaymentMethod
from app.models.procurement import PurchaseOrder, Supplier
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.models.user import Permission, Role, RolePermission, User
from app.schemas.inventory import RecipeCreate, RecipeItemCreate
from app.scripts.seed import ALL_PERMISSIONS, ROLE_DEFINITIONS
try:
    # Untracked on purpose (it carries Malik's own credentials), so it exists
    # only where it was copied. Without it the tenant is seeded minus that login.
    from app.scripts.system_admin import ensure_system_admin
except ImportError:  # pragma: no cover
    ensure_system_admin = None
from app.services import (
    ingredient_category_service,
    location_service,
    production_service,
    purchase_order_service,
    recipe_service,
    stock_service,
    supplier_service,
)
from app.utils.security import hash_password

TENANT_SLUG = "dannys"
TENANT_NAME = "Danny's Restaurant Faisalabad (Demo)"

# Punjab restaurant sales tax (PRA): 16% paid in cash, 5% paid by card. Prices
# are shown before tax, as Pakistani restaurant menus usually are. Assumption,
# not confirmed with Danny's.
TAX_BPS = 1600

USERS = [
    {"email": "admin@dannys-demo.com", "full_name": "Danny's Owner (Demo)",
     "password": "Dannys@2026", "pin": "2609", "role_name": "admin"},
    {"email": "cashier@dannys-demo.com", "full_name": "Danny's Cashier (Demo)",
     "password": "Cashier@2026", "pin": "3690", "role_name": "cashier"},
    {"email": "kitchen@dannys-demo.com", "full_name": "Danny's Kitchen (Demo)",
     "password": "Kitchen@2026", "pin": "4710", "role_name": "kitchen"},
]

LOCATION = {
    "name": "Danny's Canal Expressway",
    "code": "FSD",
    "location_type": "retail",
    "legal_name": "Danny's Restaurant",
    "address_line1": "Sitara Villas, Canal Expressway",
    "city": "Faisalabad",
    "country": "Pakistan",
    "invoice_format": "thermal_ticket",
    "invoice_prefix": "DN",
    "is_default": True,
    "notes": "Single site. The store room, kitchen and tandoor all draw on this stock.",
}

# Commission in basis points. Foodpanda's rate is a representative figure, not
# Danny's contract rate.
SALES_CHANNELS = [
    {"name": "Walk-in / Dine-in", "code": "direct", "commission_bps": 0, "fixed_fee_minor": 0,
     "notes": "Own customers, no commission."},
    {"name": "Phone Delivery", "code": "phone", "commission_bps": 0, "fixed_fee_minor": 0,
     "notes": "Call centre orders, own riders."},
    {"name": "Foodpanda", "code": "foodpanda", "commission_bps": 2500, "fixed_fee_minor": 0,
     "notes": "Representative aggregator rate. Confirm the real contract rate."},
]

FLOORS = [
    {"name": "Main Hall", "tables": 10, "capacity": 4},
    {"name": "Outdoor Terrace", "tables": 6, "capacity": 6},
]

# ---------------------------------------------------------------------------
# IMAGES (public Unsplash photos, generic, not Danny's own). Each one was looked
# at, not just fetched: None where no photo that shows the actual dish was found,
# which renders the plain placeholder rather than a wrong picture.
# ---------------------------------------------------------------------------

def _u(photo: str) -> str:
    return f"https://images.unsplash.com/{photo}?w=400&h=300&fit=crop"


IMG: dict[str, str | None] = {
    "soup": _u("photo-1547592166-23ac45744acd"),
    "salad": _u("photo-1550304943-4f24f54ddde9"),
    "fries": _u("photo-1573080496219-bb080dd4f877"),
    "nuggets": _u("photo-1562967914-608f82629710"),
    "fish_chips": _u("photo-1562967914-608f82629710"),
    "prawn": _u("photo-1565680018434-b513d5e5fd47"),
    "wings": _u("photo-1567620832903-9fc6debc209f"),
    "pasta": _u("photo-1621996346565-e3dbc646d9a9"),
    "pasta2": _u("photo-1473093295043-cdd812d0e601"),
    "chicken_steak": _u("photo-1532550907401-a500c9a57435"),
    "fish": _u("photo-1519708227418-c8fd9a32b7a2"),
    "burger": _u("photo-1568901346375-23c9450c58cd"),
    "steak": _u("photo-1600891964092-4316c288032e"),
    "karahi": _u("photo-1631452180519-c014fe946bc7"),
    "mutton_karahi": _u("photo-1545247181-516773cae754"),
    "handi": _u("photo-1603894584373-5ac82b2ae398"),
    "prawn_masala": _u("photo-1631452180519-c014fe946bc7"),
    "tikka": _u("photo-1599487488170-d11ec9c172f0"),
    "malai": _u("photo-1599487488170-d11ec9c172f0"),
    "reshmi": _u("photo-1567188040759-fb8a883dc6d8"),
    "seekh": _u("photo-1603496987351-f84a3ba5ec85"),
    "chops": _u("photo-1600891964092-4316c288032e"),
    "grill": _u("photo-1599487488170-d11ec9c172f0"),
    "chinese": _u("photo-1525755662778-989d0524087e"),
    "noodles": _u("photo-1569718212165-3a8278d5f624"),
    "fried_rice": _u("photo-1603133872878-684f208fb84b"),
    "roti": None,
    "naan": None,
    "garlic_naan": None,
    "cheese_naan": None,
    "lava": _u("photo-1624353365286-3f8d62daad51"),
    "tiramisu": _u("photo-1571877227200-a0d98ea607e9"),
    "cheesecake": _u("photo-1533134242443-d4fd215305ad"),
    "brownie": _u("photo-1606313564200-e75d5e30476c"),
    "kunafa": None,
    "frappe": _u("photo-1461023058943-07fcbe16d735"),
    "cold_coffee": _u("photo-1517701604599-bb29b565090c"),
    "mocktail": _u("photo-1551024709-8f23befc6f87"),
    "pina": _u("photo-1513558161293-cdaf765ed2fd"),
    "latte": _u("photo-1541167760496-1628856ab772"),
    "cappuccino": _u("photo-1572442388796-11668a67e53d"),
    "tea": _u("photo-1571934811356-5cc061b6821f"),
    "shake": _u("photo-1572490122747-3968b75cc699"),
    "soft_drink": _u("photo-1629203851122-3726ecdf080e"),
    "water": _u("photo-1548839140-29a749e1cf4d"),
}

# ---------------------------------------------------------------------------
# MENU. name -> (category, price in PKR, image key, description)
# Prices are Danny's own, converted to paisa below.
# ---------------------------------------------------------------------------

CATEGORIES = [
    "Soups", "Salads", "Appetizers", "Pastas", "Main Course", "Burgers & Wraps",
    "Beef Steaks", "Pakistani", "BBQ", "Chinese", "Tandoor", "Desserts",
    "Coffee & Frappe", "Mocktails & Shakes", "Hot Beverages", "Soft Drinks",
]

MENU_ITEMS: dict[str, tuple[str, int, str, str]] = {
    "Hot & Sour Soup": ("Soups", 499, "soup", "Classic hot and sour, chicken"),
    "Chicken Corn Soup": ("Soups", 499, "soup", "Creamy chicken and sweetcorn"),
    "Thai Clear Soup": ("Soups", 499, "soup", "Light lemongrass broth"),
    "Caesar Salad": ("Salads", 1049, "salad", "Romaine, parmesan, croutons, grilled chicken"),
    "Fries": ("Appetizers", 549, "fries", "Garlic mayo, honey mustard or cheese jalapeno"),
    "Chicken Nuggets (6 Pcs)": ("Appetizers", 599, "nuggets", "Crumbed chicken nuggets"),
    "Fish n Chips": ("Appetizers", 1049, "fish_chips", "Battered fish, fries, tartare"),
    "Prawn Tempura (5 Pcs)": ("Appetizers", 1699, "prawn", "Light tempura batter"),
    "Peri Peri Wings": ("Appetizers", 1299, "wings", "Flame-grilled peri peri wings"),
    "Honey Chilli Wings": ("Appetizers", 999, "wings", "Sticky honey chilli glaze"),
    "Fettuccine Pasta": ("Pastas", 1359, "pasta", "Creamy white sauce, grilled chicken"),
    "Danny's Special Pasta": ("Pastas", 2199, "pasta2", "The house signature pasta"),
    "Chicken Steak (Black Pepper)": ("Main Course", 1649, "chicken_steak",
                                     "Grilled chicken, black pepper sauce, fries"),
    "Cordon Bleu": ("Main Course", 1679, "chicken_steak", "Chicken, cheese, crumbed"),
    "Lemon Butter Fish Steak": ("Main Course", 2099, "fish", "Pan-seared fish, lemon butter"),
    "Danny's Smash": ("Burgers & Wraps", 1199, "burger", "Double smashed beef, cheese, garlic mayo"),
    "Blue Cheese Beef": ("Burgers & Wraps", 1199, "burger", "Beef patty, blue cheese"),
    "Grilled Chicken Burger": ("Burgers & Wraps", 699, "burger", "Grilled chicken fillet, garlic mayo"),
    "Rib-eye Steak (Local)": ("Beef Steaks", 3299, "steak", "Local rib-eye cut"),
    "Tenderloin Steak (Local)": ("Beef Steaks", 3299, "steak", "Local tenderloin cut"),
    "Tenderloin Steak (Imported)": ("Beef Steaks", 5699, "steak", "Imported tenderloin cut"),
    "Mutton Karahi (Half)": ("Pakistani", 2549, "mutton_karahi", "Black, white or red"),
    "Mutton Karahi (Full)": ("Pakistani", 4199, "mutton_karahi", "Black, white or red"),
    "Chicken Karahi (Half)": ("Pakistani", 1889, "karahi", "Black, white or red"),
    "Chicken Karahi (Full)": ("Pakistani", 2849, "karahi", "Black, white or red"),
    "Shahi Handi (Half)": ("Pakistani", 1549, "handi", "Boneless chicken in a creamy handi"),
    "Shahi Handi (Full)": ("Pakistani", 2449, "handi", "Boneless chicken in a creamy handi"),
    "Prawn Masala": ("Pakistani", 2799, "prawn_masala", "Prawns in a spiced masala"),
    "Chicken Tikkah Piece": ("BBQ", 499, "tikka", "Quarter chicken, charcoal grilled"),
    "Malai Boti (8 Pcs)": ("BBQ", 1349, "malai", "Creamy boneless boti"),
    "Reshmi Kabab (4 Pcs)": ("BBQ", 1199, "reshmi", "Soft chicken kabab"),
    "Chicken Behari Boti (8 Pcs)": ("BBQ", 1299, "seekh", "Behari-spiced boneless chicken"),
    "Mutton Chops (6 Chops)": ("BBQ", 3699, "chops", "Marinated mutton chops"),
    "Chicken Sheesh Tauq": ("BBQ", 1359, "grill", "Lebanese-style chicken skewers"),
    "Chicken Manchurian": ("Chinese", 1599, "chinese", "Chicken in tangy manchurian sauce"),
    "Kung Pao Chicken": ("Chinese", 1699, "chinese", "Chicken, peanuts, dry chillies"),
    "Beef Chilli Dry": ("Chinese", 1949, "chinese", "Wok-fried beef, capsicum, chilli"),
    "Chicken Chowmein": ("Chinese", 1249, "noodles", "Stir-fried noodles"),
    "Egg Fried Rice": ("Chinese", 1049, "fried_rice", "Wok-fried rice with egg"),
    "Roti": ("Tandoor", 69, "roti", "Tandoori roti"),
    "Roghni Naan": ("Tandoor", 139, "naan", "Sesame-topped naan"),
    "Garlic Naan": ("Tandoor", 169, "garlic_naan", "Butter and garlic"),
    "Cheese Naan": ("Tandoor", 549, "cheese_naan", "Stuffed with mozzarella"),
    "Molten Lava": ("Desserts", 599, "lava", "Warm chocolate lava cake"),
    "Tiramisu": ("Desserts", 699, "tiramisu", "Coffee-soaked, mascarpone"),
    "Cheese Cake": ("Desserts", 699, "cheesecake", "Baked cheesecake"),
    "Walnut Brownie": ("Desserts", 799, "brownie", "Warm brownie, walnuts"),
    "Kunafa": ("Desserts", 799, "kunafa", "Cheese kunafa, syrup"),
    "Caramel Frappe": ("Coffee & Frappe", 899, "frappe", "Blended iced caramel coffee"),
    "Classic Cold Coffee": ("Coffee & Frappe", 799, "cold_coffee", "Over ice"),
    "Blue Lightening": ("Mocktails & Shakes", 599, "mocktail", "Blue curacao mocktail"),
    "Pina Colada": ("Mocktails & Shakes", 499, "pina", "Blue ocean or classic"),
    "Oreo Pleasure": ("Mocktails & Shakes", 899, "shake", "Oreo milkshake"),
    "Lotus Shake": ("Mocktails & Shakes", 899, "shake", "Lotus biscoff milkshake"),
    "Cappuccino": ("Hot Beverages", 799, "cappuccino", "Double shot, steamed milk"),
    "Latte": ("Hot Beverages", 899, "latte", "Caramel, hazelnut or vanilla"),
    "Tea": ("Hot Beverages", 249, "tea", "Pot of tea"),
    "Doodh Patti": ("Hot Beverages", 499, "tea", "Milk tea, desi style"),
    "Soft Drink": ("Soft Drinks", 189, "soft_drink", "Can"),
    "Water (Small)": ("Soft Drinks", 90, "water", "Mineral water"),
}

# ---------------------------------------------------------------------------
# RAW INGREDIENTS (purchased). cost_per_unit in paisa per stocking unit.
# ---------------------------------------------------------------------------

def _ing(name, category, unit, cost_pkr, stock, reorder_point, reorder_qty):
    return {
        "name": name, "category": category, "unit": unit,
        "cost_per_unit": Decimal(str(cost_pkr)) * 100,
        "opening": Decimal(str(stock)),
        "reorder_point": Decimal(str(reorder_point)),
        "reorder_quantity": Decimal(str(reorder_qty)),
    }


RAW_INGREDIENTS = [
    _ing("Chicken (Karahi Cut)", "Meat & Poultry", "kg", 700, 60, 15, 50),
    _ing("Boneless Chicken", "Meat & Poultry", "kg", 1100, 45, 12, 40),
    _ing("Mutton", "Meat & Poultry", "kg", 2400, 30, 8, 25),
    _ing("Beef Mince", "Meat & Poultry", "kg", 1400, 20, 5, 15),
    _ing("Tomato", "Vegetables", "kg", 180, 40, 10, 30),
    _ing("Onion", "Vegetables", "kg", 150, 40, 10, 30),
    _ing("Ginger", "Vegetables", "kg", 600, 6, 2, 5),
    _ing("Garlic", "Vegetables", "kg", 550, 6, 2, 5),
    _ing("Green Chilli", "Vegetables", "kg", 250, 5, 1, 4),
    _ing("Capsicum", "Vegetables", "kg", 350, 8, 2, 6),
    _ing("Lettuce", "Vegetables", "kg", 400, 5, 1, 4),
    _ing("Lemon", "Vegetables", "kg", 400, 5, 1, 4),
    _ing("Yogurt", "Dairy", "kg", 260, 30, 8, 25),
    _ing("Fresh Cream", "Dairy", "L", 900, 15, 4, 12),
    _ing("Butter", "Dairy", "kg", 2500, 12, 3, 10),
    _ing("Milk", "Dairy", "L", 220, 60, 15, 50),
    # Seeded BELOW its reorder point so the low-stock alert has a real row.
    _ing("Mozzarella Cheese", "Dairy", "kg", 1800, 3, 5, 10),
    _ing("Cheddar Slices", "Dairy", "kg", 2000, 5, 1, 4),
    _ing("Cooking Oil", "Dry Store", "L", 550, 60, 15, 50),
    _ing("Salt", "Dry Store", "kg", 60, 10, 2, 10),
    _ing("Black Pepper", "Dry Store", "kg", 3000, 2, 0.5, 2),
    _ing("Karahi Spice Mix", "Dry Store", "kg", 1800, 5, 1, 4),
    _ing("Tikka Spice Mix", "Dry Store", "kg", 1800, 5, 1, 4),
    _ing("Maida (Flour)", "Dry Store", "kg", 160, 80, 20, 50),
    _ing("Yeast", "Dry Store", "kg", 1500, 2, 0.5, 2),
    _ing("Sugar", "Dry Store", "kg", 170, 25, 5, 20),
    _ing("Basmati Rice", "Dry Store", "kg", 380, 40, 10, 30),
    _ing("Cornflour", "Dry Store", "kg", 300, 10, 2, 8),
    _ing("Soy Sauce", "Dry Store", "L", 600, 8, 2, 6),
    _ing("Chilli Sauce", "Dry Store", "L", 500, 8, 2, 6),
    _ing("Mayonnaise", "Dry Store", "kg", 800, 15, 4, 12),
    _ing("Fettuccine Pasta", "Dry Store", "kg", 1200, 10, 3, 8),
    _ing("Eggs", "Dry Store", "pcs", 35, 180, 60, 180),
    _ing("Burger Buns", "Bakery", "pcs", 60, 80, 24, 80),
    _ing("Frozen Fries", "Frozen", "kg", 650, 30, 8, 25),
    _ing("Vanilla Ice Cream", "Frozen", "L", 900, 12, 3, 10),
    _ing("Espresso Beans", "Beverages", "kg", 8000, 4, 1, 3),
    _ing("Tea Leaves", "Beverages", "kg", 1800, 4, 1, 3),
    _ing("Oreo Biscuits", "Beverages", "kg", 1500, 4, 1, 3),
    _ing("Soft Drink Can", "Beverages", "pcs", 90, 240, 48, 240),
    _ing("Mineral Water (Small)", "Beverages", "pcs", 35, 240, 48, 240),
]

# ---------------------------------------------------------------------------
# SUB-RECIPES (made in-house, then used by menu recipes)
#   items -> [(ingredient, quantity, unit, waste %)]
# ---------------------------------------------------------------------------

SUB_RECIPES = [
    {
        "produces": "Karahi Masala Base", "unit": "kg", "yield_qty": Decimal("5"),
        "prep": 20, "cook": 40, "batches": Decimal("4"),
        "instructions": "Cook down tomatoes with ginger, garlic and green chilli in oil "
                        "until the oil separates. Finish with karahi spice and salt.",
        "items": [
            ("Tomato", Decimal("4"), "kg", Decimal("5")),
            ("Ginger", Decimal("0.3"), "kg", Decimal("10")),
            ("Garlic", Decimal("0.3"), "kg", Decimal("10")),
            ("Green Chilli", Decimal("0.2"), "kg", Decimal("5")),
            ("Cooking Oil", Decimal("1"), "L", Decimal("0")),
            ("Karahi Spice Mix", Decimal("0.15"), "kg", Decimal("0")),
            ("Salt", Decimal("0.08"), "kg", Decimal("0")),
        ],
    },
    {
        "produces": "Naan Dough", "unit": "kg", "yield_qty": Decimal("10"),
        "prep": 20, "cook": 0, "batches": Decimal("2"),
        "instructions": "Knead maida with yogurt, milk, yeast, sugar and salt. Rest 2 hours.",
        "items": [
            ("Maida (Flour)", Decimal("6"), "kg", Decimal("2")),
            ("Yogurt", Decimal("0.8"), "kg", Decimal("0")),
            ("Milk", Decimal("1"), "L", Decimal("0")),
            ("Yeast", Decimal("0.06"), "kg", Decimal("0")),
            ("Sugar", Decimal("0.15"), "kg", Decimal("0")),
            ("Salt", Decimal("0.1"), "kg", Decimal("0")),
        ],
    },
    {
        "produces": "Tikka Marinade", "unit": "kg", "yield_qty": Decimal("3"),
        "prep": 15, "cook": 0, "batches": Decimal("2"),
        "instructions": "Whisk yogurt with ginger, garlic, tikka spice, lemon, oil and salt.",
        "items": [
            ("Yogurt", Decimal("2"), "kg", Decimal("0")),
            ("Ginger", Decimal("0.15"), "kg", Decimal("10")),
            ("Garlic", Decimal("0.15"), "kg", Decimal("10")),
            ("Tikka Spice Mix", Decimal("0.25"), "kg", Decimal("0")),
            ("Lemon", Decimal("0.2"), "kg", Decimal("30")),
            ("Cooking Oil", Decimal("0.2"), "L", Decimal("0")),
            ("Salt", Decimal("0.05"), "kg", Decimal("0")),
        ],
    },
    {
        "produces": "Malai Marinade", "unit": "kg", "yield_qty": Decimal("2"),
        "prep": 15, "cook": 0, "batches": Decimal("2"),
        "instructions": "Blend cream, cheddar, yogurt, ginger, garlic and green chilli smooth.",
        "items": [
            ("Fresh Cream", Decimal("1"), "L", Decimal("0")),
            ("Cheddar Slices", Decimal("0.3"), "kg", Decimal("0")),
            ("Yogurt", Decimal("0.5"), "kg", Decimal("0")),
            ("Ginger", Decimal("0.05"), "kg", Decimal("10")),
            ("Garlic", Decimal("0.05"), "kg", Decimal("10")),
            ("Green Chilli", Decimal("0.05"), "kg", Decimal("5")),
            ("Salt", Decimal("0.03"), "kg", Decimal("0")),
        ],
    },
    {
        "produces": "Garlic Mayo", "unit": "kg", "yield_qty": Decimal("3"),
        "prep": 10, "cook": 0, "batches": Decimal("1"),
        "instructions": "Fold minced garlic, lemon and salt through mayonnaise. Chill.",
        "items": [
            ("Mayonnaise", Decimal("2.7"), "kg", Decimal("0")),
            ("Garlic", Decimal("0.2"), "kg", Decimal("10")),
            ("Lemon", Decimal("0.1"), "kg", Decimal("30")),
            ("Salt", Decimal("0.02"), "kg", Decimal("0")),
        ],
    },
    {
        "produces": "White Sauce", "unit": "kg", "yield_qty": Decimal("4"),
        "prep": 5, "cook": 15, "batches": Decimal("1"),
        "instructions": "Butter and flour roux, whisk in milk, melt in mozzarella, season.",
        "items": [
            ("Butter", Decimal("0.25"), "kg", Decimal("0")),
            ("Maida (Flour)", Decimal("0.25"), "kg", Decimal("0")),
            ("Milk", Decimal("3"), "L", Decimal("0")),
            ("Mozzarella Cheese", Decimal("0.5"), "kg", Decimal("0")),
            ("Salt", Decimal("0.02"), "kg", Decimal("0")),
            ("Black Pepper", Decimal("0.01"), "kg", Decimal("0")),
        ],
    },
    {
        "produces": "Black Pepper Sauce", "unit": "kg", "yield_qty": Decimal("2"),
        "prep": 5, "cook": 15, "batches": Decimal("1"),
        "instructions": "Sweat onion in butter, add crushed pepper, reduce with cream.",
        "items": [
            ("Butter", Decimal("0.15"), "kg", Decimal("0")),
            ("Onion", Decimal("0.3"), "kg", Decimal("10")),
            ("Fresh Cream", Decimal("1.5"), "L", Decimal("0")),
            ("Black Pepper", Decimal("0.05"), "kg", Decimal("0")),
            ("Salt", Decimal("0.02"), "kg", Decimal("0")),
        ],
    },
]

# ---------------------------------------------------------------------------
# MENU RECIPES. Per one serving, consume raw AND in-house ingredients.
# ---------------------------------------------------------------------------

def _karahi(meat: str, meat_kg: str, base_kg: str, butter_kg: str, cream_l: str) -> list:
    return [
        (meat, Decimal(meat_kg), "kg", Decimal("0")),
        ("Karahi Masala Base", Decimal(base_kg), "kg", Decimal("0")),
        ("Butter", Decimal(butter_kg), "kg", Decimal("0")),
        ("Fresh Cream", Decimal(cream_l), "L", Decimal("0")),
        ("Ginger", Decimal("0.02"), "kg", Decimal("10")),
        ("Green Chilli", Decimal("0.02"), "kg", Decimal("5")),
    ]


FINAL_RECIPES = {
    "Chicken Karahi (Full)": ("Cook chicken in the karahi base on high flame, finish with "
                              "butter, cream, julienne ginger and green chilli.",
                              _karahi("Chicken (Karahi Cut)", "1", "0.35", "0.05", "0.05")),
    "Chicken Karahi (Half)": ("As the full karahi, half portion.",
                              _karahi("Chicken (Karahi Cut)", "0.5", "0.2", "0.03", "0.03")),
    "Mutton Karahi (Full)": ("Cook mutton low and slow in the karahi base, finish on high flame.",
                             _karahi("Mutton", "0.75", "0.35", "0.06", "0.05")),
    "Mutton Karahi (Half)": ("As the full karahi, half portion.",
                             _karahi("Mutton", "0.4", "0.2", "0.03", "0.03")),
    "Shahi Handi (Full)": ("Boneless chicken in karahi base, finished with cream and butter.", [
        ("Boneless Chicken", Decimal("0.6"), "kg", Decimal("0")),
        ("Karahi Masala Base", Decimal("0.25"), "kg", Decimal("0")),
        ("Fresh Cream", Decimal("0.15"), "L", Decimal("0")),
        ("Butter", Decimal("0.04"), "kg", Decimal("0")),
    ]),
    "Chicken Tikkah Piece": ("Marinate overnight, grill over charcoal.", [
        ("Chicken (Karahi Cut)", Decimal("0.25"), "kg", Decimal("5")),
        ("Tikka Marinade", Decimal("0.06"), "kg", Decimal("0")),
    ]),
    "Malai Boti (8 Pcs)": ("Marinate boneless chicken in malai marinade, grill on skewers.", [
        ("Boneless Chicken", Decimal("0.35"), "kg", Decimal("5")),
        ("Malai Marinade", Decimal("0.1"), "kg", Decimal("0")),
    ]),
    "Reshmi Kabab (4 Pcs)": ("Mince boneless chicken with malai marinade, shape, grill.", [
        ("Boneless Chicken", Decimal("0.3"), "kg", Decimal("5")),
        ("Malai Marinade", Decimal("0.08"), "kg", Decimal("0")),
        ("Onion", Decimal("0.05"), "kg", Decimal("10")),
    ]),
    "Danny's Smash": ("Two 110g balls smashed on the flat top, cheese, bun, garlic mayo.", [
        ("Beef Mince", Decimal("0.2"), "kg", Decimal("3")),
        ("Cheddar Slices", Decimal("0.04"), "kg", Decimal("0")),
        ("Burger Buns", Decimal("1"), "pcs", Decimal("0")),
        ("Garlic Mayo", Decimal("0.04"), "kg", Decimal("0")),
        ("Lettuce", Decimal("0.02"), "kg", Decimal("10")),
        ("Frozen Fries", Decimal("0.15"), "kg", Decimal("0")),
    ]),
    "Grilled Chicken Burger": ("Grilled marinated fillet, lettuce, garlic mayo, fries.", [
        ("Boneless Chicken", Decimal("0.15"), "kg", Decimal("5")),
        ("Tikka Marinade", Decimal("0.02"), "kg", Decimal("0")),
        ("Burger Buns", Decimal("1"), "pcs", Decimal("0")),
        ("Garlic Mayo", Decimal("0.04"), "kg", Decimal("0")),
        ("Lettuce", Decimal("0.02"), "kg", Decimal("10")),
        ("Frozen Fries", Decimal("0.15"), "kg", Decimal("0")),
    ]),
    "Fries": ("Double fry, season, serve with garlic mayo.", [
        ("Frozen Fries", Decimal("0.25"), "kg", Decimal("0")),
        ("Cooking Oil", Decimal("0.03"), "L", Decimal("0")),
        ("Garlic Mayo", Decimal("0.04"), "kg", Decimal("0")),
    ]),
    "Chicken Steak (Black Pepper)": ("Grill the fillet, sauce on top, fries on the side.", [
        ("Boneless Chicken", Decimal("0.25"), "kg", Decimal("5")),
        ("Black Pepper Sauce", Decimal("0.1"), "kg", Decimal("0")),
        ("Frozen Fries", Decimal("0.15"), "kg", Decimal("0")),
        ("Butter", Decimal("0.02"), "kg", Decimal("0")),
    ]),
    "Fettuccine Pasta": ("Boil pasta, toss in white sauce with grilled chicken strips.", [
        ("Fettuccine Pasta", Decimal("0.15"), "kg", Decimal("0")),
        ("White Sauce", Decimal("0.2"), "kg", Decimal("0")),
        ("Boneless Chicken", Decimal("0.1"), "kg", Decimal("5")),
    ]),
    "Chicken Manchurian": ("Crisp cornflour-coated chicken, wok-tossed in manchurian sauce.", [
        ("Boneless Chicken", Decimal("0.3"), "kg", Decimal("5")),
        ("Cornflour", Decimal("0.05"), "kg", Decimal("0")),
        ("Eggs", Decimal("1"), "pcs", Decimal("0")),
        ("Capsicum", Decimal("0.05"), "kg", Decimal("10")),
        ("Soy Sauce", Decimal("0.03"), "L", Decimal("0")),
        ("Chilli Sauce", Decimal("0.05"), "L", Decimal("0")),
        ("Cooking Oil", Decimal("0.05"), "L", Decimal("0")),
    ]),
    "Egg Fried Rice": ("Wok-fry steamed rice with egg, soy and spring onion.", [
        ("Basmati Rice", Decimal("0.2"), "kg", Decimal("0")),
        ("Eggs", Decimal("2"), "pcs", Decimal("0")),
        ("Soy Sauce", Decimal("0.02"), "L", Decimal("0")),
        ("Cooking Oil", Decimal("0.03"), "L", Decimal("0")),
    ]),
    "Roti": ("Hand-stretched, baked on the tandoor wall.", [
        ("Naan Dough", Decimal("0.09"), "kg", Decimal("0")),
    ]),
    "Roghni Naan": ("Brush with milk and egg wash, sesame, bake.", [
        ("Naan Dough", Decimal("0.13"), "kg", Decimal("0")),
        ("Butter", Decimal("0.01"), "kg", Decimal("0")),
    ]),
    "Garlic Naan": ("Garlic and butter on top, bake.", [
        ("Naan Dough", Decimal("0.13"), "kg", Decimal("0")),
        ("Garlic", Decimal("0.01"), "kg", Decimal("10")),
        ("Butter", Decimal("0.015"), "kg", Decimal("0")),
    ]),
    "Cheese Naan": ("Stuff with mozzarella, seal, bake, butter.", [
        ("Naan Dough", Decimal("0.15"), "kg", Decimal("0")),
        ("Mozzarella Cheese", Decimal("0.08"), "kg", Decimal("0")),
        ("Butter", Decimal("0.015"), "kg", Decimal("0")),
    ]),
    "Cappuccino": ("Double shot, steamed milk, foam.", [
        ("Espresso Beans", Decimal("0.018"), "kg", Decimal("0")),
        ("Milk", Decimal("0.18"), "L", Decimal("0")),
    ]),
    "Latte": ("Double shot, flavoured syrup, steamed milk.", [
        ("Espresso Beans", Decimal("0.018"), "kg", Decimal("0")),
        ("Milk", Decimal("0.22"), "L", Decimal("0")),
        ("Sugar", Decimal("0.015"), "kg", Decimal("0")),
    ]),
    "Classic Cold Coffee": ("Espresso, milk, ice cream, over ice.", [
        ("Espresso Beans", Decimal("0.018"), "kg", Decimal("0")),
        ("Milk", Decimal("0.2"), "L", Decimal("0")),
        ("Vanilla Ice Cream", Decimal("0.06"), "L", Decimal("0")),
        ("Sugar", Decimal("0.02"), "kg", Decimal("0")),
    ]),
    "Doodh Patti": ("Tea leaves boiled in milk with sugar.", [
        ("Tea Leaves", Decimal("0.008"), "kg", Decimal("0")),
        ("Milk", Decimal("0.2"), "L", Decimal("0")),
        ("Sugar", Decimal("0.015"), "kg", Decimal("0")),
    ]),
    "Tea": ("Pot of tea, milk on the side.", [
        ("Tea Leaves", Decimal("0.006"), "kg", Decimal("0")),
        ("Milk", Decimal("0.05"), "L", Decimal("0")),
    ]),
    "Oreo Pleasure": ("Blend ice cream, milk and Oreo.", [
        ("Vanilla Ice Cream", Decimal("0.15"), "L", Decimal("0")),
        ("Milk", Decimal("0.15"), "L", Decimal("0")),
        ("Oreo Biscuits", Decimal("0.05"), "kg", Decimal("0")),
    ]),
    "Soft Drink": ("Resale item: one can.", [
        ("Soft Drink Can", Decimal("1"), "pcs", Decimal("0")),
    ]),
    "Water (Small)": ("Resale item: one bottle.", [
        ("Mineral Water (Small)", Decimal("1"), "pcs", Decimal("0")),
    ]),
}

# ---------------------------------------------------------------------------
# SUPPLIERS AND PURCHASING. Generic names, not real Faisalabad businesses.
# ---------------------------------------------------------------------------

SUPPLIERS = [
    {"code": "POULTRY", "name": "Faisal Poultry Traders (Demo)", "contact_name": "Supply desk",
     "phone": "+92 300 0000001", "city": "Faisalabad", "country": "Pakistan",
     "payment_terms": "Weekly", "lead_time_days": 1,
     "items": ["Chicken (Karahi Cut)", "Boneless Chicken", "Eggs"]},
    {"code": "MEAT", "name": "Canal Meat Supply (Demo)", "contact_name": "Supply desk",
     "phone": "+92 300 0000002", "city": "Faisalabad", "country": "Pakistan",
     "payment_terms": "Weekly", "lead_time_days": 1,
     "items": ["Mutton", "Beef Mince"]},
    {"code": "SABZI", "name": "Sabzi Mandi Wholesale (Demo)", "contact_name": "Supply desk",
     "phone": "+92 300 0000003", "city": "Faisalabad", "country": "Pakistan",
     "payment_terms": "Cash on delivery", "lead_time_days": 0,
     "items": ["Tomato", "Onion", "Ginger", "Garlic", "Green Chilli", "Capsicum",
               "Lettuce", "Lemon"]},
    {"code": "DAIRY", "name": "Lyallpur Dairy & Dry Store (Demo)", "contact_name": "Supply desk",
     "phone": "+92 300 0000004", "city": "Faisalabad", "country": "Pakistan",
     "payment_terms": "15 days", "lead_time_days": 2,
     "items": ["Yogurt", "Fresh Cream", "Butter", "Milk", "Mozzarella Cheese",
               "Cheddar Slices", "Cooking Oil", "Maida (Flour)", "Basmati Rice",
               "Sugar", "Mayonnaise", "Frozen Fries"]},
]


async def get_or_create_tenant(db: AsyncSession) -> Tenant:
    tenant = (await db.execute(select(Tenant).where(Tenant.slug == TENANT_SLUG))).scalar_one_or_none()
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
    existing = (
        await db.execute(select(RestaurantConfig).where(RestaurantConfig.tenant_id == tenant.id))
    ).scalar_one_or_none()
    if existing is not None:
        print("  Config already exists, skipping.")
        return
    db.add(RestaurantConfig(
        tenant_id=tenant.id,
        payment_flow="order_first",
        currency="PKR",
        timezone="Asia/Karachi",
        tax_inclusive=False,
        default_tax_rate=TAX_BPS,
        cash_tax_rate_bps=1600,
        card_tax_rate_bps=500,
        receipt_header="Danny's Restaurant\nSitara Villas, Canal Expressway, Faisalabad",
        receipt_footer="Thank you for dining at Danny's!",
    ))
    await db.flush()
    print("  Created restaurant config (PKR, PRA 16% cash / 5% card).")


async def get_or_create_users(db: AsyncSession, tenant: Tenant) -> User:
    # Permission.code is globally unique, not per tenant: reuse by code.
    perm_map: dict[str, Permission] = {}
    for code, description in ALL_PERMISSIONS:
        perm = (await db.execute(select(Permission).where(Permission.code == code))).scalar_one_or_none()
        if perm is None:
            perm = Permission(tenant_id=tenant.id, code=code, description=description)
            db.add(perm)
            await db.flush()
        perm_map[code] = perm

    role_map: dict[str, Role] = {}
    for role_name, role_def in ROLE_DEFINITIONS.items():
        role = (
            await db.execute(select(Role).where(Role.name == role_name, Role.tenant_id == tenant.id))
        ).scalar_one_or_none()
        if role is None:
            role = Role(tenant_id=tenant.id, name=role_name, description=role_def["description"], is_active=True)
            db.add(role)
            await db.flush()
        have = {
            rp.permission_id
            for rp in (await db.execute(select(RolePermission).where(RolePermission.role_id == role.id))).scalars()
        }
        for perm_code in role_def["permissions"]:
            if perm_map[perm_code].id not in have:
                db.add(RolePermission(tenant_id=tenant.id, role_id=role.id, permission_id=perm_map[perm_code].id))
        await db.flush()
        role_map[role_name] = role

    admin: User | None = None
    for spec in USERS:
        user = (
            await db.execute(select(User).where(User.email == spec["email"], User.tenant_id == tenant.id))
        ).scalar_one_or_none()
        if user is None:
            user = User(
                tenant_id=tenant.id,
                email=spec["email"],
                full_name=spec["full_name"],
                hashed_password=hash_password(spec["password"]),
                pin_code=hash_password(spec["pin"]),
                role_id=role_map[spec["role_name"]].id,
                is_active=True,
            )
            db.add(user)
            await db.flush()
            print(f"  Created user '{spec['email']}' ({spec['role_name']}).")
        if spec["role_name"] == "admin":
            admin = user

    if ensure_system_admin is not None:
        await ensure_system_admin(db, tenant, role_map["admin"])
    else:
        print("  ! system_admin.py not present: universal Malik login NOT created on this tenant.")
    assert admin is not None
    return admin


async def get_or_create_menu(db: AsyncSession, tenant: Tenant) -> dict[str, MenuItem]:
    cat_map: dict[str, Category] = {}
    for order, name in enumerate(CATEGORIES):
        cat = (
            await db.execute(select(Category).where(Category.name == name, Category.tenant_id == tenant.id))
        ).scalar_one_or_none()
        if cat is None:
            cat = Category(tenant_id=tenant.id, name=name, display_order=order, is_active=True)
            db.add(cat)
            await db.flush()
        cat_map[name] = cat

    existing = {
        mi.name: mi
        for mi in (await db.execute(select(MenuItem).where(MenuItem.tenant_id == tenant.id))).scalars()
    }
    for order, (name, (cat_name, price_pkr, img, description)) in enumerate(MENU_ITEMS.items()):
        if name in existing:
            continue
        item = MenuItem(
            tenant_id=tenant.id,
            category_id=cat_map[cat_name].id,
            name=name,
            description=description,
            price=price_pkr * 100,
            image_url=IMG[img],
            display_order=order,
            is_available=True,
        )
        db.add(item)
        existing[name] = item
    await db.flush()
    print(f"  Menu: {len(CATEGORIES)} categories, {len(MENU_ITEMS)} items.")
    return existing


async def get_or_create_raw_ingredients(db: AsyncSession, tenant: Tenant) -> dict[str, Ingredient]:
    ing_map: dict[str, Ingredient] = {}
    for spec in RAW_INGREDIENTS:
        await ingredient_category_service.ensure_category(db, tenant.id, spec["category"])
        ing = (
            await db.execute(
                select(Ingredient).where(Ingredient.name == spec["name"], Ingredient.tenant_id == tenant.id)
            )
        ).scalar_one_or_none()
        if ing is None:
            ing = Ingredient(
                tenant_id=tenant.id,
                name=spec["name"],
                category=spec["category"],
                unit=spec["unit"],
                cost_per_unit=spec["cost_per_unit"],
                current_stock=0,  # rollup of location stock, set by move_stock
                reorder_point=spec["reorder_point"],
                reorder_quantity=spec["reorder_quantity"],
                is_active=True,
                is_produced=False,
            )
            db.add(ing)
            await db.flush()
        ing_map[spec["name"]] = ing
    print(f"  Raw ingredients: {len(RAW_INGREDIENTS)}.")
    return ing_map


async def get_or_create_sub_recipes(
    db: AsyncSession, tenant: Tenant, admin: User, ing_map: dict[str, Ingredient]
) -> None:
    await ingredient_category_service.ensure_category(db, tenant.id, "Made In-House")
    for spec in SUB_RECIPES:
        produced = (
            await db.execute(
                select(Ingredient).where(Ingredient.name == spec["produces"], Ingredient.tenant_id == tenant.id)
            )
        ).scalar_one_or_none()
        if produced is None:
            produced = Ingredient(
                tenant_id=tenant.id, name=spec["produces"], category="Made In-House",
                unit=spec["unit"], cost_per_unit=0, current_stock=0,
                reorder_point=0, reorder_quantity=0, is_active=True, is_produced=True,
            )
            db.add(produced)
            await db.flush()
        ing_map[spec["produces"]] = produced

        has_recipe = (
            await db.execute(
                select(Recipe.id).where(
                    Recipe.tenant_id == tenant.id,
                    Recipe.produces_ingredient_id == produced.id,
                    Recipe.is_active == True,  # noqa: E712
                )
            )
        ).first()
        if has_recipe is not None:
            continue

        recipe = await recipe_service.create_recipe(
            db,
            tenant.id,
            RecipeCreate(
                produces_ingredient_id=produced.id,
                yield_servings=spec["yield_qty"],
                prep_time_minutes=spec["prep"],
                cook_time_minutes=spec["cook"],
                instructions=spec["instructions"],
                recipe_items=[
                    RecipeItemCreate(ingredient_id=ing_map[n].id, quantity=q, unit=u, waste_factor=w)
                    for n, q, u, w in spec["items"]
                ],
            ),
            admin.id,
        )
        print(
            f"  Sub-recipe '{spec['produces']}': batch Rs {recipe.total_ingredient_cost/100:,.0f} "
            f"-> Rs {recipe.cost_per_serving/100:,.2f}/{spec['unit']}"
        )


async def get_or_create_final_recipes(
    db: AsyncSession, tenant: Tenant, admin: User, ing_map: dict[str, Ingredient],
    menu_map: dict[str, MenuItem],
) -> None:
    for item_name, (instructions, items) in FINAL_RECIPES.items():
        menu_item = menu_map[item_name]
        if await recipe_service.get_recipe_by_menu_item(db, tenant.id, menu_item.id) is not None:
            continue
        recipe = await recipe_service.create_recipe(
            db,
            tenant.id,
            RecipeCreate(
                menu_item_id=menu_item.id,
                yield_servings=Decimal("1"),
                instructions=instructions,
                recipe_items=[
                    RecipeItemCreate(ingredient_id=ing_map[n].id, quantity=q, unit=u, waste_factor=w)
                    for n, q, u, w in items
                ],
            ),
            admin.id,
        )
        pct = recipe.cost_per_serving / menu_item.price * 100
        print(
            f"  Recipe '{item_name}': cost Rs {recipe.cost_per_serving/100:,.0f}, "
            f"price Rs {menu_item.price/100:,.0f}, food cost {pct:.1f}%"
        )


async def get_or_create_location(db: AsyncSession, tenant: Tenant) -> Location:
    loc = (
        await db.execute(
            select(Location).where(Location.tenant_id == tenant.id, Location.code == LOCATION["code"])
        )
    ).scalar_one_or_none()
    if loc is None:
        loc = await location_service.create_location(db, tenant.id, dict(LOCATION))
        print(f"  Location '{LOCATION['name']}' created.")
    return loc


async def get_or_create_channels(db: AsyncSession, tenant: Tenant) -> dict[str, SalesChannel]:
    out: dict[str, SalesChannel] = {}
    for spec in SALES_CHANNELS:
        ch = (
            await db.execute(
                select(SalesChannel).where(SalesChannel.tenant_id == tenant.id, SalesChannel.code == spec["code"])
            )
        ).scalar_one_or_none()
        if ch is None:
            ch = await location_service.create_channel(db, tenant.id, dict(spec))
        out[spec["code"]] = ch
    return out


async def get_or_create_floors_and_station(db: AsyncSession, tenant: Tenant) -> None:
    number = 1
    for order, spec in enumerate(FLOORS):
        floor = (
            await db.execute(select(Floor).where(Floor.tenant_id == tenant.id, Floor.name == spec["name"]))
        ).scalar_one_or_none()
        if floor is None:
            floor = Floor(tenant_id=tenant.id, name=spec["name"], display_order=order, is_active=True)
            db.add(floor)
            await db.flush()
            for i in range(spec["tables"]):
                db.add(Table(
                    tenant_id=tenant.id, floor_id=floor.id, number=number + i,
                    capacity=spec["capacity"], shape="square" if spec["capacity"] <= 4 else "rectangle",
                    pos_x=60 + (i % 5) * 140, pos_y=60 + (i // 5) * 140,
                    width=80 if spec["capacity"] <= 4 else 110, height=80, is_active=True,
                ))
            await db.flush()
            print(f"  Floor '{spec['name']}' with {spec['tables']} tables.")
        number += spec["tables"]

    # Every ticket routes to the FIRST active station, so one is enough.
    station = (
        await db.execute(select(KitchenStation).where(KitchenStation.tenant_id == tenant.id))
    ).first()
    if station is None:
        db.add(KitchenStation(tenant_id=tenant.id, name="Main Kitchen", display_order=0, is_active=True))
        await db.flush()
        print("  Kitchen station 'Main Kitchen' created.")


async def get_or_create_payment_methods(db: AsyncSession, tenant: Tenant) -> dict[str, PaymentMethod]:
    existing = {
        m.code: m
        for m in (await db.execute(select(PaymentMethod).where(PaymentMethod.tenant_id == tenant.id))).scalars()
    }
    for code, name, requires_ref, order in [
        ("cash", "Cash", False, 1),
        ("card", "Card", True, 2),
        ("mobile_wallet", "JazzCash / Easypaisa", True, 3),
        ("bank_transfer", "Bank Transfer", True, 4),
    ]:
        if code not in existing:
            method = PaymentMethod(tenant_id=tenant.id, code=code, display_name=name, is_active=True,
                                   requires_reference=requires_ref, sort_order=order)
            db.add(method)
            existing[code] = method
    await db.flush()
    return existing


async def seed_opening_stock(
    db: AsyncSession, tenant: Tenant, location: Location, ing_map: dict[str, Ingredient], admin: User
) -> None:
    for spec in RAW_INGREDIENTS:
        ingredient = ing_map[spec["name"]]
        row = await stock_service.get_or_create_stock_row(db, tenant.id, location.id, ingredient.id)
        if Decimal(str(row.quantity)) != 0:
            continue  # Already stocked. Never top up on a re-run.
        await stock_service.move_stock(
            db,
            tenant_id=tenant.id,
            ingredient_id=ingredient.id,
            quantity_delta=spec["opening"],
            transaction_type="purchase",
            location_id=location.id,
            performed_by=admin.id,
            reference_number="OPENING",
            notes="Opening balance",
        )
        row.reorder_point = spec["reorder_point"]
        row.reorder_quantity = spec["reorder_quantity"]
    await db.flush()
    print("  Opening stock set.")


async def seed_suppliers_and_purchasing(
    db: AsyncSession, tenant: Tenant, location: Location, ing_map: dict[str, Ingredient], admin: User
) -> None:
    """Four suppliers with catalogues, then one PO received, one sent, one draft."""
    sup_map: dict[str, Supplier] = {}
    for spec in SUPPLIERS:
        sup = (
            await db.execute(select(Supplier).where(Supplier.tenant_id == tenant.id, Supplier.code == spec["code"]))
        ).scalar_one_or_none()
        if sup is None:
            data = {k: v for k, v in spec.items() if k != "items"}
            sup = await supplier_service.create_supplier(db, tenant.id, data)
            for name in spec["items"]:
                await supplier_service.upsert_supplier_item(db, tenant.id, sup.id, {
                    "ingredient_id": ing_map[name].id,
                    "last_price_minor": ing_map[name].cost_per_unit,
                    "is_preferred": True,
                })
            print(f"  Supplier '{spec['name']}' with {len(spec['items'])} items.")
        sup_map[spec["code"]] = sup

    if (await db.execute(select(PurchaseOrder.id).where(PurchaseOrder.tenant_id == tenant.id))).first():
        print("  Purchase orders already present, skipped.")
        return

    def line(name: str, qty: str) -> dict:
        return {"ingredient_id": ing_map[name].id, "quantity_ordered": Decimal(qty),
                "unit_price_minor": ing_map[name].cost_per_unit}

    # 1. Chicken: ordered, sent, delivered and booked in.
    po = await purchase_order_service.create_purchase_order(
        db, tenant_id=tenant.id, supplier_id=sup_map["POULTRY"].id, location_id=location.id,
        lines=[line("Chicken (Karahi Cut)", "25"), line("Boneless Chicken", "20"), line("Eggs", "90")],
        notes="Weekend stock", created_by=admin.id,
    )
    await purchase_order_service.mark_sent(db, tenant_id=tenant.id, po_id=po.id)
    po = await purchase_order_service.get_purchase_order(db, tenant.id, po.id)
    await purchase_order_service.receive_goods(
        db, tenant_id=tenant.id, po_id=po.id,
        lines=[{"purchase_order_item_id": it.id, "quantity_received": it.quantity_ordered} for it in po.items],
        document_reference="FPT-INV-1182", performed_by=admin.id,
    )
    print(f"  PO {po.po_number}: sent and received in full.")

    # 2. Mutton and mince: sent, awaiting delivery.
    po2 = await purchase_order_service.create_purchase_order(
        db, tenant_id=tenant.id, supplier_id=sup_map["MEAT"].id, location_id=location.id,
        lines=[line("Mutton", "15"), line("Beef Mince", "10")], created_by=admin.id,
    )
    await purchase_order_service.mark_sent(db, tenant_id=tenant.id, po_id=po2.id)
    print(f"  PO {po2.po_number}: sent, awaiting delivery.")

    # 3. Dairy: a draft, covering the mozzarella that is below its reorder point.
    po3 = await purchase_order_service.create_purchase_order(
        db, tenant_id=tenant.id, supplier_id=sup_map["DAIRY"].id, location_id=location.id,
        lines=[line("Mozzarella Cheese", "10"), line("Fresh Cream", "12")], created_by=admin.id,
    )
    print(f"  PO {po3.po_number}: draft.")


async def seed_production(
    db: AsyncSession, tenant: Tenant, location: Location, ing_map: dict[str, Ingredient], admin: User
) -> None:
    """Make the in-house items, through the real production service."""
    for spec in SUB_RECIPES:
        produced = ing_map[spec["produces"]]
        row = await stock_service.get_or_create_stock_row(db, tenant.id, location.id, produced.id)
        if Decimal(str(row.quantity)) > 0:
            continue
        recipe = (
            await db.execute(
                select(Recipe).where(
                    Recipe.tenant_id == tenant.id,
                    Recipe.produces_ingredient_id == produced.id,
                    Recipe.is_active == True,  # noqa: E712
                )
            )
        ).scalar_one()
        result = await production_service.run_production(
            db, tenant_id=tenant.id, recipe_id=recipe.id, batches=spec["batches"],
            location_id=location.id, performed_by=admin.id,
        )
        print(f"  Produced {result['produced_quantity']} {spec['unit']} of {result['recipe_name']}.")


async def seed_demo_orders(
    db: AsyncSession, tenant: Tenant, location: Location, channels: dict[str, SalesChannel],
    menu_map: dict[str, MenuItem], methods: dict[str, PaymentMethod], admin: User,
) -> None:
    """A few days of completed sales. Each deducts stock through the same
    service a real completion uses, so the movement ledger is genuine."""
    if (await db.execute(select(Order.id).where(Order.tenant_id == tenant.id).limit(1))).first():
        print("  Demo orders already present, skipped.")
        return

    # (days ago, hour in Karachi, order type, channel, [(item, qty)])
    plan = [
        (3, 13, "dine_in", "direct", [("Chicken Karahi (Full)", 1), ("Garlic Naan", 4), ("Soft Drink", 4)]),
        (3, 20, "dine_in", "direct", [("Mutton Karahi (Half)", 1), ("Malai Boti (8 Pcs)", 1), ("Roti", 6)]),
        (3, 21, "takeaway", "direct", [("Danny's Smash", 2), ("Fries", 1)]),
        (2, 14, "call_center", "phone", [("Chicken Tikkah Piece", 4), ("Roghni Naan", 4)]),
        (2, 20, "dine_in", "direct", [("Fettuccine Pasta", 2), ("Chicken Steak (Black Pepper)", 1),
                                      ("Cappuccino", 2)]),
        (2, 22, "takeaway", "foodpanda", [("Grilled Chicken Burger", 3), ("Fries", 2)]),
        (1, 13, "dine_in", "direct", [("Chicken Manchurian", 1), ("Egg Fried Rice", 1), ("Water (Small)", 2)]),
        (1, 20, "dine_in", "direct", [("Chicken Karahi (Half)", 1), ("Reshmi Kabab (4 Pcs)", 1),
                                      ("Cheese Naan", 1), ("Roti", 4), ("Doodh Patti", 2)]),
        (1, 21, "takeaway", "foodpanda", [("Danny's Smash", 1), ("Oreo Pleasure", 1)]),
        (0, 13, "dine_in", "direct", [("Shahi Handi (Full)", 1), ("Garlic Naan", 3), ("Latte", 2)]),
        (0, 14, "call_center", "phone", [("Mutton Karahi (Full)", 1), ("Roti", 8)]),
    ]

    pk = timezone(timedelta(hours=5))
    today = datetime.now(pk).replace(minute=15, second=0, microsecond=0)
    for index, (days_ago, hour, order_type, channel_code, lines) in enumerate(plan, start=1):
        when = (today - timedelta(days=days_ago)).replace(hour=hour)
        if when > datetime.now(pk):
            when = datetime.now(pk) - timedelta(minutes=30)
        subtotal = sum(menu_map[n].price * q for n, q in lines)
        tax = subtotal * TAX_BPS // 10000
        order = Order(
            tenant_id=tenant.id,
            order_number=f"DN-{index:04d}",
            order_type=order_type,
            status="completed",
            payment_status="paid",
            subtotal=subtotal,
            tax_amount=tax,
            discount_amount=0,
            total=subtotal + tax,
            created_by=admin.id,
            location_id=location.id,
            sales_channel_id=channels[channel_code].id,
            customer_name="Walk-in" if order_type != "call_center" else "Phone customer",
            customer_phone="03000000000" if order_type == "call_center" else None,
            created_at=when,
        )
        db.add(order)
        await db.flush()
        for name, qty in lines:
            item = menu_map[name]
            db.add(OrderItem(
                tenant_id=tenant.id, order_id=order.id, menu_item_id=item.id, name=item.name,
                quantity=qty, unit_price=item.price, total=item.price * qty,
            ))
        db.add(Payment(
            tenant_id=tenant.id, order_id=order.id, method_id=methods["cash"].id, kind="payment",
            status="completed", amount=order.total, tendered_amount=order.total, change_amount=0,
            processed_by=admin.id, processed_at=when,
        ))
        await db.flush()
        await production_service.consume_for_order(db, tenant_id=tenant.id, order_id=order.id,
                                                   performed_by=admin.id)
        await location_service.snapshot_commission(db, tenant.id, order)

    print(f"  {len(plan)} completed demo orders, stock deducted for each.")


async def seed() -> None:
    async with async_session_factory() as db:
        tenant = await get_or_create_tenant(db)
        await get_or_create_config(db, tenant)
        admin = await get_or_create_users(db, tenant)
        menu_map = await get_or_create_menu(db, tenant)
        ing_map = await get_or_create_raw_ingredients(db, tenant)
        await get_or_create_sub_recipes(db, tenant, admin, ing_map)
        await get_or_create_final_recipes(db, tenant, admin, ing_map, menu_map)
        location = await get_or_create_location(db, tenant)
        channels = await get_or_create_channels(db, tenant)
        await get_or_create_floors_and_station(db, tenant)
        methods = await get_or_create_payment_methods(db, tenant)
        await seed_opening_stock(db, tenant, location, ing_map, admin)
        await seed_suppliers_and_purchasing(db, tenant, location, ing_map, admin)
        await seed_production(db, tenant, location, ing_map, admin)
        await seed_demo_orders(db, tenant, location, channels, menu_map, methods, admin)
        await db.commit()
        print(f"\nDone. Tenant slug '{TENANT_SLUG}'. Credentials are in the client folder, not here.")


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
