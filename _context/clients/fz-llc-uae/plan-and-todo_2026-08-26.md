# FZ LLC (Martin Zubeldia, UAE) — plan and TODO

## 🔴 Standing directive from Malik, 2026-08-26 (later same day) — read this before doing anything else

**"I need the complete thing. No half-cooked jobs."** Everything under "Explicitly NOT done yet"
below is not optional scope for later — it is the actual deliverable. Do not present a partial
build as ready, and do not quietly narrow scope to whatever's fastest. If something in that list
turns out to be genuinely infeasible or needs a real decision from Malik, say so explicitly and
ask — don't just skip it silently.

**Malik's own admin login is now UNIVERSAL across tenants, not per-tenant** — per his explicit
follow-up ("cant have different credentials all round"). Canonical definition:
`backend/app/scripts/system_admin.py` (`SYSTEM_ADMIN_USER` + `ensure_system_admin` helper, which
syncs in place, not just create-if-missing). Applied and verified on **local dev only**:
`chick-shack` (via `sync_system_admin.py`) and `martin-fz` (via `seed_fz_llc.py`, which now calls
the shared helper) both accept the identical `malik@sitaratech.info` login. See
[[universal-system-admin-login]]. **NOT applied to the live production Chick Shack server** —
needs Malik's explicit go-ahead first, separate from this local build. Separate from the demo
persona login (`ADMIN_USER`) that goes to Martin himself.

**Tenant onboarding — production deployment — must be safe and smooth, with ZERO interference
with Chick Shack.** Chick Shack is a live business on the same shared box taking real orders
24/7 — see `memory/server-deployment-rules.md` (mandatory read before any server op) and
[[chick-shack-two-deploy-pipelines]]. Whatever gets built for exposing `martin-fz` on a
client-visible URL (new tenant, new subdomain, nginx config, etc.) must not touch Chick Shack's
containers, DNS, nginx routes, or data — verify this explicitly, don't just assume additive
config is safe. `pg_dump` before any server-side DB change, per [[data-integrity]] /
`memory/data-integrity.md`.

## ✅ Built and VERIFIED this session (2026-08-26, local dev only — not deployed anywhere client-visible)

- **Multi-layer recipe/sub-recipe production chain — the core ask from the call.** Schema change
  (migration `w9x0y1z2a3b4`): a `Recipe` now produces either a `menu_item_id` (sellable item, as
  before) or a `produces_ingredient_id` (an in-house sub-recipe like dough/sauce/stuffing), never
  both/neither (DB check constraint). `backend/app/services/recipe_service.py` rolls a sub-recipe's
  cost up onto the ingredient it produces (`sync_produced_ingredient_cost`), so a normal recipe
  that later consumes that ingredient picks up the correct cost automatically — raw → sub-recipe →
  intermediate → final, exactly what Martin described.
  **Verified, not just written:** 4 new backend tests (`tests/test_recipe_service.py`) pass,
  including the full 3-layer chain (flour+butter → dough @ 7.35 AED/kg → final item cost 1.1025
  AED). Also verified live through the real HTTP API (not just the seed script/tests) — see below.
- **Found and fixed a real, pre-existing bug while building this**, unrelated to the new feature:
  `Recipe.effective_date` (and `StockCount.reviewed_at`) was missing `DateTime(timezone=True)` in
  the model, so any recipe creation against Postgres failed with an asyncpg tz mismatch. This
  explains why `BOM_IMPLEMENTATION_STATUS.md` marked recipes "100% Complete" with "⏳ needs browser
  testing" still unchecked — recipe creation had never actually been exercised end-to-end against
  Postgres. **The backend test suite uses SQLite in-memory, which doesn't enforce this, so it never
  caught it** — a real gap between the test environment and Postgres, worth remembering next time
  something "tests green" but has never been hit through the real API.
- **`martin-fz` demo tenant seeded locally** (`backend/app/scripts/seed_fz_llc.py`, idempotent,
  re-runnable): AED currency, 5% VAT, no floors/tables seeded (no dine-in), 3 categories, 4 menu
  items, 12 raw ingredients, 3 sub-recipes (Croissant Dough, Chicken Stuffing, Cheese Sauce), 4
  final recipes consuming them. Admin login credentials are in the seed script file itself
  (`ADMIN_USER` dict) — not repeated here.
  **Verified live via the real API**, not just the seed script's own print statements: PIN login
  returns valid tokens, `GET /inventory/recipes` shows all 7 recipes with correct rolled-up costs,
  `GET /inventory/ingredients` shows the 3 produced ingredients with synced costs, `GET /menu/full`
  returns the seeded menu. Frontend serves `/login?shop=martin-fz` (HTTP 200) — the URL mechanism
  Martin's demo link would use — but the actual page render was **not** visually checked (no
  browser tooling available in this session, see [[no-claude-in-chrome]]).
- Full backend regression run in progress at time of writing (`pytest tests/`, background, no
  result yet) — existing recipe/inventory endpoints had **zero test coverage before this session**
  despite the "100% Complete" status doc, which is itself worth a note back to Malik.

## ⚠️ Explicitly NOT done yet — do not oversell these on Monday

- **Admin UI for building a sub-recipe.** `RecipeBuilderPage.tsx` only knows how to create a
  menu-item recipe; there is no frontend control yet to pick "produces an ingredient" instead. The
  backend/API/seed fully support it; the admin screen to let a real user build one does not exist.
- **2-location model** (production/B2B location + delivery-only location, inventory transfer
  between them) — not started. Today's tenant has no location concept at all beyond the
  no-dine-in setup.
- **Per-channel commission % + net-profit-by-channel reporting** (Section 8 of the scope doc) —
  not started.
- **A4 VAT tax invoice template** for the B2B location — not started (only the existing thermal
  ticket exists).
- **Supplier master + PO workflow + email PO sending** — not started.
- **OCR-based goods receiving** — not started.
- **AI-assisted PO quantity suggestion** — not started.
- **Deployment to a client-visible demo URL.** Everything above lives on the local dev stack only
  (`localhost:8090`). Standing rule: never hand `pos-demo.duckdns.org` to a client. Putting this in
  front of Martin needs its own careful step following `server-deployment-rules.md` — not rushed
  alongside feature-building.

## ⚠️ Deadline
**Full written quote due by Monday 2026-08-31.** Call was Wednesday 2026-08-26; Martin was
explicit he does not want it slipping to Tuesday/Wednesday — he's planning his next two months and
wants a number before the 1st. Malik is sending demo login credentials directly alongside the
quote — so a client-visible URL (not just localhost) needs to exist before send.

## Commercial target
Near-zero upfront, flat **225 AED/month all-inclusive** — see
[[fz-llc-pricing-and-build-posture]]. Martin's own ceiling logic: if a custom build costs ~4 years
of a subscription alternative, he walks. He's had 3 bad POS experiences already — the number needs
to look visibly cheap against that mental model, not defensible-on-paper.

## What's already in hand
- `refs/2026-08-24_client-scope-of-work.md` — client's written 11-section MVP scope
- `voice-notes/2026-08-26_martin_pos-workflow-walkthrough.mp4` + `.txt` — full call transcript
- `integrations/2026-08-26_delivery-and-payment-research.md` — Talabat/Careem/noon/Deliveroo/
  Uber Eats status + Deliverect aggregator option + UAE payment gateway comparison
- `discovery.md` — full absorbed notes, fit-gap against existing POS, this call's specific asks

## TODO — before Monday (2026-08-31)

### 1. Draft the two-tier written quote (the actual deliverable Martin asked for)
- [ ] **Tier A: platform without e-commerce** — POS + Inventory + Procurement + Recipe/Production
  + OCR receiving + AI PO suggestions + multi-location + channel-commission reporting, cash-first,
  manual channel tagging, no delivery-platform API dependency
- [ ] **Tier B: platform with e-commerce** — Tier A + a custom ordering website (Stripe checkout →
  POS order population → accept/reject → ticket printing), same pattern as the Chick Shack UK
  reference shown on the call
- [ ] State clearly: **custom e-commerce vs. Shopify-connected-to-the-POS are functionally
  equivalent once integrated** — this was said directly on the call, don't contradict it in the
  written quote. The value case for Tier B is convenience/one-vendor simplicity, not capability.
- [ ] Break out ongoing costs as **three separate line items**, not one bundled number: software
  subscription, annual hosting, minimum maintenance
- [ ] Include a week-by-week timeline: assessment → deployment → review, matching what was
  discussed live (roughly first 3-4 weeks post-signoff are test transactions + workflow mapping)
- [ ] Price toward 225 AED/month all-inclusive target, near-zero upfront — this is the anchor,
  don't build the quote up from an effort-based estimate the way Crescent Consultancy's was
- [ ] Two-location model: production/B2B location (A4 tax invoices, no thermal ticket) +
  delivery-only location (call center + apps + e-commerce), inventory transfer between them —
  make sure the quote reflects 2 locations specifically, not a generic multi-location line
- [ ] Send the quote **without waiting on delivery-platform API confirmations** — Martin explicitly
  said not to wait on that; note in the quote that API-integration scope is priced separately once
  each platform confirms access (he already agreed integration-or-not is a different scope/price)

### 2. Give Martin and his partners demo access
- [x] **`martin-fz` demo tenant built and verified locally** — AED, no dine-in, multi-layer
  recipe/sub-recipe production chain (dough/stuffing/sauce → final items), real menu, real costed
  recipes. See "Built and VERIFIED this session" above. Login credentials are in
  `backend/app/scripts/seed_fz_llc.py`.
- [ ] **Still needed: a client-visible URL.** Currently only reachable at `localhost:8090`.
  Standing rule: never hand `pos-demo.duckdns.org` to a client — needs its own subdomain/URL,
  following `server-deployment-rules.md` (shared box with Orbit CRM, pg_dump before any server DB
  change). This is the actual blocker before credentials can go out with the quote.
- [ ] Frame it exactly as discussed: "not the final product, just to see what exists and how it
  can be tuned to your workflow"

### 3. Delivery platform integration groundwork (in parallel, doesn't block the quote)
- [ ] Get API documentation or a named technical contact for **Talabat, Careem, and noon Food**
  (see `integrations/2026-08-26_delivery-and-payment-research.md` for the docs-portal URLs
  already found — Talabat's is the most complete: NDA + PGP credential process)
- [ ] **Correct Martin on Uber Eats** — it does not operate in the UAE (exited 2020, folded into
  Careem). Substitute Talabat as the real third major platform. Raise this directly since he named
  Uber Eats himself; don't just silently swap it in the quote without telling him why
- [ ] Do not commit to an AI-agent portal-scraping fallback without checking each platform's ToS —
  flagged live on the call as a real restriction risk for "huge organizations like Noon or Careem"

### 4. Build (continues after the demo URL / quote are out)
- [x] Multi-layer recipe/sub-recipe production chain (raw → sub-recipe → intermediate → final) —
  built, tested, verified live via API. See top of this file.
- [ ] 2-location model (production/B2B + delivery-only), inventory transfer between them — not
  started; today's tenant has no location concept beyond no-dine-in
- [ ] Admin UI to build a sub-recipe (RecipeBuilderPage only supports menu-item recipes today)
- [ ] Per-channel commission % field feeding net-profit reporting (Section 8)
- [ ] A4 VAT-compliant tax invoice template for the B2B location + back-office quotations
- [ ] Supplier master + PO workflow + email PO sending
- [ ] OCR-based goods receiving
- [ ] AI-assisted PO quantity suggestion
- [ ] If Tier B is chosen: e-commerce site on the Chick Shack UK pattern (Stripe checkout → POS →
  accept/reject → ticket printing)
- [ ] Delivery platform API integrations, sequenced: cash+manual first, then evaluate Deliverect
  aggregator vs. direct Talabat/Careem/noon integrations once volume/priority is known

## Open questions still to resolve with Martin (not blocking the Monday quote)
- Business's actual trading name (only "FZ LLC" appears anywhere so far)
- Which delivery platforms FZ LLC actually plans to list on first
- Whether card payment is needed at launch or cash-only is fine for MVP
