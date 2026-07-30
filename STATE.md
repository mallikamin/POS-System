# STATE — Restaurant POS System

**Last refreshed:** 2026-07-31 (session J) · **Branch:** `main`

**Session J in one line:** Finished the photo-integration work session I left in progress
(`PAUSE_CHECKPOINT_2026-07-31.md`). Re-verified every proposed photo→item mapping in
`CLASSIFICATION.md` against real `menu.ts` descriptions before wiring anything in — rejected
6 of the 15 approved photos rather than force a bad fit, including two the first-pass
classification missed: a real Coca-Cola can in frame, and a third-party-branded "Chicken" box
with its own logo. 9 photos used (4 swapped in place, 5 new per-item overrides), each cropped
separately to thumb/hero sizes via ffmpeg. Deployed to Cloudflare and verified against the
**live** site (bundle + all 18 image URLs), not the deploy log — caught and confirmed-resolved
one transient bad response on first check. Full write-up: `_state/open-items.md` **OI-56**.
Commit `a361fc8`, pushed.

**Session H in one line:** Added a persistent "under testing, please call instead" banner to
every storefront view (commit `abea022`) — UAT with Imran hasn't happened yet and Stripe/menu
are still being tuned, but the site keeps taking real orders 24/7 in the meantime. Shipped via
`git push` first, which only deploys the POS/backend side; the storefront needed its own
`cd storefront && npm run deploy` (Cloudflare Workers), run and verified separately by fetching
the live bundle. **`docs/DEPLOYMENT_PLAYBOOK.md`'s one-line summary was rewritten** to state
both pipelines up front — see `ERROR_LOG.md` 2026-07-30 session H for the full incident. Banner
stays until Malik says to remove it; it is copy-only, does not disable checkout.

**Session G in one line:** OI-55 fully closed (Brevo authenticated + proved + branded HTML
shipped at `3ab141b`, deployed, verified live). Card payment (OI-41/H-6) investigated and
explained — not a bug, deliberately flagged off — but deferred: proving capture-on-accept
needs the shop genuinely open and someone accepting a real order, so Malik is resuming that
**next time the restaurant is open** (storefront itself shows "Opens 16:00" same day,
2026-07-30 — Malik said "tomorrow," so confirm which he means before assuming either).
**Loose end: order `260730-001` ("Chicken Fillet", placed to prove the HTML email) is a real
pre-order still sitting in the queue**, same situation as the two from earlier in the
session — nobody voided it. Give Imran a heads-up or void it via `reject_order` before he
opens, same pattern used twice already this session.
✅ Session E ended fully pushed and deployed at `7797af2` (the "held back Stripe commits" in an
earlier header version were pushed late in session E; Stripe live in **TEST mode**, keys verified
in the container). **Session F adds 4 commits — OI-51…OI-54 — and pushing them IS the deploy.**
That deploy runs migration `q3r4s5t6u7v8` (additive column on `restaurant_configs` + chick-shack
backfill by slug). Verify the effect after push per the playbook: deployed commit, schema
revision `q3r4s5t6u7v8` inside the backend container, every hostname's own certificate.

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
| Chick Shack storefront | ✅ **Live** on the client's real domain, Cloudflare SSL. 🟡 **Testing-mode banner up on every view since 2026-07-31** ("please do not place an order, call 07719 566 889 instead") — checkout itself is unchanged and still works, this is copy-only. Stays until Malik says remove it | `_state/chick-shack-uk.md` |
| Chick Shack ordering | 🔴 **LIVE, 24/7.** Out-of-hours orders are accepted as **pre-orders** and shown as such on all three surfaces. Accept/reject is always manual | `_state/chick-shack-uk.md` |
| Chick Shack tenant + menu in DB | ✅ **Seeded locally and on production 2026-07-28/29** — 8 categories, 62 items, 11 delivery areas, GBP. Logins verified | `_state/decisions.md` D-11 |
| Multi-tenant routing | ✅ **Fixed 2026-07-28.** Public routes keyed by slug; PIN login no longer searches across tenants | `_state/decisions.md` D-10 |
| Public ordering API | ✅ Built, tenant-scoped, queue endpoint. **Deployed 2026-07-29** | `_state/chick-shack-uk.md` |
| Order-queue tablet view | ✅ **Deployed with the full lifecycle** at `/online-orders`. Accept → out for delivery → delivered/paid; completed orders leave Active. **Not yet opened on Imran's real tablet** | `_state/open-items.md` OI-36 |
| Storefront checkout wiring | ✅ **Merged and PUBLISHED 2026-07-29.** Menu from the API, checkout posts, confirmation follows the order to delivered. Email required; "leave it out" ticks print on the ticket | `_state/open-items.md` OI-28 / OI-37 |
| API access from the storefront domain | ✅ **Fixed on the server 2026-07-29.** `CORS_ORIGINS` now allows both Chick Shack origins; preflight verified, unknown origins still refused | `_state/open-items.md` OI-40 |
| Stripe | 🔶 **DEPLOYED IN TEST MODE**, keys verified inside the container. Manual capture: authorise at checkout, **capture on Accept, cancel on Reject**, so a rejected order is never charged — this is exactly why proving it needs the shop genuinely open (Malik, 2026-07-30): the capture-on-accept step only fires when someone accepts a real order on the tablet. `cardPaymentEnabled` is **false** by design (not a bug — flagged off until a test card completes end to end, so no real customer's card gets silently declined against TEST keys). **Test override exists:** `chickshackg84.com/?card=1` shows the card button to whoever has that link only, `storefront/src/lib/cardPayment.ts`. **36 tests**, proven against the real sandbox. **Hardening H-1…H-10 done except H-6** — the four money-critical guards were **mutation-checked**, i.e. each was shown to fail when the code it defends is broken | `docs/STRIPE_HARDENING_CHECKLIST.md` · OI-20 / OI-41 |
| Printing | ✅ **ON PAPER (photographed 2026-07-29)**, and session F built Imran's two asks: **3 labelled copies per ticket in ONE payload** (one `rawbt:` navigation) and the **daily `#NNN` double-size at the top of each copy**. Byte-level verified + tested; **paper check on his printer still pending** | OI-51 / OI-52 ✅ built · `ERROR_LOG.md` |
| Served / delivered gap | ✅ **CLOSED and deployed.** Tablet has out-for-delivery / delivered / mark-paid; completed orders leave the Active tab; the customer's page follows it | `_state/open-items.md` OI-44 |
| Customer emails | ✅ **RESOLVED 2026-07-30 — Brevo live, real order proved it, then branded.** Order `260729-003`: confirmation delivered in 2 seconds, Gmail "Show original" — SPF PASS, DKIM PASS (`d=chickshackg84.com`), DMARC PASS. Domain authentication needed a fix along the way (Brevo requires its own DMARC record to flip `authenticated`; resolved by editing Imran's single `_dmarc` record in place, same `p=none` policy, not duplicating it). **Same session: all 4 emails (received/accepted/rejected/on_the_way) given branded HTML** — ink/flame/ember from `tailwind.config.js`, no logo (none exists), inline-style table layout for client compat, every customer-supplied string `html.escape()`'d (checkout form is public input). Shipped `3ab141b`, deployed, verified live via order `260730-001` — real Gmail screenshot confirms it renders as designed. Test suite: 45/45 email tests, 432/444 full suite (12 pre-existing, unrelated). Runbook: `docs/EMAIL_SETUP_RUNBOOK.md` | `_state/open-items.md` **OI-55** |
| Menu modifier prompts | ✅ **BUILT and deployed to production, 2026-07-31.** Peri-Peri Heat renamed to match his till; "make it a meal" is now 25 real Meal sibling products (drink + chips upgrade), not a flat +£3 tick. Exclusion ticks (no lettuce etc.) turned out to already be built. Verified against the live API: 87 items, no duplicates | `_state/open-items.md` OI-45 |
| Storefront photos | ✅ **9 real chunky-chicken-sourced photos live, replacing stock, deployed 2026-07-31.** 6 of 15 approved photos rejected on re-verification (2 for undisclosed trademark issues, 4 for product mismatch) rather than forced in. Verified against the live bundle + all 18 image URLs, not the deploy log | `_state/open-items.md` OI-56 |
| Backend test suite | ✅ **409 passing — run and verified 2026-07-29 session E**, not inherited. Session E started from a verified **393** (session D's "391" was two short) and added **16** for the Stripe hardening. Same **12 pre-existing failures** throughout (10 failed + 2 errors), all in QuickBooks-Desktop/parked code | `ERROR_LOG.md` |
| Core POS (10 phases) | ✅ Production, 98/99 UAT | `_state/pos-platform.md` |
| QuickBooks Online | ✅ Live. Sync is **manual by design**, not broken | `_state/pos-platform.md` |
| POS demo sites | ✅ Green (`pos-demo.duckdns.org`, `eats.sitaratech.info`) | `_state/infrastructure.md` |
| CI (`ci.yml`) | ❌ **Red on every commit.** Ruff + ESLint fail; Ruff exits before the test step, so **CI has never run the suite**. All findings are in parked code, none are live bugs. Deploys are a separate workflow and are green | `_state/open-items.md` OI-47 |
| Nightly demo-data cron | ❌ **Has never run** | `_state/open-items.md` OI-11 |

---

## 🔴 Next action — set by Imran's live walkthrough, 2026-07-29 (session E)

**Session F built all four walkthrough items** — details in `_state/open-items.md`:

1. ✅ **OI-51** — three copies per ticket, repeated **inside** the ESC/POS payload.
2. ✅ **OI-52** — daily `#NNN` double-size + "COPY n OF 3" on every copy. No new counter.
3. ✅ **OI-53** — `/orders` shows Accept (routes to the queue) and trims online orders;
   the server now **refuses** the generic `confirmed→in_kitchen` for online orders, which
   would have cooked food without ETA, capture or notification.
4. ✅ **OI-54** — `online_ordering_only` per-tenant flag; chick-shack lands on
   `/online-orders`. Migration backfills production by slug, so the deploy flips it.

Still to verify on the real tablet/printer: 3 slips with big numbers actually on paper.

5. ✅ **OI-55, email egress — DONE 2026-07-30.** Brevo authenticated, `BREVO_API_KEY` live
   on the server, real order `260729-003` delivered its confirmation email in 2 seconds with
   SPF/DKIM/DMARC all PASS. **Same session, also shipped:** branded HTML for all 4 emails
   (`3ab141b`), verified live via order `260730-001`. Closed.

## 🔴 Resume here (session G paused 2026-07-30 ~06:15 PKT)

1. **Void or flag order `260730-001`** before Imran opens — see note at the top of this file.
2. **Stripe card payment, next time the shop is open:** use `chickshackg84.com/?card=1` to
   reveal the card button (hidden from real customers on purpose), run a real TEST-mode card
   through checkout, then **accept the order on the tablet and confirm the capture actually
   fires** — that's OI-41, and it can only be proven with the shop live because capture is
   tied to a real Accept action, not to checkout.
3. **H-6** (dashboard-only, can be done anytime, doesn't need the shop open): register the
   webhook in the Stripe dashboard, then put `STRIPE_WEBHOOK_SECRET` on the server. Code side
   already done — see the checklist under H-6.
4. Once OI-41 + H-6 both close, flip `cardPaymentEnabled: true` in `storefront/src/data/menu.ts`
   and redeploy — that's what actually turns the card button on for real customers.

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
| **About to deploy anything** | `docs/DEPLOYMENT_PLAYBOOK.md` — **two separate pipelines.** `git push origin main` ships the POS backend/admin only; the Chick Shack **storefront** needs its own `cd storefront && npm run deploy` (Cloudflare Workers). A green push/Action proves nothing about the storefront — verify the live bundle. See `ERROR_LOG.md` 2026-07-30 session H |
| Touching a server, domain or DNS | `_state/infrastructure.md` **and** `memory/server-deployment-rules.md` |
| Touching the database | `memory/data-integrity.md` — **`pg_dump` first, no exceptions** |
| Debugging something odd | `ERROR_LOG.md` — it is a real log of real mistakes |
| About to re-argue a decision | `_state/decisions.md` — it may already be settled and logged |
| Picking up work | `_state/open-items.md` |

**Standing cautions.** The DigitalOcean box is **shared** with two other projects behind one nginx —
`docker ps -a` and check volume mounts before any container operation. `chickshackg84.com` carries
the client's **live email**; only ever touch its `A` and `www` records. Never echo a credential.
