"""
Mock QB Chart of Accounts fixtures for testing the diagnostic tool.

5 scenarios representing different Pakistani company setups:
  1. standard_fbr       — textbook FBR-compliant names
  2. non_standard       — creative accountant names, nothing matches cleanly
  3. fresh_qb           — brand new QB, only default accounts
  4. mixed_urdu_english — bilingual account names
  5. heavy_custom       — large chart with 80+ accounts, deep hierarchy

Each fixture returns list[dict] in the same format as
MappingService.fetch_qb_accounts():
  {"id", "name", "account_type", "account_sub_type",
   "fully_qualified_name", "current_balance", "active"}
"""

from __future__ import annotations


def _acct(
    id: str,
    name: str,
    account_type: str,
    account_sub_type: str | None = None,
    fully_qualified_name: str | None = None,
    current_balance: float = 0.0,
    active: bool = True,
) -> dict:
    return {
        "id": id,
        "name": name,
        "account_type": account_type,
        "account_sub_type": account_sub_type,
        "fully_qualified_name": fully_qualified_name or name,
        "current_balance": current_balance,
        "active": active,
    }


# ---------------------------------------------------------------------------
# Scenario 1: Standard FBR-compliant Pakistani restaurant
# This should match almost perfectly with our pakistani_restaurant template.
# ---------------------------------------------------------------------------
def standard_fbr() -> list[dict]:
    """
    Textbook Pakistani restaurant accounts. Named exactly or very close
    to what our templates expect. Tests the 'easy path' — high matches.
    """
    return [
        # Income
        _acct("1", "Food Sales", "Income", "SalesOfProductIncome"),
        _acct("2", "Beverage Sales", "Income", "SalesOfProductIncome"),
        _acct("3", "Takeaway Revenue", "Income", "SalesOfProductIncome"),
        _acct("4", "Delivery Fee Income", "Other Income", "OtherMiscellaneousIncome"),
        _acct("5", "Service Charge Income", "Income", "ServiceFeeIncome"),

        # COGS
        _acct("10", "Food Cost of Goods Sold", "Cost of Goods Sold", "SuppliesMaterialsCogs"),
        _acct("11", "Beverage Cost", "Cost of Goods Sold", "SuppliesMaterialsCogs"),
        _acct("12", "Packaging & Disposables", "Cost of Goods Sold", "SuppliesMaterialsCogs"),

        # Tax
        _acct("20", "GST/Sales Tax Payable", "Other Current Liability", "SalesTaxPayable"),
        _acct("21", "FBR Sales Tax", "Other Current Liability", "SalesTaxPayable"),
        _acct("22", "PRA Punjab Tax", "Other Current Liability", "SalesTaxPayable"),

        # Bank / Cash
        _acct("30", "Cash Register", "Bank", "CashOnHand", current_balance=25000),
        _acct("31", "HBL Business Account", "Bank", "Checking", current_balance=450000),
        _acct("32", "Meezan Bank", "Bank", "Savings", current_balance=120000),
        _acct("33", "JazzCash Settlement", "Bank", "CashOnHand"),
        _acct("34", "Easypaisa Settlement", "Bank", "CashOnHand"),

        # Expenses
        _acct("40", "Rent Expense", "Expense", "OccupancyCost"),
        _acct("41", "Utility Bills", "Expense", "Utilities"),
        _acct("42", "Staff Salaries", "Expense", "PayrollExpenses"),
        _acct("43", "Kitchen Equipment Maintenance", "Expense", "RepairMaintenance"),
        _acct("44", "Marketing & Advertising", "Expense", "AdvertisingPromotional"),
        _acct("45", "Insurance Premium", "Expense", "Insurance"),
        _acct("46", "Restaurant License & Permits", "Expense", "LegalProfessionalFees"),
        _acct("47", "Delivery Rider Cost", "Expense", "OtherMiscellaneousServiceCost"),

        # Financial
        _acct("50", "Discount Allowed", "Income", "SalesOfProductIncome"),
        _acct("51", "Cash Rounding", "Expense", "OtherMiscellaneousServiceCost"),
        _acct("52", "Cash Over/Short", "Expense", "OtherMiscellaneousServiceCost"),

        # Liability
        _acct("60", "Tips Payable", "Other Current Liability", "OtherCurrentLiabilities"),
        _acct("61", "Gift Card Liability", "Other Current Liability", "OtherCurrentLiabilities"),
        _acct("62", "Foodpanda Commission", "Expense", "CommissionsAndFees"),
    ]


# ---------------------------------------------------------------------------
# Scenario 2: Non-standard names — creative accountant
# Names are different from template, but semantically equivalent.
# Tests the fuzzy matching quality.
# ---------------------------------------------------------------------------
def non_standard() -> list[dict]:
    """
    Accountant used non-standard names. None match template exactly.
    Tests Jaccard + synonym + type matching.
    """
    return [
        # Income (creative names)
        _acct("101", "Restaurant Food Revenue", "Income", "SalesOfProductIncome"),
        _acct("102", "Drinks & Beverages Income", "Income", "SalesOfProductIncome"),
        _acct("103", "Parcel/Takeout Sales", "Income", "SalesOfProductIncome"),
        _acct("104", "Delivery Charges Collected", "Other Income", "OtherMiscellaneousIncome"),
        _acct("105", "Tip/Service Fee Revenue", "Income", "ServiceFeeIncome"),
        _acct("106", "Catering & Events Revenue", "Income", "SalesOfProductIncome"),

        # COGS (different naming)
        _acct("110", "Kitchen Raw Material Cost", "Cost of Goods Sold", "SuppliesMaterialsCogs"),
        _acct("111", "Drink Supplies Cost", "Cost of Goods Sold", "SuppliesMaterialsCogs"),
        _acct("112", "Packing Material Expense", "Expense", "SuppliesMaterials"),

        # Tax (abbreviated)
        _acct("120", "Govt Tax Payable", "Other Current Liability", "SalesTaxPayable"),
        _acct("121", "Federal Tax Obligation", "Other Current Liability", "SalesTaxPayable"),

        # Bank (local names)
        _acct("130", "Main Cash Drawer", "Bank", "CashOnHand", current_balance=15000),
        _acct("131", "Allied Bank Current A/C", "Bank", "Checking", current_balance=800000),
        _acct("132", "Mobile Payments - Jazz", "Bank", "CashOnHand"),
        _acct("133", "Easypaisa Mobile Wallet", "Bank", "CashOnHand"),

        # Expenses (verbose)
        _acct("140", "Monthly Shop Rent", "Expense", "OccupancyCost"),
        _acct("141", "Electricity & Gas Bills", "Expense", "Utilities"),
        _acct("142", "Employee Wages & Benefits", "Expense", "PayrollExpenses"),
        _acct("143", "Equipment Repair & Upkeep", "Expense", "RepairMaintenance"),
        _acct("144", "Social Media & Print Ads", "Expense", "AdvertisingPromotional"),
        _acct("145", "Business Insurance Policy", "Expense", "Insurance"),
        _acct("146", "Food Authority License", "Expense", "LegalProfessionalFees"),
        _acct("147", "Rider & Courier Payments", "Expense", "OtherMiscellaneousServiceCost"),
        _acct("148", "Platform Commission - Foodpanda", "Expense", "CommissionsAndFees"),

        # Financial (unusual names)
        _acct("150", "Customer Discounts Given", "Income", "SalesOfProductIncome"),
        _acct("151", "Petty Cash Adjustments", "Expense", "OtherMiscellaneousServiceCost"),
        _acct("152", "Till Variance", "Expense", "OtherMiscellaneousServiceCost"),

        # Extra accounts template doesn't have
        _acct("160", "Owner's Drawing", "Equity", "PersonalExpense"),
        _acct("161", "Interior Decoration", "Other Expense", "Depreciation"),
        _acct("162", "Staff Meals Allowance", "Expense", "Meals"),
        _acct("163", "Uniform Expense", "Expense", "OtherMiscellaneousServiceCost"),
        _acct("164", "Waste Disposal & Cleaning", "Expense", "OtherMiscellaneousServiceCost"),
    ]


# ---------------------------------------------------------------------------
# Scenario 3: Fresh QB — only default accounts (minimal)
# Brand new company, accountant hasn't customized anything yet.
# Almost nothing should match — template needs to create accounts.
# ---------------------------------------------------------------------------
def fresh_qb() -> list[dict]:
    """
    Default QB accounts for a new company. Only generic accounts exist.
    Tests the 'create everything' path.
    """
    return [
        # QB defaults
        _acct("1", "Sales", "Income", "SalesOfProductIncome"),
        _acct("2", "Services", "Income", "ServiceFeeIncome"),
        _acct("3", "Discounts given", "Income", "SalesOfProductIncome"),

        _acct("10", "Cost of Goods Sold", "Cost of Goods Sold", "SuppliesMaterialsCogs"),

        _acct("20", "Advertising", "Expense", "AdvertisingPromotional"),
        _acct("21", "Bank Charges", "Expense", "BankCharges"),
        _acct("22", "Insurance", "Expense", "Insurance"),
        _acct("23", "Interest Paid", "Expense", "InterestPaid"),
        _acct("24", "Office Supplies", "Expense", "OfficeGeneralAdministrativeExpenses"),
        _acct("25", "Professional Fees", "Expense", "LegalProfessionalFees"),
        _acct("26", "Rent or Lease", "Expense", "OccupancyCost"),
        _acct("27", "Repairs", "Expense", "RepairMaintenance"),
        _acct("28", "Utilities", "Expense", "Utilities"),

        _acct("30", "Checking", "Bank", "Checking", current_balance=50000),
        _acct("31", "Savings", "Bank", "Savings"),

        _acct("40", "Board of Equalization Payable", "Other Current Liability", "SalesTaxPayable"),
        _acct("41", "Loan Payable", "Long Term Liability", "NotesPayable"),

        _acct("50", "Opening Balance Equity", "Equity", "OpeningBalanceEquity"),
        _acct("51", "Retained Earnings", "Equity", "RetainedEarnings"),
    ]


# ---------------------------------------------------------------------------
# Scenario 4: Mixed English/Urdu transliteration
# Some accounts use Roman Urdu names. Tests synonym matching with
# Pakistani terms (khana, kiraya, tankhwah, bijli, etc.)
# ---------------------------------------------------------------------------
def mixed_urdu_english() -> list[dict]:
    """
    Bilingual chart — some Urdu transliteration mixed with English.
    Tests our Pakistani synonym sets (khana, kiraya, bijli, etc.)
    """
    return [
        # Income (Urdu-influenced)
        _acct("1", "Khana Sales", "Income", "SalesOfProductIncome"),
        _acct("2", "Chai & Sharbat Revenue", "Income", "SalesOfProductIncome"),
        _acct("3", "Parcel Amdani", "Income", "SalesOfProductIncome"),  # amdani = income
        _acct("4", "Service Charge Amdani", "Income", "ServiceFeeIncome"),

        # COGS
        _acct("10", "Khana Kharcha (Food Cost)", "Cost of Goods Sold", "SuppliesMaterialsCogs"),
        _acct("11", "Drink Saman Cost", "Cost of Goods Sold", "SuppliesMaterialsCogs"),
        _acct("12", "Packing Saman", "Cost of Goods Sold", "SuppliesMaterialsCogs"),

        # Tax
        _acct("20", "FBR Tax Payable", "Other Current Liability", "SalesTaxPayable"),
        _acct("21", "Punjab PRA Tax", "Other Current Liability", "SalesTaxPayable"),

        # Bank
        _acct("30", "Naqd (Cash Register)", "Bank", "CashOnHand", current_balance=18000),
        _acct("31", "Meezan Bank Islamic A/C", "Bank", "Checking", current_balance=350000),
        _acct("32", "JazzCash Wallet", "Bank", "CashOnHand"),
        _acct("33", "Easypaisa Account", "Bank", "CashOnHand"),

        # Expenses (mixed)
        _acct("40", "Dukaan Kiraya (Rent)", "Expense", "OccupancyCost"),
        _acct("41", "Bijli Gas Paani Bills", "Expense", "Utilities"),
        _acct("42", "Tankhwah (Staff Salary)", "Expense", "PayrollExpenses"),
        _acct("43", "Marammat (Repair)", "Expense", "RepairMaintenance"),
        _acct("44", "Istihar (Advertising)", "Expense", "AdvertisingPromotional"),
        _acct("45", "Bima (Insurance)", "Expense", "Insurance"),
        _acct("46", "License Fee", "Expense", "LegalProfessionalFees"),
        _acct("47", "Delivery Rider Kharcha", "Expense", "OtherMiscellaneousServiceCost"),

        # Financial
        _acct("50", "Riaayat (Discount)", "Income", "SalesOfProductIncome"),
        _acct("51", "Cash Rounding Fark", "Expense", "OtherMiscellaneousServiceCost"),
        _acct("52", "Cash Over Short Fark", "Expense", "OtherMiscellaneousServiceCost"),

        # Liability
        _acct("60", "Bakshish (Tips)", "Other Current Liability", "OtherCurrentLiabilities"),
        _acct("61", "Foodpanda Commission Kharcha", "Expense", "CommissionsAndFees"),
    ]


# ---------------------------------------------------------------------------
# Scenario 5: Heavy customization — large chart with 80+ accounts
# Accountant has deep sub-account hierarchy, many accounts our template
# doesn't cover, plus some that DO match but are buried in the hierarchy.
# ---------------------------------------------------------------------------
def heavy_custom() -> list[dict]:
    """
    80+ accounts with deep hierarchy. Tests:
    - Finding matches buried in subaccounts
    - Handling many 'unmapped' accounts gracefully
    - Performance with larger account lists
    """
    return [
        # === Income (8 accounts, heavily segmented) ===
        _acct("1", "Revenue", "Income", "SalesOfProductIncome",
               "Revenue"),
        _acct("2", "Dine-In Food Sales", "Income", "SalesOfProductIncome",
               "Revenue:Dine-In Food Sales"),
        _acct("3", "Takeaway Food Sales", "Income", "SalesOfProductIncome",
               "Revenue:Takeaway Food Sales"),
        _acct("4", "Delivery Food Sales", "Income", "SalesOfProductIncome",
               "Revenue:Delivery Food Sales"),
        _acct("5", "Beverage Revenue", "Income", "SalesOfProductIncome",
               "Revenue:Beverage Revenue"),
        _acct("6", "Dessert & Bakery Sales", "Income", "SalesOfProductIncome",
               "Revenue:Dessert & Bakery Sales"),
        _acct("7", "Corporate Catering Revenue", "Income", "SalesOfProductIncome",
               "Revenue:Corporate Catering Revenue"),
        _acct("8", "Delivery Charges Income", "Other Income", "OtherMiscellaneousIncome",
               "Other Income:Delivery Charges Income"),
        _acct("9", "Service Charge Revenue", "Income", "ServiceFeeIncome",
               "Revenue:Service Charge Revenue"),
        _acct("10", "Loyalty Program Redemptions", "Other Income", "OtherMiscellaneousIncome",
               "Other Income:Loyalty Program Redemptions"),

        # === COGS (6 accounts) ===
        _acct("20", "Cost of Food Sold", "Cost of Goods Sold", "SuppliesMaterialsCogs",
               "COGS:Cost of Food Sold"),
        _acct("21", "Cost of Beverages Sold", "Cost of Goods Sold", "SuppliesMaterialsCogs",
               "COGS:Cost of Beverages Sold"),
        _acct("22", "Packaging Cost", "Cost of Goods Sold", "SuppliesMaterialsCogs",
               "COGS:Packaging Cost"),
        _acct("23", "Kitchen Consumables", "Cost of Goods Sold", "SuppliesMaterialsCogs",
               "COGS:Kitchen Consumables"),
        _acct("24", "Food Waste & Spoilage", "Cost of Goods Sold", "SuppliesMaterialsCogs",
               "COGS:Food Waste & Spoilage"),
        _acct("25", "Recipe Development Cost", "Cost of Goods Sold", "SuppliesMaterialsCogs",
               "COGS:Recipe Development Cost"),

        # === Tax (4 accounts) ===
        _acct("30", "Sales Tax Payable - FBR", "Other Current Liability", "SalesTaxPayable",
               "Tax:Sales Tax Payable - FBR"),
        _acct("31", "PRA Punjab Sales Tax", "Other Current Liability", "SalesTaxPayable",
               "Tax:PRA Punjab Sales Tax"),
        _acct("32", "Withholding Tax Payable", "Other Current Liability", "SalesTaxPayable",
               "Tax:Withholding Tax Payable"),
        _acct("33", "Advance Tax - FBR", "Other Current Liability", "OtherCurrentLiabilities",
               "Tax:Advance Tax - FBR"),

        # === Bank (7 accounts) ===
        _acct("40", "Main Cash Register", "Bank", "CashOnHand",
               "Cash:Main Cash Register", current_balance=45000),
        _acct("41", "Petty Cash Fund", "Bank", "CashOnHand",
               "Cash:Petty Cash Fund", current_balance=5000),
        _acct("42", "HBL Current Account", "Bank", "Checking",
               "Bank:HBL Current Account", current_balance=1200000),
        _acct("43", "MCB Savings Account", "Bank", "Savings",
               "Bank:MCB Savings Account", current_balance=500000),
        _acct("44", "JazzCash Business", "Bank", "CashOnHand",
               "Digital:JazzCash Business"),
        _acct("45", "Easypaisa Business", "Bank", "CashOnHand",
               "Digital:Easypaisa Business"),
        _acct("46", "Credit Card Settlements", "Bank", "Checking",
               "Bank:Credit Card Settlements"),

        # === Expenses (25 accounts — deep hierarchy) ===
        _acct("50", "Rent & Occupancy", "Expense", "OccupancyCost",
               "Operating:Rent & Occupancy"),
        _acct("51", "Electricity Bill", "Expense", "Utilities",
               "Operating:Utilities:Electricity Bill"),
        _acct("52", "Sui Gas Bill", "Expense", "Utilities",
               "Operating:Utilities:Sui Gas Bill"),
        _acct("53", "Water & Sewerage", "Expense", "Utilities",
               "Operating:Utilities:Water & Sewerage"),
        _acct("54", "Internet & Phone", "Expense", "Utilities",
               "Operating:Utilities:Internet & Phone"),
        _acct("55", "Kitchen Staff Salaries", "Expense", "PayrollExpenses",
               "Payroll:Kitchen Staff Salaries"),
        _acct("56", "Floor Staff Salaries", "Expense", "PayrollExpenses",
               "Payroll:Floor Staff Salaries"),
        _acct("57", "Management Salaries", "Expense", "PayrollExpenses",
               "Payroll:Management Salaries"),
        _acct("58", "Delivery Staff Wages", "Expense", "PayrollExpenses",
               "Payroll:Delivery Staff Wages"),
        _acct("59", "Staff Overtime", "Expense", "PayrollExpenses",
               "Payroll:Staff Overtime"),
        _acct("60", "EOBI & Social Security", "Expense", "PayrollExpenses",
               "Payroll:EOBI & Social Security"),
        _acct("61", "Kitchen Equipment Repair", "Expense", "RepairMaintenance",
               "Maintenance:Kitchen Equipment Repair"),
        _acct("62", "AC & Refrigeration Service", "Expense", "RepairMaintenance",
               "Maintenance:AC & Refrigeration Service"),
        _acct("63", "Building Maintenance", "Expense", "RepairMaintenance",
               "Maintenance:Building Maintenance"),
        _acct("64", "Facebook & Instagram Ads", "Expense", "AdvertisingPromotional",
               "Marketing:Facebook & Instagram Ads"),
        _acct("65", "Print Media & Banners", "Expense", "AdvertisingPromotional",
               "Marketing:Print Media & Banners"),
        _acct("66", "Restaurant Insurance", "Expense", "Insurance",
               "Operating:Restaurant Insurance"),
        _acct("67", "Health Department License", "Expense", "LegalProfessionalFees",
               "Operating:Health Department License"),
        _acct("68", "Legal & Professional Fees", "Expense", "LegalProfessionalFees",
               "Operating:Legal & Professional Fees"),
        _acct("69", "Delivery Rider Fuel & Costs", "Expense", "OtherMiscellaneousServiceCost",
               "Delivery:Delivery Rider Fuel & Costs"),
        _acct("70", "Foodpanda Commission Expense", "Expense", "CommissionsAndFees",
               "Platforms:Foodpanda Commission Expense"),
        _acct("71", "Cheetay Commission", "Expense", "CommissionsAndFees",
               "Platforms:Cheetay Commission"),
        _acct("72", "POS System Subscription", "Expense", "OtherMiscellaneousServiceCost",
               "Technology:POS System Subscription"),
        _acct("73", "Accounting Software", "Expense", "OtherMiscellaneousServiceCost",
               "Technology:Accounting Software"),
        _acct("74", "Staff Training & Development", "Expense", "OtherMiscellaneousServiceCost",
               "Operating:Staff Training & Development"),

        # === Financial (3 accounts) ===
        _acct("80", "Customer Discounts", "Income", "SalesOfProductIncome",
               "Revenue:Customer Discounts"),
        _acct("81", "Cash Rounding Adjustment", "Expense", "OtherMiscellaneousServiceCost",
               "Adjustments:Cash Rounding Adjustment"),
        _acct("82", "Cash Over Short Account", "Expense", "OtherMiscellaneousServiceCost",
               "Adjustments:Cash Over Short Account"),

        # === Liability (5 accounts) ===
        _acct("90", "Tips & Gratuity Payable", "Other Current Liability", "OtherCurrentLiabilities",
               "Liabilities:Tips & Gratuity Payable"),
        _acct("91", "Gift Voucher Liability", "Other Current Liability", "OtherCurrentLiabilities",
               "Liabilities:Gift Voucher Liability"),
        _acct("92", "Customer Deposits", "Other Current Liability", "OtherCurrentLiabilities",
               "Liabilities:Customer Deposits"),
        _acct("93", "Unearned Catering Revenue", "Other Current Liability", "OtherCurrentLiabilities",
               "Liabilities:Unearned Catering Revenue"),
        _acct("94", "Security Deposits Held", "Other Current Liability", "OtherCurrentLiabilities",
               "Liabilities:Security Deposits Held"),

        # === Other (accounts template won't cover — unmapped) ===
        _acct("100", "Furniture & Fixtures", "Fixed Asset", "FurnitureAndFixtures"),
        _acct("101", "Kitchen Equipment", "Fixed Asset", "MachineryAndEquipment"),
        _acct("102", "Vehicle - Delivery Bike", "Fixed Asset", "Vehicles"),
        _acct("103", "Accumulated Depreciation", "Fixed Asset", "AccumulatedDepreciation"),
        _acct("104", "Owner's Capital", "Equity", "OwnersEquity"),
        _acct("105", "Owner's Drawing", "Equity", "PersonalExpense"),
        _acct("106", "Retained Earnings", "Equity", "RetainedEarnings"),
        _acct("107", "Accounts Receivable", "Accounts Receivable", "AccountsReceivable"),
        _acct("108", "Accounts Payable", "Accounts Payable", "AccountsPayable"),
        _acct("109", "Bank Loan - NBP", "Long Term Liability", "NotesPayable"),
        _acct("110", "Employee Advances", "Other Current Asset", "EmployeeCashAdvances"),
        _acct("111", "Prepaid Rent", "Other Current Asset", "PrepaidExpenses"),
        _acct("112", "Depreciation Expense", "Expense", "Depreciation"),
        _acct("113", "Interest Income", "Other Income", "InterestEarned"),
        _acct("114", "Gain/Loss on Disposal", "Other Income", "OtherMiscellaneousIncome"),
    ]


# ---------------------------------------------------------------------------
# Registry — easy lookup by name
# ---------------------------------------------------------------------------
FIXTURES: dict[str, callable] = {
    "standard_fbr": standard_fbr,
    "non_standard": non_standard,
    "fresh_qb": fresh_qb,
    "mixed_urdu_english": mixed_urdu_english,
    "heavy_custom": heavy_custom,
}


def get_fixture(name: str) -> list[dict]:
    """Get a test fixture by name. Raises KeyError if not found."""
    return FIXTURES[name]()


def list_fixtures() -> list[dict]:
    """List available fixtures with metadata."""
    return [
        {
            "name": "standard_fbr",
            "description": "Standard FBR-compliant Pakistani restaurant (30 accounts)",
            "account_count": len(standard_fbr()),
        },
        {
            "name": "non_standard",
            "description": "Creative accountant names, nothing matches exactly (28 accounts)",
            "account_count": len(non_standard()),
        },
        {
            "name": "fresh_qb",
            "description": "Brand new QB company, only default accounts (19 accounts)",
            "account_count": len(fresh_qb()),
        },
        {
            "name": "mixed_urdu_english",
            "description": "Bilingual Urdu/English account names (26 accounts)",
            "account_count": len(mixed_urdu_english()),
        },
        {
            "name": "heavy_custom",
            "description": "Large chart with 80+ accounts, deep hierarchy",
            "account_count": len(heavy_custom()),
        },
    ]
