# Pause Checkpoint — 2026-08-01 (session N)

## Project
- **Name**: POS System / Chick Shack UK (chickshackg84.com)
- **Path**: C:\Users\Malik\desktop\pos-project
- **Branch**: main
- **HEAD**: `9952df6` — everything from this session is committed and pushed, and the
  "Deploy to Production" Action for this exact commit **succeeded** (3m16s). `git status`
  shows only the same pre-existing ~99-103 dirty markdown paths documented throughout
  `STATE.md` — never `git add .`, leave them alone.

## Goal
Chick Shack UK online ordering. This session resumed mid-incident from
`PAUSE_CHECKPOINT_2026-07-31-F.md`: a live sandbox card test had shown a real
capture-on-accept failure (OI-41). This session root-caused and fixed that bug, then ran
a full live end-to-end retest with Imran on the phone. **The payment mechanism itself is
now PROVEN correct** (verified directly against Stripe and the DB, not just a UI
surface). That same retest surfaced several real UX/polish bugs on top of the now-working
payment flow — three were found and fixed this session, and four more (listed below) were
raised in the final round and **deliberately deferred**: Malik explicitly said to use
`/handoff` and build them in a fresh session rather than continuing here.

## Completed
- [x] Root-caused and fixed capture-on-accept (`593513b`). `create_checkout_session`
  read `session["payment_intent"]` immediately after `Session.create()`, but confirmed
  against the real sandbox (a throwaway probe session), Stripe does not create the
  PaymentIntent until the customer actually pays — `stripe_payment_intent_id` was
  written `None` and stayed that way forever. New `stripe_service.resolve_payment_intent_id`
  resolves it from Stripe directly at Accept time; `accept_order` now guards on
  `stripe_checkout_session_id` (reliably set at session-creation) instead of the
  often-still-empty intent id; the webhook independently backfills the id from its own
  event object. 7 new tests, 2 mutation-checked by hand (temporarily reverted each guard,
  confirmed the test fails, restored the fix). Deployed and verified live **inside the
  container**, not just a green Action.
- [x] Root-caused and fixed the tablet's new-order sound never firing (`87923b4`): (1)
  the chime only fired `if (which === "pending")`, so a tablet left on Active/All never
  rang; (2) the real cause of total silence — `chime()` built a brand-new `AudioContext`
  every poll tick, never from a user gesture, and Chrome (Android especially) creates
  every such context `suspended` with **no exception thrown**. Fixed with one persistent,
  explicitly-resumed `AudioContext` behind a new "Enable sound" button, and a
  tab-independent watcher for new pending orders.
- [x] Voided leftover real test order `260731-001` (`pg_dump` backup taken and verified
  first, 42 tables) and separately cancelled its Stripe authorisation — confirmed
  directly against the Stripe API afterwards: `status: canceled`, `amount_received: 0`.
  No money was ever taken.
- [x] **Full live retest, order `260731-003`. OI-41 is PROVEN**, independently verified:
  Stripe (`status: succeeded`, `amount_received` exactly matches the order total, a real
  charge exists) AND the DB (`payment_status: paid`, `stripe_payment_intent_id` correctly
  resolved, `payment_captured_at` landed ~1s before `accepted_at`).
- [x] That same retest surfaced 3 real bugs, all found, fixed, tested and deployed
  (`b90057c`):
  1. Printed kitchen ticket said "NOT PAID" on the genuinely-captured order above. Root
     cause: the ticket is a self-contained, pre-rendered ESC/POS payload, cached the
     moment an order enters the pending queue (purely so the Print button can navigate
     synchronously without Chrome dropping the `rawbt:` handoff) — nothing ever
     invalidated that cache once payment status changed. Fixed with `invalidateTicket`:
     deletes the stale cache entry and re-fetches in the background (never awaited, so
     it can't reintroduce the dropped-gesture bug) after Accept, Mark paid, and a
     cash-settled handover.
  2. Chime too quiet for a busy floor (first pass). Reused the already noise-tested
     3-tone chime + OS Notification pattern from `C:\FBAI\bilal-app\src\worker.js`,
     pushed louder (gain capped just under 1.0 to avoid clipping), both armed by the
     same "Enable sound" tap. **Malik confirmed after this deploy that it is still too
     quiet even with the tablet's media volume already maxed — see Pending item 4.**
  3. Accepted-order email's "Payment: Paid" was plain muted grey. Now bold (`<strong>`)
     in the HTML email; plain-text version reads "PAID".
  `tsc` + `vite build` + eslint all clean. Backend: 443 passed (+1 new test), same 12
  pre-existing QB-Desktop/parked failures throughout this whole session.
- [x] Explained (not bugs, working as designed, but real gaps) two things Malik hit
  during testing: the storefront's "Notes for the kitchen" textarea persists per-browser
  and only clears on a **successfully placed** order (so leftover text from an earlier
  abandoned test can resurface — pre-existing, already flagged unfixed in `-F`, still not
  scheduled); and the Pay button silently stayed disabled because a 4-character test
  address failed a `> 4` length check with **zero visible error message** — a real UX
  gap (no inline validation feedback) worth fixing, not yet done, not blocking today.
- [x] The `b90057c` deploy's own Action showed a red X — investigated rather than
  assumed broken: every real deploy step passed, only the automated post-deploy health
  check hit a transient `502` (this project's known nginx-stale-upstream-IP-after-
  recreation class of issue, self-resolved by the very next deploy 40s later).
  Independently verified live health AND the actual running code in both containers
  afterward, before telling Malik anything was ready. Logged in `ERROR_LOG.md`.
- [x] `STATE.md` kept current throughout (commits `e31703b`, `28b305b`, `6ccf126`,
  `9952df6`) — reflects everything above accurately as of HEAD.

## In Progress
None. Everything above is committed, pushed, and confirmed deployed.

## Pending — Malik's 4 fresh observations from the `260731-003`/`004` retest. NOT yet
built. Malik's own instruction: **use `/handoff`, build these in the new session.**

1. **"Order received" email wrongly says "Payable on delivery" for a card order that was
   actually prepaid** (order `260731-004` screenshot). Malik, verbatim: *"prepaid vs paid
   on delivery have to be clearly segregated. this is a prepaid order, payment will be
   processed when order is accepted by kitchen. this needs to be clearly mentioned."*
   `email_service.py`'s `_payment_status_text()` (added earlier this session, `e3bc6ea`)
   already has three branches — paid / authorised-but-not-captured / cash — read it
   first to see which branch actually fired for this order and why the rendered copy
   read "Payable on delivery" rather than something unambiguous like "Prepaid by card —
   we only charge you once the shop accepts your order." The word "Payable" itself may
   be the whole problem, since it reads identically to a cash-on-delivery order.
2. **Receipt's "PAID ONLINE" line is small text at the bottom** — needs the same visual
   weight as the DELIVERY line. Malik: *"needs to be in a bigger font like the DELIVERY
   font. bold if possible."* Look at `backend/app/services/print_service.py`,
   `build_online_order_ticket` (~line 217-223) — the `NOT PAID` branch already uses
   `t.center("*** NOT PAID ***", bold=True, big=True)`. Find/build the corresponding PAID
   branch and give it the exact same `bold=True, big=True` treatment. "Unpaid is
   shouted, not whispered" was already this project's stated design principle for this
   ticket — paid should shout too, just a calmer message.
3. **Remove the "COPY n OF 3" line from the printed ticket entirely.** Imran, verbatim
   (via Malik): *"Can you remove where it says copy 1 of 3 As all three copies are for
   separate stations And 1 out of the three is used for taking the delivery."* Find where
   `build_online_order_ticket` prints "COPY {n} OF {total}" (built for OI-52, session F)
   and delete that line from the ESC/POS payload. **Do NOT touch the daily `#NNN`
   double-size number line** (OI-52's other half) — only the copy-count line goes.
4. **Chime still too quiet with the tablet's media volume already maxed out**
   (screenshot of Android Sound settings confirms). Malik: *"need to increase at least
   2-3x."* Gain alone won't do it further — `playAlertTones` in
   `frontend/src/pages/online-orders/OnlineOrdersPage.tsx` already peaks at 0.9-0.95,
   near the ceiling before a sine wave clips into distortion. A genuine loudness increase
   needs a different technique, reasoned through this session but **not yet
   implemented**:
   - Switch oscillator type from `"sine"` to `"square"` (or sawtooth) — far more
     harmonic energy at the same peak amplitude, reads as objectively louder and more
     alarm-like. Appropriate for a noisy floor: unmistakable beats pleasant here.
   - Layer 2 oscillators per tone (unison, one an octave up) instead of one — more
     simultaneous acoustic energy hitting the ear at once.
   - Shorten the fade in/out envelope — hold near-peak gain for most of each tone's
     duration instead of a smooth exponential ramp that spends much of it quiet.
   - Add a `DynamicsCompressorNode` between the oscillators and `ctx.destination` so the
     extra energy from layering can't clip into harsh distortion — this is the actual
     mechanism that allows genuinely louder rather than hitting the same ceiling sooner.
   - Consider a 3rd repeat of the sequence (currently repeats once, i.e. two passes
     total) given how noisy this floor genuinely is.
   No way to test real perceived loudness from this environment — verify `tsc` + `vite
   build` + eslint clean, then it MUST be confirmed on the real tablet by Malik/Imran
   before calling it closed. Don't claim "louder" without that confirmation.

## Key Decisions
- **OI-41 (capture-on-accept) is PROVEN, not just deployed** — verified directly against
  Stripe's own API and the DB for a real order, independent of any UI surface. Don't
  re-litigate this; all 4 pending items above are cosmetic/UX, not payment-correctness.
- `payment_authorized_at` is deliberately no longer set at checkout-session-creation time
  (removed in `593513b`) — only set once real authorisation is confirmed, by the webhook
  or by Accept's own resolve step. Do not reintroduce the premature write.
- Ticket URLs are cached client-side specifically to survive Chrome-on-Android's
  user-gesture requirement for the `rawbt:` navigation — any future print/ticket change
  must preserve "no `await` between a tap and `sendToPrinter`".
- Order `260731-001` is closed (voided, Stripe hold cancelled) — don't revisit it.
- Two deploy pipelines, unchanged: `git push origin main` ships POS backend/admin
  (including the `frontend/` tablet app used for online-orders); the Chick Shack
  **storefront** (Cloudflare Workers) is separate and was NOT touched this session.

## Files Modified (all committed and pushed, HEAD `9952df6`)
- `backend/app/services/stripe_service.py` — `resolve_payment_intent_id`, corrected a
  wrong comment, checkout-session route write is now opportunistic-only.
- `backend/app/services/public_order_service.py` — `accept_order` guards on
  `stripe_checkout_session_id`, resolves a missing intent id from Stripe directly.
- `backend/app/api/v1/public.py` — no longer sets `payment_authorized_at` early; webhook
  backfills `stripe_payment_intent_id` from its own event object.
- `backend/tests/test_stripe_payments.py` — 9 new/changed tests across both rounds this
  session, 2 mutation-checked by hand.
- `frontend/src/pages/online-orders/OnlineOrdersPage.tsx` — Enable sound button +
  persistent `AudioContext`, tab-independent new-order watcher, `invalidateTicket`,
  3-tone chime, OS Notification. **Will be touched again for Pending item 4.**
- `backend/app/services/email_service.py` — bold "Paid" in the accepted email (HTML +
  plain text). **Will be touched again for Pending item 1.**
- `backend/tests/test_order_lifecycle_and_email.py` — 1 new test for bold-Paid.
- `STATE.md` — updated 4 times this session, current as of HEAD.
- `ERROR_LOG.md` — 1 new entry (transient 502 during a deploy health check).
- `backend/app/services/print_service.py` — **NOT yet touched, needs Pending items 2+3.**

## Uncommitted Changes
None from this session's actual work. `git status` shows only the pre-existing
~99-103 dirty markdown paths already documented throughout `STATE.md` — never
`git add .` in this repo (`.env.demo` is tracked and carries live credentials).

## Errors & Resolutions
- Capture-on-accept root cause — found and fixed, see Completed and `ERROR_LOG.md`
  (2026-07-31 session M entry + this session's fix).
- Stale ticket cache / quiet chime (round 1) / unbold email — all found and fixed this
  session.
- Transient 502 on a deploy health check — self-resolved, logged, not a code defect.
- **Chime still too quiet even after the first fix** — this is Pending item 4. The first
  fix addressed *why there was no sound at all*; this is a separate, second-order
  "loud enough for a real noisy floor" problem that needs a different technique
  (harmonics/layering/compression), not just a bigger gain number.

## Critical Context
- Server: `ssh root@159.65.158.26`. `pos-system-backend-1` / `pos-system-frontend-1` /
  `pos-system-nginx-1` all freshly recreated ~20:35 UTC 2026-07-31, healthy, verified
  live directly (not just via the Action).
- `docker exec pos-system-backend-1` has a **read-only rootfs** — `docker cp` into it
  fails. Run one-off diagnostic scripts via
  `docker exec -i pos-system-backend-1 python3 - < script.py` (stdin), not by copying
  the file in first.
- Stale build artifacts accumulate in the frontend container's `assets/` folder across
  deploys (multiple old-hash `OnlineOrdersPage-*.js` / `index-*.js` files coexist,
  harmless, nothing references them). If ever verifying "which code is actually live",
  trace forward from `index.html`'s referenced entry bundle — never assume the
  newest-looking filename is the one in use.
- Chrome browser automation still would not connect this session (consistent with every
  session this week) — try `mcp__claude-in-chrome__tabs_context_mcp` once at the start
  of the new session in case it's back, but don't loop on it if not; all frontend
  verification this session was `tsc`/`vite build`/eslint + direct container/bundle
  inspection.
- Stripe is still **sandbox/test mode** (`sk_test_...`) throughout — no real money has
  moved this entire session, including orders `260731-003`/`004`. Live keys stay off
  until all 4 pending items are built AND retested clean by Malik/Imran.
- `docs/STRIPE_HARDENING_CHECKLIST.md` is unaffected by any of the 4 pending items — none
  of them are Stripe/payment-correctness work, all four are print/email/audio polish.
