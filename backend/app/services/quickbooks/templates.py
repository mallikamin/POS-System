"""QuickBooks Chart of Accounts template library — the QB Playbook.

40 restaurant templates covering every cuisine, format, business model,
and tax jurisdiction a client could walk in with.  Templates are composed
from reusable mapping blocks so each one is self-contained but the code
stays DRY and maintainable.

Usage::

    from app.services.quickbooks.templates import MAPPING_TEMPLATES
    template = MAPPING_TEMPLATES["pakistani_bbq_specialist"]
"""

from __future__ import annotations

from typing import Any, Optional

# ---------------------------------------------------------------------------
# Mapping-type constants (must match mappings.py)
# ---------------------------------------------------------------------------
_INCOME = "income"
_COGS = "cogs"
_TAX = "tax_payable"
_BANK = "bank"
_EXPENSE = "expense"
_OCL = "other_current_liability"
_DISCOUNT = "discount"
_ROUNDING = "rounding"
_CASH_SHORT = "cash_over_short"
_TIPS = "tips"
_GIFT_CARD = "gift_card_liability"
_SVC_CHARGE = "service_charge"
_DELIVERY = "delivery_fee"
_PLATFORM = "foodpanda_commission"

# QB account type/sub-type shortcuts
_INC = "Income"
_COGS_T = "Cost of Goods Sold"
_EXP = "Expense"
_OCL_T = "Other Current Liability"
_BANK_T = "Bank"
_OCA = "Other Current Asset"

_SALES = "SalesOfProductIncome"
_SVC_FEE = "ServiceFeeIncome"
_CONTRA = "DiscountsRefundsGiven"
_OTHER_INC = "OtherPrimaryIncome"
_SUPPLIES = "SuppliesMaterialsCogs"
_LABOR_COGS = "CostOfLaborCos"
_CASH_HAND = "CashOnHand"
_CHECKING = "Checking"
_SAVINGS = "Savings"
_OCA_SUB = "OtherCurrentAssets"
_OCL_SUB = "OtherCurrentLiabilities"
_TRAVEL = "Travel"
_COMMISSION = "CommissionsAndFees"
_MISC_EXP = "OtherMiscellaneousServiceCost"
_RENT = "Rent"
_UTILITIES = "Utilities"
_ADVERTISING = "AdvertisingPromotional"
_PAYROLL = "PayrollExpenses"
_INSURANCE = "Insurance"
_REPAIR = "RepairMaintenance"
_OFFICE = "OfficeExpenses"
_ENTERTAINMENT = "Entertainment"
_LEGAL = "LegalProfessionalFees"


# ---------------------------------------------------------------------------
# Reusable Mapping Blocks
# ---------------------------------------------------------------------------
def _m(mapping_type: str, name: str, account_type: str, account_sub_type: str,
       is_default: bool, description: str) -> dict:
    """Shorthand mapping constructor."""
    return {
        "mapping_type": mapping_type,
        "name": name,
        "account_type": account_type,
        "account_sub_type": account_sub_type,
        "is_default": is_default,
        "description": description,
    }


# --- Pakistan Tax (FBR + PRA) ---
_PAK_PUNJAB_TAX = [
    _m(_TAX, "FBR GST Payable (17%)", _OCL_T, _OCL_SUB, True,
       "Federal Board of Revenue General Sales Tax — 17% standard rate"),
    _m(_TAX, "PRA PST Payable (16%)", _OCL_T, _OCL_SUB, False,
       "Punjab Revenue Authority Provincial Sales Tax on services — 16%"),
]
_PAK_SINDH_TAX = [
    _m(_TAX, "FBR GST Payable (17%)", _OCL_T, _OCL_SUB, True,
       "Federal Board of Revenue General Sales Tax — 17% standard rate"),
    _m(_TAX, "SRB SST Payable (13%)", _OCL_T, _OCL_SUB, False,
       "Sindh Revenue Board Sales Tax on services — 13%"),
]
_PAK_KPK_TAX = [
    _m(_TAX, "FBR GST Payable (17%)", _OCL_T, _OCL_SUB, True,
       "Federal Board of Revenue General Sales Tax — 17% standard rate"),
    _m(_TAX, "KPRA Sales Tax Payable (15%)", _OCL_T, _OCL_SUB, False,
       "Khyber Pakhtunkhwa Revenue Authority Sales Tax — 15%"),
]
_PAK_ISLAMABAD_TAX = [
    _m(_TAX, "FBR GST Payable (17%)", _OCL_T, _OCL_SUB, True,
       "Federal Board of Revenue General Sales Tax — 17% (ICT — no provincial tax)"),
]
_VAT_STANDARD = [
    _m(_TAX, "VAT Payable", _OCL_T, _OCL_SUB, True,
       "Value Added Tax collected from customers — standard rate"),
    _m(_TAX, "VAT Reduced Rate Payable", _OCL_T, _OCL_SUB, False,
       "VAT at reduced rate (takeaway / essential items)"),
]
_UAE_TAX = [
    _m(_TAX, "VAT Payable (5%)", _OCL_T, _OCL_SUB, True,
       "UAE Value Added Tax — 5% standard rate"),
    _m(_TAX, "Tourism Dirham Payable", _OCL_T, _OCL_SUB, False,
       "Tourism dirham fee collected per transaction (applicable in hospitality)"),
]
_SAUDI_TAX = [
    _m(_TAX, "VAT Payable (15%)", _OCL_T, _OCL_SUB, True,
       "KSA Value Added Tax — 15% standard rate"),
]
_GENERIC_TAX = [
    _m(_TAX, "Sales Tax Payable", _OCL_T, _OCL_SUB, True,
       "Sales tax collected from customers (configure rate per jurisdiction)"),
]

# --- Pakistan Mobile Wallets ---
_PAK_MOBILE = [
    _m(_BANK, "JazzCash Settlement", _BANK_T, _CHECKING, False,
       "JazzCash mobile wallet settlement account"),
    _m(_BANK, "Easypaisa Settlement", _BANK_T, _CHECKING, False,
       "Easypaisa mobile wallet settlement account"),
]

# --- Base Bank/Cash (every restaurant) ---
_BASE_BANK = [
    _m(_BANK, "Cash Register", _BANK_T, _CASH_HAND, True,
       "Physical cash in POS cash drawer / till"),
    _m(_BANK, "Bank Account (Card Settlements)", _BANK_T, _CHECKING, False,
       "Bank account receiving credit/debit card settlements"),
]

# --- Pakistan Delivery Ecosystem ---
_PAK_DELIVERY = [
    _m(_BANK, "Foodpanda Settlement", _OCA, _OCA_SUB, False,
       "Foodpanda receivable — funds due until weekly/monthly payout"),
    _m(_DELIVERY, "Delivery Expense", _EXP, _TRAVEL, True,
       "Delivery operations: fuel, vehicle maintenance, routing"),
    _m(_EXPENSE, "Rider Commission", _EXP, _COMMISSION, False,
       "Per-order commission paid to delivery riders"),
    _m(_PLATFORM, "Platform Commission (Foodpanda)", _EXP, _COMMISSION, True,
       "Commission deducted by Foodpanda (25-35%) per marketplace order"),
]

# --- International Delivery ---
_INTL_DELIVERY = [
    _m(_BANK, "Marketplace Settlement Receivable", _OCA, _OCA_SUB, False,
       "Amounts due from third-party delivery platforms pending payout"),
    _m(_DELIVERY, "Delivery Expense", _EXP, _TRAVEL, True,
       "Delivery operations costs"),
    _m(_EXPENSE, "Rider Commission", _EXP, _COMMISSION, False,
       "Per-order commission to delivery drivers"),
    _m(_PLATFORM, "Marketplace Platform Commission", _EXP, _COMMISSION, True,
       "Commission fees charged by delivery platforms"),
]

# --- Base Expense (every restaurant) ---
_BASE_EXPENSE = [
    _m(_DISCOUNT, "Discount Given", _INC, _CONTRA, True,
       "Contra-revenue: coupons, manager comps, promotions, happy hour"),
    _m(_ROUNDING, "Rounding Adjustment", _EXP, _MISC_EXP, True,
       "Sub-rupee/sub-unit rounding differences on cash transactions"),
]

# --- Base Liability (every restaurant) ---
_BASE_LIABILITY = [
    _m(_TIPS, "Tips Payable", _OCL_T, _OCL_SUB, True,
       "Tips collected from customers pending distribution to staff"),
    _m(_GIFT_CARD, "Gift Card Liability", _OCL_T, _OCL_SUB, True,
       "Unredeemed gift card / voucher balances"),
    _m(_OCL, "Customer Deposits", _OCL_T, _OCL_SUB, True,
       "Advance deposits for catering, large orders, events"),
    _m(_CASH_SHORT, "Cash Over/Short", _EXP, _MISC_EXP, True,
       "Discrepancies between expected and actual cash drawer counts"),
]

# --- Service Charge ---
_SVC_CHARGE_INCOME = [
    _m(_SVC_CHARGE, "Service Charge Revenue", _INC, _SVC_FEE, True,
       "Service charge / gratuity added to dine-in bills"),
]

# --- Multi-brand / Franchise extras ---
_FRANCHISE_EXPENSE = [
    _m(_EXPENSE, "Royalty Fee Expense", _EXP, _COMMISSION, False,
       "Franchise royalty fees (typically 5-8% of gross revenue)"),
    _m(_EXPENSE, "Marketing Fund Contribution", _EXP, _ADVERTISING, False,
       "Franchise marketing/advertising fund (typically 2-3% of revenue)"),
    _m(_EXPENSE, "Brand License Fee", _EXP, _LEGAL, False,
       "Annual brand license / territory fee"),
]

# --- Hotel / Resort extras ---
_HOTEL_EXTRAS = [
    _m(_INCOME, "Room Service Revenue", _INC, _SALES, False,
       "Revenue from in-room dining / room service orders"),
    _m(_INCOME, "Banquet & Conference F&B", _INC, _SALES, False,
       "Food & beverage revenue from banquet halls and conferences"),
    _m(_INCOME, "Minibar Revenue", _INC, _SALES, False,
       "Revenue from in-room minibar consumption"),
    _m(_OCL, "Room Charge Receivable", _OCA, _OCA_SUB, False,
       "F&B charges posted to guest room folios pending checkout settlement"),
]

# --- Online Payment ---
_ONLINE_PAYMENT = [
    _m(_BANK, "Online Payment Settlement", _BANK_T, _CHECKING, False,
       "Settlement from online payment providers (Stripe, Square, etc.)"),
]


# =========================================================================
# Income + COGS blocks per cuisine/format
# =========================================================================

# Pakistani Full-Service
_PAKISTANI_INCOME = [
    _m(_INCOME, "Food Sales", _INC, _SALES, True, "Default income for all food sales"),
    _m(_INCOME, "Beverage Sales", _INC, _SALES, False, "Drinks, juices, lassi, chai, soft drinks"),
    _m(_INCOME, "BBQ & Grill Sales", _INC, _SALES, False, "Tikka, seekh kebab, chapli, malai boti"),
    _m(_INCOME, "Biryani & Rice Sales", _INC, _SALES, False, "Biryani, pulao, rice dishes"),
    _m(_INCOME, "Karahi & Curry Sales", _INC, _SALES, False, "Karahi, handi, salan, curries"),
    _m(_INCOME, "Naan & Bread Sales", _INC, _SALES, False, "Naan, roti, paratha, kulcha"),
    _m(_INCOME, "Dessert Sales", _INC, _SALES, False, "Kheer, gulab jamun, ras malai, halwa"),
    _m(_INCOME, "Takeaway Sales", _INC, _SALES, False, "Takeaway/parcel channel revenue"),
    _m(_INCOME, "Delivery Revenue", _INC, _SALES, False, "Call center and website delivery orders"),
    _m(_INCOME, "Catering Revenue", _INC, _SALES, False, "Dawat, event, bulk catering orders"),
    _m(_INCOME, "Foodpanda Revenue", _INC, _SALES, False, "Foodpanda marketplace (gross before commission)"),
]
_PAKISTANI_COGS = [
    _m(_COGS, "Food Cost", _COGS_T, _SUPPLIES, True, "Meat, vegetables, spices, flour, oil, ghee"),
    _m(_COGS, "Beverage Cost", _COGS_T, _SUPPLIES, False, "Soft drinks, juices, milk, tea, water"),
    _m(_COGS, "Packaging Cost", _COGS_T, _SUPPLIES, False, "Takeaway containers, bags, napkins, utensils"),
]

# Pakistani BBQ Specialist
_BBQ_INCOME = [
    _m(_INCOME, "Tikka & Kebab Sales", _INC, _SALES, True, "Chicken tikka, seekh kebab, malai boti, reshmi kebab"),
    _m(_INCOME, "Sajji & Whole Roast Sales", _INC, _SALES, False, "Whole sajji, lamb chops, raan"),
    _m(_INCOME, "Chapli & Specialty Kebab", _INC, _SALES, False, "Chapli kebab, bihari boti, gola kebab"),
    _m(_INCOME, "Naan & Bread Sales", _INC, _SALES, False, "Tandoori naan, roghni naan, paratha"),
    _m(_INCOME, "Sides & Raita Sales", _INC, _SALES, False, "Salad, raita, chutney, fries"),
    _m(_INCOME, "Beverage Sales", _INC, _SALES, False, "Lassi, doodh soda, soft drinks, water"),
    _m(_INCOME, "Takeaway Sales", _INC, _SALES, False, "Takeaway/parcel orders"),
    _m(_INCOME, "Catering & Dawat Revenue", _INC, _SALES, False, "Bulk BBQ catering for events"),
]
_BBQ_COGS = [
    _m(_COGS, "Meat Cost", _COGS_T, _SUPPLIES, True, "Chicken, mutton, beef — primary raw material"),
    _m(_COGS, "Charcoal & Fuel Cost", _COGS_T, _SUPPLIES, False, "Charcoal, wood, gas for grilling"),
    _m(_COGS, "Spice & Marinade Cost", _COGS_T, _SUPPLIES, False, "Spice mixes, yogurt marinade, oil"),
    _m(_COGS, "Packaging Cost", _COGS_T, _SUPPLIES, False, "Foil trays, takeaway boxes, bags"),
]

# Biryani House
_BIRYANI_INCOME = [
    _m(_INCOME, "Biryani Sales", _INC, _SALES, True, "Chicken, mutton, beef, prawn biryani"),
    _m(_INCOME, "Pulao & Rice Sales", _INC, _SALES, False, "Yakhni pulao, kabuli pulao, plain rice"),
    _m(_INCOME, "Raita & Sides Sales", _INC, _SALES, False, "Raita, salad, achar, papad"),
    _m(_INCOME, "Karahi & Curry Sales", _INC, _SALES, False, "Karahi, qorma, salan (complementary)"),
    _m(_INCOME, "Beverage Sales", _INC, _SALES, False, "Cold drinks, lassi, water"),
    _m(_INCOME, "Takeaway Sales", _INC, _SALES, False, "Takeaway orders (typically 60%+ of revenue)"),
    _m(_INCOME, "Delivery Revenue", _INC, _SALES, False, "Delivery channel orders"),
]
_BIRYANI_COGS = [
    _m(_COGS, "Rice & Grain Cost", _COGS_T, _SUPPLIES, True, "Basmati rice, sella rice (bulk purchase)"),
    _m(_COGS, "Meat Cost", _COGS_T, _SUPPLIES, False, "Chicken, mutton, beef for biryani"),
    _m(_COGS, "Spice & Oil Cost", _COGS_T, _SUPPLIES, False, "Saffron, spice mixes, ghee, cooking oil"),
    _m(_COGS, "Packaging Cost", _COGS_T, _SUPPLIES, False, "Biryani boxes, bags, disposable plates"),
]

# Pakistani Street Food / Dhaba
_STREET_FOOD_INCOME = [
    _m(_INCOME, "Chaat & Snack Sales", _INC, _SALES, True, "Gol gappay, dahi baray, chana chaat, samosa"),
    _m(_INCOME, "Roll & Paratha Sales", _INC, _SALES, False, "Roll paratha, egg paratha, anda shami"),
    _m(_INCOME, "Fries & Fast Food Sales", _INC, _SALES, False, "Fries, burger, shawarma, zinger"),
    _m(_INCOME, "Beverage Sales", _INC, _SALES, False, "Fresh juice, sugarcane, ganne ka ras, chai"),
    _m(_INCOME, "Takeaway Sales", _INC, _SALES, False, "Walk-up takeaway (primary channel)"),
]
_STREET_FOOD_COGS = [
    _m(_COGS, "Food Ingredient Cost", _COGS_T, _SUPPLIES, True, "Chickpeas, flour, potatoes, eggs, oil"),
    _m(_COGS, "Disposable & Packaging Cost", _COGS_T, _SUPPLIES, False, "Paper plates, cups, bags, napkins"),
]

# Nihari / Paye House
_NIHARI_INCOME = [
    _m(_INCOME, "Nihari Sales", _INC, _SALES, True, "Beef nihari, nalli nihari (primary product)"),
    _m(_INCOME, "Paye & Siri Sales", _INC, _SALES, False, "Paye, siri paye (breakfast specialty)"),
    _m(_INCOME, "Haleem Sales", _INC, _SALES, False, "Haleem (seasonal and regular)"),
    _m(_INCOME, "Naan & Bread Sales", _INC, _SALES, False, "Khamiri roti, naan, kulcha"),
    _m(_INCOME, "Beverage Sales", _INC, _SALES, False, "Chai, lassi, cold drinks"),
    _m(_INCOME, "Takeaway Sales", _INC, _SALES, False, "Morning takeaway orders"),
]
_NIHARI_COGS = [
    _m(_COGS, "Meat & Bone Cost", _COGS_T, _SUPPLIES, True, "Beef shank, trotters, bones (slow-cook stock)"),
    _m(_COGS, "Spice & Masala Cost", _COGS_T, _SUPPLIES, False, "Nihari masala, whole spices, ghee"),
    _m(_COGS, "Flour & Bread Cost", _COGS_T, _SUPPLIES, False, "Flour for naan and khamiri roti"),
]

# Pakistani Sweets & Bakery
_SWEETS_INCOME = [
    _m(_INCOME, "Mithai Sales", _INC, _SALES, True, "Laddu, barfi, jalebi, gulab jamun, rasgulla"),
    _m(_INCOME, "Bakery Sales", _INC, _SALES, False, "Cake, pastries, bread, rusks, biscuits"),
    _m(_INCOME, "Nimko & Snack Sales", _INC, _SALES, False, "Nimko, namkeen, samosa, pakora"),
    _m(_INCOME, "Seasonal & Eid Sales", _INC, _SALES, False, "Eid special boxes, Ramadan items, sheer khurma"),
    _m(_INCOME, "Wholesale Revenue", _INC, _SALES, False, "B2B wholesale to shops and retailers"),
    _m(_INCOME, "Custom Order Revenue", _INC, _SALES, False, "Custom cakes, wedding sweets, event trays"),
]
_SWEETS_COGS = [
    _m(_COGS, "Dairy & Khoya Cost", _COGS_T, _SUPPLIES, True, "Milk, khoya, cream, butter, ghee"),
    _m(_COGS, "Sugar & Flour Cost", _COGS_T, _SUPPLIES, False, "Sugar, flour, maida, semolina"),
    _m(_COGS, "Dry Fruit & Nut Cost", _COGS_T, _SUPPLIES, False, "Almonds, pistachios, cashews, cardamom"),
    _m(_COGS, "Packaging & Box Cost", _COGS_T, _SUPPLIES, False, "Gift boxes, trays, wrapping, ribbons"),
]

# Karachi Seafood
_SEAFOOD_INCOME = [
    _m(_INCOME, "Fish Sales", _INC, _SALES, True, "Fried fish, grilled fish, fish tikka, fish karahi"),
    _m(_INCOME, "Prawn & Shrimp Sales", _INC, _SALES, False, "Prawn karahi, grilled prawns, prawn biryani"),
    _m(_INCOME, "Crab & Lobster Sales", _INC, _SALES, False, "Crab masala, lobster (premium/seasonal)"),
    _m(_INCOME, "Squid & Specialty Sales", _INC, _SALES, False, "Calamari, squid fry, mixed seafood platter"),
    _m(_INCOME, "Sides & Bread Sales", _INC, _SALES, False, "Naan, rice, salad, chutney"),
    _m(_INCOME, "Beverage Sales", _INC, _SALES, False, "Fresh lime, cold drinks, lassi"),
]
_SEAFOOD_COGS = [
    _m(_COGS, "Fresh Fish Cost", _COGS_T, _SUPPLIES, True, "Daily fish purchase (market-price, variable)"),
    _m(_COGS, "Shellfish & Premium Seafood", _COGS_T, _SUPPLIES, False, "Prawns, crabs, lobster, squid"),
    _m(_COGS, "Spice & Cooking Cost", _COGS_T, _SUPPLIES, False, "Oil, masala, lemon, flour for frying"),
]

# Lahore Food Street
_FOOD_STREET_INCOME = [
    _m(_INCOME, "BBQ Station Sales", _INC, _SALES, True, "Tikka, seekh, boti from BBQ stalls"),
    _m(_INCOME, "Karahi Station Sales", _INC, _SALES, False, "Chicken karahi, mutton karahi live cooking"),
    _m(_INCOME, "Biryani Station Sales", _INC, _SALES, False, "Biryani, pulao from rice station"),
    _m(_INCOME, "Fry & Chaat Station Sales", _INC, _SALES, False, "Fried fish, chaat, gol gappay, pakoray"),
    _m(_INCOME, "Dessert Station Sales", _INC, _SALES, False, "Falooda, kulfi, jalebi, rabri"),
    _m(_INCOME, "Beverage Station Sales", _INC, _SALES, False, "Fresh juice, lassi, doodh jalebi"),
    _m(_INCOME, "Takeaway Sales", _INC, _SALES, False, "Takeaway from all stations"),
]
_FOOD_STREET_COGS = [
    _m(_COGS, "Meat & Poultry Cost", _COGS_T, _SUPPLIES, True, "Chicken, mutton, beef for all stations"),
    _m(_COGS, "Vegetable & Produce Cost", _COGS_T, _SUPPLIES, False, "Onions, tomatoes, herbs, salad"),
    _m(_COGS, "Cooking Fuel Cost", _COGS_T, _SUPPLIES, False, "LPG gas, charcoal for open-air cooking"),
    _m(_COGS, "Disposable & Serving Cost", _COGS_T, _SUPPLIES, False, "Paper plates, plastic utensils, cups"),
]

# Chinese / Pakistani-Chinese
_CHINESE_INCOME = [
    _m(_INCOME, "Chinese Entree Sales", _INC, _SALES, True, "Manchurian, sweet & sour, chilli chicken/prawn"),
    _m(_INCOME, "Rice & Noodle Sales", _INC, _SALES, False, "Fried rice, chowmein, lo mein, egg rice"),
    _m(_INCOME, "Soup Sales", _INC, _SALES, False, "Hot & sour, corn, wonton, egg drop soup"),
    _m(_INCOME, "Starter & Dim Sum Sales", _INC, _SALES, False, "Spring rolls, dumplings, wontons, tempura"),
    _m(_INCOME, "Beverage Sales", _INC, _SALES, False, "Drinks, mocktails, ice cream"),
    _m(_INCOME, "Delivery Revenue", _INC, _SALES, False, "Delivery orders (typically high for Chinese)"),
]
_CHINESE_COGS = [
    _m(_COGS, "Meat & Seafood Cost", _COGS_T, _SUPPLIES, True, "Chicken, prawns, beef for wok cooking"),
    _m(_COGS, "Noodle & Rice Cost", _COGS_T, _SUPPLIES, False, "Noodles, rice, wrappers, flour"),
    _m(_COGS, "Sauce & Condiment Cost", _COGS_T, _SUPPLIES, False, "Soy sauce, vinegar, chilli sauce, cornstarch"),
    _m(_COGS, "Vegetable Cost", _COGS_T, _SUPPLIES, False, "Capsicum, cabbage, mushrooms, baby corn"),
]

# Pizza Chain
_PIZZA_INCOME = [
    _m(_INCOME, "Pizza Sales", _INC, _SALES, True, "All pizza varieties (primary revenue)"),
    _m(_INCOME, "Side & Appetizer Sales", _INC, _SALES, False, "Garlic bread, wings, wedges, pasta"),
    _m(_INCOME, "Beverage Sales", _INC, _SALES, False, "Soft drinks, juice, water"),
    _m(_INCOME, "Combo Deal Sales", _INC, _SALES, False, "Bundle/combo deals for tracking deal mix"),
    _m(_INCOME, "Delivery Revenue", _INC, _SALES, False, "Delivery channel (typically 50%+ for pizza)"),
    _m(_INCOME, "Dine-In Revenue", _INC, _SALES, False, "Dine-in channel tracking"),
]
_PIZZA_COGS = [
    _m(_COGS, "Cheese & Dairy Cost", _COGS_T, _SUPPLIES, True, "Mozzarella, cheddar, cream cheese (largest cost)"),
    _m(_COGS, "Dough & Flour Cost", _COGS_T, _SUPPLIES, False, "Flour, yeast, oil for dough preparation"),
    _m(_COGS, "Topping & Meat Cost", _COGS_T, _SUPPLIES, False, "Pepperoni, chicken, vegetables, olives, mushrooms"),
    _m(_COGS, "Sauce Cost", _COGS_T, _SUPPLIES, False, "Tomato sauce, BBQ sauce, ranch, garlic sauce"),
    _m(_COGS, "Box & Packaging Cost", _COGS_T, _SUPPLIES, False, "Pizza boxes, delivery bags, insulated carriers"),
]

# Burger Joint
_BURGER_INCOME = [
    _m(_INCOME, "Burger Sales", _INC, _SALES, True, "Beef, chicken, specialty burgers"),
    _m(_INCOME, "Fries & Sides Sales", _INC, _SALES, False, "Fries, onion rings, coleslaw, corn"),
    _m(_INCOME, "Shake & Beverage Sales", _INC, _SALES, False, "Milkshakes, soft drinks, iced tea"),
    _m(_INCOME, "Combo Meal Sales", _INC, _SALES, False, "Meal deals, family boxes"),
    _m(_INCOME, "Wrap & Sandwich Sales", _INC, _SALES, False, "Wraps, subs, and non-burger items"),
    _m(_INCOME, "Delivery Revenue", _INC, _SALES, False, "Delivery channel"),
]
_BURGER_COGS = [
    _m(_COGS, "Patty & Meat Cost", _COGS_T, _SUPPLIES, True, "Beef patties, chicken strips, fillet"),
    _m(_COGS, "Bun & Bread Cost", _COGS_T, _SUPPLIES, False, "Burger buns, tortillas, sub rolls"),
    _m(_COGS, "Sauce & Topping Cost", _COGS_T, _SUPPLIES, False, "Cheese slices, lettuce, mayo, ketchup, jalapenos"),
    _m(_COGS, "Fries & Oil Cost", _COGS_T, _SUPPLIES, False, "Frozen fries, frying oil"),
    _m(_COGS, "Packaging Cost", _COGS_T, _SUPPLIES, False, "Burger boxes, bags, cups"),
]

# Steakhouse
_STEAK_INCOME = [
    _m(_INCOME, "Steak Sales", _INC, _SALES, True, "Ribeye, sirloin, T-bone, filet mignon"),
    _m(_INCOME, "Appetizer & Salad Sales", _INC, _SALES, False, "Soups, salads, bread basket, starters"),
    _m(_INCOME, "Dessert Sales", _INC, _SALES, False, "Cheesecake, molten lava, ice cream"),
    _m(_INCOME, "Wine & Bar Sales", _INC, _SALES, False, "Wine pairings, cocktails, mocktails"),
    _m(_INCOME, "Side Dish Sales", _INC, _SALES, False, "Mashed potato, grilled vegetables, mac & cheese"),
    _m(_INCOME, "Private Dining Revenue", _INC, _SVC_FEE, False, "Private room bookings and prix fixe events"),
]
_STEAK_COGS = [
    _m(_COGS, "Premium Meat Cost", _COGS_T, _SUPPLIES, True, "Imported/aged beef cuts (highest COGS item)"),
    _m(_COGS, "Wine & Beverage Cost", _COGS_T, _SUPPLIES, False, "Wine, spirits, bar ingredients"),
    _m(_COGS, "Produce & Dairy Cost", _COGS_T, _SUPPLIES, False, "Vegetables, butter, cream, cheese"),
]

# Japanese / Sushi
_JAPANESE_INCOME = [
    _m(_INCOME, "Sushi & Sashimi Sales", _INC, _SALES, True, "Nigiri, maki, sashimi, rolls"),
    _m(_INCOME, "Ramen & Noodle Sales", _INC, _SALES, False, "Ramen, udon, soba bowls"),
    _m(_INCOME, "Tempura & Fried Sales", _INC, _SALES, False, "Tempura, katsu, gyoza, karaage"),
    _m(_INCOME, "Bento Box & Set Sales", _INC, _SALES, False, "Bento boxes, lunch/dinner sets"),
    _m(_INCOME, "Beverage Sales", _INC, _SALES, False, "Green tea, sake, soft drinks, Japanese soda"),
]
_JAPANESE_COGS = [
    _m(_COGS, "Fresh Fish & Seafood Cost", _COGS_T, _SUPPLIES, True, "Imported salmon, tuna, shrimp, eel (premium)"),
    _m(_COGS, "Rice & Noodle Cost", _COGS_T, _SUPPLIES, False, "Sushi rice, nori, ramen noodles"),
    _m(_COGS, "Sauce & Condiment Cost", _COGS_T, _SUPPLIES, False, "Soy sauce, wasabi, mirin, sake for cooking"),
]

# Thai
_THAI_INCOME = [
    _m(_INCOME, "Curry Sales", _INC, _SALES, True, "Green, red, massaman, panang curry"),
    _m(_INCOME, "Noodle & Rice Sales", _INC, _SALES, False, "Pad thai, fried rice, pad see ew"),
    _m(_INCOME, "Soup Sales", _INC, _SALES, False, "Tom yum, tom kha, wonton soup"),
    _m(_INCOME, "Starter Sales", _INC, _SALES, False, "Spring rolls, satay, fish cakes, larb"),
    _m(_INCOME, "Beverage Sales", _INC, _SALES, False, "Thai iced tea, coconut water, smoothies"),
    _m(_INCOME, "Delivery Revenue", _INC, _SALES, False, "Delivery orders"),
]
_THAI_COGS = [
    _m(_COGS, "Protein Cost", _COGS_T, _SUPPLIES, True, "Chicken, shrimp, tofu, beef"),
    _m(_COGS, "Coconut & Spice Cost", _COGS_T, _SUPPLIES, False, "Coconut milk, lemongrass, galangal, chilli"),
    _m(_COGS, "Noodle & Rice Cost", _COGS_T, _SUPPLIES, False, "Rice noodles, jasmine rice, tapioca"),
]

# Italian
_ITALIAN_INCOME = [
    _m(_INCOME, "Pasta Sales", _INC, _SALES, True, "Spaghetti, penne, lasagna, risotto"),
    _m(_INCOME, "Pizza Sales", _INC, _SALES, False, "Wood-fire pizza, calzone"),
    _m(_INCOME, "Appetizer & Salad Sales", _INC, _SALES, False, "Bruschetta, caprese, Caesar salad, antipasti"),
    _m(_INCOME, "Dessert Sales", _INC, _SALES, False, "Tiramisu, panna cotta, gelato, cannoli"),
    _m(_INCOME, "Wine & Beverage Sales", _INC, _SALES, False, "Italian wines, espresso, limoncello"),
]
_ITALIAN_COGS = [
    _m(_COGS, "Pasta & Flour Cost", _COGS_T, _SUPPLIES, True, "Imported pasta, semolina, flour for fresh pasta"),
    _m(_COGS, "Cheese & Dairy Cost", _COGS_T, _SUPPLIES, False, "Parmesan, mozzarella, ricotta, cream, butter"),
    _m(_COGS, "Olive Oil & Import Cost", _COGS_T, _SUPPLIES, False, "Imported olive oil, balsamic, sun-dried tomatoes"),
    _m(_COGS, "Wine Cost", _COGS_T, _SUPPLIES, False, "Wine inventory for by-glass and bottle service"),
]

# QSR / Fast Food
_QSR_INCOME = [
    _m(_INCOME, "Counter Sales", _INC, _SALES, True, "Walk-in counter and takeaway orders"),
    _m(_INCOME, "Drive-Through Revenue", _INC, _SALES, False, "Drive-through lane orders"),
    _m(_INCOME, "Delivery Revenue", _INC, _SALES, False, "Own-rider and call-center delivery"),
    _m(_INCOME, "Marketplace Revenue", _INC, _SALES, False, "Foodpanda, Cheetay marketplace (gross)"),
    _m(_INCOME, "Combo Meal Sales", _INC, _SALES, False, "Combo/deal meals for tracking deal mix"),
    _m(_INCOME, "Beverage Sales", _INC, _SALES, False, "Soft drinks, shakes, juices"),
    _m(_INCOME, "Add-On & Sides Sales", _INC, _SALES, False, "Fries, sides, sauces, add-ons"),
]
_QSR_COGS = [
    _m(_COGS, "Food Cost", _COGS_T, _SUPPLIES, True, "Food ingredients, pre-processed items, frozen stock"),
    _m(_COGS, "Beverage Cost", _COGS_T, _SUPPLIES, False, "Beverage syrup, cups, lids, straws"),
    _m(_COGS, "Packaging Cost", _COGS_T, _SUPPLIES, False, "Boxes, bags, wraps, disposable packaging"),
]

# Cafe
_CAFE_INCOME = [
    _m(_INCOME, "Coffee & Tea Sales", _INC, _SALES, True, "Hot/cold coffee, chai, specialty drinks"),
    _m(_INCOME, "Pastry & Bakery Sales", _INC, _SALES, False, "Croissants, muffins, cakes, baked goods"),
    _m(_INCOME, "Sandwich & Light Meal Sales", _INC, _SALES, False, "Sandwiches, wraps, paninis, light meals"),
    _m(_INCOME, "Cold Beverage Sales", _INC, _SALES, False, "Iced drinks, smoothies, frappes, cold brew"),
    _m(_INCOME, "Retail Merchandise Sales", _INC, _SALES, False, "Coffee beans, mugs, branded merchandise"),
    _m(_INCOME, "Delivery Revenue", _INC, _SALES, False, "Delivery orders"),
]
_CAFE_COGS = [
    _m(_COGS, "Coffee & Tea Cost", _COGS_T, _SUPPLIES, True, "Beans, tea leaves, milk, syrups, cups"),
    _m(_COGS, "Bakery & Food Cost", _COGS_T, _SUPPLIES, False, "Bakery ingredients, sandwich fillings"),
    _m(_COGS, "Packaging Cost", _COGS_T, _SUPPLIES, False, "Takeaway cups, lids, sleeves, bags"),
]

# Fine Dining
_FINE_DINING_INCOME = [
    _m(_INCOME, "Tasting Menu Revenue", _INC, _SALES, True, "Multi-course tasting/degustation menus"),
    _m(_INCOME, "A La Carte Sales", _INC, _SALES, False, "Individual dish orders from main menu"),
    _m(_INCOME, "Wine & Sommelier Sales", _INC, _SALES, False, "Wine pairings, by-glass, bottle service"),
    _m(_INCOME, "Cocktail & Bar Sales", _INC, _SALES, False, "Craft cocktails, spirits, aperitifs, digestifs"),
    _m(_INCOME, "Private Dining Revenue", _INC, _SVC_FEE, False, "Private room hire and exclusive events"),
    _m(_INCOME, "Corkage Fee Revenue", _INC, _SVC_FEE, False, "Corkage fees for BYO wine"),
]
_FINE_DINING_COGS = [
    _m(_COGS, "Premium Ingredient Cost", _COGS_T, _SUPPLIES, True, "Imported proteins, truffles, foie gras, wagyu"),
    _m(_COGS, "Wine & Spirits Cost", _COGS_T, _SUPPLIES, False, "Wine inventory, spirits for bar program"),
    _m(_COGS, "Produce & Dairy Cost", _COGS_T, _SUPPLIES, False, "Organic vegetables, artisan cheese, cream, butter"),
    _m(_COGS, "Labor - Kitchen Brigade", _COGS_T, _LABOR_COGS, False, "Specialized chef wages (direct food cost)"),
]

# Buffet
_BUFFET_INCOME = [
    _m(_INCOME, "Buffet Revenue (Per Head)", _INC, _SALES, True, "Per-person buffet charges (adult/child)"),
    _m(_INCOME, "Premium Buffet Upgrade", _INC, _SALES, False, "Premium tier (seafood, steak upgrade)"),
    _m(_INCOME, "Beverage Sales", _INC, _SALES, False, "Drinks, juices, unlimited beverage packages"),
    _m(_INCOME, "Event Booking Revenue", _INC, _SALES, False, "Birthday, corporate event buffet bookings"),
    _m(_INCOME, "A La Carte Add-On Sales", _INC, _SALES, False, "Individual items ordered beyond buffet"),
]
_BUFFET_COGS = [
    _m(_COGS, "Food Cost (Buffet)", _COGS_T, _SUPPLIES, True, "All food for buffet stations (variable per head)"),
    _m(_COGS, "Food Waste & Spoilage", _COGS_T, _SUPPLIES, False, "Buffet waste — unconsumed food at close"),
    _m(_COGS, "Beverage Cost", _COGS_T, _SUPPLIES, False, "Drinks, juice, unlimited beverage stock"),
]

# Food Court Vendor
_FOOD_COURT_INCOME = [
    _m(_INCOME, "Counter Sales", _INC, _SALES, True, "Food court counter sales (primary channel)"),
    _m(_INCOME, "Combo Deal Sales", _INC, _SALES, False, "Meal deals and combo offers"),
    _m(_INCOME, "Beverage Sales", _INC, _SALES, False, "Drinks from own counter"),
]
_FOOD_COURT_COGS = [
    _m(_COGS, "Food Cost", _COGS_T, _SUPPLIES, True, "All food ingredients"),
    _m(_COGS, "Packaging Cost", _COGS_T, _SUPPLIES, False, "Trays, disposable utensils, napkins"),
]
_FOOD_COURT_EXPENSE = [
    _m(_EXPENSE, "Mall Rent / Commission", _EXP, _RENT, False, "Fixed rent or revenue-share to mall"),
    _m(_EXPENSE, "Common Area Maintenance", _EXP, _RENT, False, "CAM charges for shared food court area"),
]

# Cloud Kitchen
_CLOUD_KITCHEN_INCOME = [
    _m(_INCOME, "Brand A Revenue", _INC, _SALES, True, "Revenue from primary virtual brand"),
    _m(_INCOME, "Brand B Revenue", _INC, _SALES, False, "Revenue from second virtual brand"),
    _m(_INCOME, "Brand C Revenue", _INC, _SALES, False, "Revenue from third virtual brand"),
    _m(_INCOME, "Marketplace Revenue (Aggregated)", _INC, _SALES, False, "Total marketplace platform revenue (all brands)"),
    _m(_INCOME, "Direct Order Revenue", _INC, _SALES, False, "Website/app direct orders"),
]
_CLOUD_KITCHEN_COGS = [
    _m(_COGS, "Shared Kitchen Food Cost", _COGS_T, _SUPPLIES, True, "Shared ingredients across all brands"),
    _m(_COGS, "Brand-Specific Ingredient Cost", _COGS_T, _SUPPLIES, False, "Unique ingredients per brand"),
    _m(_COGS, "Packaging Cost (Multi-Brand)", _COGS_T, _SUPPLIES, False, "Brand-specific packaging for each virtual brand"),
]
_CLOUD_KITCHEN_EXPENSE = [
    _m(_EXPENSE, "Kitchen Rent", _EXP, _RENT, False, "Cloud kitchen facility rent"),
    _m(_EXPENSE, "Platform Commission (Multi)", _EXP, _COMMISSION, False, "Combined platform fees across all brands"),
    _m(_EXPENSE, "Virtual Brand Marketing", _EXP, _ADVERTISING, False, "Per-brand social media and platform advertising"),
]

# Food Truck
_FOOD_TRUCK_INCOME = [
    _m(_INCOME, "Food Sales", _INC, _SALES, True, "All food items from truck menu"),
    _m(_INCOME, "Beverage Sales", _INC, _SALES, False, "Drinks, water, canned beverages"),
    _m(_INCOME, "Event & Festival Revenue", _INC, _SALES, False, "Revenue from booked events and food festivals"),
]
_FOOD_TRUCK_COGS = [
    _m(_COGS, "Food Cost", _COGS_T, _SUPPLIES, True, "All food ingredients"),
    _m(_COGS, "Disposable & Packaging Cost", _COGS_T, _SUPPLIES, False, "Biodegradable containers, napkins, bags"),
]
_FOOD_TRUCK_EXPENSE = [
    _m(_EXPENSE, "Fuel & Vehicle Cost", _EXP, _TRAVEL, False, "Truck fuel, maintenance, parking fees"),
    _m(_EXPENSE, "Event & Permit Fees", _EXP, _MISC_EXP, False, "Location permits, festival stall fees, event booking"),
    _m(_EXPENSE, "Generator & Equipment", _EXP, _REPAIR, False, "Generator fuel, equipment maintenance"),
]

# Catering Company
_CATERING_INCOME = [
    _m(_INCOME, "Corporate Catering Revenue", _INC, _SALES, True, "Corporate events, meetings, office catering"),
    _m(_INCOME, "Wedding & Event Revenue", _INC, _SALES, False, "Wedding, engagement, large-scale events"),
    _m(_INCOME, "Per-Head Catering Revenue", _INC, _SALES, False, "Per-person pricing for standard menus"),
    _m(_INCOME, "Custom Menu Revenue", _INC, _SALES, False, "Custom/bespoke menu design and execution"),
    _m(_INCOME, "Equipment Rental Income", _INC, _SVC_FEE, False, "Chafing dish, crockery, linen rental"),
    _m(_INCOME, "Setup & Staffing Fee", _INC, _SVC_FEE, False, "Event setup, serving staff hire charges"),
]
_CATERING_COGS = [
    _m(_COGS, "Catering Food Cost", _COGS_T, _SUPPLIES, True, "Bulk ingredients for events"),
    _m(_COGS, "Catering Labor Cost", _COGS_T, _LABOR_COGS, False, "Hired chefs and serving staff per event"),
    _m(_COGS, "Transport & Logistics", _COGS_T, _SUPPLIES, False, "Food transport, ice, hot-holding equipment"),
    _m(_COGS, "Disposable & Decor Cost", _COGS_T, _SUPPLIES, False, "Disposables, table decor, floral for events"),
]

# Hotel Restaurant
_HOTEL_INCOME = [
    _m(_INCOME, "Restaurant Dine-In Revenue", _INC, _SALES, True, "Main restaurant dine-in sales"),
    _m(_INCOME, "Lobby Lounge Revenue", _INC, _SALES, False, "Lobby cafe/lounge food & beverage"),
    _m(_INCOME, "Pool Bar Revenue", _INC, _SALES, False, "Pool-side bar and snack service"),
    _m(_INCOME, "Breakfast Buffet Revenue", _INC, _SALES, False, "Breakfast buffet (included + walk-in)"),
    _m(_INCOME, "Takeaway Revenue", _INC, _SALES, False, "External takeaway orders"),
]
_HOTEL_COGS = [
    _m(_COGS, "Food Cost (All Outlets)", _COGS_T, _SUPPLIES, True, "Combined food cost across all F&B outlets"),
    _m(_COGS, "Beverage & Bar Cost", _COGS_T, _SUPPLIES, False, "Spirits, wine, mixers across all bars"),
    _m(_COGS, "Breakfast Buffet Cost", _COGS_T, _SUPPLIES, False, "Dedicated breakfast station ingredients"),
]

# Bar & Lounge
_BAR_INCOME = [
    _m(_INCOME, "Bar & Spirits Sales", _INC, _SALES, True, "Primary: cocktails, spirits, beer"),
    _m(_INCOME, "Food & Snack Sales", _INC, _SALES, False, "Bar food, appetizers, sharing platters"),
    _m(_INCOME, "Hookah / Shisha Revenue", _INC, _SALES, False, "Hookah service and flavors"),
    _m(_INCOME, "Cover Charge / Entry Fee", _INC, _SVC_FEE, False, "Door charge, event nights, DJ nights"),
    _m(_INCOME, "Private Event Revenue", _INC, _SVC_FEE, False, "Private party and VIP area bookings"),
]
_BAR_COGS = [
    _m(_COGS, "Spirits & Beverage Cost", _COGS_T, _SUPPLIES, True, "Alcohol, mixers, garnishes, ice"),
    _m(_COGS, "Food Cost", _COGS_T, _SUPPLIES, False, "Bar food ingredients"),
    _m(_COGS, "Hookah & Consumable Cost", _COGS_T, _SUPPLIES, False, "Hookah flavors, coals, hoses, foil"),
]
_BAR_EXPENSE = [
    _m(_EXPENSE, "DJ & Entertainment", _EXP, _ENTERTAINMENT, False, "DJ fees, live music, sound system"),
    _m(_EXPENSE, "Liquor License & Compliance", _EXP, _LEGAL, False, "License fees, compliance costs"),
]

# Juice Bar
_JUICE_INCOME = [
    _m(_INCOME, "Fresh Juice Sales", _INC, _SALES, True, "Fresh-pressed juices, citrus, seasonal"),
    _m(_INCOME, "Smoothie & Bowl Sales", _INC, _SALES, False, "Smoothies, acai bowls, protein shakes"),
    _m(_INCOME, "Health Shot Sales", _INC, _SALES, False, "Ginger, wheatgrass, immunity shots"),
    _m(_INCOME, "Snack & Light Meal Sales", _INC, _SALES, False, "Salads, wraps, energy bars"),
    _m(_INCOME, "Subscription Revenue", _INC, _SVC_FEE, False, "Monthly juice/smoothie subscriptions"),
]
_JUICE_COGS = [
    _m(_COGS, "Fresh Produce Cost", _COGS_T, _SUPPLIES, True, "Fruits, vegetables (high perishability)"),
    _m(_COGS, "Supplements & Add-In Cost", _COGS_T, _SUPPLIES, False, "Protein powder, chia, flaxseed, honey"),
    _m(_COGS, "Cup & Packaging Cost", _COGS_T, _SUPPLIES, False, "Eco-friendly cups, straws, bowls"),
]

# Ice Cream Parlor
_ICE_CREAM_INCOME = [
    _m(_INCOME, "Ice Cream & Gelato Sales", _INC, _SALES, True, "Scoops, cones, cups, kulfi"),
    _m(_INCOME, "Sundae & Specialty Sales", _INC, _SALES, False, "Sundaes, banana split, specialty creations"),
    _m(_INCOME, "Shake & Float Sales", _INC, _SALES, False, "Milkshakes, ice cream floats, blended drinks"),
    _m(_INCOME, "Waffle & Topping Sales", _INC, _SALES, False, "Waffles, crepes, brownie à la mode"),
    _m(_INCOME, "Take-Home Tub Sales", _INC, _SALES, False, "Pint/quart tubs for home consumption"),
]
_ICE_CREAM_COGS = [
    _m(_COGS, "Ice Cream & Dairy Cost", _COGS_T, _SUPPLIES, True, "Cream, milk, sugar, flavoring, stabilizers"),
    _m(_COGS, "Topping & Sauce Cost", _COGS_T, _SUPPLIES, False, "Chocolate, sprinkles, fruit, nuts, whipped cream"),
    _m(_COGS, "Cone & Packaging Cost", _COGS_T, _SUPPLIES, False, "Waffle cones, cups, spoons, tub containers"),
]

# Bakery (Wholesale)
_BAKERY_WHOLESALE_INCOME = [
    _m(_INCOME, "Wholesale Bread Revenue", _INC, _SALES, True, "B2B bread supply to restaurants/hotels"),
    _m(_INCOME, "Wholesale Pastry Revenue", _INC, _SALES, False, "B2B pastries, croissants, Danish supply"),
    _m(_INCOME, "Custom Cake Revenue", _INC, _SALES, False, "Custom cakes, wedding cakes, corporate"),
    _m(_INCOME, "Retail Counter Sales", _INC, _SALES, False, "Walk-in retail from bakery counter"),
    _m(_INCOME, "Seasonal & Holiday Revenue", _INC, _SALES, False, "Eid, Christmas, Valentine's specialty items"),
]
_BAKERY_WHOLESALE_COGS = [
    _m(_COGS, "Flour & Grain Cost", _COGS_T, _SUPPLIES, True, "Flour, yeast, baking powder (bulk purchase)"),
    _m(_COGS, "Dairy & Egg Cost", _COGS_T, _SUPPLIES, False, "Butter, cream, eggs, milk"),
    _m(_COGS, "Chocolate & Specialty Cost", _COGS_T, _SUPPLIES, False, "Chocolate, fondant, food coloring, vanilla"),
    _m(_COGS, "Packaging & Box Cost", _COGS_T, _SUPPLIES, False, "Cake boxes, bread bags, wholesale packaging"),
]

# Breakfast Spot
_BREAKFAST_INCOME = [
    _m(_INCOME, "Halwa Puri Sales", _INC, _SALES, True, "Halwa puri, channay (primary morning item)"),
    _m(_INCOME, "Paratha & Egg Sales", _INC, _SALES, False, "Paratha, anda paratha, omelette"),
    _m(_INCOME, "Nihari & Paye Sales", _INC, _SALES, False, "Nihari, paye (morning specialties)"),
    _m(_INCOME, "Chai & Lassi Sales", _INC, _SALES, False, "Doodh patti, kashmiri chai, lassi"),
    _m(_INCOME, "Takeaway Sales", _INC, _SALES, False, "Morning rush takeaway orders"),
]
_BREAKFAST_COGS = [
    _m(_COGS, "Flour & Oil Cost", _COGS_T, _SUPPLIES, True, "Flour for puri/paratha, ghee, cooking oil"),
    _m(_COGS, "Chickpea & Lentil Cost", _COGS_T, _SUPPLIES, False, "Channay, daal, dried legumes"),
    _m(_COGS, "Dairy & Egg Cost", _COGS_T, _SUPPLIES, False, "Milk, eggs, yogurt for lassi"),
]

# Dessert Parlor
_DESSERT_INCOME = [
    _m(_INCOME, "Waffle & Crepe Sales", _INC, _SALES, True, "Belgian waffles, crepes, pancakes"),
    _m(_INCOME, "Cake & Pastry Sales", _INC, _SALES, False, "Cheesecake, brownies, pastries by slice"),
    _m(_INCOME, "Beverage Sales", _INC, _SALES, False, "Hot chocolate, specialty coffee, shakes"),
    _m(_INCOME, "Delivery Revenue", _INC, _SALES, False, "Dessert delivery (Instagram-driven orders)"),
]
_DESSERT_COGS = [
    _m(_COGS, "Batter & Flour Cost", _COGS_T, _SUPPLIES, True, "Waffle mix, crepe batter, flour, sugar"),
    _m(_COGS, "Chocolate & Topping Cost", _COGS_T, _SUPPLIES, False, "Nutella, chocolate sauce, whipped cream, fruit"),
    _m(_COGS, "Packaging Cost", _COGS_T, _SUPPLIES, False, "Dessert boxes, Instagram-worthy packaging"),
]

# Tea House
_TEA_INCOME = [
    _m(_INCOME, "Tea & Chai Sales", _INC, _SALES, True, "Doodh patti, kashmiri chai, green tea, karak chai"),
    _m(_INCOME, "Snack Sales", _INC, _SALES, False, "Bun kebab, samosa, pakora, cake rusk"),
    _m(_INCOME, "Specialty Drink Sales", _INC, _SALES, False, "Pink chai, matcha, herbal infusions"),
]
_TEA_COGS = [
    _m(_COGS, "Tea & Milk Cost", _COGS_T, _SUPPLIES, True, "Tea leaves, milk, sugar, cardamom"),
    _m(_COGS, "Snack Ingredient Cost", _COGS_T, _SUPPLIES, False, "Flour, meat, vegetables for snacks"),
]

# Shawarma / Wrap Shop
_SHAWARMA_INCOME = [
    _m(_INCOME, "Shawarma & Wrap Sales", _INC, _SALES, True, "Chicken/beef shawarma, doner, wraps"),
    _m(_INCOME, "Platter & Plate Sales", _INC, _SALES, False, "Shawarma plate, rice plate, mixed grill"),
    _m(_INCOME, "Fries & Side Sales", _INC, _SALES, False, "Fries, hummus, garlic sauce, fattoush"),
    _m(_INCOME, "Beverage Sales", _INC, _SALES, False, "Drinks, ayran, jallab"),
    _m(_INCOME, "Delivery Revenue", _INC, _SALES, False, "Late-night delivery orders"),
]
_SHAWARMA_COGS = [
    _m(_COGS, "Meat & Rotisserie Cost", _COGS_T, _SUPPLIES, True, "Chicken thighs, beef for spit, marinade"),
    _m(_COGS, "Bread & Wrap Cost", _COGS_T, _SUPPLIES, False, "Arabic bread, tortillas, pita"),
    _m(_COGS, "Sauce & Condiment Cost", _COGS_T, _SUPPLIES, False, "Garlic sauce, tahini, pickles, vegetables"),
]

# Fried Chicken Chain
_FRIED_CHICKEN_INCOME = [
    _m(_INCOME, "Fried Chicken Sales", _INC, _SALES, True, "Fried chicken pieces, strips, wings"),
    _m(_INCOME, "Burger & Sandwich Sales", _INC, _SALES, False, "Zinger, crispy burger, wraps"),
    _m(_INCOME, "Family Bucket Sales", _INC, _SALES, False, "Family meals, sharing buckets"),
    _m(_INCOME, "Sides & Beverage Sales", _INC, _SALES, False, "Fries, coleslaw, corn, drinks"),
    _m(_INCOME, "Kids Meal Sales", _INC, _SALES, False, "Kids meals with toy/activity"),
    _m(_INCOME, "Delivery Revenue", _INC, _SALES, False, "Delivery channel orders"),
]
_FRIED_CHICKEN_COGS = [
    _m(_COGS, "Chicken Cost", _COGS_T, _SUPPLIES, True, "Fresh/frozen chicken (largest cost item)"),
    _m(_COGS, "Breading & Marinade Cost", _COGS_T, _SUPPLIES, False, "Flour, spice mix, marinade, buttermilk"),
    _m(_COGS, "Frying Oil Cost", _COGS_T, _SUPPLIES, False, "Cooking oil (high consumption, regular change)"),
    _m(_COGS, "Packaging Cost", _COGS_T, _SUPPLIES, False, "Buckets, boxes, bags, cups"),
]

# Subscription Meal Service
_SUBSCRIPTION_INCOME = [
    _m(_INCOME, "Weekly Subscription Revenue", _INC, _SALES, True, "Weekly tiffin/meal plan subscriptions"),
    _m(_INCOME, "Monthly Subscription Revenue", _INC, _SALES, False, "Monthly meal plan recurring revenue"),
    _m(_INCOME, "One-Time Meal Order Revenue", _INC, _SALES, False, "Non-subscription individual orders"),
    _m(_INCOME, "Corporate Meal Plan Revenue", _INC, _SALES, False, "Office/corporate bulk meal subscriptions"),
]
_SUBSCRIPTION_COGS = [
    _m(_COGS, "Meal Prep Food Cost", _COGS_T, _SUPPLIES, True, "Ingredients for batch meal preparation"),
    _m(_COGS, "Container & Packaging Cost", _COGS_T, _SUPPLIES, False, "Meal prep containers, insulated bags, labels"),
    _m(_COGS, "Route Delivery Cost", _COGS_T, _SUPPLIES, False, "Fuel, vehicle for route-based delivery"),
]
_SUBSCRIPTION_LIABILITY = [
    _m(_OCL, "Deferred Subscription Revenue", _OCL_T, _OCL_SUB, False,
       "Prepaid subscription revenue not yet earned (delivered)"),
]

# Resort Restaurant
_RESORT_INCOME = [
    _m(_INCOME, "Main Restaurant Revenue", _INC, _SALES, True, "Fine dining main restaurant"),
    _m(_INCOME, "Beach / Pool Bar Revenue", _INC, _SALES, False, "Pool-side and beach bar F&B"),
    _m(_INCOME, "Room Service Revenue", _INC, _SALES, False, "In-room dining charges"),
    _m(_INCOME, "All-Inclusive Package F&B", _INC, _SALES, False, "F&B portion of all-inclusive packages"),
    _m(_INCOME, "Event & Wedding F&B Revenue", _INC, _SALES, False, "Destination wedding and event catering"),
    _m(_INCOME, "Spa Cafe Revenue", _INC, _SALES, False, "Light meals and juices at spa"),
]
_RESORT_COGS = [
    _m(_COGS, "Food Cost (All Outlets)", _COGS_T, _SUPPLIES, True, "Combined food across all resort outlets"),
    _m(_COGS, "Beverage & Bar Cost", _COGS_T, _SUPPLIES, False, "Alcohol, juices, cocktail ingredients"),
    _m(_COGS, "Import & Premium Ingredient Cost", _COGS_T, _SUPPLIES, False, "Imported items for international guests"),
]
_RESORT_EXTRAS = [
    _m(_OCL, "Guest Folio Receivable", _OCA, _OCA_SUB, False,
       "F&B charges posted to room but not yet settled at checkout"),
    _m(_INCOME, "Foreign Currency Revenue", _INC, _OTHER_INC, False,
       "Revenue received in foreign currency (USD/EUR) from international guests"),
]


# =========================================================================
# COMPOSE ALL 40 TEMPLATES
# =========================================================================
def _t(name: str, description: str, income: list, cogs: list,
       tax: list, bank: list | None = None, delivery: list | None = None,
       extra_expense: list | None = None, extra_liability: list | None = None,
       svc_charge: bool = False) -> dict[str, Any]:
    """Compose a complete template from blocks."""
    mappings: list[dict] = []
    mappings.extend(income)
    if svc_charge:
        mappings.extend(_SVC_CHARGE_INCOME)
    mappings.extend(cogs)
    mappings.extend(tax)
    mappings.extend(bank or _BASE_BANK)
    if delivery:
        mappings.extend(delivery)
    if extra_expense:
        mappings.extend(extra_expense)
    mappings.extend(_BASE_EXPENSE)
    mappings.extend(_BASE_LIABILITY)
    if extra_liability:
        mappings.extend(extra_liability)
    return {"name": name, "description": description, "mappings": mappings}


MAPPING_TEMPLATES: dict[str, dict[str, Any]] = {

    # =====================================================================
    # PAKISTANI CUISINE (8)
    # =====================================================================

    "pakistani_restaurant": _t(
        "Pakistani Restaurant (Full-Service)",
        "Full-service Pakistani restaurant with BBQ, Karahi, Biryani, Naan, Desserts. "
        "FBR GST 17% + PRA PST 16%. JazzCash/Easypaisa. Foodpanda. Multi-channel.",
        _PAKISTANI_INCOME, _PAKISTANI_COGS, _PAK_PUNJAB_TAX,
        _BASE_BANK + _PAK_MOBILE, _PAK_DELIVERY, svc_charge=True,
    ),

    "pakistani_bbq_specialist": _t(
        "Pakistani BBQ & Tikka House",
        "BBQ-focused restaurant: tikka, sajji, seekh kebab, chapli. Heavy charcoal COGS. "
        "Takeaway-dominant. Dawat catering. FBR + PRA tax.",
        _BBQ_INCOME, _BBQ_COGS, _PAK_PUNJAB_TAX,
        _BASE_BANK + _PAK_MOBILE, _PAK_DELIVERY,
    ),

    "biryani_house": _t(
        "Biryani House / Rice Specialist",
        "Biryani-focused chain. High-volume takeaway (60%+). Bulk rice/spice procurement. "
        "FBR + PRA. Delivery-heavy with Foodpanda.",
        _BIRYANI_INCOME, _BIRYANI_COGS, _PAK_PUNJAB_TAX,
        _BASE_BANK + _PAK_MOBILE, _PAK_DELIVERY,
    ),

    "pakistani_street_food": _t(
        "Pakistani Street Food / Dhaba",
        "Informal dhaba or street food stall: chaat, gol gappay, roll paratha, fries. "
        "Cash-heavy, minimal card. Low overhead. FBR + PRA.",
        _STREET_FOOD_INCOME, _STREET_FOOD_COGS, _PAK_PUNJAB_TAX,
        _BASE_BANK + _PAK_MOBILE,
    ),

    "nihari_paye_house": _t(
        "Nihari & Paye House (Traditional Breakfast)",
        "Traditional Pakistani breakfast specialty: nihari, paye, haleem, siri. "
        "Early morning hours, single-category focus. Cash-dominant.",
        _NIHARI_INCOME, _NIHARI_COGS, _PAK_PUNJAB_TAX,
        _BASE_BANK + _PAK_MOBILE,
    ),

    "pakistani_sweets_bakery": _t(
        "Pakistani Sweets & Bakery (Mithai Shop)",
        "Mithai shop + bakery: laddu, barfi, jalebi, cakes, bread. Retail + wholesale. "
        "Eid/seasonal spikes. Custom orders. FBR + PRA.",
        _SWEETS_INCOME, _SWEETS_COGS, _PAK_PUNJAB_TAX,
        _BASE_BANK + _PAK_MOBILE, _PAK_DELIVERY,
    ),

    "karachi_seafood": _t(
        "Karachi Seafood Restaurant",
        "Sindh-based seafood: fish, prawn, crab. SRB tax (not PRA). Market-price items. "
        "Premium pricing. Variable daily COGS based on catch.",
        _SEAFOOD_INCOME, _SEAFOOD_COGS, _PAK_SINDH_TAX,
        _BASE_BANK + _PAK_MOBILE, _PAK_DELIVERY,
    ),

    "lahore_food_street": _t(
        "Lahore Food Street (Multi-Station)",
        "Open-air food street format: multiple cooking stations under one entity. "
        "BBQ station, karahi station, fry station. High foot traffic. FBR + PRA.",
        _FOOD_STREET_INCOME, _FOOD_STREET_COGS, _PAK_PUNJAB_TAX,
        _BASE_BANK + _PAK_MOBILE, _PAK_DELIVERY,
    ),

    # =====================================================================
    # INTERNATIONAL CUISINE (8)
    # =====================================================================

    "international_restaurant": _t(
        "International Restaurant (Continental/Fusion)",
        "Full-service international restaurant. VAT-based tax. Wine and bar program. "
        "Tip income (owner-retained model). Marketplace delivery.",
        [*_PAKISTANI_INCOME[:1],  # Food Sales as default
         _m(_INCOME, "Appetizer & Starter Sales", _INC, _SALES, False, "Soups, salads, starters"),
         _m(_INCOME, "Main Course Sales", _INC, _SALES, False, "Entrees and main dishes"),
         _m(_INCOME, "Dessert Sales", _INC, _SALES, False, "Desserts and sweet items"),
         _m(_INCOME, "Bar & Beverage Sales", _INC, _SALES, False, "Cocktails, mocktails, beverages"),
         _m(_INCOME, "Wine Sales", _INC, _SALES, False, "Wine by glass and bottle"),
         _m(_INCOME, "Takeaway Sales", _INC, _SALES, False, "Takeaway orders"),
         _m(_INCOME, "Catering & Events Revenue", _INC, _SALES, False, "Private events and catering"),
         _m(_INCOME, "Tip Income (Owner Retained)", _INC, _OTHER_INC, False, "Tips retained by business")],
        _PAKISTANI_COGS, _VAT_STANDARD,
        _BASE_BANK + _ONLINE_PAYMENT, _INTL_DELIVERY, svc_charge=True,
    ),

    "chinese_restaurant": _t(
        "Chinese / Pakistani-Chinese Restaurant",
        "Chinese and Pakistani-Chinese fusion. Manchurian, chowmein, fried rice, soups. "
        "Delivery-heavy. MSG-free options. FBR + PRA for Pakistan-based.",
        _CHINESE_INCOME, _CHINESE_COGS, _PAK_PUNJAB_TAX,
        _BASE_BANK + _PAK_MOBILE, _PAK_DELIVERY,
    ),

    "pizza_chain": _t(
        "Pizza Chain / Pizzeria",
        "Pizza franchise or independent. Delivery-first (50%+). Combo deals. "
        "Cheese/dough are dominant COGS. Dine-in + delivery + marketplace.",
        _PIZZA_INCOME, _PIZZA_COGS, _GENERIC_TAX,
        _BASE_BANK + _ONLINE_PAYMENT, _INTL_DELIVERY,
    ),

    "burger_joint": _t(
        "Burger Joint / American Fast Food",
        "Burger restaurant: beef/chicken burgers, fries, shakes. High customization. "
        "Combo meals. Delivery-friendly. Patty COGS dominant.",
        _BURGER_INCOME, _BURGER_COGS, _GENERIC_TAX,
        _BASE_BANK + _ONLINE_PAYMENT, _INTL_DELIVERY,
    ),

    "steakhouse": _t(
        "Steakhouse / Grill",
        "Premium steakhouse. Imported/aged beef. High-value COGS. Wine pairings. "
        "Service charge. Private dining. Minimal takeaway.",
        _STEAK_INCOME, _STEAK_COGS, _VAT_STANDARD,
        _BASE_BANK + _ONLINE_PAYMENT, svc_charge=True,
    ),

    "japanese_sushi": _t(
        "Japanese / Sushi Restaurant",
        "Sushi, sashimi, ramen, tempura. Imported fish COGS (premium). "
        "Bento boxes. Minimal delivery. VAT-based.",
        _JAPANESE_INCOME, _JAPANESE_COGS, _VAT_STANDARD,
        _BASE_BANK + _ONLINE_PAYMENT, _INTL_DELIVERY,
    ),

    "thai_restaurant": _t(
        "Thai Restaurant",
        "Thai cuisine: curries, pad thai, tom yum, satay. Coconut milk/lemongrass COGS. "
        "Moderate delivery. VAT-based.",
        _THAI_INCOME, _THAI_COGS, _VAT_STANDARD,
        _BASE_BANK + _ONLINE_PAYMENT, _INTL_DELIVERY,
    ),

    "italian_restaurant": _t(
        "Italian Restaurant / Trattoria",
        "Italian: pasta, wood-fire pizza, risotto. Imported cheese/olive oil COGS. "
        "Wine list. Dessert focus. Service charge.",
        _ITALIAN_INCOME, _ITALIAN_COGS, _VAT_STANDARD,
        _BASE_BANK + _ONLINE_PAYMENT, _INTL_DELIVERY, svc_charge=True,
    ),

    # =====================================================================
    # FORMAT / MODEL TYPES (10)
    # =====================================================================

    "qsr": _t(
        "Quick Service Restaurant (QSR)",
        "Fast food / QSR. Counter, drive-through, delivery. Combo meals. "
        "High volume, simplified COGS. FBR/PRA or VAT.",
        _QSR_INCOME, _QSR_COGS, _GENERIC_TAX,
        _BASE_BANK + _PAK_MOBILE, _PAK_DELIVERY,
    ),

    "cafe": _t(
        "Cafe / Coffee Shop",
        "Coffee shop: coffee, tea, pastries, light meals. Retail merchandise. "
        "Delivery via platforms.",
        _CAFE_INCOME, _CAFE_COGS, _GENERIC_TAX,
        _BASE_BANK + _ONLINE_PAYMENT, _INTL_DELIVERY,
    ),

    "fine_dining": _t(
        "Fine Dining Restaurant",
        "White tablecloth fine dining. Tasting menus, wine pairings, sommelier. "
        "Service charge 10-15%. Corkage fee. Private rooms. High COGS per cover.",
        _FINE_DINING_INCOME, _FINE_DINING_COGS, _VAT_STANDARD,
        _BASE_BANK + _ONLINE_PAYMENT, svc_charge=True,
    ),

    "buffet_restaurant": _t(
        "Buffet Restaurant",
        "All-you-can-eat buffet. Per-head pricing. Multiple food stations. "
        "High waste COGS. Event bookings.",
        _BUFFET_INCOME, _BUFFET_COGS, _GENERIC_TAX,
        _BASE_BANK + _ONLINE_PAYMENT, svc_charge=True,
    ),

    "food_court_vendor": _t(
        "Food Court Vendor",
        "Mall food court stall. Shared seating area. Mall rent or revenue-share commission. "
        "Limited menu. Peak-hour focused. No delivery.",
        _FOOD_COURT_INCOME, _FOOD_COURT_COGS, _GENERIC_TAX,
        extra_expense=_FOOD_COURT_EXPENSE,
    ),

    "cloud_kitchen": _t(
        "Cloud Kitchen / Ghost Kitchen",
        "Delivery-only, multi-brand from one kitchen. Each virtual brand tracked separately. "
        "High platform commission. Shared COGS allocation.",
        _CLOUD_KITCHEN_INCOME, _CLOUD_KITCHEN_COGS, _GENERIC_TAX,
        _BASE_BANK + _ONLINE_PAYMENT, _INTL_DELIVERY,
        extra_expense=_CLOUD_KITCHEN_EXPENSE,
    ),

    "food_truck": _t(
        "Food Truck / Mobile Kitchen",
        "Mobile food operation. Event fees, location permits. Limited menu. "
        "Cash-heavy. Fuel expense. No fixed dine-in.",
        _FOOD_TRUCK_INCOME, _FOOD_TRUCK_COGS, _GENERIC_TAX,
        extra_expense=_FOOD_TRUCK_EXPENSE,
    ),

    "catering_company": _t(
        "Catering Company (Events Only)",
        "Events-only catering. Per-head/per-event pricing. Advance deposits. "
        "Equipment rental. Hired event staff. No walk-in storefront.",
        _CATERING_INCOME, _CATERING_COGS, _GENERIC_TAX,
        _BASE_BANK + _ONLINE_PAYMENT,
    ),

    "hotel_restaurant": _t(
        "Hotel Restaurant (Multi-Outlet)",
        "Hotel F&B operation. Main restaurant, lobby lounge, pool bar, room service. "
        "Banquet halls. Minibar. Room-charge posting. Conference F&B.",
        _HOTEL_INCOME, _HOTEL_COGS, _VAT_STANDARD,
        _BASE_BANK + _ONLINE_PAYMENT, svc_charge=True,
        extra_expense=_HOTEL_EXTRAS[:3],  # room service, banquet, minibar as income already
        extra_liability=[*_HOTEL_EXTRAS[3:]],  # room charge receivable
    ),

    "bar_lounge": _t(
        "Bar & Lounge",
        "Alcohol-primary, food secondary. Hookah/shisha. DJ/entertainment. "
        "Cover charge. Happy hour pricing. VIP bookings.",
        _BAR_INCOME, _BAR_COGS, _VAT_STANDARD,
        _BASE_BANK + _ONLINE_PAYMENT,
        extra_expense=_BAR_EXPENSE, svc_charge=True,
    ),

    # =====================================================================
    # SPECIALTY (8)
    # =====================================================================

    "juice_bar": _t(
        "Juice Bar / Smoothie Shop",
        "Fresh juice, smoothies, acai bowls, health shots. High perishable produce COGS. "
        "Subscription memberships. Eco-friendly packaging.",
        _JUICE_INCOME, _JUICE_COGS, _GENERIC_TAX,
        _BASE_BANK + _ONLINE_PAYMENT, _INTL_DELIVERY,
    ),

    "ice_cream_parlor": _t(
        "Ice Cream / Gelato / Kulfi Parlor",
        "Ice cream, gelato, kulfi. Scoops, sundaes, shakes. Seasonal demand. "
        "Take-home tubs. Waffle cones. Low delivery.",
        _ICE_CREAM_INCOME, _ICE_CREAM_COGS, _GENERIC_TAX,
        _BASE_BANK + _PAK_MOBILE,
    ),

    "bakery_wholesale": _t(
        "Bakery (Wholesale + Retail)",
        "Production bakery: wholesale B2B to hotels/restaurants + retail counter. "
        "Custom cakes. Seasonal items. High flour/dairy COGS.",
        _BAKERY_WHOLESALE_INCOME, _BAKERY_WHOLESALE_COGS, _GENERIC_TAX,
        _BASE_BANK + _ONLINE_PAYMENT,
    ),

    "breakfast_spot": _t(
        "Breakfast / Nashta Spot",
        "Pakistani breakfast: halwa puri, channay, paratha, nihari. "
        "Morning-only hours (5am-12pm). Weekend rush. Cash-dominant.",
        _BREAKFAST_INCOME, _BREAKFAST_COGS, _PAK_PUNJAB_TAX,
        _BASE_BANK + _PAK_MOBILE,
    ),

    "dessert_parlor": _t(
        "Dessert Parlor / Sweet Cafe",
        "Desserts only: waffles, crepes, cheesecake, brownies. Instagram-driven. "
        "Low savory COGS. Delivery via marketplace. Premium packaging.",
        _DESSERT_INCOME, _DESSERT_COGS, _GENERIC_TAX,
        _BASE_BANK + _ONLINE_PAYMENT, _INTL_DELIVERY,
    ),

    "tea_house": _t(
        "Tea House / Chai Cafe",
        "Doodh patti, kashmiri chai, green tea specialist. Light snacks. "
        "Low COGS. High margin. Social gathering spot.",
        _TEA_INCOME, _TEA_COGS, _PAK_PUNJAB_TAX,
        _BASE_BANK + _PAK_MOBILE,
    ),

    "shawarma_wrap_shop": _t(
        "Shawarma & Wrap Shop",
        "Shawarma, doner, wraps. Rotisserie equipment. Late-night hours. "
        "Delivery-heavy. Quick service. FBR + PRA.",
        _SHAWARMA_INCOME, _SHAWARMA_COGS, _PAK_PUNJAB_TAX,
        _BASE_BANK + _PAK_MOBILE, _PAK_DELIVERY,
    ),

    "fried_chicken_chain": _t(
        "Fried Chicken Chain",
        "Fried chicken: pieces, burgers, family buckets. Kids meals. "
        "Chicken and frying oil dominant COGS. High delivery volume.",
        _FRIED_CHICKEN_INCOME, _FRIED_CHICKEN_COGS, _GENERIC_TAX,
        _BASE_BANK + _ONLINE_PAYMENT, _INTL_DELIVERY,
    ),

    # =====================================================================
    # BUSINESS COMPLEXITY (6)
    # =====================================================================

    "multi_branch_chain": _t(
        "Multi-Branch Restaurant Chain (10+ Locations)",
        "Multi-location chain. Branch-level tracking via QB Classes. Central kitchen. "
        "Consolidated P&L. Inter-branch transfers. Bulk procurement.",
        [*_PAKISTANI_INCOME,
         _m(_INCOME, "Central Kitchen Revenue", _INC, _SALES, False, "Revenue from central kitchen to branches"),
         _m(_INCOME, "Inter-Branch Transfer Revenue", _INC, _OTHER_INC, False, "Internal transfers between locations")],
        [*_PAKISTANI_COGS,
         _m(_COGS, "Central Kitchen Cost", _COGS_T, _SUPPLIES, False, "Central commissary ingredient cost"),
         _m(_COGS, "Inter-Branch Transfer Cost", _COGS_T, _SUPPLIES, False, "Cost of goods transferred between branches")],
        _PAK_PUNJAB_TAX,
        _BASE_BANK + _PAK_MOBILE, _PAK_DELIVERY, svc_charge=True,
    ),

    "franchise_operation": _t(
        "Franchise Operation",
        "Franchise model. Royalty fees (5-8%), marketing fund (2-3%), brand license. "
        "Territory fees. Franchisor reporting. FBR + PRA.",
        _QSR_INCOME, _QSR_COGS, _PAK_PUNJAB_TAX,
        _BASE_BANK + _PAK_MOBILE, _PAK_DELIVERY,
        extra_expense=_FRANCHISE_EXPENSE,
    ),

    "multi_brand_operator": _t(
        "Multi-Brand Operator (3+ Brands)",
        "Runs multiple restaurant brands from shared infrastructure. "
        "Separate P&L per brand. Shared overhead allocation. Combined COGS purchasing.",
        _CLOUD_KITCHEN_INCOME, _CLOUD_KITCHEN_COGS, _GENERIC_TAX,
        _BASE_BANK + _ONLINE_PAYMENT, _INTL_DELIVERY,
        extra_expense=[
            _m(_EXPENSE, "Shared Overhead Allocation", _EXP, _RENT, False, "Rent/utility allocation across brands"),
            _m(_EXPENSE, "Brand-Specific Marketing", _EXP, _ADVERTISING, False, "Per-brand marketing spend"),
            *_CLOUD_KITCHEN_EXPENSE,
        ],
    ),

    "subscription_meal_service": _t(
        "Subscription Meal / Tiffin Service",
        "Weekly/monthly meal subscriptions. Tiffin delivery. Route-based logistics. "
        "Deferred revenue for prepaid plans. Corporate meal programs.",
        _SUBSCRIPTION_INCOME, _SUBSCRIPTION_COGS, _GENERIC_TAX,
        _BASE_BANK + _ONLINE_PAYMENT,
        extra_liability=_SUBSCRIPTION_LIABILITY,
    ),

    "marketplace_heavy": _t(
        "Marketplace-Heavy Restaurant (60%+ Delivery Platforms)",
        "Highly dependent on Foodpanda, Cheetay, UberEats. Multi-platform commission tracking. "
        "Platform-specific settlement accounts. Minimal dine-in.",
        [_m(_INCOME, "Foodpanda Revenue", _INC, _SALES, True, "Foodpanda orders (gross, before commission)"),
         _m(_INCOME, "Cheetay Revenue", _INC, _SALES, False, "Cheetay orders (gross)"),
         _m(_INCOME, "UberEats Revenue", _INC, _SALES, False, "UberEats orders (gross)"),
         _m(_INCOME, "Direct Order Revenue", _INC, _SALES, False, "Own website/app/phone orders"),
         _m(_INCOME, "Walk-In Revenue", _INC, _SALES, False, "Minimal walk-in/takeaway")],
        [_m(_COGS, "Food Cost", _COGS_T, _SUPPLIES, True, "All food ingredients"),
         _m(_COGS, "Packaging Cost (Platform-Branded)", _COGS_T, _SUPPLIES, False, "Platform-specific packaging requirements")],
        _PAK_PUNJAB_TAX,
        [*_BASE_BANK, *_PAK_MOBILE,
         _m(_BANK, "Foodpanda Settlement A/C", _OCA, _OCA_SUB, False, "Foodpanda weekly payout receivable"),
         _m(_BANK, "Cheetay Settlement A/C", _OCA, _OCA_SUB, False, "Cheetay payout receivable"),
         _m(_BANK, "UberEats Settlement A/C", _OCA, _OCA_SUB, False, "UberEats payout receivable")],
        extra_expense=[
            _m(_PLATFORM, "Foodpanda Commission", _EXP, _COMMISSION, True, "Foodpanda commission (25-35%)"),
            _m(_EXPENSE, "Cheetay Commission", _EXP, _COMMISSION, False, "Cheetay commission per order"),
            _m(_EXPENSE, "UberEats Commission", _EXP, _COMMISSION, False, "UberEats commission per order"),
            _m(_EXPENSE, "Platform Marketing Spend", _EXP, _ADVERTISING, False, "Promoted listings on delivery platforms"),
            _m(_DELIVERY, "Delivery Expense", _EXP, _TRAVEL, True, "Own delivery rider costs"),
        ],
    ),

    "resort_restaurant": _t(
        "Resort / Club Restaurant",
        "Resort or country club F&B. Pool bar, beach restaurant, room service. "
        "Package inclusions. International guests (multi-currency). Event venue.",
        _RESORT_INCOME, _RESORT_COGS, _UAE_TAX,
        _BASE_BANK + _ONLINE_PAYMENT, svc_charge=True,
        extra_liability=_RESORT_EXTRAS,
    ),

    # =====================================================================
    # MULTI-FRANCHISE COMPLEX (1)
    # =====================================================================

    "multi_franchise_pakistani": _t(
        "Multi-Franchise Pakistani Restaurant (5 Branches, Central Kitchen)",
        "Multi-franchise operation across Punjab cities. Per-branch revenue "
        "tracking via QB Classes. Central kitchen commissary. Inter-branch "
        "transfers. Franchise royalty (6%) and marketing fund (3%). "
        "Multi-province tax (FBR + PRA). Consolidated and per-branch P&L.",
        # --- Income: per-branch + central kitchen + franchise ---
        [_m(_INCOME, "Gulberg Branch Revenue", _INC, _SALES, True,
            "Revenue from Gulberg (Lahore) flagship branch"),
         _m(_INCOME, "DHA Branch Revenue", _INC, _SALES, False,
            "Revenue from DHA (Lahore) branch"),
         _m(_INCOME, "Johar Town Branch Revenue", _INC, _SALES, False,
            "Revenue from Johar Town (Lahore) branch"),
         _m(_INCOME, "Model Town Branch Revenue", _INC, _SALES, False,
            "Revenue from Model Town (Lahore) branch"),
         _m(_INCOME, "Airport Branch Revenue", _INC, _SALES, False,
            "Revenue from Allama Iqbal Airport branch"),
         _m(_INCOME, "Central Kitchen Revenue", _INC, _SALES, False,
            "Revenue from central kitchen supplying branches"),
         _m(_INCOME, "Inter-Branch Transfer Revenue", _INC, _OTHER_INC, False,
            "Internal revenue from inter-branch stock transfers"),
         _m(_INCOME, "Franchise Fee Income", _INC, _SVC_FEE, False,
            "Initial franchise fees from new franchisees"),
         _m(_INCOME, "Biryani & Rice Sales", _INC, _SALES, False,
            "Biryani, pulao, rice dishes (all branches)"),
         _m(_INCOME, "BBQ & Grill Sales", _INC, _SALES, False,
            "Tikka, seekh kebab, boti (all branches)"),
         _m(_INCOME, "Karahi & Curry Sales", _INC, _SALES, False,
            "Karahi, handi, salan (all branches)"),
         _m(_INCOME, "Beverage Sales", _INC, _SALES, False,
            "Drinks, lassi, chai (all branches)"),
         _m(_INCOME, "Naan & Bread Sales", _INC, _SALES, False,
            "Naan, roti, paratha (all branches)"),
         _m(_INCOME, "Dessert Sales", _INC, _SALES, False,
            "Kheer, gulab jamun, halwa (all branches)"),
         _m(_INCOME, "Takeaway Sales", _INC, _SALES, False,
            "Takeaway/parcel from all branches"),
         _m(_INCOME, "Delivery Revenue", _INC, _SALES, False,
            "Call center and delivery orders"),
         _m(_INCOME, "Foodpanda Revenue", _INC, _SALES, False,
            "Foodpanda marketplace orders (gross before commission)")],
        # --- COGS ---
        [_m(_COGS, "Food Cost", _COGS_T, _SUPPLIES, True,
            "Meat, vegetables, spices, flour, oil (all branches)"),
         _m(_COGS, "Beverage Cost", _COGS_T, _SUPPLIES, False,
            "Soft drinks, juices, milk, tea (all branches)"),
         _m(_COGS, "Packaging Cost", _COGS_T, _SUPPLIES, False,
            "Takeaway containers, bags (all branches)"),
         _m(_COGS, "Central Kitchen Cost", _COGS_T, _SUPPLIES, False,
            "Central commissary ingredient and prep cost"),
         _m(_COGS, "Inter-Branch Transfer Cost", _COGS_T, _SUPPLIES, False,
            "Cost of goods transferred between branches"),
         _m(_COGS, "Commissary Allocation", _COGS_T, _SUPPLIES, False,
            "Central kitchen overhead allocated to branches")],
        # --- Tax: multi-province ---
        [_m(_TAX, "FBR GST Payable (17%)", _OCL_T, _OCL_SUB, True,
            "Federal Board of Revenue GST — 17% (all branches)"),
         _m(_TAX, "PRA PST Payable (16%)", _OCL_T, _OCL_SUB, False,
            "Punjab Revenue Authority PST — 16% (Lahore branches)"),
         _m(_TAX, "SRB SST Payable (13%)", _OCL_T, _OCL_SUB, False,
            "Sindh Revenue Board SST — 13% (if Karachi expansion)")],
        # --- Bank: per-branch + corporate + mobile + platform ---
        [_m(_BANK, "Gulberg Cash Register", _BANK_T, _CASH_HAND, True,
            "Cash drawer at Gulberg branch"),
         _m(_BANK, "DHA Cash Register", _BANK_T, _CASH_HAND, False,
            "Cash drawer at DHA branch"),
         _m(_BANK, "Johar Town Cash Register", _BANK_T, _CASH_HAND, False,
            "Cash drawer at Johar Town branch"),
         _m(_BANK, "Model Town Cash Register", _BANK_T, _CASH_HAND, False,
            "Cash drawer at Model Town branch"),
         _m(_BANK, "Airport Cash Register", _BANK_T, _CASH_HAND, False,
            "Cash drawer at Airport branch"),
         _m(_BANK, "Corporate Bank Account", _BANK_T, _CHECKING, False,
            "Central corporate bank for all settlements"),
         _m(_BANK, "JazzCash Settlement", _BANK_T, _CHECKING, False,
            "JazzCash mobile wallet settlement"),
         _m(_BANK, "Easypaisa Settlement", _BANK_T, _CHECKING, False,
            "Easypaisa mobile wallet settlement"),
         _m(_BANK, "Foodpanda Settlement", _OCA, _OCA_SUB, False,
            "Foodpanda receivable — weekly payout"),
         _m(_BANK, "Franchise Royalty Receivable", _OCA, _OCA_SUB, False,
            "Royalty receivable from franchisees")],
        # --- Delivery ---
        _PAK_DELIVERY,
        # --- Extra expense: franchise + per-branch ---
        extra_expense=[
            _m(_EXPENSE, "Royalty Fee Expense (6%)", _EXP, _COMMISSION, False,
               "Franchise royalty fee — 6% of gross branch revenue"),
            _m(_EXPENSE, "Marketing Fund (3%)", _EXP, _ADVERTISING, False,
               "Franchise marketing/advertising fund — 3% of revenue"),
            _m(_EXPENSE, "Brand License Fee", _EXP, _LEGAL, False,
               "Annual brand license and territory fee"),
            _m(_EXPENSE, "Central Kitchen Allocation", _EXP, _RENT, False,
               "Central kitchen overhead allocated to HQ"),
            _m(_EXPENSE, "Gulberg Rent & Utilities", _EXP, _RENT, False,
               "Rent and utilities for Gulberg branch"),
            _m(_EXPENSE, "DHA Rent & Utilities", _EXP, _RENT, False,
               "Rent and utilities for DHA branch"),
            _m(_EXPENSE, "Johar Town Rent & Utilities", _EXP, _RENT, False,
               "Rent and utilities for Johar Town branch"),
            _m(_EXPENSE, "Model Town Rent & Utilities", _EXP, _RENT, False,
               "Rent and utilities for Model Town branch"),
            _m(_EXPENSE, "Airport Rent & Utilities", _EXP, _RENT, False,
               "Rent and utilities for Airport branch"),
            _m(_PLATFORM, "Platform Commission (Foodpanda)", _EXP, _COMMISSION, True,
               "Foodpanda commission (25-35%) deducted per order"),
        ],
        # --- Extra liability: franchise-specific ---
        extra_liability=[
            _m(_OCL, "Royalty Payable", _OCL_T, _OCL_SUB, False,
               "Franchise royalty payable to franchisor"),
            _m(_OCL, "Marketing Fund Payable", _OCL_T, _OCL_SUB, False,
               "Marketing fund payable to brand HQ"),
            _m(_OCL, "Inter-Branch Payable", _OCL_T, _OCL_SUB, False,
               "Payable for goods received from other branches"),
            _m(_OCL, "Inter-Branch Receivable", _OCA, _OCA_SUB, False,
               "Receivable for goods sent to other branches"),
            _m(_OCL, "Security Deposits Held", _OCL_T, _OCL_SUB, False,
               "Security deposits held from franchise partners"),
        ],
        svc_charge=True,
    ),
}
