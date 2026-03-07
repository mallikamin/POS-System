# Pause Checkpoint — 2026-03-04

## Project
- **Name**: POS System (Restaurant POS)
- **Path**: C:\Users\Malik\desktop\POS-Project
- **Branch**: `main`

## Goal
Working through revised client checklist based on `docs/POS Upgrade.pdf` and `C:\Users\Malik\Downloads\POS.docx`. Currently on **Test #4** — multi-order table sessions: verifying table status reconciliation, session payments, and receipt rendering for split cash/card transactions.

## Completed
- [x] **Table status reconciliation fix** — tables were showing red/occupied after full payment. Root cause: reconciliation used OR logic (`NOT completed OR NOT paid`) instead of payment-centric logic. Changed to: table is occupied only if it has non-voided, non-completed orders that are NOT paid/refunded. Deployed + verified all tables green on live server.
- [x] **Auto-complete served+paid orders** — `_sync_order_payment_status` now auto-transitions dine-in orders from "served" to "completed" when fully paid, preventing stale table occupancy.
- [x] **Stale order cleanup** — 6 old test/seed orders (dating back to Feb 10) were stuck in non-terminal states on tables. Completed them via script on live server.
- [x] **Receipt: order number** — Changed from meaningless "SESSION-798f6e3c" to actual order numbers (comma-separated for multi-order sessions)
- [x] **Receipt: order grouping** — Items now grouped by order with `— Order #260304-001 —` headers for session receipts
- [x] **Receipt: payment consolidation** — Multiple per-order allocations (e.g., Cash 774 + Cash 726) now consolidated by method (Cash 1500)
- [x] **Receipt: per-method tax breakdown** — Split payments show "Cash Tax (16%)" and "Card Tax (5%)" with correct amounts instead of generic "GST (16%)". Fixed formula from `amount * rate / 10000` (wrong) to `amount - round(amount * 10000 / (10000 + rate))` (correct extraction from inclusive amounts)
- [x] **Receipt: payment detail** — Each payment method shows Pre-tax amount + Tax @ rate% breakdown
- [x] **Receipt: missing tax rates in session receipts** — Backend was not sending `cash_tax_rate_bps`/`card_tax_rate_bps` in session receipt data. Fixed.
- [x] **All tests passing**: 247/247 (full suite)
- [x] **All deployed to production**: 5/5 services healthy on pos-demo.duckdns.org

## In Progress
- [ ] **Client checklist Test #4** — multi-order table session testing. Table status and receipt fixes are done and deployed. User confirmed receipt works. **Continue with remaining test items in the checklist.**

## Pending
- [ ] Remaining client checklist tests (#5 onward) from `docs/POS Upgrade.pdf` and `C:\Users\Malik\Downloads\POS.docx`
- [ ] Commit all uncommitted changes (15 modified files, +1122/-186 lines)

## Key Decisions
- **Table occupancy = payment-centric**: A table is occupied if it has unsettled (unpaid) orders. Once paid, table frees regardless of kitchen pipeline status. This is simpler and correct for order-first mode (the restaurant's mode).
- **Auto-complete served+paid**: Dine-in orders auto-transition to "completed" when paid + served. Does NOT auto-complete in_kitchen/ready orders (kitchen pipeline should flow naturally through KDS).
- **Receipt tax extraction formula**: Tax from inclusive amounts uses `base = amount * 10000 / (10000 + rate)`, `tax = amount - base`. Previous formula was wrong.
- **Receipt payment consolidation**: Backend consolidates payments by method name before sending to frontend. Cleaner than frontend-side aggregation.

## Files Modified (this session)
### Backend
- `backend/app/services/floor_service.py` — Payment-centric table reconciliation logic
- `backend/app/services/payment_service.py` — Auto-complete served+paid dine-in orders
- `backend/app/services/receipt_service.py` — Session receipt: real order numbers, order labels on items, consolidated payments, cash/card tax rate fields
- `backend/app/schemas/receipt.py` — Added `order_label` field to `ReceiptItem`
- `backend/app/api/v1/floor.py` — (pre-existing change from earlier session)
- `backend/tests/test_table_status.py` — (pre-existing tests from earlier session)
- `backend/tests/test_payments.py` — (pre-existing tests from earlier session)
- `backend/tests/test_p2_session_payments.py` — (pre-existing tests from earlier session)

### Frontend
- `frontend/src/components/pos/ReceiptModal.tsx` — Order grouping with headers, per-method tax breakdown with correct formula, consolidated payment display with pre-tax/tax detail
- `frontend/src/pages/dine-in/DineInPage.tsx` — (pre-existing change)
- `frontend/src/pages/payment/PaymentPage.tsx` — (pre-existing change)
- `frontend/src/pages/payment/SessionPaymentPage.tsx` — (pre-existing change)
- `frontend/src/stores/floorStore.ts` — (pre-existing change)

## Uncommitted Changes
15 modified files, +1122/-186 lines on `main` branch. NOT committed. All changes are deployed to production but not in git yet.

## Errors & Resolutions
- **Tables stuck as red/occupied after payment** → Root cause: reconciliation OR logic treated served+paid orders as active. Fixed to payment-centric AND logic. Also cleaned up 6 stale seed orders on live server.
- **Receipt showing "SESSION-xyz"** → Changed to actual order numbers from the session's orders
- **Receipt GST(16%) on split payment** → Backend wasn't sending cash/card tax rates in session receipt. Added `cash_tax_rate_bps`/`card_tax_rate_bps` to session receipt return.
- **Receipt tax calculation wrong** → Formula `amount * rate / 10000` applies rate to inclusive amount (wrong). Fixed to `amount - round(amount * 10000 / (10000 + rate))`.

## Critical Context
- **Server**: 159.65.158.26 (SGP1), 5/5 services healthy, all fixes deployed
- **Tests**: 247/247 passing locally in Docker test runner
- **Client checklist**: Based on two docs: `docs/POS Upgrade.pdf` and `C:\Users\Malik\Downloads\POS.docx`
- **Test #4 PASSED** (multi-order table sessions) — user confirmed receipt works
- **Next**: Continue with remaining checklist tests. Also need to commit the 15 modified files.
- **Stale data cleaned**: Old seed/test orders on T1-T7/T30 were completed via script. If re-seeding, those will come back.
