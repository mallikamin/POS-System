# Pause Checkpoint — 2026-07-29 (C)

## Project
- **Name**: Restaurant POS System — Chick Shack UK workstream
- **Path**: `C:\Users\Malik\desktop\pos-project`
- **Branch**: `main` @ `4636ae0`, pushed and deployed. Everything is merged; the
  `feat/storefront-checkout-wiring` branch is finished with.

## Goal

Give Chick Shack a complete online ordering channel: customer orders on the website, the
order reaches the shop's tablet, staff accept it with a lead time, a ticket prints, the
customer is emailed at each step, and the order can be driven all the way to delivered and
paid. **Malik's standing instruction is to build the whole thing and stop asking piece by
piece.** Imran confirmed the scope 2026-07-29 03:06: *"You've got it, exactly what I'm
looking for, thanks."*

---

## 🔴 THE HEADLINE: ORDERING IS LIVE

`chickshackg84.com` was **published** at ~00:30 UK on 2026-07-29 and **takes real orders
right now, 24/7**. Every order lands on Imran's tablet at
`https://eats.sitaratech.info/online-orders?shop=chick-shack`.

**Imran has still never opened that page on his real tablet.** That is the single biggest
untested link in the chain, and he has not yet been told the site is live.

---

## Completed this session

### The order can now finish (was the whole point)
- [x] Tablet lifecycle buttons: one **"Out for delivery" / "Ready for collection"** button
      whose wording follows `service_type`, then **"Delivered" / "Collected"** which settles
      an unpaid cash order in the same tap and **says so on the button face**, plus a
      separate **"Mark paid"** for the driver-returns-later case.
- [x] Completed orders leave the Active tab. Previously an accepted order reached
      `in_kitchen` and stopped forever.
- [x] Confirmation screen follows the order to the end. Fixed two real bugs while there: it
      claimed **"Ready for collection" the instant the shop ACCEPTED** (food not made yet),
      and it **stopped polling on accept** so it could never learn anything after.

### 24/7 pre-orders (a reversal — read the reasoning)
- [x] I first gated checkout to 14:00–22:00 so a 3am order could not land on an unwatched
      tablet. **Malik pushed back and was right**: refusing a customer loses the order.
      Reversed. The clock now only changes what everyone is *told*.
- [x] Out-of-hours orders are accepted as **pre-orders**, labelled as such on the checkout
      (before committing, not after), the confirmation page ("we'll confirm when we open at
      16:00", never the give-up "ring us" line), and the tablet (blue, *"Pre-order · placed
      00:55, 29 Jul"* instead of screaming red "660 min ago").
- [x] Nothing is auto-accepted. Accept/reject stays a human decision.

### "Leave it out" ticks (Imran asked for these directly)
- [x] No onion / lettuce / tomato / salad / mayo / ketchup / salsa / Algerian sauce, on
      burgers, wraps and the chicken plates.
- [x] **Deliberately NOT modifier rows.** They carry no price, so they ride on the line's
      `notes` field — already accepted by the API and already printed **in bold** by
      `print_service`. Zero backend change, zero re-seed.
- [x] Verified end to end, not assumed: placed through the real public endpoint, rendered
      the actual ESC/POS payload, decoded CP437 → `** No onion` present, `£` still `0x9C`.

### Email code (still sends nothing)
- [x] `Reply-To` added (`EMAIL_REPLY_TO`, falls back to `EMAIL_FROM`). A sending domain is
      not a mailbox — without it a customer's reply goes nowhere.
- [x] Email made **required** at storefront checkout.

### Tests
- [x] **373 passing**, up from 342. Same 12 pre-existing failures (10 QB Desktop, 1
      pay_first string, 1 void 401).
- [x] 31 new in `backend/tests/test_order_lifecycle_and_email.py`. The shipped lifecycle and
      email code had had **zero** tests; "342 passing" was hiding that.

### 🔺 Two silent deployment bugs found and fixed (see ERROR_LOG)
- [x] **The deploy script was eaten by its own `pg_dump`.** It ran as `ssh host << 'ENDSSH'`,
      so the server read it from stdin — and `docker compose exec` reads stdin too, so
      pg_dump swallowed the rest of the script. It stopped after the backup and reported
      success. **`alembic upgrade head` had therefore NEVER run from CI.** Migrations only
      ever applied because the backend's `start.sh` does them at boot.
- [x] **`git pull || true` hid a refused pull.** The server had a hand-edited
      `nginx.demo.conf`, so pull aborted; the frontend kept updating (it is rsync'd) while
      **the backend sat stale at `b0dbb6a`**. Resolved on the box **without discarding
      anything** — `git diff FETCH_HEAD` was empty, so that one path was stashed, pulled,
      stash dropped, md5 identical before and after. Backup at
      `/root/nginx.demo.conf.pre-pull-20260728-232309`.
- [x] Remote half is now `scripts/deploy-remote.sh`, scp'd and run **by path** with
      `ssh -n`. nginx is recreated **last**; verification checks **all three hostnames serve
      their own certificate** with a browser UA (the old `curl` health check could never
      have passed — the bot filter drops `curl/`).
- [x] **Four consecutive clean deploys since.** "Merge to main" is now a complete deploy
      with no hand-fixing.

### Deployed + verified on production
- [x] Migration `o1p2q3r4s5t6` (`orders.customer_email`) applied — confirmed in the
      backend's own upgrade log, not assumed.
- [x] `/ready`, `/complete`, `/paid` all return 401 unauthenticated (routes live + guarded).
- [x] All five hostnames 200, each on its own certificate; Orbit CRM untouched.
- [x] CORS from `chickshackg84.com` returns the allow-origin header.

### Client capture
- [x] Imran's **EposNow screen recording** transcribed and frame-captured →
      `_context/clients/chick-shack-uk/voice-notes/2026-07-29_imran_eposnow-menu-walkthrough.md`
      (+ frames in `refs/eposnow-menu/`). **It settles OI-45.**

---

## In Progress

- [ ] **Nothing mid-edit.** Working tree is clean for our files; everything committed and
      pushed.

## Pending — in order

- [ ] **1. TELL IMRAN THE SITE IS LIVE.** Orders can arrive at any moment. Give him
      `https://eats.sitaratech.info/online-orders?shop=chick-shack`. **Never** hand out
      `pos-demo.duckdns.org`.
- [ ] **2. Malik's own end-to-end test.** Full walkthrough was given in chat: log in at
      `https://eats.sitaratech.info/login?shop=chick-shack` (email+password, NOT PIN — PIN
      needs the tenant named), open the tablet URL, then order from `chickshackg84.com` in
      incognito. ⚠️ **A "Could not reach the printer" toast on a laptop is EXPECTED** — the
      `rawbt:` scheme only exists on Imran's Android tablet.
- [ ] **3. Email — THE NEXT TASK.** Provider chosen: **Mailjet free** (6,000/mo, 200/day,
      no card, SMTP relay, DKIM on free tier). Address `orders@chickshackg84.com`.
      **Full step-by-step in `docs/EMAIL_SETUP_RUNBOOK.md`.** Malik does the DNS; he asked
      for exact records. **One additive TXT record, nothing modified.**
- [ ] **4. UAT runs** — we order and Imran accepts; then he orders himself and drives it to
      delivered.
- [ ] **5. OI-45 menu modifiers** — now fully specified by the video, no schema change.
- [ ] **6. Stripe (OI-20)** — blocked on the client's account. **OI-46 must be built with
      it**: a prepaid pre-order that is rejected needs a refund, and the rejection screen
      currently says "nothing has been charged".

---

## Key Decisions

- **Solo vs Meal are separate products, not conditional modifiers.** From the video: EposNow
  has `PERI PERI WING MEALS` and `PERI PERI WINGS SOLO` as sibling categories. **This kills
  the hard part of OI-45** — both previously-proposed designs (a "No meal" first option, and
  a conditional-group schema change) are **withdrawn**. Zero schema change needed.
- **Exclusions are notes, not modifiers.** No price, nothing to validate, and the ticket
  already prints notes in bold. A closed tick-list rather than free text, because a kitchen
  ticket is read by a person at speed and free text invites "no unions".
- **Exclusions are part of the cart line key**, so a plain wrap and a no-onion wrap stay two
  lines. Persist version bumped to 3.
- **Never refuse an order on the clock.** Reversed my own gate. Take it as a pre-order.
- **Email: skip Mailjet's SPF instruction deliberately.** A domain may have only ONE SPF
  record, so following it means *editing* the live one on a domain carrying Imran's business
  email. It buys nothing: **DMARC passes if SPF OR DKIM aligns**, and our DKIM will align.
- **`mark_paid` on `/complete` says so on the button.** Settling silently would be dishonest.

## Files Modified (all committed)

**Frontend**: `src/pages/online-orders/OnlineOrdersPage.tsx`, `src/services/onlineOrdersApi.ts`
**Storefront**: `src/components/{Checkout,OrderConfirmation,ItemModal,CartPanel}.tsx`,
`src/lib/{api,delivery}.ts`, `src/store/cart.ts`, `src/types.ts`, `src/data/menu.ts`, `src/App.tsx`
**Backend**: `app/config.py`, `app/services/email_service.py`,
`tests/test_order_lifecycle_and_email.py` (new)
**CI**: `.github/workflows/deploy-production.yml`, `scripts/deploy-remote.sh` (new)
**Docs**: `STATE.md`, `ERROR_LOG.md`, `_state/open-items.md`,
`docs/DEPLOYMENT_PLAYBOOK.md` (new), `docs/EMAIL_SETUP_RUNBOOK.md` (new),
`_context/clients/chick-shack-uk/voice-notes/2026-07-29_imran_eposnow-menu-walkthrough.md` (new)

## Uncommitted Changes

All of this session's work is **committed and pushed**. The ~99 other dirty paths
(44 M / 13 D / 42 ??) are **pre-existing and belong to someone else** — a bulk edit adding a
QA notice to ~50 markdown docs, plus unstaged `PAUSE_CHECKPOINT_*` moves into
`docs/history/`. Left alone deliberately.
**Never `git add .` in this repo** — the production env file is tracked and holds live secrets.

## Errors & Resolutions

All three written up in full in `ERROR_LOG.md`:
- Deploy script truncated by its own `pg_dump` reading stdin → script moved to a file, `ssh -n`
- `git pull || true` hiding a refused pull, backend stale → pull failure now fatal
- Checkout had no opening-hours gate at all → replaced with pre-order labelling
- `.env.example` could not be edited (cred-guard refuses credential-shaped paths) → the email
  keys are documented in `docs/EMAIL_SETUP_RUNBOOK.md` instead. **Still open**, cosmetic.

## Critical Context

- **Deploying = `git push origin main`.** It now recreates nginx and verifies every hostname.
  Read `docs/DEPLOYMENT_PLAYBOOK.md` before touching the server.
- **Publishing the storefront is separate**: `cd storefront && npm run deploy` (Cloudflare
  Workers, not the droplet). Already done.
- **cred-guard blocks commands containing `--env-file .env.demo` and refuses to read/edit
  `.env*`.** Not a bug — work around it by splitting commands or writing commit messages to
  a file. Malik confirmed: *"cred guard is here so u dont echo back secrets, rest u have all
  access."*
- **nginx returns 444 to `curl`/`wget` UAs by design.** Always pass a browser `-A`.
- **The box is shared with Orbit CRM.** `docker ps -a` and check mounts before container ops.
- **Login sheets**: `C:\Users\Malik\Downloads\ChickShack-PRODUCTION.txt`. Never echo.
- **Shop hours 16:00–22:00 UK.** Avoid production work mid-service.
- Local stack up on `localhost:8090`; a few "Wiring Test" / "Exclusion Test" orders sit in the
  **local** chick-shack queue (OI-42). Production was written to only by real deploys.
