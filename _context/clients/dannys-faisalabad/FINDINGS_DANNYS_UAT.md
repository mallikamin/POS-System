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
| **D-01 round 2** | A2 channel select (re-walk 2026-09-25 13:34 PKT) | **Still no logo after the round 1 deploy. Malik asked for it in round 1; I left D-01 open waiting for a clean PNG/SVG instead of shipping a placeholder.** Malik: use a placeholder, the demo is now. Logo now supplied: `assets/dannys-logo-from-malik.jpg` (160x160 JPG, gold on black marble). Build: show it on the login screen (when `?shop=dannys`) and in the POS header next to the tenant name. Use this JPG as is; swap for a vector later if they have one. | Our miss: waited for perfect instead of following the instruction. | **High, next round, first item** | OPEN |
| D-02 re-walk | A2 channel select | Four cards now: Dine-In, Takeaway, Call Center, Foodpanda. Duplicates gone. | | | PASS (browser, 2026-09-25) |
| D-08 re-walk | A3 (`R2-A3-portion-choice.png`) | Chicken Karahi asks Portion (required, choose 1): Half / Full +Rs 960. Full karahi Rs 2,849; GST 16% Rs 456; total Rs 3,305, correct by hand. Floors Hall 1 / Hall 2 / Tree House show. | | | PASS (browser) |
| D-33 | A3 menu, Pakistani (`R2-A3-portion-choice.png`) | 2nd and 4th dish cards in Pakistani show the same photo. | Seed image URLs. | Low | OPEN |
| **D-34** | A3 cart (`R2-A3-cart-7-items.png`, `R2-A3-cart-8th-hidden.png`, `R2-A3-cart-8th-after-scroll.png`) | Once the cart is taller than its box, a newly added item IS added (count 7 to 8 items, total updates) but lands below the fold; the order taker sees no change in the list until they scroll down, and gets confused. Malik: need a better way to show it. Fix: on add, scroll the cart list to the added line (or to the line whose qty went up) and flash-highlight it for ~1 s. Consider compact rows (qty stepper inline with the name) so more lines fit. 8-line total Rs 15,042 + GST 2,407 = 17,449, correct. | Cart list does not follow the newest line. | **High** (daily use, order-taker confusion) | OPEN |
| D-18 re-walk | B1 (`R2-B1-sent-to-kitchen.png`) | Send to Kitchen: "Order #260925-002 sent to kitchen!" at 13:47 PKT (today's Pakistan date). T5 turns red; Table Session shows Running Total / Due Rs 17,449 and Settle Table. | | | PASS (browser) |
| D-35 | B1 menu, Desserts (`R2-B1-sent-to-kitchen.png`) | Kunafa has no photo (grey plate icon); every other dessert has one. | Seed image missing (52 of 57 dishes have images). Use a placeholder photo, per the D-01 lesson. | Low | OPEN |
| D-12/D-14 re-walk | C1 (`R2-C1-kitchen-light.png`) | Kitchen screen is light, larger text; ticket #260925-002 shows **Table 5** and 8 items. No waiter line, because the order was taken with "No waiter" (expected). | | | PASS (browser) |
| **D-36** | C1 kitchen (`R2-C1-kitchen-light.png`) | Ticket lists **"Chicken Karahi" with no portion**. The kitchen cannot tell Half from Full, so the cook makes the wrong quantity. The POS cart showed "Full +Rs. 960"; the ticket drops the modifier. (Old ticket #260924-001 read "(Half)" only because the dish name carried it.) | Ticket card does not render order-item modifiers; check whether `kitchen_ticket_items` carries them at all. | **High** (wrong food out of the kitchen) | OPEN |
| D-13 residue | C1 kitchen | Ghost ticket **#260924-001** (the 09-24 API test order, completed and paid) still in NEW at 949 min. The fix stops new ghosts; this one pre-dates it. Clear before the client sees the board. | Test debris from before the sync fix. | High for the demo | OPEN, needs Malik's OK to clear on prod |
| **D-21 re-walk (kitchen half)** | C2/C3 (`R2-C2-kitchen-ready.png`, `R2-C2-orders-ready-synced.png`, `R2-C3-kitchen-served.png`, `R2-C3-orders-served-synced.png`) | Kitchen Start > Ready: Orders screen shows #260925-002 **Ready** (Mark Served). Kitchen Serve: Orders shows **Served**. The order now follows the kitchen. Served ticket shows a greyed "Served" label, no dead Complete button (D-15). Payment half still to walk. | | | PASS (browser, 13:53 PKT) |
| D-37 | C3 orders (`R2-C3-orders-served-synced.png`) | A served, **unpaid** dine-in order offers **Complete** as the main blue button. If it completes without payment, a waiter can close a table that never paid. **Check in code what Complete does on an unpaid order** before the demo; likely hide it (or make it "Settle") until paid. | **Confirmed in code 2026-09-25:** `order_service.transition_order` (`:733-756`) lets served -> completed through with no payment check; it frees the table and deducts stock, leaving a completed, unpaid order. Pay-first guards only confirmed -> in_kitchen. Fix: refuse completed for dine-in / takeaway / call-centre unless `payment_status == "paid"` (manager override with reason if needed); POS shows Settle / Pay instead of Complete until paid. Regression test. | **High** (unpaid table can be closed) | OPEN, confirmed |
| **D-21 re-walk (payment half)** | D1/D2 (`R2-D1-session-paid.png`, `R2-D2-order-completed.png`, `R2-D3-receipt.png`) | Settle Table, cash, tendered 18,000: Paid 17,449, Due 0, "Session Fully Paid". Order **Completed** by itself (no Complete press). Receipt: name once + address (D-19), "+ Full (+Rs. 960)" under the karahi, Tendered 18,000, **Change Rs 551** whole rupees (D-17/D-22). Card bill 15,042 + 5% = 15,794, correct. **DB (read-only, tenant-filtered):** order `completed / paid`, T5 `available`, **33 consumption rows**; Chicken (Karahi Cut) -0.5 -0.5 kg (Half + Full), Karahi Masala Base -0.2 (dish) -0.15 (Full) -0.2 (Prawn Masala), each matching the active recipes. **D-21 PASS end to end in the browser.** | | | PASS (browser + DB, 14:05 PKT) |
| **D-31 round 2** | F1 admin sidebar (`R2-F1-sidebar-bloated.png`) | Still ~25 flat entries after round 1. Malik: group them in collapsible sections; Settings = General + Menu, Staff, Customers, Roles, Discounts, Locations. "Can u do something in 1 single go or need spoonfeeding every time?" | Round 1 logged D-31 and did not build it. Our miss. | High | FIXED in batch 4 (below) |
| D-39 | Tax Invoices (`R2-F2-tax-invoices-aed.png`) | Tax Invoices visible to Danny's at all, and its sales list prints **"AED 17,448.72"** for a PKR restaurant. | Page fell back to a hard-coded "AED" until an invoice was opened. | High (wrong currency on screen) | FIXED in batch 4 |
| D-38 | Admin > Stock (`R2-F3-stock-no-images.png`) | Every ingredient shows the grey "no image" icon. Malik: use placeholder images. | Seed set no ingredient images. | Medium | FIXED in batch 4 |
| D-31 re-walk | F1 (`R3-F1-admin-grouped.png`) | Sidebar: Dashboard + Sales & Reports, Inventory, Purchasing, Settings, all collapsed. Invoicing and Integrations gone for Danny's. Logo in the POS header (`R3-A2-header-logo.png`). | | | PASS (browser) |
| D-30 re-walk | F1 | Today = 5 orders, Rs 34,737, which is the Pakistan day: #260924-002 (01:59 PKT today) + 260925-001..004. Top item Chicken Karahi 4 sold Rs 11,396 = 4 x 2,849, correct. **3 of the 5 are Claude's API test orders (001, 003, 004)**: they will show in the client demo unless voided or the day rolls over. | | | PASS (browser) |
| D-40 | F1 Hourly Sales (`R3-F1-admin-grouped.png`) | Hourly chart shows no visible bars (one faint marker near 14:00) although 5 orders are on the day. Check whether bars render at all or are too short to see. | Unknown, check `AdminDashboard` chart scaling. | Medium (owner's first screen) | OPEN, investigate |
| D-38 re-walk | G1 Stock (`R3-G1-stock-photos.png`) | Real photos on every stock row; Inventory group opened itself with Stock highlighted. Quantities after today's orders (e.g. Basmati 39.4 kg from 40) consistent with the D-21 deductions. | | | PASS (browser) |
| **D-41** | G2 Recipe Builder (`R3-G2-recipe-builder-modes.png`) | Malik: "danny will procure everything unlike martin producing something so their recipe management has to be organized accordingly." Builder offered Sub-recipe mode; seed had 7 in-house items (Karahi Masala Base, Naan Dough, marinades, sauces) with production runs. | Seed modelled Danny's like FZ LLC. | High (pitch is recipes) | FIXED batch 6 |
| **D-42** | G2 Recipe Builder (`R3-G2-recipe-three-karahis*.png`) | "Why are there 3 options?" Chicken Karahi, Chicken Karahi (Half), Chicken Karahi (Full) all listed. | Builder listed hidden (retired) dishes. | Medium | FIXED batch 6 |
| D-41/D-42 re-walk | G3 (`R3-G3-recipe-flattened*.png`) | Builder: only "Menu item recipe" and "Add-on or portion"; one Chicken Karahi (6 hidden behind the switch); Version 2 lists bought ingredients only (chicken 0.5, tomato 0.16, ginger 0.032, garlic 0.012, chilli 0.028, oil 0.04, spice 0.006, salt 0.003, butter 0.03, cream 0.03). | | | PASS (browser) |
| D-43 | G3 | "Where are the portions?" The Full portion's recipe was only on the Add-on tab; the dish showed no sign of it. | Builder did not relate a dish to its modifier recipes. | High | FIXED `e75e4f5`: "Portions and add-ons" panel under the dish recipe (per choice: price, what it adds, extra cost, Edit). |
| **D-44** | G4 Portions panel (`R3-G4-portions-panel-null-names.png`) | Panel renders, but Full reads "Adds null 0.5 kg, null 0.12 kg, ..." Extra cost Rs 477 is right. The Full recipe itself (`R3-G4-full-portion-recipe.png`) shows names correctly. | Panel reads `ingredient_name` from the recipe LIST (`GET /inventory/recipes`), which does not populate it; the single-recipe load does. Fix: populate `ingredient_name` in the list response (backend), or map names from the loaded `ingredients` array (frontend). Add a test that the list carries names. Correction 2026-09-26: NO endpoint filled it (list, get, create, edit all returned null); the recipe screen shows names because it maps them from its own ingredients list. | High (demo screen) | FIXED `c84e9df`: loaders eager-load each line's ingredient, `_enrich_recipe` names it on all four paths; route test fails without the fix. Local read of Danny's data: 332 lines, 0 unnamed. Browser PASS 2026-09-26 (Malik screenshot: Full lists every ingredient by name). |
| D-45 | G4 Portions panel | Half shows an "Add recipe" button next to "Nothing extra from stock: this is the base recipe above". Contradictory: Half should not invite a recipe. | Button shown for every choice without a recipe. | Medium | FIXED `c84e9df`: no-charge choice without a recipe shows no button. A paid add-on without a recipe keeps "Add recipe" and now reads "No recipe yet: selling it takes nothing off stock and adds no cost" (the old text called it the base recipe). Browser PASS 2026-09-26 (Malik screenshot: Half has no button). |
| D-46 | H1 Suppliers list | Lead time reads "1 days" (Canal Meat, Faisal Poultry). List otherwise PASS: 4 suppliers, terms, orders, spend. | Unpluralised label. | Low | OPEN, next batch |
| D-47 | H1 Supplier purchase history | PO date shows "9/24/2026" (US order); Pakistan reads 24/09/2026 and 5/9 would be ambiguous. Catalogue + history otherwise PASS (PO-260924-002 Rs 50,000 = 15 kg mutton x 2,400 + 10 kg beef mince x 1,400). | Browser-locale date formatting. | Low | OPEN, next batch (check other screens for the same) |
| D-48 | H2 Purchase orders list | Draft PO-260924-003 reads "2 lines still owed"; nothing is owed on an unsent order. List otherwise PASS: 3 POs, totals match supplier spend, actions per status right (Sent: Receive, Draft: Send, Received: Print only). | "Still owed" shown for any status with unreceived lines. | Low | OPEN, next batch: show it only once Sent / partly received |
| D-49 | Admin > Stock | No search box to find a particular ingredient in the stock list (Malik, 2026-09-26). | Missing feature. | Medium | OPEN, next batch |
| D-50 | Admin > Stock | Scrollbar is faint; needs to be visible and bold (Malik, 2026-09-26). | Default thin scrollbar styling. | Low | OPEN, next batch |
| D-51 | H2 Receive PO | Receive PO-260924-002 PASS: Beef Mince 19.382 -> 29.382 kg, Mutton 28.094 -> 43.094 kg (exact), PO now Received. But the GRN is numbered GRN-260925-001 at ~01:00 PKT on 26 Sep: PO/GRN/transfer numbers still use the UTC day (open item from 2026-09-25 ERROR_LOG). | Numbering not on `tenant_time`. | Medium | OPEN, next batch |
| D-52 | Reports > Top 10 / Bottom 5 | Show the product photo beside each item (we already have them). | Tables are text only. | Medium | OPEN, next batch |
| D-53 | Reports > Hourly Revenue | Chart ignores the end of the date range: `fetchHourlyBreakdown(dateFrom)` (`ReportsPage.tsx:129`), so This Week / This Month chart only the first day. Every other block on the page does follow the range (checked in code, lines 127-132). Yesterday's chart itself PASS (bars at 01, 11, 13, 14, 16 match the 7 orders). | Endpoint and call take one date. | High (wrong numbers on any multi-day range) | OPEN, next batch |
| D-54 | Reports > Bottom 5 | Hot & Sour Soup and Classic Cold Coffee appear in BOTH Top 10 and Bottom 5 (13 items sold on 25 Sep). An item cannot be a top and a bottom performer. | Bottom 5 not excluded from Top 10 when fewer than 15 items sold. | Medium | OPEN, next batch |
| D-55 | Reports + Dashboard cards | Comparison on major cards and Top 10: value vs the previous equivalent period, e.g. "Rs 93,428, down 5% from Rs 94,xxx last week". Today vs yesterday, This Week vs last week, This Month vs last month, custom range vs the same-length range before it. All dynamic with the filter (Malik, 2026-09-26). Build rule: compare like for like: a part-week is compared with the same elapsed days of last week, not the whole of last week, or every Monday reads "down 85%". | New. | High (owner-facing) | OPEN, next batch |
| D-56 | Reports: table-size analysis | Dine-in by seat count (`tables.capacity` already exists): orders, average order value, and what each size orders (e.g. 4-seaters mostly Chicken Karahi, 6-seaters add Mutton). Real figures only: show counts behind every claim and hide a pattern below a minimum sample; no generated prose. Depends on Danny's real table layout (D-05). | New. | Medium | OPEN, next batch |
| D-57 | Owner live feed | Live event list for the owner: "Tree House Table 1 settled their bill, Rs 14,xxx", "Hall 1 Table 4 placed an order", "Hall 2 Table 3 order moved to kitchen". Built from real order/kitchen/payment events (WebSocket `orders`/`floor` rooms exist), floor + table label + amount, no AI text. | New. | High (owner-facing) | OPEN, next batch |
| D-58 | Reports > Waiter Performance | "No waiter-assigned orders" for 25 Sep although all 7 were dine-in. Not yet checked whether the POS assigns a waiter to a dine-in order at all. | To investigate. | Medium | OPEN, check before next batch |
| (pass) | Reports + Z-Report, 25 Sep | Browser PASS 2026-09-26: Reports Today = 0 (PKT day), Yesterday 7 orders / Rs 41,667 / tax Rs 5,747 / all cash; Z-Report 25/09 identical. Cross-checked against the raw order list (`_files/2026-09-26/orders_for_day.py`): 7 completed + paid, Rs 41,667.20. 5 of the 7 are Claude API test orders (Rs 17,325). | - | - | PASS |
| D-59 | Login `?shop=dannys` | Logo, name, PIN pad PASS (browser, 2026-09-26). Browser tab still reads "POS System" with a generic globe icon. | Static `<title>` / favicon. | Low | OPEN, next batch: title + icon from `tenantBranding` |
| D-60 | Day summary (Malik, 2026-09-26) | One daily report: what the restaurant sold, cash vs card, how much inventory was used, what is left, and the cash position. | New. Build as an extension of the Z-Report (already has sales + cash/card), not a second daily screen that could disagree with it: add inventory consumed that day (from stock movements), closing stock, and cash position (opening float + cash taken - refunds - cash expenses = cash that should be in the drawer). | High (owner-facing) | OPEN, this batch |
| D-61 | Go-live: opening stock (Malik, 2026-09-26) | When Danny's starts, the owner must enter opening stock for every item in one go and carry on. Today stock can only be changed one row at a time ("Adjust Stock"). | Missing: a one-screen opening count (every active ingredient, quantity + cost), booked as an "opening stock" movement so history and the day summary read it correctly. | High (go-live) | FIXED LOCALLY 2026-09-26 (not deployed): Stock > "Opening Stock" dialog lists every active ingredient with its current figure and cost; only changed rows are sent. `POST /locations/stock/opening-count` books `counted - on hand` as a new `opening` movement type (ref `OPENING-yymmdd`), so re-saving moves nothing; a cost updates `cost_per_unit` except for produced or purchase-unit ingredients. 8 route tests incl. day summary excludes it (with an adjustment as positive control); fails when booked as `adjustment`. Caveat: used after go-live it would book shrinkage as "opening", not as an adjustment. Browser pending. |
| D-62 | Go-live: opening balances (Malik, 2026-09-26) | Opening cash in hand (and bank, if tracked) on day one. Today only a cash drawer session's opening float exists. | Missing. Scope with D-60 cash position, which must start from it. | High (go-live) | FIXED LOCALLY 2026-09-26 (not deployed), **cash only**: nothing tracks the bank (the POS never learns when card takings land), so a bank figure would drift; the finding said "if tracked". New `opening_balances` (one row per tenant, cash at the START of `as_of`), `GET/PUT /opening-balance`, card at the top of Purchasing > Other Income. Z-Report cash position adds "Cash in hand at start of day" = opening + every earlier day's net cash (same formula as net cash), and "Expected cash in hand at end of day"; nothing shown before the opening date. Floats not added (moved cash, not new money). Route test with a backdated real cash sale as positive control; fails when the payments leg is dropped. Local Postgres: today's start = yesterday's end. Browser pending. |
| D-63 | Other income / receipts (Malik, 2026-09-26) | Record money in that is not a sale (e.g. scrap sale, rent received, event deposit), per day, with category and cash/bank. | Missing: no income module. Must feed the D-60 day summary cash position. | Medium | FIXED LOCALLY 2026-09-26 (not deployed): Purchasing > Other Income (list, add, edit, delete; categories Scrap Sale, Rent Received, Event Deposit, Other, plus add-your-own). `method` is `cash` or `bank`, enforced (no free text). Cash rows enter the Z-Report cash position (`other_cash_in`, listed line by line) and the last drawer's expected cash, like cash expenses; bank rows never count as cash. Migration `c3d4e5f6a7b8` (3 new tables, nothing altered), round-tripped on local Postgres, CHECK constraints present. 6 route tests; fails when bank rows leak into cash. Local Postgres walk 0 failures. Browser pending. |
| D-64 | Expenses (Malik, 2026-09-26) | Salaries, admin, operational expenses. | EXISTS: Purchasing > Expenses, with categories and payment method (`models/expense.py`). To check in UAT: that Danny's has sensible categories (Salaries, Utilities, Rent, Admin, Repairs) and that cash expenses reduce the D-60 cash position. | Medium | CHECKED IN CODE 2026-09-26: defaults already include Rent, Salaries & Wages, Utilities, Repairs & Maintenance (seeded on first open of the screen); "Admin" is not a default. Cash expenses already reduce the cash position (payment method containing "cash"). To do after deploy: open Danny's list on prod, add "Admin" for Danny's only (not a new default, which would add it to every tenant). |
| (deploy) | Round 3, 2026-09-26 ~03:30 PKT | D-46..D-60 DEPLOYED in `619cfd8` (run 36197066196 success). Waiters Waqas/Bilal/Asad created on prod via Staff API (`_files/2026-09-26/add_dannys_waiters.py`, no login). Prod API check `_files/2026-09-26/check_round3_prod.py`: 0 failures (25 Sep 7 orders Rs 41,667.20; bottom 5 disjoint; photos on all top 10; hourly 24-26 Sep = 10 orders; table size 4-seaters 7 visits; KPIs compare to yesterday 03:34; Z-Report has inventory_used / stock_left / cash_position). Local suite: same 13 failed + 2 errors as baseline, 1052 passed. **Browser NOT yet clicked.** Open: drawer expected-cash double-subtracts change (`payment_service._calculate_expected_drawer_balance`), verified in code, awaiting Malik's decision. | - | - | DEPLOYED, browser pending |
| D-65 | Dashboard (browser, 2026-09-26 05:36) | Round 3 dashboard PASS: comparison "Down 100% vs yesterday: Rs 6,894 to 05:36" is right (0 sold today; yesterday's 01:59 order). But Avg Order Value also reads "Down 100%" with no orders today: an average of nothing is not a fall; should read "No orders yet". "Updated 5:36:15 AM" is 12-hour; the rest of the app is 24-hour. Also: live feed (10 s) showed order 260926-001 while the KPI cards (30 s) still read 0; refresh the cards with the feed. D-57 live feed browser PASS ("Hall 1, Table 1 placed an order: 1 item, Rs 3,305", 05:37). D-58 PASS: order 260926-001 carries waiter Waqas (Waiter), checked via orders API. Full feed walk PASS 05:37-05:40: placed, ready, settled (Cash Rs 3,305), served; order then completed + paid (API), Dine-In tile back to 0. Paid-but-Ready on the KDS is correct, not stale: payment does not serve food. | AOV compared even when today has 0 orders; `toLocaleTimeString()` default. | Low | FIXED LOCALLY 2026-09-26 (not deployed): AOV footer reads "No orders yet today" at 0 orders; "Updated" clock en-GB 24-hour; the feed calls the dashboard's reload when a refresh brings a new event (cards follow the feed, no extra polling); Z-Report channel line "1 order". Type-check clean. Browser pending. |
| D-66 | Dashboard > Table Utilization | Reads 0% with Hall 1 Table 1 occupied (browser, 05:37). Other cards PASS after refresh: Rs 3,305 "Down 52%" vs Rs 6,894 to 05:37 (correct), orders 1 vs 1 "No change", hourly bar at 05:00. | Pre-existing unit mismatch: backend `table_utilization` is a 0-1 fraction (`round(occupied/total, 2)` = 0.06 for 1 of 16), `AdminDashboard.tsx` shows `Math.round(value)%` and a bar of `value%` as if it were 0-100. | Medium (wrong number on the owner's screen) | FIXED LOCALLY 2026-09-26 (not deployed): `AdminDashboard.tsx` multiplies the fraction by 100 for the figure and the bar (1 of 16 = 6%). Browser pending. |
| (pass) | D-60 Z-Report day summary, 26 Sep (browser) | PASS. Inventory used Rs 1,028 = base Chicken Karahi recipe 550.95 + Full portion 477.46 (recipes API); chicken 1 kg = 0.5 + 0.5. Cash position Rs 3,305 = the cash payment; "no drawer opened" stated, no invented float. Stock left: Mutton 43.094 / Beef Mince 29.382 match the GRN; Mozzarella 2.42 < 5 flagged LOW. Small: "1 orders" under Sales by Channel (pre-existing), log with D-65. | - | - | PASS |
| D-67 | Cash drawer close (all tenants) | Expected cash subtracts change twice: payments store the bill amount (`amount`) with change separate, and `payment_service._calculate_expected_drawer_balance` subtracts `change_amount` again, so every cash sale needing change understates "expected" and reports the drawer short. Verified in code on all payment paths (single, split, session, session split). | Double count. | High (money, every tenant with a drawer) | FIXED LOCALLY 2026-09-26 (not deployed): change no longer subtracted in `payment_service._calculate_expected_drawer_balance`, the Z-Report drawer block, or the demo seed; D-60 cash position already correct. Test `test_change_given_is_not_counted_twice` passes, and fails with 505000 (Rs 50 short) when the old line is put back. Its first failure (drawer saw no sale) was a SQLite test artifact: second-resolution TEXT timestamps vs a bound `.000000`, so a same-second payment fell outside the window; Postgres unaffected; test opens the drawer 1 s earlier. Full suite 11 failed + 2 errors, all pre-existing. Past closed sessions keep their stored figures. |
| D-68 | Drawer close vs Z-Report drawer (found in code, 2026-09-26) | The two "expected in drawer" figures use different rules. Drawer close (`payment_service._calculate_expected_drawer_balance`): float + cash sales - refunds. Z-Report drawer block (D-60): the same minus the day's cash expenses plus (D-63) cash other income, charged to the last drawer of the day. On a day with a cash expense or cash income the close screen and the Z-Report disagree. | Two formulas for one figure. Expenses and income carry a date, not a time, so which session they belong to is a rule to choose, not a bug to patch. | Medium | OPEN, decision for Malik: should cash paid out / taken in outside sales count against the drawer at close? |
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

### Deploy, 2026-09-25 (UTC 05:52 to 06:40)

* Pushed `41270ce`; Deploy to Production green; live bundle `index-D3b8Rq9O.js` from release
  `41270ce` carries the batch 3 strings. CI and Staging workflows red, as on every push since
  09-06 (frontend lint across old files, not this change).
* pg_dump `/root/backups/pos-pre-reseed-dannys-20260925-060127.sql.gz` (2.2 MB, 62 tables,
  completion marker present), then `seed_dannys` on prod, rc 0.
* **New fault found by the walk: `/menu/full` returned 500 for Danny's.** The re-seed hid the 6
  old Half/Full dishes; `menu_service.get_full_menu` filtered them by reassigning
  `category.items`, and the request commit wrote `category_id = NULL` for them. Code from
  February, latent for every tenant, first hit here. Fixed with `set_committed_value` in
  `fb6b747`, regression test `tests/test_full_menu_hidden_items.py` (fails without the fix).
  Full suite 1,026 pass, failures all in the known-on-HEAD list. Deployed, green.
* `walk_dannys.py --order` on prod after the fix: **0 failures.** Order `260925-001` (T1, Full
  karahi + 2 roti) left in place, completed. Channel check did not run (script calls a wrong
  URL, 422); channel retirement seen only in the seed output.
* **Same pattern still live in `public_order_service.py:146-160`** (storefront menu: items,
  modifier groups, modifiers). Not fixed here: outside this scope and the file carries other
  uncommitted work. Raised with Malik.
* Still NOT verified: nobody has clicked batches 1-3 in a browser. Re-walk D-21 next.

### Batch 4, 2026-09-25 afternoon: everything open from the round 2 walk, in one go

Malik stopped the walk at Admin > Stock: fix it all at once, no more one-by-one. Fixes D-01,
D-13 residue, D-31, D-33, D-34, D-35, D-36, D-37, D-38, D-39.

* **D-31 admin menu:** grouped, collapsible sections (Dashboard; Sales & Reports; Inventory;
  Purchasing; B2B Invoicing; Integrations; Settings = General, Menu, Staff, Customers, Roles,
  Discounts, Locations). The group holding the current page opens itself. **All tenants**, Martin
  included; nothing removed, only grouped. Danny's hides QuickBooks x2, Transfers, Order Planner,
  Quotations, Tax Invoices through `hidden_ui_modules` (seed). New module slugs in `lib/modules.ts`.
* **D-39:** Tax Invoices uses the tenant's currency, not a hard-coded AED.
* **D-01 logo:** `lib/tenantBranding.ts` + `public/tenant-logos/dannys.jpg`. Login shows the logo
  and "Danny's Restaurant" when the shop is `dannys`; POS header shows the logo beside the name.
  Static file keyed by slug, no DB change, other tenants untouched.
* **D-38/D-35/D-33 images:** 76 drawn placeholder tiles (food icon on a group colour) in
  `public/placeholders/`, from `_files/2026-09-25/make_placeholders.py`; seed applies them to every
  ingredient without an image and to Roti, 3 naans, Kunafa and Prawn Masala (which had the karahi
  photo). An uploaded image is never replaced.
* **D-34 cart:** the line just added (or whose quantity went up) scrolls into view and flashes.
* **D-36 ticket portion:** ticket items carry `modifiers` (API + live event, required field, no
  default); kitchen card prints them in bold under the dish, and item notes in italics.
* **D-37:** backend refuses completed for an unpaid dine-in order ("Settle the bill"); the order
  card shows **Settle Bill** as the main button instead of Complete. Takeaway / call centre / B2B
  unchanged (COD and credit sales complete before payment). Payment path unaffected: it sets
  paid before completed and does not use `transition_order`.
* **D-13 residue:** seed closes kitchen tickets whose order is completed or voided (served_at =
  created_at, so they leave the board at once). Clears #260924-001 on prod.
* Evidence: new tests `test_unpaid_dine_in_cannot_be_completed`, `test_ticket_carries_the_portion`;
  `test_kitchen_ws` payload shape updated. Frontend type-check clean, build clean. Seed run twice
  locally after a local dump: first run 76 placeholder rows + modules set, second run 0 (idempotent).
  **NOT verified: nobody has clicked it.**
* **Deployed `ff21452`** (Deploy to Production green; release `ff21452` holds 76 placeholders +
  logo; each served 200 with the right content type). pg_dump
  `/root/backups/pos-pre-round2-dannys-20260925-093805.sql.gz` (2.26 MB, 62 tables, marker ok).
  Seed on prod: menu trimmed, 76 placeholder rows, **1 stale ticket closed (#260924-001)**.
  Opening stock is never topped up on a re-run (checked in code). Walk after deploy: 0 failures,
  incl. 57/57 dish images and ticket portion ["Full"]; test orders 260925-003 and -004 on T1,
  completed. Full backend suite 1,028 pass, failures identical to HEAD; D-37 guard
  mutation-checked.

### Batch 5, 2026-09-25: real photos, hourly chart (deployed `d405c8b`)

* **D-38 round 2.** Malik on the drawn icons: "u couldnt use an actual image of basmati rice?"
  Replaced with 76 real Creative Commons photos from Openverse (Wikimedia unreachable, Unsplash
  search needs a key). `scripts/fetch_item_photos.py`: 4 candidates per item on labelled contact
  sheets, picked by eye, 25 re-searched when no candidate was right, final set checked on one
  labelled sheet. Hosted in `frontend/public/photos/` with `CREDITS.md`. Compromises, said plainly:
  Breadcrumbs shows bread, Caramel Syrup a caramel-topped slice, a few sauces/marinades show the
  finished dish. Icon tiles and their generator deleted.
* **D-40 fixed:** Hourly Sales bars (dashboard and Reports) had no column height and collapsed to
  2px. `h-full` on the column.
* Prod: pg_dump `/root/backups/pos-pre-photos-dannys-20260925-110254.sql.gz` (2.26 MB, 62 tables,
  marker ok); seed set photos on 76 rows; DB: 70/70 ingredients and 6 dishes on `/photos/`, 0 on
  `/placeholders/`; sample photos served 200 image/jpeg.

### Batch 6, 2026-09-25: Danny's buys everything (D-41, D-42)

* Seed: every dish and portion recipe lists PURCHASED ingredients only. `_flatten` expands each
  in-house item into what it was made of, same amounts (a direct line keeps its waste %, merged
  lines add effective quantity). Chicken Karahi: tomato 0.2 x 4/5 = 0.160 kg, ginger 0.020 +
  0.012 = 0.032 kg; cost Rs 551 before and after. Upgrade path re-versions the 26 affected recipes
  (version 2) and retires the 7 sub-recipes and in-house items (deactivated, not deleted: history
  refers to them). Fresh path no longer creates sub-recipes or production runs.
* `hidden_ui_modules` adds `production` for Danny's: Production nav, Sub-recipe mode in the
  builder and "Run Production" on Stock are hidden. FZ LLC unchanged.
* Stock screen / low-stock list skip retired ingredients (all tenants).
  `tests/test_stock_hides_retired_ingredients.py`, fails without the fix.
* Recipe Builder hides dishes taken off the menu, with a "Show dishes taken off the menu (N)"
  switch (all tenants). Add-on button reads "Add-on or portion (modifier)".
* Local: dump, seed x2 (26 re-versioned + 7 retired, then 0), DB: 0 active recipes using an
  in-house item, 0 active sub-recipes.
* Deployed `a9ac39e` + `e4df9c1`. Prod showed 5 in-house lines left: the recipes of the 6 old
  Half/Full dishes (only exist on prod, from the first seed). `e4df9c1` retires those recipes too.
  pg_dumps `pos-pre-flatten-dannys-20260925-113723` and `pos-pre-flatten2-dannys-20260925-114203`
  (both verified). Prod DB after: 0 in-house lines in active recipes, 0 active sub-recipes.
  Walk: 0 failures; Full karahi took chicken 1.0 kg and tomato 0.294 kg ((0.16 + 0.12) x 1.05).
* **Claude test orders on the Danny's tenant today: 260925-001, -003, -004, -005, -006** (API
  walks, all completed and paid). They inflate today's dashboard; ask Malik before voiding.

### Deploy notes (before the deploy above)

* Batches 1-3 are committed LOCALLY, not pushed. Pushing to main deploys to production.
* **Visible to Martin (FZ LLC, in UAT)**: light kitchen screen, wider order panel with folded
  options, takeaway/call-centre orders auto-complete when served + paid, his order numbers and
  reports on Dubai time. Worth a line to him.
* After deploy: pg_dump, then re-run `seed_dannys.py` on prod (upgrades the tenant in place),
  run `walk_dannys.py https://eats.sitaratech.info --order` with `LOGIN_GAP=13`, then resume the
  browser UAT at Step 12 (Admin > Stock) and re-walk D-21 first.
