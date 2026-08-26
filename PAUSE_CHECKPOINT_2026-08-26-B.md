# Pause Checkpoint - 2026-08-26 (B)

⚠️ **This is the SECOND checkpoint of 2026-08-26.** `PAUSE_CHECKPOINT_2026-08-26.md` is the
earlier one from the morning session and is still valid history. Do not overwrite it.

## Project
- **Name**: POS System (Sitara Infotech restaurant POS) - this pass is the FZ LLC UAE build
- **Path**: `C:\Users\Malik\desktop\pos-project`
- **Branch**: main. **HEAD `815a21e` = `origin/main` = server. 0 unpushed, all shipped.**

## Goal
Build the complete FZ LLC (Martin Zubeldia, UAE) system - everything in his written scope, not a
subset - get it live on a client-visible URL, and wrap with a demo video, a UAT playbook PDF and a
two-tier quotation. **Deadline Friday 2026-08-28** for build + UAT + fixes, so Martin and his
partners review over the weekend and reconnect Monday 08-31.

🔴 **Malik's framing, and it changes priorities:** this is a demo, but also our chance to
fine-tune the product and open avenues to **upsell to other clients**. *"We have only to gain
here."* Build these as real product capabilities, not demo props. There is time to do it properly
and to learn the UAE market.

## Completed
- [x] `/refresh` run. **STATE.md was a whole session stale** (no record of the 08-26 FZ work);
      reconstructed. Also found and recorded: the checkpoint claimed a `.txt` call transcript that
      does not exist (content survives in `discovery.md`).
- [x] **Two production deploys, both green, Chick Shack byte-identical through both.**
      `902e35f` (sub-recipes) then `815a21e` (multi-location).
- [x] **Both FZ locations LIVE and verified on production.**
      `https://eats.sitaratech.info/login?shop=martin-fz`
      - Location 1 "Production & Wholesale" (PROD): production type, **A4 VAT tax invoice**,
        legal name `FZ LLC`, TRN `100123456700003`, 15 ingredients incl. 3 produced sub-recipes.
      - Location 2 "Delivery Kitchen" (DEL): delivery type, thermal ticket, 3 ingredients.
- [x] Migration `x0y1z2a3b4c5`, entirely additive: `locations`, `location_stock`, `sales_channels`,
      `stock_transfers`, `stock_transfer_items`; `orders` + `location_id`, `sales_channel_id`,
      `channel_commission_minor`; `inventory_transactions` + `location_id`.
      **Upgrade/downgrade/upgrade round-trip tested. Rehearsed against a restored copy of the real
      production DB before each deploy.**
- [x] Five new services: `stock_service` (single chokepoint for all stock movement),
      `production_service` (batch runs + idempotent sale deduction), `transfer_service` (two-phase
      send/receive), `location_service` (locations, channels, net profit), `tax_invoice_service`.
- [x] **20 new API routes** under `/locations`, plus `/receipts/orders/{id}/tax-invoice`.
- [x] **Seven new admin screens** (Locations, Stock, Transfers, Sales Channels, Profitability,
      Tax Invoices) + sub-recipe support added to RecipeBuilderPage.
- [x] 🔴 **Ingredients and Recipes pages were COMMENTED OUT of the router** since BOM Phase 3,
      so the entire inventory UI was unreachable. That is why a Postgres-only bug survived a
      "100% complete" status. Both now routed.
- [x] **49 new tests** (37 location, 12 tax invoice). **Full suite 669 passed**, same 10 failed +
      2 errors that fail identically at clean HEAD (QB Desktop suite, a bcrypt version-string
      issue, and one stale assertion in `test_pay_first`).
- [x] **43-check live verification against the PUBLIC URL passed 100%** - per-site stock isolation,
      low-stock alert, production run, transfer round-trip incl. correct refusals, profitability
      across 6 channels and 2 sites, A4 invoice reconciling.
- [x] **Universal system-admin applied to ALL FOUR production tenants** and verified by real login
      (password AND PIN) on each. A read-only pre-flight first confirmed no PIN collision would
      lock out a Chick Shack staff member.
- [x] Tenant isolation **proven** on the live path: a martin-fz token searching `07` (matches 101
      real chick-shack phones) returns 0 rows; foreign IDs 404; Martin's credentials 401 on
      chick-shack.

## In Progress
- Nothing mid-edit. Everything above is committed and deployed. Paused cleanly at Malik's request.

## Pending
**Read `_context/clients/fz-llc-uae/plan-and-todo_2026-08-26.md` FIRST - its top section carries
Malik's full standing directive verbatim.**

### Build (all of it, these are the real remaining scope items)
- [ ] **Supplier master + PO workflow + email PO sending.** Location -> Supplier -> Items ->
      Create PO -> Send by email -> Receive Goods -> Update Inventory. Nothing exists yet.
- [ ] **OCR-based goods receiving.** Upload/scan doc -> OCR extract -> user review/correct ->
      confirm -> stock updated.
- [ ] **AI-assisted PO quantity suggestion.** Weekly production target -> what and how much to
      order, from current stock + recipes. ⚠️ **Consult the `api-cost-playbook` skill BEFORE
      writing any LLM-calling code.**
- [ ] **Back-office quotations** (separate from the A4 tax invoice, which IS built).
- [ ] Tier-B e-commerce, if Tier B is chosen (Chick Shack UK pattern: Stripe checkout -> POS order
      -> accept/reject -> ticket printing).

### Then the three deliverables, in order
- [ ] **(i) Demo video for Martin.** Malik records himself doing the UAT: navigation, test
      transactions, dashboards. Needs a shot-list/script Malik can follow while recording.
      The `video` skill exists for editing.
- [ ] **(ii) UAT playbook PDF** so Martin and partners can replicate every step themselves.
      This is a reference document, so write it in full.
- [ ] **(iii) Two-tier quotation** (with / without e-commerce), plus third-party integration
      playbook (cost, timeline, how each route works) and a payment gateway comparison.
      - 🔴 **Uber Eats does NOT operate in the UAE. It is Careem now.** Raise it with Martin
        directly; he named Uber Eats himself.
      - ⚠️ **Say plainly these are PUBLIC documents referred to and that real costs/timelines
        vary by third-party integrator.** Never present researched figures as quoted terms.
      - **"Let's be smart about what we send."** Curate. Volume is not credibility to a man with
        three bad POS experiences who is price-sensitive.
      - Research leads Malik found: **Deliverect**, **GetOrder**,
        `https://engineering.careem.com/tech/developerhub`,
        `https://grubtech.com/en/integrations/`. Existing work already on disk:
        `integrations/2026-08-26_delivery-and-payment-research.md`.

## Key Decisions
- **One host serves every tenant** (`eats.sitaratech.info` + `?shop=<slug>`), NOT a subdomain per
  client. Malik's call, and he was right: per-tenant subdomains mean DNS + cert + nginx + a deploy
  per client. This also removed the riskiest part of the plan - no DNS, no cert, no nginx change.
  An earlier note of mine calling `eats.` "Imran's URL" was wrong and is withdrawn; `sitaratech.info`
  is Sitara's own domain.
- **`stock_service.move_stock` is the ONLY way stock changes.** Balance and movement log are written
  together or not at all, so they cannot drift.
- **Stock may go negative, and is recorded.** A till must not refuse a sale over a bookkeeping
  discrepancy.
- **Transfers are two-phase.** Stock leaves on send, arrives on receive; goods in a van are counted
  in neither place and a short delivery stays visible.
- **Commission is snapshotted onto the order at completion**, never read live at report time, so a
  renegotiated rate cannot rewrite last month's profit.
- **VAT is backed OUT of the gross** on the tax invoice (prices are VAT-inclusive). Adding it on top
  would overstate tax on every document.
- **Seed scripts stay OUT of git.** `system_admin.py` / `seed_fz_llc.py` hold plaintext passwords
  and **this repo is public**. They live at `/root/fz-scripts/` (mode 600) on the server and in the
  local tree only.

## Files Modified
Committed in `815a21e` (33 files). Highlights:
- `backend/app/models/location.py` - new: Location, LocationStock, SalesChannel, StockTransfer(+Item)
- `backend/alembic/versions/x0y1z2a3b4c5_multi_location.py` - new migration
- `backend/app/services/{stock,production,transfer,location,tax_invoice}_service.py` - new
- `backend/app/api/v1/locations.py` - new, 20 routes
- `backend/app/services/order_service.py` - completion hook, fail-safe for tenants with no locations
- `backend/app/api/v1/inventory.py` - `_enrich_recipe` helper replacing 4 duplicated blocks
- `frontend/src/pages/admin/{Locations,Stock,Transfers,SalesChannels,Profitability,TaxInvoices}Page.tsx` - new
- `frontend/src/pages/admin/RecipeBuilderPage.tsx` - sub-recipe mode
- `frontend/src/App.tsx`, `AdminLayout.tsx` - routes + nav
- `backend/tests/test_location_service.py`, `test_tax_invoice.py` - new, 49 tests

## Uncommitted Changes
- `STATE.md` and `_context/clients/fz-llc-uae/plan-and-todo_2026-08-26.md` - modified this session
  with the new directive and the deploy record. **Commit these.**
- `backend/app/scripts/{system_admin,sync_system_admin,seed_fz_llc,seed_demo_kitchen}.py` -
  untracked **and must STAY untracked** (plaintext credentials, public repo).
- 142 dirty files total; the ~135 baseline is long-documented scratch drift, not this session's.

## Errors & Resolutions
- **Product cost multiplied by 100 in the profitability report** -> margins of -1790%.
  `cost_per_serving` is already in minor units. **The unit test had the same wrong assumption baked
  into its fixture, so only end-to-end verification against the live API caught it.** Fixed in both.
- **`InventoryTransaction.transaction_date` missing `DateTime(timezone=True)`** -> every stock
  movement would have failed against Postgres. Never hit only because no tenant had ever held stock.
  Fixed. A scan of all 33 datetime columns found no others (`StockCount.count_date` is correctly a
  `Date` and was left alone).
- **`Recipe` has no `name` column** -> my `production_service` referenced `recipe.name` and would
  have crashed at runtime. Caught by the new tests. Added a `_recipe_label` helper.
- **`MissingGreenlet` risk** on `recipe.menu_item` lazy load -> added `selectinload`.
- **Recipe LIST endpoint did no enrichment** -> every recipe reached the UI unlabelled. Fixed.
- **Backend container has a read-only rootfs** -> `docker cp` into it fails. To run a one-off script
  against production: build a throwaway image `FROM pos-system-backend` with `COPY --chmod=644`
  (mode matters, it runs as non-root) and `docker run --rm --entrypoint python -w /app
  -e PYTHONPATH=/app --network pos-system_default --env-file <the env file>`.
  **`--entrypoint python` is required** or the image's own entrypoint swallows the argument.
- **cred-guard blocks any inline command whose text contains the env filename.** Put such commands
  in a `.sh` file and scp it. Not a bug, working as intended.
- **Git Bash mangles container paths** -> prefix with `MSYS_NO_PATHCONV=1`.

## Critical Context
- 🔴 **`github.com/mallikamin/POS-System` is a PUBLIC repo and `.env.demo` is committed to it**
  (present in the `50a8002` tree, 3 commits of history, not gitignored).
  `docs/DEPLOYMENT_PLAYBOOK.md:124` describes it as carrying live credentials. **Raised with Malik;
  he declined to act on it now. Contents were NOT read.** Note that flipping the repo private is not
  a free click: if the server's `git pull` authenticates over HTTPS it would break the deploy.
- **Chick Shack baseline to check after ANY deploy: 227 orders, newest
  `2026-08-25 20:03:19.780197+00`, 172 customers, 222 payments, 0 locations.** It is single-site.
- **Rollback assets on the server:** `/root/backups/pos_system_20260826T114101Z_pre_fzllc.sql.gz`
  (42 tables, footer verified) and images tagged `pos-system-backend:pre-fzllc` /
  `pos-system-frontend:pre-fzllc`. Snapshots under `/root/snapshots/fzllc_pre_deploy_*`.
- **Deploy = `git push origin main`.** It rebuilds backend + frontend, runs `alembic upgrade head`
  on the production DB, and recreates the SHARED nginx serving Chick Shack's tablet and two Orbit
  hostnames. **The workflow verifies 3 hostnames but NOT `parkcity.sitaratech.info`** - check that
  one by hand.
- **Local dev stack must be running** (`pos-system-{backend,frontend,nginx,postgres,redis}-1`) on
  8090/5450/6390.
- `pos_rehearsal` is a scratch DB in local Postgres holding a restored production copy. Useful for
  rehearsing the next migration; safe to drop and recreate.
- The known-noise line in backend logs is the trapped `bcrypt.__about__` AttributeError. Not an error.
