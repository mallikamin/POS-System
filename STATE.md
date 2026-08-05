# STATE — Restaurant POS System

**Last refreshed:** 2026-08-05 (03:55 UK) — session U. **Branch:** `main`, HEAD `d9f57e7`
(`99b6757` + the docs close-out commit; the ~124-file uncommitted doc reorg in the tree is the
known pre-existing one, not new work).
**Nothing is in flight. All shipped work below is deployed, verified live, and committed.**

## 🟡 Raised by Malik 2026-08-05 — three observations. BUILT + TESTED LOCALLY, **NOT DEPLOYED**

Registered as **OI-69 / OI-70 / OI-71** in `_state/open-items.md`. Malik picked the approach for
each before any code was written. **Committed? No. Pushed? No. Live? No.** Awaiting his go-ahead.

| # | What he saw | Verdict | Built |
|---|---|---|---|
| **OI-69** | No way to log out of `/online-orders` — "stuck in this window" | **Real, and a closed loop.** `/online-orders` sits outside both layouts, which own the only logout buttons; `/login` bounces an authenticated user to `/`, and `/` redirects back to `/online-orders` for this tenant. Only escape was typing `/admin`. | New bookmarked **`/switch`** route: sign out + clear the remembered shop + land on a login form with an optional Restaurant field. **Deliberately unlinked from the queue** so the shop's unattended tablet can never hit it mid-service. |
| **OI-70** | Wants Garelochhead local time, placed vs accepted | **Real, two defects.** No absolute time and no accepted time on the card at all; and `placedAt()` had no `timeZone`, so it rendered in the *viewer's* zone — right on the shop tablet by accident, silently +4/5h wrong on Malik's screen in Pakistan. | Card now reads `12 min ago · placed 19:56 · accepted 19:59`, every clock time from `config.timezone` (`Europe/London`). Pending keeps the relative age because it is what justifies the red/amber border. |
| **OI-71** | Dip tubs still under the parent item — "are receipts working?" | **Receipts were already fine — verified inside the running container, not assumed.** `DIP TUBS` roll-up live in `print_service.py` (server at `d9f57e7`, `grep -c` → 1). One-line gap in the tablet UI only. | Card now shows a `DIP TUBS` block with per-name counts and drops dips from the item sub-lines — same grouping and same `" (Dip Tub)"` suffix rule as the ticket. |

**Scope: tablet frontend only. Zero backend diff, zero storefront diff** — no payment, order-number,
email, ticket or reporting path is touched, so yesterday's clean day cannot be regressed by this.

**Verification actually run** (not claimed): `tsc --noEmit -p tsconfig.app.json` clean · `vite build`
clean · eslint **0 issues in every touched file** (the repo's 22 pre-existing problems are unchanged
and all in files not touched here) · the pure display helpers extracted to `frontend/src/lib/
orderDisplay.ts` and **bundled with esbuild and run for real** — 29/29 against real 2026-08-04 orders
(`C010`, `C011`, and Malik's 3× Fillet Tower screenshot), including GMT/BST, midnight rollover and a
bad-timezone fallback. **The runner's own process timezone was `Asia/Karachi`** — i.e. the bug's
actual conditions — and it still produced UK times. Both fixes **mutation-checked**: removing the
`timeZone` option fails 12 tests, counting dip occurrences instead of quantity fails 2.

> ⚠️ **Do not `git add -A` here.** The tree still carries OI-60's paused, **never build-tested**
> backend work (`backend/Dockerfile`, `backend/scripts/start.sh`, `backend/logging_config.json`) —
> `start.sh` gained `--log-config logging_config.json`, which would go to production untested and
> can break backend startup. Also uncommitted and unrelated: `StaffManagementPage.tsx` (+41),
> `QUICKBOOKS_PLAYBOOK.md`, `seed_demo_kitchen.py`, and the ~119-file doc reorg. **Stage by explicit
> filename**, exactly as session S did.


## 🟢 Where things stand at the end of 2026-08-04

**The shop's first full day on the fixed card flow: 11 online orders, all 11 paid, £349.72, zero
unpaid, zero rejected.** Verified against the production DB, not assumed. Every order was card, every
one captured. Malik's own read of the evening: *"rest of the day went smooth."*

| Order | Placed (UK) | Type | Total | Paid |
|---|---|---|---|---|
| `260804-001` … `-004` | 15:26–16:24 | mixed | £36.04 / £62.92 / £70.32 / £12.69 | ✅ |
| `260804-D005` … `-C011` | 16:46–19:56 | mixed | £15.67 … £20.86 | ✅ |

The switch from `260804-004` to `260804-D005` mid-service is the C/D numbering going live. **No
existing order number was rewritten** — by design.

**🔴 Resume here — nothing is broken; these are the open threads:**
1. **Imran/Malik UAT the pause button on the real tablet.** It is live but has never been pressed in
   anger. It needs a page refresh on the tablet to appear (new JS bundle, old one cached) — Malik hit
   exactly this and thought it was missing.
2. **OI-60 (backend log persistence) is still paused and uncommitted**, untouched since session Q.
   6 files written, not build-tested. See `_state/open-items.md` OI-60.
3. **OI-63 test flakiness is now understood but unfixed** — see the note at the bottom of this block.

### What happened on 2026-08-04 (sessions T, in order)

**1. OI-65 — the card gate, rebuilt as an actual rule.** Imran's screenshot showed order `260803-003`
reading "CARD — PAYMENT PROCESSING" while already accepted. Root cause: OI-61's gate was a `WHERE`
clause on the `pending` query only, and the tablet's ungated **All** tab still drew live Accept
buttons. `accept_order` had no server-side check at all. Money was never at risk — 16 card orders
across 02–03 Aug reconciled 1:1 against 16 live Stripe PaymentIntents, all `succeeded`.
- ⚠️ **My first attempt was rejected, correctly.** It gated only `pending` (repeating the same
  mistake) and papered over the hole with a "Waiting for the customer's card payment" panel on the
  All tab. Malik: *"'waiting for customer's card payment' is exactly what we dont want to show in
  POS… why are u putting in temporary hacks?"* **Lesson kept: when a rule is bypassed through an
  ungated view, close the view — never dress the hole up in the UI.**
- Final shape (`d3d1e7d`): gate on **every** queue state; hard server-side guard in `accept_order`
  (`CardPaymentNotConfirmed`); no grace window at all; poll-time Stripe re-check so publication never
  depends on one webhook; atomic conditional `UPDATE` for the publication claim; "order received"
  email moved to the moment Stripe approves. Tablet files reverted byte-identical to `1f55cf1`.

**2. The £98.96 report scare — the real money-display bug.** The reports screen showed £98.96 online
and "prepaid" revenue when only £36.04 had been taken. Two causes: both report queries summed
`Order.total` for every non-voided order, and "prepaid" meant `stripe_checkout_session_id IS NOT
NULL` — a session created the instant the customer reaches Stripe, paid or not.
- Fixed in `4e2fe5c`: prepaid now means `payment_captured_at IS NOT NULL`, and reports exclude card
  orders Stripe never approved, exactly as the tablet does.
- **Root cause of all three incidents in three days was the same**: the "is this order real" rule
  written in one place and not the others. It now lives once, in
  **`backend/app/services/order_visibility.py`** (`is_real_order()` / `money_actually_taken()`), and
  the queue, the reports and the prepaid split all import it. **Do not re-express it inline.**
- Same commit fixed the wording that caused the scare: an order on the tablet is now *always*
  Stripe-approved, so "CARD — PAYMENT PROCESSING" was false. Reads **`CARD APPROVED — DO NOT
  COLLECT`** with the held amount; ticket prints `*** CARD APPROVED ***`.

**3. Imran's two new features (`6378b67`).**
- **Pause online ordering** — one tablet button, stops collection and delivery together. Enforced
  server-side in `create_public_order` (HTTP 503, `OnlineOrderingPaused`), **not just hidden in the
  storefront**. While off the customer's whole checkout form — name, phone, address and the Pay
  button — is not rendered; they get Imran's exact wording with the phone number, on the homepage and
  at checkout. Orders attempted while paused are **lost by design** (Malik's explicit call).
  Default is ON. Turning OFF asks for confirmation; resuming is one tap.
- **C/D in online order numbers** — `260804-C001` / `260804-D002`, **one shared counter**.

**4. The counter race Malik caught (`99b6757`).** He spotted that a probe printed `-C006` and `-D006`
together and asked how two orders could share a number. The probe output was misleading (three calls,
nothing saved between them) — but he had found a real hole I introduced: with the C/D letter,
`count(*) + 1` could hand `C006` and `D006` to two simultaneous orders, and those are *different
strings*, so `uq_order_tenant_number` could not catch it either.
- Fixed: allocate from the **highest number already issued today** with the letter stripped (one
  sequence across both letters, and no rewind onto a number already printed when a row is voided),
  under a per-tenant `FOR UPDATE` lock so a read-modify-write cannot double-issue.
- Checked production first: **zero duplicate order numbers have ever existed.** Closed before it bit.
  The closest real case was `C010`/`C011`, 22 seconds apart — well outside the window.

### Verification standard actually met (not just claimed)
515 tests passing, failure list compared against a clean-HEAD `git worktree` — **zero regressions**.
`ruff` clean on touched files, `tsc`/`vite build` clean for tablet and storefront. Deploy verified by
reading symbols **out of the running application object**, resolving `index.html` → entry → chunk for
the frontends, and proving the queue gate end-to-end with a probe order that was rolled back.

### ⚠️ Two traps that cost time today — read before verifying anything
- **`/usr/share/nginx/html/assets/` accumulates every historical chunk** (uploads never `--delete`).
  Grepping the assets directory proves nothing. Resolve `index.html` → `index-*.js` → the chunk it
  actually imports.
- **~10 test failures are time-of-day dependent, not real** — the OI-63 UTC-vs-Europe/London boundary
  bug. They fail late at night and pass in the afternoon. **A baseline captured at 23:00 is not
  comparable to a run at 16:30.** Re-baseline at the same clock, in a worktree, before claiming
  regressions. Still unfixed; this is the honest explanation for the count moving 21 → 13 → 10.

**⚠️ Superseded — kept only for the lesson.** The session's FIRST attempt (`a7da2fb`) was a
workaround and Malik rejected it, correctly. It gated only `state="pending"` — inheriting OI-61's
original scoping mistake — and then papered over the resulting hole by replacing the tablet's
Accept/Reject buttons with a "Waiting for the customer's card payment" panel on the "All" tab. Two
things wrong with that: he never asked for the Accept button to change, and **a "waiting for card
payment" row in the POS is exactly what the rule exists to prevent** — an unpaid card order should
not be there to be labelled in the first place. Corrected in `d3d1e7d`: **the gate applies to every
queue state**, the two frontend files are reverted byte-identical to `1f55cf1`, the Accept button is
untouched, and the `awaiting_card_payment` field (which existed only to drive that panel) is gone.
**The lesson, worth keeping: when a rule is bypassed through an ungated view, close the view — do
not dress the hole up in the UI.**
**✅ OI-65 is BUILT, TESTED, DEPLOYED and INDEPENDENTLY VERIFIED LIVE** (commits `a7da2fb` +
`93876b1`, 2026-08-03 ~23:15 UK / 2026-08-04 ~03:15 PK, after the shop's 22:00 close so no order was
in flight). Full detail in `_state/open-items.md` **OI-65**.
**🔴 Next action: Imran/Malik's live UAT on tomorrow's real card orders** — specifically that a card
order now appears on the tablet only *after* Stripe approves, and that the customer's "order
received" email arrives at that moment rather than at checkout. Nothing else outstanding.

**Session T in one line (2026-08-04): Imran's screenshot showed order `260803-003` reading "CARD —
PAYMENT PROCESSING" while already accepted — i.e. OI-61's card-payment gate was bypassed in
production within a day of shipping. Root-caused against the real DB, audit trail and live Stripe
API; reconciled the money (clean, no loss, no double-charge); then rebuilt the gate as an actual
invariant per Malik's rule that a card order must not land in the POS until Stripe approves it, with
no timeout of any kind.**

- ⚠️ **CORRECTION to session S's claim below.** Session S described OI-61 as *"the structural fix, so
  staff can no longer act on money that isn't confirmed yet."* **That was overstated.** What shipped
  was a `WHERE` clause on `list_merchant_orders(state="pending")` only. The tablet renders
  Accept/Reject for any unanswered order on **every** tab, the "All" tab is ungated, and
  `accept_order` had no server-side guard at all. Production found the hole the next day. Session S's
  own "6 of 11 (55%)" figure did improve to **1 of 5 (20%)** on 08-03 — the fix helped materially, it
  just was not the guarantee it was written up as.
- **The money is fine, and this is verified, not assumed:** 16 card orders across 02–03 Aug ↔ 16 live
  Stripe PaymentIntents, 1:1, all `succeeded`, `amount_received == amount` on every one. Zero
  uncaptured, zero dangling authorisations, zero orphan charges, nothing to refund. `260803-003` was
  charged exactly once, correctly, by a late capture at 17:11:02. **This was a real defect but not a
  financial incident.** OI-61's *secondary* net (the amber "CARD — PAYMENT PROCESSING" banner instead
  of red "NOT PAID — COLLECT") is why it surfaced as a question from Imran rather than a second
  double-charge.
- **The 5-minute grace window was the deeper error and is now gone entirely.** It would not have
  saved this order regardless of the All-tab hole: it would have released it at 17:09:51, still 70s
  before Stripe authorised at 17:11:01. The customer spent 6m06s on the Checkout page; the window had
  been calibrated on one day's worst case (179s) and was exceeded the very next day.
- **Malik's rule, implemented literally:** cash/COD lands as-is (no payment to process); a card order
  lands only once Stripe approves, however long that takes. Enforced in three places rather than one
  — the queue filter, a hard `accept_order` guard (`CardPaymentNotConfirmed`) that closes the All
  tab / stale render / direct-API paths, and a poll-time Stripe re-check
  (`publish_authorized_card_orders`) so publication never depends on a single webhook delivery. The
  publication claim is an atomic conditional UPDATE so the webhook and the tablet's two 10s polls
  cannot all "win" and triple-email the customer.
- **The "order received" email moved to the authorisation moment** — it used to fire before the
  customer had even reached Stripe, which under a hard gate would promise food for an order the shop
  can never see. Cash on delivery is unchanged.
- **496 passed** (baseline 485 + 11 new), failure list byte-identical to clean HEAD via a throwaway
  `git worktree`, zero regressions. `ruff`/`tsc`/`vite build` clean. `authorization_for_session`
  verified against the **real live Stripe API**, not only mocks.
- **Deployed and independently verified live, beyond the green Action** (this project's own "verify
  the effect, never the exit code" rule), final commit `d3d1e7d`: server `git log` matches;
  backend/frontend/nginx containers freshly recreated and healthy; symbols read back **out of the
  running application object**, not the file on disk (`publish_authorized_card_orders` and
  `CardPaymentNotConfirmed` present, `awaiting_card_payment` confirmed **absent** from the live
  `MerchantOrderSummary` schema, `PENDING_QUEUE_PAYMENT_GRACE` genuinely **gone — 0 references in
  both `public_order_service.py` and `print_service.py`**, `mark_card_order_authorized` correctly
  async).
- **The tablet is back to its original bundle, proven by content hash.** The live `index.html` loads
  `OnlineOrdersPage-bINTpwNa.js` — the exact chunk that was live *before* this session. Vite's
  content hashing means an identical hash is proof the source reverted byte-for-byte. Confirmed in
  that chunk: `"Accept"` and `"Reject"` present, "Waiting for the customer" **0**,
  `awaiting_card_payment` **0**. ⚠️ Note for future verification: `/usr/share/nginx/html/assets/`
  **accumulates every historical chunk** (uploads never `--delete`), so grepping the assets directory
  proves nothing — resolve `index.html` → `index-*.js` → the chunk it actually imports.
- **Proven end-to-end against the live database with a real probe order**, then cleaned up: an unpaid
  card order (`stripe_checkout_session_id` set, `payment_authorized_at` NULL) was **invisible in all
  three states — pending, active AND all**; the instant `payment_authorized_at` was set it became
  visible in pending and all. Probe deleted and confirmed gone. This is the actual behavioural proof,
  not a code reading.
- ⚠️ **One residual, stated rather than glossed:** the *negative* case (an unpaid Stripe session
  returning not-authorised) is unit-tested and safe by construction — the gate keys off PaymentIntent
  **status**, and `requires_capture`/`succeeded` *are* Stripe's own statement that money is held — but
  it was never exercised against a real unpaid live session, because all 17 live sessions are
  `complete`/`paid` and manufacturing one means creating a session on Imran's live Stripe account.
  Offered to Malik as an explicit option; he chose to deploy without it. **Tomorrow's first real card
  order is therefore the true end-to-end proof of the negative path.**

---

**Session S in one line (2026-08-03): Imran reported (voice notes) a real double-charge — a
customer paid online but the ticket and "accepted" email both said NOT PAID because staff accepted
before Stripe's authorisation landed; staff took payment again on the card machine and had to
refund. Confirmed 6 of 11 card orders that day (55%) hit this same race. Fixed at the source: a
card order is now hidden from the tablet's pending decision queue until Stripe confirms
authorisation (or a 5-minute grace window passes), so staff can no longer act on unconfirmed money
— plus defense-in-depth (ticket auto-invalidation on payment-status change, a 3rd "CARD
PROCESSING" ticket/tablet state, late-capture re-sends the "accepted" email, email wording keyed off
`stripe_checkout_session_id` not `stripe_payment_intent_id`). Same commit also shipped a 70p flat
service fee, dip-tub ticket consolidation, and a Z-Report currency-on-direct-landing fix.**

- 18 new tests, 476 passed; 13 pre-existing failures confirmed unrelated via clean-HEAD `git stash`
  comparison done BEFORE writing any code (logged as **OI-63**, not fixed — likely a date-boundary/
  timezone bug in `online_report_service.py`, distinct from the older OI-59 SQLite `func.cast` issue).
- `pg_dump` backup taken first (`~/backups/pre_oi61_20260803_045556.dump`). Committed (`f06979f`),
  staged by explicit filename (not `git add -A`, to avoid sweeping in the ~119-file pre-existing doc
  reorg sitting uncommitted in the tree). Pushed and deployed both pipelines — backend/tablet via
  `git push` (GitHub Actions, server `git log` matches, new code grepped directly out of the running
  container) and storefront via `cd storefront && npm run deploy` (Cloudflare, live bundle
  byte-identical to the local build, contains the new "Service Fee" line).
- **Malik's own retry/fallback idea and Imran's "pause accepting orders" toggle idea were
  deliberately NOT built tonight** — logged as **OI-62** for later scoping, not rushed on a live
  payments system under time pressure.
- **New priority raised in the same session, not yet started**: Malik is travelling and unavailable
  today, Imran is off, and the shop is staffed by people unfamiliar with the system. He wants a
  couple of hours of stress testing to confirm the card-payment flow works end to end before trusting
  it unsupervised. He has no live card and floated Stripe test/sandbox mode without disturbing the
  live storefront (`chickshackg84.com`, real orders, live Stripe keys) — asked for a concrete plan,
  not just validation of the idea. Full options already scoped in
  `PAUSE_CHECKPOINT_2026-08-03.md`'s Pending section: direct-API test bypassing the storefront,
  local dev's Stripe-key situation, whether real production traffic already exercises the fix enough
  to skip a synthetic re-test. **This is the next action.**

---

**Session Q in one line: Malik asked to double-check the card-payment flow for a specific loophole
("do we ever assume the customer has paid when he hasn't?"). Traced the whole pipeline (tablet,
ticket, email, confirmation page) and confirmed no such loophole exists — all four independently key
off the same server-derived `payment_status`, which only flips to `paid` via a real captured Payment
row. Found one real, narrower gap instead: a race between the shop answering an order (Accept/Reject)
and the customer's card finishing authorisation — fixed and deployed, commit `dfc88e9`. Also added a
durable Stripe audit trail per Malik's request ("keep all logs ... so any dispute can easily be
addressed"). Malik explicitly said "yes commit push deploy live" before any of this happened. Deploy
verified live beyond the green Action — see below.**

- **The race window**: `accept_order`/`reject_order` only ever act on a Stripe PaymentIntent that
  already exists at the moment they run. If staff tap Accept/Reject while the customer is still
  entering card details, there is nothing yet to capture/cancel — correct, falls through as an
  ordinary unpaid order (tablet shows "NOT PAID — COLLECT"). But if the authorisation then lands a
  few seconds later, nothing was previously watching for it: the hold just sat there until Stripe
  auto-expired it days later (no revenue loss or double-charge risk, but a dangling, unreconciled
  authorisation and potential customer confusion). **Fixed**: `reconcile_late_authorization()`,
  triggered from the same `payment_intent.amount_capturable_updated` webhook event that already
  backfills the intent id, closes it symmetrically — captures if the order was already accepted
  (kitchen already committed to the food), releases if already rejected, no-ops if still pending or
  already captured. A late capture that itself fails is logged loudly (`stripe_capture_failed`) as an
  unavoidable, human-needs-to-know case — food already made, card genuinely declined at the capture
  moment, cannot be fixed programmatically.
- **Durable Stripe audit trail**: every Stripe transaction now writes to the existing `audit_logs`
  table (tenant-scoped, queryable by `entity_id` = order id) — checkout session created, capture on
  Accept, cancel on Reject, and every webhook delivery received, *including* `payment_intent.canceled`/
  `payment_intent.payment_failed`, which deliberately change nothing on the order but are still real
  events a dispute conversation may need evidence of. Each row carries the Stripe event/intent id,
  amount, and who did it (staff user id for Accept/Reject, "Stripe webhook" for automated events).
  **Caveat**: DB-only for now, no viewer page — look it up via `make psql` filtering
  `entity_type='order' AND entity_id=<order id>` until/unless a report UI is asked for.
- 9 new tests (functional: late-capture, late-cancel, still-pending no-op, no-double-capture-on-
  replay, failed-late-capture; audit: checkout/accept/reject/webhook-event logging). Full suite:
  **479 passed**, same 14 pre-existing unrelated failures as session P (2 session-O + 12 QB-Desktop/
  parked) — zero new regressions, exact expected delta. `ruff check` clean.
- **Deployed and independently verified live, commit `dfc88e9`.** `git push origin main` (backend-
  only, no `storefront/` changes). "Deploy to Production" Action green including its own "Verify
  deployment" health check. Independently confirmed beyond the green Action: SSH'd in, `git log` on
  the server matches `dfc88e9` exactly, `pos-system-backend-1` freshly recreated and healthy; **the
  new code was grepped directly out of the running container** (`reconcile_late_authorization` present
  in `/app/app/services/public_order_service.py`, plus the new `stripe_checkout_created`/
  `stripe_capture_failed` audit action strings) — not assumed from the diff.
- **Next action for the Stripe fix itself**: nothing outstanding. The fix is dormant until the
  specific race timing occurs again in production; no live UAT step is needed (it is not a UI-visible
  feature).

## 🔴 Resume here — session Q paused mid-task 2026-08-02, two open threads

1. **Imran email check → found the real production log-retention gap → OI-60 opened → paused
   mid-build, on Malik's instruction, to write this down properly before continuing.** Full detail,
   design, and an exact done/pending file checklist: `_state/open-items.md` **OI-60**. Short version:
   - Imran said he placed two dummy test orders (collection + delivery) and didn't get an email for
     one. Checked the DB directly: the delivery order's email was typed `imzyyr@gmail.con` (missing
     the "m"), the collection order's was correct. **Not a code bug** — confirmed the email-send path
     has no service-type branching at all, and told Malik so.
   - That check needed yesterday's backend logs, which were already gone — the container had been
     recreated by this same session's own earlier deploy. Root cause: `backend`/`nginx` are
     `read_only: true` with no persistent volume, and both are recreated on every `git push`, so
     `docker logs` history resets on every deploy (this repo deploys several times a day).
   - **OI-60a (backend fix) is fully designed and all 6 files are WRITTEN, but UNCOMMITTED** —
     `backend/Dockerfile`, `backend/logging_config.json` (new), `backend/scripts/start.sh`,
     `docker-compose.demo.yml`, `docker/logrotate/pos-backend.conf` (new), `scripts/deploy-remote.sh`.
     The logging dictConfig was validated directly (`logging.config.dictConfig()`, not just read) and
     one real duplicate-handler bug was caught and fixed before it ever reached a container. **Not yet
     build-tested against the real Dockerfile** (local dev compose uses a different `Dockerfile.dev`,
     so it won't exercise these changes) **and not committed/pushed/deployed.** OI-60's checklist in
     `_state/open-items.md` has the exact resume point — read it before touching these files again,
     don't rediscover the design from scratch.
   - **OI-60b (nginx) is deferred and not started at all**, deliberately — nginx is shared with Orbit
     CRM and this box has two prior nginx-recreation outages on record. Treat as fully separate,
     re-derive its specific design (don't assume OI-60a's UID/handler approach transfers as-is).
2. **Stripe went LIVE and was proven with a real transaction, 2026-08-02 (verbal from Malik + Imran,
   cross-checked against our own DB — not yet independently re-verified by this session against a
   fresh read after the fact).** Malik set the 3 live values (`STRIPE_SECRET_KEY`, `STRIPE_
   PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`) directly on the server himself (values never passed
   through the assistant — verified only by safe prefix-count checks, e.g. confirming the running
   container's key starts `sk_live_`, never printing it). Real order `260801-004` (collection, £2.78,
   Imran's own card) was placed via the existing `?card=1` test override and accepted — **captured
   for real**, confirmed three ways: Stripe's own live dashboard (Mastercard •••5881, "Succeeded")
   and its "first payment" email, our `orders`/`payments` tables (matching amount and PaymentIntent
   id), and this session's own new audit trail (`stripe_checkout_created` with a `cs_live_...` session
   id → `stripe_captured` → `stripe_webhook_payment_intent.succeeded` landing 2s later, proving the
   live webhook registration is genuinely working end to end, not just Accept's own direct capture).
   **Imran approved going fully live, in writing (WhatsApp, shown to the assistant):** "Yes please...
   Ready to go live tomorrow... we will see how things are."
   - **Three things Imran asked for in the same message, now being built (2026-08-02, still same
     session): make the card option live, remove the "under testing" banner, and add a delivery
     cut-off mechanism.** Voice-note feedback on the third item was transcribed locally
     (`faster-whisper`, matching the established pattern from session K) — see
     `_context/clients/chick-shack-uk/voice-notes/` for a written copy once saved. Requirement:
     online delivery stops being taken at **21:30** for every delivery area except **Garelochhead**
     (**21:45**) — confirmed against the real `delivery_areas` table, not guessed from the mis-
     transcribed "gear lockhead". Collection is unaffected, stays open to the shop's normal 22:00
     close. **Malik corrected the assistant's first proposed design** (hiding the delivery option
     entirely) — the actual ask: reuse the *existing* pre-order pattern (`lib/delivery.ts`
     `orderTiming`/`isOpenNow` — "closed, opens at 16:00, your order will be accepted then, and
     you'll get a confirmation email") but trigger it for delivery specifically at the earlier
     cut-off, not just at the shop's overall close time. No backend/DB change expected — delivery
     areas and shop hours are both plain storefront config (`storefront/src/data/menu.ts`), not
     API-fetched.
   - **Malik's own words, explicitly expected and fine, not a bug if seen:** deploying this outside
     current opening hours means any real order placed overnight will correctly show as a pre-order
     and get "accepted when the restaurant opens tomorrow" — that is the intended behavior, not a
     regression.
   - **⚠️ Malik then corrected the design a second time** (his message: "no dont remove the delivery
     option - that will cause confusion"). Final, actually-being-built behavior: the delivery option
     stays visible always. Past its cut-off (or before opening, or after the shop's general close),
     it gets the SAME "closed, opens at 16:00, accepted then, confirmation email coming" pre-order
     treatment already used shop-wide — never hidden, never a separate refusal path.

## 🔴 Resume here — session Q paused via /handoff mid-build 2026-08-02, THREE threads

**A — delivery cut-off + card-live + banner-removal feature: CODE MOSTLY WRITTEN, UNTESTED,
UNCOMMITTED.** 7 storefront files touched (`git status --porcelain -- storefront/src` confirms
exactly these, nothing else): `types.ts`, `data/menu.ts`, `lib/delivery.ts`, `lib/pendingOrder.ts`,
`components/Checkout.tsx`, `components/OrderConfirmation.tsx`, `App.tsx`. What's actually done vs
not — **read this list before touching these files, don't rediscover the design:**
- [x] `types.ts` — `DeliveryArea.closeTime?` (per-area override) + `ShopConfig.deliveryCloseTime`.
- [x] `data/menu.ts` — `deliveryCloseTime: "21:30"`; Garelochhead's entry gained `closeTime: "21:45"`.
- [x] `lib/delivery.ts` — `orderTiming(now, service?, areaId?)` extended (backward compatible,
      existing no-arg callers still work), returns a new `closedReason: "shop_closed" |
      "delivery_cutoff"` field. New private `deliveryCloseTimeFor(areaId)` helper.
- [x] `components/Checkout.tsx` — `timing` now computed from live `service`/`areaId` state (was
      shop-wide only); pre-order banner copy branches on `closedReason` + now promises the
      confirmation email; `onPlaced`/`savePendingOrder` signatures extended to carry `timing` through
      (needed because the Stripe round-trip is a fresh page load — nothing survives except what's
      explicitly stashed).
- [x] `lib/pendingOrder.ts` — `Stashed`/`savePendingOrder`/`takePendingOrder` all carry `timing`
      alongside the order now; **`takePendingOrder`'s return shape changed** from `ApiOrderResponse |
      null` to `{ order, timing } | null` — this is the one signature change most likely to bite if
      re-derived from memory instead of read.
- [x] `App.tsx` — new `timing` state threaded through `onPlaced`/the Stripe-return effect/
      `OrderConfirmation`/`onDone` reset. `restored` (from `takePendingOrder`) updated for the new
      `{order, timing}` shape.
- [x] `components/OrderConfirmation.tsx` — takes `timing` as a required prop instead of calling
      `orderTiming()` itself (avoids a second, possibly-different computation after time has passed);
      copy updated to branch on `closedReason` + mention the confirmation email, matching Checkout's.
- [x] **`tsc`/`vite build` — DONE, session R (2026-08-02).** `tsc --noEmit` clean, `vite build` clean
      (46 modules, no errors) — the Checkout↔App↔OrderConfirmation↔pendingOrder prop/return-shape
      wiring is consistent.
- [x] **Manual verification of the cut-off math — DONE, session R.** Bundled `delivery.ts` with
      esbuild and ran the real `orderTiming()` (not a reimplementation) against 18 real-clock-time
      cases in `Europe/London`/BST: pre-order window open (14:00), shop open/close (16:00/22:00),
      21:29/21:30 non-Garelochhead delivery cutoff, 21:44/21:45 Garelochhead's own later cutoff,
      collection unaffected through to 22:00, overnight pre-order, and both backward-compat fallback
      paths (no `areaId`, no `service` at all). All 18 matched the intended design exactly — cutoff is
      inclusive (>=), collection only stops at the shop's general close, Garelochhead's 21:45 override
      is respected.
- [x] **`cardPaymentEnabled: true` flip — DONE, session R** (`data/menu.ts` ~line 567).
- [x] **"Under testing" banner — REMOVED, session R** (`App.tsx`, was lines ~97-112; the sticky
      header wrapper itself was kept, only the banner `<div>` and its comment were deleted). Rebuilt
      after both changes — `tsc`/`vite build` clean again, and the built `dist/` bundle greped clean
      of the "under testing" string.
- [x] **DEPLOYED AND VERIFIED LIVE, 2026-08-02 ~18:00 PK / ~14:00 UK, commit `678cdde`.** Malik
      pinged with explicit go-ahead ("we can initiate the deployment. over to u") after his ~2hr gap.
      Committed the 7 storefront files only (not the unrelated, still-unfinished OI-60 backend files),
      `git push origin main`, then `cd storefront && npm run deploy` (`vite build && wrangler deploy`
      — Cloudflare Workers, separate pipeline from the DO backend). **Verified beyond the exit code**:
      live `index.html` references the exact just-built bundle hashes (`index-a54c_nbI.js`/
      `index-iaUHhEfe.css`); the live JS bundle fetched from `chickshackg84.com` is **byte-identical**
      to the local build output (194,249 bytes, `diff` clean); the "under testing" banner string has
      **zero occurrences** in the live bundle. Both `chickshackg84.com` and `www.chickshackg84.com`
      serving the new version. **Real customers now see the live card-payment option, the delivery
      cut-off (21:30/21:45 Garelochhead) is active, and the testing banner is gone.**
- [x] **"Stripe Reconciliation" mismatch — INVESTIGATED, CONFIRMED, and the underlying test orders
      CLEANED UP, session R (2026-08-02).** Confirmed against the real DB (not just STATE.md prose):
      `260801-002`/`-003` had `cs_test_...` checkout session ids, created 17:48/19:21 UTC on
      2026-08-01 — before the live key went on the server at ~20:01 UTC that same day (right before
      `260801-004`, which has `cs_live_...`). Stripe correctly refuses to find a test-mode
      PaymentIntent via a live key — expected behavior, not a money-safety bug (`cardPaymentEnabled`
      was `false` for real customers the entire time Stripe was in test mode, so these could only have
      been internal `?card=1`-override tests, never a real customer). **Malik then asked to clear
      test orders for a clean slate.** Pulled all 17 orders ever placed for the tenant, classified
      them, and got his explicit scope: pg_dump backup taken and verified (42 tables, `orders` table
      confirmed present) → checked for `inventory_transactions` FK blockers (none) → deleted 11 orders
      (`260729-001/002/003`, `260730-001`, `260731-001/003/004/005`, `260801-001/002/003`) plus 3
      orphaned `audit_logs` rows tied to `260801-003`, in one transaction, verified via row-count
      output (`DELETE 3` / `DELETE 11`) and a post-delete re-query. **Deliberately kept, per Malik's
      explicit choice**: `260801-004` (the one proven real-money live capture — now the only
      `payment_status='paid' AND stripe_payment_intent_id IS NOT NULL` row left, confirmed by query —
      reconciliation will now show 1 checked / 0 mismatches), plus 4 orders with real-looking UK
      customer details (Jill Cochrane `260730-002`, Daisy Glover `260730-003`, Gregg Ross `260730-004`,
      Rachel Mccoll `260730-005`, all `voided`) that were NOT confirmed as test data — left untouched,
      not silently assumed to be test orders.
- [ ] **Separately flagged, not yet acted on: `260731-002` ("Leanna") is sitting `in_kitchen`,
      unpaid, since 2026-07-31 20:01 — neither voided nor completed.** Not part of the cleanup scope
      (real-looking customer details, same ambiguity as the 4 kept-voided orders above). May be a
      genuinely unresolved real order Imran's team never closed out — worth asking him about, not
      assumed either way.

**B — Malik asked (2026-08-02) whether deployment can be scheduled automatically for "tomorrow",**
since that's when Imran said he's ready to go live, rather than needing a live session at the exact
moment. **Not yet investigated or answered.** Real considerations for whoever picks this up:
`schedule`/`CronCreate` tooling exists and could fire `cd storefront && npm run deploy` at a set
time, but `DEPLOYMENT_PLAYBOOK.md` is explicit that a storefront deploy is "the UAT trigger... run it
only when he is at the tablet and expecting it. Time it with him" — "tomorrow" is not a time. Get an
actual HH:MM from Malik/Imran before building any automation, and confirm whether Imran wants to be
online watching at that exact moment (matching how the live Stripe test itself was coordinated) or is
genuinely fine with an unattended scheduled push.

**C — OI-60 (backend log persistence) is still separately paused from earlier in this same session,
untouched since.** See the OI-60 entry above and `_state/open-items.md` — unrelated to A/B, don't
conflate.

---

**Session P in one line: OI-57 (online-orders date filter/pagination/sort) and OI-58 (Chick Shack
reporting) are both BUILT, tested, and DEPLOYED to production, commit `55ac6de`. Malik confirmed
"commit and push" explicitly before either happened. Deploy verified live, not just green CI — see
below. Awaiting Malik's UAT.**

- **OI-57 built**: `list_merchant_orders` gained `date`/`date_from`/`date_to`/`offset`/`sort`
  (shop-timezone-aware day bounds, same fallback pattern as `print_service._offset_minutes`);
  `MerchantQueueResponse` gained `total_count`/`offset`/`limit`/`sort`; `OnlineOrdersPage.tsx` got a
  date picker, pagination controls and a sort toggle for Active/All (Pending's FIFO default kept,
  exactly as flagged for UAT). 8 new backend tests reproduce the exact reported bug and prove it
  fixed. Curl-verified against the known 7-orders-from-2026-07-28 local dataset: today-only default
  correctly shows 0 pending, an explicit `date=2026-07-28` correctly shows the 5 unaccepted ones,
  pagination and both sort directions all hand-checked.
- **OI-58 built, all four reports, in priority order**: fixed the mechanism first —
  `get_sales_summary` now exposes `online_revenue`/`online_orders` (was computed then silently
  discarded) and `get_live_operations` gained an `online` bucket, both platform-wide fixes, not
  Chick-Shack-only. New lean route `/online-orders/reports` (`OnlineReportsPage.tsx`), ink/flame/
  ember branded, shop name from `useConfigStore` (never hardcoded). Daily Sales reuses the
  now-fixed sales-summary endpoint; Prepaid vs Cash-on-Delivery and Rejected Orders are new
  dedicated queries (`online_report_service.py`); Stripe reconciliation (built last, per Malik's
  "maybe") added a read-only `stripe_service.retrieve_payment_intent` and degrades to an error row
  instead of a 500 when Stripe isn't configured (confirmed live in local dev, which has no Stripe
  key). 19 new backend tests. Curl-verified against real Postgres with a hand-built prepaid/COD/
  rejected order trio; every CSV actually downloaded and its content read, not just status-checked.
- ⚠️ **Real, separate bug found and deliberately NOT fixed (logged, not silently absorbed)**: this
  whole project's `func.cast(Order.created_at, Date)` report date-filter pattern is silently
  unverifiable by the backend's own pytest suite (SQLite casts it to a bare integer year, which can
  never compare true against a date bound) — every date-ranged report test that has ever passed did
  so with zero real orders behind it. Production is unaffected (real Postgres casts correctly,
  confirmed live). New OI-58c/d queries were written with plain datetime-range comparisons
  specifically to avoid inheriting this. Full root-cause in `ERROR_LOG.md` 2026-08-01, tracked as
  **OI-59** (low priority, not scheduled).
- Backend suite: **470 passed** (450 baseline + 19 new + 1 fixture change), same 2 pre-existing
  unrelated failures from session O plus the same 12 QB-Desktop/parked ones — nothing new broken.
  `tsc`/`vite build`/eslint clean for `frontend/`.
- **Browser click-through of the new UI was not possible** — the Chrome extension still will not
  connect, consistent with every session this week (see session L/M/N notes below) — verified
  instead via the production build output and by calling the exact same API endpoints the page
  calls, with hand-checked responses.
- **Deployed and independently verified live, commit `55ac6de`.** `git push origin main` (single
  pipeline — no `storefront/` changes this session). "Deploy to Production" Action green including
  its own "Verify deployment" health check (no transient 502 this time). Independently confirmed
  beyond the green Action, per this project's own "verify the effect, never the exit code" rule:
  SSH'd in, `git log` on the server matches `55ac6de` exactly, all 5 containers healthy/freshly
  recreated; the 6 new `/reports/online/*` routes are genuinely registered inside the running
  backend (checked via `app.routes`, not assumed from the diff); the live frontend bundle contains
  `OnlineReportsPage-3KnZgxlW.js` — **byte-identical chunk hash to the local build**, not just "a
  file exists"; and all 5 new/changed endpoints called for real over the actual public HTTPS domain
  (`eats.sitaratech.info`, with a browser User-Agent — nginx 444s bare curl-style clients here) came
  back `200` with exactly the expected new response shape (`total_count`/`offset`/`limit`/`sort` on
  the queue; `online_revenue`/`online_orders` on sales-summary; the three new online-report bodies).
  `Deploy to Staging` (AWS) failed identically to every prior push — confirmed pre-existing, not a
  regression from this deploy.
- **Next action: Malik UATs both OI-57 and OI-58 live** at `eats.sitaratech.info/online-orders` and
  its new "Reports" button. Nothing else is outstanding from this session's own work.

---

**Session O in one line: all 4 of session N's pending UX/polish items are built, tested and pushed — email wording, bold PAID ticket line, COPY-line removal, and a genuinely different (not just louder) chime technique. Awaiting Malik/Imran's live retest, the chime especially.**

- **Item 1 — "order received" email now says "Prepaid by card" for a card order, not "Payable on delivery".** Root cause, confirmed by reading the actual call order: this email fires inside `POST /orders`, synchronously right after the order is created — **before** the frontend even makes its separate `checkout-session` call, so `stripe_payment_intent_id` is structurally never set yet at send time for ANY order, cash or card. The email's existing 3-branch `_payment_status_text()` could therefore never render its "card held" branch here; it always fell through to the cash wording. Fixed without a DB migration: `PublicOrderCreate` gained a request-only `payment_method: "cash"|"card"` field (the storefront already tracks this client-side, in `Checkout.tsx`'s `payment` state, before submission) that threads through `notify_customer` → `send_order_email` → `_html_received`/`_body_received` as `intends_card_payment`, used only to pick the email's wording — never persisted, never used for any payment-correctness decision. Real Stripe state (`payment_status == "paid"`, or an authorised-not-captured intent) still takes priority over the stated intent if this function is ever reused elsewhere. 6 new/changed tests.
- **Item 2 — receipt's "PAID ONLINE" line is now `bold=True, big=True`**, matching "NOT PAID"'s existing weight (`print_service.py`, `_render_copy`). New byte-level test asserts the `SIZE_DOUBLE + BOLD_ON` prefix.
- **Item 3 — "COPY n OF 3" removed entirely from the printed ticket** (Imran: all three copies go to separate stations, none is "the extra one"). The daily `#NNN` double-size line directly above it is untouched. Cleaned up the now-dead `copy_number`/`copies` params on `_render_copy`.
- **Item 4 — chime rebuilt with a different technique, not just more gain** (`OnlineOrdersPage.tsx`, `playAlertTones`): square wave (was sine), two unison oscillators per tone (one an octave up), a short attack + near-peak hold instead of a smooth exponential ramp, a shared `DynamicsCompressorNode` so the extra layered energy comes out louder instead of clipping, and a 3rd repeat pass (was 2). **Cannot be verified for real perceived loudness from this environment — needs Malik/Imran on the real tablet, this is the next ask.**
- Backend: 450 passed, `tsc`+`vite build`+eslint clean for both `frontend/` (tablet) and `storefront/` (storefront has no eslint config, confirmed pre-existing). **Two test failures surfaced that are NOT from this session's diff** — `test_p1a_features.py::TestVoidHardening::test_void_with_reason_succeeds` and `test_pay_first.py::TestPayFirstTransitionBlock::test_transition_blocked_without_payment` — confirmed by `git stash` on exactly this session's touched files, re-running both against unmodified HEAD, and getting the identical failures; stash was popped back immediately. Not fixed (out of scope), logged in `ERROR_LOG.md` 2026-08-01 session O for whoever picks these up. The documented 12 pre-existing QB-Desktop/parked failures are unaffected either way.
- **Both deploy pipelines shipped and independently verified live, 2026-08-01, commit `f450da9`.** `git push origin main` deployed the backend + `frontend/` tablet app — "Deploy to Production" Action green including its own health check (no transient 502 this time), and independently confirmed inside the freshly-recreated `pos-system-backend-1`/`pos-system-frontend-1` containers: `email_service.py` has "Prepaid by card", `print_service.py` has no "COPY" and `PAID ONLINE` is `bold=True, big=True`, and the live `OnlineOrdersPage-CkRgTwiX.js` chunk contains `createDynamicsCompressor`/`square` — same content hash as the local build. Separately, `cd storefront && npm run deploy` shipped `Checkout.tsx`/`api.ts` to Cloudflare — live bundle hash (`index-BIU7HVPh.js`) and byte count (193,808) match the local build exactly, and the live bundle contains the new `payment_method` field. `chickshackg84.com` returns 200 throughout.
- **Same session, Imran confirmed the chime is loud (his exact words: "Yes it was loud. And annoying. Good") — item 4 CONFIRMED working on the real tablet.** Also confirmed already-correct (no code change needed): the new-order chime already fires regardless of which in-app tab (Pending/Active/All) is on screen, on its own independent poll — verified by re-reading `OnlineOrdersPage.tsx`'s `checkForNewOrders` effect and comparing directly against `C:\FBAI\bilal-app\src\worker.js`'s `pollInbound`/`playChime`/`showOSNotification`, same technique. Separately, a real printer incident: printer switched off mid-order, reprint came out truncated — assessed as a printer/RawBT stuck-buffer issue (full power-cycle + fresh order suggested), not caused by tonight's `print_service.py` changes, since that diff only removed text and didn't touch how the payload streams. **Not yet independently confirmed clean on a retest.**
- **New lead, same evening: Imran is referring a second UK restaurant** (wants to avoid Stripe, prefers Bank of Scotland/Lloyds or Clydesdale Bank — name not yet known). Payment-gateway research (Cardnet/Worldpay/Opayo/PayPal/Stripe fees compared) written up in `_context/notes/2026-08-01_uk-payment-gateways-non-stripe.md`; open question is what specifically went wrong with Stripe for this client, not yet answered. Also fixed two Chick-Shack docs that were sitting outside `_context/clients/chick-shack-uk/` and logged the multi-tenant client-folder convention as a standing rule (`memory/multi-tenant-client-folders.md`).

## ✅ OI-57 / OI-58 built AND deployed session P (2026-08-01) — resume here for Malik's UAT only

**Both fully built, curl-verified, and deployed live — see the top of this file and
`_state/open-items.md` for complete detail.** Malik's own words, the bar for calling this closed:
*"no half cooked jobs... once everything is 2000% done only then confirm, i will then do UAT."*
That bar is met and Malik explicitly said "commit and push" before either commit or deploy
happened. **The only thing outstanding is Malik's own UAT — do not re-build either item.**

- **OI-57 — online-orders queue date filter/pagination/sort — ✅ BUILT + DEPLOYED**, commit `55ac6de`.
- **OI-58 — Chick Shack lean branded reports — ✅ BUILT + DEPLOYED**, commit `55ac6de`.
- If picking this up fresh: don't rebuild, don't redeploy. Point Malik at
  `eats.sitaratech.info/online-orders` (date/pagination/sort controls) and its new "Reports" button
  (`/online-orders/reports`) for UAT.

<details><summary>Original ask, kept for reference (both now built per this spec)</summary>

- **OI-57 — online-orders queue: date filter (today-only default, not all-time), pagination
  (`offset`+`total_count`, not just a bare `limit`), and a sort toggle** for Active/All (Pending's
  existing FIFO oldest-first default is deliberate — keep it unless Malik says otherwise on UAT).
  Reproduced the underlying bug already, in the local DB: 7 total online orders exist, all from
  2026-07-28, 5 still sitting unaccepted — Pending shows 3-day-old orders today with nothing to
  scope it to "today." Exact files/line numbers already identified in the OI-57 writeup.
- **OI-58 — Chick Shack reporting: a lean, branded reports view.** Access is NOT the gap (Imran and
  Malik are both already `admin` role and could reach `/admin/reports` today) — the gap is that
  online orders are silently dropped from every existing report/dashboard breakdown despite being
  counted in top-line totals, and the existing reports UI is the wrong shape for a single-channel
  tenant. Fix the online-orders-invisible bug platform-wide first (benefits every future
  online-ordering tenant, not just this one), then build a new lean route with Daily Sales
  (custom range), Prepaid vs Cash-on-Delivery (new), Rejected Orders (new), and a Stripe
  reconciliation report last (Malik flagged it "maybe" — lower priority, build after the other
  three are solid).

</details>

- **Capture-on-accept (OI-41), root cause found.** `create_checkout_session` read `session["payment_intent"]` immediately after `Session.create()` and stored it on the order -- but confirmed against the real sandbox (a throwaway probe session), Stripe does **not** create the PaymentIntent at that point, only once the customer actually submits payment. `orders.stripe_payment_intent_id` was written `None` and stayed that way forever: the webhook's own backstop (`payment_intent.amount_capturable_updated`) never persisted it either, and was itself blocked by an unrelated, prematurely-set `payment_authorized_at`. `accept_order`'s guard on `stripe_payment_intent_id` then silently no-opped on Accept -- no exception, nothing logged, straight through to `in_kitchen` with `payment_status` still `unpaid`. Confirmed against the real order (`260731-001`): DB had `stripe_checkout_session_id` + `payment_authorized_at` set but `stripe_payment_intent_id` still `None`; Stripe's own PaymentIntent (`pi_3TzL3jFnGj7KcDjJ0NYqItbA`) was sitting fully authorised, `requires_capture`, `amount_capturable: 1299` -- the money was never lost, just never captured.
  **Fix (commit `593513b`):** `accept_order` now guards on `stripe_checkout_session_id` (reliably set at session-creation) and resolves the missing intent id from Stripe directly via new `stripe_service.resolve_payment_intent_id`. The webhook independently backfills the id from its own event object. The premature `payment_authorized_at` write at session-creation was removed. **7 new tests, 2 mutation-checked by hand** (temporarily reverted each guard to its old shape, confirmed the new test fails, restored the fix). Full suite: 442 passed, same 12 pre-existing QB-Desktop/parked failures. Deployed and **verified live inside the container** (both the new function and the corrected guard read back from the running backend, not just a green Action).
  **⚠️ H-6 was already actually done**, confirmed directly against the Stripe API this session (webhook registered at `eats.sitaratech.info/api/v1/public/stripe/webhook`, enabled, all 4 events subscribed) -- the line below and the old "H-6 outstanding" language elsewhere in this file were stale.
  **Closed out:** order `260731-001` voided (`pg_dump` backup taken and verified first, 42 tables) and its Stripe authorisation explicitly cancelled -- confirmed directly against the Stripe API afterwards: `status: canceled`, `amount_received: 0`. No money was ever taken. **Imran has not yet re-run the test with a fresh order.**
- **Tablet "new order" sound, root cause found (two bugs), fixed, commit `87923b4`.** (1) The chime only fired `if (which === "pending")` -- a tablet left on the "Active"/"All" tab never rang for anything new, silently. (2) The real cause of total silence: `chime()` built a brand-new `AudioContext` on every poll tick, never from a user gesture. Chrome -- Android especially, which is what this tablet runs -- creates every `AudioContext` `suspended` until resumed inside a genuine tap, with **no exception thrown**, just no sound. The exact same "Chrome on Android needs a real gesture" rule already bit the `rawbt:` print button once before (`ERROR_LOG.md`, 2026-07-29).
  **Fix:** one persistent `AudioContext`, resumed from a new explicit "Enable sound" button (mirrors the KDS's existing audio on/off pattern) that plays an immediate confirmation beep on tap. The new-order watch now polls independently of whichever tab is on screen. `tsc` + `vite build` + eslint all clean; no browser-in-the-loop test possible (Chrome extension still won't connect, consistent with every session this week). **Malik has not yet tapped "Enable sound" or retested live.**
- **Malik/Imran ran the real end-to-end test (order `260731-003`, 2026-08-01). OI-41 itself is PROVEN: verified directly against Stripe (`status: succeeded`, `amount_received` exactly matches the order total, capture landed ~1s before `accepted_at`) and the DB (`payment_status: paid`, intent id correctly resolved this time).** Three separate, real bugs surfaced in that same test, all found, fixed and deployed (commit `b90057c`):
  1. **Printed kitchen ticket said "NOT PAID" despite the order being genuinely captured.** The ticket is a self-contained ESC/POS payload, cached the instant an order enters the pending queue purely so the Print button can navigate synchronously (Chrome drops the `rawbt:` handoff otherwise) -- nothing ever invalidated that cache once payment status actually changed. Fixed: `invalidateTicket` drops the stale entry and re-fetches in the background (never awaited, so it can't reintroduce the dropped-gesture bug) after Accept, Mark paid, and a cash-settled handover.
  2. **Chime was too quiet for a crowded, noisy restaurant floor.** Reused the already noise-tested 3-tone chime + OS Notification pattern from `C:\FBAI\bilal-app\src\worker.js`, pushed louder again per Malik's explicit ask (gain capped just under 1.0 to avoid clipping; the sequence repeats once). The OS notification is a second, independent channel armed in the same "Enable sound" tap.
  3. **Accepted-order email's "Payment: Paid" was plain muted grey**, easy to miss beside "Due on delivery". Now bold in HTML; plain-text reads "PAID".
  `tsc` + `vite build` + eslint clean; backend 443 passed (+1 new test), same 12 pre-existing failures. **Not yet re-verified live by Malik/Imran** -- a second full retest is the next step, not a formality: confirm the ticket now prints PAID, the chime is actually loud enough, and the email reads clearly.
- Also surfaced and explained during this test, not bugs: (a) the storefront's "Notes for the kitchen" box persists per-browser and only clears on a **successfully placed** order, so leftover text from an abandoned earlier test can resurface -- pre-existing, was already flagged unfixed in `-F`, not yet scheduled; (b) the Pay button silently stayed disabled because the test delivery address ("Test", 4 chars) failed a `> 4` length check with zero visible error -- working as designed, but the lack of any inline validation message is a real UX gap worth fixing, not yet done.

**Session M — independent re-verification of the whole photo round, against Malik's own source doc (`Imran Links.docx`), not against our own checkpoints.** Malik queried the count ("31 links"); the docx (30 link-lines: 29 distinct external source photos + 1 self-referencing reuse-instruction link) was cross-checked one-for-one against every row already recorded — full match, nothing skipped, nothing extra. Re-verified live from scratch (not trusting the prior session's claims): live API (87 items, 0 duplicate names, all 10 drink names correct), all 38 image basenames × thumb+hero (76 files) fetched fresh from `chickshackg84.com` and confirmed valid, checkout disclaimer + testing banner confirmed present in the live JS bundle. **Found and fixed one real bug in the PDF-regeneration script itself** (not a live-site bug): compositing a transparent webp onto RGB directly left black/checkerboard artifacts in the "now on site" column; fixed by flattening onto white via the alpha channel first. Regenerated `Chick_Shack_Photo_Review.pdf` (Desktop, not git-tracked) with fresh live thumbnails for all 27 used photos. Still open: Hash Brown's photo mapping remains Claude's own guess, never confirmed by Imran — flagged again in this PDF.

**Session M continued — 4 more of Imran's links wired in and deployed: Gravy (8oz), Coleslaw (8oz), Spicy Rice, Beans (8oz).** All 4 previously had no photo at all (inherited category fallback). Gravy from `rendalls-cdn.co.uk`, Coleslaw and Rice from the already-vetted `chunkychicken.com`, all clean. **Beans caught a real issue**: the source Malik got approval to use was a live `shutterstock.com` preview URL with a visible "shutterstock.com · 83031757" watermark baked into the bottom of the image — Claude initially and wrongly told Malik it had no visible watermark; caught it while reviewing the actual crop, corrected course, re-asked, and on his direction cropped the watermark strip out before deploying (same bowl photo, no credit line live). `tsc` + `vite build` clean for both rounds, deployed via `cd storefront && npm run deploy`, verified live (byte-exact match on all new image URLs, new JS bundle hash confirmed in `index.html`). Commits `2b7f7b0` (gravy/coleslaw/rice) and `bc7076c` (beans), both pushed. `Chick_Shack_Photo_Review.pdf` regenerated with a new "New this round" page; total tracked photo links now 33.

**Session M continued — Salad Box (real photo) + Fruit Shoot (deliberate brand-mismatch override) deployed.** Salad Box: Imran's own kitchen photo of the actual product (WhatsApp), no provenance concern at all — best source of the whole round. **Fruit Shoot: Malik explicitly instructed deploying the "Simply Fruity" bottle photos as the live Fruit Shoot Orange/Blackcurrant photo**, after being shown clearly (in higher resolution than before) that the branding reads "Simply Fruity", not "Fruit Shoot" — same mismatch already rejected twice this session (once via a blurry gstatic thumbnail, once via this same clearer photo when Claude first asked). Both crops legibly show "SIMPLY fruity" branding on the live site — a fully informed decision, not a quality miss. `MenuItem.image` is item-level not per-variant, so one combined photo (both bottles) represents the whole Fruit Shoot line (2 flavour variants). PDF's "NOT USED" section rewritten to note this instead of listing Fruit Shoot as rejected. Commit `7ddb77c`, pushed, verified live (byte-exact). **If Imran or a customer ever asks why the drink shows a different brand name, the answer is on record here** — flag it back to Malik if it comes up, don't silently re-decide it.

**Session L, later rounds (commits `55373da` through `57f6915`):** Continued live photo
sourcing + Imran's UAT feedback. Wired in 22 more real photos total (Boneless Breast, Peri
Burger, Chicken Fillet Burger, Fish/Veggie Burger and Veggie Wrap — previously had NO photo at
all, Chicken Fillet/Peri Wrap, Sides category fallback, Onion Rings, Peri+Plain Wedges, Corn
Cob, Mozzarella Sticks, Hash Brown, and the full drinks set: Irn Bru, Diet Irn Bru, Rubicon
Passionfruit, Levi Roots, Water, Pepsi, Pepsi Max, Fanta Orange, 7up, plus Chilli Cheese Bites).
Two photos deliberately NOT used — "Simply Fruity" bottles sent for Fruit Shoot are a different
brand entirely, same class of mismatch as the Coca-Cola photo rejected in OI-56. Also built:
drink serving-size labels (all soft drinks now "(Can)", Water "(500ml)", Fruit Shoot "(330ml)")
— required a production DB rename (`rename_chick_shack_drinks_2026_07_31.py`, same idempotent
in-place-UPDATE pattern as the earlier item/dip renames this session, `pg_dump` backed up first,
verified live via API: zero duplicates, zero stale old names, 87 items unchanged) — and a
delivery service-fee disclaimer on Checkout's Payment section, matching the printed menu board's
exact wording. Generated `Chick_Shack_Photo_Review.pdf` (local `fpdf2` + Pillow, no external
service) as a client-facing deliverable for Malik to send Imran — one row per photo with source
link, source thumbnail, live-site thumbnail, and status; regenerated after each round. Saved to
`C:\Users\Malik\Desktop\Chick_Shack_Photo_Review.pdf`, NOT git-tracked. Every one of Imran's 29
photo/feedback links sent this session has now been reviewed and either deployed or explicitly
flagged as not used — nothing outstanding. Full ledger in `PAUSE_CHECKPOINT_2026-07-31-D.md`
and `-E`.

**Session L in one line:** Built the per-item kitchen-notes feature Malik asked for right after
approving UAT item (iv) — design confirmed with him first via `AskUserQuestion` (two rounds;
his second answer corrected a too-abstract first framing), then built: a free-text "Anything
else?" field in `ItemModal.tsx` next to the "leave it out" ticks, travelling the same path as
exclusions (`CartLine.note` is part of the line's identity like `exclusions`, joins the line's
`notes` string, prints bold `** ` on the kitchen ticket — zero `print_service.py` changes
needed). Connection to Checkout: `orderNotes` was lifted out of `Checkout.tsx` local state into
the cart store itself, so `add()` can write `"ItemName: note"` straight into the same box the
customer sees at checkout, and it survives navigating back to the menu (Checkout is conditionally
unmounted, not just hidden). Basket persist version bumped 3→4 (same discard-at-boundary
treatment as the exclusions bump). Caught and fixed one real bug before shipping: the new
textarea's `text-sm` class silently overrode `index.css`'s global `textarea { font-size: 16px }`
rule, which exists specifically to stop iOS Safari zooming the page on focus — switched to the
same `.field` class every other input in the app uses. No backend/DB changes at all, so no
`pg_dump` needed — pure frontend, `tsc`+`vite build` clean. Deployed via
`cd storefront && npm run deploy`; first bundle fetch hit the same "mid-propagation SPA
fallback" Cloudflare issue `ERROR_LOG.md` already documented from session J (200 OK, ~1KB of
`index.html` instead of the real ~192KB bundle) — waited 8s, re-fetched, got the real
192,520-byte bundle matching the build output exactly, with the new strings and the testing-mode
banner both confirmed present. Commit `d0d3199`, pushed. Chrome extension tried again this
session (4th session running) — still would not connect; verified structurally + via the live
bundle instead, per the now-established pattern.

**Session K in one line:** Malik's first live UAT pass on OI-45(b) surfaced 3 real issues,
all fixed and deployed: (1) a solo item gave no hint a Meal version existed — Meal items were
appended in one block after every solo item in a category instead of interleaved, and the
item modal had no cross-link; both fixed, plus a `reorder_chick_shack_meal_modifiers_2026_07_31.py`
one-off was needed to fix the *live* modifier-group order too, since `seed_chick_shack.py`'s
`_link()` is additive-only and a plain reseed doesn't reposition an existing link (same failure
shape as the two rename bugs from the session before). (2) Meal items showed optional dip/sauce
choices before the required drink + chips upgrade — reordered. (3) Checkout landed scrolled to
the bottom of the page — `view` swaps screens in place rather than routing, so scroll position
carried over; added scroll-to-top on every view change. Backend: `pg_dump` backed up, reseed +
reorder script run on production, verified via the live API (item order + group order both
correct). Storefront: deployed to Cloudflare, live bundle verified for the new code, testing-mode
banner reconfirmed present. Commit `8017321`, pushed.

**Same session, follow-up:** the modifier-group fix above was too narrow — Malik caught the
identical bug on **solo** items too (Peri Peri Burger showing Dips before the required
Peri-Peri Heat), live. Root cause fixed properly this time in `seed_chick_shack.py` itself:
`_seed_items` now deletes and recreates every item's `menu_item_modifier_groups` links on
every reseed, in the order that item's `modifierGroups` specifies, instead of the old
additive-only `_link()` that never repositioned an existing link. Closes the whole class of
bug for good — any future reorder in menu.ts now takes effect on the next plain reseed, no
one-off script needed. `pg_dump` backed up, reseeded on production, and **swept all 87 live
menu items programmatically**: zero items show an optional group before a required one.
Commit `97ec8c8`, pushed.

**Same session, UAT item (iv):** the "leave it out" ticks (No Onion, No Lettuce, etc.) turned
out to have **never rendered on the live site at all**, for any item. `exclusionsFor()` matched
`item.categoryId` against a hardcoded slug Set ("burgers", "wraps", ...) — correct for the local
fallback menu, but `categoryId` is a database UUID once the live API menu loads, so the check
silently never matched. Same slug-vs-UUID class of bug already solved for images, never applied
here. Fixed by matching on the category's NAME instead (resolved by `MenuBrowser` from its own
always-correct `categories` list, passed to `ItemModal` as a plain prop) — no schema change.
Pure frontend fix, no DB involved. `tsc` clean, deployed to Cloudflare, live bundle verified
for the new code. Commit `a178d78`, pushed. **Malik confirmed fixed, approved.**

## 🔴 Resume here (session L, UAT of Imran's 07-31 six-item list in progress)

**Per-item kitchen notes — BUILT and deployed, live, 2026-07-31 session L.** Design confirmed
with Malik first (see session L summary above). Not yet Malik-verified live (he hasn't clicked
through it yet) — this is a new, unreviewed feature, not one of the original six UAT items, so
flag it to him explicitly rather than folding it silently into the (v)/(vi) walkthrough.



Going one item at a time via `AskUserQuestion`-style manual checks, Malik approving or
reporting back after each. Progress against
`_context/clients/chick-shack-uk/voice-notes/2026-07-31_imran_meal-modifiers-and-photos.md`'s
six items:
- (i) Meal modifiers — ✅ approved, after 3 rounds of real fixes (see above)
- (ii) New-order sound alert — **root cause found and fixed, session N (2026-08-01),
  commit `87923b4`** (tab-scoped chime + unresumed AudioContext, see session N summary
  above). Deployed. Not yet tested live — Malik will tap "Enable sound" and test on the
  real tablet himself.
- (iii) Allergy notice + kitchen notes box — ✅ approved
- (iv) Remove-selections ("leave it out" ticks) — ✅ approved, after fixing a real bug (see above)
- (v) Burger name suffixes — ✅ approved. Pre-checked server-side by sweeping the live production
  API (`GET /public/chick-shack/menu`, all 87 items) before asking Malik to look: all 10 burger
  items end "…Burger", all 6 wrap items end "…Wrap", Meal siblings correctly read "…Burger Meal" /
  "…Wrap Meal", zero duplicate names anywhere — ruling out the stale-duplicate-row failure mode
  `ERROR_LOG.md` documented for this exact rename. Malik then confirmed visually on the live site.
- (vi) Chunky-chicken photos — **in progress** (built and deployed in session I/J, being walked
  through now as part of THIS structured UAT pass)

**Per-item notes ask from Malik right after approving (iv) — ✅ BUILT, deployed, live-tested by
Malik, session L.** Design confirmed via two rounds of `AskUserQuestion` before any code was
written: ticket style = same bold treatment as exclusions; connection = the item note is written
straight into the same Checkout "Notes for the kitchen" box, editable from there. Malik tried it
live and found one real UX issue: the auto-inserted text was prefixed `"ItemName: comment"`,
which reads as clutter with several items each carrying a note. Fixed to insert the plain comment
text only (no item-name prefix) — the per-line note still reaches the kitchen ticket correctly
attached to its own item regardless of what the checkout box says. Redeployed, verified live.
Same session, two more of his live-testing findings, both shipped: the allergen notice was
checkout-only and is now also on the homepage; the Meal-item photos still show the solo item's
photo with no chips/drink in frame — **flagged as needing real photography, not fixed**, since
the only prior candidate photos showing a full meal composition (`menuitem-6.jpg`,
`menuitem-8.jpg` from the session J chunky-chicken source set) were deliberately rejected at the
time for showing a rival Coca-Cola can and a fake competitor-branded box — there is no safe
existing asset to pull from. Malik said to let it wait.

**Same session, direct feedback from Imran (via Malik, WhatsApp screenshots) — three more real
fixes, all shipped and verified:**
1. **Exclusions scoping** — the "leave it out" ticks were showing on Peri Peri Grilled Chicken
   and Fried Chicken too. Imran confirmed directly: only Burgers and Wraps should have it. The
   code already carried a `⚠️` comment flagging this exact scope as an unconfirmed guess from an
   earlier session ("confirm it with him") — now settled by his own words.
   `EXCLUDABLE_CATEGORY_NAMES` cut to `{"Burgers", "Wraps"}`. Pure frontend, deployed, verified
   live (bundle byte count matched build exactly).
2. **Variant visibility** — piece-count options (2pc/3pc/4pc etc.) on fried chicken, wings,
   tenders and peri items were invisible in the menu list; only a "from £X" hinted more than one
   option existed. Added a subtitle to `MenuBrowser.tsx` list cards listing every variant name
   for multi-variant items. Pure frontend, deployed, verified live.
3. **Dip modifier naming** — Imran: kitchen staff need "dip tub" in the wording so a ticket line
   like "- Ketchup" reads as a separate 2oz tub, not an instruction to put it ON the burger/wrap.
   Root cause: `print_service.py` prints a bare `modifier.name` with zero group context, so the
   dip group's own "(2oz tub)" label never reached the kitchen ticket. This one touched the
   database, so handled carefully: `seed_chick_shack.py` matches `Modifier` rows by
   `(tenant, group_id, name)`, so a blind rename in `menu.ts` would have created 9 duplicate
   rows rather than renaming them (the exact additive-only-seeder class already documented for
   item renames). Wrote `rename_chick_shack_dip_modifiers_2026_07_31.py`, same in-place-UPDATE
   pattern as the earlier item-rename script. Sequence: `pg_dump` backup taken and verified
   (88.5KB, 42 tables) → renamed the 9 existing rows in place on production → reseeded → verified
   live via the public API: all 9 dip options now read "…(Dip Tub)", same group id (genuinely
   the same row, not a new group), zero duplicates anywhere across all 87 items, and the 3
   standalone Dips-category products (sold on their own, no ambiguity there) correctly left
   untouched. Also closed in this round: **Imran confirmed printing on his own hardware** — "I
   did print an order yesterday which we received and 3 copies printed" — closing the last open
   piece of OI-51/52.

**Same session, severe regression found and fixed while building item #2 above: every
multi-variant item had silently lost its size/quantity selector, live.** While verifying why the
new variant-visibility subtitle had nothing to show for "Fried Chicken", the live API confirmed
the item had NO Choice modifier group at all, despite `menu.ts` and `chick_shack_menu.json` both
having one. Root cause: `97ec8c8` (earlier today, session K) made `_seed_items` delete and
recreate every item's `menu_item_modifier_groups` links from `entry["modifierGroups"]` to fix
group ORDER — but a multi-variant item's "<name> -- Choice" group is linked separately, and that
delete step ran unconditionally, wiping the Choice-group link out again before session K's own
reseed finished, with nothing in the recreate list to restore it. **Every multi-variant item on
the live site — Half/Full Chicken on the Bone, Boneless Breast 2pc/4pc, Peri Wings, Peri Tenders,
Fried Chicken, Fried Chicken Combo, Spicy Fried Wings, Fried Tenders, and all their Meal
versions — showed only its cheapest price with zero way to select size, piece-count, or
rice/chips/half-half**, silently, no error anywhere (`menuAdapter.ts`'s own documented
flat-price fallback absorbed it cleanly). Fixed by building one `group_ids` list (variant group +
`entry["modifierGroups"]`) and doing a single delete+recreate pass; removed the now-dead
`_link()` helper. `pg_dump` backed up (88.6KB, 42 tables), deployed, reseeded, verified live via
the API: all 16 affected items now correctly expose their full option list, zero duplicates.
Independent confirmation: Imran sent a voice note (transcribed locally with `faster-whisper`,
since it isn't directly playable) describing this exact same missing-selector problem, item by
item, unprompted — everything he listed matched what the fix restored, so no separate feature
work was needed for that note. Malik explicitly declined a check of whether any real customer
order was placed during the broken window ("forget the existing orders, just fix and deploy").

**Same session, 3 stock photos replaced with real photography, Imran-supplied reference links.**
Two from `chunkychicken.com` (confirmed same UK "Chunky Chicken" franchise brand as the OI-56
source, `chunky-chicken.uk` — not a different, unvetted business): grilled chicken quarters now
the **Peri Peri Grilled Chicken category fallback** (`peri-grilled.webp`, was still original
stock), and grilled wings now the **Peri Peri Wings** item photo (`peri-wings.webp`, also still
original stock). A third link was a Google Images thumbnail-cache URL (`gstatic.com`) with no
identifiable original source — flagged to Malik as the same class of unclear-provenance risk
already rejected once in OI-56 (the Coca-Cola can, the fake-branded box); **Malik explicitly
overrode that caution** ("just add the picture its fine") and it was used as a new **Peri
Tenders** per-item photo (previously had none, inherited the category image) — grilled tender
strips with chips, added as a new `ImageName` entry. All three sources had genuine alpha
transparency (verified with PIL before cropping), so none needed the white-patch fix the nuggets
photo required. Cropped to thumb (240×180) and hero (720×480) separately per the established
convention, deployed, and verified live — all 6 image URLs return the correct byte-exact files
(one `peri-tenders` URL hit the known Cloudflare mid-propagation SPA-fallback issue on first
check, resolved after a longer wait and confirmed on retry).

**Next action:** UAT item (vi), chunky-chicken photos — in progress now.

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
| Stripe | ✅ **LIVE MODE, proven with a real transaction, 2026-08-02 — as of now (source: Malik + Imran verbal/WhatsApp, cross-checked against our own DB same session).** Order `260801-004`, £2.78, Imran's real card, captured for real — confirmed against Stripe's live dashboard, our `payments` table, and the audit trail. Live keys set directly on the server by Malik (never passed through the assistant). **Imran approved going fully live in writing.** `cardPaymentEnabled` is **still false as of this row** — flipping it, removing the testing banner, and shipping a new delivery cut-off feature are in progress this same session, not yet deployed; see the session Q "Resume here" section above for exact status. **Test override still exists:** `chickshackg84.com/?card=1`. H-1 through H-10 previously all confirmed done | `docs/STRIPE_HARDENING_CHECKLIST.md` · OI-20 / OI-41 |
| Printing | ✅ **ON PAPER (photographed 2026-07-29)**, session F built Imran's two asks: **3 labelled copies per ticket in ONE payload** (one `rawbt:` navigation) and the **daily `#NNN` double-size at the top of each copy**. **Paper check on his own printer now CONFIRMED 2026-07-31 (session L)** — Imran, to Malik: "I did print an order yesterday which we received and 3 copies printed." Closes the last open item under OI-51/52 | OI-51 / OI-52 ✅ built + ✅ confirmed on real hardware · `ERROR_LOG.md` |
| Served / delivered gap | ✅ **CLOSED and deployed.** Tablet has out-for-delivery / delivered / mark-paid; completed orders leave the Active tab; the customer's page follows it | `_state/open-items.md` OI-44 |
| Customer emails | ✅ **RESOLVED 2026-07-30 — Brevo live, real order proved it, then branded.** Order `260729-003`: confirmation delivered in 2 seconds, Gmail "Show original" — SPF PASS, DKIM PASS (`d=chickshackg84.com`), DMARC PASS. Domain authentication needed a fix along the way (Brevo requires its own DMARC record to flip `authenticated`; resolved by editing Imran's single `_dmarc` record in place, same `p=none` policy, not duplicating it). **Same session: all 4 emails (received/accepted/rejected/on_the_way) given branded HTML** — ink/flame/ember from `tailwind.config.js`, no logo (none exists), inline-style table layout for client compat, every customer-supplied string `html.escape()`'d (checkout form is public input). Shipped `3ab141b`, deployed, verified live via order `260730-001` — real Gmail screenshot confirms it renders as designed. Test suite: 45/45 email tests, 432/444 full suite (12 pre-existing, unrelated). Runbook: `_context/clients/chick-shack-uk/EMAIL_SETUP_RUNBOOK.md` | `_state/open-items.md` **OI-55** |
| Menu modifier prompts | ✅ **BUILT and deployed to production, 2026-07-31.** Peri-Peri Heat renamed to match his till; "make it a meal" is now 25 real Meal sibling products (drink + chips upgrade), not a flat +£3 tick. Exclusion ticks (no lettuce etc.) turned out to already be built. Verified against the live API: 87 items, no duplicates | `_state/open-items.md` OI-45 |
| Storefront photos | ✅ **12 real photos live now** (9 from OI-56 + 3 more session L, same-day): Peri Grilled category fallback, Peri Wings, and a new Peri Tenders photo. 6 of the original 15 rejected on re-verification (2 trademark, 4 product mismatch). Only **fried-chicken, fried-tenders, sides-chips** still on original stock. Meal-item "with chips & drink" composite photos still needed — flagged, deferred, no safe asset exists | `_state/open-items.md` OI-56 |
| Backend test suite | ✅ **409 passing — run and verified 2026-07-29 session E**, not inherited. Session E started from a verified **393** (session D's "391" was two short) and added **16** for the Stripe hardening. Same **12 pre-existing failures** throughout (10 failed + 2 errors), all in QuickBooks-Desktop/parked code | `ERROR_LOG.md` |
| Core POS (10 phases) | ✅ Production, 98/99 UAT | `_state/pos-platform.md` |
| QuickBooks Online | ✅ Live. Sync is **manual by design**, not broken | `_state/pos-platform.md` |
| POS demo sites | ✅ Green (`pos-demo.duckdns.org`, `eats.sitaratech.info`) | `_state/infrastructure.md` |
| CI (`ci.yml`) | ❌ **Red on every commit.** Ruff + ESLint fail; Ruff exits before the test step, so **CI has never run the suite**. All findings are in parked code, none are live bugs. Deploys are a separate workflow and are green | `_state/open-items.md` OI-47 |
| Nightly demo-data cron | ❌ **Has never run** | `_state/open-items.md` OI-11 |
| Production log persistence | 🟡 **Backend fix designed and written, PAUSED uncommitted, session Q (2026-08-02).** `backend`/`nginx` are recreated on every deploy and are `read_only:true` with no persistent volume, so `docker logs` history is lost every push — sometimes within hours. All 6 backend files edited/written, config validated directly, but not build-tested, not committed, not deployed — resume from OI-60a's checklist, don't redesign. nginx not started | `_state/open-items.md` **OI-60** |

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
