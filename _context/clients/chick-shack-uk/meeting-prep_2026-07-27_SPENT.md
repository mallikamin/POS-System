# Chick Shack UK — Meeting Prep (2026-07-27)

**Attendees:** Imran R (+44 7909 313456), Faizan (+92 300 9458890), Malik
**Background facts:** `docs/CHICK_SHACK_UK_DISCOVERY_2026-07-26.md`
**Build status:** approved but NOT started as of 2026-07-26. Nothing new has been built since.

---

## 1. PRE-MEETING CHECKS (do these before the call)

- [ ] **Load the demo in a browser** — https://eats.sitaratech.info/login and https://pos-demo.duckdns.org
      Last verified **2026-07-15, 11 days ago**. This project has a documented history of "verified working"
      claims that were false (see STATE.md "Unverified claims"). Do not walk into a live demo assuming it's up.
      Credentials: `demo@demo.kitchen` / password `demo123` / PIN `1111`
- [ ] **Check the demo data doesn't look stale** — the nightly demo-refresh cron has **never actually run**
      (known broken). Order dates/figures may look old or odd on screen.
- [ ] **Decide whether the 1-pager goes in the room.** `EXECUTIVE-SUMMARY-1PAGER.md:35` markets
      "Online Ordering (branded portal, zero commission)" and "QR Table Ordering" as *current* features.
      **Neither exists.** Line 65 of the same doc correctly puts them in a future phase — it contradicts itself.
      Either don't hand it over, or correct line 35 first.

---

## 2. THE DEMO WILL SHOW RUPEES

The frontend hard-codes PKR (140 `formatPKR()` call sites, 173 literal `Rs.` strings). A live demo to a
UK client will display **Rs.** on every price.

**Have the answer ready:** currency is a per-restaurant configuration — the field already exists in the
backend (`restaurant_config.currency`) — and their instance will be set to GBP. That is accurate. The
frontend sweep to honour it is ~1-2 days and is first in the build queue.

Don't let it be discovered mid-demo without a prepared line.

---

## 3. QUESTIONS TO ASK — in priority order

**#1 — the one that sets the timeline:**
> **"When did the 12-month EposNow contract start?"**

He said *"12month contract then we own the equipment."* If he's early in the term, switching means paying
two subscriptions or an exit penalty, and he doesn't own the hardware yet either. **This single answer
sets the realistic go-live date.** Ask it early — it reframes everything else.

**#2 — Counter printer** (he promised this info):
- Make and model of the **integrated** counter printer?
- Is it Ethernet/WiFi, or USB into the till?
  - Ethernet → we drive it directly, same as the kitchen printer. Clean.
  - USB into the locked Android till → he needs a separate device, and we need a local print bridge on it.

**#3 — The one-minute test:**
> "Can you open Chrome on the till and load any website — google.com will do?"

Decides whether he reuses the existing screen or buys a tablet. He hasn't tried it. Ask him to try it live.

**#4 — Operational:**
- How reliable is the internet at the shop? *(We have no offline mode — if the line drops, the till stops.
  Better raised by us now than discovered on a Friday night.)*
- Busy-night order volume and peak hour?
- Is the cash drawer kicked by the counter printer? *(If yes, our printing work covers it for free.)*
- One site, or more planned?

**#5 — Website scope** (biggest variable in the quote):
- Collection only, or delivery too? Delivery means addresses, zones, and delivery fees.
- Does he want a full brand website (about/contact/gallery) or just an ordering page?
- Who owns the domain? Does one exist?
- Stripe account — is it already verified and live, or newly created?

---

## 4. WHAT IS TRUE — say this confidently

- **Runs in a browser. No app to install.** Verified: pure React SPA over HTTPS, no native wrapper.
  Works on Android, Windows, iPad — this is a genuine advantage over locked vendor hardware.
- **Core POS is real and deployed** — 10 phases complete, 98/99 UAT pass, live on a server today.
  Dine-in, takeaway, call-centre ordering, payments, split payments, refunds, cash drawer sessions,
  Z-reports, staff management, reporting, audit logging.
- **QuickBooks Online integration is live in production** — real company connected, 19 account mappings,
  sync tested end-to-end. (Currently manual sync, by design.)
- **Kitchen Display System is fully built** — he declined it (*"Don't need one just a printer Is ok"*),
  but it's there if he changes his mind, at no extra build cost.
- **No commission, no per-terminal vendor lock-in** — contrast with the EposNow subscription model.

## 5. WHAT IS NOT BUILT — do not imply otherwise

| Feature | Reality |
|---|---|
| Thermal / network printing | **Not built.** Browser print dialog only today. Approved to build. |
| Kitchen ticket printing | **Not built.** KDS is screen-only. This is his stated requirement. |
| Website + checkout | **Not built.** Full build. |
| Stripe / any payment gateway | **Not built.** Adapter is an empty stub. |
| GBP / multi-currency | **Not built** in the frontend. Backend field exists. |
| Offline mode | **Not built.** No local queue, no caching. |
| QR ordering | **Not built.** Roadmap only. |
| Aggregator integrations (Just Eat etc.) | **Not built** — and he has no platforms, so not needed. |

**Safe framing:** these are scoped, approved, and short — not speculative. Give a timeline only after
question #1 is answered, because his contract end date, not our build speed, is likely the binding constraint.

---

## 6. COMMERCIAL NOTES

- **Faizan is in the group and TastyBites runs the same EposNow system** (*"It's the same system as tasty
  bites"*). One displacement build — printing, storefront, multi-currency — serves both leads. Relevant to
  how much custom work is worth absorbing here.
- **He has no delivery platforms at all.** So the website isn't a commission-saving alternative to Just Eat —
  it would be his *only* online channel. That's a bigger promise and a bigger opportunity: no existing volume
  to migrate (low risk), but also no proven online demand (he may expect traffic the site won't create by itself).
  Worth setting expectations that a website is an ordering channel, not a marketing engine.
- Card machine stays as-is (standalone). Only integrate it later if he asks — that's a separate gateway project.

---

## 7. AFTER THE MEETING — capture immediately

Update `docs/CHICK_SHACK_UK_DISCOVERY_2026-07-26.md` and `STATE.md` with: contract start date, counter
printer model, browser-test result, website scope decision, and anything committed to verbally.
