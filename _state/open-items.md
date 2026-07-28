# Open items register

**Last updated:** 2026-07-28 (19:45 PKT) — printer self-test slip received; OI-33 halved.

Numbered so they can be referenced across sessions. **Numbers are never reused.** Closed items stay
here with their outcome for one cycle, then move to the bottom.

Priority: 🔴 blocks the current goal · 🟠 needed before go-live · 🟡 real but not urgent

---

## 🔴 Blocking

**OI-20 · Stripe account not connected.**
Imran says he has one. Unknown whether it is verified and live or newly created. **Gates the entire
payment path**, which is the remaining bulk of the build. Ask before starting Stripe work.

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

**OI-37 · The storefront should fetch its menu from the API, not `menu.ts`.**
The menu now exists as rows (D-11), but `storefront/src/data/menu.ts` is still what the site renders,
so there are two sources of truth and they will drift. Switching the storefront to
`GET /public/chick-shack/menu` also means Imran can change a price from the admin screen instead of
waiting for a redeploy — which is most of what "manage my own menu" means to him.

**OI-38 · Is Chick Shack VAT registered?** The seed sets tax to **0**, deliberately, rather than
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

**OI-28 · Storefront checkout still posts to nothing.** `place()` in `Checkout.tsx` fabricates a
reference and clears the basket. Wiring it to `POST /public/orders` is the next frontend job.

**OI-29 · How the ETA reaches the customer is undecided.** Never discussed with the client. The API
returns it and there is a status-poll endpoint, but nothing pushes it. Recommended default: on-screen
confirmation plus email, which adds no recurring cost. **Ask Imran.**

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
