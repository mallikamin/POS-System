# Open items register

**Last updated:** 2026-07-29 (session E) — **Stripe hardening H-1…H-10 done except H-6**; new
**OI-49** (register the Stripe webhook — the last hardening item, a dashboard step). Earlier the
same day: storefront checkout wired (OI-28, OI-37 closed) and the CORS blocker found and fixed on
the server (OI-40); OI-41 (card payment gated on Stripe), OI-42 (local test orders).

Numbered so they can be referenced across sessions. **Numbers are never reused.** Closed items stay
here with their outcome for one cycle, then move to the bottom.

Priority: 🔴 blocks the current goal · 🟠 needed before go-live · 🟡 real but not urgent

---

## 🔴 Blocking

**OI-43 ✅ RESOLVED 2026-07-29 (session D) · Email is configured end to end.**
Mailjet free account created, `chickshackg84.com` validated and **DKIM verified**. Two additive
TXT records (ownership + DKIM) — **nothing existing was modified**, and the client's live mail was
re-verified against 1.1.1.1 after every change: MX, SPF (still one record, unedited), DMARC and
all four `livemail*` selectors unchanged. Mailjet's SPF instruction was **deliberately skipped**,
because DMARC passes on DKIM alignment alone and editing the single live SPF record on a domain
carrying his business email is the one change that could damage it.
- **Send path proven before the credentials existed** — driven against a local SMTP sink and
  asserted on the bytes that actually reached the server. All four messages plus the collection
  variant; the four guards hold, including a dead mail server being swallowed rather than
  failing an order.
- **Credentials verified before deployment** — authenticated against `in-v3.mailjet.com` on
  both 587/STARTTLS and 465/SSL. 587 chosen. Mailjet advertises `8BITMIME`, which settles the
  `£` encoding question.
- **`orders@chickshackg84.com` now receives.** A Fasthosts **forwarder** to
  `Rb.dining.group.ltd@gmail.com` was created alongside the existing `info@` one, so a customer
  reply reaches the inbox Imran actually reads. **He has no mailbox on this domain** — the
  quota is 0 and `info@` was only ever a forwarder, which also closes the long-open question of
  whether the domain's mail was real. A paid mailbox was considered and rejected: it only helps
  if someone logs in and checks it.
- 9 keys appended to the production env file after a timestamped backup; no duplicates.

*Original description, kept for context:*

**OI-43 (superseded) · Provider chosen, DNS + env outstanding.**
Parts 1 and 2 were done first: `orders.customer_email` persists, email is **required** at
checkout, and `Reply-To` is set (`e0168c4`) — a sending domain is not a mailbox.
**Full step-by-step in `docs/EMAIL_SETUP_RUNBOOK.md`.**

*Original description, kept for context:*

**OI-43 (original) · No email exists anywhere in this system.**
Raised by Imran 2026-07-29 (OI-29). He wants two emails: on placement, and on accept carrying the
lead time. **This is a go-live blocker rather than a refinement**, because his own worked example is
a pre-order placed at 14:00 and accepted at 15:30 — the confirmation screen learns the ETA by
polling and gives up after 20 minutes, so that customer would never find out they had been accepted.
Three parts, in order:
1. **Persist the address.** `customer_email` is accepted by `POST /public/{tenant}/orders` and then
   **discarded** — `Order` has no email column and `_link_customer` never sets `Customer.email`,
   though that column exists. Nothing is sendable today.
2. **Make email required at checkout.** It is currently optional (`contactOk` needs only name and
   phone) and labelled "for your receipt". If it is the notification channel it cannot be optional.
3. **A sender.** No transactional email provider is configured. Needs an account and a domain — and
   `chickshackg84.com` carries the client's live business email, so any DNS record for sending must
   be added additively and verified, per the DKIM near-miss on 2026-07-27.

**OI-44 ✅ RESOLVED 2026-07-29 · The order can now finish.** Tablet has one service-type-aware
"Out for delivery"/"Ready for collection" button, then "Delivered"/"Collected" which settles an
unpaid cash order in the same tap (and says so on the button), plus a separate "Mark paid" for
the driver-returns-later case. Completed orders leave the Active tab. The customer's confirmation
page now follows the order all the way instead of stopping at "accepted". Deployed.
*Superseded description below, kept for the record:*

**OI-44 (original) · The order stops dead at `in_kitchen`.**
Independently raised by Imran 2026-07-29 and by Malik before him, which is about as strong a signal
as a gap gets. An accepted order never leaves the Active tab, so the queue grows forever and the day
never settles. The state machine **already** supports it (`ready → served → completed` plus
`PATCH /orders/{id}`); what is missing is the tablet UI and the customer-facing status.
Two notes on scope: the label must follow the service type ("Out for delivery" vs "Ready for
collection"), and Imran asked directly whether the button is worth having — **it is, and not mainly
for the notification: it is the only thing that closes an order.** Still to ask him: does the final
tap also mark a cash order paid, or is that a second tap?

**OI-45 · Menu items need real modifier prompts. TWO separate asks, do not conflate them.**

⏸️ **Parked until the QC pass by Malik's own reply to Imran, 2026-07-29 03:09:** *"we'll get to
the fine details in the QC part... i'll get to those as the backend plumbing is finished."*
Do not build this before the lifecycle/email plumbing lands. Imran was still mid-list at 03:10,
so **the requirement is not yet fully captured** — collect the rest before designing.

**(45a) Required heat-level choice — EASY, no schema change.**
Imran 03:10: *"Such as: for peri burgers, peri wraps, both single and double and peri wings and
peri tenders. Needs to have the following."* + a photo of his **EposNow till** showing a modal
titled **"Peri-Peri Heat"** with exactly two options, **Hot Heat** and **Mild Heat**, and the
validation text **"Please choose 1"** (screenshot taken on Peri Peri Wings Solo, £7.99).
So: a **required single-select** group on the peri items. That is `min_selections=1,
max_selections=1` with two £0.00 options — the existing modifier engine does this natively on
both front ends. **No schema change, no conditionality.** Cost is a seeder change and a re-seed.
Still to confirm: the exact item list, and whether Hot/Mild is the full set (his board may also
have Medium/Extra Hot — the photo shows only two).

**(45b) "Make it a meal" needs to ask what is IN the meal — HARD.**
Imran 03:08: *"In the menu the make it a meal needs modifiers. For each make it a meal item."*
Today it is a single flat +£3.00 tick with one option. He wants the drink (and probably the
side) chosen when the upgrade is taken.
**Confirm with him first** — it decides the model: drink only or drink and side; which drinks
are included at £3.00 and which are an upcharge (cans are £1.79 on the board); is the side
always chips.
✅ **The conditionality problem is DEAD — settled by his own screen recording, 03:15.**
Both previously-considered options (a "No meal" first option, or a conditional-group schema
change) are **withdrawn.** Neither is needed and neither should be built.

**EposNow makes Solo and Meal SEPARATE PRODUCTS** in sibling sub-categories
(`PERI PERI WING MEALS` vs `PERI PERI WINGS SOLO`). The meal product simply *has* the drink
and chips groups attached; the solo product does not. The question "should I ask about a
drink?" never arises, so nothing conditional is required. **Zero schema change** — our
`ModifierGroup` already carries `required` / `min_selections` / `max_selections` and groups
attach per item. It is also the model Imran already trains his staff on.

**The exact configuration, transcribed and frame-verified**, is in
`_context/clients/chick-shack-uk/voice-notes/2026-07-29_imran_eposnow-menu-walkthrough.md`
(+ archived frames in `refs/eposnow-menu/`). Summary:
- `Peri-Peri Heat` — **required, choose 1**: Hot £0.00 / Mild £0.00
- `Adults Meal Deal Drink` — **required, choose 1**, all £0.00: 7UP, Fanta Orange, Levi Roots
  Caribbean Crush, Pepsi Max, Water, Diet Irn Bru, Irn Bru, Pepsi, Rubicon Passion Fruit
- `Kids Meal Deal Drink` — **required, choose 1**, two options ONLY: Fruit Shoot Blackcurrant,
  Fruit Shoot Orange. He was emphatic: *"no other option of any fizzy drinks or canned drinks."*
- `Meal Deal Upgrade` — **optional, up to 1**: Regular Chips £0.00 (included), Large Fries
  £0.79, Peri Peri Fries £0.99, Large Peri Peri Fries £1.19, Wedges £1.39, Peri Peri Wedges £1.59
- Meal uplift **+£3.00**; kids solo £3.99

🔺 **He wants the website to BEAT his till on one point.** His EposNow does *not* prompt for
heat on the double peri peri burger and he calls that out as wrong: *"it should ask you… so on
the website I'm asking if you could add on."* Heat is wanted on **peri burgers, peri wraps
(single and double), peri wings, peri tenders.**

**(45c) Per-line notes / exclusions — he asked for this explicitly and it is not built.**
*"a notes option whether if they don't want any like no onion or lettuce, no salsa, no Algerian
sauce, no ketchup… make our life a lot easier."* His till has free text plus "Popular Notes"
quick-picks (No Onion / No Lettuce / No Tomato / No Mayo).
**The backend already supports this end to end** — `order_items.notes` exists, and
`ApiOrderLineRequest.notes` is accepted and persisted. **The gap is storefront UI only**: the
cart line does not carry a note. Recommend a **tick-list of £0.00 modifiers** over free text,
because a kitchen ticket is read by a human at speed and free text invites ambiguity.

⬜ **Five things still unanswered — do not invent them.** Full list at the bottom of the
walkthrough note: exact meal-variant product list, whether +£3.00 is uniform, whether Hot/Mild
is the whole heat scale, kids upgrade prices, and tick-list vs free text.
Either way this is **not storefront-only**: the choices must exist as rows or the order
endpoint will refuse them, so it means new groups in `seed_chick_shack.py` and a re-seed.

**OI-46 ✅ DISSOLVED 2026-07-29 by the client's own answer — there is nothing to refund.**
Asked directly whether a website prepaid order should be charged at placement or on acceptance,
Imran answered **"Once accepted."** That makes it Stripe **manual capture**: authorise at
checkout, **capture on the Accept tap**, **cancel the authorisation on Reject**. A rejected order
is therefore never charged, the rejection screen's *"nothing has been charged"* stays true, and
no refund path is needed. **Build the capture/cancel model, not a refund model.**
⚠️ One real constraint it introduces: a card authorisation expires after **~7 days**, so a
pre-order cannot be held open indefinitely. Fine for same-day and next-day, which is all he does.
*Original description — a refund gap that only existed under charge-at-placement:*
Raised 2026-07-29 when 24/7 pre-ordering went in. A customer could pay at 02:00 for a shop that
opens at 16:00 and then be declined, and `reject_order` had **no refund call**.

**OI-48 · Customers should be able to CHOOSE a time. Not built, and it is not a tweak.**
Raised by Imran 2026-07-29: *"they can select a time (we open at 4) so earliest delivery would be
4.30pm."* Today the storefront has **no time picker at all** — an out-of-hours order is simply
labelled a pre-order and the shop supplies the ETA when it accepts. He is describing the customer
picking a slot, bounded below by opening time plus a lead time. That means a new field on the
order, validating the requested slot against opening hours, surfacing it on the tablet card and
the kitchen ticket, and deciding what happens when the shop cannot meet the chosen time.
**Deliberately logged rather than absorbed into the Stripe work.**

**OI-49 · Register the Stripe webhook. The last hardening item, and it is a dashboard step.**
Raised 2026-07-29 (session E) as H-6 of `docs/STRIPE_HARDENING_CHECKLIST.md`, where the full
procedure is written out. Everything else in that checklist (H-1…H-5, H-7…H-10) is **done**.
The **code half of H-6 is also done**: all six Stripe keys are now declared in the backend's
`environment:` list in `docker-compose.demo.yml`. ⚠️ **None of them were there before** — the
keys would have been written to the server env file and never reached the container, so card
payment would have been silently unavailable behind a green deploy. That is the identical
failure logged for the email keys earlier the same day; see `ERROR_LOG.md`.
What is left is Malik's, in the Stripe dashboard: add the endpoint
`https://eats.sitaratech.info/api/v1/public/stripe/webhook`, subscribe to the four
`payment_intent.*` events, put the signing secret on the server, deploy, then **read the value
back from inside the running container** and send a test event. Until the secret exists the
endpoint refuses everything, which is the correct fail-closed state, not a bug.

**OI-47 · CI has been red on every commit, and the lint failure means the tests never run.**
Found 2026-07-29 (session D) while verifying a deploy. **Both** CI jobs fail: backend Ruff
(~30 findings) and frontend ESLint. The Ruff step runs *before* the test step and exits 1, so
**`ci.yml` has not executed the backend suite on any recent commit** — the 373 passing figure
comes from running it by hand, and nothing automated would catch a regression.
Nothing here is a live bug: the findings are almost all `F401` unused imports in **parked**
subsystems (QB Desktop at 33%, BOM seeders) plus `E712`/`F841`. The one that looks alarming,
`app/models/menu.py:92 F821 Undefined name 'Recipe'`, was checked and is **not** a defect —
it is a SQLAlchemy string forward reference resolved from the mapper registry at runtime; it
only lacks a `TYPE_CHECKING` import. The live menu serves and the suite passes.
**Not blocking, and deploys are unaffected** (`deploy-production.yml` is a separate workflow and
is green). But a permanently-red CI is the same failure this repo already logged on 2026-07-27:
a safety net nobody can read. **Deliberately not fixed here** — it is ~30 edits across code that
is parked, which is Malik's call, not a side effect of the Chick Shack work. Fix is either a
one-off cleanup or scoping Ruff to exclude parked paths until they are revived.

**OI-20 ✅ RESOLVED 2026-07-29 · Stripe account connected.**
Imran's account is real, live and GBP (`Chick Shack`, `acct_1TngvxFnGj7KcDjJ`). He granted Malik a
**Developer** seat — the least-privilege role that can manage API keys and webhooks and cannot
touch payouts. Work starts in the **sandbox**; live keys only once the sandbox flow passes.
⚠️ Stripe **does not support Pakistan**, so the signup country is answered **United Kingdom**.
That field only shapes the personal user profile — it does not create a merchant account, because
this is a team invitation onto his existing UK business.
**Now open as OI-23** — the integration itself, still unbuilt.

**OI-38 ✅ ANSWERED 2026-07-29 · Chick Shack is NOT VAT registered.** Imran, directly: *"We are not
VAT registered yet."* The seed's **0% tax is therefore correct**, not a placeholder, and no change
is needed before taking money. Revisit only if he registers.

**OI-31 ✅ RESOLVED 2026-07-27 06:43 · He does not need to buy anything.** He said the printer was
incompatible and he would buy a new one — repeating back our own superseded Bluetooth-era advice, not
reporting a finding. Malik asked the deciding question and Imran answered: *"Connected to a Ethernet
switch and the switch is connected to the broadband router."* **The printer is on the shop LAN**, so
the tablet can reach it on TCP:9100. **£0 hardware.** Second wasted purchase stopped this week by the
same rule: he never buys hardware without sending the link first.
**Now open as OI-33** — the remaining verification.

**OI-33 ✅ RESOLVED 2026-07-28 16:00 UK — IT PRINTS.** Malik walked Imran through RawBT setup
remotely over WhatsApp, one screenshot per step, ~20 minutes, finishing minutes before the shop
opened. **Test print produced paper from the EposNow kitchen printer, driven by the tablet.**
**EposNow does not hold port 9100** and there is **no wireless-to-wired client isolation** — the last
two real risks in the printing path, both dead. Width corrected to `576` dots and verified with
RawBT's ruler calibration print. Full config recipe and the width trap in `printing.md`.

**Now open as OI-35** — our own bytes have still never touched paper.

**OI-36 ✅ BUILT 2026-07-28 · Order-queue tablet view.** `/online-orders`, standalone and fullscreen
like the KDS. Pending / Active / All, cards showing phone, address, area, items, modifiers and
notes, a loud unpaid banner, accept with a one-tap ETA (15-90 min), reject with a reason, and
"print again" on accepted orders. Poll every 10s with a chime on genuinely new orders. Scoped to
exactly what the client described and nothing more.
**Verified end to end against the running stack:** order placed on the public API → appeared in the
queue → accepted with a 45-minute ETA → moved pending→active → ticket bytes built → customer status
showed the ETA. **Not yet opened in a browser on a real tablet.**

**OI-39 · Chick Shack's 11 delivery areas were seeded into the WRONG TENANT.**
Found 2026-07-28. `seed_chick_shack_delivery.py` ran on 07-27 when `chick-shack` did not exist, so
Garelochhead £3 through Arrochar £15 all landed on **`demo-restaurant`**, the Pakistani demo. They
are now correctly seeded on `chick-shack` too, but **the 11 bogus rows are still on the demo tenant**
and will show UK villages in any demo of the Pakistani restaurant. Deleting them is a destructive
op on a tenant we were not asked to touch, so it is left for Malik to call. Backup taken first:
`logs/backups/pre_chick_shack_seed_2026-07-28.sql`.
*This is precisely the failure D-10 is about: a script that resolves "the tenant" loosely.*

**OI-37 ✅ RESOLVED 2026-07-29 · The storefront now fetches its menu from the API.**
`GET /public/chick-shack/menu` is the source of ids, names and prices, so a price Imran edits in the
admin screen reaches the website without a redeploy. `menu.ts` is retained **only** for what the
database does not hold: food photos, the deliberate no-photo opt-outs, and the delivery-area list.
Photos are joined back on by **item name**, which is the same key `seed_chick_shack.py` matched on.
Parity was verified rather than assumed: 37 items had a photo before and 37 after, and all 62 API
item names join. If anyone renames an item on one side only, the item keeps working and silently
loses its photo — the harness check for that is worth keeping.

**OI-40 ✅ RESOLVED 2026-07-29 · The API refused calls from the storefront's own domain.**
`CORS_ORIGINS` in `.env.demo` was `https://pos-demo.duckdns.org` only. The menu fetch from
`chickshackg84.com` returned 200 with **no `access-control-allow-origin` header**, so every browser
would have discarded it — the site would have silently fallen back to "ring us" and nobody would
have seen an error. Now set to `pos-demo.duckdns.org, eats.sitaratech.info, chickshackg84.com,
www.chickshackg84.com`; backend and nginx recreated, all four sites on the box verified with their
own certificates. Preflight `OPTIONS` confirmed; an unknown origin still gets no header, so it is
not a wildcard. `.env.demo` backed up first as `.env.demo.bak.20260728-201748`.
*This is the failure mode that has no error message. Test CORS with an `Origin` header, not by
whether the endpoint returns 200.*

**OI-38 — see the ✅ ANSWERED entry above. Original wording kept for the record:**
**Is Chick Shack VAT registered?** The seed sets tax to **0**, deliberately, rather than
assuming 20% UK VAT. Totals match the printed board either way under `tax_inclusive`, so nothing is
wrong today, but this must be answered before real money moves. Ask alongside the Stripe question.

**OI-35 · Test our ESC/POS on the real printer.** ⬇️ **Software half closed 2026-07-28.**
Byte-level check on a real order's ticket: **4 × `0x9C`** (the CP437 pound, one per money line),
**zero** UTF-8 pound sequences, widest line exactly **48 chars**, and the payload ends with
`GS V 66 0` (partial cut). The `£`, the column width and the cut are therefore correct — verified,
not assumed.
**Still untested: the physical handoff only.** Whether Chrome on his Android honours the `rawbt:`
scheme, or whether we fall back to the `intent:` form. That needs his tablet and nothing else.
⚠️ **Decide first how the file reaches the tablet.** `storefront/public/print-test.html` is generated
and self-contained but **not deployed**; putting it on the client's live domain is Malik's call. A
`.prn` sent over WhatsApp avoids deploying anything — untested whether WhatsApp passes the extension
through and whether Android routes it to RawBT.

<details><summary>Original OI-33, kept for the record</summary>

✅ **Answered by the label + self-test slip** (photos archived in
`_context/clients/chick-shack-uk/refs/`, full table in `printing.md`):
- **IP `192.168.1.208`, static (DHCP disabled)** — no router reservation needed.
- **80 mm, 48 characters per line, Font A** — our default is confirmed correct.
- **Default code page 0 = PC437** — our `£`→`0x9C` encoding matches the printer's power-on default.
- **eposnow `POS80GXn`, ESC/POS, cutter fitted, listening on TCP 9100.**
- Firmware 2017 → **no AirPrint/IPP**, so RawBT is the path. That upside is closed off.

✅ **Tablet is on the same LAN — confirmed 2026-07-28 15:52 UK.** Tablet `192.168.1.153`, printer
`192.168.1.208`, both gateway `192.168.1.254`, both mask `255.255.255.0`.

⬜ **Still needs Imran, tablet in hand — nothing here can be done from Pakistan:**
1. **Test 1: RawBT test print.** Install `ru.a402d.rawbtprinter`, add a network printer at
   `192.168.1.208` port `9100`, tap test print. If paper comes out it simultaneously proves
   reachability, that **EposNow is not holding port 9100**, and that the router is not isolating
   Wi-Fi from wired. **This single tap settles the last real technical risk in the printing path.**
3. **Test 2: print from a web page.** `storefront/public/print-test.html` is generated and ready.
   **Not deployed** — it would go on the client's live domain, so that is Malik's call.

</details>

*(OI-32 removed 2026-07-28 — a referral-lead note misfiled as a blocking build item. It duplicated
what `chick-shack-uk.md` already records under Commercial upside. Number not reused.)*

---

## 🟠 Needed before go-live

**OI-21 ✅ MIGRATED AND VERIFIED 2026-07-27.** `n0o1p2q3r4s5` applied locally after a `pg_dump`.
⚠️ **It had a real bug that only running it could expose:** `delivery_areas.created_at` was created
without `server_default=now()`, which `BaseMixin` relies on, so **every insert failed on the NOT NULL**.
Fixed in the migration itself rather than stacked as a patch, since it had never run anywhere. Table
and all 8 order columns verified against the live schema. **Not yet applied on the server.**

**OI-27 ✅ SEEDED 2026-07-27.** All 11 areas and the £5 minimum are in the DB.
`backend/app/scripts/seed_chick_shack_delivery.py` — idempotent, tenant-scoped, updates in place and
retires removed areas rather than deleting, so it is safe to re-run after a price change.
**Not yet run on the server.**

**OI-28 ✅ RESOLVED 2026-07-29 · Storefront checkout posts a real order.**
`place()` now posts to `POST /public/chick-shack/orders` with **ids and quantities only**, and the
confirmation screen polls `orders/{id}/status` until the shop accepts or rejects. The chosen variant
travels as a modifier id, because in the database that is what it is (D-11). Verified three ways
against the running stack: the server contract, the real storefront TypeScript driven from node, and
the merchant half (queue → accept 45 min → the customer's status showing the ETA → an 822-byte
ticket with a `rawbt:` URL). Basket subtotal and server subtotal agreed exactly.
**Committed on `feat/storefront-checkout-wiring`; not merged, not published.**

**OI-41 · Card payment is hidden until Stripe exists.** `SHOP.cardPaymentEnabled = false`, so
checkout offers only "pay on collection/delivery". The order endpoint creates every order **unpaid**
and nothing behind it takes money, so a "Pay now by card" button would tell a customer they had paid
when they had not. Flip it only with Stripe Checkout **and** its signature-verified webhook live.

**OI-42 · Test orders left on the LOCAL chick-shack tenant.** Four orders named "Wiring Test" /
"TS Wiring Test" sit in the local pending/active queue from this session's verification; one was
accepted with a 45-minute ETA. Local only — **production was never written to.** Harmless, but they
will show on a local tablet demo. Deleting them is a destructive DB op, so it is left for Malik.

**OI-29 ✅ ANSWERED BY THE CLIENT 2026-07-29 · The channel is EMAIL.** Imran described it unprompted
in a voice note and said "email" every time, never SMS. He wants **two**: one the moment the order is
placed, one when the shop accepts, carrying the lead time. Now tracked as OI-43.
See `_context/clients/chick-shack-uk/voice-notes/2026-07-29_imran_order-lifecycle-and-emails.md`.

**OI-30 ✅ RESOLVED 2026-07-27 · The test suite runs again, and it had been dead for four months.**
Docker started; the suite then errored on *every* DB-backed test because `stock_counts` (JSONB, added
2026-03-26 in BOM Phase 1) was never added to `_SKIP_TABLE_NAMES` in `conftest.py`. The autouse
fixture failed before any test body ran. **The rule that would have caught it was already written in
`ERROR_LOG.md` on 2026-02-23**, then violated a month later and unnoticed for four months because
nothing ran the suite.
**Now 317 passing.** The 12 remaining failures are all pre-existing and unrelated — see OI-34.
⚠️ **Any "N tests passing" claim in this repo dated between 2026-03-26 and 2026-07-27 is unverified.**
Run against the local Docker backend: `docker exec pos-system-backend-1 python -m pytest -q`.

**OI-34 · 12 pre-existing test failures, none related to the current work.**
- **10 × QuickBooks Desktop** (parked at 33%): the tests index `result["success"]` but the code
  returns a `QBXMLParseResult` object. Test/implementation drift from March.
- **1 × `test_pay_first`**: asserts the literal string `"Payment required"`; the message was since
  reworded to something friendlier and the test was never updated.
- **1 × `test_void_with_reason_succeeds`**: returns 401, a fixture auth problem.
None block the Chick Shack work. They were invisible until the suite was revived.

**OI-23 · Stripe integration not built.** Checkout Session + signature-verified idempotent webhook.
`PaymentGateway` is an abstract stub. Payment confirmed by webhook only, never by browser redirect.

**OI-24 · `SHOP.orderingEnabled` still `false`.** Correct for now. Flip only after OI-21/22/23 are
tested end to end. A fake order confirmation is worse than no site.

**OI-25 ✅ RESOLVED 2026-07-27 · Printer is Ethernet.** Confirmed by Imran. Our discovery note was
right, his recollection was wrong. **No printer purchase needed**, and the Bluetooth
single-connection problem is moot — TCP:9100 takes jobs from EposNow and from us.
**Superseded since:** the **Pi is gone** (print fires on the Accept tap, so nothing runs unattended)
and the **IP is known** (`192.168.1.208`, 2026-07-28). The only survivor of this item is *"does
EposNow hold a persistent socket on 9100"*, now tracked under **OI-33**. See `printing.md`.

**OI-26 · ~173 hardcoded `Rs.` literals in `frontend/src`** bypass the currency formatter. The
formatter itself is fixed; these are the stragglers. Any of them on a screen the client sees will
show rupees on a GBP site.

---

## 🟡 Real, not urgent

**OI-10 · No PIN-uniqueness constraint anywhere.**
`authenticate_by_pin` (`backend/app/services/auth_service.py:52`) returns the **first** bcrypt match
across active tenant users. A PIN collision silently logs someone into the wrong account. This
actually happened on 2026-07-15 and was fixed for those two users; **the structural hole remains.**
Needs a uniqueness check at user-creation time, or a startup/seed collision audit.

**OI-11 · Nightly demo-data cron has never run.**
Three stacked faults: the credentials file was never created on the server; the host `python3` has no
`psycopg2`; and the Postgres container publishes no host port, so a bare-host cron process cannot
reach the DB by design. Needs a rewrite to run inside a container on the Postgres network, not just
a credentials file. Was marked "deployed and verified" while completely non-functional.

**OI-12 · Chrome extension disconnected**, so browser-based visual verification is unavailable this
session and the last. Server-side checks confirmed `eats.sitaratech.info`; a human browser check is
still outstanding.

**OI-13 · 3 server-local files drift from git** — `docker/nginx/nginx.conf` (gzip block) and
`frontend/.dockerignore` exist on the server but were never committed.

**OI-14 · `memory/server-deployment-rules.md` inventory incomplete** — does not mention
`parkcity.sitaratech.info`/Orbit sharing the same nginx.

**OI-15 · Stray Docker volumes** `pos-system_certbot-etc` / `pos-system_certbot-var` are redundant
since the cert merge. Safe to remove; nobody has.

**OI-16 · Two client-facing docs claim things the code does not do.**
`CLAUDE.md:20` (per-station thermal printing) and `EXECUTIVE-SUMMARY-1PAGER.md:35` (online ordering
and QR ordering as current features). **Unknown whether that 1-pager already went to the UK
prospect** — Malik to confirm. Either correct them or close the gap by building.

**OI-17 · UAT-093 / ENH-016** — duplicate email crashes the page instead of showing a toast. The only
UAT failure of 99.

**OI-18 · QB sync mode undecided** — auto vs manual vs scheduled. Waiting on BPO World, not a bug.

**OI-19 · Client contact name ambiguity.** Recording is `rizwan uk meeting.mp4`; contact of record is
**Imran R**; a third party "Rizwan" is referenced on the call. Confirm before any named document goes
out.

---

## Recently closed

**OI-01 ✅ 2026-07-27 · Custom domain blocked by dead Vercel DNS records.** Deleted exactly the two
Vercel records; `wrangler deploy` attached both custom domains. Email verified intact. See
`infrastructure.md`.

**OI-02 ✅ 2026-07-27 · No images on the storefront.** Every item now shows a photo, with a branded
fallback tile for items where a stock photo would misrepresent the food. Images are self-hosted,
lazy-loaded thumbnails plus on-demand heroes. **They are stock placeholders, not his food** — real
photography is still wanted.

**OI-03 ✅ 2026-07-27 · Multi-currency formatter.** Config-driven; found and fixed a real bug where
£8.50 would have rendered as £9.

**OI-04 ✅ 2026-07-27 · Stale "Current Priority: Petrol Pump" lines** corrected in `memory/MEMORY.md`
and `QUICK_REFERENCE.md`.
⚠️ **Standing correction, do not lose:** that petrol pump is a **PAKISTAN** business — the owner is
Kuwait-based, which is the only reason "Kuwait" is in the folder name. It is **PKR + FBR/PRA, never
KWD, never Kuwait VAT**, and it is a **separate project** at
`C:\ST\Sitara Infotech\Kuwait Petrol Pump\kuwait-petrol-pump`. Several archived files still assert
the wrong version; treat any "Kuwait VAT / KWD / paisa→fils" line in `docs/history/` as known-false.
