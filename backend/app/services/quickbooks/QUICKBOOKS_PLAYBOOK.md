# QuickBooks Integration Playbook

> The complete setup guide for integrating QuickBooks Online with our POS system.
> Every restaurant type, every tax jurisdiction, every business model — covered.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Database Tables (5 Tables)](#2-database-tables)
3. [OAuth Setup — Connect QuickBooks](#3-oauth-setup)
4. [The Template System — 40 Templates](#4-the-template-system)
5. [Account Mapping — How It Works](#5-account-mapping)
6. [Entity Mapping — POS to QB Linkage](#6-entity-mapping)
7. [Sync Engine — What Gets Synced](#7-sync-engine)
8. [API Endpoints Reference](#8-api-endpoints)
9. [Environment Configuration](#9-environment-configuration)
10. [Client Onboarding Playbook](#10-client-onboarding-playbook)
11. [Template Catalog (All 40)](#11-template-catalog)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                     POS SYSTEM                                │
│                                                               │
│  Orders ──┐                                                   │
│  Payments ─┼──▶ Sync Engine ──▶ QB Client ──▶ QuickBooks API │
│  Menu ────┘    (sync.py)       (client.py)    (Intuit REST)   │
│                    │                               │          │
│                    ▼                               ▼          │
│              Mapping Service              OAuth Service       │
│              (mappings.py)                (oauth.py)          │
│                    │                               │          │
│                    ▼                               ▼          │
│              Template Library             Token Encryption    │
│              (templates.py)              (Fernet from         │
│              40 templates                 SECRET_KEY)         │
│              939 mappings                                     │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │              PostgreSQL (5 Tables)                       │  │
│  │  qb_connections · qb_account_mappings · qb_entity_map   │  │
│  │  qb_sync_queue  · qb_sync_log                           │  │
│  └─────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### File Layout

```
backend/app/services/quickbooks/
├── __init__.py          # Public exports
├── oauth.py             # OAuth 2.0 lifecycle (connect, refresh, revoke)
├── client.py            # Async HTTP client for QB API v3
├── mappings.py          # MappingService (smart defaults, CRUD, validation)
├── templates.py         # 40 composable Chart of Accounts templates
├── sync.py              # Sync orchestrator (orders→receipts, daily close)
└── QUICKBOOKS_PLAYBOOK.md  # This file

backend/app/models/quickbooks.py     # 5 ORM models
backend/app/schemas/quickbooks.py    # Pydantic request/response schemas
backend/app/api/v1/quickbooks.py     # FastAPI route handlers
```

---

## 2. Database Tables

All tables follow the project convention: UUID primary key + `tenant_id` + `created_at` + `updated_at`.

### 2.1 `qb_connections`
One row per tenant's QuickBooks link.

| Column | Type | Purpose |
|--------|------|---------|
| `realm_id` | String(50) | QuickBooks company ID (unique per tenant) |
| `company_name` | String(255) | Cached company display name |
| `access_token_encrypted` | Text | Fernet-encrypted OAuth2 access token |
| `refresh_token_encrypted` | Text | Fernet-encrypted OAuth2 refresh token |
| `access_token_expires_at` | DateTime | Access token expiry (~60 min from Intuit) |
| `refresh_token_expires_at` | DateTime | Refresh token expiry (~100 days, rolling) |
| `scope` | String(500) | `com.intuit.quickbooks.accounting` |
| `is_active` | Boolean | False = disconnected or expired |
| `connected_by` | UUID FK→users | Admin who authorized the connection |
| `connected_at` | DateTime | When OAuth was completed |
| `last_sync_at` | DateTime | Timestamp of last successful sync |
| `last_sync_status` | String(20) | `success` / `failed` / `in_progress` |
| `company_info` | JSON | Cached QB company metadata |
| `webhook_verifier_token` | String(255) | For QB webhook signature verification |

**Security**: Tokens are Fernet-encrypted at rest. The encryption key is derived from `SECRET_KEY` via SHA-256 → base64.

### 2.2 `qb_account_mappings`
Links POS accounting concepts → QB Chart of Accounts entries.

| Column | Type | Purpose |
|--------|------|---------|
| `connection_id` | UUID FK→qb_connections | Which QB connection |
| `mapping_type` | String(50) | `income`, `cogs`, `tax_payable`, `bank`, `expense`, `discount`, `tips`, etc. |
| `pos_reference_id` | UUID (nullable) | For entity-specific mappings (e.g. a category UUID) |
| `pos_reference_type` | String(50) | `category`, `tax_rate`, `payment_method` |
| `pos_reference_name` | String(255) | Human label: "BBQ & Grill" |
| `qb_account_id` | String(50) | QuickBooks account ID |
| `qb_account_name` | String(255) | QuickBooks account display name |
| `qb_account_type` | String(50) | `Income`, `Expense`, `Bank`, etc. |
| `qb_account_sub_type` | String(50) | `SalesOfProductIncome`, `CashOnHand`, etc. |
| `is_default` | Boolean | One default per mapping_type (catch-all) |
| `is_auto_created` | Boolean | True = created by template application |

**Lookup logic**: When syncing an order item from the "BBQ" category:
1. Check for category-specific mapping (`pos_reference_type='category'`, `pos_reference_id=bbq_uuid`)
2. Fall back to default income mapping ("Food Sales")

### 2.3 `qb_entity_mappings`
Links individual POS entities → QB entities.

| Column | Type | Purpose |
|--------|------|---------|
| `entity_type` | String(50) | `menu_item`, `category`, `customer`, `tax_code`, `payment_method`, `vendor`, etc. |
| `pos_entity_id` | UUID | POS entity UUID |
| `pos_entity_name` | String(255) | "Chicken Biryani" |
| `qb_entity_id` | String(50) | QuickBooks entity ID |
| `qb_entity_type` | String(50) | `Item`, `Customer`, `TaxCode`, etc. |
| `qb_entity_name` | String(255) | QB display name |
| `qb_entity_ref` | JSON | Full QB ref object for API calls |
| `sync_direction` | String(20) | `pos_to_qb` / `qb_to_pos` / `bidirectional` |
| `last_synced_at` | DateTime | Last sync timestamp |
| `sync_hash` | String(64) | SHA-256 of last synced state (drift detection) |

### 2.4 `qb_sync_queue`
Async job queue for sync operations.

| Column | Type | Purpose |
|--------|------|---------|
| `job_type` | String(50) | `create_sales_receipt`, `create_credit_memo`, `sync_item`, etc. |
| `entity_type` | String(50) | `order`, `menu_item`, `customer`, `daily_close` |
| `entity_id` | UUID | Specific POS entity (null for batch jobs) |
| `priority` | Integer | 0=critical, 5=normal, 10=bulk |
| `status` | String(20) | `pending` → `processing` → `completed` / `failed` / `dead_letter` |
| `payload` | JSON | Serialized data for the operation |
| `result` | JSON | QB API response on success |
| `error_message` | Text | Error description on failure |
| `retry_count` / `max_retries` | Integer | Exponential backoff (default 3 retries) |
| `idempotency_key` | String(100) | Prevents duplicate syncs |

### 2.5 `qb_sync_log`
Full audit trail of every QB API call.

| Column | Type | Purpose |
|--------|------|---------|
| `sync_type` | String(50) | Same as job_type + `oauth_connect`, `webhook`, etc. |
| `action` | String(20) | `create` / `update` / `delete` / `void` / `query` |
| `status` | String(20) | `success` / `failed` / `skipped` / `partial` |
| `http_method` / `http_url` | String | Raw HTTP details |
| `request_payload` / `response_payload` | JSON | Full request/response bodies |
| `response_status_code` | Integer | HTTP status |
| `error_message` / `error_code` | String | QB error details |
| `duration_ms` | Integer | Round-trip latency |
| `qb_doc_number` | String(50) | QB document number (e.g. Sales Receipt #) |
| `amount_paisa` | Integer | Transaction amount for financial audit |
| `batch_id` | UUID | Groups related operations |

---

## 3. OAuth Setup

### 3.1 Prerequisites

1. **Intuit Developer Account** at https://developer.intuit.com
2. **Create an app** → get `Client ID` and `Client Secret`
3. **Set Redirect URI** in Intuit app settings to match your `QB_REDIRECT_URI`

### 3.2 Environment Variables

```env
# .env
QB_CLIENT_ID=ABc123...your_client_id
QB_CLIENT_SECRET=xyz789...your_client_secret
QB_REDIRECT_URI=http://localhost:8090/api/v1/integrations/quickbooks/callback
QB_ENVIRONMENT=sandbox   # sandbox | production
```

### 3.3 OAuth Flow

```
Admin clicks "Connect QuickBooks"
        │
        ▼
GET /api/v1/integrations/quickbooks/connect
        │
        ├── Generates CSRF state token (stored in-memory, 10-min TTL)
        ├── Returns Intuit OAuth URL
        │
        ▼
Frontend redirects to Intuit OAuth consent page
        │
        ▼
User authorizes → Intuit redirects back with code + state + realmId
        │
        ▼
GET /api/v1/integrations/quickbooks/callback?code=...&state=...&realmId=...
        │
        ├── Validates CSRF state (single-use)
        ├── Exchanges code for tokens (POST to Intuit token endpoint)
        ├── Encrypts tokens with Fernet (derived from SECRET_KEY)
        ├── Fetches company info from QB API
        ├── Upserts QBConnection record
        │
        ▼
Connection established → ready for mapping + sync
```

### 3.4 Token Lifecycle

| Token | Lifetime | Handling |
|-------|----------|---------|
| Access Token | ~60 minutes | Auto-refreshed with 5-minute buffer before expiry |
| Refresh Token | ~100 days (rolling) | Each use extends by 100 days. Stored encrypted. |

If the refresh token expires (user doesn't use the system for 100+ days):
- Connection marked `is_active=False`
- User must re-authorize via OAuth

### 3.5 Token Security

- Tokens encrypted at rest with **Fernet symmetric encryption**
- Encryption key derived from `SECRET_KEY` via `SHA-256 → base64`
- All workers share the same `SECRET_KEY`, so any worker can decrypt
- If `SECRET_KEY` changes, all existing tokens become unreadable → user must reconnect

---

## 4. The Template System

### 4.1 What Templates Do

When a client connects QuickBooks, instead of manually creating 20-35 accounts one by one, the admin selects a template and presses one button. The template:

1. **Creates accounts** in QuickBooks (if they don't exist)
2. **Saves mappings** locally (POS concept → QB account)
3. **Sets defaults** (which account to use when no specific mapping exists)

### 4.2 Template Architecture

Templates are composed from **reusable building blocks**, not monolithic definitions:

```python
# Building blocks (composable pieces)
_PAK_PUNJAB_TAX = [FBR GST 17%, PRA PST 16%]
_PAK_MOBILE     = [JazzCash, Easypaisa settlements]
_BASE_BANK      = [Cash Register, Bank Account for Card]
_BASE_EXPENSE   = [Discount Given, Rounding Adjustment]
_BASE_LIABILITY = [Tips Payable, Gift Card Liability, Customer Deposits, Cash Over/Short]
_PAK_DELIVERY   = [Foodpanda Settlement, Delivery Expense, Rider Commission, Platform Commission]

# Cuisine-specific blocks
_PAKISTANI_INCOME = [Food Sales, Beverage, BBQ, Biryani, Karahi, Naan, Dessert, Takeaway, Delivery, Catering, Foodpanda]
_PAKISTANI_COGS   = [Food Cost, Beverage Cost, Packaging Cost]

# Compose a template from blocks
"pakistani_restaurant" = _t(
    name="Pakistani Restaurant (Full-Service)",
    income=_PAKISTANI_INCOME,
    cogs=_PAKISTANI_COGS,
    tax=_PAK_PUNJAB_TAX,
    bank=_BASE_BANK + _PAK_MOBILE,
    delivery=_PAK_DELIVERY,
    svc_charge=True,
)
```

This means:
- Adding a new template = 5-10 lines of code
- Changing tax for all Pakistani templates = edit one block
- Every template is self-contained when expanded

### 4.3 Mapping Types

Every mapping has a `mapping_type` that tells the sync engine what it's for:

| mapping_type | What It Maps | Example QB Account |
|---|---|---|
| `income` | Revenue from food/beverage sales | "Food Sales" (Income) |
| `cogs` | Cost of goods sold | "Food Cost" (COGS) |
| `tax_payable` | Tax collected from customers | "FBR GST Payable" (Other Current Liability) |
| `bank` | Where money sits | "Cash Register" (Bank) |
| `expense` | Operating costs | "Rider Commission" (Expense) |
| `discount` | Contra-revenue for promotions | "Discount Given" (Income, contra) |
| `rounding` | Cash rounding differences | "Rounding Adjustment" (Expense) |
| `cash_over_short` | Drawer count discrepancies | "Cash Over/Short" (Expense) |
| `tips` | Tips collected for staff | "Tips Payable" (Liability) |
| `gift_card_liability` | Unredeemed gift cards | "Gift Card Liability" (Liability) |
| `service_charge` | Mandatory service charge | "Service Charge Revenue" (Income) |
| `delivery_fee` | Delivery operations cost | "Delivery Expense" (Expense) |
| `foodpanda_commission` | Platform commission deducted | "Platform Commission" (Expense) |
| `other_current_liability` | Deposits, prepayments | "Customer Deposits" (Liability) |

### 4.4 Required Defaults

The sync engine requires these mapping types to have a default (is_default=True):

1. `income` — where to book revenue
2. `cogs` — where to book food cost
3. `tax_payable` — where to book collected tax
4. `bank` — where cash payments go
5. `discount` — where discounts are recorded
6. `rounding` — where rounding differences go
7. `cash_over_short` — where drawer discrepancies go

The validation endpoint (`POST /mappings/validate`) checks all of these.

---

## 5. Account Mapping — How It Works

### 5.1 Two-Level Lookup

```
Order Item: "Chicken Biryani" (category: Biryani & Rice)
        │
        ▼
Step 1: Check category-specific mapping
        pos_reference_type = "category"
        pos_reference_id   = <biryani_category_uuid>
        mapping_type       = "income"
        │
        ├── Found? → Use "Biryani & Rice Sales" account
        │
        └── Not found?
                │
                ▼
Step 2: Fall back to default income mapping
        mapping_type = "income"
        is_default   = True
        │
        └── Use "Food Sales" account (catch-all)
```

### 5.2 Smart Default Application

When applying a template:

```
For each mapping in template:
  1. Check if mapping already exists (type + name dedup)
     → Skip if exists
  2. Search QB for matching account (by name, prefer matching type)
     → Found? Use existing account
     → Not found + auto_create=True? Create it via QB API
     → Not found + auto_create=False? Skip
  3. Save QBAccountMapping record locally
```

### 5.3 Single-Default Invariant

At most **one** mapping per `mapping_type` can be `is_default=True`. When promoting a new default, the old one is automatically demoted.

---

## 6. Entity Mapping — POS to QB Linkage

Entity mappings link individual POS records to their QB counterparts:

| POS Entity | QB Entity | Example |
|---|---|---|
| Menu Item | Item (Service) | "Chicken Biryani" → QB Item #42 |
| Category | Class | "BBQ" → QB Class "BBQ & Grill" |
| Customer | Customer | "Walk-In" → QB Customer "Walk-In Customer" |
| Tax Rate | TaxCode | FBR 17% → QB TaxCode "GST-17" |
| Payment Method | PaymentMethod | "Cash" → QB PaymentMethod "Cash" |
| Vendor | Vendor | "Meat Supplier" → QB Vendor "ABC Meats" |

**Drift detection**: Each mapping stores a `sync_hash` (SHA-256 of the last synced state). On subsequent syncs, if the hash differs, the entity is re-synced.

---

## 7. Sync Engine — What Gets Synced

### 7.1 Sync Types (What Happens When)

| POS Event | QB Action | QB Entity Created |
|---|---|---|
| Customer pays and leaves | `create_sales_receipt` | **Sales Receipt** |
| Manager voids an order | `create_credit_memo` | **Credit Memo** |
| Cash refund issued | `create_refund_receipt` | **Refund Receipt** |
| End of day close | `create_journal_entry` | **Journal Entry** (daily summary) |
| End of day close | `create_deposit` | **Deposit** (cash+card to bank) |
| New menu item added | `sync_item` | **Item** (Product/Service) |
| Corporate credit order | `create_invoice` | **Invoice** |
| Invoice payment received | `create_payment` | **Payment** |
| Catering quote sent | `create_estimate` | **Estimate** |
| Supplier invoice received | `create_bill` | **Bill** |
| Supplier paid | `create_bill_payment` | **Bill Payment** |
| Ingredient ordered | `create_purchase_order` | **Purchase Order** |
| Cash moved to bank | `create_transfer` | **Transfer** |

### 7.2 Currency Handling

```
POS: Integer paisa (1 PKR = 100 paisa)
QB:  Decimal strings ("150.00")

Conversion: paisa_to_decimal(15000) → "150.00"
```

All monetary values in the POS are stored as integer paisa. The sync engine converts to decimal strings for every QB API call using `ROUND_HALF_UP`.

### 7.3 Sales Receipt Structure

When an order is completed, the sync engine builds a Sales Receipt:

```json
{
  "CustomerRef": {"value": "walk_in_customer_qb_id"},
  "TxnDate": "2024-01-15",
  "PrivateNote": "POS Order #240115-001 | Dine-In | Table 5",
  "Line": [
    {
      "Amount": 450.00,
      "Description": "Chicken Biryani x2",
      "DetailType": "SalesItemLineDetail",
      "SalesItemLineDetail": {
        "ItemRef": {"value": "biryani_qb_item_id"},
        "Qty": 2,
        "UnitPrice": 225.00
      }
    },
    {
      "Amount": 76.50,
      "Description": "FBR GST 17%",
      "DetailType": "SalesItemLineDetail",
      "SalesItemLineDetail": {
        "ItemRef": {"value": "tax_item_id"}
      }
    }
  ],
  "DepositToAccountRef": {"value": "cash_register_qb_id"}
}
```

### 7.4 Daily Close (Journal Entry + Deposit)

At end of day, the sync engine creates:

1. **Journal Entry** — Summarizes all revenue, COGS, tax, discounts
2. **Deposit** — Records cash and card settlements to bank

### 7.5 Job Queue & Retry

- Jobs are queued with priority (0=immediate, 5=normal, 10=bulk)
- Failed jobs retry with exponential backoff (up to `max_retries`, default 3)
- After max retries → status moves to `dead_letter` for manual review
- `idempotency_key` prevents duplicate syncs for the same event
- Admin can manually retry dead-letter jobs via API

---

## 8. API Endpoints Reference

All endpoints under: `/api/v1/integrations/quickbooks/`

### OAuth Flow
| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/connect` | Admin | Generate OAuth authorization URL |
| GET | `/callback` | User | Handle Intuit OAuth redirect |
| GET | `/status` | User | Check connection status |
| POST | `/disconnect` | Admin | Revoke tokens and deactivate |

### Company
| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/company` | User | Fetch live company info from QB |

### Account Mappings (Chart of Accounts)
| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/mappings` | User | List all mappings (filter by type) |
| POST | `/mappings` | Admin | Create a new mapping |
| PATCH | `/mappings/{id}` | Admin | Update a mapping |
| DELETE | `/mappings/{id}` | Admin | Delete a mapping |
| POST | `/mappings/validate` | User | Check if required mappings exist |
| GET | `/mappings/templates` | User | List available templates |
| POST | `/mappings/smart-defaults` | Admin | Apply a template |

### QB Account Discovery
| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/accounts` | User | Fetch QB Chart of Accounts for mapping wizard |

### Entity Mappings
| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/entity-mappings` | User | List POS↔QB entity links |

### Sync Operations
| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/sync` | Admin | Trigger manual sync |
| GET | `/sync/stats` | User | Aggregated sync statistics |
| GET | `/sync/jobs` | User | List sync queue jobs |
| GET | `/sync/log` | User | Audit trail of QB API calls |
| POST | `/sync/jobs/{id}/retry` | Admin | Retry a failed job |

### Manual Sync Types
```json
{
  "sync_type": "full_sync | sync_items | sync_customers | sync_orders | daily_summary",
  "date_from": "2024-01-01T00:00:00Z",
  "date_to": "2024-01-31T23:59:59Z",
  "entity_ids": ["uuid1", "uuid2"]
}
```

---

## 9. Environment Configuration

### Required Variables

```env
# QuickBooks OAuth
QB_CLIENT_ID=your_intuit_client_id
QB_CLIENT_SECRET=your_intuit_client_secret
QB_REDIRECT_URI=http://localhost:8090/api/v1/integrations/quickbooks/callback
QB_ENVIRONMENT=sandbox

# Security (CRITICAL: used for token encryption)
SECRET_KEY=your-production-secret-key
```

### QB Environment Options

| Value | API Base URL | Use For |
|-------|-------------|---------|
| `sandbox` | `sandbox-quickbooks.api.intuit.com` | Development & testing |
| `production` | `quickbooks.api.intuit.com` | Live client data |

### Intuit URLs (auto-configured)

| Purpose | URL |
|---------|-----|
| OAuth Authorization | `https://appcenter.intuit.com/connect/oauth2` |
| Token Exchange | `https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer` |
| Token Revocation | `https://developer.api.intuit.com/v2/oauth2/tokens/revoke` |
| API (Sandbox) | `https://sandbox-quickbooks.api.intuit.com/v3/company/{realmId}` |
| API (Production) | `https://quickbooks.api.intuit.com/v3/company/{realmId}` |

---

## 10. Client Onboarding Playbook

### Step-by-Step: New Client Setup

```
Step 1: Admin connects QuickBooks
        └── Click "Connect QuickBooks" → authorize on Intuit

Step 2: Select template
        └── "What type of restaurant are you?"
            └── Choose from 40 templates

Step 3: Apply smart defaults
        └── POST /mappings/smart-defaults
            body: { "template": "pakistani_restaurant", "auto_create_accounts": true }
            └── Creates ~25-35 QB accounts automatically
            └── Maps each to POS accounting concepts

Step 4: Validate mappings
        └── POST /mappings/validate
            └── Checks all 7 required types have defaults
            └── Flags any missing or empty mappings

Step 5: (Optional) Customize
        └── Map specific categories to specific income accounts
            e.g., "BBQ" category → "BBQ & Grill Sales" QB account
        └── Add category-specific income tracking for P&L detail

Step 6: Start syncing
        └── Orders auto-sync on completion
        └── Daily close generates summary journal entries
```

### The Sales Pitch

> "Click this link, authorize your QuickBooks, select your restaurant type, and your POS books itself. Every sale, every void, every tax rupee — automatically recorded. Your accountant goes from 4 hours of data entry to 10 minutes of review. We support Pakistani tax (FBR + PRA) out of the box, with 40 pre-built accounting structures for every type of restaurant."

---

## 11. Template Catalog

### Pakistani Cuisine (8 templates)

| # | Template Key | Name | Mappings | Tax | Key Features |
|---|---|---|---|---|---|
| 1 | `pakistani_restaurant` | Pakistani Restaurant (Full-Service) | 31 | FBR+PRA | BBQ, Karahi, Biryani, Naan, Dessert. JazzCash/Easypaisa. Foodpanda. Service charge. |
| 2 | `pakistani_bbq_specialist` | Pakistani BBQ & Tikka House | 28 | FBR+PRA | Tikka, sajji, seekh. Charcoal COGS. Dawat catering. Takeaway-dominant. |
| 3 | `biryani_house` | Biryani House / Rice Specialist | 27 | FBR+PRA | Biryani, pulao. 60%+ takeaway. Bulk rice procurement. Delivery-heavy. |
| 4 | `pakistani_street_food` | Pakistani Street Food / Dhaba | 19 | FBR+PRA | Chaat, gol gappay, roll paratha. Cash-heavy. Low overhead. |
| 5 | `nihari_paye_house` | Nihari & Paye House | 21 | FBR+PRA | Nihari, paye, haleem. Morning specialty. Single-category focus. |
| 6 | `pakistani_sweets_bakery` | Pakistani Sweets & Bakery | 26 | FBR+PRA | Mithai, bakery, nimko. Retail + wholesale. Eid seasonal spikes. |
| 7 | `karachi_seafood` | Karachi Seafood Restaurant | 25 | FBR+SRB | Fish, prawn, crab. **Sindh tax** (SRB 13%). Market-price COGS. |
| 8 | `lahore_food_street` | Lahore Food Street | 27 | FBR+PRA | Multi-station: BBQ, karahi, fry, dessert. High foot traffic. |

### International Cuisine (8 templates)

| # | Template Key | Name | Mappings | Tax | Key Features |
|---|---|---|---|---|---|
| 9 | `international_restaurant` | International Restaurant | 28 | VAT | Continental/fusion. Wine & bar. Tip income. Service charge. |
| 10 | `chinese_restaurant` | Chinese / Pakistani-Chinese | 26 | FBR+PRA | Manchurian, chowmein, fried rice. Delivery-heavy. |
| 11 | `pizza_chain` | Pizza Chain / Pizzeria | 25 | Generic | Pizza, sides, combos. Cheese/dough COGS. 50%+ delivery. |
| 12 | `burger_joint` | Burger Joint / American | 25 | Generic | Burgers, fries, shakes. Combo meals. Patty COGS dominant. |
| 13 | `steakhouse` | Steakhouse / Grill | 21 | VAT | Premium/imported beef. Wine pairings. Private dining. Service charge. |
| 14 | `japanese_sushi` | Japanese / Sushi | 23 | VAT | Sushi, ramen, tempura. Imported fish COGS. Bento boxes. |
| 15 | `thai_restaurant` | Thai Restaurant | 24 | VAT | Curries, pad thai, tom yum. Coconut/lemongrass COGS. |
| 16 | `italian_restaurant` | Italian / Trattoria | 25 | VAT | Pasta, wood-fire pizza, wine. Imported cheese/olive oil. Service charge. |

### Format / Model Types (10 templates)

| # | Template Key | Name | Mappings | Tax | Key Features |
|---|---|---|---|---|---|
| 17 | `qsr` | Quick Service Restaurant | 25 | Generic | Counter, drive-through, delivery. Combo meals. High volume. |
| 18 | `cafe` | Cafe / Coffee Shop | 23 | Generic | Coffee, pastries, light meals. Retail merchandise. |
| 19 | `fine_dining` | Fine Dining | 22 | VAT | Tasting menus, wine pairings, sommelier. Corkage fee. Private rooms. |
| 20 | `buffet_restaurant` | Buffet Restaurant | 19 | Generic | Per-head pricing. Multiple stations. Food waste COGS. |
| 21 | `food_court_vendor` | Food Court Vendor | 16 | Generic | Mall stall. Mall rent/commission expense. No delivery. |
| 22 | `cloud_kitchen` | Cloud Kitchen / Ghost Kitchen | 25 | Generic | Delivery-only, multi-brand. Per-brand revenue tracking. |
| 23 | `food_truck` | Food Truck / Mobile Kitchen | 17 | Generic | Mobile. Event/festival revenue. Fuel expense. Permit fees. |
| 24 | `catering_company` | Catering Company | 20 | Generic | Events-only. Per-head pricing. Equipment rental. Hired staff. |
| 25 | `hotel_restaurant` | Hotel Restaurant | 24 | VAT | Multi-outlet. Room service. Banquet. Minibar. Room charge posting. |
| 26 | `bar_lounge` | Bar & Lounge | 22 | VAT | Alcohol-primary. Hookah. DJ/entertainment. Cover charge. VIP. |

### Specialty (8 templates)

| # | Template Key | Name | Mappings | Tax | Key Features |
|---|---|---|---|---|---|
| 27 | `juice_bar` | Juice Bar / Smoothie Shop | 22 | Generic | Fresh produce, high perishability. Subscription revenue. |
| 28 | `ice_cream_parlor` | Ice Cream / Gelato / Kulfi | 19 | Generic | Scoops, sundaes, shakes. Take-home tubs. Seasonal demand. |
| 29 | `bakery_wholesale` | Bakery (Wholesale + Retail) | 19 | Generic | B2B wholesale + retail counter. Custom cakes. Seasonal items. |
| 30 | `breakfast_spot` | Breakfast / Nashta Spot | 20 | FBR+PRA | Halwa puri, paratha, nihari. Morning hours only. Cash-dominant. |
| 31 | `dessert_parlor` | Dessert Parlor / Sweet Cafe | 21 | Generic | Waffles, crepes, cheesecake. Instagram-driven delivery. |
| 32 | `tea_house` | Tea House / Chai Cafe | 17 | FBR+PRA | Doodh patti, kashmiri chai. Light snacks. High margin. |
| 33 | `shawarma_wrap_shop` | Shawarma & Wrap Shop | 24 | FBR+PRA | Shawarma, doner, wraps. Late-night hours. Delivery-heavy. |
| 34 | `fried_chicken_chain` | Fried Chicken Chain | 24 | Generic | Fried chicken, family buckets, kids meals. Frying oil COGS. |

### Business Complexity (6 templates)

| # | Template Key | Name | Mappings | Tax | Key Features |
|---|---|---|---|---|---|
| 35 | `multi_branch_chain` | Multi-Branch Chain (10+) | 35 | FBR+PRA | Branch-level tracking via QB Classes. Central kitchen. Inter-branch transfers. |
| 36 | `franchise_operation` | Franchise Operation | 29 | FBR+PRA | Royalty fees (5-8%). Marketing fund (2-3%). Brand license. |
| 37 | `multi_brand_operator` | Multi-Brand Operator (3+) | 27 | Generic | Multiple brands, shared infrastructure. Per-brand P&L. |
| 38 | `subscription_meal_service` | Subscription Meal / Tiffin | 18 | Generic | Weekly/monthly plans. Deferred revenue. Route delivery. Corporate. |
| 39 | `marketplace_heavy` | Marketplace-Heavy (60%+) | 27 | FBR+PRA | Multi-platform commission tracking. Per-platform settlement accounts. |
| 40 | `resort_restaurant` | Resort / Club Restaurant | 23 | UAE VAT | Pool bar, beach restaurant, room service. All-inclusive packages. Multi-currency. |

### Tax Jurisdictions Covered

| Region | Tax | Templates Using It |
|--------|-----|-------------------|
| Punjab, Pakistan | FBR GST 17% + PRA PST 16% | #1-6, #8, #10, #30, #32-33, #35-36, #39 |
| Sindh, Pakistan | FBR GST 17% + SRB SST 13% | #7 |
| KPK, Pakistan | FBR GST 17% + KPRA 15% | (available as block, not default) |
| Islamabad, Pakistan | FBR GST 17% only | (available as block, not default) |
| UAE | VAT 5% + Tourism Dirham | #40 |
| Saudi Arabia | VAT 15% | (available as block, not default) |
| International (VAT) | Standard + Reduced rate | #9, #13-16, #19, #25-26 |
| Generic | Configurable sales tax | #11-12, #17-18, #20-24, #27-29, #31, #34, #37-38 |

### Payment Methods Covered

| Method | Templates |
|--------|-----------|
| Cash Register | All 40 |
| Bank (Card Settlements) | All 40 |
| JazzCash Settlement | Pakistani templates (#1-8, #10, #17, #30, #32-33, #35-36, #39) |
| Easypaisa Settlement | Pakistani templates (same as above) |
| Online Payment (Stripe/Square) | International + format templates (#9, #11-16, #18-19, #22, #24-29, #31, #34, #37-38, #40) |
| Foodpanda Settlement | Templates with delivery (#1-3, #6-8, #10) |
| Multi-platform (Foodpanda + Cheetay + UberEats) | #39 (marketplace-heavy) |

---

## 12. Troubleshooting

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| "QB is not configured" (503) | Missing `QB_CLIENT_ID` or `QB_CLIENT_SECRET` | Set env vars in `.env` |
| "Invalid or expired state token" | OAuth took too long (>10 min) or double-click | Retry the connect flow |
| "Failed to decrypt token" | `SECRET_KEY` changed since connection was made | User must reconnect QB |
| "Refresh token expired" | User hasn't synced in 100+ days | User must reconnect QB |
| Template not found | Wrong template key | Use `GET /mappings/templates` to see available keys |
| "QB Fault code 6240" | Duplicate name in QB Chart of Accounts | Account already exists — check QB manually |
| Sync job stuck in "processing" | Worker crashed mid-job | Job will auto-retry after `next_retry_at` |
| Dead letter job | Failed 3+ times | Check `error_message`, fix root cause, then `POST /sync/jobs/{id}/retry` |

### Validation Checklist

Before going live with a client, run:

```bash
# 1. Check connection is active
GET /api/v1/integrations/quickbooks/status
→ is_connected: true

# 2. Validate all required mappings exist
POST /api/v1/integrations/quickbooks/mappings/validate
→ is_valid: true, missing_required: []

# 3. Check QB accounts were created
GET /api/v1/integrations/quickbooks/accounts
→ Should see all template accounts in the list

# 4. Test a sync
POST /api/v1/integrations/quickbooks/sync
body: { "sync_type": "sync_orders", "entity_ids": ["one_test_order_uuid"] }
→ jobs_created: 1

# 5. Check sync log
GET /api/v1/integrations/quickbooks/sync/log
→ Last entry should show status: "success"
```

### QB API Minor Version

The client pins to **minor version 73** (`QB_API_MINOR_VERSION = 73`). This is set in `client.py` and sent as a query parameter on every API call. Update this if Intuit deprecates the version.

---

## Stats

- **40 templates** covering every restaurant type
- **939 total account mappings** across all templates
- **5 database tables** for complete QB state management
- **18 API endpoints** for OAuth, mappings, sync, and diagnostics
- **14 QB entity types** supported by the client (Sales Receipt, Invoice, Payment, Credit Memo, Refund Receipt, Journal Entry, Deposit, Estimate, Bill, Bill Payment, Purchase Order, Transfer, Vendor Credit, Class)
- **8 tax jurisdictions** pre-configured (Punjab, Sindh, KPK, Islamabad, UAE, Saudi, International VAT, Generic)
