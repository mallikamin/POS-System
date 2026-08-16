# Pause Checkpoint, 2026-08-15 (early PK / late 14 Aug UK)

## Project
- **Name**: Restaurant POS, Chick Shack UK online ordering channel
- **Path**: `C:\Users\Malik\desktop\pos-project`
- **Branch**: `main` · **HEAD** `1bcdb7b`, pushed. Server verified at `de10856` in the previous
  session; the three commits after `2366c99` are docs-only.
- **Storefront**: Cloudflare version `c8d8a9b6`
- 🔴 **This session wrote docs only. NOTHING was committed and NOTHING was pushed.** See
  "Uncommitted" below and the deliberate reason.

## Goal
Imran proposed (via Malik, 2026-08-14) **10% off online orders over £50**. Malik asked for a
proper analysis off real website orders: order breakdown, average order value, what discount
margin makes sense, top items, "where is the opportunity". Registered as **OI-82**. Analysis only.
No build was requested and none was authorised.

## Completed
- [x] `/refresh` run properly. STATE.md read first, dated files newest-first, git checked.
  **One drift found and corrected**: STATE.md claimed HEAD `2366c99`; three docs commits
  (`fc1b03d`, `de10856`, `1bcdb7b`) had landed after it. No functional drift.
- [x] **Read-only production analysis**, tenant `chick-shack`, six query batches. Orders counted
  with the system's own `is_real_order()` predicate plus rejected/voided removed, so the numbers
  match what the reports page would say. No writes, no restarts, Orbit untouched.
- [x] **Verdict formed: do not run 10% over £50.** £50 sits above the 93rd percentile of his own
  baskets. Costs a certain £42.10/fortnight to 7 customers who already spend it; the nudge pool
  is 3 to 5 orders averaging £2.73 short.
- [x] **Threshold sweep**: measured nudgeable-pool-per-giveaway at ten thresholds. **£40 is the
  peak at 1.70; £50 is the worst on the board at 0.43**, worse than £25.
- [x] **Found the actual opportunity, which is not the top end.** 53% of orders are one or two
  items averaging under £20; 50 orders a fortnight have no side, no drink and no dip at all;
  81 of 94 customers ordered once and never came back.
- [x] Costed nine offer variants against the same 15 days of real orders.
- [x] **Written up**: `_context/clients/chick-shack-uk/discount-analysis_2026-08-14.md` (full,
  with method, caveats, open questions and build reality check).
- [x] **Re-runnable read-only SQL saved**:
  `_context/clients/chick-shack-uk/discount-analysis_queries.sql`, with the three gotchas that
  cost time recorded in its header.
- [x] STATE.md + `_state/open-items.md` OI-82 updated with the full findings.
- [x] **Plain-English artifact** for Malik:
  `https://claude.ai/code/artifact/5fc8f9a0-9683-41f9-b45a-9d9c845f2a98`
- [x] Explained step by step in chat after Malik said the first pass was too jargon-heavy:
  band breakdown → the two groups the offer splits into → where the line should go and where the
  real opportunity is.

## In Progress
- Nothing. No code in flight, no deploy pending.

## Pending
- [ ] **Malik puts the numbers to Imran.** Nothing has been sent. Step 4 ("what I'd actually
      build and in what order") was offered in chat and not yet delivered.
- [ ] **Three questions only Imran can answer**: (1) his real food gross margin, (2) what a can
      and a portion of chips actually cost him, (3) whether he is trying to fix average order
      size, order count, or repeat customers.
- [ ] **Decide what to build**, if anything, once Imran replies. Ranked recommendation is in
      STATE.md and OI-82. The checkout add-on prompt is storefront-only and much cheaper than
      any discount mechanism; it should be priced separately and probably done first.
- [ ] **Commit and push these docs when the shop is shut** (see below).
- [ ] Carried over, untouched this session: **tip-flow UAT** (OI-81 residual), **OI-80** (CI and
      Deploy-to-Staging red on every commit, no signal), **OI-76** what3words reply drafted and
      unsent, **HSTS** on Cloudflare, **chips-flow UAT** from 08-13.

## Key Decisions
- **Pushed back on the client's idea rather than costing it out obediently.** The proposal is
  well-intentioned and the data says it loses money, so the analysis leads with "don't do this"
  and then answers the better question, where the opportunity actually is.
- **Did NOT commit or push.** Any push to this repo redeploys the droplet (no path filter), and
  the shop trades 16:00 to 22:00 UK. These are docs; there is no reason to blip the live API
  during service for them. Hold until close, exactly as the 08-13 docs push was held.
- **Analysed against `is_real_order()` rather than raw rows**, so the figures reconcile with the
  reports page. That excluded 4 abandoned/declined checkouts, 4 rejected and 4 voided from 116.
- **Labelled the 65% gross margin as an assumption every single time it appears**, and showed the
  55% and 75% sensitivity, because it is the one input we do not hold and it is load-bearing.
- **Stripped every em dash from the new docs and the artifact** per the standing rule.

## Files Modified (all UNCOMMITTED)
- `_context/clients/chick-shack-uk/discount-analysis_2026-08-14.md` (new)
- `_context/clients/chick-shack-uk/discount-analysis_queries.sql` (new)
- `STATE.md` (header corrected to HEAD `1bcdb7b`, new OI-82 block at top)
- `_state/open-items.md` (OI-82 added at top)
- `PAUSE_CHECKPOINT_2026-08-15.md` (this file, new)

## Uncommitted Changes
The five files above, **plus the ~127 pre-existing dirty files** (the long-standing doc reorg,
OI-60's paused and never build-tested backend work in `backend/Dockerfile` and
`backend/scripts/start.sh`, `frontend/src/pages/admin/StaffManagementPage.tsx`, and the untracked
`backend/app/scripts/seed_demo_kitchen.py`). All pre-existing and deliberate.

> ⚠️ **Do NOT `git add -A` in this repo.** Stage by explicit filename, every time.

## The numbers, so a fresh session does not have to re-query

110 orders, 31 Jul to 14 Aug, £2,750.44 food, average order **£25.00**, median £22.95, p90 £38.15.

| Band | Orders | % | Money | % | Avg |
|---|---:|---:|---:|---:|---:|
| Under £25 | 66 | 60.0% | £1,092.89 | 39.7% | £16.56 |
| £25 to £38 | 32 | 29.1% | £1,018.27 | 37.0% | £31.82 |
| £38 to £50 | 5 | 4.5% | £218.27 | 7.9% | £43.65 |
| £50 and over | 7 | 6.4% | £421.01 | 15.3% | £60.14 |

- Cost of the proposed offer on today's behaviour: **£42.10 / fortnight, ~£85 / month.**
- Break-even: a nudge only pays if the basket was under **£42.31** (at 65% GM). The three orders
  in £45 to £50 average £47.27, so each is about **minus £3.20**.
- Threshold sweep (pool within £8 below, per free giveaway): £25 → 0.75, £30 → 0.88, £35 → 1.47,
  **£40 → 1.70**, £45 → 0.40, **£50 → 0.43**.
- Items per order: **1 item 27 orders (£12.39 avg), 2 items 32 (£19.70)**, 3 items 22, 4 items 16.
- Of 67 orders under £25: 57 no side, 59 no drink, 64 no dip, **50 none of the three**.
- Repeat: **81 customers ordered once** (£27.06 avg lifetime), 10 twice (£42.41), 2 three times,
  1 four times.
- Channel: delivery 68 orders £27.17 avg (6 of the 7 over £50); collection 40 orders £21.07.
- +£1 on every order = **+£111/fortnight**; +£2 = **+£222**; +£4 = **+£444**.

⚠️ **The dataset is live and moves.** The count crept 108 → 111 during the session as real orders
landed. Re-run the saved SQL before quoting anything to a client.

## Errors & Resolutions
- **`round(double precision, int) does not exist`** killed two queries containing
  `percentile_cont`. Cast to `::numeric`. **Resolved**, and recorded in the saved SQL header.
- **`role " -d" does not exist`** when trying to inline SQL through `ssh` + `docker exec sh -c`.
  The nested quoting collapses. **Resolved** by writing a `.sql` file, piping it over `ssh`,
  `docker cp` into the container, then `psql -f`. Do it that way every time.
- **`column m.price does not exist`** on the modifier table. It is **`price_adjustment`**.
  **Resolved.**
- **Em dashes written into the artifact and the STATE/OI blocks** against the standing rule.
  Caught before finishing and stripped from all of them; artifact republished to the same URL.
  **Resolved.**

## Critical Context
- 🔴 **`chickshackg84.com` is live and taking real orders.** Shop hours 16:00 to 22:00 UK,
  delivery 16:30 to 21:30. Deploy only when shut unless Malik explicitly says otherwise.
- **Two deploy pipelines**: `git push origin main` = backend + tablet frontend (droplet);
  `cd storefront && npm run deploy` = customer site (Cloudflare). A green push proves nothing
  about the other. **Any push redeploys the droplet**, docs included.
- **Server `159.65.158.26`**, `~/pos-system`, shared with Orbit CRM behind one nginx. Read
  `memory/server-deployment-rules.md` and `memory/data-integrity.md` before touching it. nginx
  returns 444 to curl, pass a browser `-A`.
- **Production DB access that worked this session**, read-only:
  `ssh root@159.65.158.26` then
  `docker exec pos-system-postgres-1 sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB -f /tmp/q.sql'`.
  Chick Shack tenant id `8b2b6223-7db9-443b-8ace-34dd115a9275`.
- **Any discount work is a real build, not a setting.** `discount_amount=0` is hardcoded at
  `backend/app/services/public_order_service.py:572`, and grepping `storefront/src` for
  `promo|discount|coupon` returns **zero hits**. It would touch basket UI, price calc, Stripe
  line items, the printed ticket, the emails, the tablet card and the reports, across both
  pipelines.
- **CI is red and carries no signal (OI-80).** Judge deploys by Deploy-to-Production plus effect.
