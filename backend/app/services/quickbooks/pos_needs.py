"""
POS Accounting Needs — the fixed list of accounting concepts the POS system
requires mapped to QuickBooks accounts.

This replaces the 40-template system. Instead of selecting a template,
the system knows what it needs and fuzzy-matches directly against the
JV partner's actual QB Chart of Accounts.

Each need has:
  - key: unique identifier used as mapping_type in QBAccountMapping
  - label: human-readable name for the admin UI
  - description: explains what this maps to in restaurant accounting
  - expected_qb_type: QB AccountType(s) this should map to
  - expected_qb_sub_type: optional QB AccountSubType hint
  - required: if True, sync won't work without this mapping
  - search_hints: keywords the fuzzy engine uses to find matches
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AccountingNeed:
    """One accounting concept the POS needs mapped to QB."""
    key: str
    label: str
    description: str
    expected_qb_types: list[str]
    expected_qb_sub_type: str | None = None
    required: bool = False
    search_hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "expected_qb_types": self.expected_qb_types,
            "expected_qb_sub_type": self.expected_qb_sub_type,
            "required": self.required,
            "search_hints": self.search_hints,
        }


# ---------------------------------------------------------------------------
# The master list — every accounting concept the POS cares about
# ---------------------------------------------------------------------------
POS_ACCOUNTING_NEEDS: list[AccountingNeed] = [
    # ── INCOME ──────────────────────────────────────────────
    AccountingNeed(
        key="income",
        label="Food Sales Income",
        description="Primary revenue account for food/beverage sales (dine-in, takeaway, delivery)",
        expected_qb_types=["Income", "Other Income"],
        expected_qb_sub_type="SalesOfProductIncome",
        required=True,
        search_hints=["food sales", "sales", "revenue", "income", "food revenue",
                       "dining revenue", "restaurant sales", "food income"],
    ),
    AccountingNeed(
        key="beverage_income",
        label="Beverage Sales Income",
        description="Separate revenue tracking for beverages (chai, juice, soft drinks)",
        expected_qb_types=["Income", "Other Income"],
        expected_qb_sub_type="SalesOfProductIncome",
        required=False,
        search_hints=["beverage sales", "drink sales", "beverage revenue",
                       "chai", "juice", "sharbat"],
    ),

    # ── COST OF GOODS SOLD ──────────────────────────────────
    AccountingNeed(
        key="cogs",
        label="Cost of Goods Sold",
        description="Direct food costs — ingredients, raw materials, recipe costs",
        expected_qb_types=["Cost of Goods Sold"],
        expected_qb_sub_type="SuppliesMaterialsCogs",
        required=True,
        search_hints=["cogs", "cost of goods", "food cost", "raw material",
                       "ingredient", "recipe cost", "purchase", "procurement"],
    ),

    # ── TAX ─────────────────────────────────────────────────
    AccountingNeed(
        key="tax_payable",
        label="Sales Tax Payable",
        description="Tax collected on sales — GST/FBR (17%), PRA/PST (16%), or VAT",
        expected_qb_types=["Other Current Liability"],
        expected_qb_sub_type="GlobalTaxPayable",
        required=True,
        search_hints=["tax payable", "sales tax", "gst", "fbr", "pra", "pst",
                       "sst", "vat", "tax collected", "government tax",
                       "federal tax", "provincial tax", "withholding"],
    ),

    # ── BANK / PAYMENT METHODS ──────────────────────────────
    AccountingNeed(
        key="bank",
        label="Bank / Deposit Account",
        description="Where card payments and bank transfers are deposited",
        expected_qb_types=["Bank"],
        expected_qb_sub_type="Checking",
        required=True,
        search_hints=["bank", "checking", "current account", "savings",
                       "deposit", "hbl", "meezan", "ubl", "mcb", "allied", "nbp"],
    ),
    AccountingNeed(
        key="cash",
        label="Cash on Hand",
        description="Physical cash register / drawer for cash payments",
        expected_qb_types=["Bank", "Other Current Asset"],
        expected_qb_sub_type="CashOnHand",
        required=False,
        search_hints=["cash", "register", "drawer", "till", "petty cash",
                       "cash on hand", "cash register"],
    ),
    AccountingNeed(
        key="mobile_wallet",
        label="Mobile Wallet Account",
        description="JazzCash, Easypaisa, SadaPay digital payment deposits",
        expected_qb_types=["Bank", "Other Current Asset"],
        required=False,
        search_hints=["jazzcash", "easypaisa", "sadapay", "nayapay",
                       "mobile wallet", "digital payment"],
    ),

    # ── ADJUSTMENTS ─────────────────────────────────────────
    AccountingNeed(
        key="discount",
        label="Discounts Given",
        description="Customer discounts, promotional offers, loyalty discounts",
        expected_qb_types=["Income", "Other Income", "Expense"],
        expected_qb_sub_type="DiscountsRefundsGiven",
        required=True,
        search_hints=["discount", "rebate", "allowance", "markdown",
                       "concession", "promotional discount"],
    ),
    AccountingNeed(
        key="rounding",
        label="Rounding Adjustment",
        description="Small rounding differences on cash transactions",
        expected_qb_types=["Expense", "Other Expense", "Income"],
        expected_qb_sub_type="OtherMiscellaneousExpense",
        required=True,
        search_hints=["rounding", "round off", "adjustment", "difference"],
    ),
    AccountingNeed(
        key="cash_over_short",
        label="Cash Over/Short",
        description="Discrepancies between expected and actual cash drawer totals",
        expected_qb_types=["Expense", "Other Expense"],
        expected_qb_sub_type="OtherMiscellaneousExpense",
        required=True,
        search_hints=["over short", "cash over", "cash short", "variance",
                       "discrepancy", "cash over short"],
    ),

    # ── SERVICE / TIPS ──────────────────────────────────────
    AccountingNeed(
        key="tips",
        label="Tips / Gratuity",
        description="Tips collected from customers and passed to staff",
        expected_qb_types=["Other Current Liability", "Income"],
        required=False,
        search_hints=["tip", "tips", "gratuity", "bakshish"],
    ),
    AccountingNeed(
        key="service_charge",
        label="Service Charge",
        description="Mandatory service charge added to bills",
        expected_qb_types=["Income", "Other Current Liability"],
        required=False,
        search_hints=["service charge", "service fee"],
    ),

    # ── DELIVERY ────────────────────────────────────────────
    AccountingNeed(
        key="delivery_fee",
        label="Delivery Fee Income",
        description="Delivery charges collected from customers",
        expected_qb_types=["Income", "Other Income"],
        required=False,
        search_hints=["delivery fee", "delivery charge", "delivery income",
                       "shipping", "dispatch"],
    ),
    AccountingNeed(
        key="foodpanda_commission",
        label="Platform Commission Expense",
        description="Commission paid to Foodpanda, Cheetay, or other delivery platforms",
        expected_qb_types=["Expense", "Cost of Goods Sold"],
        expected_qb_sub_type="OtherMiscellaneousServiceCost",
        required=False,
        search_hints=["foodpanda", "commission", "platform fee", "cheetay",
                       "careem", "bykea", "aggregator"],
    ),

    # ── GIFT CARDS ──────────────────────────────────────────
    AccountingNeed(
        key="gift_card_liability",
        label="Gift Card Liability",
        description="Unredeemed gift cards / vouchers — liability until used",
        expected_qb_types=["Other Current Liability"],
        required=False,
        search_hints=["gift card", "voucher", "coupon", "credit note",
                       "gift voucher"],
    ),

    # ── COMMON EXPENSES ────────────────────────────────────
    AccountingNeed(
        key="rent_expense",
        label="Rent / Occupancy",
        description="Monthly rent for restaurant premises",
        expected_qb_types=["Expense"],
        expected_qb_sub_type="OccupancyCost",
        required=False,
        search_hints=["rent", "lease", "occupancy", "premises", "kiraya"],
    ),
    AccountingNeed(
        key="salary_expense",
        label="Salaries & Wages",
        description="Staff payroll — kitchen, service, delivery riders",
        expected_qb_types=["Expense"],
        expected_qb_sub_type="PayrollExpenses",
        required=False,
        search_hints=["salary", "salaries", "wages", "payroll", "staff cost",
                       "compensation", "tankhwah"],
    ),
    AccountingNeed(
        key="utility_expense",
        label="Utilities",
        description="Electricity, gas, water bills",
        expected_qb_types=["Expense"],
        expected_qb_sub_type="Utilities",
        required=False,
        search_hints=["utility", "utilities", "electricity", "gas", "water",
                       "bijli", "sui gas"],
    ),
    AccountingNeed(
        key="packaging_expense",
        label="Packaging & Disposables",
        description="Takeaway containers, bags, disposable items",
        expected_qb_types=["Expense", "Cost of Goods Sold"],
        required=False,
        search_hints=["packaging", "container", "disposable", "packing",
                       "takeaway supplies"],
    ),
]

# ---------------------------------------------------------------------------
# Quick lookup helpers
# ---------------------------------------------------------------------------
NEEDS_BY_KEY: dict[str, AccountingNeed] = {n.key: n for n in POS_ACCOUNTING_NEEDS}
REQUIRED_NEEDS: list[AccountingNeed] = [n for n in POS_ACCOUNTING_NEEDS if n.required]
OPTIONAL_NEEDS: list[AccountingNeed] = [n for n in POS_ACCOUNTING_NEEDS if not n.required]

def get_all_needs_as_dicts() -> list[dict]:
    """Return all needs as serializable dicts for API responses."""
    return [n.to_dict() for n in POS_ACCOUNTING_NEEDS]
