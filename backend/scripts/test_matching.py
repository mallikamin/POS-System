"""
Test the Attempt 2 fuzzy matching engine against public/realistic QB Chart of Accounts datasets.

Run from project root:
    docker compose exec backend python -m scripts.test_matching

Or locally (if dependencies are installed):
    cd backend && python -m scripts.test_matching
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.quickbooks.fuzzy_match import find_best_matches, THRESHOLD_HIGH, THRESHOLD_MEDIUM
from app.services.quickbooks.pos_needs import POS_ACCOUNTING_NEEDS

# ---------------------------------------------------------------------------
# Fixture 1: Pakistani Restaurant (35 accounts)
# Realistic Lahore/Islamabad restaurant chain. Uses local bank names,
# Urdu terminology, Pakistani tax (FBR/PRA), mobile wallets.
# Expected grade: A (nearly all needs matched)
# ---------------------------------------------------------------------------
FIXTURE_PAKISTANI_RESTAURANT: list[dict] = [
    # Bank
    {"id": "1", "name": "HBL Current Account", "account_type": "Bank", "account_sub_type": "Checking", "fully_qualified_name": "HBL Current Account", "active": True},
    {"id": "2", "name": "Meezan Bank Savings", "account_type": "Bank", "account_sub_type": "Savings", "fully_qualified_name": "Meezan Bank Savings", "active": True},
    {"id": "3", "name": "Cash Register - Main", "account_type": "Bank", "account_sub_type": "CashOnHand", "fully_qualified_name": "Cash Register - Main", "active": True},
    {"id": "4", "name": "JazzCash Business", "account_type": "Bank", "account_sub_type": "Checking", "fully_qualified_name": "JazzCash Business", "active": True},
    {"id": "5", "name": "Easypaisa Merchant", "account_type": "Bank", "account_sub_type": "Checking", "fully_qualified_name": "Easypaisa Merchant", "active": True},
    # Receivable
    {"id": "6", "name": "Accounts Receivable", "account_type": "Accounts Receivable", "account_sub_type": "AccountsReceivable", "fully_qualified_name": "Accounts Receivable", "active": True},
    # Current Asset
    {"id": "7", "name": "Undeposited Funds", "account_type": "Other Current Asset", "account_sub_type": "UndepositedFunds", "fully_qualified_name": "Undeposited Funds", "active": True},
    {"id": "8", "name": "Food Inventory", "account_type": "Other Current Asset", "account_sub_type": "Inventory", "fully_qualified_name": "Food Inventory", "active": True},
    {"id": "9", "name": "Beverage Stock", "account_type": "Other Current Asset", "account_sub_type": "Inventory", "fully_qualified_name": "Beverage Stock", "active": True},
    # Fixed Asset
    {"id": "10", "name": "Kitchen Equipment", "account_type": "Fixed Asset", "account_sub_type": "MachineryAndEquipment", "fully_qualified_name": "Kitchen Equipment", "active": True},
    {"id": "11", "name": "Restaurant Furniture", "account_type": "Fixed Asset", "account_sub_type": "FurnitureAndFixtures", "fully_qualified_name": "Restaurant Furniture", "active": True},
    {"id": "12", "name": "Delivery Bikes", "account_type": "Fixed Asset", "account_sub_type": "Vehicles", "fully_qualified_name": "Delivery Bikes", "active": True},
    {"id": "13", "name": "Leasehold Improvements", "account_type": "Fixed Asset", "account_sub_type": "LeaseholdImprovements", "fully_qualified_name": "Leasehold Improvements", "active": True},
    # Payable
    {"id": "14", "name": "Accounts Payable", "account_type": "Accounts Payable", "account_sub_type": "AccountsPayable", "fully_qualified_name": "Accounts Payable", "active": True},
    # Current Liability
    {"id": "15", "name": "GST/FBR Tax Payable", "account_type": "Other Current Liability", "account_sub_type": "GlobalTaxPayable", "fully_qualified_name": "GST/FBR Tax Payable", "active": True},
    {"id": "16", "name": "PRA Sales Tax Payable", "account_type": "Other Current Liability", "account_sub_type": "SalesTaxPayable", "fully_qualified_name": "PRA Sales Tax Payable", "active": True},
    {"id": "17", "name": "Tips Payable to Staff", "account_type": "Other Current Liability", "account_sub_type": "OtherCurrentLiabilities", "fully_qualified_name": "Tips Payable to Staff", "active": True},
    {"id": "18", "name": "Gift Vouchers Outstanding", "account_type": "Other Current Liability", "account_sub_type": "OtherCurrentLiabilities", "fully_qualified_name": "Gift Vouchers Outstanding", "active": True},
    # Equity
    {"id": "19", "name": "Owner's Equity", "account_type": "Equity", "account_sub_type": "OwnersEquity", "fully_qualified_name": "Owner's Equity", "active": True},
    {"id": "20", "name": "Retained Earnings", "account_type": "Equity", "account_sub_type": "RetainedEarnings", "fully_qualified_name": "Retained Earnings", "active": True},
    # Income
    {"id": "21", "name": "Dine-In Food Sales", "account_type": "Income", "account_sub_type": "SalesOfProductIncome", "fully_qualified_name": "Dine-In Food Sales", "active": True},
    {"id": "22", "name": "Takeaway & Delivery Revenue", "account_type": "Income", "account_sub_type": "SalesOfProductIncome", "fully_qualified_name": "Takeaway & Delivery Revenue", "active": True},
    {"id": "23", "name": "Chai & Beverage Sales", "account_type": "Income", "account_sub_type": "SalesOfProductIncome", "fully_qualified_name": "Chai & Beverage Sales", "active": True},
    {"id": "24", "name": "Catering & Events Income", "account_type": "Income", "account_sub_type": "SalesOfProductIncome", "fully_qualified_name": "Catering & Events Income", "active": True},
    {"id": "25", "name": "Delivery Charges Collected", "account_type": "Income", "account_sub_type": "ServiceFeeIncome", "fully_qualified_name": "Delivery Charges Collected", "active": True},
    {"id": "26", "name": "Service Charge Income", "account_type": "Income", "account_sub_type": "ServiceFeeIncome", "fully_qualified_name": "Service Charge Income", "active": True},
    {"id": "27", "name": "Discounts & Promotions", "account_type": "Income", "account_sub_type": "DiscountsRefundsGiven", "fully_qualified_name": "Discounts & Promotions", "active": True},
    # COGS
    {"id": "28", "name": "Food & Ingredient Cost", "account_type": "Cost of Goods Sold", "account_sub_type": "SuppliesMaterialsCogs", "fully_qualified_name": "Food & Ingredient Cost", "active": True},
    {"id": "29", "name": "Packaging & Disposables", "account_type": "Cost of Goods Sold", "account_sub_type": "SuppliesMaterialsCogs", "fully_qualified_name": "Packaging & Disposables", "active": True},
    {"id": "30", "name": "Foodpanda Commission", "account_type": "Cost of Goods Sold", "account_sub_type": "OtherCostsOfServiceCos", "fully_qualified_name": "Foodpanda Commission", "active": True},
    # Expense
    {"id": "31", "name": "Staff Salaries & Wages", "account_type": "Expense", "account_sub_type": "PayrollExpenses", "fully_qualified_name": "Staff Salaries & Wages", "active": True},
    {"id": "32", "name": "Shop Rent", "account_type": "Expense", "account_sub_type": "RentOrLeaseOfBuildings", "fully_qualified_name": "Shop Rent", "active": True},
    {"id": "33", "name": "Bijli, Gas & Water", "account_type": "Expense", "account_sub_type": "Utilities", "fully_qualified_name": "Bijli, Gas & Water", "active": True},
    {"id": "34", "name": "Cash Over/Short", "account_type": "Expense", "account_sub_type": "OtherMiscellaneousServiceCost", "fully_qualified_name": "Cash Over/Short", "active": True},
    # Other Expense
    {"id": "35", "name": "Rounding Adjustment", "account_type": "Other Expense", "account_sub_type": "OtherMiscellaneousExpense", "fully_qualified_name": "Rounding Adjustment", "active": True},
]

# ---------------------------------------------------------------------------
# Fixture 2: Generic Small Business (30 accounts)
# A retail/services shop — no restaurant-specific accounts. Tests how the
# fuzzy engine handles mismatched domains.
# Expected grade: C or D (many POS needs unmatched)
# ---------------------------------------------------------------------------
FIXTURE_GENERIC_SMALL_BUSINESS: list[dict] = [
    # Bank
    {"id": "101", "name": "Business Checking", "account_type": "Bank", "account_sub_type": "Checking", "fully_qualified_name": "Business Checking", "active": True},
    {"id": "102", "name": "Business Savings", "account_type": "Bank", "account_sub_type": "Savings", "fully_qualified_name": "Business Savings", "active": True},
    {"id": "103", "name": "Petty Cash", "account_type": "Bank", "account_sub_type": "CashOnHand", "fully_qualified_name": "Petty Cash", "active": True},
    # Receivable
    {"id": "104", "name": "Accounts Receivable (A/R)", "account_type": "Accounts Receivable", "account_sub_type": "AccountsReceivable", "fully_qualified_name": "Accounts Receivable (A/R)", "active": True},
    # Current Asset
    {"id": "105", "name": "Inventory Asset", "account_type": "Other Current Asset", "account_sub_type": "Inventory", "fully_qualified_name": "Inventory Asset", "active": True},
    {"id": "106", "name": "Undeposited Funds", "account_type": "Other Current Asset", "account_sub_type": "UndepositedFunds", "fully_qualified_name": "Undeposited Funds", "active": True},
    {"id": "107", "name": "Prepaid Expenses", "account_type": "Other Current Asset", "account_sub_type": "PrepaidExpenses", "fully_qualified_name": "Prepaid Expenses", "active": True},
    # Fixed Asset
    {"id": "108", "name": "Furniture and Equipment", "account_type": "Fixed Asset", "account_sub_type": "FurnitureAndFixtures", "fully_qualified_name": "Furniture and Equipment", "active": True},
    {"id": "109", "name": "Accumulated Depreciation", "account_type": "Fixed Asset", "account_sub_type": "AccumulatedDepreciation", "fully_qualified_name": "Accumulated Depreciation", "active": True},
    # Payable
    {"id": "110", "name": "Accounts Payable (A/P)", "account_type": "Accounts Payable", "account_sub_type": "AccountsPayable", "fully_qualified_name": "Accounts Payable (A/P)", "active": True},
    # Credit Card
    {"id": "111", "name": "Mastercard Business", "account_type": "Credit Card", "account_sub_type": "CreditCard", "fully_qualified_name": "Mastercard Business", "active": True},
    # Current Liability
    {"id": "112", "name": "Sales Tax Payable", "account_type": "Other Current Liability", "account_sub_type": "SalesTaxPayable", "fully_qualified_name": "Sales Tax Payable", "active": True},
    {"id": "113", "name": "Payroll Liabilities", "account_type": "Other Current Liability", "account_sub_type": "PayrollTaxPayable", "fully_qualified_name": "Payroll Liabilities", "active": True},
    {"id": "114", "name": "Loan Payable - Current", "account_type": "Other Current Liability", "account_sub_type": "LoanPayable", "fully_qualified_name": "Loan Payable - Current", "active": True},
    # Long-Term Liability
    {"id": "115", "name": "Bank Loan", "account_type": "Long Term Liability", "account_sub_type": "NotesPayable", "fully_qualified_name": "Bank Loan", "active": True},
    # Equity
    {"id": "116", "name": "Opening Balance Equity", "account_type": "Equity", "account_sub_type": "OpeningBalanceEquity", "fully_qualified_name": "Opening Balance Equity", "active": True},
    {"id": "117", "name": "Retained Earnings", "account_type": "Equity", "account_sub_type": "RetainedEarnings", "fully_qualified_name": "Retained Earnings", "active": True},
    {"id": "118", "name": "Owner's Investment", "account_type": "Equity", "account_sub_type": "OwnersEquity", "fully_qualified_name": "Owner's Investment", "active": True},
    # Income
    {"id": "119", "name": "Product Sales", "account_type": "Income", "account_sub_type": "SalesOfProductIncome", "fully_qualified_name": "Product Sales", "active": True},
    {"id": "120", "name": "Service Revenue", "account_type": "Income", "account_sub_type": "ServiceFeeIncome", "fully_qualified_name": "Service Revenue", "active": True},
    {"id": "121", "name": "Shipping & Handling Income", "account_type": "Income", "account_sub_type": "ServiceFeeIncome", "fully_qualified_name": "Shipping & Handling Income", "active": True},
    {"id": "122", "name": "Refunds & Allowances", "account_type": "Income", "account_sub_type": "DiscountsRefundsGiven", "fully_qualified_name": "Refunds & Allowances", "active": True},
    # COGS
    {"id": "123", "name": "Cost of Products Sold", "account_type": "Cost of Goods Sold", "account_sub_type": "SuppliesMaterialsCogs", "fully_qualified_name": "Cost of Products Sold", "active": True},
    {"id": "124", "name": "Shipping & Freight Cost", "account_type": "Cost of Goods Sold", "account_sub_type": "ShippingFreightDeliveryCos", "fully_qualified_name": "Shipping & Freight Cost", "active": True},
    # Expense
    {"id": "125", "name": "Advertising & Marketing", "account_type": "Expense", "account_sub_type": "AdvertisingPromotional", "fully_qualified_name": "Advertising & Marketing", "active": True},
    {"id": "126", "name": "Bank Service Charges", "account_type": "Expense", "account_sub_type": "BankCharges", "fully_qualified_name": "Bank Service Charges", "active": True},
    {"id": "127", "name": "Insurance - General", "account_type": "Expense", "account_sub_type": "Insurance", "fully_qualified_name": "Insurance - General", "active": True},
    {"id": "128", "name": "Office Supplies & Expenses", "account_type": "Expense", "account_sub_type": "OfficeGeneralAdministrativeExpenses", "fully_qualified_name": "Office Supplies & Expenses", "active": True},
    {"id": "129", "name": "Payroll Expenses", "account_type": "Expense", "account_sub_type": "PayrollExpenses", "fully_qualified_name": "Payroll Expenses", "active": True},
    {"id": "130", "name": "Rent Expense", "account_type": "Expense", "account_sub_type": "RentOrLeaseOfBuildings", "fully_qualified_name": "Rent Expense", "active": True},
    {"id": "131", "name": "Repairs & Maintenance", "account_type": "Expense", "account_sub_type": "RepairMaintenance", "fully_qualified_name": "Repairs & Maintenance", "active": True},
    {"id": "132", "name": "Utilities", "account_type": "Expense", "account_sub_type": "Utilities", "fully_qualified_name": "Utilities", "active": True},
    {"id": "133", "name": "Legal & Professional Fees", "account_type": "Expense", "account_sub_type": "LegalProfessionalFees", "fully_qualified_name": "Legal & Professional Fees", "active": True},
    # Other Expense
    {"id": "134", "name": "Depreciation Expense", "account_type": "Other Expense", "account_sub_type": "Depreciation", "fully_qualified_name": "Depreciation Expense", "active": True},
]

# ---------------------------------------------------------------------------
# Fixture 3: US Restaurant (from Simple Restaurant Accounting)
# Real-world COA with 90+ accounts: detailed inventory sub-categories,
# liquor/beer/wine, staff wages, direct operating expenses.
# Source: https://simplerestaurantaccounting.com/quickbooks-chart-of-accounts-import-file/
# Expected grade: A (restaurant-specific, most needs matched)
# ---------------------------------------------------------------------------
FIXTURE_US_RESTAURANT: list[dict] = [
    # Bank
    {"id": "201", "name": "Primary Checking", "account_type": "Bank", "account_sub_type": "Checking", "fully_qualified_name": "Bank Accounts:Primary", "active": True},
    {"id": "202", "name": "2nd Bank Account", "account_type": "Bank", "account_sub_type": "Checking", "fully_qualified_name": "Bank Accounts:2nd", "active": True},
    {"id": "203", "name": "Merchant Account 1", "account_type": "Bank", "account_sub_type": "Checking", "fully_qualified_name": "Bank Accounts:Merchant 1", "active": True},
    {"id": "204", "name": "Merchant Account 2", "account_type": "Bank", "account_sub_type": "Checking", "fully_qualified_name": "Bank Accounts:Merchant 2", "active": True},
    # Receivable
    {"id": "205", "name": "Accounts Receivable", "account_type": "Accounts Receivable", "account_sub_type": "AccountsReceivable", "fully_qualified_name": "Accounts Receivable", "active": True},
    # Current Assets
    {"id": "206", "name": "Cash", "account_type": "Other Current Asset", "account_sub_type": "OtherCurrentAssets", "fully_qualified_name": "Cash", "active": True},
    {"id": "207", "name": "Undeposited Funds", "account_type": "Other Current Asset", "account_sub_type": "UndepositedFunds", "fully_qualified_name": "Undeposited Funds", "active": True},
    {"id": "208", "name": "Food Inventory", "account_type": "Other Current Asset", "account_sub_type": "Inventory", "fully_qualified_name": "Food Inventory", "active": True},
    {"id": "209", "name": "Beverage Inventory", "account_type": "Other Current Asset", "account_sub_type": "Inventory", "fully_qualified_name": "Beverage Inventory", "active": True},
    {"id": "210", "name": "Liquor Inventory", "account_type": "Other Current Asset", "account_sub_type": "Inventory", "fully_qualified_name": "Liquor Inventory", "active": True},
    {"id": "211", "name": "Beer Inventory", "account_type": "Other Current Asset", "account_sub_type": "Inventory", "fully_qualified_name": "Beer Inventory", "active": True},
    {"id": "212", "name": "Wine Inventory", "account_type": "Other Current Asset", "account_sub_type": "Inventory", "fully_qualified_name": "Wine Inventory", "active": True},
    {"id": "213", "name": "Merchandise Inventory", "account_type": "Other Current Asset", "account_sub_type": "Inventory", "fully_qualified_name": "Merchandise Inventory", "active": True},
    {"id": "214", "name": "Bar & Consumable Inventory", "account_type": "Other Current Asset", "account_sub_type": "Inventory", "fully_qualified_name": "Bar & Consumable Inventory", "active": True},
    # Fixed Assets
    {"id": "215", "name": "Land & Building", "account_type": "Fixed Asset", "account_sub_type": "Buildings", "fully_qualified_name": "Fixed Assets:Land & Building", "active": True},
    {"id": "216", "name": "Automobile", "account_type": "Fixed Asset", "account_sub_type": "Vehicles", "fully_qualified_name": "Fixed Assets:Automobile", "active": True},
    {"id": "217", "name": "Furniture Fixtures & Equipment", "account_type": "Fixed Asset", "account_sub_type": "FurnitureAndFixtures", "fully_qualified_name": "Fixed Assets:Furniture Fixtures & Equipment", "active": True},
    {"id": "218", "name": "Leasehold Improvements", "account_type": "Fixed Asset", "account_sub_type": "LeaseholdImprovements", "fully_qualified_name": "Fixed Assets:Leasehold Improvements", "active": True},
    {"id": "219", "name": "Accumulated Depreciation", "account_type": "Fixed Asset", "account_sub_type": "AccumulatedDepreciation", "fully_qualified_name": "Accumulated Depreciation", "active": True},
    # Other Assets
    {"id": "220", "name": "Security Deposits Asset", "account_type": "Other Asset", "account_sub_type": "SecurityDeposits", "fully_qualified_name": "Security Deposits Asset", "active": True},
    # Payable
    {"id": "221", "name": "Accounts Payable", "account_type": "Accounts Payable", "account_sub_type": "AccountsPayable", "fully_qualified_name": "Accounts Payable", "active": True},
    # Credit Card
    {"id": "222", "name": "Credit Card", "account_type": "Credit Card", "account_sub_type": "CreditCard", "fully_qualified_name": "Credit Card", "active": True},
    # Current Liability
    {"id": "223", "name": "Sales Tax Payable", "account_type": "Other Current Liability", "account_sub_type": "SalesTaxPayable", "fully_qualified_name": "Sales Tax Payable", "active": True},
    {"id": "224", "name": "Payroll Liabilities", "account_type": "Other Current Liability", "account_sub_type": "PayrollTaxPayable", "fully_qualified_name": "Payroll Liabilities", "active": True},
    {"id": "225", "name": "Employee Tips Payable", "account_type": "Other Current Liability", "account_sub_type": "OtherCurrentLiabilities", "fully_qualified_name": "Employee Tips Payable", "active": True},
    {"id": "226", "name": "Gift Cards & Certificates", "account_type": "Other Current Liability", "account_sub_type": "OtherCurrentLiabilities", "fully_qualified_name": "Gift Cards & Certificates", "active": True},
    {"id": "227", "name": "Customer Credits", "account_type": "Other Current Liability", "account_sub_type": "OtherCurrentLiabilities", "fully_qualified_name": "Customer Credits", "active": True},
    # Long-Term
    {"id": "228", "name": "Notes Payable", "account_type": "Long Term Liability", "account_sub_type": "NotesPayable", "fully_qualified_name": "Notes Payable", "active": True},
    # Equity
    {"id": "229", "name": "Opening Bal Equity", "account_type": "Equity", "account_sub_type": "OpeningBalanceEquity", "fully_qualified_name": "Opening Bal Equity", "active": True},
    {"id": "230", "name": "Retained Earnings", "account_type": "Equity", "account_sub_type": "RetainedEarnings", "fully_qualified_name": "Retained Earnings", "active": True},
    # Income
    {"id": "231", "name": "Food Sales", "account_type": "Income", "account_sub_type": "SalesOfProductIncome", "fully_qualified_name": "Food Sales", "active": True},
    {"id": "232", "name": "Beverage Sales", "account_type": "Income", "account_sub_type": "SalesOfProductIncome", "fully_qualified_name": "Beverage Sales", "active": True},
    {"id": "233", "name": "Liquor Sales", "account_type": "Income", "account_sub_type": "SalesOfProductIncome", "fully_qualified_name": "Liquor Sales", "active": True},
    {"id": "234", "name": "Beer Sales", "account_type": "Income", "account_sub_type": "SalesOfProductIncome", "fully_qualified_name": "Beer Sales", "active": True},
    {"id": "235", "name": "Wine Sales", "account_type": "Income", "account_sub_type": "SalesOfProductIncome", "fully_qualified_name": "Wine Sales", "active": True},
    {"id": "236", "name": "Merchandise Sales", "account_type": "Income", "account_sub_type": "SalesOfProductIncome", "fully_qualified_name": "Merchandise Sales", "active": True},
    {"id": "237", "name": "Catering & Contracts", "account_type": "Income", "account_sub_type": "SalesOfProductIncome", "fully_qualified_name": "Catering & contracts", "active": True},
    {"id": "238", "name": "Other Operating Income", "account_type": "Income", "account_sub_type": "OtherPrimaryIncome", "fully_qualified_name": "Other Operating Income", "active": True},
    {"id": "239", "name": "Discounts", "account_type": "Income", "account_sub_type": "DiscountsRefundsGiven", "fully_qualified_name": "Discounts", "active": True},
    # COGS
    {"id": "240", "name": "Food Costs", "account_type": "Cost of Goods Sold", "account_sub_type": "SuppliesMaterialsCogs", "fully_qualified_name": "Food Costs", "active": True},
    {"id": "241", "name": "Beverage Cost", "account_type": "Cost of Goods Sold", "account_sub_type": "SuppliesMaterialsCogs", "fully_qualified_name": "Beverage Cost", "active": True},
    {"id": "242", "name": "Merchandise Cost", "account_type": "Cost of Goods Sold", "account_sub_type": "SuppliesMaterialsCogs", "fully_qualified_name": "Merchandise Cost", "active": True},
    {"id": "243", "name": "Delivery & Direct Labor Cost", "account_type": "Cost of Goods Sold", "account_sub_type": "CostOfLaborCos", "fully_qualified_name": "Delivery & direct labor Cost", "active": True},
    {"id": "244", "name": "Merchant Account Fees", "account_type": "Cost of Goods Sold", "account_sub_type": "OtherCostsOfServiceCos", "fully_qualified_name": "Merchant Account Fees", "active": True},
    {"id": "245", "name": "Inventory Loss/Waste", "account_type": "Cost of Goods Sold", "account_sub_type": "SuppliesMaterialsCogs", "fully_qualified_name": "Inventory Loss/Waste", "active": True},
    # Expense - Payroll
    {"id": "246", "name": "Management Wages", "account_type": "Expense", "account_sub_type": "PayrollExpenses", "fully_qualified_name": "Payroll Expenses:Management Wages", "active": True},
    {"id": "247", "name": "Staff Wages", "account_type": "Expense", "account_sub_type": "PayrollExpenses", "fully_qualified_name": "Payroll Expenses:Staff Wages", "active": True},
    {"id": "248", "name": "Contract Labor", "account_type": "Expense", "account_sub_type": "PayrollExpenses", "fully_qualified_name": "Payroll Expenses:Contract Labor", "active": True},
    {"id": "249", "name": "Employee Benefits", "account_type": "Expense", "account_sub_type": "PayrollExpenses", "fully_qualified_name": "Payroll Expenses:Employee Benefits", "active": True},
    {"id": "250", "name": "Payroll Taxes", "account_type": "Expense", "account_sub_type": "TaxesPaid", "fully_qualified_name": "Payroll Expenses:Payroll Taxes", "active": True},
    # Expense - Direct Operating
    {"id": "251", "name": "Restaurant & Kitchen Supply", "account_type": "Expense", "account_sub_type": "SuppliesMaterials", "fully_qualified_name": "Direct Operating Expense:Restaurant & Kitchen Supply", "active": True},
    {"id": "252", "name": "Cleaning Supply & Expense", "account_type": "Expense", "account_sub_type": "SuppliesMaterials", "fully_qualified_name": "Direct Operating Expense:Cleaning Supply & Expense", "active": True},
    {"id": "253", "name": "Laundry - Linen - Uniforms", "account_type": "Expense", "account_sub_type": "SuppliesMaterials", "fully_qualified_name": "Direct Operating Expense:Laundry - Linen - Uniforms", "active": True},
    {"id": "254", "name": "Business Licenses and Permits", "account_type": "Expense", "account_sub_type": "TaxesPaid", "fully_qualified_name": "Direct Operating Expense:Business Licenses and Permits", "active": True},
    {"id": "255", "name": "POS - Tech support - Online services", "account_type": "Expense", "account_sub_type": "OfficeGeneralAdministrativeExpenses", "fully_qualified_name": "Direct Operating Expense:POS - Tech support", "active": True},
    {"id": "256", "name": "Advertising and Promotion", "account_type": "Expense", "account_sub_type": "AdvertisingPromotional", "fully_qualified_name": "Advertising and Promotion", "active": True},
    {"id": "257", "name": "Repairs and Maintenance", "account_type": "Expense", "account_sub_type": "RepairMaintenance", "fully_qualified_name": "Repairs and Maintenance", "active": True},
    {"id": "258", "name": "Utilities", "account_type": "Expense", "account_sub_type": "Utilities", "fully_qualified_name": "Utilities", "active": True},
    {"id": "259", "name": "Telephone & Internet", "account_type": "Expense", "account_sub_type": "Utilities", "fully_qualified_name": "Telephone & Internet Connection", "active": True},
    # Expense - G&A
    {"id": "260", "name": "Bad Debts - Over/short", "account_type": "Expense", "account_sub_type": "BadDebts", "fully_qualified_name": "General and Administrative:Bad Debts - Over/short", "active": True},
    {"id": "261", "name": "Bank Service Charges", "account_type": "Expense", "account_sub_type": "BankCharges", "fully_qualified_name": "General and Administrative:Bank Service Charges", "active": True},
    {"id": "262", "name": "Insurance", "account_type": "Expense", "account_sub_type": "Insurance", "fully_qualified_name": "General and Administrative:Insurance", "active": True},
    {"id": "263", "name": "Professional Fees", "account_type": "Expense", "account_sub_type": "LegalProfessionalFees", "fully_qualified_name": "General and Administrative:Professional Fees", "active": True},
    {"id": "264", "name": "Office Supplies", "account_type": "Expense", "account_sub_type": "OfficeGeneralAdministrativeExpenses", "fully_qualified_name": "General and Administrative:Office Supplies", "active": True},
    {"id": "265", "name": "Rent Expense", "account_type": "Expense", "account_sub_type": "RentOrLeaseOfBuildings", "fully_qualified_name": "Rent Expense", "active": True},
    {"id": "266", "name": "Equipment Rental", "account_type": "Expense", "account_sub_type": "EquipmentRental", "fully_qualified_name": "Equipment Rental", "active": True},
    # Other Expense
    {"id": "267", "name": "Depreciation Expense", "account_type": "Expense", "account_sub_type": "OtherMiscellaneousServiceCost", "fully_qualified_name": "Depreciation Expense", "active": True},
    {"id": "268", "name": "Other Expense", "account_type": "Other Expense", "account_sub_type": "OtherMiscellaneousExpense", "fully_qualified_name": "Other expense", "active": True},
]


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------
def run_matching_for_fixture(fixture_name: str, qb_accounts: list[dict]) -> dict:
    """Run POS needs matching against a fixture and return results."""
    items = []
    matched_count = 0
    candidate_count = 0
    unmatched_count = 0

    for need in POS_ACCOUNTING_NEEDS:
        search_name = need.label
        search_type = need.expected_qb_types[0] if need.expected_qb_types else "Income"

        # Match with label
        candidates = find_best_matches(
            template_name=search_name,
            template_type=search_type,
            template_sub_type=need.expected_qb_sub_type,
            qb_accounts=qb_accounts,
            max_candidates=5,
            min_score=0.15,
        )

        # Also try each search hint
        for hint in need.search_hints:
            hint_candidates = find_best_matches(
                template_name=hint,
                template_type=search_type,
                template_sub_type=need.expected_qb_sub_type,
                qb_accounts=qb_accounts,
                max_candidates=3,
                min_score=0.15,
            )
            existing_ids = {c.qb_account_id for c in candidates}
            for hc in hint_candidates:
                if hc.qb_account_id not in existing_ids:
                    candidates.append(hc)
                    existing_ids.add(hc.qb_account_id)
                else:
                    for i, existing in enumerate(candidates):
                        if existing.qb_account_id == hc.qb_account_id and hc.score > existing.score:
                            candidates[i] = hc
                            break

        candidates.sort(key=lambda c: c.score, reverse=True)
        candidates = candidates[:5]

        best = candidates[0] if candidates else None
        if best and best.score >= THRESHOLD_HIGH:
            status = "matched"
            matched_count += 1
        elif best and best.score >= THRESHOLD_MEDIUM:
            status = "candidates"
            candidate_count += 1
        else:
            status = "unmatched"
            unmatched_count += 1

        items.append({
            "need_key": need.key,
            "need_label": need.label,
            "required": need.required,
            "status": status,
            "best_match_name": best.qb_account_name if best else None,
            "best_match_score": best.score if best else 0,
            "best_match_confidence": best.confidence if best else "none",
            "num_candidates": len(candidates),
            "all_candidates": [(c.qb_account_name, round(c.score, 3)) for c in candidates[:3]],
        })

    total = len(POS_ACCOUNTING_NEEDS)
    covered = matched_count + candidate_count
    if total == 0:
        grade = "A"
    elif matched_count / total >= 1.0:
        grade = "A"
    elif covered / total >= 0.90:
        grade = "A"
    elif covered / total >= 0.60:
        grade = "B"
    elif covered / total >= 0.40:
        grade = "C"
    else:
        grade = "F"

    return {
        "fixture": fixture_name,
        "total_qb_accounts": len(qb_accounts),
        "total_needs": total,
        "matched": matched_count,
        "candidates": candidate_count,
        "unmatched": unmatched_count,
        "coverage_pct": round(covered / total * 100, 1) if total else 0,
        "grade": grade,
        "items": items,
    }


def print_results(result: dict) -> None:
    """Pretty-print matching results."""
    print(f"\n{'='*80}")
    print(f"  FIXTURE: {result['fixture']}")
    print(f"  QB Accounts: {result['total_qb_accounts']}  |  POS Needs: {result['total_needs']}")
    print(f"  Grade: {result['grade']}  |  Matched: {result['matched']}  |  Candidates: {result['candidates']}  |  Unmatched: {result['unmatched']}")
    print(f"  Coverage: {result['coverage_pct']}%")
    print(f"{'='*80}")

    # Color codes
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    DIM = "\033[2m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    for item in result["items"]:
        req = "*" if item["required"] else " "
        status = item["status"]

        if status == "matched":
            icon = f"{GREEN}[OK]{RESET}"
        elif status == "candidates":
            icon = f"{YELLOW}[??]{RESET}"
        else:
            icon = f"{RED}[--]{RESET}"

        score = item["best_match_score"]
        match_name = item["best_match_name"] or "(none)"

        print(f"  {icon} {req} {item['need_label']:<30s} -> {match_name:<35s} {BOLD}{score:.3f}{RESET}")

        # Show other candidates if status is "candidates"
        if status == "candidates" and len(item["all_candidates"]) > 1:
            for name, sc in item["all_candidates"][1:]:
                print(f"       {DIM}alt: {name:<35s} {sc:.3f}{RESET}")

    # Summary of problems
    unmatched_required = [i for i in result["items"] if i["status"] == "unmatched" and i["required"]]
    if unmatched_required:
        print(f"\n  {RED}{BOLD}UNMATCHED REQUIRED:{RESET}")
        for item in unmatched_required:
            print(f"    - {item['need_label']} ({item['need_key']})")

    print()


def main():
    fixtures = [
        ("Pakistani Restaurant (35 accts)", FIXTURE_PAKISTANI_RESTAURANT),
        ("Generic Small Business (34 accts)", FIXTURE_GENERIC_SMALL_BUSINESS),
        ("US Restaurant - SimpleRestAcctg (68 accts)", FIXTURE_US_RESTAURANT),
    ]

    all_results = []
    for name, accounts in fixtures:
        result = run_matching_for_fixture(name, accounts)
        all_results.append(result)
        print_results(result)

    # Summary table
    print(f"\n{'='*80}")
    print(f"  SUMMARY")
    print(f"{'='*80}")
    print(f"  {'Fixture':<45s} {'Grade':>5s} {'Matched':>8s} {'Cands':>6s} {'Unmatched':>10s} {'Coverage':>10s}")
    print(f"  {'-'*45} {'-'*5} {'-'*8} {'-'*6} {'-'*10} {'-'*10}")
    for r in all_results:
        print(f"  {r['fixture']:<45s} {r['grade']:>5s} {r['matched']:>8d} {r['candidates']:>6d} {r['unmatched']:>10d} {r['coverage_pct']:>9.1f}%")
    print()


if __name__ == "__main__":
    main()
