# STATE — Restaurant POS System

**Last refreshed:** 2026-07-28 23:30 PKT · **Branch:** `feat/chick-shack-storefront` · **HEAD:** `22150c5` (**still nothing committed** — two days of work is dirty in the tree)
*2026-07-28: **the printer prints**, walked through remotely with Imran. Then multi-tenant routing
fixed (a real cross-tenant PIN flaw), Chick Shack tenant + 62-item menu seeded, logins verified.
Backend suite 341 passing. Prior session: `_state/sessions/2026-07-27_0700.md`.*

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
| Chick Shack tenant + menu in DB | ✅ **Seeded 2026-07-28** — 8 categories, 62 items, GBP. Logins verified | `_state/decisions.md` D-11 |
| Multi-tenant routing | ✅ **Fixed 2026-07-28.** Public routes keyed by slug; PIN login no longer searches across tenants | `_state/decisions.md` D-10 |
| Public ordering API | ✅ Built + tenant-scoped + queue endpoint. **Not deployed** | `_state/chick-shack-uk.md` |
| Order-queue tablet view | ✅ **Built 2026-07-28** at `/online-orders`. Whole chain verified end to end locally | `_state/open-items.md` OI-36 |
| Stripe | ⬜ Not started. Blocked on the client's account | `_state/open-items.md` OI-20 |
| Printing | ✅ **PROVEN ON SITE 2026-07-28.** The tablet printed to his existing EposNow printer. £0 hardware. Our own bytes not yet tested | `_state/printing.md` |
| Order-queue tablet view | ⬜ **This is what the client thinks he is buying.** Server side exists, UI does not | `_state/chick-shack-uk.md` |
| Backend test suite | ✅ **Alive again** — 317 passing. Had been dead since 2026-03-26 | `ERROR_LOG.md` |
| Core POS (10 phases) | ✅ Production, 98/99 UAT | `_state/pos-platform.md` |
| QuickBooks Online | ✅ Live. Sync is **manual by design**, not broken | `_state/pos-platform.md` |
| POS demo sites | ✅ Green (`pos-demo.duckdns.org`, `eats.sitaratech.info`) | `_state/infrastructure.md` |
| Nightly demo-data cron | ❌ **Has never run** | `_state/open-items.md` OI-11 |

---

## Next action

Printing is proven on the client's own hardware. The API is tenant-scoped, the queue endpoint exists,
and the menu is in the database. What remains, in order:

1. ~~**Order-queue tablet view.**~~ ✅ **Built 2026-07-28** at `/online-orders`. Open it in a browser
   on a real tablet — that is the one thing not yet done.
2. **Wire the storefront checkout** to `POST /public/chick-shack/orders`. Now unblocked: the menu
   exists as rows, so the basket can carry real UUIDs. `place()` in `Checkout.tsx` still fabricates
   a reference. **The storefront should fetch `GET /public/chick-shack/menu` rather than keep using
   the hardcoded `menu.ts`.**
3. **Stripe Checkout + signature-verified idempotent webhook.** Payment confirmed by webhook only.
4. Only then flip `SHOP.orderingEnabled` to `true`.

**Not deployed.** Everything above runs locally only. The server still has the old code, the old
routes and no `chick-shack` tenant.

🔺 **The client is now pulling for item 1.** 2026-07-28 20:06 PKT, unprompted:
*"I need access to back end of website to accept orders."* Malik replied that he would send the direct
POS link. **That screen does not exist yet**, and the public ordering API is built but **not deployed
to the server** — so there is currently no link that would show him a Chick Shack order. Do not send
one until there is. See `_state/chick-shack-uk.md`.

**Waiting on the client (not blocking the build):**
- ~~RawBT test print~~ ✅ **Done 2026-07-28 — it prints.** See `_state/printing.md`.
- The **Stripe account** needs connecting (OI-20). Ask before starting step 3.

⚠️ **Housekeeping that is overdue:** nothing on this branch is committed. The storefront, the public
ordering API, the printing module and 45 new tests all sit as uncommitted working-tree changes on top
of a March commit. One power cut ends the week.

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
