# Pause Checkpoint, 2026-08-17 (early PK / late 16 Aug UK)

## Project
- **Name**: Restaurant POS, Chick Shack UK online ordering channel
- **Path**: `C:\Users\Malik\desktop\POS-Project`
- **Branch**: `main` · **HEAD `baa63f3`**, pushed and deployed
- **Server**: verified at `baa63f3`, alembic **`v8w9x0y1z2a3 (head)`**
- **Storefront**: Cloudflare `c8d8a9b6`, **not redeployed this session** (no storefront change)

## What this session did
Three separate things, in order: a win-back email campaign built and fired, a live production bug
found by Malik and fixed end to end, and the Google review email measured properly for the first
time.

## Completed

### 1. Win-back email campaign (OI-83) — SENT
- [x] `/refresh` run properly; STATE.md drift corrected (dirty-file count, and the 08-15 docs that
      were never committed).
- [x] **Sized the list against production, read-only**: 103 people, 84 one-time customers.
      Re-runnable SQL saved at `_context/clients/chick-shack-uk/email-cohorts_queries.sql`.
- [x] **Verified the real sending limits** from the live Brevo account and their docs, not memory:
      Free plan **300/day**, API limit 1,000 req/sec (irrelevant at this size), our usage 26-50/day.
- [x] Designed 8 template concepts, published as an artifact, iterated to Malik's brief ("just give
      me designs"), then narrowed to one.
- [x] **Built `backend/app/scripts/winback_email.py`** — `--dry-run` / `--test` / `--send`, paced at
      7.5s, resumable sent-log so it cannot double-email, bad-domain guard.
- [x] Test email sent to Malik and confirmed delivered before anything went to customers.
- [x] **FIRED: 84 sent, 83 delivered, 0 hard bounces, 0 spam complaints, 0 unsubscribes.**

### 2. OI-84 — the card/cash window. FOUND, FIXED, DEPLOYED, VERIFIED
- [x] Diagnosed from Malik's observation of the live screen; every step read out of the code.
- [x] Fixed properly rather than patched: new column written in the order's own INSERT, predicate
      hardened belt-and-braces, **one shared `is_card_order()` helper replacing the same question
      asked inline in four files**, and the `accept_order` money guard re-keyed.
- [x] 6 new tests + 2 end-to-end, **mutation-checked twice**; full suite 565 passed, same 10
      failures + 2 errors as before (all inspected, all pre-existing).
- [x] **Scheduled and deployed unattended at 02:30 PK** via `scripts/deploy_oi84.sh`, with
      `pg_dump` verified restorable first, and verified by effect afterwards.

### 3. Google review email measured (OI-85)
- [x] Proved it lands in **Primary**, button works, ~55% open rate — and still **0 reviews in ~240
      sends**. Baseline recorded (16 reviews / 5.0) so it is measurable from here.

## Pending
- [ ] **Judge the campaign Monday evening (18 Aug).** Tonight's zero is 1.5h of trading, not a result.
      Target: open rate and any second order from the 84.
- [ ] **OI-85**: diagnose why the review email converts at zero. Nothing authorised.
- [ ] **Tell Imran about `gmail.con` / `gmail.cim`** — two customers have never received any email
      from the shop, including order confirmations.
- [ ] **One-click unsubscribe** (currently `mailto:` reply-with-STOP). Well under an hour.
- [ ] **One-tap reorder deep link** — `cart.ts:reconcile()` already does the hard part.
- [ ] Carried over, untouched: OI-82 (discount analysis, nothing sent to Imran), OI-80 (CI red, no
      signal), OI-76 (what3words reply drafted, unsent), HSTS, tip-flow UAT, chips-flow UAT.

## Key Decisions
- **Pushed back on my own advice twice, because Malik was right both times.** (1) I called the
  unsubscribe build "about a day"; it is well under an hour. (2) I proposed a credit floor to stop
  the campaign exhausting the daily send limit; peak transactional is 50 against a 300 cap, so it
  cannot bind. **Do not pad estimates and do not invent guardrails for volumes this business is
  nowhere near.**
- **Contradicted Malik on the review count and was wrong.** He said zero; I cited the profile's 16
  and called it an attribution gap. The review *dates* settled it against me. **A total is not a
  rate.** Saved as a memory.
- **Deployed as a script, not a feature**, for the campaign — no deploy, no droplet recreation
  during service.
- **Deploy scheduled rather than rushed.** OI-84 is a money-path change; it waited for close.

## Files Modified

**Committed and pushed (`baa63f3`, 10 files):** `backend/app/models/order.py`,
`backend/app/services/order_visibility.py`, `public_order_service.py`, `email_service.py`,
`print_service.py`, `backend/app/api/v1/public.py`,
`backend/alembic/versions/v8w9x0y1z2a3_order_intends_card_payment.py`,
`backend/tests/test_card_intent_window.py`, `test_stripe_payments.py`,
`test_public_tenant_routing.py`.

**Uncommitted (docs and tooling from this session):** `STATE.md`, `_state/open-items.md`,
`_context/clients/chick-shack-uk/voice-of-customer.md`,
`_context/clients/chick-shack-uk/email-cohorts_queries.sql`,
`backend/app/scripts/winback_email.py`, `backend/app/scripts/inbox_placement_probe.py`,
`scripts/deploy_oi84.sh`, this file — **plus the ~132 pre-existing dirty files and the OI-82 docs
from 08-15 that were held back and still are.**

> ⚠️ **Do NOT `git add -A` in this repo.** Stage by explicit filename, every time.

## Errors & Resolutions
- **`docker cp` into the backend container fails**: rootfs is read-only. `/tmp` is a writable 64M
  tmpfs. **Resolved**: pipe with `docker exec -i sh -c 'cat > /tmp/x.py'`.
- **The deploy script's first draft hardcoded `TARGET_EPOCH=1755379800`, a 2025 timestamp.** It would
  have skipped the wait and deployed mid-service. **Resolved**: derive from a date string. Caught by
  printing the target back in human-readable form instead of trusting the number.
- 🔴 **`TZ=Europe/London date` silently returns local time on Git Bash for Windows, with no error.**
  The shop-open guard was reading the wrong clock while looking correct. **Resolved**: read the UK
  hour off the droplet, which has real tzdata. **Guard then tested live** — a `--now` run at 20:30 UK
  aborted correctly before any dump or push.
- **My inbox-placement probe reported the review email as unconfigured.** `google_review_url` is on
  `RestaurantConfig`, not `Tenant`, and a `getattr(..., "")` default hid it. **Resolved.** Nearly
  raised a false alarm about a working feature.
- **`cred-guard` blocks shell heredocs containing the word "token".** Use the Edit tool instead.
- **~2 minute 502 after deploy**: nginx held old upstream IPs until CI recreated it. Cleared itself,
  shop closed, zero impact. Known trap, now observed.

## Critical Context
- 🔴 **`chickshackg84.com` is live and taking real orders.** Hours 16:00-22:00 UK. **Deploy only when
  shut.**
- **Two deploy pipelines**: `git push origin main` = backend + tablet (droplet); `cd storefront &&
  npm run deploy` = customer site (Cloudflare). A green push proves nothing about the other.
- **Read `memory/server-deployment-rules.md` and `memory/data-integrity.md` before touching the
  server.** `pg_dump` first, always. nginx returns 444 to curl, pass a browser `-A`.
- **Production read-only DB access**: `ssh root@159.65.158.26`, write a `.sql` file, `docker cp` into
  postgres, `psql -f`. Chick Shack tenant `8b2b6223-7db9-443b-8ace-34dd115a9275`.
- **Marketing copy follows the village-centric brief.** `_context/clients/chick-shack-uk/
  voice-of-customer.md`. Transactional emails excluded, deliberately.
- **CI and Deploy-to-Staging are red on every commit and carry no signal (OI-80).** Judge deploys by
  Deploy-to-Production plus effect.

## Resume prompt
> Refresh context on the POS project (Chick Shack). Read STATE.md first. HEAD is `baa63f3`, deployed
> and verified. Then: check the win-back campaign result (84 emails sent 16 Aug, judge Monday
> evening) and pick up OI-85, why the Google review email has produced zero reviews in ~240 sends.
