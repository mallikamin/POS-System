# Danny's UAT: findings log (internal, for the next round of fixes)

> **UAT PAUSED 2026-09-25 ~02:20 PKT at Step 12: Admin > Stock** (sections A-F1 walked).
> Malik: enough findings to build. Resume the walk from Admin > Stock after the fix round is
> deployed, and re-walk D-21 (kitchen > pay > stock) first.

Not for the client. Every finding from the walk, with its source screenshot in `uat-screens/`.
Status: OPEN until fixed AND re-walked in a browser.

| ID | Screen | Finding | Cause (if known) | Severity | Status |
|---|---|---|---|---|---|
| D-01 | A1 login (`A1-login.png`), A2 header | No Danny's logo. Login says "POS System"; header shows the tenant name as text only. Malik wants the Danny's logo on the login and main screens. | No per-tenant logo support on the login screen yet (login is shown before the shop is known unless `?shop=` is set). | Medium (first impression in the demo) | OPEN |
| D-02 | A2 channel select (`A2-channel-select.png`) | Six channel cards where four are expected. "Walk-in / Dine-in" duplicates Dine-In, "Phone Delivery" duplicates Call Center. Staff will not know which to press. | **Our seed.** `seed_dannys.py` created sales channels `direct` and `phone` with `pos_visible` left true, so they render as cards next to the order types. Only Foodpanda should be a card. | High (confusing on the first screen) | OPEN |
| D-03 | A1 login | URL drops `?shop=dannys` after load and shows `/login`. Login still worked, so the shop was remembered. Recorded only to confirm nothing is wrong. | By design (slug saved, then URL tidied). | None | CLOSED, works |
| D-05 | A3 floor (`A3-dine-in-floor-menu.png`) | Floors are wrong for Danny's. Malik: "probably 2 halls and 1 tree house". Seeded Main Hall (10) + Outdoor Terrace (6). | Our seed guessed. **Verbal, "probably": confirm table counts per area with Danny's.** | Medium | OPEN |
| D-06 | A3 floor | T1 shows amber with "Unreserve" / "Mark Available", i.e. reserved, on a fresh tenant. | Unknown. Possibly left by our 2026-09-24 API test order, or clicked during the walk. **Check before fixing.** | Low | OPEN, investigate |
| D-07 | A3 order panel (`A3-order-panel-cramped.png`) | Right-hand order panel too narrow. With 4 items, the item list is a small scroll box and the third item is cut off; Site / Channel / Charges / totals / handling take most of the height. Malik: panel should be wider, and the lower section collapsible so the whole order is visible. | Layout. | High (daily use by waiters) | OPEN |
| D-08 | A3 menu | No Half / Full portion choice. Tapping a dish adds it straight away. Malik expects to choose the portion on the dish. | **Our seed** made "Chicken Karahi (Half)" and "(Full)" separate items. Fix idea: one item per dish + required "Portion" modifier (Half / Full), each modifier carrying its own recipe (OI-99 supports modifier recipes), base item recipe-less, base price = Half, Full = +difference. Verify stock deduction per portion after. | High (core to a Pakistani menu) | OPEN |
| D-09 | A3 channel (`A3-channel-no-channel.png`) | Channel defaults to "No channel" on a dine-in order. Should default to the dine-in channel (Walk-in / Dine-in) automatically. | No default channel per order type. Also ties to D-02: once those duplicate cards are hidden, the dropdown default is how dine-in gets its channel. | Medium (reports by channel will be wrong if staff forget) | OPEN |
| D-10 | A3 order panel | Site dropdown truncates to "Danny's Canal E". For a single-site restaurant the Site picker could be hidden entirely. | Layout / single-location tenant. | Low | OPEN |
| D-11 | A3 totals | Tax line reads "GST (16%)". PRA restaurant tax in Punjab is usually shown as PST / Punjab Sales Tax on bills. **Ask Danny's what their current bills print.** | Label. | Low | OPEN, question |
| D-12 | C1 kitchen (`C1-kitchen-display.png`) | Kitchen Display is dark navy. Malik wants a lighter background. Check it stays readable from a distance under kitchen lighting. | Styling. | Medium | OPEN |
| D-13 | C1 kitchen | Ticket #260924-001 sits in NEW at 243 min, though that order is completed and paid (our 2026-09-24 API test). Completing an order does not close its kitchen ticket, so the board fills with ghosts whenever the POS moves an order on without the kitchen bumping it. | Order status and kitchen ticket status are not synced on completion (walked via `/orders/{id}/status` + payment). **Real product gap, not only test debris.** Clear #001 from the board before any demo. | High | OPEN |
| D-14 | C1 kitchen | Ticket shows "dine in" but no table number, and no waiter. The kitchen cannot tell whose food it is. | Ticket card does not render `table` / waiter. | High | OPEN |
| D-15 | C2 kitchen (`C2-served.png`) | SERVED column offers a **Complete** button to the kitchen. Unclear what it does to an unpaid dine-in order: if it completes the order it bypasses Settle Table / payment and the table session. **Test before the client sees it.** | Needs checking in code + walk. | High until checked | OPEN, investigate |
| D-16 | C2 kitchen | The Prep / Ready / Served progress labels under each ticket are tiny and faint. Make the progress readable at a distance. | Styling, pairs with D-12. | Low | OPEN |
| D-17 | D1 payment (`D1-payment-mode.png`) | Cash amount pre-fills **6893.88** while every total on the page reads Rs 6,894. Pakistani cash has no paisa in practice; the cashier sees two different numbers for the same bill. Round the cash due to whole rupees (and say how, e.g. nearest rupee). | 16% of 5,943 = 950.88; display rounds, the amount field does not. | Medium | OPEN |
| D-18 | D1 receipt (`D1-receipt-preview.png`) | Order number **260924-002** on a receipt dated **25/09/2026 1:59 am**. The number's date part is yesterday: order numbers use the UTC date, not Pakistan time, so every order between 00:00 and 05:00 PKT gets the previous day's prefix. Danny's is open to ~1 am. | Order-number generator uses UTC date. **Verify in `order_service` before fixing.** Also check the daily counter resets at local midnight, and Z-report day boundaries. | High (end-of-day and audit confusion) | OPEN, verify |
| D-19 | D1 receipt | Receipt header prints the restaurant twice: "Danny's Restaurant Faisalabad (Demo)" then "Danny's Restaurant". | **Our seed**: `receipt_header` repeats the name. Make it address + phone + PRA/NTN number only. | Low | OPEN |
| D-20 | D1 settle | Worked: Settle Table shows the order, Paid / Due, and both bill totals side by side, Cash (16%) Rs 6,894 and Card (5%) Rs 6,240, both correct by hand. Recorded as a pass. | | None | PASS |
| **D-21** | D2 paid (`D2-fully-paid.png`) | **Stock was NOT deducted for the browser-walked order.** #260924-002 was served on the kitchen board and paid in full, the screen says "Session Fully Paid", yet in the DB (checked 2026-09-25): order `status = in_kitchen`, `payment_status = paid`, kitchen ticket `served`, **0 inventory transactions**, and Table 1 already `available`. The order is stuck in `in_kitchen` for ever and never completes, so recipes never deduct. This is the headline flow of the Danny's pitch and it fails. | Kitchen ticket status and order status are separate state machines: KDS **Serve** moves the ticket, not the order. Payment auto-complete (fixed 2026-09-24) only fires when the ORDER is `served`, which never happens on this path. The 2026-09-24 API test passed only because it moved the order via `/orders/{id}/status`, which no one does in the real flow. **Lesson: API-verified was not verified, again.** Fix: KDS transitions must drive the order (ticket served, all tickets for the order served, then order `served`), AND a fully paid order past the kitchen must complete. Then re-walk in the browser and check `inventory_transactions`. Same root as D-13. | **Critical** | OPEN |
| D-22 | D2 paid | Tendered Rs 7,000, change stored as Rs 106.12 (paisa again, see D-17). The screen shown did not display the change to give back. Check the change is shown clearly, in whole rupees. | Rounding (D-17) + UI. | Medium | OPEN, check |
| D-21 update | E1 orders (`E1-orders-stuck-in-kitchen.png`) | Confirmed in the UI: Orders > Active shows #260924-002 as **In Kitchen** with "Mark Ready" as the main action, 9 minutes after the kitchen served it and the bill was paid. Staff would see a paid, eaten order as still cooking. | Same as D-21. | Critical | OPEN |
| D-23 | E1 orders | Order card says **5 items**; the kitchen ticket for the same order says **7 items**. One counts lines, the other counts quantities. Pick one (quantities, as the kitchen does) and use it everywhere. | Inconsistent counting. | Low | OPEN |
| D-24 | E1 orders | Order card has no **Paid** badge. Only the presence of a Refund button hints it is paid. Staff cannot see paid / unpaid at a glance. | Card does not show `payment_status`. | Medium | OPEN |
| D-21 code | | Confirmed in code 2026-09-25: `kitchen_service.transition_ticket` (`kitchen_service.py:170`) sets only `ticket.status` and timestamps; `api/v1/kitchen.py` never calls `order_service`. Kitchen and order state machines are fully disconnected. | | | |
| D-25 | E2 completed (`E2-completed-list.png`) | Two numbering formats side by side: seeded `DN-0001..0011` and live `260924-001`. And two labels for the same channel: `Dine-In` (#001, no channel set) vs `Walk-in / Dine-in`. Looks untidy in a demo. | **Our seed** (DN- numbers; #001 created by API with no channel). Renumber seeded orders to the live format and set channel; D-09 fixes new orders. | Low | OPEN |
| D-26 | E2 mark ready (`E2-mark-ready.png`) | POS **Mark Ready** works: card moves to Ready, button becomes **Mark Served**. Manual workaround path so far holds. | | None | PASS |
| D-27 | E3 (`E3-active-tab-flicker-all-orders.png`) | After **every** action on the Orders screen (Mark Ready, Mark Served, Complete), the **Active** tab briefly shows ALL orders (13, including every completed one) before settling. Malik saw it on each click. A cashier could tap the wrong card in that moment. | Likely the refresh after an action fetches without the tab's status filter, then the filtered fetch replaces it (or two fetches race). **Check `OrdersPage` refetch.** | Medium | OPEN |
| D-28 | E3 (`E3-served-needs-complete.png`) | An order that is already **paid** and then marked **Served** does not complete itself; it waits in Active with a **Complete** button. Paid + served should be done. | Auto-complete only lives in the payment path (fires when paying a served order), not in the served transition (serving a paid order). Fold into the D-21 fix: whichever of paid / served happens last completes the order. | High (part of D-21) | OPEN |
| D-21 workaround | E3 | **Workaround confirmed, 2026-09-25 02:15 PKT:** POS Mark Ready (02:10) > Mark Served (02:14) > Complete (02:15) took #260924-002 to `completed`, and stock was deducted: 4 consumption rows. So the inventory engine is fine; only the kitchen-to-order link is missing. | | | |
| D-29 | E3 | The 4 rows are all from **Egg Fried Rice** (rice, eggs, soy, oil): the only dish in that order with a recipe. Hot & Sour, Nuggets, Prawn Tempura and Walnut Brownie have no recipe, so they deducted nothing, correctly. **27 of 60 dishes have recipes.** A tester tapping at random will think inventory is broken. | **Our seed** covered 27 items. Either add recipes to all 60 before the client walks it, or tell testers which dishes carry recipes. Also consider flagging "no recipe" on the dish in admin. | High (for the demo) | OPEN |
| **D-30** | F1 dashboard (`F1-admin-dashboard.png`) | **"Today" on the dashboard is the UTC day, not Pakistan's.** At 02:16 PKT on 25 Sep it shows Today's Revenue Rs 20,271 from 4 orders, "+77.6% vs yesterday". DB check: those 4 are DN-0010 (24 Sep 13:15 PKT), DN-0011 (24 Sep 14:15), #001 (24 Sep 21:58) and #002 (25 Sep 01:59), i.e. every order since 00:00 **UTC** on the 24th. The true PKT "today" is 1 order, Rs 6,894. Top 5 Items has the same error. Every day from 00:00 to 05:00 PKT the owner sees yesterday's numbers as today's. | Dashboard KPIs bucket by UTC date. Same root as D-18 (order numbers). **One fix for both: every "day" boundary uses the tenant's `timezone` (`Asia/Karachi`).** Check Reports, Z-Report and the hourly chart too. | **High** (wrong money on the owner's first screen) | OPEN |
| D-31 | F1 sidebar (`F1-admin-menu-*.png`) | Admin sidebar lists 25 modules including QuickBooks Online, QB Desktop, Quotations, Tax Invoices, Transfers, Locations, Order Planner. Several mean nothing to a single-site Pakistani restaurant and make the product look complicated. | `hidden_ui_modules` exists per tenant (presentation only). Agree a trimmed list for Danny's, e.g. hide QuickBooks x2, Quotations, Tax Invoices, Transfers. **Keep Locations/Stock/Production.** | Medium | OPEN |
| D-32 | F1 dashboard | Live Operations shows an **Online** card; Danny's has no online ordering (Foodpanda is a separate channel). | Card list not driven by tenant's channels. | Low | OPEN |
| D-18 update | | **Confirmed in the DB:** #001 created 24/09 21:58 PKT, #002 created **25/09 01:59 PKT**, both prefixed 260924. | | | |
| D-04 | A2 header | Tenant name reads "Danny's Restaurant Faisalabad (Demo)". Fine for now; drop "(Demo)" if this becomes their live shop. | Seed `TENANT_NAME`. | Low | OPEN |

## Assets received

* `assets/signage-photo-1.png`, `assets/signage-photo-2.png`: photos of the outdoor Danny's
  signage (red script "Danny's"). **Not a usable logo file.** Ask Danny's for the logo as PNG
  (transparent background) or SVG. If none exists, the signage can be traced into a clean
  wordmark as a stop-gap, but say so to them.

## Build log

### Batch 1, 2026-09-25: kitchen and order move together (local, NOT deployed yet)

Fixes D-21, D-28, D-13, D-14, D-15, D-12, D-16.

* `kitchen_service.sync_order_from_tickets`: all tickets Ready -> order Ready; all Served ->
  order Served. Called from the ticket-status route in a savepoint, so a problem moving the order
  never blocks the kitchen. Dine-in, takeaway, call centre only; online orders untouched.
* `order_service.transition_order`: Served + already paid -> Completed (D-28), which runs the
  stock deduction. `_sync_tickets_to_order` moves tickets when the POS moves the order (Ready,
  Served, Completed, Voided), so no ghost tickets (D-13).
* `payment_service`: paying a Served order completes it for all three POS order types (was
  dine-in only) and closes its tickets.
* Kitchen queue: `served_within_minutes=30`; served tickets drop off after 30 min instead of
  accumulating for ever.
* Ticket shows **Table N · Waiter** (D-14), in both the page load and the live update message.
* Kitchen screen re-skinned light, larger text (D-12). Served tickets show "Served" instead of the
  dead **Complete** button (D-15: it had no next state and only raised an error).
* **D-16 correction:** the Prep / Ready / Served row is three jump buttons, not labels. Made
  readable (larger, darker, clearly disabled when not available).

Evidence: `tests/test_kitchen_order_sync.py`, 8 tests, all pass; mutation check (removing the
sync call) fails 3 of them. Full suite: 1,009 pass; the failures that remain fail identically on
committed HEAD (QB Desktop stale tests, void re-auth 401, 2 online date-filter tests, and the 2
from 2026-09-24). Frontend `npm run type-check` clean.
**NOT verified: nobody has clicked it. Re-walk D-21 in a browser after deploy.**

### Batch 2, 2026-09-25: the restaurant's own day, not UTC's (local, NOT deployed yet)

Fixes D-18, D-30.

* New `app/utils/tenant_time.py` (zone, tenant_timezone, local_now/today, local day/range
  bounds in UTC). One implementation for the whole backend.
* Order numbers use the tenant's local date (D-18). **Also changes Chick Shack**: its numbers
  now follow the UK date instead of UTC; only differs between 00:00 and 01:00 BST, when it is
  closed. Intended.
* Dashboard KPIs, today vs yesterday: local day bounds (D-30).
* Reports (summary, items, voids, payment methods, waiters): 12 UTC date casts -> local bounds.
  Hourly chart buckets by local hour (a 13:15 PKT lunch was in the 08:00 bar).
* Z-report: orders, payments, drawer sessions on the local day.
* Frontend Dashboard / Reports / Z-Report: "today", "yesterday", "week start", "month start"
  from the device's calendar via `utils/localDate.ts`, not `toISOString()` (UTC). Month start
  was the last day of the previous month in Pakistan.
* NOT changed (logged for later): PO / GRN / transfer / quotation number prefixes and the AI
  usage day still use UTC; `ExpensesPage`, `OnlineReportsPage`, QB sync dates still use
  `toISOString()`.

Evidence: `tests/test_tenant_local_day.py`, 5 tests at a fixed clock of 01:30 PKT; mutation
(zone forced to UTC) fails 4. Three UK order-number tests updated to expect the tenant's date
(they had hard-coded UTC and failed as the run crossed UK midnight). Full suite 1,011+ pass,
remaining failures identical to HEAD. `npm run type-check` clean.

### Batch 3, 2026-09-25: POS screens and Danny's data (local, NOT deployed yet)

Fixes D-02, D-05, D-07, D-08, D-09, D-10, D-17, D-19, D-22, D-23, D-24, D-27, D-29.

* D-07 order panel: `lg:w-80` -> `lg:w-96`; Channel / Site / Charges / kitchen-vs-direct fold
  behind one **Order options** row (collapsed, one-line summary always visible). Totals and the
  main button stay out. **All tenants**, including Martin's.
* D-09/D-10: empty channel reads **"Direct (no commission)"**; Site picker hidden when a tenant
  has one site.
* D-17/D-22: `minorToInputString` / `snapToDue` in `utils/currency.ts`. PKR box pre-fills whole
  rupees; posting within half a rupee of due posts the exact due (no 12-paisa overpay); change
  shows as Rs 106. AED/GBP keep decimals. Checked with 8 node cases, all pass.
* D-23: order lists count portions (sum of quantity), as the kitchen does.
* D-24: **Paid** / **Part paid** badge on open order cards.
* D-27: order-list reload after Mark Ready/Served/Complete/Void keeps the tab's filter (was
  loading every order, hence the flash of completed orders).
* Seed (`seed_dannys.py`, idempotent, also upgrades the existing tenant in place):
  - D-02 channels: Foodpanda only; "Walk-in / Dine-in" and "Phone Delivery" deactivated.
  - D-05 floors: Hall 1 (10), Hall 2 (6), Tree House (6, new). **Counts still a guess.**
  - D-08 portions: one dish + required "Portion" choice (Half +0 / Full +Rs 960/1,650/900) for
    Chicken Karahi, Mutton Karahi, Shahi Handi. Dish recipe = Half; Full modifier recipe = the
    extra. Old 6 Half/Full dishes hidden (past orders point at them).
  - D-29: 22 new ingredients, recipes for all 57 dishes on sale (was 27 of 60).
  - D-19: receipt header is the address only.
* Verified locally: upgrade path (over yesterday's tenant) and fresh path (from the pre-seed
  dump) both clean; every seeded order deducts; Mutton Karahi Full took 0.40 + 0.35 kg.
  **API walk of the exact failed browser path, 0 failures:** Full karahi -> kitchen
  preparing/ready/served -> order served -> cash paid -> completed -> chicken -1.0 kg, base
  -0.35 kg; order number 260925-001 while UTC was still the 24th; ticket shows T1.
* Full backend suite: 1,014 pass; the 5 failures are the ones proven to fail on HEAD.

### Not done (open)

* D-01 logo: need a real PNG/SVG from Danny's. D-04 "(Demo)" in the name. D-11 GST vs PST:
  ask Danny's. D-31 hidden admin modules: agree the list. D-32 Online card. D-25 seeded DN-
  numbers. D-06 T1 reserved: not reproduced; T1 was `available` in the DB at 02:05.
* Fish n Chips costs out at 59.5% on placeholder prices; tune if it distracts in the demo.
* UTC still used by PO/GRN/transfer/quotation numbers and some other pages (see batch 2).

### Deploy notes (next session)

* Batches 1-3 are committed LOCALLY, not pushed. Pushing to main deploys to production.
* **Visible to Martin (FZ LLC, in UAT)**: light kitchen screen, wider order panel with folded
  options, takeaway/call-centre orders auto-complete when served + paid, his order numbers and
  reports on Dubai time. Worth a line to him.
* After deploy: pg_dump, then re-run `seed_dannys.py` on prod (upgrades the tenant in place),
  run `walk_dannys.py https://eats.sitaratech.info --order` with `LOGIN_GAP=13`, then resume the
  browser UAT at Step 12 (Admin > Stock) and re-walk D-21 first.
