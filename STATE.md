# STATE — Restaurant POS System

**Last refreshed:** 2026-07-29 (session E) · **Branch:** `main` · **HEAD:** `a707a53`
🔴 **5 commits ahead of `origin/main` (= `447847a`). 4 of them are held back ON PURPOSE** —
`b884b0e`, `8ff61ce`, `889d5ad`, `9ebf896` (Stripe). **Pushing IS deploying**, and they change
`accept_order`, the exact path the UAT exercises. Push only after the UAT passes; the deploy then
runs migration `p2q3r4s5t6u7` (4 nullable columns on `orders`, additive, already applied locally).
The 5th, `a707a53`, is the session-D checkpoint doc and rides along with them.
**Everything up to `447847a` is pushed and deployed** (email/Mailjet included).

🔴 **THE STOREFRONT IS PUBLISHED AND `chickshackg84.com` IS TAKING REAL ORDERS, 24/7.**
Published 2026-07-29 ~00:30 UK. **There is no time gate** — an order placed while the shop is shut
is accepted as a **pre-order** and labelled as one on the website, the confirmation page and the
tablet. Refusing out-of-hours customers was tried and reversed: it loses the order to whoever is
still taking them. Nothing is auto-accepted; Imran's team still accepts or rejects every order by
hand. **Any real order now goes straight to his tablet — UAT is live.**

*2026-07-29 (late session): merged to `main` and deployed. The **whole order lifecycle** is now
wired end to end — tablet buttons for out-for-delivery / delivered / mark-paid, completed orders
leave the Active tab, and the customer's confirmation page follows it. Storefront gained required
email, **"leave it out" ticks** that print in bold on the kitchen ticket, and an ordering window.
Migration `o1p2q3r4s5t6` (`orders.customer_email`) **applied on production** — verified in the
backend's own upgrade log, not assumed. Backend suite **373 passing** (was 342), same 12
pre-existing failures — **re-run and verified at 373 on 2026-07-29 session D**, not inherited
from a checkpoint claim.*

*⚠️ **Two silent deployment bugs were found and fixed** — both had been live for an unknown
number of deploys. The deploy script was being truncated by its own `pg_dump` reading stdin, so
`alembic upgrade head` had **never run** from CI; and `git pull || true` was hiding a refused
pull, so the **backend had been stale on the server at `b0dbb6a`** while the frontend kept
updating. Full write-ups in `ERROR_LOG.md`. The deploy now recreates nginx itself and verifies
every hostname's certificate, so "merge to main" is a complete deploy with no hand-fixing.*

*~~Email still sends nothing: no SMTP provider and no sending domain chosen.~~ **Superseded
2026-07-29 session D** — Mailjet is wired, DKIM verified, 9 keys live in the running container,
`orders@chickshackg84.com` sends and receives. OI-43 is RESOLVED. **No real message has been sent
yet**; the UAT is the first one.*
*2026-07-29: everything below was **committed, pushed and deployed to production**. Migration
`n0o1p2q3r4s5` applied on the server, `chick-shack` seeded there (62 items), `eats.sitaratech.info`
finally given its own certificate. Backend suite 342 passing, same 12 pre-existing failures.
Prior sessions: `PAUSE_CHECKPOINT_2026-07-29.md`, `_state/sessions/2026-07-27_0700.md`.*
*2026-07-28: the printer prints, walked through remotely with Imran. Multi-tenant routing fixed
(a real cross-tenant PIN flaw), Chick Shack tenant + 62-item menu seeded, logins verified.*

> ⚠️ The 99 dirty paths in the working tree are **not** current work. They are a pre-existing bulk
> edit that added a QA notice to ~50 markdown docs, plus 13 unstaged `PAUSE_CHECKPOINT_*` moves into
> `docs/history/`. Left alone deliberately. **Never `git add .` in this repo** (`.env.demo` is tracked
> and carries live credentials).

**This file is the dashboard and the authoritative entry point. Read it first, then one topic file.**
Detail lives in `_state/`. History lives in `docs/history/` and is never current.
New here? → **`_state/README.md`**.

---

## Current focus

**Chick Shack UK — online ordering channel.** A UK takeaway keeps its EposNow till for in-house trade;
we supply the online channel alongside it: website with checkout, plus a tablet showing live orders.
£300 build + £35/month, paid at go-live. **Not a POS displacement.**

🔴 **The storefront is live at https://chickshackg84.com and TAKING ORDERS 24/7** — out-of-hours
orders are accepted as labelled pre-orders, never refused.

---

## Live status

| Area | Status | Detail |
|---|---|---|
| Chick Shack storefront | ✅ **Live** on the client's real domain, Cloudflare SSL | `_state/chick-shack-uk.md` |
| Chick Shack ordering | 🔴 **LIVE, 24/7.** Out-of-hours orders are accepted as **pre-orders** and shown as such on all three surfaces. Accept/reject is always manual | `_state/chick-shack-uk.md` |
| Chick Shack tenant + menu in DB | ✅ **Seeded locally and on production 2026-07-28/29** — 8 categories, 62 items, 11 delivery areas, GBP. Logins verified | `_state/decisions.md` D-11 |
| Multi-tenant routing | ✅ **Fixed 2026-07-28.** Public routes keyed by slug; PIN login no longer searches across tenants | `_state/decisions.md` D-10 |
| Public ordering API | ✅ Built, tenant-scoped, queue endpoint. **Deployed 2026-07-29** | `_state/chick-shack-uk.md` |
| Order-queue tablet view | ✅ **Deployed with the full lifecycle** at `/online-orders`. Accept → out for delivery → delivered/paid; completed orders leave Active. **Not yet opened on Imran's real tablet** | `_state/open-items.md` OI-36 |
| Storefront checkout wiring | ✅ **Merged and PUBLISHED 2026-07-29.** Menu from the API, checkout posts, confirmation follows the order to delivered. Email required; "leave it out" ticks print on the ticket | `_state/open-items.md` OI-28 / OI-37 |
| API access from the storefront domain | ✅ **Fixed on the server 2026-07-29.** `CORS_ORIGINS` now allows both Chick Shack origins; preflight verified, unknown origins still refused | `_state/open-items.md` OI-40 |
| Stripe | 🔶 **BUILT + HARDENED, not deployed.** Manual capture: authorise at checkout, **capture on Accept, cancel on Reject**, so a rejected order is never charged. **36 tests**, proven against the real sandbox. **Hardening H-1…H-10 done except H-6** (session E) — the four money-critical guards were **mutation-checked**, i.e. each was shown to fail when the code it defends is broken. `cardPaymentEnabled` still **false** | `docs/STRIPE_HARDENING_CHECKLIST.md` · OI-20 / OI-41 |
| Printing | ✅ **OUR OWN TICKET IS ON PAPER — 2026-07-29, first time.** Photographed. Needed a real fix: both print paths `await`ed a fetch before navigating to `rawbt:`, which ends the user gesture, and Chrome on Android then drops the handoff **silently** while the server logs a cheerful 200. URLs are now prefetched and the button navigates synchronously. **Wanted next: 3 copies + the daily number printed large** | OI-51 / OI-52 · `ERROR_LOG.md` |
| Served / delivered gap | ✅ **CLOSED and deployed.** Tablet has out-for-delivery / delivered / mark-paid; completed orders leave the Active tab; the customer's page follows it | `_state/open-items.md` OI-44 |
| Customer emails | 🔴 **CANNOT SEND FROM THIS SERVER.** The first real send failed: `TimeoutError`. Proven from the droplet — SMTP **25/465/587 time out** (DigitalOcean anti-spam block), **2525 resets**, and **`api.mailjet.com:443` TLS-resets** while Stripe and GitHub handshake fine from the same box. Credentials and DKIM are almost certainly fine; **the route is blocked**. Session D's "authenticated on 587/465" was run from Malik's laptop, not the server — which is exactly why this was missed | `_state/open-items.md` **OI-55** |
| Menu modifier prompts | ⏸️ **Parked to QC by Malik 03:09.** Imran wants a required Hot/Mild "Peri-Peri Heat" choice on peri items (easy, no schema change) **and** meal-contents choices (hard, conditional). Requirement still incomplete — he was mid-list | `_state/open-items.md` OI-45 |
| Backend test suite | ✅ **409 passing — run and verified 2026-07-29 session E**, not inherited. Session E started from a verified **393** (session D's "391" was two short) and added **16** for the Stripe hardening. Same **12 pre-existing failures** throughout (10 failed + 2 errors), all in QuickBooks-Desktop/parked code | `ERROR_LOG.md` |
| Core POS (10 phases) | ✅ Production, 98/99 UAT | `_state/pos-platform.md` |
| QuickBooks Online | ✅ Live. Sync is **manual by design**, not broken | `_state/pos-platform.md` |
| POS demo sites | ✅ Green (`pos-demo.duckdns.org`, `eats.sitaratech.info`) | `_state/infrastructure.md` |
| CI (`ci.yml`) | ❌ **Red on every commit.** Ruff + ESLint fail; Ruff exits before the test step, so **CI has never run the suite**. All findings are in parked code, none are live bugs. Deploys are a separate workflow and are green | `_state/open-items.md` OI-47 |
| Nightly demo-data cron | ❌ **Has never run** | `_state/open-items.md` OI-11 |

---

## 🔴 Next action — set by Imran's live walkthrough, 2026-07-29 (session E)

**Build these four first, in this order, then email.** All four came from Imran watching the
system work on his own tablet, so they are observed needs, not speculation.

1. **OI-51** — three copies of the ticket per accepted order (put the repeat in the ESC/POS
   payload, not three navigations).
2. **OI-52** — the daily number printed **large** on every copy, plus "COPY 1 OF 3".
   ⚠️ The numbering already exists and already resets daily. Do not build a counter.
3. **OI-53** — `/orders` has no Accept button; add it and trim the view for a website-only shop.
4. **OI-54** — the landing page offers Dine-In / Takeaway / Call Center, all dead ends for
   this client. Land on a dashboard or the queue instead. **Per-tenant, not global.**
5. **Then OI-55, email egress** — and note the ports question is already settled, so do not
   re-test SMTP.

*Everything below this line predates the walkthrough.*

## Next action

**Everything up to `447847a` is deployed and published.** `merge to main` is a complete deploy: it
recreates nginx itself and verifies every hostname's certificate, so there is no hand-fixing step.

🔴 **UAT is live NOW.** `chickshackg84.com` accepts orders at any hour and every one lands on
Imran's tablet at `https://eats.sitaratech.info/online-orders?shop=chick-shack`.

In order:

1. **The UAT with Imran** — order → **first real email send** → tablet → print → accept →
   out for delivery → delivered. He has never opened the tablet page on the real device
   (OI-36); that is still the single biggest untested link.
2. **Push the 4 held Stripe commits** once the UAT passes, and watch the deploy — it runs
   migration `p2q3r4s5t6u7`. Verify the *effect* (schema revision, container start time,
   deployed commit), never the exit code.
3. ✅ **Stripe hardening — DONE in session E except H-6.** H-1 to H-5 and H-7 to H-10 are
   fixed, tested and, for the four money-critical ones, **mutation-checked**. H-1 turned out
   to be safe today purely by luck and is now robust; see `ERROR_LOG.md`.
4. ⏳ **H-6, the only hardening item left, and it is a dashboard step for Malik:** register
   the webhook in Stripe, then put `STRIPE_WEBHOOK_SECRET` on the server. The **code half is
   already done** — all six Stripe keys are now declared in `docker-compose.demo.yml`, which
   they were **not** before (they would have been written to the env file and never reached
   the container: card silently off, deploy green). Exact steps are in the checklist under
   H-6.
5. **Storefront card UI** — `cardPaymentEnabled` stays `false` until a test card completes end
   to end (OI-41).
6. **OI-45 menu modifiers** (fully specified, no schema change) and **OI-48 time picker** (new,
   not built, not a tweak).

**Client answers now in hand:** not VAT registered (OI-38 closed, 0% tax is correct); charge on
acceptance (OI-46 dissolved); Stripe account live with a Developer seat (OI-20 closed); wants a
customer-chosen time (OI-48 raised).

---

## Read before you touch anything

| If you are… | Read |
|---|---|
| Working on the client build | `_state/chick-shack-uk.md` |
| Touching a server, domain or DNS | `_state/infrastructure.md` **and** `memory/server-deployment-rules.md` |
| Touching the database | `memory/data-integrity.md` — **`pg_dump` first, no exceptions** |
| Debugging something odd | `ERROR_LOG.md` — it is a real log of real mistakes |
| About to re-argue a decision | `_state/decisions.md` — it may already be settled and logged |
| Picking up work | `_state/open-items.md` |

**Standing cautions.** The DigitalOcean box is **shared** with two other projects behind one nginx —
`docker ps -a` and check volume mounts before any container operation. `chickshackg84.com` carries
the client's **live email**; only ever touch its `A` and `www` records. Never echo a credential.
