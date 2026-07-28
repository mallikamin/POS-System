# Chick Shack UK — workstream state

**Last updated:** 2026-07-27 (06:20 PKT) — client voice note at 06:05 confirmed the target feature set
and reopened the printing question. See `printing.md` and OI-31 / OI-32.
**Stage:** Building. Storefront live on the client's real domain; ordering deliberately disabled.
**Reference material** (transcript, proposal, menu, DNS dump): `_context/clients/chick-shack-uk/`

> ⚠️ **CORRECTION 2026-07-29 — the "Build status" table below is two days stale. Do not trust it.**
> Overtaken on 07-28 and 07-29: **printing is proven on the client's own printer** (item 11),
> the **order-queue tablet view is built and deployed** (item 10), the **public API is migrated,
> tenant-scoped and deployed to production** (item 5), and the **62-item menu + 11 delivery areas
> are seeded on production**. Item 8 (storefront wired to the real API) is the only one of these
> still genuinely open, and it is the current priority.
> `STATE.md` and `PAUSE_CHECKPOINT_2026-07-29.md` are authoritative until this file is rewritten.

---

## The deal in one paragraph

Chick Shack UK is a takeaway in Garelochhead, Scotland. This is **not** an EposNow displacement —
the client keeps EposNow for all in-house trade and wants an **online ordering channel alongside it**:
his own website with checkout, plus a tablet in the shop showing live online orders. His words:
*"a bit like a Uber Eats tablet or a Just Eat order pad."* The two systems run side by side and are
**deliberately not reconciled**; he was shown the split-books consequence and accepted it.

| | |
|---|---|
| Contact | **Imran R** — +44 7909 313456 |
| Introduced by | Faizan (+92 300 9458890), also the TastyBites contact |
| Commercials | **£300** build + **£35/month**. Nothing upfront; £300 due on go-live |
| Timeline quoted | 2 weeks from menu + hosting access (both received 2026-07-27) |
| Explicitly refused | QuickBooks or any accounting integration, EposNow integration, KDS, sales reconciliation |

⚠️ Name ambiguity, still unresolved: the call recording is `rizwan uk meeting.mp4` and a third name,
**Rizwan**, is referenced on the call. **Imran R** is the confirmed contact. Confirm before any named
document goes out.

---

## Build status

| # | Item | Status |
|---|---|---|
| 1 | Multi-currency / GBP formatter | ✅ Done |
| 2 | Storefront (menu, cart, checkout UI, delivery pricing) | ✅ Built |
| 3 | Deployed to Cloudflare Workers | ✅ Live |
| 4 | Custom domain `chickshackg84.com` | ✅ Live 2026-07-27 |
| 5 | `online` order_type + public ordering API | ✅ **Built 2026-07-27** — not yet migrated or run |
| 6 | Accept / reject + ETA on the order | ✅ **Built** — endpoints + columns |
| 7 | Stripe Checkout + signature-verified webhook | ⬜ **Next.** Blocked on the client's Stripe account |
| 8 | Storefront wired to the real API | ⬜ Still posts to nothing |
| 9 | Flip `SHOP.orderingEnabled` to `true` | ⬜ Gated on 7-8 |
| 10 | Order-queue tablet view (adapt existing KDS) | ⬜ |
| 11 | Printing | ⬜ See `printing.md`. **Not a launch blocker** |
| 12 | Sweep ~173 hardcoded `Rs.` literals in `frontend/src` | ⬜ |

**The client described the product in his own words on 2026-07-27 06:05, and it is items 6 + 10:**
*"the exact same tablet, which is connected [to a] printer. When an order comes in he either accepts
or rejects, and he can change the lead time for the delivery, or the time for collection."* That is
accept/reject with an adjustable ETA on a tablet order queue, and nothing more. **Item 10 is therefore
not a nice-to-have, it is the thing he thinks he is buying.** The server side of it already exists;
the tablet view does not. Scope item 10 to that description and resist adding to it.

### What landed in the backend 2026-07-27

**Migration `n0o1p2q3r4s5` — WRITTEN BUT NOT YET RUN.** Docker was down this session, so it has not
been applied anywhere, including locally. **Run and verify it before trusting any of the below.**

| File | What |
|---|---|
| `models/order.py` | `service_type`, `delivery_address`, `delivery_area`, `delivery_fee`, `accepted_at`, `rejected_at`, `rejection_reason`, `eta_minutes` |
| `models/delivery.py` | New `delivery_areas` table — tenant-scoped, code/name/fee |
| `models/restaurant_config.py` | `delivery_minimum` |
| `schemas/public_order.py` | Public request/response schemas |
| `services/public_order_service.py` | Server-side pricing, accept/reject |
| `api/v1/public.py` | `GET /public/menu`, `POST /public/orders`, status poll, manage accept/reject |
| `tests/test_public_ordering.py` | 18 tests, all passing |

**`order_type` needed no migration.** It is a plain `String(20)` with a comment, not a CHECK
constraint — the real constraint was a Pydantic pattern. Earlier notes implied otherwise.

### Three decisions in that code worth knowing

1. **The browser never sends a price.** The public item schema sets `extra="forbid"`, so posting
   `unit_price` returns 422 rather than being silently ignored. Every amount is recomputed from the
   database. This is the single most important property of the endpoint and
   `tests/test_public_ordering.py` exists to defend it.
2. **Modifiers are validated against the item they are applied to.** Without that check a caller
   could apply one item's negative-priced modifier (the seed menu has a -400 "Half serving") to any
   other item on the menu.
3. **Online orders get a dedicated non-login user** (`online-orders@system.local`, `is_active=False`)
   rather than making `Order.created_by` nullable. That column is relied on by reports, audit and the
   status log. Inactive also means it cannot participate in a PIN collision, since
   `authenticate_by_pin` only loops active users.

### Not wired up yet

- **The storefront still posts to nothing.** `place()` in `Checkout.tsx` fakes a reference. Connecting
  it to `POST /public/orders` is the next frontend job.
- **`delivery_areas` has no rows.** The 11 areas and the £5 minimum currently live only in
  `storefront/src/data/menu.ts`. They need seeding into the DB, or the server cannot price delivery.
- **No kitchen ticket is created on order placement**, by design — an online order is a request until
  the shop accepts it. The ticket fires on accept.

### Live URLs

- **https://chickshackg84.com** and **https://www.chickshackg84.com** — the client's real domain,
  the one printed on his menus. HTTP 200, Cloudflare SSL.
- `https://chick-shack-storefront.mallikamiin.workers.dev` — the same worker's default URL.

### ⚠️ Ordering is switched OFF on purpose

`SHOP.orderingEnabled = false` in `storefront/src/data/menu.ts`. Checkout shows the basket total and
asks the customer to phone. `place()` in `Checkout.tsx` fakes a reference and clears the basket — **no
order is created and no payment is taken.**

The printed menus already advertise `WWW.CHICKSHACKG84.COM`, so a browsable menu beats the 404
customers were getting. But **a fake order confirmation is worse than either.** Do not flip this flag
until items 5-7 are built and tested end to end.

**Do not present the current checkout to the client as working.**

---

## What is left to build, in order

**1. Public ordering API** (`backend/`)
- Add `online` to `order_type`. **No DB migration needed for this** — the column is a plain
  `String(20)` with only a comment (`backend/app/models/order.py:41-44`); the real constraint is a
  Pydantic pattern at `backend/app/schemas/order.py:35`.
- New unauthenticated `GET /public/menu` and `POST /public/orders`.
- ⚠️ **Server-side pricing is mandatory here.** The existing authenticated schema
  (`OrderItemCreate.unit_price`) **accepts the price from the client**. That is tolerable for a
  trusted till and unacceptable on a public endpoint. The public path needs its own schema taking
  **only IDs and quantities**, with every price re-read from the database.
- ⚠️ `Order.created_by` is `nullable=False` and FKs to `users`. A public order has no logged-in user,
  so this needs either a designated system user or a nullable column + migration. Decide deliberately.

**2. Accept / reject + ETA** — needs a migration (new columns). No such gate exists in the order state
machine today. How the ETA reaches the customer was never discussed; recommended default is on-screen
confirmation plus email, which adds no recurring cost.

**3. Stripe** — Checkout Session plus a **signature-verified, idempotent webhook**. Payment is
confirmed by the webhook only, never by the browser redirect. Cash on delivery is the same order left
unpaid. `PaymentGateway` is an abstract stub today, so this is the one genuinely from-scratch piece.

Reusable as-is: menu engine, orders, customers (phone lookup + history), admin dashboard and reports,
WebSockets.

---

## Menu and delivery — confirmed against the printed board

Transcribed from the client's official print-ready A4 PDF (artwork dated 05/2026), saved at
`_context/clients/chick-shack-uk/refs/`. **Every section was checked item by item against
`storefront/src/data/menu.ts` and all prices match.** Verified, not assumed.

### Delivery is priced BY VILLAGE, not by postcode

This would have been a real money bug. Nearly all these villages share the **same G84 outward code**,
so the postcode-prefix model built first quoted £3.00 for a £15.00 Arrochar run.

| Area | Fee | | Area | Fee |
|---|---|---|---|---|
| Garelochhead | £3.00 | | Rosneath | £4.50 |
| Greenfields Camp | £3.00 | | Caravan Park | £6.00 |
| Southgate & Shanden | £4.00 | | Kilcreggan & Cove | £7.00 |
| Mambeg, Clynder & Rahane | £4.00 | | Helensburgh | £10.00 |
| Portincaple | £4.00 | | Arrochar | £15.00 |
| Rhu | £4.50 | | | |

Checkout uses an area picker, which is also how the shop and its drivers already think about it.
**Delivery minimum £5.00.**

Also off the board: hours **Mon-Sun 16:00-22:00**, phones 01436 653 143 / 07719 566 889, allergen
notice (now shown at checkout), and "HOME DELIVERY OR COLLECTION" — delivery is not speculative.

Applied 2026-07-27 at Imran's request: removed Fanta Pineapple Grapefruit; added Rubicon Passionfruit
and Levi Roots Caribbean Crush at £1.79.

---

## Open questions for Imran

**Blocking the build:**
1. **Stripe account** — he says he has one. Is it verified and live, or newly created? Needs
   connecting. This gates the entire payment path.

**Not blocking, but needed before go-live:**
2. The board says *"A service fee may be applied for long distance deliveries"* — on top of the area
   fees, or already included?
3. Have prices moved since the 05/2026 print run?
4. Area spellings: the print reads *Potiancapl*, *Rosneth*, *Helensbrough*; the app renders
   **Portincaple, Rosneath, Helensburgh**. Cheap to revert if he wants the board wording verbatim.
5. Spare printer make / model / connection type.
6. Tablet Android + Chrome version (he sent a photo of the back only).
7. Logo / food photos.

**Owed to him, unprompted:** he asked *"which database is it?"* on the call and never got an answer.
It is **PostgreSQL 16**.

**Worth raising:** `chick-shack.com` is on the same Fasthosts account and is a far better
customer-facing URL than `chickshackg84.com`. His call, but customers have to type it.

---

## Commercial upside, and the risk in it

Imran offered to introduce 3-4 other UK operators, plus his uncle (**Ali Fish and Chips** — no EPOS at
all, pen and paper, currently being *"messed around"* by a local developer), plus "another two
people." Up to ~6 UK sites.

⚠️ **The uncle entry is now in doubt — OI-32.** The 2026-07-27 06:05 voice note describes an uncle who
**already runs tablet-plus-printer online ordering through another UK provider, working.** That is not
a pen-and-paper prospect. Either there are two uncles or one of the two records is wrong. Do not count
him as a lead until it is confirmed.

⚠️ Unqualified, and offered **before** he saw a price. He will quote his own price onward, so
**£300/£35 anchors the whole pipeline**, not just this one job. Logged as a known risk in
`decisions.md`; already argued and settled, do not re-litigate.
