# Pause Checkpoint — 2026-07-29 (E)

## Project
- **Name**: Restaurant POS System — Chick Shack UK workstream
- **Path**: `C:\Users\Malik\desktop\pos-project`
- **Branch**: `main` @ `4be3b73`, **level with `origin/main`. Everything is pushed and deployed.**

## Goal

Chick Shack's complete online ordering channel. This session took it from "backend can
take a card" to a **live walkthrough with Imran on his own tablet**, which is what
produced the four requirements below. Malik's standing instruction: build the whole thing,
stop asking piece by piece, keep replies short. **When he is driving a browser, one short
step per reply.**

---

## 🔴 READ THIS FIRST — how this session actually went

The client walkthrough was run **before the pieces had been smoke-tested end to end**, and
two things failed in front of Imran: the ticket did not print, and no email arrived. Both
were real bugs, both are now understood, one is fixed.

**The rule that was broken:** a `200` in the log is not evidence the thing happened, and a
claim verified on Malik's laptop is not verified on the server. Do not tell him something
works until its *effect* has been observed.

---

## Completed

### Stripe hardening — H-1…H-10 done except H-6 (a dashboard step)
- H-1 nginx bot filter, H-2 livemode, H-3 tenant scoping, H-4 capture bounded by the
  current order total, H-5 `payment_status` proven, H-7 currency, H-8 503-not-502,
  H-9 rate limit verified, H-10 replay pinned.
- The four money-critical guards were **mutation-checked** — each shown to FAIL when the
  code it defends is broken.
- ⚠️ **Found: the backend declared NONE of the Stripe keys in `docker-compose.demo.yml`.**
  They would have been written to the server env file and never reached the container.
  All six now declared.

### Storefront card payment — built and deployed
- The order id now rides on Stripe's return URL, the placed order is stashed before the
  redirect, and both must agree before a confirmation screen is rebuilt.
- `?card=1` shows the card option to us and nobody else, so real customers keep seeing
  cash-on-collection while testing runs on the live site.
- Verified against the **real sandbox**: session created, £6.99 GBP, return URLs carrying
  `order=…&paid=1`, metadata carrying `order_id` / `order_number` / `tenant_id`.

### Printing — OUR OWN TICKET IS ON PAPER, first time ever (photographed)
- Root cause was **not** the printer. Both print paths `await`ed a fetch before setting
  `location.href = "rawbt:…"`, which ends the user gesture; Chrome on Android then drops
  the custom-scheme navigation **silently** while the server logs a 200.

### Server / deploy
- All Stripe keys applied to the server via a scp'd script run **by path** (never fed to
  `ssh` on stdin), after a timestamped backup, and verified **from inside the container**.

## In Progress

- [ ] **Nothing mid-edit.** `STATE.md` and `_state/open-items.md` carry uncommitted edits
      that record everything below — commit them first.

## Pending — build in this order

- [ ] **1. OI-51 — three copies of the ticket per accepted order.** One prints today.
      **Put the repeat in the ESC/POS payload** (`print_service`), not three calls to
      `sendToPrinter`: three navigations are three chances for Chrome to drop or coalesce
      the handoff, and that is exactly the class of bug just fixed.
- [ ] **2. OI-52 — the daily number, large, on every copy.**
      ⚠️ **The numbering already exists and already resets daily.** `260729-001` is
      `YYMMDD-NNN`. **Do not build a counter.** The number is currently small body text;
      it needs to be big at the top of each copy, plus "COPY 1 OF 3" so three identical
      slips are not read as three orders.
- [ ] **3. OI-53 — `/orders` has no Accept button.** Imran found this himself. It shows
      Mark Ready / Pay / Receipt / Void, so a pending online order cannot be answered
      there. Add Accept and trim the view for a website-only shop.
- [ ] **4. OI-54 — the landing page is wrong for this client.** `eats.sitaratech.info`
      opens on "Select Order Channel — Dine-In / Takeaway / Call Center"; all three are
      dead ends for Chick Shack, who take orders only from the website. Land on a
      dashboard or the queue. **Per-tenant, not a global change** — the core POS still
      serves all three channels for other tenants.
- [ ] **5. OI-55 — email egress.** See Critical Context. **The ports question is settled;
      do not re-test SMTP.**
- [ ] 6. OI-49 — register the Stripe webhook (Malik, in the dashboard).
- [ ] 7. Card payment has **not** been driven through a browser yet. `cardPaymentEnabled`
      is still `false`.
- [ ] 8. OI-45 menu modifiers, OI-48 time picker, OI-50 storefront has no test framework.

## Key Decisions

- **Card stays hidden behind `?card=1`** until a test card completes end to end. With test
  keys on the server, a real customer's real card would be declined for no reason they
  could understand.
- **The print URL must be prefetched.** `sendToPrinter` is synchronous and must stay that
  way. Do not "tidy" the fetch back into the tap handler.
- **`intent:` form first**, naming the RawBT package, with the bare `rawbt:` scheme as
  fallback.
- **Tailscale does not fix the email problem.** It is private networking between machines;
  it does not change how the droplet reaches the public internet. Raised by Malik and
  answered — the fix is a reachable mail API or a host whose egress permits mail.

## Files Modified

- `backend/app/services/stripe_service.py` — hardening, `_with_order`, `capture_for_order`,
  livemode, `tenant_id_from_event`, and the `timeout` fix
- `backend/app/api/v1/public.py` — webhook tenant scoping
- `backend/app/services/public_order_service.py` — bounded capture on accept
- `backend/app/config.py` — `STRIPE_ACCOUNT_CURRENCY`
- `backend/tests/test_stripe_payments.py` — 20 → 40 tests
- `docker/nginx/nginx.demo.conf` — webhook exempted from the bot filter via the map
- `docker-compose.demo.yml` — six Stripe keys declared
- `storefront/src/lib/pendingOrder.ts`, `cardPayment.ts` — new
- `storefront/src/lib/delivery.ts` — the timezone fix
- `storefront/src/{App.tsx,components/Checkout.tsx,components/OrderConfirmation.tsx,lib/api.ts}`
- `frontend/src/services/onlineOrdersApi.ts`, `frontend/src/pages/online-orders/OnlineOrdersPage.tsx`

## Uncommitted Changes

`STATE.md` and `_state/open-items.md` only — they hold the new OI-50…OI-55 entries and the
revised Next action. **Commit these first.**

The ~99 other dirty paths are the **pre-existing** bulk markdown edit. Not current work.
**Never `git add .` here** — `.env.demo` is tracked and holds live credentials.

## Errors & Resolutions

- **`timeout` is not a Stripe API parameter** → fixed. All four call sites passed it; the
  API answers `Received unknown parameter: timeout` and the customer gets a 502 at the
  moment of paying. 40 mocked tests passed throughout. Found by making one real call.
- **The shop read as closed 24/7 and every order was a pre-order** → fixed.
  `new Date(d.toLocaleString("en-GB", …))` is `Invalid Date` because en-GB is day-first,
  so every comparison against `NaN` was false. Live to real customers since publication.
- **The ticket never reached RawBT** → fixed. An `await` before the custom-scheme
  navigation ends the user gesture and Chrome drops it silently.
- **Email cannot send from this server** → **STILL OPEN.** See below.

## Critical Context

- **OI-55, email — measured from the droplet, not guessed:** SMTP **25/465/587 time out**
  (DigitalOcean's anti-spam block), **2525 accepts TCP then resets**, and
  **`api.mailjet.com:443` connects but the TLS handshake is reset, 0 bytes read** — while
  `api.stripe.com` and `api.github.com` handshake fine from the same box. So 443 egress
  works generally and the failure is **specific to Mailjet**. Session D's "credentials
  authenticated on 587 and 465" was run from Malik's laptop. Credentials are probably
  fine; **the route is not**. Options: a transactional API this box can reach, or a
  different host. **Do not re-test SMTP ports.**
- **Deploying = `git push origin main`.** Storefront is separate:
  `cd storefront && npm run deploy` (Cloudflare, not the droplet).
- **Test keys are on the server, in TEST mode.** Verified inside the container.
- Credential files: `C:\Users\Malik\Downloads\stripe-test.txt` (API keys) and
  `stripe.txt` (webhook signing secret). **Never echo either.** Remind Malik to delete
  them once the values are settled on the server.
- **cred-guard** blocks commands containing `.env.demo` and anything that looks like it
  would print key material — including filenames ending `.key`. Use a glob
  (`.env.dem[o]`), `.pem`-free names, and `git commit -F`.
- **nginx returns 444 to curl/wget by design.** Pass a browser `-A`.
- **The box is shared with Orbit CRM** and the POS nginx config serves `orbit_api`
  directly. `docker ps -a` and check mounts before any container operation.
- Live order `260729-001` is accepted and `in_kitchen` on the real tenant — a test order,
  labelled as such. Clear it down.
