# PR: P0-P2 Feature Bundle — Sessions, Discounts, Approvals

## Summary
Implements the P0-P2 feature bundle from the BWL 3rd March review: receipt polish, payment preview, void hardening, table sessions, discount engine, consolidated session payments, discount reporting, and manager approval workflow.

**6 commits** | **4 migrations** | **24+ new tests** | **213 total tests passing**

## Scope

### Included
- **P0**: Receipt modifier pricing fix (no +Rs. 0), table number/label visibility across Orders, Payment, and Receipt
- **P1-A**: Payment preview endpoint (dual cash/card totals), void re-auth with mandatory reason + password verification token
- **P1-B**: Table sessions (open/close/attach orders/bill summary), discount type CRUD, apply/remove discounts with receipt integration
- **P2-S1**: Consolidated session payment (full, split, partial) with oldest-first allocation
- **P2-S2**: Discount reporting in sales summary, Z-report, and CSV export
- **P2-S3**: Manager approval workflow — configurable percent/fixed thresholds, password re-auth for high-value discounts

### Excluded
- Payment gateway integration (future)
- Rider GPS tracking / delivery module
- Foodpanda API integration (stub only)
- FBR/PRA tax submission (stub only)
- Kitchen station assignment UI improvements

## Breaking Changes
- **Void API**: `POST /orders/{id}/void` now **requires** `reason` field (min 1 char). Callers sending empty body will get 422.
- **Report schemas**: `SalesSummary` and `ZReport` responses now include additional fields (`total_discount`, `net_revenue`, `discount_breakdown`). Additive — no fields removed.

## Migration Instructions

```bash
# From project root, inside backend container:
alembic upgrade head

# This applies 4 new migrations in sequence:
# h4i5j6k7l8m9 — payment mode tax rates
# i5j6k7l8m9n0 — table sessions
# j6k7l8m9n0o1 — discount engine
# k7l8m9n0o1p2 — discount approval thresholds
```

**New tables**: `table_sessions`, `discount_types`, `order_discounts`
**Modified tables**: `restaurant_configs` (+4 columns), `orders` (+2 columns: `table_session_id`, `discount_amount`)

## Test Evidence

| Check | Result |
|-------|--------|
| Alembic migrations to head | PASS |
| Backend tests (213 total) | **213 passed, 0 failed** |
| TypeScript check (`tsc --noEmit`) | PASS (clean) |
| Frontend production build (`vite build`) | PASS (2.25s) |
| P0 code inspection (modifier prices, table visibility) | PASS (3/3 criteria) |
| P1-A code inspection (payment preview, void re-auth) | PASS (2/2 criteria) |
| P1-B code inspection (sessions, discounts, receipt) | PASS (4/4 criteria) |
| P2 code inspection (session pay, reports, approval) | PASS (3/3 criteria) |

### New test files
- `test_p1a_features.py` — 12 tests (payment preview, void hardening, verify-password)
- `test_p1b_table_sessions.py` — 10+ tests (open, idempotent, bill summary, close)
- `test_p1b_discounts.py` — 13+ tests (CRUD, apply, remove, stacking, validation)
- `test_p2_session_payments.py` — 11 tests (full/split/partial, overpay, closed session)
- `test_p2_discount_reports.py` — 14+ tests (aggregation, API structure, CSV)
- `test_p2_discount_approval.py` — 12+ tests (threshold logic, token validation, config)

## UAT Checklist

- Previous UAT: 98/99 PASS (99%) — see `UAT_CHECKLIST.md`
- Only prior failure: UAT-093 (duplicate email crashes page) — pre-existing, not in P0-P2 scope
- P0-P2 features verified via targeted code inspection (Step 3 of release readiness)
- Full details: `docs/RELEASE_NOTES_P0_P2_2026-03-03.md`

## Commits

```
8c5baef P0: receipt modifier pricing and table visibility in orders/payment
d88e308 P1-A: payment preview and void re-auth hardening
b28571a P1-B: table sessions and discount engine
b76bb83 P2-Slice 1: consolidated session payment
fe54149 P2-Slice 2: discount reporting in sales summary, z-report, and CSV
552e343 P2-Slice 3: discount approval workflow with manager verify token
```

## Diff Stats
- **183 files changed** (includes all prior phases on branch)
- **P0-P2 specific**: ~30 files, ~2,500 lines added
