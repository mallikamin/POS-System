# Pause Checkpoint — 2026-09-06

## Project
- **Name**: Restaurant POS System (Sitara Infotech)
- **Path**: `C:\Users\Malik\desktop\pos-project`
- **Branch**: `main`, all this session's work committed AND pushed (head `df461b5`)
- **Client in focus**: FZ LLC, Martin Zubeldia, tenant `martin-fz` on https://eats.sitaratech.info

## Goal
Martin sent four more WhatsApp messages on 2026-09-06 with five new asks. Build all of them,
consolidate every piece of feedback he has ever given into one place, verify the whole set
against the live API, then walk a step-by-step UAT with Malik and reply to Martin once with
everything confirmed.

## Completed
- [x] Consolidated all of Martin's feedback into three dated files under
      `_context/clients/fz-llc-uae/`: round 1 (M1-M7), round 2 (M8), round 3 (M9-M13, new).
- [x] **M9 Production**: preview + run history + a real menu entry. The engine already
      existed; it had no menu entry, no history and asked for "batches" not an amount.
- [x] **M10 Expenses**: four new tables, categories, PDF/photo invoice attachments on an
      authenticated route, period totals. Nothing in it touches stock.
- [x] **M11 Ingredient categories**: master list, dropdown with inline add, rename that moves
      the ingredients with it, delete refused while in use, case-insensitive matching.
- [x] **M12 Mobile**: zoom unlocked, 15 tables given working scrollers, the three till screens
      stack on a phone with the cart as a bottom sheet.
- [x] **M13 Direct sale**: `fulfilment_mode` on the order; "direct" completes, prints and
      deducts at once. Refused in pay-first mode.
- [x] Migration `f6a7b8c9d0e1` written, run and reversed on real Postgres 16 locally.
- [x] `backend/tests/test_martin_round3.py`, 25 route-level tests, green. 1009 green overall.
- [x] Deployed at `b4505fa`, verified on the production database read-only.
- [x] **All twelve of Martin's asks re-checked over the real API on production.** Record:
      `_context/clients/fz-llc-uae/API_VERIFICATION_2026-09-06.md`.
- [x] UAT script written: `_context/clients/fz-llc-uae/UAT_FZ_LLC_2026-09-06.md`, 43 steps.

## In Progress
- [ ] **Nothing is mid-edit.** The build is finished, deployed and pushed.

## Pending
- [ ] **Walk the 43-step UAT with Malik, ONE STEP PER MESSAGE.** Script is
      `_context/clients/fz-llc-uae/UAT_FZ_LLC_2026-09-06.md`. It must be done on a laptop
      AND on a phone; steps 33-42 are phone-only and cannot be faked from a resized browser.
- [ ] Draft the single reply to Martin once UAT passes. The material is already written in
      the "What was built, item by item" section of the round-3 feedback file.
- [ ] Answer the two commercial follow-ups in that same reply: he wants a demo for his
      partners, and his partners prefer **a meeting in the Dubai office rather than a call**.
      Three rounds old now.
- [ ] Tell Martin two things about his own data: **Deliveroo is not set up** on his Sales
      Channels screen (the only one of his six missing), and **every channel is on 0%
      commission**, which makes the profitability report meaningless until he enters the real
      rates. Both are his data entry, not build gaps.

## Key Decisions
- **No `production_runs` table.** A run's two stock movements ARE the fact. A header row
  beside them would be a second version of it, free to disagree.
- **`ingredients.category` stays a string.** The new `ingredient_categories` table is the
  master list behind the dropdown, not a foreign key. Converting the column would mean
  rewriting every ingredient row on every tenant to close a usability gap.
- **Expenses never touch stock.** An ingredient purchase already lives in the purchase order
  and the goods receipt; duplicating it would double-count food cost in every report.
- **`amount_minor` is the whole invoice, `tax_minor` is the VAT inside it.** That is how a UAE
  invoice reads. Enforced in the service and again by a CHECK constraint.
- **A direct sale is refused in pay-first mode**, not quietly reinterpreted, because payment
  is what releases an order there.
- **The zoom lock came off.** `user-scalable=no` was right for a till and wrong for the admin
  portal. `touch-action: manipulation` on controls still kills double-tap zoom.
- **Draft expenses are excluded from every total.** A half-entered invoice is not money owed.

## Files Modified
Committed and pushed across four commits: `80a3ad3` (backend), `dc446a8` (frontend),
`b4505fa` (cart-sheet fix), `3818754` + `df461b5` (state and verification records).

- `backend/app/models/expense.py`, `schemas/expense.py`, `services/expense_service.py`,
  `api/v1/expenses.py` — the expenses module, all new.
- `backend/app/services/ingredient_category_service.py` — the M11 master list, new.
- `backend/app/models/inventory.py` — `IngredientCategory`.
- `backend/app/services/production_service.py` — `preview_production`, `list_production_runs`.
- `backend/app/services/stock_service.py` — `stock_on_hand`, a read-only balance lookup.
- `backend/app/services/order_service.py` — `OrderRuleError` and the `direct` branch.
- `backend/app/services/media_service.py` — `store_document`, PDF by magic bytes.
- `backend/alembic/versions/f6a7b8c9d0e1_martin_round3_expenses_categories.py` — four tables.
- `frontend/src/pages/admin/ProductionPage.tsx`, `ExpensesPage.tsx` — new screens.
- `frontend/src/components/admin/CategoryField.tsx`, `components/pos/MobileCartSheet.tsx` — new.
- `frontend/index.html`, `src/index.css` — the M12 viewport and table rules.
- 9 admin pages got table scrollers; the 3 till pages stack on a phone.

## Uncommitted Changes
Everything from THIS session is committed and pushed. What remains dirty in the tree belongs
to **other sessions and was deliberately left alone**:
- `backend/alembic/versions/b0c1d2e3f4a5_order_meta_pixel_fields.py` — untracked Meta pixel
  migration, **re-parented onto `f6a7b8c9d0e1`** so the local chain has one head. Not committed.
- `backend/app/services/public_order_service.py`, `models/order.py`, `api/v1/public.py`,
  `schemas/public_order.py`, `services/meta_capi.py` — the same Meta pixel work.
- A long tail of root-level docs and deleted old checkpoints, dirty before this session began.

## Errors & Resolutions
- FastAPI `AssertionError: Status code 204 must not have a response body` on the new delete
  routes → the existing pattern in this codebase passes `response_model=None` explicitly.
- The mobile cart sheet rendered its children twice, mounting two CartPanels and discarding
  anything typed into the sheet on close → rewritten to one instance that is never unmounted;
  only its positioning changes. Fixed in `b4505fa`.
- The first production verification reported 14 failures; **11 were the harness**, checking a
  schema at `/openapi.json` that production does not expose. Three more were mine: the 422
  body echoes the request so searching it for a field name always matches; the charges live on
  the order detail not the list row; the customer address field is `default_address`.
- The verification created a probe customer that could not be undone through the API, because
  **there is no DELETE endpoint for a customer by design** → removed from the production
  database directly after a `pg_dump` to
  `/root/backups/pre_zzprobe_cleanup_20260906_102857.sql`. `martin-fz` back to 0 customers,
  `chick-shack` untouched at 215.

## Critical Context
- 🔴 **NOTHING HAS BEEN CLICKED IN A BROWSER.** The database, the API and the shipped bundle
  are all verified. The pixels are not. Do not reply to Martin before the UAT is walked.
- **STEP-MODE IS ON for the UAT.** One step per message, one thing to report back, then stop
  and wait. No roadmap tables, no sub-steps, no multi-item report-back lists.
- Production head is `alembic_version = f6a7b8c9d0e1`. The live release symlink points at
  `releases/b4505fa...`.
- Deploying is `git push origin main`; CI builds the frontend and the box is shared with
  Chick Shack, a live business. Never build the frontend on the server, it OOMs at 2GB.
- The FZ admin login for the live tenant is in a file Malik pointed at in his Downloads
  folder. Referenced by path only. **Never echo it.**
- Martin's tenant currently holds 16 ingredients, 8 ingredient categories, 0 customers,
  0 expenses, 6 sales channels and 12 orders. Any UAT that creates data should be cleaned up
  or, better, done on data he can keep.
- Verification scripts from this session live in the session scratchpad under
  `C:\Users\Malik\AppData\Local\Temp\claude\C--Users-Malik-desktop-pos-project\...\scratchpad\`
  and are disposable.
