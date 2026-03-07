# Pause Checkpoint — 2026-03-04 (Session C)

## Project
- **Name**: POS System (Restaurant POS)
- **Path**: C:\Users\Malik\desktop\POS-Project
- **Branch**: `main`

## Goal
Working through BWL client POS checklist (21 items). Testing implemented features end-to-end on live server (pos-demo.duckdns.org).

## Completed This Session
- [x] **Waiter name on order cards + receipts** (`be6c862`) — OrderCard shows waiter with user icon, ReceiptModal shows "Waiter: Name" line
- [x] **Table session auto-close fix** (`9b4161a`) — Per-order payments now auto-close table sessions when all orders paid. Previously only session payment endpoints closed sessions, causing stale sessions to aggregate when tables reused.
- [x] **Customer selector for Dine-In/Takeaway** (`96fd4c8`) — CartPanel now has expandable customer bar: defaults to "Walk-in Customer", phone search links existing customer records, manual name entry supported
- [x] **Walk-in customer sentinel** — Inserted into live DB (was missing — only created by seed script)
- [x] **Stale session cleanup** — Closed 6 orphaned open sessions and freed 3 occupied tables on live server
- [x] **Voided 3 test orders** (260304-006/007/008) to free T1/T2/T5
- [x] **247/247 tests passing**
- [x] **All deployed to production** — 5/5 services healthy

## Tests Completed (8 of 21)

### Test 1: Modifier/add-on prices on receipt — PASS
Modifiers show as separate lines with individual +/- prices on receipt.

### Test 2: Table number on order screen — PASS
Order cards show table number/label with MapPin icon.

### Test 3: Split cash/card payment on bill — PASS
Receipt shows both Cash and Card payment lines separately with per-method tax breakdown.

### Test 4: Dine-In table sessions (consolidated billing) — PASS
Multiple orders on same table → session payment page → combined total → table releases after full payment.

### Test 5: Dual totals + discount application — PASS
Cash vs Card preview totals visible before payment. Discounts reflected. Modifier prices itemized on receipt.

### Test 6: Void authorization flow — PASS
Mandatory reason (6A), mandatory password (6B), successful void with auth (6C), voided badge shown (6D).

### Test 7: Waiter assignment — PASS
Waiter dropdown on Dine-In (7A), waiter name on order card + receipt (7B), takeaway works without waiter (7C).

### Test 8: Customer profile / Walk-in default — PASS
Walk-in Customer default, phone search for existing customers, manual name entry, shown on receipt.

## Remaining Tests (9-21 from BWL Checklist)
Based on `docs/POS Upgrade.pdf` and `C:\Users\Malik\Downloads\POS.docx`:

- **Test 9**: Pay-first mode toggle — switch to pay_first in Settings, verify kitchen blocks without payment
- **Tests 10-21**: Remaining client checklist items (need to reference original docs for exact items)

## Recent Commits
```
96fd4c8 Add customer selector to dine-in/takeaway cart panel
9b4161a Auto-close table session when all orders paid via per-order payment
be6c862 Show waiter name on order cards and receipts
```

## Key Fixes This Session
- **Session auto-close**: `_sync_order_payment_status` in payment_service.py now calls `_maybe_close_session` when order is paid and has a table_session_id. Removed redundant close from `pay_session`/`split_session_payment` to avoid double-close errors.
- **Walk-in customer**: Sentinel record (phone=0000000000) was missing in live DB. Inserted directly. Backend logic at order_service.py:173-186 already handled lookup.
- **Customer selector**: CartPanel now imports `searchCustomers` from customerApi. Debounced phone search (300ms, 3+ chars). Selected customer's name/phone passed to createOrderFromCart. Defaults to Walk-in Customer if untouched.

## Files Modified This Session
### Backend
- `backend/app/services/payment_service.py` — `_maybe_close_session` helper + wired into `_sync_order_payment_status`, removed duplicate close from session payment endpoints
- `backend/app/services/receipt_service.py` — Added waiter_name to both order and session receipts
- `backend/app/schemas/receipt.py` — Added `waiter_name` field

### Frontend
- `frontend/src/components/pos/CartPanel.tsx` — Customer selector (phone search + manual name + Walk-in default)
- `frontend/src/components/pos/OrderCard.tsx` — Waiter name display with User icon
- `frontend/src/components/pos/ReceiptModal.tsx` — Waiter name + waiter_name in ReceiptData interface
- `frontend/src/types/order.ts` — Added waiter_id/waiter_name to OrderListItem

## Git State
- All committed and pushed to `main`
- No uncommitted code changes
- Production deployed and healthy

## Critical Context
- **Server**: 159.65.158.26 (SGP1), 5/5 services healthy
- **Tests**: 247/247 passing locally
- **Walk-in customer exists in live DB** — phone=0000000000
- **All stale sessions cleaned up** — no orphaned open sessions
- **Client checklist**: 21 items total, 8 tested and passed, 13 remaining
- **Next**: Test #9 (Pay-first mode) then continue through remaining checklist
