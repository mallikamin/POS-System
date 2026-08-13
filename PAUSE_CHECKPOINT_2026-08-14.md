# Pause Checkpoint — 2026-08-14 (~01:15 PK / ~21:15 UK 13 Aug)

## Project
- **Name**: Restaurant POS — Chick Shack UK online ordering channel
- **Path**: `C:\Users\Malik\desktop\pos-project`
- **Branch**: `main` · **HEAD** `fc1b03d` · ⚠️ **ONE UNPUSHED COMMIT** (see Critical Context)
- **Server**: at `2366c99` (the feature commit; the unpushed one is docs-only)
- **Storefront**: Cloudflare version `c8d8a9b6`

## Goal
Imran requested two checkout changes (via Malik, 2026-08-13): rename "Service Fee" to
"Platform Fee" everywhere, and add a tip option at checkout (£2/£4/£5/custom, card tips charged
with the order through Stripe, cash tips ride the bill for the rider). Malik added a third:
a Tips card on the revenue reports, split card vs cash. Registered as **OI-81**. All three were
built, tested, and deployed live the same day — during service, on Malik's explicit instruction
("deploy because we can have a live runtime experience").

## Completed
- [x] **Backend `2366c99`, deployed and verified on the server.** `orders.tip` column (migration
  `u7v8w9x0y1z2`, single head, applied live), `tip` on the public order schema validated 0..2000
  pence, included in `total`, never taxed, never counted toward the delivery minimum, snapshotted
  at creation. Its own "Tip" line on Stripe / printed ticket / emails; on unpaid tickets the
  COLLECT total includes it. "Platform Fee" rename on every surface; `service_fee` field names
  unchanged.
- [x] **Reports**: `prepaid-vs-cod` returns `prepaid_tips` / `cod_tips` under the same
  money-actually-taken rule as revenue (rule imported from `order_visibility`, not re-expressed);
  CSV gained Card/Cash/Total Tips rows; `/online-orders/reports` gained a Tips section
  (Total / Card / Cash tiles).
- [x] **Storefront** (Cloudflare `c8d8a9b6`): tip chips None/£2/£4/£5/Other + custom input with
  £20 cap message, no explanatory copy (Malik cut "100% goes to your rider" as redundant), total
  updates live, `tip` sent only when > 0. Platform Fee rename on checkout + confirmation.
- [x] **Tablet frontend**: Platform Fee label, Tip row on order cards (renders only when tip > 0).
  Verified in the SERVED chunk (`OnlineOrdersPage-CXjt_H5D.js`: "Platform Fee" 1, "Tip" 1,
  "Service Fee" 0), not just the green Action.
- [x] **Zero regressions, proven**: full suite 546 passed vs 536 on a clean-HEAD worktree at the
  same clock, identical 21 failures + 2 errors line-for-line both sides (parked QB-Desktop suite +
  OI-63 time-of-day set). +10 = the new tip/rename tests. Both frontends typecheck clean, ruff clean.
- [x] **Live verification**: server at `2366c99`, `orders.tip` present, alembic at head, container
  source greps clean, live menu API 200 GBP, live storefront bundle `index-CviMWmK5.js` has zero
  "Service Fee", 0 backend exceptions, 0 nginx 5xx, Orbit CRM untouched (2-3 months uptime).
- [x] **Found and fixed real git drift**: OI-78's storefront source (App.tsx retries, menu.ts
  loading state, connection copy) was live on Cloudflare since `f0d8764a` but NEVER committed —
  the 08-13 checkpoint's "committed" claim was wrong. `2366c99` commits it; git now matches
  production. ERROR_LOG.md entry written (with the rule: verify "committed" via `git log -- path`,
  and account for every dirty storefront file before a deploy, because `npm run deploy` ships the
  TREE, not the repo).
- [x] STATE.md, `_state/open-items.md` (OI-81 closed), ERROR_LOG.md updated — committed as
  `fc1b03d`, NOT pushed (see below).
- [x] Mockup artifact updated to match shipped UI:
  `https://claude.ai/code/artifact/25779e7e-3e75-4292-8de6-b6642ff46a51`

## In Progress
- Nothing. No code is in flight.

## Pending
- [ ] 🔴 **PUSH `fc1b03d` when the shop is shut** (docs-only: STATE.md, open-items, ERROR_LOG).
      Held because ANY push to main triggers `deploy-production.yml` (no path filter), which
      recreates backend + nginx = ~1 min mid-service API blip for a docs change. Shop hours
      16:00–22:00 UK. `git push origin main`, then confirm the Action goes green and the sites
      load. A monitor was armed for 22:02 UK but dies if this session ends first.
- [ ] **Malik's live UAT of the tip flow** — the one unverified step: place an order with a tip
      (card: Stripe page shows the Tip line; £25.75 + £3.50 must charge £29.25), confirm the
      ticket prints "Tip", the tablet card shows it, and the reports Tips tiles move off £0.00.
- [ ] **OI-80** — CI and Deploy-to-Staging still red on every commit, no signal. Root cause
      unread; decide fix / quarantine / delete workflow.
- [ ] **OI-76** — what3words: verdict "do not buy" (licence 6.3(b)/6.3(e)(iii)), reply drafted,
      unsent. Malik picks what goes back to Imran.
- [ ] **HSTS** on Cloudflare once Always Use HTTPS has a few quiet days.
- [ ] Chips-flow UAT from 08-13, if Malik never ran it (Add button reads "Choose chips",
      sections Heat → Chips → Drink → Dip).
- [ ] Standing note: tips ride inside `order.total`, so Daily Sales revenue includes them.
      The Tips tiles are where the split lives. If Imran later wants tips excluded from revenue
      figures, that's a new item — not built.

## Key Decisions
- **Deployed mid-service on Malik's explicit instruction** (his message: "i think deploy because
  we can have a live runtime experience"). Backend first, storefront second, so the API knew
  `tip` before any browser could send it. Cost: ~1 min backend blip ~20:34 UK; logs show no
  failed customer requests.
- **Tip capped at £20 server-side** (`PublicOrderCreate.tip`, ge=0 le=2000) — a fat-fingered
  "350" for "3.50" must never become a real card charge. Malik chose £20 over £50/no-cap.
- **Tips shown on BOTH service types** (Malik's call), collection tips go to the counter.
- **No explanatory copy on the tip UI** — Malik cut it as redundant.
- **Tips split in reports uses the prepaid/COD rule**, so a tip can never sit in a bucket its
  order's revenue is not in; voided orders and abandoned checkouts count nowhere.
- **Docs push held until close** rather than causing a second mid-service redeploy.
- **The tip is the ONE amount the client may send** — everything else about the order's money is
  still server-computed. Old bundles that send no `tip` key work forever (default 0, tested).

## Files Modified (all committed in `2366c99`)
Backend: migration `u7v8w9x0y1z2_order_tip.py` (new), `models/order.py`, `schemas/public_order.py`,
`schemas/online_report.py`, `services/public_order_service.py`, `services/stripe_service.py`,
`services/email_service.py`, `services/print_service.py`, `services/online_report_service.py`,
`api/v1/public.py`, `api/v1/online_reports.py`, tests ×4 (tenant_routing, online_reports,
escpos_printing, stripe_payments — 10 new tests).
Frontend: `services/onlineOrdersApi.ts`, `services/onlineReportsApi.ts`,
`pages/online-orders/OnlineOrdersPage.tsx`, `pages/online-orders/OnlineReportsPage.tsx`.
Storefront: `lib/api.ts`, `components/Checkout.tsx`, `components/OrderConfirmation.tsx`, plus the
previously-uncommitted OI-78 files `App.tsx` and `store/menu.ts`.
Docs (committed in unpushed `fc1b03d`): `STATE.md`, `_state/open-items.md`, `ERROR_LOG.md`.

## Uncommitted Changes
**~127 dirty files, all pre-existing and all deliberate** — the long-standing doc reorg plus
OI-60's paused, never build-tested backend work (`backend/Dockerfile`, `backend/scripts/start.sh`).
Also pre-existing and untouched: `frontend/src/pages/admin/StaffManagementPage.tsx` (dirty, origin
unknown, NOT shipped — the git push builds frontend from the committed repo),
`backend/app/scripts/seed_demo_kitchen.py` (untracked). A leftover worktree from an older session
exists at `...171d37d0.../scratchpad/base2` (859e8b0) — not this session's, left alone.

> ⚠️ **Do NOT `git add -A` in this repo.** Stage by explicit filename, every time.

## Errors & Resolutions
- **OI-78 storefront source live but never committed** → committed in `2366c99`; ERROR_LOG entry
  with the two rules. **Resolved.**
- **`pytest lastfailed` cache showed 33 entries vs the run's 21+2** → stale entries from earlier
  sessions; resolved by re-running the full suite with the complete failure list captured and
  comparing line-for-line against a same-clock clean-worktree run. **Resolved** (trust the run
  output, never the cache).
- **9-11 date-range tests fail after midnight PK** (local `date.today()` vs UTC `created_at`,
  OI-63 shape) → pre-existing, identical on clean HEAD. My two new report tests use the UTC date
  instead, so they pass at any clock. **Baseline, not a regression.**
- **First 4-file test run showed `sort_toggle` failing** → clock/inter-test flakiness; passed in
  isolation and on every later run. **Not a regression.**

## Critical Context
- 🔴 **`chickshackg84.com` is live and taking real orders.** Shop hours 16:00–22:00 UK
  (20:00–02:00 PK); delivery 16:30–21:30. Deploy only when shut unless Malik explicitly says
  otherwise (he did, once, for OI-81).
- **Two deploy pipelines**: `git push origin main` = backend + tablet frontend (droplet);
  `cd storefront && npm run deploy` = customer site (Cloudflare). A green push proves nothing
  about the other. ANY push redeploys the droplet — no path filter — so docs pushes also blip
  the API.
- **Server `159.65.158.26`**, `~/pos-system`, shared with Orbit CRM behind one nginx. Read
  `memory/server-deployment-rules.md` + `memory/data-integrity.md` before touching it. nginx
  returns 444 to curl — pass a browser `-A`.
- The deploy workflow takes its own verified `pg_dump` before `alembic upgrade head` and aborts
  on an empty dump; latest manual backup from 08-12 also exists
  (`/root/backups/pos_system_20260812T210746Z_pre_OI79.sql.gz`).
- **CI is red and carries no signal (OI-80).** Judge deploys by Deploy-to-Production + effect.
- **Local tests**: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/ -q`. Baseline
  ~21 failures + 2 errors; ~10 are time-of-day dependent — re-baseline in a `git worktree` at the
  same clock before claiming a regression. Python is the venv 3.12, never global 3.9.
- Tip presets/cap: presets live in `storefront/src/components/Checkout.tsx` (`[0,200,400,500]`),
  the cap in BOTH `Checkout.tsx` (UI message) and `backend/app/schemas/public_order.py`
  (`le=2000`) — change them together.
