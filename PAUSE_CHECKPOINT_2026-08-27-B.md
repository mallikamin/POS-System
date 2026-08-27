# Pause Checkpoint — 2026-08-27-B

Second checkpoint of 2026-08-27. **`PAUSE_CHECKPOINT_2026-08-27.md` (04:20) is history and
must NOT be overwritten** — this file supersedes it. The `-B` suffix is deliberate; the pause
skill overwrites a same-day filename unconditionally.

## Project
- **Name**: POS System (Sitara Infotech) — FZ LLC UAE build
- **Path**: `C:\Users\Malik\desktop\pos-project`
- **Branch**: main. **HEAD `af962c0` = `origin/main` = server. 0 unpushed.**

## Goal (unchanged)
Get the finished FZ LLC build in front of Martin Zubeldia: a demo video, a walkthrough PDF and
a two-tier quotation, so he and his partners review over the weekend and reconnect Monday
08-31.

## 🔴 WHAT MALIK WANTS NEXT, IN HIS ORDER

1. **UAT step by step, together, from Exercise 9.** He drives, ONE STEP PER MESSAGE
   (`step-guard.py` is armed and sticky). Exercises 1–8 are done by hand; 9–15 have been
   verified **by script only**, not by eye.
2. **One clean demo video.**
3. **A lean UAT guide.**

⚠️ **Read the tone note below before doing anything else.**

## The correction that defined this session, and must not be repeated

Malik, verbatim: *"why do we have to stop at every step fix it. why cant u be smart about it…
you could have literally fixed everything before we initiated the UAT… i want a comprehensive
sweep. i dont want even martin to find petty issues."*

He was right. The failure mode was **fixing the instance while the class survived**: F18 was
fixed in the cart and reappeared on the receipt; F19 was fixed in three places and a fourth
kept the old formula. **When something is found, sweep the whole codebase for its class
before moving on.** Do not hand him screens to break one at a time.

## Where things stand

### Deployed today: four green production deploys
| Commit | What |
|---|---|
| `e4a3d2e` | F19 tax-inclusive money path + F14–F18 |
| `8425257` | F22 one frontend tax rule, F23 real printable bill, F24 receipt currency |
| `31e5d15` | F26 shared currency table, F27 locales, F18 completed |
| `af962c0` | F28 the last 68 Decimal fields + typed AI-usage rows |

🟢 **Chick Shack measured before and after every deploy, same tenant-scoped query, identical at
all five measurements: 233 orders / newest `2026-08-26 19:40:58` / 166 customers / 219
payments / 642087 total / 87 menu items.**

🟢 **Proved inside the RUNNING PRODUCTION backend, not from a green Action:**
```
F19  3 x AED 9.00 @5% incl -> (129, 2700)      was (135, 2835)
     chick-shack rate 0     -> (0, 642087) under BOTH conventions
     playbook AED 100 @5%   -> VAT 476, the 4.76 promised in writing
F18  AED->VAT  GBP->VAT  PKR->GST  zero-rate->Tax
F26  AED 380.00 / £380.00 / Rs.380.00 / XYZ 380.00 — all four generators agree
F28  SupplierResponse.total_spend_minor -> 12345.0 (float)
```
Backups: `/root/backups/pos_pre_taxfix_20260827T082602Z.sql.gz` and
`…T101739Z.sql.gz` (381K, gzip verified, 56 table blocks).

### The headline bug, F19
**Tax was charged twice on tax-inclusive prices.** `restaurant_configs.tax_inclusive` has
existed since Phase 2, defaults to true, and was read by **exactly one service**
(`tax_invoice_service`) while the order path ignored it. 3 × AED 9.00 rang up at **28.35
instead of 27.00**, and the A4 invoice disagreed with the amount actually taken.
**Chick Shack was never affected** — `default_tax_rate = 0`, and at rate 0 both formulas are
identical. There is a test pinning that, using their real 642087 total.

### 🔴 The lesson that outranks the bug
**No test had ever created an order.** Not via `order_service.create_order`, not via
`POST /api/v1/orders` — verified by grep, zero hits for either. Every order in the suite was a
hand-built ORM row with a literal `tax_amount`, so the tax calculation had never executed once
in 765 tests. Where totals *were* asserted, the expectation encoded the bug
(`test_p1a_features` declared `tax_inclusive=True` and then asserted the tax was added — and
passed, because the code ignored the flag).
**Now 824 passing** (+59). `backend/tests/test_tax_inclusive_pricing.py` has 48 tests
including three that create real orders through the real service.

### Test baseline — memorise this
**824 passed, 10 failed, 2 errors.** The 10 are pre-existing and unrelated: 8 QuickBooks
Desktop QBXML/adapter, 1 stale error-message string in `test_pay_first`, 1 HTTP 401 in
`TestVoidHardening`. **If you see 10/2, nothing has regressed.**

## Findings — 21 in total, in `_state/uat-findings-fz-llc-batch2.md`

**Fixed and live (15):** F13 partial, F14 ingredients crash, F15 admin config never loaded
(rupees on a UAE tenant), F16 AED undefined, F17 seventeen `(PKR)` labels, F18 GST→VAT,
F19 double tax, F22 self-contradicting VAT on one screen, F23 Print Bill printed a screenshot,
F24 receipt hardcoded to rupees, F26 three document generators could not render AED,
F27 seven hardcoded locales, F28 sixty-eight Decimal fields.

**Still open (7):**
| # | What | Blocks the demo? |
|---|---|---|
| **F29** | **Profitability report returns 0 rows** — no completed order carries channel data | 🔴 **YES — Exercise 10 renders blank** |
| F30 | `martin-fz` has no kitchen stations, so nothing routes to a kitchen screen | only if the video mentions the kitchen |
| F10 | Admin sidebar does not collapse | no |
| F11 | Recipe Builder ingredient list has no search | no |
| F12 | Login shows a "Restaurant" slug field with `e.g. chick-shack` as placeholder — leaks another client's name | cosmetic, but on the first screen of the video |
| F20 | Deploy never prunes old bundles (52 payment bundles where 2 are live) — makes post-deploy greps lie | no |
| F21 | **Playbook Exercise 8 is wrong** — tells Martin to check stock right after ringing up, but stock moves only on **completion** | must fix in the PDF |
| F25 | **No frontend test suite exists at all** — and 7 of this session's findings were frontend | after Martin |

## 🔴 Do this before recording anything
1. **Fix F29** — seed completed orders carrying channel data, or Exercise 10 shows Martin an
   empty screen. This is the report he specifically asked for.
2. **Decide the TRN.** `100123456700003` is a placeholder and it prints on the A4 tax invoice
   at both locations. Either get Martin's real one or say plainly on the call that it is dummy
   data. Do not let it pass unmentioned on a legal tax document.
3. **Re-render `proposal/FZ_LLC_System_Walkthrough.pdf`** — Exercise 8 is wrong (F21) and
   several named screens have changed.
4. **Clean the demo order list.** `martin-fz` now has test orders from UAT plus two from the
   scripted sweep. `FZ-0001` carries `tax = 0` (old seed data, pre-fix).

## What was verified by script but NOT by eye
Exercises 9–15 were driven end to end through the API as the `martin-fz` admin, **32
assertions, 0 failures** — including VAT **added** on a purchase order (supplier quotes net),
VAT **inside** a quotation total (selling side inclusive), the blank PO price filling from the
catalogue, partial receipt raising stock and writing back the price actually paid, the planner
making dough in-house rather than buying it, a non-menu quotation refusing to convert **for the
right reason**, and a menu-only quotation converting **at the quoted price**.
**None of that has been seen in a browser.** That is what the step-by-step UAT is for.

## Reusable tooling built this session (in the scratchpad)
Worth keeping — they turn "did anyone check?" into a command:
- `api_sweep2.py` — enumerates **every** GET route from the app and drives it as a real tenant.
  Last run: 67 routes, **zero 5xx**.
- `flow_sweep.py` / `flow_sweep2.py` — exercises 9–15 end to end with per-claim assertions.
- `sweep2.py` — regex sweep for hardcoded currency / locale / tax-name / tax-formula.
- `decimal_sweep.py` + `check_ser3.py` — finds every `Decimal` on a response schema and proves
  all 119 serialise as JSON numbers.
Scratchpad: `C:\Users\Malik\AppData\Local\Temp\claude\C--Users-Malik-desktop-pos-project\a501f33a-cc8e-4a35-b1aa-fa5d4a1b8268\scratchpad`

## Critical context carried forward
- **Server `159.65.158.26`, `~/pos-system`, shared nginx with Orbit CRM.** Read
  `memory/server-deployment-rules.md` and `memory/data-integrity.md` first. `pg_dump` before
  any DB op, no exceptions.
- **`git push origin main` IS the deploy.** Chick Shack trades **16:00–22:00 UK**; deploy
  outside that unless Malik explicitly clears it. Today's four all went out ~08:30–10:30 UK.
- **Measure Chick Shack the same way before and after every deploy.** Tenant-scoped, always.
- ⚠️ **The production backend container has a READ-ONLY rootfs** — `docker cp` into it fails.
  Pipe scripts in: `cat f.py | docker exec -i -e PYTHONPATH=/app pos-system-backend-1 python -`
- ⚠️ **The box has ~120MB free RAM.** A `gzip -dc | grep -c` over a backup got OOM-killed and
  returned exit 255 *after* writing a perfectly good dump. Verify with `gzip -t` instead.
- ⚠️ **Never grep the assets directory to check a deploy.** 52 stale `PaymentPage-*.js` bundles
  sit there; only the one referenced by the entry chunk is live. Grepping the directory
  reports a successful deploy as failed (F20).
- **The server returns 444 to curl.** Pass a browser `-A`. Not an outage.
- **`cred-guard` blocks the Bash tool on anything naming a `.env` path**, and on `grep`
  patterns that look credential-shaped. Use the Grep tool or a script.
- 🔴 **Do not commit `_context/clients/fz-llc-uae/proposal/`** — public repo, live negotiation.
- **Must stay untracked** (plaintext credentials, public repo):
  `backend/app/scripts/{system_admin,sync_system_admin,seed_fz_llc,seed_demo_kitchen}.py` and
  the four `verify_*.py`.
- **Anthropic key rotation is still pending.** Malik deferred it this session
  (*"its fine for now. drop that note"*). It is Thrive's live production key. Do not raise it
  again unless he does.
- **Martin's login was written to `C:\Users\Malik\Desktop\martin-login.txt`** at his request.
