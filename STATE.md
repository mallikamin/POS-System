# STATE — Restaurant POS System

**Last refreshed:** 2026-07-29 · **Branch:** `feat/storefront-checkout-wiring` · **HEAD:** `90190a2`, pushed
*(branched off `main` @ `6b00f78`. **Deliberately not on `main`:** a push to `main` triggers
`deploy-production.yml`, and every deploy leaves nginx on the old backend IP until it is recreated
by hand — which would 502 `eats.sitaratech.info`, the URL Imran's tablet uses.)*
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

**The storefront is live at https://chickshackg84.com — but it cannot take orders yet, by design.**

---

## Live status

| Area | Status | Detail |
|---|---|---|
| Chick Shack storefront | ✅ **Live** on the client's real domain, Cloudflare SSL | `_state/chick-shack-uk.md` |
| Chick Shack ordering | 🔒 **Deliberately OFF** — checkout asks the customer to phone | `_state/chick-shack-uk.md` |
| Chick Shack tenant + menu in DB | ✅ **Seeded locally and on production 2026-07-28/29** — 8 categories, 62 items, 11 delivery areas, GBP. Logins verified | `_state/decisions.md` D-11 |
| Multi-tenant routing | ✅ **Fixed 2026-07-28.** Public routes keyed by slug; PIN login no longer searches across tenants | `_state/decisions.md` D-10 |
| Public ordering API | ✅ Built, tenant-scoped, queue endpoint. **Deployed 2026-07-29** | `_state/chick-shack-uk.md` |
| Order-queue tablet view | ✅ **Built + deployed** at `/online-orders`. Whole chain verified end to end locally. **Not yet opened on Imran's real tablet** | `_state/open-items.md` OI-36 |
| Storefront checkout wiring | ✅ **Built + verified 2026-07-29** on `feat/storefront-checkout-wiring`. Menu from the API, checkout posts, confirmation polls. **Not merged, not published** | `_state/open-items.md` OI-28 / OI-37 |
| API access from the storefront domain | ✅ **Fixed on the server 2026-07-29.** `CORS_ORIGINS` now allows both Chick Shack origins; preflight verified, unknown origins still refused | `_state/open-items.md` OI-40 |
| Stripe | ⬜ Not started. Blocked on the client's account. Not needed for either UAT run | `_state/open-items.md` OI-20 |
| Printing | ✅ **PROVEN ON SITE 2026-07-28.** The tablet printed to his existing EposNow printer. £0 hardware. Our own bytes still not on paper | `_state/printing.md` |
| Served / delivered gap | ⬜ Accepted orders reach `in_kitchen` and stop. Active tab grows forever, takings never settle | `PAUSE_CHECKPOINT_2026-07-29.md` |
| Backend test suite | ✅ **342 passing** (2026-07-29), 12 pre-existing failures. Had been dead 2026-03-26 to 07-27 | `ERROR_LOG.md` |
| Core POS (10 phases) | ✅ Production, 98/99 UAT | `_state/pos-platform.md` |
| QuickBooks Online | ✅ Live. Sync is **manual by design**, not broken | `_state/pos-platform.md` |
| POS demo sites | ✅ Green (`pos-demo.duckdns.org`, `eats.sitaratech.info`) | `_state/infrastructure.md` |
| Nightly demo-data cron | ❌ **Has never run** | `_state/open-items.md` OI-11 |

---

## Next action

Printing is proven on the client's own hardware. The API is tenant-scoped and deployed, the queue
endpoint exists, the tablet view is live, and the menu is in the production database. What remains,
in order:

~~1. Wire the storefront checkout.~~ ✅ **Done 2026-07-29.** Menu comes from the API, checkout posts
a real order, the confirmation screen polls for the shop's answer, `orderingEnabled` is on.
Committed on `feat/storefront-checkout-wiring`, **not merged and not published.**

**The one remaining step before UAT is a single command**, and it is deliberately unrun:

```
cd storefront && npm run deploy        # builds + wrangler deploy
```

🔺 **That command is the UAT trigger, not a build step.** The moment it lands, ordering is live on
`chickshackg84.com` for any real customer, and every order goes to Imran's tablet. Run it only when
Imran is at the tablet and expecting it. `dist/` is already built and verified.

1. **UAT run 1**: we place an order, Imran accepts on the tablet, the ticket prints.
2. **UAT run 2**: Imran places the order himself on the website, then accepts it.
3. **The served / delivered gap.** An accepted order reaches `in_kitchen` and stops. Reuse the
   existing `ready → served → completed` machine and `PATCH /orders/{id}`. **Ask Imran** whether
   "Delivered" also marks a cash order paid, or whether that is a second tap.
4. **Stripe Checkout + signature-verified idempotent webhook.** Payment confirmed by webhook only.
   Not needed for either UAT run. Until it exists, `SHOP.cardPaymentEnabled` stays `false` and
   checkout offers only "pay on collection/delivery" — the server creates every order **unpaid**.

⚠️ **Do not merge this branch to `main` casually.** A push to `main` runs `deploy-production.yml`,
which redeploys the box and leaves nginx on the old backend IP — a 502 on `eats.sitaratech.info`,
the URL Imran's tablet uses, until nginx is recreated by hand.

🔺 **The client asked for this himself.** 2026-07-28 20:06 PKT, unprompted:
*"I need access to back end of website to accept orders."* That screen now exists and is deployed:
`https://eats.sitaratech.info/online-orders?shop=chick-shack`. **Never hand out
`pos-demo.duckdns.org`** — it works, but it is a demo URL.

**Waiting on the client (not blocking the build):**
- The **Stripe account** needs connecting (OI-20). Ask before starting step 5.
- **Is Chick Shack VAT registered?** (OI-38). Tax is seeded at 0 deliberately. Must be answered
  before real money moves.

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
