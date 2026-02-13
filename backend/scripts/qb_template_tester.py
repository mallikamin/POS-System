#!/usr/bin/env python3
from __future__ import annotations  # PEP 604 unions on Python 3.9

"""QuickBooks Template Test Harness — tests all 40 templates.

For each template, simulates POS transactions and shows exactly how they
map to QuickBooks entities, with full journey display:
  POS Terminal → Backend API → Database → QuickBooks Online

Test scenarios per template:
  1. Completed dine-in order       → Sales Receipt
  2. Completed takeaway order      → Sales Receipt (different channel)
  3. Voided order                  → Credit Memo
  4. Partial refund                → Refund Receipt
  5. Daily close (all completed)   → Journal Entry + Deposit

Usage:
    cd POS-Project
    python backend/scripts/qb_template_tester.py                        # Summary of all 40
    python backend/scripts/qb_template_tester.py pakistani_restaurant   # Full detail for one
    python backend/scripts/qb_template_tester.py --all                  # Full detail, all 40
    python backend/scripts/qb_template_tester.py --all > report.txt     # Save to file
    python backend/scripts/qb_template_tester.py --list                 # Template names only
    python backend/scripts/qb_template_tester.py --json biryani_house   # JSON payload output
"""

import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Import templates directly (bypass __init__.py to avoid DB/settings deps)
# ---------------------------------------------------------------------------
import importlib.util

_templates_path = Path(__file__).resolve().parent.parent / "app" / "services" / "quickbooks" / "templates.py"
_spec = importlib.util.spec_from_file_location("qb_templates", _templates_path)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
MAPPING_TEMPLATES: dict[str, dict[str, Any]] = _mod.MAPPING_TEMPLATES  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Currency helpers (from sync.py — pure functions)
# ---------------------------------------------------------------------------

def paisa_to_decimal(paisa: int) -> str:
    d = Decimal(paisa) / Decimal(100)
    return str(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def format_pkr(paisa: int) -> str:
    return f"Rs.{paisa_to_decimal(paisa)}"


# ---------------------------------------------------------------------------
# Mock POS data structures
# ---------------------------------------------------------------------------

@dataclass
class MockModifier:
    name: str
    price: int  # paisa


@dataclass
class MockOrderItem:
    menu_item_id: uuid.UUID
    name: str
    category_name: str
    category_id: uuid.UUID
    quantity: int
    unit_price: int       # paisa
    total: int            # paisa
    modifiers: list[MockModifier] = field(default_factory=list)
    notes: str | None = None


@dataclass
class MockOrder:
    id: uuid.UUID
    order_number: str
    order_type: str       # dine_in | takeaway | call_center | foodpanda
    status: str           # completed | voided
    items: list[MockOrderItem]
    subtotal: int         # paisa
    tax_amount: int       # paisa
    discount_amount: int  # paisa
    total: int            # paisa
    customer_name: str | None = None
    customer_phone: str | None = None
    table_label: str | None = None
    notes: str | None = None
    payment_method: str = "Cash"
    payment_status: str = "paid"
    delivery_fee: int = 0          # paisa
    platform_commission: int = 0   # paisa
    platform_name: str | None = None
    branch_name: str | None = None  # for multi-franchise scenarios
    created_at: datetime = field(
        default_factory=lambda: datetime(2026, 2, 13, 13, 0, 0, tzinfo=timezone.utc)
    )


# ---------------------------------------------------------------------------
# Category → Income Account routing (synonym-aware keyword matching)
# ---------------------------------------------------------------------------

_CATEGORY_SYNONYMS: dict[str, list[str]] = {
    "drinks": ["beverage", "drink"],
    "beverage": ["drinks", "drink"],
    "bread": ["naan", "roti", "paratha", "tandoori"],
    "naan": ["bread", "roti"],
    "bbq": ["grill", "tikka", "kebab", "kabab"],
    "grill": ["bbq", "tikka"],
    "tikka": ["bbq", "grill", "kebab"],
    "kebab": ["bbq", "tikka", "kabab"],
    "curry": ["karahi", "salan", "handi"],
    "karahi": ["curry", "salan", "handi"],
    "rice": ["biryani", "pulao"],
    "biryani": ["rice", "pulao"],
    "sweets": ["dessert", "mithai", "sweet"],
    "dessert": ["sweets", "mithai", "sweet"],
    "mithai": ["sweets", "dessert"],
    "tea": ["chai", "doodh"],
    "chai": ["tea", "doodh"],
    "juice": ["smoothie", "fresh"],
    "smoothie": ["juice", "fresh"],
    "chicken": ["poultry"],
    "poultry": ["chicken"],
    "seafood": ["fish", "prawn", "crab"],
    "fish": ["seafood", "machli"],
    "sides": ["raita", "chutney", "salad"],
    "pizza": ["flatbread"],
    "burger": ["sandwich"],
    "pasta": ["spaghetti", "noodle"],
    "steak": ["beef", "tenderloin"],
    "sushi": ["sashimi", "maki"],
    "coffee": ["espresso", "latte", "cappuccino"],
    "ice": ["gelato", "kulfi", "frozen"],
    "wrap": ["shawarma", "roll"],
    "shawarma": ["wrap", "doner"],
    "fried": ["crispy", "crunchy"],
    "nihari": ["paye", "breakfast"],
    "paye": ["nihari", "trotters"],
    "sajji": ["roast", "whole"],
    "chapli": ["specialty", "peshawari"],
}

_STOP_WORDS = frozenset({
    "sales", "revenue", "cost", "of", "and", "&", "the", "a", "an",
    "income", "expense", "total", "net", "gross", "payable", "receivable",
})


def _normalize_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from a string."""
    words = text.lower().replace("&", " ").replace("/", " ").replace("-", " ").replace("(", " ").replace(")", " ").split()
    return {w for w in words if w not in _STOP_WORDS and len(w) > 1}


def _expand_with_synonyms(keywords: set[str]) -> set[str]:
    """Expand keyword set with known synonyms."""
    expanded = keywords.copy()
    for kw in keywords:
        if kw in _CATEGORY_SYNONYMS:
            expanded.update(_CATEGORY_SYNONYMS[kw])
    return expanded


# ---------------------------------------------------------------------------
# Mapping resolver (simulates MappingService without DB)
# ---------------------------------------------------------------------------

class MockMappingResolver:
    """Resolves account mappings from a template's mapping list.

    Mirrors the real ``SyncService._get_account_mapping()`` resolution:
      1. Try category-specific match (keyword matching against income accts)
      2. Fall back to the default income account
    """

    def __init__(self, template_mappings: list[dict]):
        self._by_type: dict[str, list[dict]] = {}
        self._qb_counter = 100

        for m in template_mappings:
            mt = m["mapping_type"]
            self._qb_counter += 1
            m["_qb_id"] = str(self._qb_counter)

            if mt not in self._by_type:
                self._by_type[mt] = []
            self._by_type[mt].append(m)

    def get_default(self, mapping_type: str) -> dict | None:
        mappings = self._by_type.get(mapping_type, [])
        for m in mappings:
            if m.get("is_default"):
                return m
        return mappings[0] if mappings else None

    def get_all(self, mapping_type: str) -> list[dict]:
        return self._by_type.get(mapping_type, [])

    def has_type(self, mapping_type: str) -> bool:
        return mapping_type in self._by_type

    def resolve_income_for_category(self, category_name: str) -> dict | None:
        """Resolve the best income account for a POS menu category.

        Uses keyword matching with synonym expansion:
          "Rice & Biryani" → matches "Biryani & Rice Sales"
          "BBQ & Grill"    → matches "BBQ & Grill Sales"
          "Drinks"         → matches "Beverage Sales" (via synonym)
          "Sides"          → falls back to default "Food Sales"
        """
        income_accounts = self.get_all("income")
        if not income_accounts:
            return None

        cat_keywords = _expand_with_synonyms(_normalize_keywords(category_name))
        if not cat_keywords:
            return self.get_default("income")

        best_match = None
        best_score = 0

        for acct in income_accounts:
            if acct.get("is_default"):
                continue  # Skip default — use it only as fallback
            acct_keywords = _normalize_keywords(acct["name"])
            overlap = len(cat_keywords & acct_keywords)
            if overlap > best_score:
                best_score = overlap
                best_match = acct

        if best_match and best_score > 0:
            return best_match
        return self.get_default("income")


# ---------------------------------------------------------------------------
# Sample order factory
# ---------------------------------------------------------------------------

def make_sample_orders() -> dict[str, MockOrder]:
    """Create realistic sample POS orders for template testing."""

    cat_bbq = uuid.uuid4()
    cat_rice = uuid.uuid4()
    cat_drinks = uuid.uuid4()
    cat_dessert = uuid.uuid4()
    cat_bread = uuid.uuid4()
    cat_curry = uuid.uuid4()

    # --- Order 1: Completed dine-in (3 items, 1 with modifiers) ---
    o1_items = [
        MockOrderItem(
            menu_item_id=uuid.uuid4(),
            name="Chicken Biryani",
            category_name="Rice & Biryani",
            category_id=cat_rice,
            quantity=2,
            unit_price=45000,
            total=90000,
        ),
        MockOrderItem(
            menu_item_id=uuid.uuid4(),
            name="Seekh Kabab (6 pcs)",
            category_name="BBQ & Grill",
            category_id=cat_bbq,
            quantity=3,
            unit_price=18000,
            total=54000,
            modifiers=[
                MockModifier(name="Extra Spicy", price=0),
                MockModifier(name="Green Chutney", price=2000),
            ],
        ),
        MockOrderItem(
            menu_item_id=uuid.uuid4(),
            name="Mint Raita",
            category_name="Sides",
            category_id=cat_rice,
            quantity=1,
            unit_price=8000,
            total=8000,
        ),
    ]
    sub1 = sum(i.total for i in o1_items)
    tax1 = int(sub1 * 16 / 100)

    order1 = MockOrder(
        id=uuid.uuid4(),
        order_number="260213-001",
        order_type="dine_in",
        status="completed",
        items=o1_items,
        subtotal=sub1,
        tax_amount=tax1,
        discount_amount=0,
        total=sub1 + tax1,
        table_label="T-05",
        payment_method="Cash",
        created_at=datetime(2026, 2, 13, 13, 45, 0, tzinfo=timezone.utc),
    )

    # --- Order 2: Completed takeaway (with discount) ---
    o2_items = [
        MockOrderItem(
            menu_item_id=uuid.uuid4(),
            name="Chicken Karahi (Half)",
            category_name="Karahi & Curry",
            category_id=cat_curry,
            quantity=1,
            unit_price=120000,
            total=120000,
            notes="Less oil",
        ),
        MockOrderItem(
            menu_item_id=uuid.uuid4(),
            name="Tandoori Naan",
            category_name="Bread",
            category_id=cat_bread,
            quantity=4,
            unit_price=4000,
            total=16000,
        ),
        MockOrderItem(
            menu_item_id=uuid.uuid4(),
            name="Lassi (Sweet)",
            category_name="Drinks",
            category_id=cat_drinks,
            quantity=2,
            unit_price=15000,
            total=30000,
        ),
    ]
    sub2 = sum(i.total for i in o2_items)
    tax2 = int(sub2 * 16 / 100)
    disc2 = 10000  # Rs.100 discount

    order2 = MockOrder(
        id=uuid.uuid4(),
        order_number="260213-002",
        order_type="takeaway",
        status="completed",
        items=o2_items,
        subtotal=sub2,
        tax_amount=tax2,
        discount_amount=disc2,
        total=sub2 + tax2 - disc2,
        customer_name="Ahmed Khan",
        customer_phone="03001234567",
        payment_method="Credit Card",
        created_at=datetime(2026, 2, 13, 14, 20, 0, tzinfo=timezone.utc),
    )

    # --- Order 3: Voided dine-in (customer complaint / wrong order) ---
    o3_items = [
        MockOrderItem(
            menu_item_id=uuid.uuid4(),
            name="Mutton Biryani",
            category_name="Rice & Biryani",
            category_id=cat_rice,
            quantity=1,
            unit_price=55000,
            total=55000,
        ),
        MockOrderItem(
            menu_item_id=uuid.uuid4(),
            name="Naan",
            category_name="Bread",
            category_id=cat_bread,
            quantity=2,
            unit_price=4000,
            total=8000,
        ),
    ]
    sub3 = sum(i.total for i in o3_items)
    tax3 = int(sub3 * 16 / 100)

    order3 = MockOrder(
        id=uuid.uuid4(),
        order_number="260213-003",
        order_type="dine_in",
        status="voided",
        items=o3_items,
        subtotal=sub3,
        tax_amount=tax3,
        discount_amount=0,
        total=sub3 + tax3,
        table_label="T-12",
        notes="Wrong order delivered — voided by manager",
        created_at=datetime(2026, 2, 13, 15, 10, 0, tzinfo=timezone.utc),
    )

    # --- Order 4: Call center delivery (completed) ---
    o4_items = [
        MockOrderItem(
            menu_item_id=uuid.uuid4(),
            name="Mutton Biryani",
            category_name="Rice & Biryani",
            category_id=cat_rice,
            quantity=3,
            unit_price=55000,
            total=165000,
        ),
        MockOrderItem(
            menu_item_id=uuid.uuid4(),
            name="Gulab Jamun (6 pcs)",
            category_name="Desserts",
            category_id=cat_dessert,
            quantity=2,
            unit_price=15000,
            total=30000,
        ),
    ]
    sub4 = sum(i.total for i in o4_items)
    tax4 = int(sub4 * 16 / 100)

    order4 = MockOrder(
        id=uuid.uuid4(),
        order_number="260213-004",
        order_type="call_center",
        status="completed",
        items=o4_items,
        subtotal=sub4,
        tax_amount=tax4,
        discount_amount=0,
        total=sub4 + tax4,
        customer_name="Fatima Ali",
        customer_phone="03219876543",
        payment_method="JazzCash",
        delivery_fee=15000,  # Rs.150 delivery fee
        created_at=datetime(2026, 2, 13, 19, 30, 0, tzinfo=timezone.utc),
    )

    # --- Order 5: Foodpanda platform order (completed) ---
    o5_items = [
        MockOrderItem(
            menu_item_id=uuid.uuid4(),
            name="Chicken Biryani",
            category_name="Rice & Biryani",
            category_id=cat_rice,
            quantity=2,
            unit_price=45000,
            total=90000,
        ),
        MockOrderItem(
            menu_item_id=uuid.uuid4(),
            name="Chicken Tikka (8 pcs)",
            category_name="BBQ & Grill",
            category_id=cat_bbq,
            quantity=1,
            unit_price=48000,
            total=48000,
        ),
        MockOrderItem(
            menu_item_id=uuid.uuid4(),
            name="Raita",
            category_name="Sides",
            category_id=cat_rice,
            quantity=1,
            unit_price=8000,
            total=8000,
        ),
    ]
    sub5 = sum(i.total for i in o5_items)
    tax5 = int(sub5 * 16 / 100)
    platform_comm = int(sub5 * 30 / 100)  # 30% Foodpanda commission

    order5 = MockOrder(
        id=uuid.uuid4(),
        order_number="260213-005",
        order_type="foodpanda",
        status="completed",
        items=o5_items,
        subtotal=sub5,
        tax_amount=tax5,
        discount_amount=0,
        total=sub5 + tax5,
        customer_name="Foodpanda Customer",
        customer_phone="N/A",
        payment_method="Foodpanda",
        platform_name="Foodpanda",
        platform_commission=platform_comm,
        created_at=datetime(2026, 2, 13, 20, 15, 0, tzinfo=timezone.utc),
    )

    return {
        "dine_in_completed": order1,
        "takeaway_completed": order2,
        "dine_in_voided": order3,
        "call_center_completed": order4,
        "foodpanda_completed": order5,
    }


# ---------------------------------------------------------------------------
# Payload builders (mirror sync.py logic, operate on mock data)
# ---------------------------------------------------------------------------

ORDER_TYPE_LABELS = {
    "dine_in": "Dine-In",
    "takeaway": "Takeaway",
    "call_center": "Call Center",
    "foodpanda": "Foodpanda",
    "delivery": "Delivery",
}


def _build_line_items(order: MockOrder, resolver: MockMappingResolver) -> list[dict]:
    lines: list[dict] = []

    for idx, item in enumerate(order.items, 1):
        desc = item.name
        if item.modifiers:
            desc += f" ({', '.join(m.name for m in item.modifiers)})"
        if item.notes:
            desc += f" -- {item.notes}"

        # Category-level routing: try to match item's category to a
        # specialized income account, fall back to default
        income_mapping = resolver.resolve_income_for_category(item.category_name)

        acct_ref = {}
        if income_mapping:
            acct_ref = {
                "value": income_mapping["_qb_id"],
                "name": income_mapping["name"],
            }

        line: dict[str, Any] = {
            "Id": str(idx),
            "LineNum": idx,
            "Amount": paisa_to_decimal(item.total),
            "Description": desc,
            "DetailType": "SalesItemLineDetail",
            "SalesItemLineDetail": {
                "Qty": item.quantity,
                "UnitPrice": paisa_to_decimal(item.unit_price),
            },
        }
        if acct_ref:
            line["SalesItemLineDetail"]["ItemAccountRef"] = acct_ref

        # Routing metadata (for display only, not sent to QB)
        is_default = income_mapping and income_mapping.get("is_default")
        line["_route"] = {
            "category": item.category_name,
            "account": income_mapping["name"] if income_mapping else "UNMAPPED",
            "type": (
                f"{income_mapping['account_type']}/{income_mapping['account_sub_type']}"
                if income_mapping else "N/A"
            ),
            "match": "default" if is_default else "category",
        }
        lines.append(line)

    # Discount line
    if order.discount_amount > 0:
        disc_mapping = resolver.get_default("discount")
        lines.append({
            "Id": str(len(lines) + 1),
            "LineNum": len(lines) + 1,
            "Amount": paisa_to_decimal(order.discount_amount),
            "DetailType": "DiscountLineDetail",
            "DiscountLineDetail": {"PercentBased": False, "DiscountPercent": 0},
            "_route": {
                "account": disc_mapping["name"] if disc_mapping else "UNMAPPED",
                "type": (
                    f"{disc_mapping['account_type']}/{disc_mapping['account_sub_type']}"
                    if disc_mapping else "N/A"
                ),
            },
        })
    return lines


def build_sales_receipt(order: MockOrder, resolver: MockMappingResolver) -> dict:
    lines = _build_line_items(order, resolver)
    label = ORDER_TYPE_LABELS.get(order.order_type, order.order_type)
    customer = order.customer_name or "Walk-In Customer"
    note = f"{label} order {order.order_number}"

    payload: dict[str, Any] = {
        "_qb_endpoint": "POST /v3/company/{realm}/salesreceipt",
        "DocNumber": order.order_number,
        "TxnDate": order.created_at.strftime("%Y-%m-%d"),
        "Line": lines,
        "TxnTaxDetail": {"TotalTax": paisa_to_decimal(order.tax_amount)},
        "CustomerRef": {"value": "MOCK-C1", "name": customer},
        "TotalAmt": paisa_to_decimal(order.total),
        "PrivateNote": note,
        "CustomerMemo": {"value": f"Thank you! Order #{order.order_number}"},
        "PrintStatus": "NeedToPrint",
        "EmailStatus": "NotSet",
    }

    bank = resolver.get_default("bank")
    if bank:
        payload["DepositToAccountRef"] = {"value": bank["_qb_id"], "name": bank["name"]}

    if order.order_type == "dine_in" and order.table_label:
        payload["PrivateNote"] += f" | Table: {order.table_label}"

    if order.platform_name:
        payload["PrivateNote"] += f" | Platform: {order.platform_name}"

    if order.payment_method:
        payload["PaymentMethodRef"] = {"value": "PM-1", "name": order.payment_method}

    return payload


def build_credit_memo(order: MockOrder, resolver: MockMappingResolver) -> dict:
    lines = _build_line_items(order, resolver)
    customer = order.customer_name or "Walk-In Customer"

    return {
        "_qb_endpoint": "POST /v3/company/{realm}/creditmemo",
        "DocNumber": f"VOID-{order.order_number}",
        "TxnDate": order.created_at.strftime("%Y-%m-%d"),
        "Line": lines,
        "TxnTaxDetail": {"TotalTax": paisa_to_decimal(order.tax_amount)},
        "CustomerRef": {"value": "MOCK-C1", "name": customer},
        "TotalAmt": paisa_to_decimal(order.total),
        "PrivateNote": f"Void of order {order.order_number}"
        + (f" — {order.notes}" if order.notes else ""),
    }


def build_refund_receipt(
    order: MockOrder, refund_paisa: int, resolver: MockMappingResolver,
) -> dict:
    customer = order.customer_name or "Walk-In Customer"

    if refund_paisa >= order.total:
        lines = _build_line_items(order, resolver)
    else:
        # Partial refund — single line with default income account
        income_mapping = resolver.get_default("income")
        acct_ref = {}
        if income_mapping:
            acct_ref = {
                "value": income_mapping["_qb_id"],
                "name": income_mapping["name"],
            }

        refund_line: dict[str, Any] = {
            "Id": "1", "LineNum": 1,
            "Amount": paisa_to_decimal(refund_paisa),
            "Description": f"Partial refund for order {order.order_number}",
            "DetailType": "SalesItemLineDetail",
            "SalesItemLineDetail": {
                "Qty": 1,
                "UnitPrice": paisa_to_decimal(refund_paisa),
            },
            "_route": {
                "category": "Refund",
                "account": income_mapping["name"] if income_mapping else "UNMAPPED",
                "type": (
                    f"{income_mapping['account_type']}/{income_mapping['account_sub_type']}"
                    if income_mapping else "N/A"
                ),
                "match": "default",
            },
        }
        if acct_ref:
            refund_line["SalesItemLineDetail"]["ItemAccountRef"] = acct_ref
        lines = [refund_line]

    payload: dict[str, Any] = {
        "_qb_endpoint": "POST /v3/company/{realm}/refundreceipt",
        "DocNumber": f"REF-{order.order_number}",
        "TxnDate": order.created_at.strftime("%Y-%m-%d"),
        "Line": lines,
        "CustomerRef": {"value": "MOCK-C1", "name": customer},
        "TotalAmt": paisa_to_decimal(refund_paisa),
        "PrivateNote": f"Refund for order {order.order_number}",
    }

    bank = resolver.get_default("bank")
    if bank:
        payload["DepositToAccountRef"] = {"value": bank["_qb_id"], "name": bank["name"]}

    return payload


def build_journal_entry(
    orders: list[MockOrder], resolver: MockMappingResolver, target_date: str,
) -> dict:
    total_revenue = sum(o.subtotal for o in orders)
    total_tax = sum(o.tax_amount for o in orders)
    total_discount = sum(o.discount_amount for o in orders)
    total_collected = sum(o.total for o in orders)
    count = len(orders)

    je_lines: list[dict] = []
    ln = 0

    # DEBIT: Cash / Bank
    bank = resolver.get_default("bank")
    bank_ref = (
        {"value": bank["_qb_id"], "name": bank["name"]}
        if bank else {"value": "1", "name": "Undeposited Funds"}
    )
    ln += 1
    je_lines.append({
        "Id": str(ln), "LineNum": ln,
        "Amount": paisa_to_decimal(total_collected),
        "Description": f"Daily sales ({count} orders) - {target_date}",
        "DetailType": "JournalEntryLineDetail",
        "JournalEntryLineDetail": {
            "PostingType": "Debit",
            "AccountRef": bank_ref,
        },
        "_route": {"side": "DEBIT", "account": bank_ref["name"]},
    })

    # CREDIT: Income (net of discounts)
    income = resolver.get_default("income")
    income_ref = (
        {"value": income["_qb_id"], "name": income["name"]}
        if income else {"value": "2", "name": "Sales Revenue"}
    )
    net_rev = total_revenue - total_discount
    if net_rev > 0:
        ln += 1
        je_lines.append({
            "Id": str(ln), "LineNum": ln,
            "Amount": paisa_to_decimal(net_rev),
            "Description": f"Net sales revenue - {target_date}",
            "DetailType": "JournalEntryLineDetail",
            "JournalEntryLineDetail": {
                "PostingType": "Credit",
                "AccountRef": income_ref,
            },
            "_route": {"side": "CREDIT", "account": income_ref["name"]},
        })

    # CREDIT: Tax payable
    if total_tax > 0:
        tax = resolver.get_default("tax_payable")
        tax_ref = (
            {"value": tax["_qb_id"], "name": tax["name"]}
            if tax else {"value": "3", "name": "Sales Tax Payable"}
        )
        ln += 1
        je_lines.append({
            "Id": str(ln), "LineNum": ln,
            "Amount": paisa_to_decimal(total_tax),
            "Description": f"Tax collected - {target_date}",
            "DetailType": "JournalEntryLineDetail",
            "JournalEntryLineDetail": {
                "PostingType": "Credit",
                "AccountRef": tax_ref,
            },
            "_route": {"side": "CREDIT", "account": tax_ref["name"]},
        })

    return {
        "_qb_endpoint": "POST /v3/company/{realm}/journalentry",
        "DocNumber": f"DAILY-{target_date}",
        "TxnDate": target_date,
        "Line": je_lines,
        "PrivateNote": (
            f"POS daily summary {target_date}: "
            f"{count} orders, "
            f"Subtotal {paisa_to_decimal(total_revenue)} PKR, "
            f"Disc {paisa_to_decimal(total_discount)} PKR, "
            f"Tax {paisa_to_decimal(total_tax)} PKR, "
            f"Collected {paisa_to_decimal(total_collected)} PKR"
        ),
        "Adjustment": False,
        "_totals": {
            "orders": count,
            "subtotal": total_revenue,
            "tax": total_tax,
            "discount": total_discount,
            "collected": total_collected,
        },
    }


def build_deposit(
    orders: list[MockOrder], resolver: MockMappingResolver, target_date: str,
) -> dict:
    # Group payments by method
    by_method: dict[str, int] = {}
    for o in orders:
        pm = o.payment_method or "Cash"
        by_method[pm] = by_method.get(pm, 0) + o.total

    bank = resolver.get_default("bank")
    bank_ref = (
        {"value": bank["_qb_id"], "name": bank["name"]}
        if bank else {"value": "1", "name": "Business Bank Account"}
    )

    dep_lines: list[dict] = []
    total = 0
    for method, amount in by_method.items():
        total += amount
        # Determine source account based on payment method
        if method in ("Cash",):
            from_acct = {"value": "CASH-1", "name": "Cash Drawer"}
        elif method in ("Foodpanda",):
            from_acct = {"value": "FP-1", "name": "Foodpanda Settlement"}
        elif method in ("JazzCash",):
            from_acct = {"value": "JC-1", "name": "JazzCash Settlement"}
        elif method in ("Easypaisa",):
            from_acct = {"value": "EP-1", "name": "Easypaisa Settlement"}
        else:
            from_acct = {"value": "CARD-1", "name": "Undeposited Funds"}

        dep_lines.append({
            "Amount": paisa_to_decimal(amount),
            "DetailType": "DepositLineDetail",
            "DepositLineDetail": {
                "AccountRef": from_acct,
            },
            "Description": f"{method} deposit - {target_date}",
        })

    return {
        "_qb_endpoint": "POST /v3/company/{realm}/deposit",
        "TxnDate": target_date,
        "DepositToAccountRef": bank_ref,
        "Line": dep_lines,
        "TotalAmt": paisa_to_decimal(total),
        "PrivateNote": f"POS daily deposit for {target_date}",
    }


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

REQUIRED_TYPES = [
    "income", "cogs", "tax_payable", "bank",
    "discount", "rounding", "cash_over_short",
]

TYPE_ORDER = [
    "income", "cogs", "tax_payable", "bank", "expense",
    "discount", "rounding", "cash_over_short", "tips",
    "gift_card_liability", "other_current_liability",
    "service_charge", "delivery_fee", "foodpanda_commission",
]

TYPE_LABELS = {
    "income": "INCOME",
    "cogs": "COGS",
    "tax_payable": "TAX",
    "bank": "BANK",
    "expense": "EXPENSE",
    "discount": "DISCOUNT",
    "rounding": "ROUNDING",
    "cash_over_short": "CASH O/S",
    "tips": "TIPS",
    "gift_card_liability": "GIFT CARD",
    "other_current_liability": "LIABILITY",
    "service_charge": "SVC CHARGE",
    "delivery_fee": "DELIVERY",
    "foodpanda_commission": "PLATFORM",
}

W = 105  # output width


def pr(text: str = ""):
    print(text)


def sep(char: str = "="):
    pr(char * W)


def header(text: str, char: str = "="):
    pr()
    sep(char)
    for line in text.strip().split("\n"):
        pr(line.center(W))
    sep(char)


def box_top(title: str, w: int = 100):
    pr(f"  +--- {title} {'-' * max(0, w - len(title) - 7)}+")


def box_line(text: str, w: int = 100):
    pr(f"  | {text:<{w - 4}} |")


def box_empty(w: int = 100):
    box_line("", w)


def box_bottom(w: int = 100):
    pr(f"  +{'-' * (w - 2)}+")


def box_arrow(w: int = 100):
    center = w // 2
    pr(f"  {' ' * center}|")
    pr(f"  {' ' * center}v")


def show_mappings(template: dict):
    mappings = template["mappings"]
    by_type: dict[str, list[dict]] = {}
    for m in mappings:
        mt = m["mapping_type"]
        by_type.setdefault(mt, []).append(m)

    pr(f"\n  ACCOUNT MAPPINGS ({len(mappings)} total):")
    pr(f"  {'Type':<14} {'D':>1} {'Account Name':<42} {'QB Account Type':<32}")
    pr(f"  {'-'*14} {'-':>1} {'-'*42} {'-'*32}")

    for mt in TYPE_ORDER:
        if mt not in by_type:
            continue
        lbl = TYPE_LABELS.get(mt, mt.upper())
        for m in by_type[mt]:
            d = "*" if m.get("is_default") else " "
            at = m["account_type"]
            sub = m.get("account_sub_type", "")
            full_type = f"{at}/{sub}" if sub else at
            pr(f"  {lbl:<14} {d:>1} {m['name']:<42} {full_type:<32}")
            lbl = ""  # blank after first row in group

    # Validation
    pr(f"\n  VALIDATION:")
    ok = True
    for req in REQUIRED_TYPES:
        has_default = any(
            m.get("is_default") and m["mapping_type"] == req for m in mappings
        )
        has_any = any(m["mapping_type"] == req for m in mappings)
        if not has_any:
            pr(f"    FAIL  {req} -- no mapping exists")
            ok = False
        elif not has_default:
            pr(f"    WARN  {req} -- exists but no default set")
    if ok:
        pr(f"    OK    All {len(REQUIRED_TYPES)} required types present with defaults")


# ---------------------------------------------------------------------------
# Journey display (POS -> Backend API -> Database -> QuickBooks)
# ---------------------------------------------------------------------------

BW = 100  # box width


def show_pos_terminal(order: MockOrder):
    """Display what the cashier sees on the POS screen."""
    label = ORDER_TYPE_LABELS.get(order.order_type, order.order_type)
    box_top(f"POS TERMINAL  --  {label}", BW)

    parts = [f"Order #{order.order_number}", label]
    if order.branch_name:
        parts.append(f"Branch: {order.branch_name}")
    if order.table_label:
        parts.append(f"Table: {order.table_label}")
    if order.customer_name:
        parts.append(f"Customer: {order.customer_name}")
    if order.payment_method:
        parts.append(f"Pay: {order.payment_method}")
    box_line(" | ".join(parts), BW)
    box_empty(BW)

    for i, item in enumerate(order.items, 1):
        mod = ""
        if item.modifiers:
            mod = f"  +{', '.join(m.name for m in item.modifiers)}"
        note = f"  [{item.notes}]" if item.notes else ""
        name_col = f"{i}. {item.name}"
        qty_col = f"x{item.quantity}"
        price_col = f"@{format_pkr(item.unit_price)}"
        total_col = f"= {format_pkr(item.total)}"
        box_line(f"  {name_col:<36} {qty_col:>3}  {price_col:>12}  {total_col:>14}{mod}{note}", BW)

    box_empty(BW)
    box_line(f"  {'Subtotal:':<36} {format_pkr(order.subtotal):>34}", BW)
    if order.discount_amount:
        box_line(f"  {'Discount:':<36} {'-' + format_pkr(order.discount_amount):>34}", BW)
    if order.delivery_fee:
        box_line(f"  {'Delivery Fee:':<36} {format_pkr(order.delivery_fee):>34}", BW)
    box_line(f"  {'Tax (16%):':<36} {format_pkr(order.tax_amount):>34}", BW)
    box_line(f"  {'TOTAL:':<36} {format_pkr(order.total):>34}", BW)
    if order.platform_commission:
        box_empty(BW)
        box_line(f"  Platform Commission ({order.platform_name} 30%): -{format_pkr(order.platform_commission)}", BW)
        net = order.total - order.platform_commission
        box_line(f"  Net Settlement:                       {format_pkr(net)}", BW)
    box_bottom(BW)


def show_backend_api(order: MockOrder, scenario: str):
    """Display what the backend API does."""
    box_arrow(BW)
    box_top("BACKEND API", BW)
    label = ORDER_TYPE_LABELS.get(order.order_type, order.order_type)

    if scenario == "sales_receipt":
        box_line("POST /api/v1/orders", BW)
        box_line(f"  -> Creates order record (type: {order.order_type}, status: completed)", BW)
        box_line(f"  -> Server-side tax calc: {format_pkr(order.subtotal)} x 16% = {format_pkr(order.tax_amount)}", BW)
        if order.table_label:
            box_line(f"  -> Updates table {order.table_label} status: occupied -> available", BW)
        box_empty(BW)
        box_line("POST /api/v1/integrations/quickbooks/sync  (auto-triggered)", BW)
        box_line(f"  -> Enqueues job: create_sales_receipt | priority: 0", BW)
        box_line(f"  -> Idempotency key: create_sales_receipt:order:{order.id}", BW)

    elif scenario == "credit_memo":
        box_line(f"POST /api/v1/orders/{order.id}/void", BW)
        box_line(f"  -> Updates order status: completed -> voided", BW)
        box_line(f"  -> Logs status change: voided (reason: {order.notes or 'manager void'})", BW)
        if order.table_label:
            box_line(f"  -> Updates table {order.table_label} status: occupied -> available", BW)
        box_empty(BW)
        box_line("POST /api/v1/integrations/quickbooks/sync  (auto-triggered)", BW)
        box_line(f"  -> Enqueues job: create_credit_memo | priority: 0", BW)

    elif scenario == "refund_receipt":
        box_line(f"POST /api/v1/orders/{order.id}/refund  (body: amount=50000)", BW)
        box_line(f"  -> Validates: refund Rs.500.00 <= order total {format_pkr(order.total)}", BW)
        box_line(f"  -> Creates refund record linked to order", BW)
        box_empty(BW)
        box_line("POST /api/v1/integrations/quickbooks/sync  (auto-triggered)", BW)
        box_line(f"  -> Enqueues job: create_refund_receipt | priority: 0", BW)

    elif scenario == "daily_close":
        box_line("POST /api/v1/integrations/quickbooks/sync  (type: daily_summary)", BW)
        box_line(f"  -> Aggregates all completed orders for 2026-02-13", BW)
        box_line(f"  -> Enqueues job: create_journal_entry | priority: 5", BW)
        box_line(f"  -> Enqueues job: create_deposit | priority: 5", BW)

    box_bottom(BW)


def show_database(order: MockOrder, scenario: str):
    """Display what database records are created/modified."""
    box_arrow(BW)
    box_top("DATABASE RECORDS", BW)

    if scenario in ("sales_receipt", "credit_memo"):
        status = "completed" if scenario == "sales_receipt" else "voided"
        box_line("TABLE: orders", BW)
        box_line(f"  id: {str(order.id)[:8]}... | order_number: {order.order_number} | type: {order.order_type}", BW)
        box_line(f"  status: {status} | subtotal: {order.subtotal} | tax: {order.tax_amount} | total: {order.total}", BW)
        box_empty(BW)
        box_line(f"TABLE: order_items ({len(order.items)} rows)", BW)
        for i, item in enumerate(order.items, 1):
            box_line(f"  {i}: {item.name:<30} | qty: {item.quantity} | price: {item.unit_price:>6} | total: {item.total:>7}", BW)
        if order.items and order.items[0].modifiers:
            box_empty(BW)
            box_line("TABLE: order_item_modifiers", BW)
            for mod in order.items[0].modifiers if order.items else []:
                pass
            for item in order.items:
                for mod in item.modifiers:
                    box_line(f"  item: {item.name} -> modifier: {mod.name} ({mod.price} paisa)", BW)
        box_empty(BW)
        box_line("TABLE: order_status_log", BW)
        box_line(f"  status: {status} | changed_by: cashier | timestamp: {order.created_at.isoformat()}", BW)
        box_empty(BW)

        sync_type = "create_sales_receipt" if scenario == "sales_receipt" else "create_credit_memo"
        box_line("TABLE: qb_sync_queue", BW)
        box_line(f"  job_type: {sync_type} | status: pending -> processing -> completed", BW)
        box_line(f"  entity_type: order | entity_id: {str(order.id)[:8]}... | priority: 0", BW)
        box_line(f"  idempotency_key: {sync_type}:order:{str(order.id)[:8]}...", BW)
        box_empty(BW)
        box_line("TABLE: qb_sync_log", BW)
        qb_type = "SalesReceipt" if scenario == "sales_receipt" else "CreditMemo"
        doc_num = order.order_number if scenario == "sales_receipt" else f"VOID-{order.order_number}"
        box_line(f"  sync_type: {qb_type.lower()} | action: create | status: success", BW)
        box_line(f"  qb_entity_type: {qb_type} | qb_doc_number: {doc_num}", BW)
        box_line(f"  amount_paisa: {order.total} | http_status: 200 | duration_ms: ~450", BW)

    elif scenario == "refund_receipt":
        box_line("TABLE: orders (no change - original order stays completed)", BW)
        box_line(f"  id: {str(order.id)[:8]}... | order_number: {order.order_number} | status: {order.status}", BW)
        box_empty(BW)
        box_line("TABLE: qb_sync_queue", BW)
        box_line(f"  job_type: create_refund_receipt | status: pending -> completed", BW)
        box_line(f"  entity_type: order | entity_id: {str(order.id)[:8]}... | priority: 0", BW)
        box_empty(BW)
        box_line("TABLE: qb_sync_log", BW)
        box_line(f"  sync_type: refund_receipt | action: create | status: success", BW)
        box_line(f"  qb_entity_type: RefundReceipt | qb_doc_number: REF-{order.order_number}", BW)
        box_line(f"  amount_paisa: 50000 | http_status: 200", BW)

    elif scenario == "daily_close":
        box_line("TABLE: qb_sync_queue (2 jobs)", BW)
        box_line(f"  [1] job_type: create_journal_entry | status: completed | priority: 5", BW)
        box_line(f"  [2] job_type: create_deposit | status: completed | priority: 5", BW)
        box_empty(BW)
        box_line("TABLE: qb_sync_log (2 entries)", BW)
        box_line(f"  [1] sync_type: journal_entry | qb_doc_number: DAILY-2026-02-13 | status: success", BW)
        box_line(f"  [2] sync_type: deposit | status: success", BW)

    box_bottom(BW)


def show_quickbooks(payload: dict, entity_type: str, resolver: MockMappingResolver | None = None):
    """Display the resulting QuickBooks entry."""
    box_arrow(BW)
    endpoint = payload.get("_qb_endpoint", "")
    box_top(f"QUICKBOOKS ONLINE  --  {entity_type}  [{endpoint}]", BW)

    for key in ["DocNumber", "TxnDate"]:
        if key in payload:
            box_line(f"  {key}: {payload[key]}", BW)

    if "CustomerRef" in payload:
        box_line(f"  Customer: {payload['CustomerRef'].get('name', 'N/A')}", BW)

    if "TotalAmt" in payload:
        box_line(f"  TotalAmt: {payload['TotalAmt']} PKR", BW)

    if "TxnTaxDetail" in payload:
        box_line(f"  Tax: {payload['TxnTaxDetail'].get('TotalTax', '0.00')} PKR", BW)

    if "DepositToAccountRef" in payload:
        ref = payload["DepositToAccountRef"]
        box_line(f"  DepositTo: {ref.get('name', 'N/A')}", BW)

    if "PaymentMethodRef" in payload:
        ref = payload["PaymentMethodRef"]
        box_line(f"  PaymentMethod: {ref.get('name', 'N/A')}", BW)

    if "PrivateNote" in payload:
        box_line(f"  Note: {payload['PrivateNote']}", BW)

    lines = payload.get("Line", [])
    if lines:
        box_empty(BW)
        box_line(f"  Line Items ({len(lines)}):", BW)

        for line in lines:
            route = line.get("_route", {})
            dt = line.get("DetailType", "")

            if dt == "SalesItemLineDetail":
                d = line.get("SalesItemLineDetail", {})
                acct = d.get("ItemAccountRef", {}).get("name", route.get("account", "UNMAPPED"))
                match_type = route.get("match", "")
                match_tag = f" (default)" if match_type == "default" else f" (category match)" if match_type == "category" else ""
                box_line(f"    [{line['LineNum']}] {line.get('Description', '')}", BW)
                box_line(f"        Qty {d.get('Qty',1)} x {d.get('UnitPrice','0')} = {line['Amount']} PKR", BW)
                box_line(f"        -> Income: \"{acct}\"{match_tag}", BW)

            elif dt == "DiscountLineDetail":
                box_line(f"    [{line['LineNum']}] DISCOUNT: -{line['Amount']} PKR", BW)
                box_line(f"        -> Contra: \"{route.get('account', 'UNMAPPED')}\"", BW)

            elif dt == "JournalEntryLineDetail":
                d = line.get("JournalEntryLineDetail", {})
                side = d.get("PostingType", "")
                acct = d.get("AccountRef", {}).get("name", "N/A")
                box_line(f"    [{line['LineNum']}] {side:>6}: {line['Amount']} PKR", BW)
                box_line(f"        Account: \"{acct}\"", BW)
                box_line(f"        Memo: {line.get('Description', '')}", BW)

            elif dt == "DepositLineDetail":
                d = line.get("DepositLineDetail", {})
                acct = d.get("AccountRef", {}).get("name", "N/A")
                box_line(f"    {line.get('Description', '')}: {line['Amount']} PKR", BW)
                box_line(f"        From: \"{acct}\"", BW)

    # Double-entry effect for SalesReceipt / CreditMemo
    if entity_type in ("SalesReceipt", "CreditMemo") and resolver:
        box_empty(BW)
        total_amt = payload.get("TotalAmt", "0.00")
        tax_amt = payload.get("TxnTaxDetail", {}).get("TotalTax", "0.00")
        deposit_acct = payload.get("DepositToAccountRef", {}).get("name", "Cash Register")

        # Calculate item totals by account
        acct_totals: dict[str, Decimal] = {}
        for line in lines:
            if line.get("DetailType") == "SalesItemLineDetail":
                acct_name = line.get("SalesItemLineDetail", {}).get("ItemAccountRef", {}).get("name", "Food Sales")
                amount = Decimal(line["Amount"])
                acct_totals[acct_name] = acct_totals.get(acct_name, Decimal(0)) + amount

        if entity_type == "SalesReceipt":
            box_line("  Double-Entry Effect:", BW)
            box_line(f"    DR  {deposit_acct:<50} {total_amt:>10}", BW)
            for acct, amt in acct_totals.items():
                box_line(f"    CR  {acct:<50} {str(amt):>10}", BW)
            if Decimal(tax_amt) > 0:
                tax_acct = resolver.get_default("tax_payable")
                tax_name = tax_acct["name"] if tax_acct else "Tax Payable"
                box_line(f"    CR  {tax_name:<50} {tax_amt:>10}", BW)
        elif entity_type == "CreditMemo":
            box_line("  Double-Entry Effect (reversal):", BW)
            for acct, amt in acct_totals.items():
                box_line(f"    DR  {acct:<50} {str(amt):>10}", BW)
            if Decimal(tax_amt) > 0:
                tax_acct = resolver.get_default("tax_payable")
                tax_name = tax_acct["name"] if tax_acct else "Tax Payable"
                box_line(f"    DR  {tax_name:<50} {tax_amt:>10}", BW)
            box_line(f"    CR  Accounts Receivable / Refund Due{' ' * 11} {total_amt:>10}", BW)

    box_bottom(BW)


def show_payload_json(payload: dict):
    """Print clean JSON payload (for --json mode)."""
    clean = {k: v for k, v in payload.items() if not k.startswith("_")}
    for line in clean.get("Line", []):
        line.pop("_route", None)
    pr(json.dumps(clean, indent=2, default=str))


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

def run_template_tests(
    template_key: str,
    template: dict,
    orders: dict[str, MockOrder],
    *,
    json_mode: bool = False,
):
    resolver = MockMappingResolver(template["mappings"])

    header(f"TEMPLATE: {template_key}\n{template['name']}")
    pr(f"\n  {template['description']}")

    show_mappings(template)

    # ==== SCENARIO 1: Completed dine-in -> Sales Receipt ====
    o1 = orders["dine_in_completed"]
    pr(f"\n{'=' * W}")
    pr(f"  SCENARIO 1: Completed Dine-In Order  ->  QB SalesReceipt".center(W))
    pr(f"{'=' * W}")

    if json_mode:
        p1 = build_sales_receipt(o1, resolver)
        show_payload_json(p1)
    else:
        show_pos_terminal(o1)
        show_backend_api(o1, "sales_receipt")
        show_database(o1, "sales_receipt")
        p1 = build_sales_receipt(o1, resolver)
        show_quickbooks(p1, "SalesReceipt", resolver)

    # ==== SCENARIO 2: Completed takeaway (with discount) -> Sales Receipt ====
    o2 = orders["takeaway_completed"]
    pr(f"\n{'=' * W}")
    pr(f"  SCENARIO 2: Completed Takeaway Order (with discount)  ->  QB SalesReceipt".center(W))
    pr(f"{'=' * W}")

    if json_mode:
        p2 = build_sales_receipt(o2, resolver)
        show_payload_json(p2)
    else:
        show_pos_terminal(o2)
        show_backend_api(o2, "sales_receipt")
        show_database(o2, "sales_receipt")
        p2 = build_sales_receipt(o2, resolver)
        show_quickbooks(p2, "SalesReceipt", resolver)

    # ==== SCENARIO 3: Voided order -> Credit Memo ====
    o3 = orders["dine_in_voided"]
    pr(f"\n{'=' * W}")
    pr(f"  SCENARIO 3: Voided Order  ->  QB CreditMemo".center(W))
    pr(f"{'=' * W}")

    if json_mode:
        p3 = build_credit_memo(o3, resolver)
        show_payload_json(p3)
    else:
        show_pos_terminal(o3)
        show_backend_api(o3, "credit_memo")
        show_database(o3, "credit_memo")
        p3 = build_credit_memo(o3, resolver)
        show_quickbooks(p3, "CreditMemo", resolver)

    # ==== SCENARIO 4: Partial refund -> Refund Receipt ====
    pr(f"\n{'=' * W}")
    pr(f"  SCENARIO 4: Partial Refund (Rs.500.00)  ->  QB RefundReceipt".center(W))
    pr(f"{'=' * W}")

    # Use the takeaway order (completed) as the order being partially refunded
    o_ref = orders["takeaway_completed"]

    if json_mode:
        p4 = build_refund_receipt(o_ref, 50000, resolver)
        show_payload_json(p4)
    else:
        pr()
        box_top(f"POS TERMINAL  --  Refund", BW)
        box_line(f"Refunding Rs.500.00 against order #{o_ref.order_number} (total: {format_pkr(o_ref.total)})", BW)
        box_line(f"Customer: {o_ref.customer_name or 'Walk-In'} | Reason: Customer complaint", BW)
        box_line(f"Refund Method: Cash | Approved by: Manager", BW)
        box_bottom(BW)
        show_backend_api(o_ref, "refund_receipt")
        show_database(o_ref, "refund_receipt")
        p4 = build_refund_receipt(o_ref, 50000, resolver)
        show_quickbooks(p4, "RefundReceipt", resolver)

    # ==== SCENARIO 5: Daily Close -> Journal Entry + Deposit ====
    completed_orders = [
        orders["dine_in_completed"],
        orders["takeaway_completed"],
        orders["call_center_completed"],
        orders["foodpanda_completed"],
    ]
    target_date = "2026-02-13"
    total_collected = sum(o.total for o in completed_orders)

    pr(f"\n{'=' * W}")
    pr(f"  SCENARIO 5: Daily Close  ->  QB JournalEntry + Deposit".center(W))
    pr(f"{'=' * W}")

    if json_mode:
        je = build_journal_entry(completed_orders, resolver, target_date)
        show_payload_json(je)
        dep = build_deposit(completed_orders, resolver, target_date)
        show_payload_json(dep)
    else:
        pr()
        box_top(f"POS TERMINAL  --  End of Day Close", BW)
        box_line(f"Date: {target_date} | Closed by: Admin", BW)
        box_empty(BW)
        box_line(f"{'Channel':<20} {'Orders':>7} {'Revenue':>14} {'Tax':>12} {'Total':>14}", BW)
        box_line(f"{'-'*20} {'-'*7} {'-'*14} {'-'*12} {'-'*14}", BW)
        channel_summary: dict[str, dict] = {}
        for o in completed_orders:
            ch = ORDER_TYPE_LABELS.get(o.order_type, o.order_type)
            if ch not in channel_summary:
                channel_summary[ch] = {"count": 0, "revenue": 0, "tax": 0, "total": 0}
            channel_summary[ch]["count"] += 1
            channel_summary[ch]["revenue"] += o.subtotal
            channel_summary[ch]["tax"] += o.tax_amount
            channel_summary[ch]["total"] += o.total
        for ch, s in channel_summary.items():
            box_line(f"{ch:<20} {s['count']:>7} {format_pkr(s['revenue']):>14} {format_pkr(s['tax']):>12} {format_pkr(s['total']):>14}", BW)
        box_empty(BW)
        total_rev = sum(o.subtotal for o in completed_orders)
        total_tax = sum(o.tax_amount for o in completed_orders)
        total_disc = sum(o.discount_amount for o in completed_orders)
        box_line(f"{'TOTALS':<20} {len(completed_orders):>7} {format_pkr(total_rev):>14} {format_pkr(total_tax):>12} {format_pkr(total_collected):>14}", BW)
        if total_disc:
            box_line(f"  Discounts: -{format_pkr(total_disc)}", BW)
        box_empty(BW)
        box_line("Payment Method Breakdown:", BW)
        by_pm: dict[str, int] = {}
        for o in completed_orders:
            pm = o.payment_method or "Cash"
            by_pm[pm] = by_pm.get(pm, 0) + o.total
        for pm, amt in by_pm.items():
            box_line(f"  {pm:<30} {format_pkr(amt):>14}", BW)
        box_bottom(BW)

        # Show backend + DB for daily close
        show_backend_api(completed_orders[0], "daily_close")
        show_database(completed_orders[0], "daily_close")

        je = build_journal_entry(completed_orders, resolver, target_date)
        show_quickbooks(je, "JournalEntry")

        dep = build_deposit(completed_orders, resolver, target_date)
        show_quickbooks(dep, "Deposit")

    # Balance check
    if not json_mode:
        je = build_journal_entry(completed_orders, resolver, target_date)
        totals = je.get("_totals", {})
        debit = totals.get("collected", 0)
        credit = (totals.get("subtotal", 0) - totals.get("discount", 0)) + totals.get("tax", 0)
        balanced = debit == credit
        pr(f"\n  JOURNAL BALANCE CHECK:")
        pr(f"    Debit  (cash in):    {format_pkr(debit)}")
        pr(f"    Credit (rev + tax):  {format_pkr(credit)}")
        pr(f"    Status: {'BALANCED' if balanced else 'IMBALANCED !!!'}")
        pr()


# ---------------------------------------------------------------------------
# Multi-Franchise Scenarios (7 specialized scenarios)
# ---------------------------------------------------------------------------

_BRANCHES = [
    {"name": "Gulberg", "city": "Lahore", "class": "Branch-Gulberg"},
    {"name": "DHA", "city": "Lahore", "class": "Branch-DHA"},
    {"name": "Johar Town", "city": "Lahore", "class": "Branch-JoharTown"},
    {"name": "Model Town", "city": "Lahore", "class": "Branch-ModelTown"},
    {"name": "Airport", "city": "Lahore", "class": "Branch-Airport"},
]


def _make_franchise_orders() -> dict[str, MockOrder]:
    """Create franchise-specific mock orders with branch assignments."""
    cat_bbq = uuid.uuid4()
    cat_rice = uuid.uuid4()
    cat_drinks = uuid.uuid4()
    cat_dessert = uuid.uuid4()
    cat_bread = uuid.uuid4()
    cat_curry = uuid.uuid4()

    # Branch 1: Gulberg dine-in
    b1_items = [
        MockOrderItem(uuid.uuid4(), "Chicken Biryani", "Rice & Biryani",
                       cat_rice, 3, 45000, 135000),
        MockOrderItem(uuid.uuid4(), "Seekh Kabab (6 pcs)", "BBQ & Grill",
                       cat_bbq, 2, 18000, 36000,
                       modifiers=[MockModifier("Extra Spicy", 0)]),
        MockOrderItem(uuid.uuid4(), "Raita", "Sides",
                       cat_rice, 2, 8000, 16000),
    ]
    sub1 = sum(i.total for i in b1_items)
    tax1 = int(sub1 * 16 / 100)
    gulberg_order = MockOrder(
        id=uuid.uuid4(), order_number="260213-G01",
        order_type="dine_in", status="completed",
        items=b1_items, subtotal=sub1, tax_amount=tax1,
        discount_amount=0, total=sub1 + tax1,
        table_label="G-T03", payment_method="Cash",
        branch_name="Gulberg",
        created_at=datetime(2026, 2, 13, 13, 0, 0, tzinfo=timezone.utc),
    )

    # Branch 2: DHA takeaway
    b2_items = [
        MockOrderItem(uuid.uuid4(), "Mutton Karahi (Full)", "Karahi & Curry",
                       cat_curry, 1, 280000, 280000,
                       notes="Medium spice"),
        MockOrderItem(uuid.uuid4(), "Tandoori Naan", "Bread",
                       cat_bread, 6, 4000, 24000),
        MockOrderItem(uuid.uuid4(), "Pepsi 1.5L", "Drinks",
                       cat_drinks, 2, 12000, 24000),
    ]
    sub2 = sum(i.total for i in b2_items)
    tax2 = int(sub2 * 16 / 100)
    disc2 = 20000  # Rs.200 loyalty discount
    dha_order = MockOrder(
        id=uuid.uuid4(), order_number="260213-D01",
        order_type="takeaway", status="completed",
        items=b2_items, subtotal=sub2, tax_amount=tax2,
        discount_amount=disc2, total=sub2 + tax2 - disc2,
        customer_name="Hassan Malik", customer_phone="03011234567",
        payment_method="Credit Card", branch_name="DHA",
        created_at=datetime(2026, 2, 13, 14, 30, 0, tzinfo=timezone.utc),
    )

    # Branch 3: Johar Town Foodpanda
    b3_items = [
        MockOrderItem(uuid.uuid4(), "Chicken Biryani", "Rice & Biryani",
                       cat_rice, 2, 45000, 90000),
        MockOrderItem(uuid.uuid4(), "Chicken Tikka (8 pcs)", "BBQ & Grill",
                       cat_bbq, 1, 48000, 48000),
        MockOrderItem(uuid.uuid4(), "Gulab Jamun (6 pcs)", "Desserts",
                       cat_dessert, 1, 15000, 15000),
    ]
    sub3 = sum(i.total for i in b3_items)
    tax3 = int(sub3 * 16 / 100)
    fp_comm = int(sub3 * 30 / 100)
    johar_order = MockOrder(
        id=uuid.uuid4(), order_number="260213-J01",
        order_type="foodpanda", status="completed",
        items=b3_items, subtotal=sub3, tax_amount=tax3,
        discount_amount=0, total=sub3 + tax3,
        customer_name="Foodpanda Customer",
        payment_method="Foodpanda", platform_name="Foodpanda",
        platform_commission=fp_comm, branch_name="Johar Town",
        created_at=datetime(2026, 2, 13, 19, 0, 0, tzinfo=timezone.utc),
    )

    # Branch 4: Model Town call center delivery
    b4_items = [
        MockOrderItem(uuid.uuid4(), "Mutton Biryani", "Rice & Biryani",
                       cat_rice, 2, 55000, 110000),
        MockOrderItem(uuid.uuid4(), "Chicken Karahi (Half)", "Karahi & Curry",
                       cat_curry, 1, 120000, 120000),
        MockOrderItem(uuid.uuid4(), "Naan", "Bread",
                       cat_bread, 8, 4000, 32000),
        MockOrderItem(uuid.uuid4(), "Kheer", "Desserts",
                       cat_dessert, 2, 12000, 24000),
    ]
    sub4 = sum(i.total for i in b4_items)
    tax4 = int(sub4 * 16 / 100)
    model_order = MockOrder(
        id=uuid.uuid4(), order_number="260213-M01",
        order_type="call_center", status="completed",
        items=b4_items, subtotal=sub4, tax_amount=tax4,
        discount_amount=0, total=sub4 + tax4,
        customer_name="Ayesha Siddiqui", customer_phone="03219876543",
        payment_method="JazzCash", delivery_fee=20000,
        branch_name="Model Town",
        created_at=datetime(2026, 2, 13, 20, 0, 0, tzinfo=timezone.utc),
    )

    # Branch 5: Airport dine-in (premium pricing)
    b5_items = [
        MockOrderItem(uuid.uuid4(), "Chicken Biryani (Premium)", "Rice & Biryani",
                       cat_rice, 1, 65000, 65000),
        MockOrderItem(uuid.uuid4(), "Seekh Kabab (6 pcs)", "BBQ & Grill",
                       cat_bbq, 1, 25000, 25000),
        MockOrderItem(uuid.uuid4(), "Fresh Juice", "Drinks",
                       cat_drinks, 2, 20000, 40000),
    ]
    sub5 = sum(i.total for i in b5_items)
    tax5 = int(sub5 * 16 / 100)
    airport_order = MockOrder(
        id=uuid.uuid4(), order_number="260213-A01",
        order_type="dine_in", status="completed",
        items=b5_items, subtotal=sub5, tax_amount=tax5,
        discount_amount=0, total=sub5 + tax5,
        table_label="A-T01", payment_method="Credit Card",
        branch_name="Airport",
        created_at=datetime(2026, 2, 13, 21, 0, 0, tzinfo=timezone.utc),
    )

    return {
        "gulberg_dinein": gulberg_order,
        "dha_takeaway": dha_order,
        "johar_foodpanda": johar_order,
        "model_delivery": model_order,
        "airport_dinein": airport_order,
    }


def _build_franchise_sales_receipt(
    order: MockOrder, resolver: MockMappingResolver, branch: dict,
) -> dict:
    """Build a SalesReceipt with QB Class for branch tracking."""
    payload = build_sales_receipt(order, resolver)
    # Add QB Class for branch P&L tracking
    payload["ClassRef"] = {"value": f"CLASS-{branch['name'].upper()}", "name": branch["class"]}
    # Add branch to private note
    payload["PrivateNote"] += f" | Branch: {branch['name']} ({branch['city']})"
    return payload


def _build_inter_branch_transfer(
    from_branch: dict, to_branch: dict, resolver: MockMappingResolver,
    items_desc: str, amount_paisa: int, target_date: str,
) -> dict:
    """Build a JournalEntry for inter-branch stock transfer."""
    amount = paisa_to_decimal(amount_paisa)

    # Central Kitchen sends to branch:
    # DR Inter-Branch Transfer Cost (receiving branch)
    # CR Central Kitchen Revenue (sending kitchen)
    je_lines = [
        {
            "Id": "1", "LineNum": 1,
            "Amount": amount,
            "Description": f"Stock transfer: {items_desc} ({from_branch['name']} -> {to_branch['name']})",
            "DetailType": "JournalEntryLineDetail",
            "JournalEntryLineDetail": {
                "PostingType": "Debit",
                "AccountRef": {"value": "IB-COST-1", "name": "Inter-Branch Transfer Cost"},
                "ClassRef": {"value": f"CLASS-{to_branch['name'].upper()}", "name": to_branch["class"]},
            },
            "_route": {"side": "DEBIT", "account": "Inter-Branch Transfer Cost",
                       "class": to_branch["class"]},
        },
        {
            "Id": "2", "LineNum": 2,
            "Amount": amount,
            "Description": f"Central Kitchen supply to {to_branch['name']}",
            "DetailType": "JournalEntryLineDetail",
            "JournalEntryLineDetail": {
                "PostingType": "Credit",
                "AccountRef": {"value": "CK-REV-1", "name": "Central Kitchen Revenue"},
                "ClassRef": {"value": "CLASS-CK", "name": "Central-Kitchen"},
            },
            "_route": {"side": "CREDIT", "account": "Central Kitchen Revenue",
                       "class": "Central-Kitchen"},
        },
    ]
    return {
        "_qb_endpoint": "POST /v3/company/{realm}/journalentry",
        "DocNumber": f"XFER-{target_date}-{to_branch['name'][:3].upper()}",
        "TxnDate": target_date,
        "Line": je_lines,
        "PrivateNote": (
            f"Inter-branch transfer: {from_branch['name']} -> {to_branch['name']} | "
            f"{items_desc} | Amount: {amount} PKR"
        ),
        "Adjustment": False,
    }


def _build_royalty_entry(
    branch_revenues: dict[str, int], royalty_pct: float, marketing_pct: float,
    resolver: MockMappingResolver, target_date: str,
) -> dict:
    """Build JournalEntry for franchise royalty and marketing fund."""
    total_revenue = sum(branch_revenues.values())
    royalty_amount = int(total_revenue * royalty_pct / 100)
    marketing_amount = int(total_revenue * marketing_pct / 100)
    total_owed = royalty_amount + marketing_amount

    je_lines: list[dict] = []
    ln = 0

    # DR Royalty Fee Expense
    ln += 1
    je_lines.append({
        "Id": str(ln), "LineNum": ln,
        "Amount": paisa_to_decimal(royalty_amount),
        "Description": f"Franchise royalty {royalty_pct}% of {paisa_to_decimal(total_revenue)} PKR",
        "DetailType": "JournalEntryLineDetail",
        "JournalEntryLineDetail": {
            "PostingType": "Debit",
            "AccountRef": {"value": "ROY-EXP-1", "name": "Royalty Fee Expense (6%)"},
        },
        "_route": {"side": "DEBIT", "account": "Royalty Fee Expense (6%)"},
    })

    # DR Marketing Fund Expense
    ln += 1
    je_lines.append({
        "Id": str(ln), "LineNum": ln,
        "Amount": paisa_to_decimal(marketing_amount),
        "Description": f"Marketing fund {marketing_pct}% of {paisa_to_decimal(total_revenue)} PKR",
        "DetailType": "JournalEntryLineDetail",
        "JournalEntryLineDetail": {
            "PostingType": "Debit",
            "AccountRef": {"value": "MKT-EXP-1", "name": "Marketing Fund (3%)"},
        },
        "_route": {"side": "DEBIT", "account": "Marketing Fund (3%)"},
    })

    # CR Royalty Payable
    ln += 1
    je_lines.append({
        "Id": str(ln), "LineNum": ln,
        "Amount": paisa_to_decimal(royalty_amount),
        "Description": "Royalty payable to franchisor",
        "DetailType": "JournalEntryLineDetail",
        "JournalEntryLineDetail": {
            "PostingType": "Credit",
            "AccountRef": {"value": "ROY-PAY-1", "name": "Royalty Payable"},
        },
        "_route": {"side": "CREDIT", "account": "Royalty Payable"},
    })

    # CR Marketing Fund Payable
    ln += 1
    je_lines.append({
        "Id": str(ln), "LineNum": ln,
        "Amount": paisa_to_decimal(marketing_amount),
        "Description": "Marketing fund payable to brand HQ",
        "DetailType": "JournalEntryLineDetail",
        "JournalEntryLineDetail": {
            "PostingType": "Credit",
            "AccountRef": {"value": "MKT-PAY-1", "name": "Marketing Fund Payable"},
        },
        "_route": {"side": "CREDIT", "account": "Marketing Fund Payable"},
    })

    return {
        "_qb_endpoint": "POST /v3/company/{realm}/journalentry",
        "DocNumber": f"ROYAL-{target_date}",
        "TxnDate": target_date,
        "Line": je_lines,
        "PrivateNote": (
            f"Franchise royalty & marketing fund for {target_date}: "
            f"Royalty {royalty_pct}% = {paisa_to_decimal(royalty_amount)} PKR, "
            f"Marketing {marketing_pct}% = {paisa_to_decimal(marketing_amount)} PKR, "
            f"Total owed: {paisa_to_decimal(total_owed)} PKR"
        ),
        "Adjustment": False,
        "_totals": {
            "total_revenue": total_revenue,
            "royalty_amount": royalty_amount,
            "marketing_amount": marketing_amount,
            "total_owed": total_owed,
        },
    }


def _build_consolidated_journal(
    branch_orders: dict[str, list[MockOrder]], resolver: MockMappingResolver,
    target_date: str,
) -> dict:
    """Build consolidated JournalEntry across all branches with per-branch Classes."""
    je_lines: list[dict] = []
    ln = 0
    grand_total = 0

    for branch_name, orders in branch_orders.items():
        branch_total = sum(o.total for o in orders)
        branch_revenue = sum(o.subtotal for o in orders)
        branch_tax = sum(o.tax_amount for o in orders)
        branch_discount = sum(o.discount_amount for o in orders)
        grand_total += branch_total
        class_ref = {"value": f"CLASS-{branch_name.upper().replace(' ', '')}",
                     "name": f"Branch-{branch_name.replace(' ', '')}"}

        # DEBIT: Branch Cash/Bank
        ln += 1
        je_lines.append({
            "Id": str(ln), "LineNum": ln,
            "Amount": paisa_to_decimal(branch_total),
            "Description": f"{branch_name} daily sales ({len(orders)} orders)",
            "DetailType": "JournalEntryLineDetail",
            "JournalEntryLineDetail": {
                "PostingType": "Debit",
                "AccountRef": {"value": f"BR-CASH-{branch_name[:3].upper()}",
                               "name": f"{branch_name} Cash Register"},
                "ClassRef": class_ref,
            },
            "_route": {"side": "DEBIT", "account": f"{branch_name} Cash Register",
                       "class": class_ref["name"]},
        })

        # CREDIT: Branch Revenue (net of discounts)
        net_rev = branch_revenue - branch_discount
        if net_rev > 0:
            ln += 1
            je_lines.append({
                "Id": str(ln), "LineNum": ln,
                "Amount": paisa_to_decimal(net_rev),
                "Description": f"{branch_name} net revenue",
                "DetailType": "JournalEntryLineDetail",
                "JournalEntryLineDetail": {
                    "PostingType": "Credit",
                    "AccountRef": {"value": f"BR-REV-{branch_name[:3].upper()}",
                                   "name": f"{branch_name} Branch Revenue"},
                    "ClassRef": class_ref,
                },
                "_route": {"side": "CREDIT", "account": f"{branch_name} Branch Revenue",
                           "class": class_ref["name"]},
            })

        # CREDIT: Tax
        if branch_tax > 0:
            ln += 1
            tax_m = resolver.get_default("tax_payable")
            tax_name = tax_m["name"] if tax_m else "FBR GST Payable (17%)"
            je_lines.append({
                "Id": str(ln), "LineNum": ln,
                "Amount": paisa_to_decimal(branch_tax),
                "Description": f"{branch_name} tax collected",
                "DetailType": "JournalEntryLineDetail",
                "JournalEntryLineDetail": {
                    "PostingType": "Credit",
                    "AccountRef": {"value": "TAX-1", "name": tax_name},
                    "ClassRef": class_ref,
                },
                "_route": {"side": "CREDIT", "account": tax_name,
                           "class": class_ref["name"]},
            })

    return {
        "_qb_endpoint": "POST /v3/company/{realm}/journalentry",
        "DocNumber": f"CONSOL-{target_date}",
        "TxnDate": target_date,
        "Line": je_lines,
        "PrivateNote": (
            f"Consolidated daily summary {target_date}: "
            f"{sum(len(v) for v in branch_orders.values())} orders across "
            f"{len(branch_orders)} branches, total {paisa_to_decimal(grand_total)} PKR"
        ),
        "Adjustment": False,
        "_totals": {"grand_total": grand_total},
    }


def _build_multi_branch_deposit(
    branch_orders: dict[str, list[MockOrder]], resolver: MockMappingResolver,
    target_date: str,
) -> dict:
    """Build multi-branch deposit grouping by branch + payment method."""
    bank = resolver.get_default("bank")
    bank_ref = (
        {"value": bank["_qb_id"], "name": bank["name"]}
        if bank else {"value": "CORP-1", "name": "Corporate Bank Account"}
    )

    dep_lines: list[dict] = []
    total = 0

    for branch_name, orders in branch_orders.items():
        by_method: dict[str, int] = {}
        for o in orders:
            pm = o.payment_method or "Cash"
            by_method[pm] = by_method.get(pm, 0) + o.total
        for method, amount in by_method.items():
            total += amount
            if method in ("Cash",):
                from_acct = {"value": f"CASH-{branch_name[:3].upper()}",
                             "name": f"{branch_name} Cash Register"}
            elif method in ("Foodpanda",):
                from_acct = {"value": "FP-1", "name": "Foodpanda Settlement"}
            elif method in ("JazzCash",):
                from_acct = {"value": "JC-1", "name": "JazzCash Settlement"}
            else:
                from_acct = {"value": "CARD-1", "name": "Undeposited Funds"}
            dep_lines.append({
                "Amount": paisa_to_decimal(amount),
                "DetailType": "DepositLineDetail",
                "DepositLineDetail": {"AccountRef": from_acct},
                "Description": f"{branch_name} {method} deposit - {target_date}",
            })

    return {
        "_qb_endpoint": "POST /v3/company/{realm}/deposit",
        "TxnDate": target_date,
        "DepositToAccountRef": bank_ref,
        "Line": dep_lines,
        "TotalAmt": paisa_to_decimal(total),
        "PrivateNote": f"Consolidated multi-branch deposit for {target_date}",
    }


def run_franchise_tests(
    template_key: str, template: dict, *, json_mode: bool = False,
):
    """Run 7 franchise-specific scenarios for multi_franchise_pakistani."""
    resolver = MockMappingResolver(template["mappings"])
    f_orders = _make_franchise_orders()
    target_date = "2026-02-13"

    header(f"TEMPLATE: {template_key}\n{template['name']}")
    pr(f"\n  {template['description']}")
    show_mappings(template)

    # === SCENARIO 1: Gulberg dine-in with QB Class ===
    o_gulberg = f_orders["gulberg_dinein"]
    branch_gulberg = _BRANCHES[0]
    pr(f"\n{'=' * W}")
    pr("  SCENARIO 1: Gulberg Branch Dine-In -> SalesReceipt + QB Class".center(W))
    pr(f"{'=' * W}")

    if json_mode:
        p1 = _build_franchise_sales_receipt(o_gulberg, resolver, branch_gulberg)
        show_payload_json(p1)
    else:
        show_pos_terminal(o_gulberg)
        show_backend_api(o_gulberg, "sales_receipt")
        show_database(o_gulberg, "sales_receipt")
        p1 = _build_franchise_sales_receipt(o_gulberg, resolver, branch_gulberg)
        show_quickbooks(p1, "SalesReceipt", resolver)
        pr(f"\n  QB Class: \"{branch_gulberg['class']}\" — enables per-branch P&L filtering")

    # === SCENARIO 2: DHA takeaway with QB Class ===
    o_dha = f_orders["dha_takeaway"]
    branch_dha = _BRANCHES[1]
    pr(f"\n{'=' * W}")
    pr("  SCENARIO 2: DHA Branch Takeaway (with discount) -> SalesReceipt + QB Class".center(W))
    pr(f"{'=' * W}")

    if json_mode:
        p2 = _build_franchise_sales_receipt(o_dha, resolver, branch_dha)
        show_payload_json(p2)
    else:
        show_pos_terminal(o_dha)
        show_backend_api(o_dha, "sales_receipt")
        show_database(o_dha, "sales_receipt")
        p2 = _build_franchise_sales_receipt(o_dha, resolver, branch_dha)
        show_quickbooks(p2, "SalesReceipt", resolver)
        pr(f"\n  QB Class: \"{branch_dha['class']}\" — DHA branch revenue tracked separately")

    # === SCENARIO 3: Johar Town Foodpanda with QB Class + commission ===
    o_johar = f_orders["johar_foodpanda"]
    branch_johar = _BRANCHES[2]
    pr(f"\n{'=' * W}")
    pr("  SCENARIO 3: Johar Town Foodpanda -> SalesReceipt + Commission + QB Class".center(W))
    pr(f"{'=' * W}")

    if json_mode:
        p3 = _build_franchise_sales_receipt(o_johar, resolver, branch_johar)
        show_payload_json(p3)
    else:
        show_pos_terminal(o_johar)
        show_backend_api(o_johar, "sales_receipt")
        show_database(o_johar, "sales_receipt")
        p3 = _build_franchise_sales_receipt(o_johar, resolver, branch_johar)
        show_quickbooks(p3, "SalesReceipt", resolver)
        pr(f"\n  QB Class: \"{branch_johar['class']}\"")
        pr(f"  Foodpanda Commission (30%): -{format_pkr(o_johar.platform_commission)}")
        pr(f"  Net Settlement to branch: {format_pkr(o_johar.total - o_johar.platform_commission)}")

    # === SCENARIO 4: Central Kitchen -> Branch transfer ===
    pr(f"\n{'=' * W}")
    pr("  SCENARIO 4: Central Kitchen -> Gulberg Branch Transfer -> JournalEntry".center(W))
    pr(f"{'=' * W}")

    transfer_amount = 350000  # Rs.3,500 of marinated chicken, prepped biryani masala
    if json_mode:
        p4 = _build_inter_branch_transfer(
            {"name": "Central Kitchen", "class": "Central-Kitchen"},
            branch_gulberg, resolver,
            "Marinated chicken (20kg), Biryani masala (5kg), Naan dough (10kg)",
            transfer_amount, target_date,
        )
        show_payload_json(p4)
    else:
        pr()
        box_top("POS TERMINAL  --  Central Kitchen Transfer", BW)
        box_line("Transfer Type: Central Kitchen -> Branch", BW)
        box_line(f"From: Central Kitchen | To: {branch_gulberg['name']} Branch", BW)
        box_empty(BW)
        box_line("Items Transferred:", BW)
        box_line("  1. Marinated Chicken (20 kg)          Rs.1,800.00", BW)
        box_line("  2. Biryani Masala Mix (5 kg)           Rs.1,200.00", BW)
        box_line("  3. Naan Dough (10 kg)                    Rs.500.00", BW)
        box_empty(BW)
        box_line(f"Total Transfer Value:                   {format_pkr(transfer_amount)}", BW)
        box_line("Approved by: Central Kitchen Manager", BW)
        box_bottom(BW)

        box_arrow(BW)
        box_top("BACKEND API", BW)
        box_line("POST /api/v1/inventory/transfers", BW)
        box_line(f"  -> Creates transfer record: Central Kitchen -> {branch_gulberg['name']}", BW)
        box_line(f"  -> Items: 3 line items, total value {format_pkr(transfer_amount)}", BW)
        box_line("  -> Auto-adjusts inventory at both locations", BW)
        box_empty(BW)
        box_line("POST /api/v1/integrations/quickbooks/sync  (auto-triggered)", BW)
        box_line("  -> Enqueues job: create_journal_entry (inter-branch transfer) | priority: 3", BW)
        box_bottom(BW)

        box_arrow(BW)
        box_top("DATABASE RECORDS", BW)
        box_line("TABLE: inventory_transfers", BW)
        box_line(f"  from: Central Kitchen | to: {branch_gulberg['name']} | status: completed", BW)
        box_line(f"  total_value: {transfer_amount} paisa | items: 3 | approved_by: ck_manager", BW)
        box_empty(BW)
        box_line("TABLE: qb_sync_queue", BW)
        box_line("  job_type: create_journal_entry | entity_type: transfer | status: completed", BW)
        box_bottom(BW)

        p4 = _build_inter_branch_transfer(
            {"name": "Central Kitchen", "class": "Central-Kitchen"},
            branch_gulberg, resolver,
            "Marinated chicken (20kg), Biryani masala (5kg), Naan dough (10kg)",
            transfer_amount, target_date,
        )
        show_quickbooks(p4, "JournalEntry")
        pr()
        pr("  Double-Entry Effect (Inter-Branch Transfer):")
        pr(f"    DR  Inter-Branch Transfer Cost            {paisa_to_decimal(transfer_amount):>10}  [Class: {branch_gulberg['class']}]")
        pr(f"    CR  Central Kitchen Revenue               {paisa_to_decimal(transfer_amount):>10}  [Class: Central-Kitchen]")
        pr()
        pr("  -> Receiving branch (Gulberg) incurs cost")
        pr("  -> Central Kitchen recognizes internal revenue")
        pr("  -> QB Classes enable separate P&L per entity")

    # === SCENARIO 5: Franchise Royalty Calculation ===
    pr(f"\n{'=' * W}")
    pr("  SCENARIO 5: Franchise Royalty (6%) + Marketing Fund (3%) -> JournalEntry".center(W))
    pr(f"{'=' * W}")

    branch_revenues: dict[str, int] = {}
    for key, order in f_orders.items():
        bn = order.branch_name or "Unknown"
        branch_revenues[bn] = branch_revenues.get(bn, 0) + order.subtotal

    if json_mode:
        p5 = _build_royalty_entry(branch_revenues, 6.0, 3.0, resolver, target_date)
        show_payload_json(p5)
    else:
        pr()
        box_top("POS TERMINAL  --  Franchise Royalty Calculation", BW)
        box_line(f"Date: {target_date} | Calculation Period: Daily", BW)
        box_empty(BW)
        box_line(f"{'Branch':<25} {'Gross Revenue':>14} {'Royalty 6%':>12} {'Mktg 3%':>12} {'Total':>12}", BW)
        box_line(f"{'-'*25} {'-'*14} {'-'*12} {'-'*12} {'-'*12}", BW)

        total_rev = 0
        total_roy = 0
        total_mkt = 0
        for bn, rev in branch_revenues.items():
            roy = int(rev * 6 / 100)
            mkt = int(rev * 3 / 100)
            total_rev += rev
            total_roy += roy
            total_mkt += mkt
            box_line(f"{bn:<25} {format_pkr(rev):>14} {format_pkr(roy):>12} {format_pkr(mkt):>12} {format_pkr(roy + mkt):>12}", BW)

        box_line(f"{'-'*25} {'-'*14} {'-'*12} {'-'*12} {'-'*12}", BW)
        box_line(f"{'TOTAL':<25} {format_pkr(total_rev):>14} {format_pkr(total_roy):>12} {format_pkr(total_mkt):>12} {format_pkr(total_roy + total_mkt):>12}", BW)
        box_empty(BW)
        box_line(f"Total Due to Franchisor: {format_pkr(total_roy + total_mkt)}", BW)
        box_line(f"  Royalty (6%): {format_pkr(total_roy)} -> accrued to Royalty Payable", BW)
        box_line(f"  Marketing (3%): {format_pkr(total_mkt)} -> accrued to Marketing Fund Payable", BW)
        box_bottom(BW)

        box_arrow(BW)
        box_top("BACKEND API", BW)
        box_line("POST /api/v1/integrations/quickbooks/sync  (type: franchise_royalty)", BW)
        box_line(f"  -> Calculates royalty on {paisa_to_decimal(total_rev)} PKR gross revenue", BW)
        box_line(f"  -> Royalty 6%: {paisa_to_decimal(total_roy)} PKR", BW)
        box_line(f"  -> Marketing 3%: {paisa_to_decimal(total_mkt)} PKR", BW)
        box_line("  -> Enqueues job: create_journal_entry (franchise_royalty) | priority: 5", BW)
        box_bottom(BW)

        box_arrow(BW)
        box_top("DATABASE RECORDS", BW)
        box_line("TABLE: franchise_royalty_log", BW)
        box_line(f"  period: {target_date} | total_revenue: {total_rev}", BW)
        box_line(f"  royalty_pct: 6.0 | royalty_amount: {total_roy}", BW)
        box_line(f"  marketing_pct: 3.0 | marketing_amount: {total_mkt}", BW)
        box_line(f"  status: accrued | payment_due: 2026-03-15", BW)
        box_empty(BW)
        box_line("TABLE: qb_sync_queue", BW)
        box_line("  job_type: create_journal_entry | entity_type: royalty | status: completed", BW)
        box_bottom(BW)

        p5 = _build_royalty_entry(branch_revenues, 6.0, 3.0, resolver, target_date)
        show_quickbooks(p5, "JournalEntry")

        pr()
        pr("  Double-Entry Effect (Franchise Fees):")
        pr(f"    DR  Royalty Fee Expense (6%)               {paisa_to_decimal(total_roy):>10}")
        pr(f"    DR  Marketing Fund (3%)                    {paisa_to_decimal(total_mkt):>10}")
        pr(f"    CR  Royalty Payable                        {paisa_to_decimal(total_roy):>10}")
        pr(f"    CR  Marketing Fund Payable                 {paisa_to_decimal(total_mkt):>10}")
        debit_total = total_roy + total_mkt
        credit_total = total_roy + total_mkt
        pr(f"\n  Balance Check: DR {paisa_to_decimal(debit_total)} = CR {paisa_to_decimal(credit_total)} {'BALANCED' if debit_total == credit_total else 'IMBALANCED!'}")

    # === SCENARIO 6: Consolidated Daily Close (all branches) ===
    pr(f"\n{'=' * W}")
    pr("  SCENARIO 6: Consolidated Daily Close -> JournalEntry + Multi-Branch Deposit".center(W))
    pr(f"{'=' * W}")

    branch_order_groups: dict[str, list[MockOrder]] = {}
    for key, order in f_orders.items():
        bn = order.branch_name or "Unknown"
        if bn not in branch_order_groups:
            branch_order_groups[bn] = []
        branch_order_groups[bn].append(order)

    all_orders = list(f_orders.values())

    if json_mode:
        p6_je = _build_consolidated_journal(branch_order_groups, resolver, target_date)
        show_payload_json(p6_je)
        p6_dep = _build_multi_branch_deposit(branch_order_groups, resolver, target_date)
        show_payload_json(p6_dep)
    else:
        pr()
        box_top("POS TERMINAL  --  Consolidated End of Day Close", BW)
        box_line(f"Date: {target_date} | Closed by: Operations Manager", BW)
        box_empty(BW)
        box_line(f"{'Branch':<18} {'Orders':>7} {'Revenue':>14} {'Disc':>10} {'Tax':>12} {'Total':>14}", BW)
        box_line(f"{'-'*18} {'-'*7} {'-'*14} {'-'*10} {'-'*12} {'-'*14}", BW)

        grand_count = 0
        grand_rev = 0
        grand_disc = 0
        grand_tax = 0
        grand_total = 0
        for bn, orders in branch_order_groups.items():
            cnt = len(orders)
            rev = sum(o.subtotal for o in orders)
            disc = sum(o.discount_amount for o in orders)
            tax = sum(o.tax_amount for o in orders)
            tot = sum(o.total for o in orders)
            grand_count += cnt
            grand_rev += rev
            grand_disc += disc
            grand_tax += tax
            grand_total += tot
            box_line(f"{bn:<18} {cnt:>7} {format_pkr(rev):>14} {format_pkr(disc):>10} {format_pkr(tax):>12} {format_pkr(tot):>14}", BW)

        box_line(f"{'-'*18} {'-'*7} {'-'*14} {'-'*10} {'-'*12} {'-'*14}", BW)
        box_line(f"{'GRAND TOTAL':<18} {grand_count:>7} {format_pkr(grand_rev):>14} {format_pkr(grand_disc):>10} {format_pkr(grand_tax):>12} {format_pkr(grand_total):>14}", BW)

        box_empty(BW)
        box_line("Payment Method Breakdown (by branch):", BW)
        for bn, orders in branch_order_groups.items():
            by_pm: dict[str, int] = {}
            for o in orders:
                pm = o.payment_method or "Cash"
                by_pm[pm] = by_pm.get(pm, 0) + o.total
            parts = [f"{pm}: {format_pkr(amt)}" for pm, amt in by_pm.items()]
            box_line(f"  {bn:<16} {' | '.join(parts)}", BW)
        box_bottom(BW)

        show_backend_api(all_orders[0], "daily_close")
        show_database(all_orders[0], "daily_close")

        p6_je = _build_consolidated_journal(branch_order_groups, resolver, target_date)
        show_quickbooks(p6_je, "JournalEntry")

        p6_dep = _build_multi_branch_deposit(branch_order_groups, resolver, target_date)
        show_quickbooks(p6_dep, "Deposit")

        # Balance check
        pr(f"\n  CONSOLIDATED JOURNAL BALANCE CHECK:")
        je_debits = sum(
            int(Decimal(l["Amount"]) * 100)
            for l in p6_je["Line"]
            if l.get("JournalEntryLineDetail", {}).get("PostingType") == "Debit"
        )
        je_credits = sum(
            int(Decimal(l["Amount"]) * 100)
            for l in p6_je["Line"]
            if l.get("JournalEntryLineDetail", {}).get("PostingType") == "Credit"
        )
        pr(f"    Total Debit:  {format_pkr(je_debits)}")
        pr(f"    Total Credit: {format_pkr(je_credits)}")
        pr(f"    Status: {'BALANCED' if je_debits == je_credits else 'IMBALANCED !!!'}")

    # === SCENARIO 7: Branch P&L Summary (QB Classes) ===
    pr(f"\n{'=' * W}")
    pr("  SCENARIO 7: Per-Branch P&L via QB Classes (Reporting View)".center(W))
    pr(f"{'=' * W}")

    pr()
    pr("  This scenario demonstrates how QB Classes enable per-branch profit tracking.")
    pr("  No new QB entity is created — this is a REPORTING capability.\n")

    box_top("QUICKBOOKS REPORT: Profit & Loss by Class", BW)
    box_line(f"Period: {target_date} (Daily)", BW)
    box_empty(BW)

    col_branches = list(branch_order_groups.keys())
    # Header
    hdr = f"{'Account':<30}"
    for bn in col_branches:
        hdr += f" {bn:>14}"
    hdr += f" {'TOTAL':>14}"
    box_line(hdr, BW)
    box_line("-" * (BW - 4), BW)

    # Revenue row
    rev_row = f"{'Revenue':<30}"
    rev_total = 0
    for bn in col_branches:
        orders = branch_order_groups[bn]
        rev = sum(o.subtotal for o in orders) - sum(o.discount_amount for o in orders)
        rev_row += f" {format_pkr(rev):>14}"
        rev_total += rev
    rev_row += f" {format_pkr(rev_total):>14}"
    box_line(rev_row, BW)

    # Tax row
    tax_row = f"{'Tax Collected':<30}"
    tax_total = 0
    for bn in col_branches:
        orders = branch_order_groups[bn]
        tax = sum(o.tax_amount for o in orders)
        tax_row += f" {format_pkr(tax):>14}"
        tax_total += tax
    tax_row += f" {format_pkr(tax_total):>14}"
    box_line(tax_row, BW)

    # Gross collection
    gc_row = f"{'Gross Collection':<30}"
    gc_total = 0
    for bn in col_branches:
        orders = branch_order_groups[bn]
        gc = sum(o.total for o in orders)
        gc_row += f" {format_pkr(gc):>14}"
        gc_total += gc
    gc_row += f" {format_pkr(gc_total):>14}"
    box_line(gc_row, BW)

    box_line("-" * (BW - 4), BW)

    # Royalty (estimated at 6%)
    roy_row = f"{'Less: Royalty (6%)':<30}"
    roy_total = 0
    for bn in col_branches:
        orders = branch_order_groups[bn]
        rev = sum(o.subtotal for o in orders)
        roy = int(rev * 6 / 100)
        roy_row += f" {'-' + format_pkr(roy):>14}"
        roy_total += roy
    roy_row += f" {'-' + format_pkr(roy_total):>14}"
    box_line(roy_row, BW)

    # Marketing (estimated at 3%)
    mkt_row = f"{'Less: Marketing (3%)':<30}"
    mkt_total = 0
    for bn in col_branches:
        orders = branch_order_groups[bn]
        rev = sum(o.subtotal for o in orders)
        mkt = int(rev * 3 / 100)
        mkt_row += f" {'-' + format_pkr(mkt):>14}"
        mkt_total += mkt
    mkt_row += f" {'-' + format_pkr(mkt_total):>14}"
    box_line(mkt_row, BW)

    # Platform commission (only for Foodpanda branches)
    comm_row = f"{'Less: Platform Commission':<30}"
    comm_total = 0
    for bn in col_branches:
        orders = branch_order_groups[bn]
        comm = sum(o.platform_commission for o in orders)
        comm_row += f" {('-' + format_pkr(comm) if comm else format_pkr(0)):>14}"
        comm_total += comm
    comm_row += f" {'-' + format_pkr(comm_total):>14}"
    box_line(comm_row, BW)

    box_line("-" * (BW - 4), BW)

    # Net profit estimate
    net_row = f"{'NET BRANCH CONTRIBUTION':<30}"
    net_total = 0
    for bn in col_branches:
        orders = branch_order_groups[bn]
        rev = sum(o.subtotal for o in orders) - sum(o.discount_amount for o in orders)
        roy = int(sum(o.subtotal for o in orders) * 6 / 100)
        mkt = int(sum(o.subtotal for o in orders) * 3 / 100)
        comm = sum(o.platform_commission for o in orders)
        net = rev - roy - mkt - comm
        net_row += f" {format_pkr(net):>14}"
        net_total += net
    net_row += f" {format_pkr(net_total):>14}"
    box_line(net_row, BW)

    box_bottom(BW)

    pr("\n  Key Insight: QB Classes allow the client to run this P&L report")
    pr("  directly in QuickBooks Online, filtering by any branch or combination.")
    pr("  No custom reporting needed — it's built into QB's standard reports.")
    pr()
    pr("  How to access in QuickBooks:")
    pr("    Reports -> Profit and Loss -> Customize -> Rows/Columns -> Class")
    pr("    This gives per-branch breakdown for any date range.")
    pr()


def run_summary():
    header(f"QUICKBOOKS TEMPLATE SUMMARY -- ALL {len(MAPPING_TEMPLATES)} TEMPLATES")
    pr(
        f"\n  {'#':<4} {'Template Key':<30} {'Name':<40} "
        f"{'Maps':>4} {'INC':>4} {'COGS':>4} {'TAX':>4} {'BANK':>4} {'Valid':>5}"
    )
    pr(
        f"  {'-'*4} {'-'*30} {'-'*40} "
        f"{'-'*4} {'-'*4} {'-'*4} {'-'*4} {'-'*4} {'-'*5}"
    )

    total_maps = 0
    valid_count = 0

    for idx, (key, tmpl) in enumerate(MAPPING_TEMPLATES.items(), 1):
        maps = tmpl["mappings"]
        total_maps += len(maps)

        counts: dict[str, int] = {}
        for m in maps:
            mt = m["mapping_type"]
            counts[mt] = counts.get(mt, 0) + 1

        missing = [
            r for r in REQUIRED_TYPES
            if not any(m.get("is_default") and m["mapping_type"] == r for m in maps)
        ]
        is_valid = len(missing) == 0
        if is_valid:
            valid_count += 1
        status = "OK" if is_valid else f"MISS"

        pr(
            f"  {idx:<4} {key:<30} {tmpl['name']:<40} "
            f"{len(maps):>4} "
            f"{counts.get('income', 0):>4} "
            f"{counts.get('cogs', 0):>4} "
            f"{counts.get('tax_payable', 0):>4} "
            f"{counts.get('bank', 0):>4} "
            f"{status:>5}"
        )

    pr(f"\n  Totals: {len(MAPPING_TEMPLATES)} templates, {total_maps} mappings, "
       f"{valid_count}/{len(MAPPING_TEMPLATES)} valid")

    # Type distribution across all templates
    pr(f"\n  MAPPING TYPE DISTRIBUTION (across all templates):")
    all_types: dict[str, int] = {}
    for tmpl in MAPPING_TEMPLATES.values():
        for m in tmpl["mappings"]:
            mt = m["mapping_type"]
            all_types[mt] = all_types.get(mt, 0) + 1

    for mt in TYPE_ORDER:
        if mt in all_types:
            lbl = TYPE_LABELS.get(mt, mt.upper())
            pr(f"    {lbl:<14} {all_types[mt]:>4} total mappings")

    pr(f"\n  Usage:")
    pr(f"    python {sys.argv[0]} pakistani_restaurant   # Full detail for one")
    pr(f"    python {sys.argv[0]} --all                  # Full detail, all 40")
    pr(f"    python {sys.argv[0]} --all > report.txt     # Save to file")
    pr(f"    python {sys.argv[0]} --json biryani_house   # JSON payloads")
    pr()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    json_mode = "--json" in args
    if json_mode:
        args.remove("--json")

    if not args or args == ["--summary"]:
        run_summary()
        return

    if args == ["--list"]:
        for key in MAPPING_TEMPLATES:
            print(key)
        return

    if args == ["--all"]:
        orders = make_sample_orders()
        for key, tmpl in MAPPING_TEMPLATES.items():
            if key == "multi_franchise_pakistani":
                run_franchise_tests(key, tmpl, json_mode=json_mode)
            else:
                run_template_tests(key, tmpl, orders, json_mode=json_mode)
        return

    # Specific template(s)
    orders = make_sample_orders()
    for arg in args:
        if arg.startswith("--"):
            continue
        if arg in MAPPING_TEMPLATES:
            if arg == "multi_franchise_pakistani":
                run_franchise_tests(arg, MAPPING_TEMPLATES[arg], json_mode=json_mode)
            else:
                run_template_tests(arg, MAPPING_TEMPLATES[arg], orders, json_mode=json_mode)
        else:
            pr(f"Unknown template: {arg}")
            pr(f"Available: {', '.join(list(MAPPING_TEMPLATES.keys())[:5])} ...")
            pr(f"Run with --list to see all template names")
            sys.exit(1)


if __name__ == "__main__":
    main()
