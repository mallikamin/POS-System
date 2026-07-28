# Pause Checkpoint — 2026-07-29

## Project
- **Name**: Restaurant POS System — Chick Shack UK workstream
- **Path**: `C:\Users\Malik\desktop\pos-project`
- **Branch**: `main` @ `40c0326` (all session work committed and pushed)

## Goal

Get Chick Shack UK's online ordering channel working end to end: a customer orders on the
website, the order lands in the POS, Imran accepts it on a tablet with a lead time, and a
kitchen ticket prints on his existing EposNow printer. This session took it from
"API built locally, nothing deployed" to "deployed, seeded and live, minus the storefront
checkout".

## Completed

- [x] **Printing proven on the client's own hardware.** Walked Imran through RawBT setup
      remotely over WhatsApp, one screenshot per step. Paper came out of the EposNow
      kitchen printer, driven by his tablet. £0 hardware.
- [x] Printer specs confirmed from its own self-test slip: eposnow `POS80GXn`,
      **static `192.168.1.208`**, port 9100, 80 mm / **48 columns Font A**,
      **default code page 0 = PC437**, cutter fitted, firmware 2017 (so no AirPrint).
- [x] Caught the RawBT **width default of 384** (58 mm) and corrected it to **576**
      (80 mm). Left wrong, tickets look fine on short test strings and silently truncate
      real orders.
- [x] **Two multi-tenant defects found and fixed.** Both storefront routes and PIN login
      resolved the tenant with `SELECT ... WHERE is_active LIMIT 1`, no `ORDER BY`.
      PIN login was the serious one: it looped every active tenant and returned the first
      PIN match — the wrong login, not a failed one.
- [x] Public API now tenant-scoped: `/public/{tenant_slug}/menu|orders|orders/{id}/status`.
- [x] **New merchant queue endpoint** `GET /public/manage/orders?state=pending|active|all`
      (did not exist; the tablet had nothing to poll).
- [x] **Order-queue tablet view built** at `/online-orders` — standalone, accept with a
      one-tap ETA, reject with a reason, loud unpaid banner, print on accept, reprint.
- [x] **Chick Shack seeded** locally and on production: 8 categories, **62 items**,
      3 modifier groups, **11 delivery areas**, GBP, Europe/London, tax 0.
- [x] Menu **exported** from `storefront/src/data/menu.ts` rather than retyped
      (`storefront/scripts/export-menu.ts` → `backend/app/scripts/data/chick_shack_menu.json`).
- [x] **Deployed to production.** Server HEAD `4e14680`+, migration `n0o1p2q3r4s5` applied,
      nginx recreated with both `default.conf` and `voice.conf` mounted.
- [x] Deploy workflow now **runs migrations** with a `pg_dump` first and aborts on an
      empty dump.
- [x] **`eats.sitaratech.info` certificate issued and split into its own server block.**
      It had been in `server_name` since 2026-07-15 with no certificate — every visitor got
      `ERR_CERT_COMMON_NAME_INVALID`. Malik confirmed the site now loads.
- [x] Backend suite **342 passing** (+24 this session), same 12 pre-existing failures.

## In Progress

- [ ] **Nothing mid-edit.** The tree is clean of session work; everything is committed and
      pushed. The next task is a fresh start on the storefront.

## Pending — in order

- [ ] **UAT run 2 prerequisite: wire the storefront checkout.** This is the priority.
  - [ ] Storefront should fetch `GET /public/chick-shack/menu` instead of rendering the
        hardcoded `storefront/src/data/menu.ts`. Its IDs are slugs (`peri-half`); the order
        endpoint validates **UUIDs**. This is why no real order can be placed today.
  - [ ] `place()` in `storefront/src/components/Checkout.tsx` fabricates a reference and
        creates nothing. Post to `POST /public/chick-shack/orders`. **IDs and quantities
        only** — sending a price returns 422 by design. Every required modifier group must
        be satisfied or the order is refused with 409.
  - [ ] Confirmation screen polls `GET /public/chick-shack/orders/{id}/status` so the
        customer sees "accepted, 45 min".
  - [ ] **Only then** flip `SHOP.orderingEnabled` to `true`.
- [ ] **UAT run 1** — we place an order, Imran accepts on the tablet, ticket prints.
      Possible today.
- [ ] **UAT run 2** — Imran places the order himself on the website, then accepts.
- [ ] **The served/delivered gap (Malik spotted this).** An accepted order reaches
      `in_kitchen` and stops. There is no way to mark it collected or delivered, so the
      Active tab grows forever and takings never settle. Reuse the existing
      `ready → served → completed` machine and `PATCH /orders/{id}`.
      **Ask Imran** whether "Delivered" also marks a cash order paid, or if that is a
      second tap — it decides whether the driver or the shop closes the order.
- [ ] Stripe (OI-20, blocked on the client's account). Not needed for either UAT run.

## Key Decisions

- **Kept PIN login, fixed the resolution** (D-10). Malik offered to drop PIN for
  username/password; dropping it would have lost good tablet UX and left the real defect
  untouched. PIN now collects **every** match across tenants: 0 → 401, 1 → log in,
  2+ → 400 "name the shop". Every login working today keeps working; the wrong-login
  outcome is impossible. Unknown slug answers **401 not 404**, so tenants cannot be
  enumerated.
- **Menu variants → a required single-select "Choice" group** (D-11). Every Chick Shack
  item has variants and no top-level price; the POS `MenuItem` has one price. Item takes
  the cheapest variant as base, the rest become price adjustments.
- **Tax seeded at 0, not 20% UK VAT.** Totals match the printed board either way under
  `tax_inclusive`; a non-zero rate would assert a VAT registration nobody confirmed.
- **The server does not print.** It builds ESC/POS bytes; the tablet hands them to RawBT
  over TCP:9100. This is why printing rides on the Accept tap — no background service, so
  no Android Doze problem.
- **A failed print never un-accepts an order.** The customer has already been told yes.

## Files Modified

- `backend/app/api/v1/public.py` — tenant-slug routes, merchant queue, ticket endpoint
- `backend/app/api/v1/auth.py` — PIN collision fix, `_tenant_for_login`
- `backend/app/schemas/auth.py`, `schemas/public_order.py` — `tenant_slug`, merchant schemas
- `backend/app/services/public_order_service.py` — `list_merchant_orders`, `get_currency`
- `backend/app/services/escpos.py`, `print_service.py` — ESC/POS + kitchen ticket
- `backend/app/scripts/seed_chick_shack.py` + `data/chick_shack_menu.json` — new seeder
- `backend/tests/test_public_tenant_routing.py` (17), `test_pin_tenant_isolation.py` (8)
- `frontend/src/pages/online-orders/OnlineOrdersPage.tsx` — the tablet view
- `frontend/src/services/onlineOrdersApi.ts`, `lib/tenant.ts`, `stores/authStore.ts`
- `storefront/scripts/export-menu.ts` — menu export for the seeder
- `docker/nginx/nginx.demo.conf` — split `eats.sitaratech.info` into its own SSL block
- `.github/workflows/deploy-production.yml` — backup + migrations
- `STATE.md`, `_state/*.md`, `HANDOFF.md`

## Uncommitted Changes

All session work is **committed and pushed** to `origin/main`. 99 paths remain dirty but
none of them are this session's: they are a pre-existing bulk edit that added a QA notice
to ~50 markdown docs, plus 13 staged-then-unstaged `PAUSE_CHECKPOINT_*` file moves into
`docs/history/`. Left alone deliberately — they are someone else's uncommitted work.

## Errors & Resolutions

- CI build failed: `formatMoney` not exported → the tablet view was committed without the
  multi-currency `currency.ts` it depends on. **Local type-check passed because it ran
  against the working tree, not the commit.** Fixed in `4e14680`.
- `https://eats.sitaratech.info` served the `pos-demo` certificate → the hostname was added
  to `server_name` on 2026-07-15 but no certificate was ever issued, and one server block
  can only present one certificate. Fixed: issued via webroot, split into its own block,
  applied by **reload** (not recreation, so mounts were never at risk).
- Chick Shack's 11 delivery areas were seeded onto **`demo-restaurant`** locally on 07-27,
  because `chick-shack` did not exist yet. Correctly seeded now; the stray rows remain on
  the demo tenant locally (**OI-39**). Production was never affected.
- Tenant insert failed with a NULL `tenant_id` → `tenants.tenant_id` self-references, and
  `tenant.id` is None before flush. Fixed by generating the UUID explicitly.
- `docker cp` could not read `/tmp` in the backend container (tmpfs). Worked around by
  streaming the file to the host with `docker exec cat > file`.

## Critical Context

- **Imran's tablet URL**: `https://eats.sitaratech.info/online-orders?shop=chick-shack`
  The `?shop=` is remembered in localStorage so it survives the login redirect.
  **Do not hand out `pos-demo.duckdns.org`** — it works, but it is a demo URL.
- **Login sheet**: `C:\Users\Malik\Downloads\ChickShack-PRODUCTION.txt` (production) and
  `ChickShack.txt` (local). Never echo the contents.
- **The deploy's "Verify deployment" step always fails** — it uses curl, and this nginx
  blocks curl with HTTP 444 by design. The deploy itself succeeds. This is what generates
  the CI failure emails.
- **Every deploy leaves nginx on the old backend IP** → expect a 502 until nginx is
  recreated by hand. Always inspect volume mounts first; `/root/orbit-crm/voice.conf` must
  survive or orbit-voice goes down.
- **`.env.demo` and `droplet.txt` are tracked in git.** `.env.demo` carries production
  QuickBooks credentials, the DB password and `SECRET_KEY`, and is modified on the server —
  so `git pull` there only works while no commit touches it, and the workflow hides a
  failed pull behind `|| true`. `INFRASTRUCTURE_CREDENTIALS_REFERENCE.md` is untracked in
  the repo root. **Never `git add .` in this repo.**
- **Backend tests** need the venv built this session:
  `cd backend && ./.venv/Scripts/python.exe -m pytest tests/ -q`
- `scratchpad/e2e_order_flow.py` drives the whole chain (place → queue → accept → ticket →
  status) and is the fastest way to check the backend before touching the storefront.
- Production tenants: `chick-shack` (62 items), `cosa-nostra` (208), `demo-restaurant` (43).
