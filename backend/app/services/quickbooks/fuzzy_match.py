"""
Multi-signal fuzzy matching engine for QB Chart of Accounts diagnostic.

Compares template mappings against a client's existing QB accounts using
weighted scoring across 6 signals: exact name, anchor (distinctive) token
match, synonym overlap, QB AccountType compatibility, Jaccard word overlap,
and substring containment.

Key design: "anchor tokens" are the distinctive words in an account name
after stripping generic accounting noise (expense, cost, sales, payable...).
These are what actually identify the account's purpose, so they get the
highest non-exact weight.

Thresholds:
  >= 0.80  → high confidence (auto-suggest)
  0.55–0.79 → medium confidence (candidate, needs review)
  < 0.55   → low confidence (no match)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Synonym sets — domain-specific Pakistani / restaurant / accounting terms
# Each set groups words that are semantically equivalent for matching.
# ---------------------------------------------------------------------------
SYNONYM_SETS: list[set[str]] = [
    # 0 — Food / cuisine
    {"food", "dining", "meal", "khana", "khaana", "cuisine"},
    # 1 — Revenue words
    {"sales", "revenue", "income", "earnings", "proceeds", "turnover", "amdani"},
    # 2 — Beverage
    {"beverage", "drink", "chai", "juice", "refreshment", "soft drink", "sharbat"},
    # 3 — Catering / events
    {"catering", "event", "banquet", "function", "party", "dawat"},
    # 4 — Takeaway
    {"takeaway", "takeout", "parcel", "delivery order"},
    # 5 — Dine-in
    {"dine in", "dine-in", "eat in", "table service"},

    # 6 — Cost / COGS
    {"cost", "cogs", "purchase", "procurement", "kharcha"},
    # 7 — Ingredients
    {"ingredient", "raw material", "food cost", "recipe cost"},
    # 8 — Packaging
    {"packaging", "container", "disposable", "disposables", "packing"},

    # 9 — Tax (all tax-related terms)
    {"tax", "gst", "pst", "sst", "vat", "duty", "withholding", "sales tax"},
    # 10 — FBR / Federal
    {"fbr", "federal", "national", "government"},
    # 11 — Provincial
    {"pra", "provincial", "sindh", "kpk", "balochistan", "punjab"},

    # 12 — Cash / register
    {"cash", "register", "drawer", "till", "petty cash", "naqd"},
    # 13 — Bank
    {"bank", "checking", "savings", "current account", "hbl", "meezan",
     "ubl", "mcb", "allied", "nbp"},
    # 14 — Mobile wallets
    {"jazzcash", "easypaisa", "mobile wallet", "digital payment",
     "sadapay", "nayapay"},

    # 15 — Expense (generic)
    {"expense", "expenditure", "spending", "overhead"},
    # 16 — Rent
    {"rent", "lease", "occupancy", "premises", "kiraya"},
    # 17 — Utility
    {"utility", "utilities", "electricity", "gas", "water", "bijli",
     "sui gas", "paani"},
    # 18 — Payroll
    {"payroll", "salary", "salaries", "wages",
     "staff cost", "tankhwah"},
    # 19 — Marketing
    {"marketing", "advertising", "promotion", "publicity", "istihar", "ads"},
    # 20 — Repair / Maintenance
    {"repair", "maintenance", "upkeep", "servicing", "marammat"},
    # 21 — Insurance
    {"insurance", "coverage", "premium", "takaful", "bima"},
    # 22 — License
    {"license", "licence", "permit", "permits", "registration"},
    # 23 — Depreciation
    {"depreciation", "amortization", "write off", "wear"},
    # 24 — Inventory / supplies
    {"inventory", "stock", "supplies", "raw material", "goods", "saman"},
    # 25 — Commission
    {"commission", "brokerage", "percentage", "service fee",
     "platform fee"},

    # 26 — Discount
    {"discount", "rebate", "allowance", "markdown", "concession",
     "riaayat"},
    # 27 — Tips
    {"tip", "tips", "gratuity", "bakshish"},
    # 28 — Service charge
    {"service charge", "service fee"},
    # 29 — Gift card
    {"gift card", "gift cards", "voucher", "coupon", "credit note"},

    # 30 — Delivery platforms
    {"foodpanda", "cheetay", "careem", "bykea"},
    # 31 — Delivery
    {"delivery", "shipping", "dispatch", "courier", "rider"},

    # 32 — Rounding
    {"rounding", "round off", "adjustment", "difference", "fark"},
    # 33 — Over/Short
    {"over", "short", "variance", "discrepancy", "cash over short"},

    # 34 — Deposit / advance
    {"deposit", "deposits", "advance", "prepaid"},
]

# Build reverse lookup: word → set of synonym-set indices
# A word can belong to MULTIPLE synonym sets (e.g. "fbr" → tax + federal)
_SYNONYM_INDEX: dict[str, set[int]] = {}
for _i, _syn_set in enumerate(SYNONYM_SETS):
    for _word in _syn_set:
        _key = _word.lower()
        if _key not in _SYNONYM_INDEX:
            _SYNONYM_INDEX[_key] = set()
        _SYNONYM_INDEX[_key].add(_i)

# Grammar/noise words to strip during basic tokenization
_NOISE_WORDS = frozenset({
    "of", "the", "and", "or", "a", "an", "for", "in", "on", "to", "by",
    "with", "from", "at", "is", "its", "it", "as", "be", "no", "not",
    "-", "&", "/", ".", ",",
})

# Accounting stop words — appear in many account names, carry low
# discriminative power. Stripping these reveals the ANCHOR tokens
# that actually identify what an account is for.
_ACCT_STOP_WORDS = frozenset({
    # Generic category words
    "expense", "expenses", "cost", "costs",
    "sales", "revenue", "income",
    "payable", "receivable",
    "account", "accounts",
    # Generic qualifier words
    "fee", "fees", "given", "allowed",
    "total", "net", "gross",
    "other", "general", "misc", "miscellaneous",
    "paid", "collected",
    "current", "liability", "asset",
})

_NUMERIC_RE = re.compile(r"^[\d.%]+$")


# ---------------------------------------------------------------------------
# Scoring weights — anchor tokens dominate non-exact scoring
# ---------------------------------------------------------------------------
WEIGHT_EXACT = 1.00
WEIGHT_ANCHOR = 0.40       # Distinctive key-word matching (highest)
WEIGHT_SYNONYM = 0.25      # Domain semantic overlap
WEIGHT_TYPE = 0.20         # QB AccountType compatibility
WEIGHT_JACCARD = 0.10      # Raw word overlap
WEIGHT_SUBSTRING = 0.05    # Containment

# Confidence thresholds (lowered from 0.85/0.60 to match new scoring)
THRESHOLD_HIGH = 0.80
THRESHOLD_MEDIUM = 0.55


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class MatchSignals:
    """Breakdown of individual scoring signals."""
    exact: float = 0.0
    anchor: float = 0.0
    jaccard: float = 0.0
    synonym: float = 0.0
    type_match: float = 0.0
    substring: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "exact": round(self.exact, 4),
            "anchor": round(self.anchor, 4),
            "jaccard": round(self.jaccard, 4),
            "synonym": round(self.synonym, 4),
            "type_match": round(self.type_match, 4),
            "substring": round(self.substring, 4),
        }


@dataclass
class MatchResult:
    """Result of comparing one template mapping against one QB account."""
    score: float
    signals: MatchSignals
    confidence: str  # "high" | "medium" | "low"

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 4),
            "signals": self.signals.to_dict(),
            "confidence": self.confidence,
        }


@dataclass
class CandidateMatch:
    """A QB account matched against a template mapping, with score."""
    qb_account_id: str
    qb_account_name: str
    qb_account_type: str
    qb_account_sub_type: str | None
    fully_qualified_name: str | None
    active: bool
    score: float
    signals: MatchSignals
    confidence: str

    def to_dict(self) -> dict:
        return {
            "qb_account_id": self.qb_account_id,
            "qb_account_name": self.qb_account_name,
            "qb_account_type": self.qb_account_type,
            "qb_account_sub_type": self.qb_account_sub_type,
            "fully_qualified_name": self.fully_qualified_name,
            "active": self.active,
            "score": round(self.score, 4),
            "signals": self.signals.to_dict(),
            "confidence": self.confidence,
        }


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------
def tokenize(name: str) -> set[str]:
    """Split account name into lowercase word tokens, stripping noise."""
    words = re.split(r"[\s\-_/()&,.:;]+", name.lower())
    return {w for w in words if w and w not in _NOISE_WORDS}


def _tokenize_for_synonyms(name: str) -> set[str]:
    """
    Tokenize for synonym lookup — includes bigrams so multi-word
    synonyms like 'sales tax', 'raw material', 'sui gas' can match.
    """
    words = re.split(r"[\s\-_/()&,.:;]+", name.lower())
    clean = [w for w in words if w and w not in _NOISE_WORDS]
    tokens = set(clean)
    # Add bigrams
    for i in range(len(clean) - 1):
        tokens.add(f"{clean[i]} {clean[i + 1]}")
    return tokens


def _extract_anchor_tokens(name: str) -> set[str]:
    """
    Extract distinctive anchor tokens — the words that actually identify
    what the account is for, after removing generic accounting terms
    and numeric tokens like '17%', '16%'.
    """
    words = re.split(r"[\s\-_/()&,.:;]+", name.lower())
    return {
        w for w in words
        if w
        and w not in _NOISE_WORDS
        and w not in _ACCT_STOP_WORDS
        and not _NUMERIC_RE.match(w)
    }


# ---------------------------------------------------------------------------
# Helper: check if two tokens share a synonym group
# ---------------------------------------------------------------------------
def _share_synonym_group(token_a: str, token_b: str) -> bool:
    """Return True if two tokens belong to at least one common synonym set."""
    sets_a = _SYNONYM_INDEX.get(token_a)
    sets_b = _SYNONYM_INDEX.get(token_b)
    if sets_a and sets_b:
        return bool(sets_a & sets_b)
    return False


# ---------------------------------------------------------------------------
# Individual signal functions
# ---------------------------------------------------------------------------
def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Jaccard index: |A intersection B| / |A union B|."""
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def anchor_token_score(template_name: str, qb_name: str) -> float:
    """
    Fraction of the template's distinctive tokens found in the QB account
    name, either via direct match or synonym-group equivalence.

    This is the primary non-exact signal: if the template needs "Delivery"
    and the QB account has "Delivery", that's a strong signal regardless
    of surrounding noise words like "Expense" or "Cost".

    Synonym-equivalent matches (e.g. "gst" ↔ "tax") count at 80%.
    """
    key_t = _extract_anchor_tokens(template_name)
    key_q = _extract_anchor_tokens(qb_name)

    if not key_t:
        # Template has only generic words; fall back to Jaccard
        return 0.0

    matched = 0.0
    used_q: set[str] = set()

    for tt in key_t:
        if tt in key_q:
            # Direct token match
            matched += 1.0
            used_q.add(tt)
        else:
            # Check synonym equivalence
            for qt in key_q - used_q:
                if _share_synonym_group(tt, qt):
                    matched += 0.8  # synonym match = 80% of direct
                    used_q.add(qt)
                    break

    return min(1.0, matched / len(key_t))


def synonym_overlap(tokens_a: set[str], tokens_b: set[str]) -> float:
    """
    Fraction of synonym sets shared between two token sets.
    Uses the multi-set reverse index to map tokens → synonym set IDs,
    then computes Jaccard overlap of those IDs.
    """
    sets_a: set[int] = set()
    for token in tokens_a:
        idxs = _SYNONYM_INDEX.get(token)
        if idxs is not None:
            sets_a.update(idxs)
    sets_b: set[int] = set()
    for token in tokens_b:
        idxs = _SYNONYM_INDEX.get(token)
        if idxs is not None:
            sets_b.update(idxs)
    if not sets_a or not sets_b:
        return 0.0
    overlap = sets_a & sets_b
    union = sets_a | sets_b
    return len(overlap) / len(union)


def type_compatibility(
    type_a: str, type_b: str,
    sub_a: str | None, sub_b: str | None,
) -> float:
    """
    Score QB AccountType + AccountSubType compatibility.
    1.0 = same type + same subtype
    0.8 = same type, different/missing subtype
    0.4 = related type groups (e.g. Income/Other Income)
    0.0 = unrelated types
    """
    if type_a == type_b:
        if sub_a and sub_b and sub_a == sub_b:
            return 1.0
        elif sub_a and sub_b:
            return 0.7
        return 0.8
    # Related type groups — QB's type taxonomy
    related_groups: list[set[str]] = [
        {"Income", "Other Income"},
        {"Expense", "Other Expense"},
        {"Bank", "Other Current Asset"},
        {"Other Current Liability", "Long Term Liability"},
        {"Accounts Receivable", "Other Current Asset"},
        {"Accounts Payable", "Other Current Liability"},
        {"Cost of Goods Sold", "Expense"},
    ]
    for group in related_groups:
        if type_a in group and type_b in group:
            return 0.4
    return 0.0


def substring_match(name_a: str, name_b: str) -> float:
    """
    Check if one name contains the other as a substring.
    Returns ratio of shorter/longer for partial credit.
    """
    a = name_a.lower().strip()
    b = name_b.lower().strip()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0  # Handled by exact, but safe to score here too
    if a in b or b in a:
        shorter = min(len(a), len(b))
        longer = max(len(a), len(b))
        return shorter / longer
    return 0.0


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------
def match_score(
    template_name: str,
    template_type: str,
    template_sub_type: str | None,
    qb_name: str,
    qb_type: str,
    qb_sub_type: str | None,
) -> MatchResult:
    """
    Calculate multi-signal match score between a template mapping
    and a QB account.

    Returns MatchResult with composite score (0.0–1.0), signal breakdown,
    and confidence level (high/medium/low).
    """
    signals = MatchSignals()

    # Signal 1: Exact name match (case-insensitive)
    if template_name.lower().strip() == qb_name.lower().strip():
        signals.exact = 1.0

    # Signal 2: Anchor (distinctive) token match
    signals.anchor = anchor_token_score(template_name, qb_name)

    # Signal 3: Jaccard word overlap
    tokens_t = tokenize(template_name)
    tokens_q = tokenize(qb_name)
    signals.jaccard = jaccard_similarity(tokens_t, tokens_q)

    # Signal 4: Synonym overlap (with bigrams)
    syn_tokens_t = _tokenize_for_synonyms(template_name)
    syn_tokens_q = _tokenize_for_synonyms(qb_name)
    signals.synonym = synonym_overlap(syn_tokens_t, syn_tokens_q)

    # Signal 5: Type compatibility
    signals.type_match = type_compatibility(
        template_type, qb_type, template_sub_type, qb_sub_type,
    )

    # Signal 6: Substring containment
    signals.substring = substring_match(template_name, qb_name)

    # Composite score
    if signals.exact > 0:
        # Exact name match — very high confidence
        score = WEIGHT_EXACT * signals.exact
        if signals.type_match > 0:
            score = min(1.0, score + WEIGHT_TYPE * signals.type_match * 0.1)
    else:
        # Weighted combination of partial signals
        score = (
            WEIGHT_ANCHOR * signals.anchor
            + WEIGHT_SYNONYM * signals.synonym
            + WEIGHT_TYPE * signals.type_match
            + WEIGHT_JACCARD * signals.jaccard
            + WEIGHT_SUBSTRING * signals.substring
        )

    # Confidence classification
    if score >= THRESHOLD_HIGH:
        confidence = "high"
    elif score >= THRESHOLD_MEDIUM:
        confidence = "medium"
    else:
        confidence = "low"

    return MatchResult(
        score=round(score, 4),
        signals=signals,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Candidate finder — matches one template mapping against all QB accounts
# ---------------------------------------------------------------------------
def find_best_matches(
    template_name: str,
    template_type: str,
    template_sub_type: str | None,
    qb_accounts: list[dict],
    *,
    max_candidates: int = 5,
    min_score: float = 0.15,
) -> list[CandidateMatch]:
    """
    Score every QB account against one template mapping and return
    the top candidates above min_score, sorted by score descending.

    qb_accounts format (same as MappingService.fetch_qb_accounts()):
        [{"id": "123", "name": "Food Sales", "account_type": "Income",
          "account_sub_type": "SalesOfProductIncome",
          "fully_qualified_name": "Food Sales", "active": True}, ...]
    """
    candidates: list[CandidateMatch] = []

    for acct in qb_accounts:
        result = match_score(
            template_name=template_name,
            template_type=template_type,
            template_sub_type=template_sub_type,
            qb_name=acct.get("name", ""),
            qb_type=acct.get("account_type", ""),
            qb_sub_type=acct.get("account_sub_type"),
        )
        if result.score >= min_score:
            candidates.append(CandidateMatch(
                qb_account_id=str(acct.get("id", "")),
                qb_account_name=acct.get("name", ""),
                qb_account_type=acct.get("account_type", ""),
                qb_account_sub_type=acct.get("account_sub_type"),
                fully_qualified_name=acct.get("fully_qualified_name"),
                active=acct.get("active", True),
                score=result.score,
                signals=result.signals,
                confidence=result.confidence,
            ))

    # Sort by score descending
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:max_candidates]


# ---------------------------------------------------------------------------
# Reverse mapping — suggest what POS type a QB account might belong to
# ---------------------------------------------------------------------------
# Maps keywords found in QB account names to likely POS mapping types.
# Sorted longest-first during lookup so "delivery fee" beats "delivery".
_REVERSE_MAPPING_HINTS: dict[str, str] = {
    # Multi-word hints (higher specificity)
    "food cost": "cogs",
    "cost of goods": "cogs",
    "raw material": "cogs",
    "delivery fee": "delivery_fee",
    "delivery income": "delivery_fee",
    "delivery charge": "delivery_fee",
    "service charge": "service_charge",
    "tax payable": "tax_payable",
    "sales tax": "tax_payable",
    "gift card": "gift_card_liability",
    "gift voucher": "gift_card_liability",
    "round off": "rounding",
    "cash over": "cash_over_short",
    "over short": "cash_over_short",
    "staff cost": "expense",
    "food sales": "income",
    "beverage sales": "income",
    # Single-word hints
    "gst": "tax_payable",
    "fbr": "tax_payable",
    "pra": "tax_payable",
    "vat": "tax_payable",
    "pst": "tax_payable",
    "sst": "tax_payable",
    "cash": "bank",
    "bank": "bank",
    "checking": "bank",
    "savings": "bank",
    "jazzcash": "bank",
    "easypaisa": "bank",
    "foodpanda": "foodpanda_commission",
    "commission": "foodpanda_commission",
    "discount": "discount",
    "rebate": "discount",
    "rounding": "rounding",
    "tip": "tips",
    "gratuity": "tips",
    "voucher": "gift_card_liability",
    "cogs": "cogs",
    "ingredient": "cogs",
    "packaging": "cogs",
    "beverage": "income",
    "catering": "income",
    # Expense keywords (must NOT include "restaurant" — too broad)
    "rent": "expense",
    "salary": "expense",
    "salaries": "expense",
    "utility": "expense",
    "utilities": "expense",
    "insurance": "expense",
    "maintenance": "expense",
    "repair": "expense",
    "license": "expense",
    "permit": "expense",
    "advertising": "expense",
    "marketing": "expense",
    "depreciation": "expense",
    "delivery rider": "expense",
    "rider": "expense",
}


def suggest_mapping_type(qb_account_name: str, qb_account_type: str) -> str | None:
    """
    Given a QB account name and type, suggest what POS mapping_type
    it might correspond to. Returns None if no confident guess.

    Uses QB AccountType as a guardrail: if the keyword says "income"
    but the QB type is "Expense", trust the QB type instead.
    """
    name_lower = qb_account_name.lower()

    # Check keywords in order of specificity (longer phrases first)
    sorted_hints = sorted(
        _REVERSE_MAPPING_HINTS.items(), key=lambda x: -len(x[0])
    )
    for keyword, mapping_type in sorted_hints:
        if keyword in name_lower:
            # Guardrail: if QB AccountType contradicts the hint, use type
            if mapping_type == "income" and qb_account_type in (
                "Expense", "Other Expense", "Cost of Goods Sold",
            ):
                return "expense"
            if mapping_type == "expense" and qb_account_type in (
                "Income", "Other Income",
            ):
                return "income"
            return mapping_type

    # Fallback: use QB AccountType
    type_mapping: dict[str, str] = {
        "Income": "income",
        "Other Income": "income",
        "Cost of Goods Sold": "cogs",
        "Expense": "expense",
        "Other Expense": "expense",
        "Bank": "bank",
        "Other Current Liability": "other_current_liability",
    }
    return type_mapping.get(qb_account_type)
