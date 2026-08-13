# Pause Checkpoint — 2026-08-13 (~03:00 PK / 23:00 UK 12 Aug)

## Project
- **Name**: Restaurant POS — Chick Shack UK online ordering channel
- **Path**: `C:\Users\Malik\desktop\pos-project`
- **Branch**: `main` · **HEAD** `1d07ebc` · **nothing unpushed** · server at the same commit
- **Storefront**: Cloudflare version `f0d8764a`

## Goal
Imran reported two problems in one evening. First, that the website was "not working" — a photo of a
checkout screen reading *"Online ordering is coming very soon"* while Malik's own test order went
through fine. Second, from a printed kitchen ticket, that a meal *"doesn't say which chips"*. Both
were diagnosed, both root causes turned out to be different from the obvious guess, and both were
fixed and deployed after the 22:00 UK close.

## Completed

- [x] **OI-77 — the "not working" report. Root cause: the site served over plain HTTP.**
  `http://chickshackg84.com` returned 200 with **no redirect**, so the page origin was `http://…`,
  the menu fetch to `https://eats.sitaratech.info` carried that origin, the API correctly returned
  **no CORS header**, the browser blocked it, and `store/menu.ts` fell back to the hardcoded menu with
  ordering off. **Deterministic, not intermittent.** Fixed by Malik in Cloudflare →
  SSL/TLS → Edge Certificates → **Always Use HTTPS = On**. Zero code, zero deploy. Verified: 301,
  single hop, no loop; full customer path re-simulated end to end.
- [x] **OI-78 — the failure message.** Replaced *"Online ordering is coming very soon"* with copy that
  names the real cause, plus a **Retry** button, **four automatic retries** with a widening gap
  (2s/5s/12s/30s), an `online`-event listener, and a warning on the **menu screen** so nobody builds a
  basket before finding out. Shipped to Cloudflare as `f0d8764a`.
- [x] **OI-79 — chips not recorded on meals.** Measured first: **23 of 112 meal lines since launch
  (20.5%)**, about two a night, reached the kitchen with no chips choice. Renamed the group
  `Meal Deal Upgrade` → **`Chips`** (done live during service, safe — no validation change), then
  after close set `required: true`, `min_selections: 1`, and reordered the meal groups to
  **Heat → Chips → Drink → Dip**.
- [x] **Backend `429ce34`** — `get_public_menu` now **sorts** modifier groups by `(display_order, name)`.
  Three regression tests, mutation-checked. Full suite **536 passed** vs **533** on a clean-HEAD
  worktree, identical 21 failures and 2 errors either side → zero regressions.
- [x] **`pg_dump` taken and proven restorable** before any DB change.
- [x] STATE.md and `_state/open-items.md` updated and pushed (`1d07ebc`).

## In Progress
- Nothing. No code is in flight.

## Pending
- [ ] **Malik's morning UAT of the chips flow** — the ONLY thing not verified, and it cannot be from
      here (Chrome extension has failed to connect all week; the tablet is behind a login the
      assistant must not handle). **30 seconds:** open any meal on `chickshackg84.com`, confirm the
      Add button reads **"Choose chips"** until one is picked, and the sections run
      Heat → Chips → Drink → Dip.
- [ ] **OI-80 — CI and Deploy-to-Staging are red on every recent commit** (all 8 latest, including
      commits running in production now). Only Deploy-to-Production is meaningful. Root cause unread.
      Likely the ~21 known-failing tests (parked QuickBooks-Desktop suite + OI-63 time-of-day
      boundary + two others). Decision needed: fix, quarantine, or stop running the workflow.
- [ ] **OI-76 — what3words.** Researched, verdict is **do not buy** (licence clause 6.3(b)/6.3(e)(iii),
      not price). Reply drafted and **unsent**. Malik picks what goes back to Imran.
- [ ] **HSTS** on Cloudflare — the belt-and-braces follow-up to OI-77. Deliberately deferred because a
      long `max-age` is awkward to reverse. Revisit once Always Use HTTPS has a few days on it.
- [ ] Optional: measure what the HTTP-origin bug cost. Cloudflare Analytics has an http-vs-https split.
- [ ] Artifact mockup `https://claude.ai/code/artifact/209e67c3-4c46-4e41-bb54-82a590612238` still
      labels the chips change as "Proposed". It is now shipped. Cosmetic only.

## Key Decisions
- **Forced HTTPS rather than allow-listing `http://` in CORS.** The tempting quick fix would have made
  ordering work over an unencrypted connection, putting customer name, phone and address in clear text.
- **Split the chips fix in two.** The rename went out mid-service because it changes no validation; the
  `required` flag waited for close because `public_order_service.py:406` rejects an order whose basket
  lacks a required selection, and baskets persist in localStorage — flipping it during service would
  have failed every in-flight basket with an unrecoverable generic error.
- **Fixed the data, not the printer.** Rejected making `print_service.py` assume "Regular Chips" when
  the group is empty; that buries a menu rule in a second place, the shape behind OI-61/65/66/68/73.
- **Kept the group sort inside the public menu builder**, not on the model, so the POS tablet and admin
  screens are untouched.
- **Both drink groups got `display_order = 3`** so kids meals read the same way as adult meals.

## Files Modified (committed)
- `backend/app/services/public_order_service.py` — modifier groups now `sorted()` by
  `(display_order, name)`, same key as the item sort directly above (line ~132).
- `backend/tests/test_public_menu_group_order.py` — **new**, 3 tests: display_order wins over insertion
  and alphabetical order; ties fall back to name; the `is_active` filter survived the edit.
- `storefront/src/components/Checkout.tsx` — new failure copy + Retry button; reads `load` from the store.
- `storefront/src/App.tsx` — retry backoff constant, `online` listener, sticky `menuFailed` state, menu
  warning bar.
- `storefront/src/store/menu.ts` — `load()` sets `source: "loading"` at the start so retries reset state.
- `STATE.md`, `_state/open-items.md` — full write-up of OI-77/78/79/80.

## Uncommitted Changes
**130 dirty files, all pre-existing and all deliberate.** The long-standing doc reorg plus **OI-60's
paused, never build-tested backend work** (`backend/Dockerfile`, `backend/scripts/start.sh`,
`backend/logging_config.json` — `start.sh` gained `--log-config`, which would break backend startup if
shipped untested).

> ⚠️ **Do NOT `git add -A` in this repo.** Stage by explicit filename, every time.

## Errors & Resolutions
- **"Website not working" / "Online ordering is coming very soon"** → site served over plain HTTP,
  killing CORS. Fixed with Cloudflare Always Use HTTPS. **Resolved.**
- **`display_order` had no effect on the storefront** → `get_public_menu` filtered but never sorted the
  modifier groups. Fixed in `429ce34`. **Resolved.**
- **`sqlalchemy.exc.MissingGreenlet` in the new test** → assigning `item.modifier_groups = rows` on an
  **already-flushed** object makes SQLAlchemy load the OLD collection to compute change history, which
  is sync IO in an async session. Fixed by writing link rows directly. **Resolved.**
- **`IntegrityError: NOT NULL constraint failed: menu_item_modifier_groups.tenant_id`** → the
  association is a real model (`MenuItemModifierGroup`) carrying its own `tenant_id`, which the plain
  relationship does not populate. **Resolved.**
- **`psql: FATAL: role "postgres" does not exist`** → the role is `pos_admin`, database `pos_system`.
  **Resolved.**
- **pytest failed on `Mapped[datetime | None]`** → it had picked up global Python 3.9. Use
  `./.venv/Scripts/python.exe` (3.12). **Resolved.**
- **Quoted SQL mangled through the ssh → docker → psql layers** → write the SQL to a file, `scp`,
  `docker cp`, `psql -f`. **Resolved.**
- **My own pre-push secret scan could not block** → written as
  `(grep -c ... || echo 0) && git commit`, so it printed `1` and the commit proceeded anyway. The one
  match was prose ("secret-shaped strings"), not a credential, confirmed afterwards. **Pattern is
  still wrong and will not gate anything — fix before relying on it again.**
- **Two copy errors caught by Malik, not by me** → *"ordering is off right now"* was false (the shop
  was open; the customer's connection had failed), and I told him the reorder was data-only with no
  deploy when it was not. Both corrected before shipping.

## Critical Context
- 🔴 **`chickshackg84.com` is live and taking real orders.** Shop hours **16:00–22:00 UK**; delivery
  16:30–21:30. Deploy only when shut.
- **Two unrelated deploy pipelines.** `git push origin main` ships the **backend**; the storefront needs
  `cd storefront && npm run deploy` (Cloudflare). A green push proves nothing about the other.
- **Server `159.65.158.26`**, path `~/pos-system`. **Shared with Orbit CRM** behind one nginx — check
  `docker ps` before any container operation. Postgres container `pos-system-postgres-1`, role
  `pos_admin`, database `pos_system`. Orbit's DB is `orbit_db` — never touch it.
- **Backup from this session:**
  `/root/backups/pos_system_20260812T210746Z_pre_OI79.sql.gz` (verified: 42 COPY blocks = 42 tables,
  120 orders = 120 live).
- **CI is red and carries no signal.** Judge deploys by the **Deploy to Production** workflow and by
  verifying the effect on the server, never by CI.
- **Local backend tests:** `cd backend && ./.venv/Scripts/python.exe -m pytest tests/ -q`. Expect
  **~21 failures + 2 errors** as the baseline; roughly 10 of those are time-of-day dependent (OI-63),
  so re-baseline in a `git worktree` at the same clock before claiming a regression.
- **Docker Desktop was not running locally** this session, so dockerised tests were unavailable.
- Verification standard that worked here: resolve `index.html` → entry chunk → assert strings; read
  source **out of the running container**; assert the live **API payload**, not the code.
