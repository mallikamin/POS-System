# STATE — Restaurant POS System

**Last refreshed:** 2026-07-31 (session L) · **Branch:** `main`

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
- (ii) New-order sound alert — **deferred by Malik**, he wants to test it live on the real
  tablet himself rather than a second device/tab. Not yet checked either way.
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
| Stripe | 🔶 **DEPLOYED IN TEST MODE**, keys verified inside the container. Manual capture: authorise at checkout, **capture on Accept, cancel on Reject**, so a rejected order is never charged — this is exactly why proving it needs the shop genuinely open (Malik, 2026-07-30): the capture-on-accept step only fires when someone accepts a real order on the tablet. `cardPaymentEnabled` is **false** by design (not a bug — flagged off until a test card completes end to end, so no real customer's card gets silently declined against TEST keys). **Test override exists:** `chickshackg84.com/?card=1` shows the card button to whoever has that link only, `storefront/src/lib/cardPayment.ts`. **36 tests**, proven against the real sandbox. **Hardening H-1…H-10 done except H-6** — the four money-critical guards were **mutation-checked**, i.e. each was shown to fail when the code it defends is broken | `docs/STRIPE_HARDENING_CHECKLIST.md` · OI-20 / OI-41 |
| Printing | ✅ **ON PAPER (photographed 2026-07-29)**, session F built Imran's two asks: **3 labelled copies per ticket in ONE payload** (one `rawbt:` navigation) and the **daily `#NNN` double-size at the top of each copy**. **Paper check on his own printer now CONFIRMED 2026-07-31 (session L)** — Imran, to Malik: "I did print an order yesterday which we received and 3 copies printed." Closes the last open item under OI-51/52 | OI-51 / OI-52 ✅ built + ✅ confirmed on real hardware · `ERROR_LOG.md` |
| Served / delivered gap | ✅ **CLOSED and deployed.** Tablet has out-for-delivery / delivered / mark-paid; completed orders leave the Active tab; the customer's page follows it | `_state/open-items.md` OI-44 |
| Customer emails | ✅ **RESOLVED 2026-07-30 — Brevo live, real order proved it, then branded.** Order `260729-003`: confirmation delivered in 2 seconds, Gmail "Show original" — SPF PASS, DKIM PASS (`d=chickshackg84.com`), DMARC PASS. Domain authentication needed a fix along the way (Brevo requires its own DMARC record to flip `authenticated`; resolved by editing Imran's single `_dmarc` record in place, same `p=none` policy, not duplicating it). **Same session: all 4 emails (received/accepted/rejected/on_the_way) given branded HTML** — ink/flame/ember from `tailwind.config.js`, no logo (none exists), inline-style table layout for client compat, every customer-supplied string `html.escape()`'d (checkout form is public input). Shipped `3ab141b`, deployed, verified live via order `260730-001` — real Gmail screenshot confirms it renders as designed. Test suite: 45/45 email tests, 432/444 full suite (12 pre-existing, unrelated). Runbook: `docs/EMAIL_SETUP_RUNBOOK.md` | `_state/open-items.md` **OI-55** |
| Menu modifier prompts | ✅ **BUILT and deployed to production, 2026-07-31.** Peri-Peri Heat renamed to match his till; "make it a meal" is now 25 real Meal sibling products (drink + chips upgrade), not a flat +£3 tick. Exclusion ticks (no lettuce etc.) turned out to already be built. Verified against the live API: 87 items, no duplicates | `_state/open-items.md` OI-45 |
| Storefront photos | ✅ **9 real chunky-chicken-sourced photos live, replacing stock, deployed 2026-07-31.** 6 of 15 approved photos rejected on re-verification (2 for undisclosed trademark issues, 4 for product mismatch) rather than forced in. Verified against the live bundle + all 18 image URLs, not the deploy log | `_state/open-items.md` OI-56 |
| Backend test suite | ✅ **409 passing — run and verified 2026-07-29 session E**, not inherited. Session E started from a verified **393** (session D's "391" was two short) and added **16** for the Stripe hardening. Same **12 pre-existing failures** throughout (10 failed + 2 errors), all in QuickBooks-Desktop/parked code | `ERROR_LOG.md` |
| Core POS (10 phases) | ✅ Production, 98/99 UAT | `_state/pos-platform.md` |
| QuickBooks Online | ✅ Live. Sync is **manual by design**, not broken | `_state/pos-platform.md` |
| POS demo sites | ✅ Green (`pos-demo.duckdns.org`, `eats.sitaratech.info`) | `_state/infrastructure.md` |
| CI (`ci.yml`) | ❌ **Red on every commit.** Ruff + ESLint fail; Ruff exits before the test step, so **CI has never run the suite**. All findings are in parked code, none are live bugs. Deploys are a separate workflow and are green | `_state/open-items.md` OI-47 |
| Nightly demo-data cron | ❌ **Has never run** | `_state/open-items.md` OI-11 |

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
