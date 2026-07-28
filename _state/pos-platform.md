# POS platform state — core product

**Last updated:** 2026-07-27 (04:12 PKT). Status rows verified 2026-07-15; no code has landed since.

---

## Where the product stands

All 10 build phases complete and in production. **98/99 UAT pass** across 17 modules
(sessions 1-4). The single failure is UAT-093 — a duplicate email crashes the page instead of showing
a toast, logged as ENH-016.

| Area | Status |
|---|---|
| Core POS (10 phases) | ✅ Deployed |
| Auth, menu, floor plan, orders, KDS, payments, call centre, reports, admin | ✅ Complete |
| QuickBooks **Online** | ✅ Production live — real company connected, 19 account mappings |
| QuickBooks **Desktop** | ⏸️ Week 2 of 6 (~33%), **parked** |
| BOM / recipes | Phases 1-2 complete, Phase 3 (frontend) in progress |
| Multi-currency | ✅ Formatter fixed 2026-07-27; literal sweep still open |

### QuickBooks Online — sync is MANUAL by design

Sync works and has been tested end to end (order 260210-009, Rs. 1,044.00 → QB Sales Receipt #3).
**Auto-sync is not implemented.** The choice between auto / manual / scheduled batch is a pending
decision from the BPO World team, not a bug. When someone asks "why isn't QB syncing?", that is the
answer. See `docs/QB_SYNC_STATUS_2026-03-28.md`.

Note for the current client workstream: **Chick Shack UK explicitly refused any accounting
integration.** Our largest integration asset is worth nothing on that deal. Do not lead with it.

---

## ⚠️ Capability gap table — what the docs claim vs what the code does

Verified by reading the code, not the docs (2026-07-26). **Two client-facing documents currently
assert things the code does not do.** Either correct them or close the gap by building.

| Capability | Documented as | Actually in code |
|---|---|---|
| Thermal / receipt printing | `CLAUDE.md:20` — "thermal printer support, configurable per station" | ❌ **False.** Only `window.print()` + 80mm CSS (`ReceiptModal.tsx:100-131`). No ESC/POS, no network printer code, no print libs, no printer field on `KitchenStation`. |
| Kitchen printer routing | `CLAUDE.md:20` — "configurable per station" | ❌ Does not exist. KDS is screen-only. |
| Online ordering / website portal | `EXECUTIVE-SUMMARY-1PAGER.md:35` markets it as current | ❌ Roadmap only. **The same 1-pager, line 65, correctly puts it in Phase 3 — the two lines contradict each other.** Being built now for Chick Shack. |
| QR table ordering | `EXECUTIVE-SUMMARY-1PAGER.md:35` markets it as current | ❌ Does not exist. Grep for `qr` in `frontend/src` returns nothing. |
| Foodpanda / FBR / PRA | `CLAUDE.md` — "integration ready" | ⚠️ Stubs. Every method raises `NotImplementedError`. "Ready" is accurate only as "an adapter interface exists". |
| Offline mode | `MASTERPLAN.md:305` unchecked | ❌ No `navigator.onLine`, no IndexedDB, no queue. The app fails hard without a backend. |
| Cash drawer kick / barcode scanner / customer display | roadmap | ❌ Do not exist. |
| Multi-currency | config field existed, defaulted PKR | ✅ **Fixed 2026-07-27.** `currency.ts` is config-driven; `formatPKR` kept as a deprecated alias so all 140 call sites work untouched. |

⚠️ **Unknown whether the 1-pager has already gone to the UK prospect.** Malik to confirm.

### Genuinely true and defensible

A pure browser SPA — no native wrapper, no PWA (`frontend/index.html` has no manifest,
`vite.config.ts` has only the react plugin) — so it runs on Android, Windows and iOS browsers with
nothing to install. Touch targets are real (44/56/72 px, `tailwind.config.js:96-103`), though note
`CLAUDE.md:319` says a 48 px base while the code says 44 px.

### A real bug found in the currency work

The old `formatPKR` used `maximumFractionDigits: 0` — correct for PKR convention, but it would have
rendered **£8.50 as £9** on a live checkout. The rewrite separates two things that were conflated:

- `minorExponent` — minor units per major unit (100 paisa/rupee, 100 pence/pound). Arithmetic.
- `displayDecimals` — decimal places shown. PKR 0, GBP 2.

For PKR these differ, and using one for the other is a money bug. The table deliberately holds **PKR
and GBP only** — the two currencies this product actually serves. Do not speculatively add others.

---

## Architecture worth knowing before changing anything

- **Multi-tenant ready**: every table has a UUID PK + `tenant_id`.
- **Order state machine**: `draft → confirmed → in_kitchen → ready → served → completed`, plus
  `voided` from any state (manager only).
- **Currency is integer paisa** (1 PKR = 100 paisa). Never float.
- **Payment flow is configurable** — `order_first` or `pay_first`. In pay-first the kitchen does not
  fire until payment lands.
- **Database**: PostgreSQL 16, 33 tables. Redis 7 for pub/sub.
- Routes are thin; business logic lives in `services/`.

### Landmines documented in `ERROR_LOG.md` — read it before debugging

Recurring ones worth internalising:
- Audit/non-critical writes must use `begin_nested()` SAVEPOINT isolation, or a failed audit insert
  poisons the caller's transaction.
- Any new table using PostgreSQL-only types (JSONB, ARRAY) must be added to `_SKIP_TABLE_NAMES` in
  `backend/tests/conftest.py`, or the SQLite test suite breaks.
- Table occupancy is driven by **payment** status, not kitchen status.
- Stats must be computed from the **payments** table filtered by payment status — not from order
  totals filtered by order status — or partial payments and paid-but-in-kitchen orders are counted
  wrong.
- When extracting tax from a tax-inclusive amount:
  `base = amount * 10000 / (10000 + rate_bps)`, then `tax = amount - base`. The naive
  `amount * rate / 10000` double-counts.

### ⚠️ Structural auth weakness, still open

**There is no PIN-uniqueness constraint** at either the DB or app layer. `authenticate_by_pin`
(`backend/app/services/auth_service.py:52`) loops active tenant users and returns the **first bcrypt
match**. A PIN collision therefore logs someone into the wrong account, silently. This actually
happened (2026-07-15) and was fixed for the specific users involved, but the structural hole remains.
See `open-items.md`.
