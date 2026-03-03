# Release Notes: P0-P2 Features
**Date**: 2026-03-03
**Branch**: `wip/BWL3rdMarchChanges`
**Base**: `main` (UAT baseline, 49e6dd3)

---

## Commits (6 total, grouped by phase)

### P0: Receipt & Table Visibility (`8c5baef`)
- **Receipt modifier pricing**: Zero-price modifiers no longer display "+Rs. 0" — only non-zero adjustments shown with signed formatting
- **Table visibility**: Table number/label now visible on Orders page (OrderCard with MapPin icon), Payment page (header), and printed receipt

### P1-A: Payment Preview & Void Hardening (`d88e308`)
- **Payment preview endpoint**: `GET /orders/{id}/payment-preview` returns dual totals (cash at 16% tax, card at 5% tax) based on configurable per-method tax rates
- **Void re-authentication**: Void now requires mandatory reason (1-500 chars) + password re-auth via `POST /auth/verify-password` (5-min JWT token)
- **DB migration**: `h4i5j6k7l8m9` — adds `cash_tax_rate_bps`, `card_tax_rate_bps` to `restaurant_configs`

### P1-B: Table Sessions & Discount Engine (`b28571a`)
- **Table sessions**: Open/close sessions per table, attach multiple orders, consolidated bill summary with paid/due tracking
- **Discount types CRUD**: Admin can create percent/fixed discount types with unique codes per tenant
- **Apply/remove discounts**: Discounts applied to orders or sessions, stacking supported, validation prevents exceeding subtotal
- **Receipt integration**: Discount lines rendered on receipt between tax and total
- **DB migrations**:
  - `i5j6k7l8m9n0` — creates `table_sessions` table + `table_session_id` FK on orders
  - `j6k7l8m9n0o1` — creates `discount_types` + `order_discounts` tables, adds `discount_amount` to orders

### P2-Slice 1: Consolidated Session Payment (`b76bb83`)
- **Session payment**: Pay entire table session in one transaction (full, split, or partial)
- **Oldest-first allocation**: Payment distributed across session orders by creation time
- **Endpoints**:
  - `GET /payments/table-sessions/{id}/summary` — session payment summary with per-order breakdown
  - `POST /payments/table-sessions/{id}/pay` — single-method payment
  - `POST /payments/table-sessions/{id}/split` — multi-method split payment
- **Frontend**: New `SessionPaymentPage` with cash/card/split modes, change calculation

### P2-Slice 2: Discount Reporting (`fe54149`)
- **Sales summary**: `total_discount`, `net_revenue`, `discount_breakdown[]` added to summary response
- **Z-Report**: Same fields added — discount breakdown by source type with count/total
- **CSV export**: Discount total row + net revenue row + per-type breakdown lines
- **Frontend**: Discount cards and breakdown table in ReportsPage

### P2-Slice 3: Discount Approval Workflow (`552e343`)
- **Threshold enforcement**: Configurable percent (basis points) and fixed (paisa) thresholds — if EITHER exceeded, manager approval required
- **Manager approval flow**: Uses same verify-password JWT pattern from P1-A; frontend shows manager password dialog when "approval_required" returned
- **Settings UI**: Admin can configure both thresholds in Settings page
- **DB migration**: `k7l8m9n0o1p2` — adds `discount_approval_threshold_bps`, `discount_approval_threshold_fixed` to `restaurant_configs`

---

## API Contract Additions/Changes

### New Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/orders/{id}/payment-preview` | Cash/card tax preview |
| POST | `/auth/verify-password` | Re-auth for sensitive actions |
| POST | `/table-sessions/open` | Open/resume table session |
| GET | `/table-sessions/{id}` | Get session details |
| GET | `/table-sessions/table/{table_id}/active` | Active session for table |
| GET | `/table-sessions/{id}/bill-summary` | Session bill with paid/due |
| POST | `/table-sessions/{id}/close` | Close session |
| GET | `/discounts/types` | List discount types |
| POST | `/discounts/types` | Create discount type (admin) |
| PATCH | `/discounts/types/{id}` | Update discount type (admin) |
| DELETE | `/discounts/types/{id}` | Delete discount type (admin) |
| POST | `/discounts/apply` | Apply discount to order/session |
| DELETE | `/discounts/{id}` | Remove discount |
| GET | `/discounts/orders/{order_id}` | List discounts on order |
| GET | `/payments/table-sessions/{id}/summary` | Session payment summary |
| POST | `/payments/table-sessions/{id}/pay` | Session payment |
| POST | `/payments/table-sessions/{id}/split` | Session split payment |

### Modified Endpoints
| Method | Path | Change |
|--------|------|--------|
| POST | `/orders/{id}/void` | Now requires `reason` (mandatory) + optional `auth_token` |
| GET | `/orders` | Response now includes `table_number`, `table_label` |
| GET | `/reports/summary` | Response adds `total_discount`, `net_revenue`, `discount_breakdown` |
| GET | `/reports/z-report` | Response adds `total_discount`, `net_revenue`, `discount_breakdown` |
| GET | `/reports/csv` | CSV adds discount + net revenue rows |
| PATCH | `/config/restaurant` | Accepts `discount_approval_threshold_bps`, `discount_approval_threshold_fixed` |
| GET | `/config/restaurant` | Response includes threshold fields |

---

## Database Migrations (in order)

| Migration | Description | New Tables | Modified Tables |
|-----------|-------------|------------|-----------------|
| `h4i5j6k7l8m9` | Payment mode tax rates | — | `restaurant_configs` (+2 cols) |
| `i5j6k7l8m9n0` | P1-B table sessions | `table_sessions` | `orders` (+FK) |
| `j6k7l8m9n0o1` | P1-B discount engine | `discount_types`, `order_discounts` | `orders` (+discount_amount) |
| `k7l8m9n0o1p2` | P2 discount approval | — | `restaurant_configs` (+2 cols) |

---

## Test Results Summary

| Suite | Count | Status |
|-------|-------|--------|
| Total backend tests | **213** | **All passing** |
| P1-A tests (`test_p1a_features.py`) | 12 | Pass |
| P1-B session tests (`test_p1b_table_sessions.py`) | 10+ | Pass |
| P1-B discount tests (`test_p1b_discounts.py`) | 13+ | Pass |
| P2 session payments (`test_p2_session_payments.py`) | 11 | Pass |
| P2 discount reports (`test_p2_discount_reports.py`) | 14+ | Pass |
| P2 discount approval (`test_p2_discount_approval.py`) | 12+ | Pass |
| TypeScript check | — | Clean |
| Frontend production build | — | Clean (2.25s) |

---

## Known Residual Risks

1. **SQLite date limitation in tests**: P2-S2 discount report tests use direct SQL aggregation instead of date-filtered API queries because SQLite's `CAST(ts AS DATE)` doesn't support date comparisons. Aggregation logic proven via direct queries; API structure verified separately. Full PostgreSQL integration proven via migration + production deploy.

2. **Pre-existing items** (not introduced by P0-P2):
   - Order number race condition under concurrency (advisory lock needed)
   - Dashboard `date.today()` uses server local time vs UTC
   - No UNIQUE constraint for single open cash drawer per tenant
   - AuditLog model missing FK on tenant_id (migration has it)

3. **`auth_token` optional on void**: Token is validated if provided but not strictly required by the API schema (frontend enforces it). This allows backwards compatibility but means API-only callers could void without re-auth if they have admin JWT.

---

## Rollback Notes

**Migration downgrade order** (reverse):
```bash
# Step 1: Revert P2 discount approval threshold
alembic downgrade k7l8m9n0o1p2-1  # removes threshold columns

# Step 2: Revert P1-B discount engine
alembic downgrade j6k7l8m9n0o1-1  # drops discount_types, order_discounts, discount_amount

# Step 3: Revert P1-B table sessions
alembic downgrade i5j6k7l8m9n0-1  # drops table_sessions, table_session_id FK

# Step 4: Revert P1-A payment mode tax rates
alembic downgrade h4i5j6k7l8m9-1  # removes tax rate columns
```

**Warning**: Rollback will lose any data in `table_sessions`, `discount_types`, and `order_discounts` tables. Back up before downgrading.

**Code rollback**: `git revert 552e343..8c5baef` or reset branch to pre-P0 commit (`d9b0e0d`).
