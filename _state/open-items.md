# Open items register

**OI-80 🔴 NEW 2026-08-13, NOT FIXED. CI and Deploy-to-Staging are red on every commit, so neither
carries any signal.**

Found while shipping OI-79. `gh run list` shows **failure on all 8 most recent CI runs** and all 6
Deploy-to-Staging runs, covering `429ce34`, `c03e612`, `abf6177`, `1033943`, `52b1d1f`, `a49fef9`,
`2795ca2`, `5dda69f` — including commits that deployed cleanly and are running in production now.
Only **Deploy to Production** is green, and that is the workflow that actually ships.

**Why it matters, and it is the project's own standing lesson:** a suite nobody runs is decoration,
and a pipeline that is *always* red is worse — it looks like coverage while catching nothing. A
genuine break in `429ce34` would have produced exactly the same red as the eight before it. The local
run is currently the only real signal (536 passed, and the 21 failures + 2 errors reproduce
identically on a clean-HEAD worktree).

**Likely cause, unconfirmed:** the ~21 known-failing tests — the parked QuickBooks-Desktop suite, the
OI-63 UTC-vs-Europe/London time-of-day boundary failures, plus `test_p1a_features::
test_void_with_reason_succeeds` and `test_pay_first::test_transition_blocked_without_payment`. Nobody
has opened the CI log to check.

**Open:** root cause unread; no decision on whether to fix the tests, quarantine them, or stop running
the workflow.

---

**OI-79 ✅ CLOSED 2026-08-13. SHIPPED AND VERIFIED LIVE (`429ce34` + Cloudflare `f0d8764a`).** Chips
are now a required choice on all 25 meals and the meal groups read Heat → Chips → Drink → Dip.
Measured first: **23 of 112 meal lines since launch, 20.5%**, reached the kitchen with no chips
choice. Backup verified restorable before the change; every UPDATE tenant-scoped with a blast-radius
query confirming 0 other tenants touched. Full detail in STATE.md.

⚠️ **The lesson worth keeping, and it nearly shipped wrong:** the reorder looked like a data-only
change. It was not. `get_public_menu` **filtered** the modifier groups and never **sorted** them, so
`display_order` was inert on the storefront — setting it in the admin would have changed nothing and
been reported as done. Items in the same loop were already sorted, and the modifiers *inside* each
group were ordered by the relationship. **Only the middle level was missed, and the surrounding code
looked like proof it worked.** Verify the mechanism, not the neighbours.

---

**OI-78 ✅ CLOSED 2026-08-13. SHIPPED (Cloudflare `f0d8764a`).** A failed menu fetch no longer ends
ordering for the session: four automatic retries with a widening gap, an `online`-event listener, a
Retry button at checkout and a warning on the menu screen instead of an ambush at the checkout total.

⚠️ **Malik caught the copy before it went out.** The draft said *"ordering is off right now"* —
**false**, the shop was open; it is the customer's connection that failed. Shipped as *"Your internet
connection has dropped"* / *"We're open and taking orders as normal."* **A status message must name
whose fault it is; getting that backwards tells the customer the shop is shut.**

---

**OI-77 🟡 NEW 2026-08-12, DIAGNOSED, NOT AN OUTAGE, NOTHING BUILT. Imran reports "an issue on the
website"; his handset cannot reach the API, and the storefront reports that as "coming very soon".**

Imran's photo: a phone at checkout, basket **£23.18** (subtotal £22.48 + £0.70 service fee), showing
**"Online ordering is coming very soon / We're not taking online payments just yet. Give us a ring…"**
plus both Call buttons. He was in an **incognito** session. Malik placed a real order minutes later
that worked (`260812-C001`, collection, **PAID CASH**, accepted 17:01) and reports the site working on
his phone and laptop. 11 Aug ran clean to `260811-C013`, all card, all paid.

**Single possible cause in the deployed bundle.** `Checkout.tsx:402` branches on
`orderingLive = canOrder(menuSource, orderingPaused)`; `store/menu.ts:93` is
`SHOP.orderingEnabled && source === "api" && !paused`. The copy shown is the **non-paused** branch, so
`paused` was false, and `orderingEnabled` has been `true` since `90190a2` (2026-07-29). Therefore
**`source !== "api"`**: the `GET /public/chick-shack/menu` fetch failed on that handset and
`store/menu.ts:76` set `source: "fallback"`. The hardcoded menu rendered, ordering stayed off (correct:
fallback ids are slugs the order endpoint 422s).

**Our side verified healthy at the time of the report, not assumed:** menu API **200**, GBP, 8
categories, 87 items, `ordering_paused: false`; **8 consecutive requests all 200 at 0.93–1.06s**, so no
intermittent breach of the client's 12s `AbortController` cutoff (`lib/api.ts:196`); **CORS correct on
both real origins** (apex and `www` each get their own ACAO, `pages.dev` and `null` correctly get
none); deployed bundle resolved `index.html` → `/assets/index-D9lZ_Z-R.js` (200, 196,950 bytes, same
hash as 08-09) calling `https://eats.sitaratech.info/api/v1`.

**Not a stale cached bundle**, which was Malik's first theory, settled two ways: the handset rendered
the **Service Fee** row, which only exists from `f06979f` (2026-08-03), and every bundle since 29 July
has `orderingEnabled: true`; and incognito loads fresh regardless. ⚠️ A one-day window did exist
(`c68e616` 07-28 → `90190a2` 07-29) where this screen showed unconditionally, but no bundle from that
window can carry the service fee.

📌 **Unverified observation:** the status bar in the photo looks like Arabic script (reads like
**اتصالات / Etisalat**, a UAE carrier), which would mean the handset is not a UK device on a UK
network. Confirm whose phone it is before assuming UK customers are affected.

**The test that settles it, on his device, 10 seconds:** open
`https://eats.sitaratech.info/api/v1/public/chick-shack/menu` in the same browser. **JSON = network
fine, problem is browser-side** (content blocker, private-mode restriction, extension). **Spinner or
error = his network or DNS cannot reach that host.**

**Three real defects exposed, none of them the reported outage. Not authorised, do not build:**
1. **The copy is wrong and damaging.** A shop live for two weeks tells customers "Online ordering is
   coming very soon", i.e. "not launched yet". Should say we cannot reach our system, offer **Retry**,
   keep the phone numbers.
2. **No retry.** `App.tsx:77` fetches the menu **once on mount**. One blip and the customer browses,
   builds a basket, and is only told at the **checkout total**. Only a manual reload recovers it.
3. **Cross-origin dependency on an unrelated-looking domain.** Page is `chickshackg84.com`, API is
   `eats.sitaratech.info`. Any tracker blocker, DNS filter or carrier filter drops it **silently** into
   the copy above. Serving the API from `chickshackg84.com/api/*` via a Cloudflare route removes the
   cross-origin call, the CORS surface and the blocker surface at once. **This is the structural fix.**

**Any fix ships via `cd storefront && npm run deploy` (Cloudflare), NOT `git push`.**

**Open:** Imran has not run the one-URL test; the handset's identity, carrier and country are
unconfirmed; no fix authorised.

---

**OI-76 🔵 RESEARCHED 2026-08-10, RECOMMENDATION FORMED, NOTHING BUILT AND NOTHING SENT TO IMRAN.
Imran wants exact delivery locations, and proposes what3words (voice note, 2026-08-10 01:56 UK).**

Full transcript: `_context/clients/chick-shack-uk/voice-notes/2026-08-10_imran_what3words.md`.
**Research, costs, licence findings, recommendation and the unsent draft reply:**
`_context/clients/chick-shack-uk/delivery-location-research_2026-08-10.md`.

**Verdict: do not buy the what3words API.** Read off their published pages on 2026-08-10:
- The **Free plan cannot do the job** — AutoSuggest only, and AutoSuggest returns **no coordinates**.
  Turning three words into a pin needs `convert-to-coordinates`, which is paid. Basic is **£7.99/mo**
  for 1,000 conversions, ample for ~330 orders/month.
- **The licence, not the price, is the blocker.** Clause **6.3(b)** forbids displaying a 3 Word Address
  *alongside its corresponding coordinates*, and **6.3(e)(iii)** caps storage of the words-plus-
  coordinates pair at **30 calendar days**. That rules out the obvious build (words printed next to a
  tappable map link, kept on the order). Storing words **alone** is unlimited (6.3(e)(i)), so a plain
  optional text field costs nothing and stays compliant.
- **The conceptual point:** what3words solves a *speaking* problem, how a human transmits a location
  by voice. On our website nobody speaks — the phone already knows where it is. In Imran's security
  work both ends are trained staff with the app; a takeaway customer is a stranger who will not
  install one.

**Recommended instead, all free, in order:** (1) a driver-facing "how to find you" box, separate from
the kitchen note; (2) a "share my current location" button; (3) save the pin and directions **against
the customer record** so a hard address is solved once; (4) a map picker for the not-at-home case
(Google Maps Dynamic Maps: 10,000 free calls/month, then $7/1,000, so free at ~3% of allowance).

⚠️ **Checkout friction is the risk.** Abandonment is 1 basket in 45. Anything added must be optional,
small, and never between the customer and the Pay button.

**Verified in the repo:** `Checkout.tsx` collects address + postcode + a box labelled "Notes for the
**kitchen**" and has **no driver-facing field at all**; **no customer detail persists between orders**
(every field `useState("")`, only the basket is stored); but orders **do** link to a `Customer` row by
phone via `_link_customer`, so item (3) has its join already.

**Open:** Malik has not chosen what to send; no build authorised; a UK PAF address lookup (Ideal
Postcodes / getAddress.io / Loqate) was never costed as a fifth option; nobody has measured how many
delivery orders come from the delivery address, which is what decides whether item (4) is worth
building.

**The problem is real and he gave a case from that same night.** Delivery radius is 20 to 25 miles
around Garelochhead: named cottages instead of numbered houses, back roads, poor signal.
*"Aston Cottage, Shore Road"* was not findable in Google Maps **nor in PostTag**, which they already
use, and the driver had to ask the customer to walk out to the road.

**He is asking for advice, not ordering a build** — twice in the note. Do not treat this as a spec.

**Unresearched, and must not be answered from memory:**
- what3words is commercial. Licensing and API pricing to be checked against their current published
  terms.
- **The free alternative he has not considered:** browser Geolocation at checkout, attaching a maps
  link to the order. No third party, no app for the customer. Weak if they order away from the
  delivery address.
- what3words' catch in this exact case: the customer needs the app or the site to read their words.
  His own *"how do we influence people to use this"* is the real obstacle, and it is behavioural.
- Cheapest first move may be neither: a "how to find me" note saved on the customer record, so each
  awkward address is solved once.

⚠️ Any storefront change is a **Cloudflare deploy**, not `git push`.
See [[chick-shack-two-deploy-pipelines]].

**OI-75 🔵 NEW, NOT BUILT. Imran's QR code and a Google review link (raised 2026-08-09 by Malik).
The QR is verified working. The instruction attached to it is the part that needs resolving.**

**What arrived:** a red QR image (twice, as a standalone JPEG and inside a WhatsApp screenshot) with
Imran's *"This qr code goes to menu / On website"*. Malik asked *"do u want me to publish this on the
website menu?"* and Imran replied *"Yes please"*. Malik separately pasted a **Leave a review** link.

**Decoded, not guessed:** both images carry the identical payload **`https://www.chickshackg84.com/`**.
OpenCV's `QRCodeDetector` failed on every variant (the image has no white quiet-zone border);
`pyzbar` read it from the plain grayscale on the first try. Worth remembering for the next QR.

**Verified working on the customer's actual path** (mobile UA throughout):

| Check | Result |
|---|---|
| DNS `www.chickshackg84.com` | resolves, Cloudflare, same records as apex |
| `GET /` | **200**, no redirect, real storefront `index-D9lZ_Z-R.js` |
| `<title>` | `Chick Shack, Order Online \| Garelochhead` |
| **CORS from `https://www.chickshackg84.com`** | `access-control-allow-origin` echoes it ✅ |
| CORS from apex | echoes apex ✅ |
| CORS from an unknown origin | **no ACAO header**, correctly restrictive ✅ |
| Live menu payload | GBP, 8 categories, **87 items**, `ordering_paused: false` |

**The CORS check is the one that mattered.** `www.` is a different origin from the apex, and the
storefront calls `https://eats.sitaratech.info/api/v1` cross-origin, so a `www`-only allowlist gap
would have produced a page that renders perfectly and cannot load a single menu item. It does not
have that gap. A 200 on the HTML would not have proved this.

**"Goes to menu" is accurate.** `storefront/src/App.tsx` has no router, just one `view` state
initialised to `"menu"`. `/` *is* the menu, and there is no deeper URL to point a QR at.

⚠️ **Do not build the instruction as literally stated.** Publishing a QR that points at the website
**on** that website asks a customer already looking at the menu to scan a code to reach the menu.
The QR earns its keep **off** site: shopfront, counter, flyers, delivery bags, Instagram bio.
**Resolve with Imran first.** Two plausible readings: (a) he wants it printed and wants us to host
the image file, or (b) the thing that actually belongs on the site or receipt is the **review** QR.

**There are TWO QRs, and the second one is the review QR.** Imran sent a black QR at 23:27 PK.
It decodes to **`https://g.page/r/Ccxrn-XKIKecEBI/review`**, one character different from the link
Malik pasted (`...EAI`). **Same business, confirmed by decoding rather than by eye:** both short
codes are protobuf carrying the identical **CID `11288027046835350476`**
(placeid `ChIJm7hKDaSpiUgRzGuf5cogp5w`). The only difference is the trailing attribution byte,
`0x1002` vs `0x1012`, which Google sets from where the link was copied:
`laa=lu-desktop-review-solicitation` (desktop Business Profile) vs
`laa=nmx-review-solicitation-promoted-recommendation-card` (mobile app card). Functionally
identical for a customer. **It is Chick Shack's profile, confirmed by Malik.** Either link is safe
to use; prefer one and use it everywhere so the stats stay in one place.

**So the pair is: a menu QR and a review QR.** They belong in different places. The menu QR is an
off-site acquisition tool (shopfront, counter, delivery bags, flyers, Instagram bio). The review QR
is a post-purchase tool (printed receipt, the order confirmation screen, a table card).

**Nothing to reuse:** grep of `storefront/src` for `g.page`, `writereview` and `review` returns
**zero hits**. A review prompt on `OrderConfirmation.tsx` is new work, and it ships via
**`cd storefront && npm run deploy`** (Cloudflare), **not** `git push`.
See [[chick-shack-two-deploy-pipelines]].

**Next action: one question to Imran.** Where is the menu QR physically going, and is the review
link his (confirm by opening it)? No build until answered.

### 🟡 UNPARKED and BUILT 2026-08-10. NOT COMMITTED, NOT DEPLOYED. Read this first.

**Malik's final decisions (2026-08-10), all implemented:** item as **text, no photo** ("add the menu
item just, instead of picture for now"); **send after every order**, no once-per-customer flag;
**3 hours** after acceptance; timer-based, not a staff "Complete" tap.

**On his overnight question** (*"last email would be sent around 1am UK time... or maybe send that
first thing in morning"*): implemented as **a send window of 09:00 to 22:00 shop-local**. Anything
falling due outside it stays unclaimed until the next morning's sweep. Consequence he should know:
orders accepted after ~19:00 go out the next morning rather than the same night. Both bounds are
module constants.

**No Tailscale and no cron were needed.** The backend container runs 24/7 independently of the
tablet, so the sweep is an in-process timer (`app/services/review_email_worker.py`, every 300s,
started from `main.py`'s lifespan and cancelled on shutdown).

**Files (8):**
- `alembic/versions/t6u7v8w9x0y1_review_request_email.py` (new) — `orders.review_email_sent_at`,
  `restaurant_configs.google_review_url`, plus a partial index for the sweep's query.
- `app/models/order.py`, `app/models/restaurant_config.py` — the two columns.
- `app/services/email_service.py` — `_body_review` + `_html_review`, registered in both builder
  dicts; `send_order_email` gained `review_url` and **refuses the event when it is empty**.
- `app/services/public_order_service.py` — `send_due_review_emails()` + the three constants;
  `notify_customer` gained `review_url`.
- `app/services/review_email_worker.py` (new) — the timer.
- `app/main.py` — starts/stops the worker.
- `backend/tests/test_review_emails.py` (new) — 13 tests.

**Design decisions worth not re-deriving:**
1. **`google_review_url` is per-tenant and is also the feature switch.** NULL everywhere on deploy,
   so this ships **inert**. Hardcoding Chick Shack's link in the shared email service would be
   OI-73's hardcoded `(PKR)` in a new costume, and would send Cosa Nostra's customers to a chicken
   shop in Garelochhead.
2. **The claim is a conditional UPDATE**, not a read-then-write. `--workers 4` means four sweeps on
   the same timer. Same pattern as `mark_card_order_authorized` (OI-65).
3. **Claim is committed BEFORE sending.** Dying between the two costs one review request. The other
   order would re-send to everyone on the next sweep.
4. **`REVIEW_EMAIL_MAX_AGE = 12h`** so switching the feature on cannot mailshot old customers.
   ⚠️ Turning it on mid-evening WILL email that evening's earlier customers.
5. Reuses `is_real_order()` rather than re-expressing "is this order real".

**Verification actually run (2026-08-10, project `.venv`, Docker was down):**
- **13 new tests pass.** Full suite **521 passed**; the 21 failures + 2 errors are **byte-identical
  to a clean-HEAD `git worktree` at `ebe8d19`** run back-to-back (508 passed there, and 521-508 = 13
  = exactly the new tests). **Zero regressions.**
- **Mutation-checked, both directions.** Disabling the send window fails the 1am test; removing the
  stale-age filter fails the stale test. Both restored and re-run green.
- ⚠️ **One test was deliberately strengthened after it was found to be weak.** The sequential
  double-sweep test is satisfied by the `SELECT` filter alone and never reaches the claim, which is
  the "a query filter is not an invariant" trap (OI-61 → OI-65). A second test now drives the
  conditional UPDATE twice directly and asserts rowcount 1 then 0.
- `ruff` clean on all 8 files. `alembic heads` resolves to a single head, `t6u7v8w9x0y1`.

**✅ Verified against real PostgreSQL too, not just the SQLite suite** (local dev, `pg_dump` taken
first to `scratchpad/predeploy_local.sql`, 451 KB):
- `alembic upgrade head` applied both pending revisions. Both columns exist with the right types,
  and the partial index really is partial:
  `CREATE INDEX ix_orders_review_email_due ON public.orders USING btree (tenant_id, accepted_at) WHERE (review_email_sent_at IS NULL)`.
- **`downgrade -1` then `upgrade head` both succeed**, and the columns and index verifiably
  disappear and come back. The migration is reversible on production, not just forward-only.
- **The sweep itself was run in-process against PostgreSQL** with a real config row and a real
  order, email transport mocked: sweep 1 claimed the probe order, **sweep 2 claimed nothing**,
  `send_order_email` was awaited exactly once with `event="review"` and the right URL, and the claim
  was written to the row. Probe order deleted and confirmed gone; the borrowed timezone and the
  review URL were both restored (`0` probe rows, both tenants back to `google_review_url = NULL`).
- ⚠️ **The probe's first run "failed", and the failure was correct behaviour.** It picked
  `demo-restaurant` (`Asia/Karachi`), where 20:47 UTC is **01:47 local**, so the send window
  refused. That is the overnight guard firing against the real database. Re-run with the tenant's
  zone borrowed as `Europe/London` (21:47, in window) and it passed. **Worth remembering: this
  feature cannot be probed at an arbitrary hour without checking the tenant's local time first.**

## ✅ SHIPPED, DEPLOYED AND SWITCHED ON, 2026-08-10 (`5dda69f` + `2795ca2`)

Deployed ~05:30 BST, ~10h before the 16:00 open. Staged by explicit filename (10 files then 2);
OI-60's untested `backend/Dockerfile` and `scripts/start.sh` correctly left behind. Secret scan over
1,215 added lines: 0. `pg_dump` taken first (`~/backups/pre_review_email_20260810_053643.dump`).

**Switched ON for `chick-shack` only.** `cosa-nostra` and `demo-restaurant` remain NULL, i.e. off.

### 🔴 A real bug shipped in `5dda69f` and was caught minutes later. Read this one.

**`REVIEW_EMAIL_MAX_AGE = 12h` and the 09:00-22:00 window left a dead zone that silently binned
every peak-dinner order.** With the shop open 16:00-22:00:

| Accepted | Due | What happened at 12h |
|---|---|---|
| 16:00-19:00 | 19:00-22:00 | in window, sent that evening ✅ |
| **19:00-22:00** | 22:00-01:00 | window shut, waits for 09:00, by then 11-14h old → **dropped** |

**Found by dry-running the real query against production at the moment of switch-on**, not by
reading code and not by the green deploy. Both of 09 Aug's orders were already queued to be binned
(`260809-D001` 15.1h, `260809-D002` 13.9h at send time). Raised to **18h**, which covers acceptance
back to 15:00 the previous day at the 09:00 sweep.

⚠️ **The lesson, and it is a new one for this repo:** *the bug lived in the gap between two passing
tests.* `test_nothing_is_sent_in_the_middle_of_the_night` could not have caught it, because its
order is accepted at 21:30, only 11h before the morning sweep, so it fell inside even the broken
cutoff. Two constants were each individually sensible and wrong in combination. **When two limits
bound the same value from opposite ends, test the interaction, not each limit.** New test pins
acceptance at 19:30; reverting the constant to 12h fails it (mutation-checked).

⚠️ Second lesson: **a missing email is invisible.** This failure mode produces no error, no log and
no complaint. It looks exactly like a quiet evening. Anything that silently *declines* to act needs
a positive test, because nothing else will ever tell you.

### Live verification
- Server `git log` = `2795ca2`; migration `t6u7v8w9x0y1` applied; both columns present.
- `REVIEW_EMAIL_MAX_AGE` read back as `18:00:00` **from inside the running container**.
- Sweep run in-process against production across all 3 tenants: clean, no errors.
- Backend healthy, 0 exceptions. **Orbit CRM untouched** (8 weeks / 2 months / 3 months uptime).
- `/api/v1/health`, `/online-orders`, `chickshackg84.com` all 200.
- **Confirmed queued for the 09:00 BST sweep: 2 emails**, `260809-D001` (£42.20) and `260809-D002`
  (£11.69). That is exactly 09 Aug's two online orders.

⚠️ **Not yet observed: a real email actually arriving in a real inbox.** The first live send is the
09:00 BST sweep. Until someone sees one, delivery through Brevo for this new event type is inferred
from the three existing emails using the same transport, not proven.

### Notes for later
- **No admin UI for `google_review_url`.** Switching a tenant on is a SQL `UPDATE`. Fine for one
  restaurant, worth a Settings field when there are more.
- **The storefront confirmation-screen half was deliberately NOT built.** Malik established the page
  polls at most 2h past acceptance and has no route back once closed, so almost no customer would
  see it. Email only.
- App-level `logger.info` **never reaches production logs** (0 app lines in the whole container log).
  That is OI-60's gap, not this feature's, but it means this worker is unobservable from the logs.

<details><summary>Earlier parking note, kept for the trail</summary>

### ⏸️ PARKED 2026-08-10 by Malik ("pause this task and park it for now"). Resume from here.

Design was agreed and a copy mockup was published for his review
(artifact `077c3104-d28b-4a41-969d-5bcfd52ad241`, source at
`scratchpad/review-request-mockup.html`). **Nothing was built. No file in the repo was changed.**

**Agreed so far:** review ask goes on the order confirmation screen (extending the existing
`completed` block, which already reads *"We hope it was good. See you again soon."*) **and** in a
new email. Rejected orders never get one. Use the `...EBI` link everywhere so Google's source stats
stay in one bucket.

**Malik's two changes, received just before the pause, NOT yet incorporated:**
1. **Add the menu item and its picture to the email.**
2. **Do not wait for a staff "Complete" tap. Send the email 2 to 3 hours after the kitchen
   accepts the order.** (His reasoning: it does not depend on staff behaviour. Agreed in principle,
   see the findings below for what it actually costs.)

**Findings already established for (1), so they are not re-derived on resume:**
- **The POS database has no food photography.** `image_url` is null on **all 87** live Chick Shack
  items (checked against the live menu payload, not assumed).
- **The photos exist, but only in the storefront**, 176 files under `storefront/public/img/`,
  as `/img/thumb/<name>.webp` (240x180) and `/img/hero/<name>.webp` (720x480). The item to photo
  mapping lives in `storefront/src/data/menu.ts` and is joined **by item name** in
  `storefront/src/lib/menuAdapter.ts`. `types.ts` has the `imageThumb`/`imageHero` helpers.
- **They are publicly reachable and therefore usable in an email** (verified live):
  `https://www.chickshackg84.com/img/thumb/fried-chicken.webp` → **200, image/webp, 21 KB**;
  the hero equivalent → 200, 111 KB. Use the **thumb**, not the hero, in email.
- ⚠️ **The hard part is that the backend cannot see any of this.** Emails are built in
  `backend/app/services/email_service.py`, which has no knowledge of the name to photo map. So this
  needs a deliberate decision: duplicate the map server-side (a second home for a rule, which is the
  exact mistake OI-61/65/66/68/73 keep punishing), or backfill `menu_items.image_url` in the DB so
  there is **one** source of truth. **Backfilling the DB is the right answer** and it also fixes the
  storefront's name-join fragility.
- ⚠️ Many mail clients block remote images by default, so the email must read correctly with every
  photo suppressed. Alt text and layout have to carry it alone.

**Findings for (2), the 2 to 3 hour delay:**
- **There is no scheduler, cron or task queue in this backend.** The existing pattern for deferred
  work is to piggyback on the tablet's own poll: `publish_authorized_card_orders` runs on every
  merchant-orders poll. A review-email sweep would work the same way, which is why the idea is
  cheap. **Verify this claim on resume before relying on it.**
- ⚠️ **Consequence to design around:** the sweep only runs while the tablet is polling. An order
  accepted at 21:45 plus 3h lands at 00:45, when the tablet is off, so the email would not go until
  the shop reopens (~16:00 next day). That is probably acceptable, but it must be **bounded** so a
  stale order does not get a review request two days later.
- Anchor on **accepted_at, not created_at**. A pre-order placed at 14:00 is not accepted until 16:00,
  and the food arrives after acceptance.

---

**OI-73 ✅ CLOSED. SHIPPED AND VERIFIED LIVE 2026-08-08 (`5134430`). The sales-summary CSV labelled
Chick Shack's money in PKR (raised 2026-08-08 by Malik).**

**What he saw:** from `https://eats.sitaratech.info/online-orders/reports`, the Daily Sales CSV
download (`sales_2026-08-07_2026-08-08.csv`) read `Total Revenue (PKR),371.07`. Pounds taken in
Garelochhead, labelled rupees. The Prepaid vs COD CSV from the *same page and the same date range*
read `Prepaid Revenue (GBP)` and was correct. His instruction: **"all reports should be tied to the
tenant currency."**

**Root cause, and it is the standing lesson again.** `backend/app/api/v1/reports.py`
`export_sales_csv` hardcoded the literal string `"(PKR)"` on all 13 money rows. The online reports
(`online_reports.py`, OI-58) do it correctly via `public_order_service.get_currency(db, tenant_id)`,
which is exactly why one CSV was right and its neighbour was wrong. **A second, inline expression
of a rule that already had one home.** Same shape as OI-61/65/66/68 and the OI-72 note above.

- **The money itself was never wrong.** `371.07` is the correct GBP major-unit figure; both
  currencies in `CURRENCIES` have `minorExponent: 2`, so the exporter's `/100` is right for either.
  **Label-only defect.** Cross-checks: the prepaid CSV shows the same `371.07` under a GBP label,
  and 371.07/11 = 33.73 matches the exported Avg Order Value.
- **Nothing else was affected.** The on-screen tiles on that page were already correct:
  `OnlineReportsPage.tsx` passes `config.currency` into `formatMoney`. `frontend/src/utils/currency.ts`
  is currency-aware and `configStore` calls `setActiveCurrency` on fetch, so ReportsPage,
  AdminDashboard and ZReportPage were fine. There are **only two CSV exporters in the whole
  backend** (`reports.py`, `online_reports.py`); the other was already correct.

**Fix:** `reports.py` now resolves the tenant currency through the same `get_currency` helper and
f-strings every money label. Order *counts* deliberately keep no currency suffix.

**Verification actually run (2026-08-08, local dev container):**
- New `backend/tests/test_report_currency.py`, 4 tests: GBP tenant gets GBP on all 12 money rows and
  **no `PKR` anywhere in the file**; PKR tenant still gets PKR and no `GBP`; no-config tenant falls
  back to PKR rather than emitting an empty `()`; count rows carry no currency suffix.
- **Mutation-checked.** Reverting one row to the hardcoded `"Card Revenue (PKR)"` fails the GBP
  test. The test can fail, so its passing means something.
- Full suite **519 passed**, `ruff` clean on both touched files. The 10 failures + 2 errors are
  pre-existing: 10 are the parked QB-Desktop suite, and the two that are not
  (`test_p1a_features::test_void_with_reason_succeeds`,
  `test_pay_first::test_transition_blocked_without_payment`) were **confirmed failing identically on
  a clean-HEAD `git worktree` at `5b3dc00`**, run back-to-back in the same container. Zero regressions.

**✅ DEPLOYED ~07:40 UK on Malik's "commit push deploy", commit `5134430`.** Backend-only, shipped by
`git push origin main`; the Cloudflare storefront pipeline correctly not run. Touched no money,
order-number, email, ticket or queue path.

**Live verification, stronger than a grep:** `export_sales_csv` was **called in-process inside the
running production container against the live database**, for all 3 active tenants, over the exact
07-08 Aug range Malik used. `chick-shack` returns `Total Revenue (GBP),371.07` with **PKR count 0**;
`cosa-nostra` and `demo-restaurant` still return `(PKR)` with **GBP count 0**. The value is unchanged
from the broken export, which is the proof the defect was label-only. Server `git log` = `5134430`,
containers healthy, **Orbit CRM untouched**, all four public URLs 200 with a browser UA, 0 backend
exceptions and 0 nginx 5xx.

⚠️ **Verification trap, logged because it nearly became a false alarm:** a first 5xx count returned
"4" purely because the grep pattern ` 5[0-9][0-9] ` matched nginx's **response size** `537` rather
than the status code. Every one of those lines was `200 537`. Anchor on the status field
(`" 5[0-9][0-9] `), or tally with `grep -oE '" [0-9]{3} '`.

---

**OI-74 🔵 NOTED, NOT FIXED, NOT ASKED FOR. Two more hardcoded-PKR surfaces found while fixing OI-73.**

Deliberately left alone rather than swept in. The OI-71 lesson is that changing a live screen
nobody complained about is how you create work. Recorded so the next GBP tenant does not rediscover
them:
1. **`frontend/src/pages/admin/qb/SyncTab.tsx:137`** defines its *own local* `formatPKR` that
   hardcodes `Rs.` and `en-PK`, shadowing the currency-aware util. A GBP tenant's QuickBooks sync log
   would render `Rs.371.07`. Invisible to Chick Shack today (Imran refused QuickBooks), so it is
   latent, not live. One-line fix: import `formatMoney` from `@/utils/currency`.
2. **Input-form labels**, not reports: `Price (PKR)` / `Amount (PKR)` / `Cost per Unit (PKR)` /
   `Fixed Threshold (PKR)` in `MenuManagementPage`, `IngredientManagementPage`, `DiscountTypesPage`
   and `SettingsPage`. A Chick Shack admin editing a menu item is told to type rupees.
3. ⚠️ **A real limit worth knowing before a third currency arrives:** both CSV exporters divide by a
   literal `100`. That is correct for PKR and GBP (both 2 minor digits) and wrong for a 3-digit
   currency (KWD) or a 0-digit one (JPY). Not a bug today, but a trap if a Gulf tenant ever lands.
   The exponent already lives in `currency.ts`; the backend has no equivalent.
   (Note: the petrol pump is a **Pakistan** business, PKR, so it is not a case for this.)

---

**OI-72 🔵 NEW, NOT STARTED. Meta ads experiment for online ordering (raised 2026-08-07, Imran via
Malik). Blocked before it begins, and the measurement layer does not exist.**

**The ask:** Imran proposed running Meta ads to push online ordering. Malik: *"we'll need to first
connect his fb/ig - get admin access."*

**Blocker 1: Imran cannot act in Meta at all.** His words: *"My meta ads account is restricted and
will not allow me to post ads."* Linking the Instagram and Facebook Page returns **"Your account is
restricted. You're temporarily restricted from taking this action to protect your profile. Please
try again later."**
✅ **DIAGNOSED 2026-08-08.** Malik asked Imran for `facebook.com/accountquality`; Imran hit the
"view this on a computer" redirect on mobile, then sent the desktop **Business Support Home** page
(`/business-support-home/100004720803467`). It answers the question this entry was blocked on, and
the earlier guess ("profile-level *temporary* action block") was **half right and far too
optimistic**:

| Field | What Meta actually shows |
|---|---|
| Scope | **Personal Facebook account**, `Imran Rasul`. Not the Page, and not only an ad account. |
| Badge | 🔴 `Account restricted` |
| Date | **"Restricted on 9 Oct"**, no year rendered. **Assume ~10 months old until confirmed.** |
| Reason | *"You're not allowed to use Meta Products to advertise... didn't comply with one or more of our Advertising Standards affecting business assets, such as having too many ads rejected, attempting to circumvent our ad review process, participating in fraudulent behaviour or associating with untrustworthy accounts."* |
| Restrictions | can't use or manage ad accounts · can't create or run ads · **can't manage advertising assets or people for businesses** |
| Disabled assets | **Personal ad account**, **Audiences** |
| Page | **not listed as disabled.** Appears clean on this page. |

- **The IG-to-Page linking failure is the same restriction, not a second problem.** "Can't manage
  advertising assets or people for businesses" blocks Business-tools actions, and Meta surfaces that
  with its generic *"temporarily restricted... to protect your profile"* wording. One cause, two
  symptoms. Do not chase them separately.
- ⚠️ **This is Meta's severe advertising bucket and it is old.** Wording citing *circumvention* and
  *fraudulent behaviour* is rarely reversed, and any standard appeal window is long past if the date
  reads 2025. **Treat the appeal as a free lottery ticket, submitted once, and build the plan on the
  assumption it fails.**
- ⚠️ **"Associating with untrustworthy accounts" is a propagation clause, and the exposure is
  Malik's.** A portfolio that takes on this Page can inherit scrutiny. **Use a dedicated throwaway
  business portfolio for Chick Shack. Never the one running goldennummbers / postpaidplans.**
- **Still unverified, and each one changes the next step:**
  1. Does a `Request review` / `Disagree with decision` control still exist on the restriction
     detail, or has the appeal already been spent? The `What you can do` panel offers only
     `See accounts`, which is weak evidence the review route is already closed.
  2. What does `See accounts` list, i.e. does a **business portfolio** already exist, and is it
     restricted too? A `Finish onboarding` / daily-spend-limit card is visible, implying one exists.
  3. **Page access roles**: is Imran the only admin with Full control? He must be able to add a
     second admin or the clean-portfolio route dies too.
  4. Is the Instagram account **professional**, and already linked to some other Page?
  5. Is there an unpaid ad-account balance or failed payment method? That alone blocks publishing.
- ⚠️ **Do not create a second profile to route around this.** Meta associates accounts by device,
  payment method and IP; an evasion attempt puts the **Page** at risk, and the Page is the shop's
  real asset. Legitimate route only: appeal the restriction, and in parallel put the Page into a
  business portfolio where a *different, clean* admin (Malik) holds a separately-funded ad account.
  Ads run from an ad account inside a portfolio. They do not have to run from Imran's profile.
- **Access we actually need from Imran, in Meta's own terms** (ask for exactly this, not "admin"):
  Page **Full control** task set; Instagram linked in the same portfolio; then a **new ad account
  with its own payment method**. Domain `chickshackg84.com` must also be **verified** in the
  portfolio before any conversion optimisation works.

**Blocker 2, verified, and the bigger one: the storefront has no measurement of any kind.** Grepped
`storefront/` for `fbq`, `pixel`, `gtag`, `dataLayer`, `google-analytics`: **zero hits** (the only
matches are base64 strings in `package-lock.json`). **An ad can be run today; an order cannot be
attributed to it.** Spending before this exists buys an unreadable result.
- **The Purchase event must fire on Stripe authorisation, not at checkout start.** Counting a
  created checkout session as a conversion is exactly the defect behind the **£98.96 vs £36.04**
  scare (OI-66). **`backend/app/services/order_visibility.py` already owns "is this order real"
  (`is_real_order()` / `money_actually_taken()`). Import it; do not re-express it.** This is the
  fifth time that standing note applies (OI-61, 65, 66, 68, and now here).
- **Prefer the server-side Conversions API over a browser pixel.** The Stripe hosted-checkout round
  trip is a full page reload (nothing survives it but what `lib/pendingOrder.ts` stashes), so a
  confirmation-page pixel will systematically under-report. The natural hook is the same
  authorisation moment that already sends the "order received" email (`publish_authorized_card_orders`
  or the webhook path), which is server-side and already exactly-once by atomic conditional UPDATE.
- ⚠️ A pixel on the storefront is a **Cloudflare deploy** (`cd storefront && npm run deploy`), not a
  `git push`. See [[chick-shack-two-deploy-pipelines]].
- ⚠️ **UK/EU: this is personal data.** A pixel or CAPI send needs a consent mechanism and a privacy
  notice on the site; neither exists today. Not a blocker to investigate, but it is a blocker to
  ship, and it should be Imran's informed decision, not a silent addition to his site.

**Next action: read-only look at Imran's Meta setup to establish what is actually restricted.**
No build, no ad spend, no storefront change until that is known.

---

**OI-71 🔴 REVERTED IN FULL (`1043686`, then `1e6bff3`, then **`5b3dc00`**, 2026-08-05). The tablet
card is back to `d9f57e7` and dips render inline as an ordinary priced modifier, deliberately.**
The two entries below are kept as the incident record. **Neither shipped shape survives.** Malik
rejected the second one on sight (*"ur making it look like a freakin duplicate? dips vs dips tub?"*)
because the same dip appeared twice on one card: `Algerian Sauce (Dip Tub)` under its item, and
again as `Dips to pack: 1 × Algerian Sauce`. `5b3dc00` deleted every dip helper from
`lib/orderDisplay.ts` (OI-70's timezone work untouched, 16/16 passing) and left a standing note at
the top of the page so nobody re-derives it. **The printed ticket groups dip tubs and was correct
and untouched throughout.**
**The lesson that generalises is not "check the medium".** It is that the true answer to Imran's
question was *"receipts are already fine, this screen needs no change"*, and stopping there was the
whole job. A live screen was changed with no defect behind it, then patched twice.

<details><summary>Superseded OI-71 record (both shipped shapes, kept for the incident trail)</summary>

**OI-71 (superseded) — the tablet UI
did not roll**
- ⚠️ **Malik's UAT rejected the first shape, correctly.** *"why are dip tubs showing so differently
  — its just the regular item. what abt its price, why isnt it reflecting? i hope we are not
  screwing up with the total order value."*
- **The money was never wrong** — checked against production, not reasoned about. `260804-002`'s
  Peri Peri Wrap Meal has `unit_price` **1198 = 999 base + 99 Garlic Mayo**, `line_total =
  unit_price × quantity`; the rule holds on every row (`499+200=699`, `999+50=1049`,
  `1099+99=1198`). Malik confirmed independently from a cart: £11.49 + 99p = £12.48. The commit only
  filtered modifier *names*; no total was ever referenced. **Dips cost 99p (79p Ketchup/Mayo).**
- **The display was wrong.** Lifting a *priced modifier* out of the item whose price contains it left
  `1 × Garlic Mayo` with no price, sitting above two meals it had nothing to do with (its real parent
  was further down the card). On a card where every row carries a price, that reads as a lost charge.
- **Lesson, and it generalises: a treatment that is right on the printed ticket is not automatically
  right on screen.** On monochrome thermal paper a `DIP TUBS` heading reads as a picking list because
  nothing around it has a price. On the tablet card everything does. Check the medium before porting
  a layout across. See also [[filter-is-not-an-invariant]] for the sibling lesson about porting a
  rule rather than a layout.
- **Fixed in `1e6bff3`:** dips inline under their own item; the roll-up kept as an *instruction*
  beside the kitchen note (`Dips to pack: 1 × Garlic Mayo`). **Printed ticket untouched** — grouping
  is still right for paper.

<details><summary>Original OI-71 writeup (the receipt verification in it is still accurate)</summary>

**The tablet UI did not roll
dip tubs up; the printed ticket already did. UI-only, receipts were always fine.**
- **Built:** the card now renders a `DIP TUBS` block with per-name counts above the item list and
  filters dips out of the item sub-lines — same `" (Dip Tub)"` suffix rule, same name sort, same
  count-by-line-quantity as `print_service.py`. Logic lives in `frontend/src/lib/orderDisplay.ts`
  (`dipTubTotals`), extracted so it can be bundled and run for real; verified against `260804-C010`,
  `260804-C011` and Malik's 3× Fillet Tower screenshot (3 meals × 1 dip = **3** tubs, not 1).
  Mutation-checked: counting occurrences instead of quantity fails 2 tests.
Malik saw dip tubs still rendered as a grey sub-line under the parent item on
`eats.sitaratech.info/online-orders` and asked whether the receipt change ever shipped.
- **It shipped and it is live, verified — not assumed.** `DIP TUBS` is present in
  `print_service.py` **inside the running production container** (`docker exec pos-system-backend-1
  grep -c 'DIP TUBS'` → `1`, server `git log` at `d9f57e7`). Every `… (Dip Tub)` modifier is rolled
  up by name into a bold `DIP TUBS` block above the cook list and suppressed from the item's own
  sub-lines (`print_service.py:166-193`, shipped `f06979f`, session S / OI-64).
- **The gap is one place only: `OnlineOrdersPage.tsx:1060-1064`**, which prints
  `line.modifiers.join(", ")` verbatim, dips included. Nothing else in the codebase consolidates —
  confirmed by grep: `DIP_TUB_SUFFIX` / `"Dip Tub"` appears in `print_service.py` **and no other
  service**. The customer's email lists them inline too, which is arguably correct there (the
  customer ordered a sauce with an item, they did not order a tub) — flagged, not assumed wrong.
- **Open question at the time:** mirror the ticket on the tablet card, or leave the screen inline?
  Malik chose "mirror the ticket" — and his own UAT then showed why that was the wrong call on this
  medium. Superseded by `1e6bff3` above.

</details>

</details>

---

**OI-70 🟢 SHIPPED + VERIFIED LIVE (`1043686`, 2026-08-05) — order times were
relative-only, and the one absolute time rendered in the *viewer's* timezone, not Scotland's.**
- **Built:** the card's time line now reads `12 min ago · placed 19:56` while an order is unanswered
  and `Placed 19:56 · accepted 19:59` once it is (or `· rejected HH:MM`). Every clock time is
  formatted with `timeZone: config.timezone`, so the tablet in Garelochhead and a screen in Pakistan
  show the identical figure. The relative age is kept on pending orders **on purpose** — it is what
  justifies the red/amber border, and dropping it would leave the colour unexplained.
- `shopTime`/`placedAt` moved to `frontend/src/lib/orderDisplay.ts` and verified for real (bundled
  with esbuild, run in a process whose own timezone was `Asia/Karachi`): BST and GMT, midnight
  rollover both ways, and an invalid config value falling back instead of throwing — `Intl` throws
  on an unknown zone and a bad config row must not blank the whole queue. Mutation-checked: removing
  the `timeZone` option fails 12 tests.
- `OnlineOrdersPage` now fetches config itself when it is missing, same reason and same pattern as
  `OnlineReportsPage` — a hard refresh straight onto this route (which is how the tablet opens)
  never runs `POSLayout`'s `fetchConfig()`.
The card shows `468 min ago` and nothing else. Two separate defects behind that:
- **(a) No absolute time, and no accepted time at all.** `accepted_at` is fetched and present in
  `MerchantOrderSummary` but used only as a boolean (`OnlineOrdersPage.tsx:1095`) — the actual
  clock time an order was answered is never shown, so response time cannot be read off the screen.
- **(b) The absolute time that *does* exist is timezone-naive.** `placedAt()`
  (`OnlineOrdersPage.tsx:81-88`) calls `toLocaleString("en-GB", …)` with **no `timeZone` option**, so
  it renders in the browser's zone. On the shop tablet in Garelochhead that is correct by accident;
  on Malik's machine in Pakistan every timestamp is silently **+4h/+5h wrong**. It is only reachable
  today on pre-orders (>3h old), which is why it has not bitten yet.
- **The fix has no backend work.** `RestaurantConfig.timezone` is already `Europe/London` for this
  tenant (`seed_chick_shack.py:128`), already returned by `GET /config/restaurant`, already typed on
  the frontend (`types/index.ts:50`) and already in `useConfigStore`. Pass it as `timeZone` and
  format both stamps from it.
- **Open question for Malik:** keep `468 min ago` alongside the clock times or replace it? The
  relative age is what drives the red/amber urgency colour on a pending card, so it earns its place
  there; on an *answered* order it is noise.

---

**OI-69 🟢 SHIPPED + VERIFIED LIVE (`1043686`, 2026-08-05) — `/online-orders` was a dead
end for an admin: no logout, no user switch, no restaurant switch.**
- **Built: a new `/switch` route** (`frontend/src/pages/auth/SwitchPage.tsx`). Shows who is signed in
  and at which shop, then one button signs out **and** clears the remembered tenant slug, landing on
  the login form. `LoginPage` gained an optional **Restaurant** field, collapsed by default and
  prefilled from the remembered slug, persisted via a new `setTenantSlug()` before the login call
  (the auth store reads the slug at call time, so saving it on success would be too late).
- **`/switch` is deliberately not linked from the order queue.** That tablet is unattended in a live
  shop; a Sign-out in its header is one mis-tap from locking the counter out mid-rush, and getting
  back in needs a PIN whoever is on shift may not have. Malik reaches it by bookmark.
- **`logout()` itself was left alone on purpose** — it still keeps the tenant slug, so a staff member
  signing out on the tablet returns to the same shop. Clearing the slug belongs only to the
  deliberate "switch restaurant" action.
- **Verified the shop's own login path is behaviourally unchanged**: with a remembered slug the
  field stays collapsed and `rememberShop()` no-ops, so `loginWithPin` sees the identical slug it
  saw before. Devices with no slug (single-tenant deployments) still fall through to the server's
  own single-active-tenant rule.
Malik's words: *"once im logged in chick shack, theres no way for me to logout — im stuck in this
window."* Confirmed structurally, this is real and it is a trap, not just a missing button:
- `/online-orders` is mounted **outside** `POSLayout`/`AdminLayout` (`App.tsx:86`), deliberately, so
  it is fullscreen on the shop tablet. Both layouts own the only logout controls in the app
  (`POSLayout.tsx:50`, `AdminLayout.tsx:79`) — so the queue page has none.
- **`/login` does not rescue you.** `LoginPage` redirects to `/` when already authenticated
  (`LoginPage.tsx:30`), and `/` redirects to `/online-orders` for a tenant with
  `online_ordering_only` (`DashboardPage.tsx:73`). The loop closes.
- **Only escape today: type `/admin` by hand** (works — Malik is `admin`, and `AdminLayout` has a
  Logout). Undiscoverable, and not something to hand a client.
- **Restaurant switching is half-built.** The backend already accepts `tenant_slug` on both login
  routes and refuses to guess when >1 tenant is active (`auth.py:56-92`) — that part is done.
  `getTenantSlug()` prefers `?shop=` over the remembered slug, so `/login?shop=<other>` would work.
  But **`clearTenantSlug()` is exported and never called anywhere** (grep: `lib/tenant.ts:53`, zero
  call sites), so `logout()` leaves the previous shop's slug in `localStorage` — and there is no UI
  to pick a shop.
- **⚠️ Real risk to weigh before building, not a reason not to:** this tablet sits unattended in a
  live shop. A plain "Sign out" in the header is one mis-tap away from locking the counter out
  mid-service, and getting back in needs a PIN nobody on shift may have. Whatever ships should be
  hard to hit by accident.
- **Open question for Malik:** discreet control on the tablet itself, or a separate bookmarked
  `/switch` route (logout + clear slug + shop picker) that never appears on the shop's screen?

---

**OI-68 🟢 SHIPPED + VERIFIED LIVE (`99b6757`, 2026-08-05) — order-number allocation race.**
Malik caught this from a probe that printed `260804-C006` and `260804-D006` together. The probe
output was misleading (three generator calls, nothing saved between them, so all three correctly
reported "next is 006") — but he had found a real hole introduced by OI-67's C/D marker:
`generate_order_number` derived the number from `count(*) + 1`, so two customers checking out in the
same instant both took the same sequence, and because `-C006` and `-D006` are *different strings*
the `uq_order_tenant_number` unique index could not catch the collision either. Before the letter
existed, that index was an accidental safety net; the letter removed it.
- **Fixed two ways, both needed.** (a) Allocate from the **highest number already issued today**,
  letter stripped — one sequence across both letters, and no rewinding onto a number already printed
  on a receipt when a row is voided or deleted (which `count(*)` did). (b) A per-tenant `FOR UPDATE`
  lock on the config row, because read-max-then-insert is still a read-modify-write. SQLite omits
  `FOR UPDATE` and the tests are single-threaded, so nothing is lost there.
- **Checked production before changing anything: zero duplicate order numbers have ever existed.**
  Closed before it bit. Closest real case: `260804-C010` / `-C011`, **22 seconds** apart.
- 3 new tests: shared counter across C/D, no re-issue after a deletion, till orders keep
  `YYMMDD-NNN` while drawing from the same sequence.

---

**OI-67 🟢 SHIPPED + VERIFIED LIVE (`6378b67`, 2026-08-04) — Imran's two feature asks.**

**(a) Pause online ordering.** One button on the tablet that stops collection AND delivery together
during a rush, and resumes as cleanly.
- **Enforced server-side** in `create_public_order` — HTTP 503 with its own `OnlineOrderingPaused`
  type — **not merely hidden in the storefront**. A stale tab, a bookmarked checkout or a direct POST
  are all refused and **no order row is written**. This is the OI-61/OI-65 lesson applied up front
  rather than after an incident.
- **No submission is possible on the website while off** (Malik was explicit): the entire checkout
  form — name, phone, address and the Pay button — is not rendered. Replaced by Imran's exact
  wording, *"We are facing high demand at the moment, please directly call the restaurant
  07719 566 889 to place your order. We appreciate your patience in this regard."* Shown at the top
  of the menu too, so nobody builds a basket first.
- **Orders attempted while paused are lost by design** — Malik's explicit instruction. The point is
  to move customers to the phone; a backlog landing the instant the shop resumes would defeat it.
- **Default is ON** (`server_default=false`), so no tenant's behaviour changed on deploy. Turning
  ordering **off** asks for confirmation first (*"this will disable live orders, proceed with
  caution"*); resuming is one tap — the dangerous direction is the one that turns paying customers
  away and the one nobody notices they left on. The tablet re-reads the state from the server on
  every poll, so a second tablet cannot show a stale button.
- Migration `s5t6u7v8w9x0_pause_online_ordering.py` (`restaurant_configs.online_ordering_paused`).
  Confirmed applied on production, default `false`.
- ⚠️ **Not yet UAT'd by Imran on the real tablet.** It needs a page refresh to appear — new JS
  bundle, old one cached. Malik hit exactly this and thought the button was missing.

**(b) C/D in online order numbers.** `260804-C001` collection, `260804-D002` delivery — **one shared
counter**, per Malik: the letter marks the category, it does not start a separate sequence. Other
channels (dine-in, takeaway, call centre) pass no `service_type` and keep `YYMMDD-NNN`. **No existing
order number was rewritten** — visible live as `260804-004` → `260804-D005` mid-service.
(See OI-68 for the allocation race this exposed.)

---

**OI-66 🟢 SHIPPED + VERIFIED LIVE (`4e2fe5c`, 2026-08-04) — reports counted unpaid card orders as
revenue; the tablet called approved money "processing".** Both surfaced live, in front of the client.
- **The money display.** The reports screen showed **£98.96** online and "prepaid" revenue when only
  **£36.04** had actually been taken. Two causes: both report queries summed `Order.total` for every
  non-voided order, and `is_prepaid` was defined as `stripe_checkout_session_id IS NOT NULL` — a
  session created the instant the customer is sent to Stripe, whether or not they ever pay. Order
  `260804-002` (£62.92, unapproved at the time) was counted as prepaid revenue.
  **Prepaid now means `payment_captured_at IS NOT NULL`**, and reports exclude card orders Stripe
  never approved, exactly as the tablet does.
- **The wording.** The tablet and kitchen ticket said "CARD — PAYMENT PROCESSING" for an order Stripe
  had already approved and was holding the money for. Since OI-65 an unapproved card order cannot
  reach the tablet at all, so that state *always* means approved — "processing" read as "we don't
  know yet" about secured money and caused a live scare. Now **`CARD APPROVED — DO NOT COLLECT`**
  naming the held amount, and `*** CARD APPROVED ***` on the ticket.
- **⚠️ THE STRUCTURAL FIX, and the most important line in this entry.** All three incidents in three
  days had the same root cause: the "is this order real" rule written in one place and not the
  others. It now lives **once**, in **`backend/app/services/order_visibility.py`**
  (`is_real_order()` / `money_actually_taken()`), imported by the queue, the reports and the prepaid
  split. **Do not re-express it inline** — that is exactly what this module is named after.
- Verified after deploy: reports £98.96 = payments table £98.96 (revenue derived from orders now
  reconciles against money actually recorded), both kitchen tickets `*** PAID ONLINE ***`, live
  tablet chunk carries `CARD APPROVED` with **zero** occurrences of `PAYMENT PROCESSING`.

---

**OI-65 🟢 SHIPPED + VERIFIED LIVE (`a7da2fb` → `d3d1e7d`, 2026-08-04).** Detail below kept in full.
⚠️ **The first attempt (`a7da2fb`) was a workaround Malik rejected** — it gated only
`state="pending"` and papered over the still-open "All" tab with a "Waiting for the customer's card
payment" panel. His words: *"'waiting for customer's card payment' is exactly what we dont want to
show in POS?? why are u putting in temporary hacks? i need this fixed clinically."* Corrected in
`d3d1e7d`: the gate applies to **every** queue state, the tablet files were reverted byte-identical
to `1f55cf1`, and `awaiting_card_payment` was removed. **Lesson: when a rule is bypassed through an
ungated view, close the view — never dress the hole up in the UI.**

<details><summary>Original OI-65 writeup (accurate, kept for the incident record)</summary>

**OI-65 — the OI-61 card-payment gate was bypassed in production within a day — the OI-61 card-payment gate was bypassed in
production within a day (Imran screenshot via Malik, 2026-08-03).** Order `260803-003` (Leanne
Sharkey, £15.69, delivery/Garelochhead) showed "CARD — PAYMENT PROCESSING" while already accepted
and offering "Out for delivery".

**What the evidence actually showed** (production DB + audit trail + live Stripe API, all
re-verified this session, not taken from prose):

| Time (UTC 2026-08-03) | Event |
|---|---|
| 17:04:51.8 | order placed |
| 17:04:52.1 | Stripe Checkout session created (`cs_live_b11N…`) |
| **17:07:25.6** | **staff Accept** — 2m34s in, unauthorised, inside the 5-min grace |
| 17:10:57 | customer finally submitted card details; Stripe created the PaymentIntent |
| 17:11:01.5 | authorisation landed → `reconcile_late_authorization` fired |
| 17:11:02.9 | late capture succeeded, £15.69 taken |

**Money position: clean.** 16 card orders 02–03 Aug ↔ 16 live Stripe PaymentIntents, 1:1, every one
`succeeded` with `amount_received == amount`. Zero uncaptured, zero dangling authorisations, zero
orphan charges. No customer was double-charged. (Stripe cannot see the shop's own card terminal, so
a manual in-shop re-charge would not appear — but the tablet showed the amber "CARD — PAYMENT
PROCESSING" banner, not red "NOT PAID — COLLECT", so OI-61's *secondary* safety net did hold. That
is why this surfaced as Imran asking a question rather than as a second double-charge.)

**Two defects, not one:**
1. **The gate was a query filter, not an invariant.** It applied only to
   `list_merchant_orders(state="pending")`. `OnlineOrdersPage.tsx` renders Accept/Reject for *any*
   order with no `accepted_at`/`rejected_at` on **every** tab, and the "All" tab is ungated — that is
   the tab in Imran's screenshot. `accept_order` had no server-side guard at all; it explicitly
   commented "fall through and accept it like any other unpaid order". Tablet-staleness is ruled out:
   the session id was set 311ms after order creation and Accept came ~15 poll cycles later.
2. **The 5-minute grace window would have failed anyway.** It would have released this order at
   17:09:51 — still 70s before Stripe authorised. It had been calibrated on one day's sample (worst
   gap 179s on 08-02) and was exceeded the next day (366s).

**Why the tests didn't catch it:** all four OI-61 gate tests called `list_merchant_orders(state=
"pending")`. Nothing tested that Accept itself refuses, and nothing tested `state="all"`. The suite
exercised exactly the one path that was fixed. STATE.md's "the structural fix, so staff can no
longer act on money that isn't confirmed yet" was overstated — corrected there.

**⚠️ Note against OI-62.** OI-62 item 1 records Malik's original ask ("don't show a card order to
staff at all until Stripe's checkout fully succeeds") and asserts "the 'don't show until confirmed'
half is exactly what OI-61 already built". That was **not accurate** — OI-61 shipped it with a
5-minute escape hatch and no server-side enforcement. OI-65 is what actually builds it. The
retry/embedded-Elements half of OI-62 remains genuinely unbuilt and untouched.

**Malik's rule, which OI-65 implements literally** (his words, 2026-08-03/04): *"our card orders
should not land in POS if the payment has not been processed… even if the customer takes 2 hrs…
order becomes visible after the payment is processed"*, and *"cash on delivery orders land as it is —
there's no payment to process. card orders land after the payment has been approved by stripe."*
Flow: customer places order → Stripe checkout → **approved by Stripe** → customer gets the "order
received" email → order lands on the tablet → kitchen accepts → payment captured → ticket prints.

**What was built:**
- **Hard gate, no timeout.** `PENDING_QUEUE_PAYMENT_GRACE` deleted. A card order is published when
  `payment_authorized_at` is set and never otherwise. An abandoned checkout is never surfaced — nobody
  paid, so there is nothing to cook. Cash/COD has no checkout session and is completely unaffected.
- **The invariant: a server-side guard in `accept_order`.** Refuses any card order whose money Stripe
  has not confirmed, by any route — All tab, stale render, or direct API call. New
  `CardPaymentNotConfirmed(PublicOrderError)` so the tablet can explain rather than show an error.
  Also refuses when Stripe *cannot be reached*: unable-to-confirm is not confirmed. Refusing is
  recoverable; cooking against an unverified payment is not.
- **`stripe_service.authorization_for_session()`** — returns `(intent_id, is_authorized)` from one
  expanded round trip, keyed on PaymentIntent **status** (`requires_capture`/`succeeded`), not on the
  intent merely existing. An intent existing only proves the customer *started* paying (they may be
  on the 3-D Secure step, or Stripe may be `processing`); gating on the id would reintroduce the same
  failure one step later.
- **`publish_authorized_card_orders()` — the piece that makes "no timeout" safe.** Removing the grace
  made publication depend entirely on one webhook delivery; a dropped `amount_capturable_updated`
  would mean a customer charged and an order the shop never sees, with no expiry to save it — worse
  than the bug being fixed. So the queue re-derives authorisations straight from Stripe on every poll.
  Bounded (8 orders, <24h old), concurrent, and every Stripe failure swallowed after logging: a Stripe
  outage must never take down the queue the shop's **cash** orders also arrive through.
- **Publication claim is an atomic conditional UPDATE** (`WHERE payment_authorized_at IS NULL`), not a
  Python read-then-write. Three things can publish the same order within milliseconds — the webhook
  and the tablet's two independent 10s polls (`refresh`, `checkForNewOrders`) — and a read-then-write
  would let two of them both "win" and send the customer two "order received" emails.
- **The "order received" email moved to the authorisation moment.** It used to fire inside
  `POST /orders`, before the customer had even reached Stripe. With a hard gate that becomes a lie:
  the shop never sees the order, so it promises food to exactly the customer who then abandons
  payment. It now renders *"Card details taken. We only charge you once the shop accepts your
  order."* Cash on delivery still emails immediately, unchanged. An order already answered gets its
  "accepted" email instead of a duplicate "received".
- **The gate applies to EVERY queue state — pending, active and all.** ⚠️ This session's first
  attempt (`a7da2fb`) scoped it to `pending` only, inheriting OI-61's exact scoping mistake, and then
  papered over the resulting hole by replacing the tablet's Accept/Reject buttons with a "Waiting for
  the customer's card payment" panel on the All tab. **Malik rejected that, correctly**: he never
  asked for the Accept button to change, and a "waiting for card payment" row in the POS is precisely
  what the rule exists to prevent. Corrected in `d3d1e7d`. **The generalisable lesson: when a rule is
  bypassed through an ungated view, close the view — do not dress the hole up in the UI.**
- **Tablet: NO CHANGE AT ALL.** `OnlineOrdersPage.tsx` and `onlineOrdersApi.ts` are byte-identical to
  `1f55cf1` (proven by Vite content hash — the live chunk is `OnlineOrdersPage-bINTpwNa.js`, the same
  one that was live before this session). No new tablet state, no new copy, nothing for staff to
  learn. The `awaiting_card_payment` field existed only to drive that panel and was removed rather
  than left as dead API surface.
- **One deliberate exception to the gate:** an order that has already been *answered* stays visible,
  because hiding an order the kitchen is already cooking would be worse than showing it and the log
  must stay legible. Only reachable for rows answered before this shipped — `accept_order` now
  refuses unconfirmed card orders. Verified **zero such rows** in production.

**Verification done:** backend **496 passed** (baseline 485 + 11 new), failure list **byte-identical**
to clean-HEAD `1f55cf1` via a throwaway `git worktree` — 21 pre-existing failures + 2 errors, zero
regressions (the two date-filter failures in `test_public_tenant_routing.py` reproduce at clean HEAD;
they are the known OI-59/OI-63 SQLite `func.cast` family). `ruff` clean on all touched files (the
repo-wide count rises 85→93 only because of untracked `app/scripts/seed_demo_kitchen.py`, which does
not exist at HEAD and is not this session's work). `tsc --noEmit -p tsconfig.app.json` + `vite build`
clean. **Proven end-to-end against the live database with a temporary probe order** (then deleted and
confirmed gone): an unpaid card order was invisible in **all three** states, and became visible in
pending and all the instant `payment_authorized_at` was set — behavioural proof, not a code reading.
**`authorization_for_session` verified against the real live Stripe API**, not just mocks — the exact
`field()` subscript path (the accessor whose own docstring warns that `StripeObject` has no `.get()`)
returns a real `PaymentIntent` with working `id`/`status`, and missing keys degrade to `None`.

**Residual, stated honestly:** the *negative* case (an unpaid session returning not-authorised) is
covered by unit tests and is safe by construction — the gate keys off PaymentIntent status, and
`requires_capture`/`succeeded` *are* Stripe's statement that money is held — but it was not exercised
against a real unpaid live session, because all 17 live sessions are `complete`/`paid` and
manufacturing one means creating a session on the client's live Stripe account. Offered to Malik as
an explicit option rather than done unilaterally.

**✅ DEPLOYED AND VERIFIED LIVE**, commits `a7da2fb` (fix) + `93876b1` (removed two stale comment
references to the now-deleted grace constant — caught only because the post-deploy container grep
returned 1 instead of 0, which is exactly why that check exists). Deployed 2026-08-03 ~23:15 UK,
after the 22:00 close, so no live order was in flight. Verified beyond the green Action by reading
the new symbols **out of the running application object** and by smoke-testing
`publish_authorized_card_orders` / both queue states against **real production data** — see STATE.md
for the full evidence list. **Next: Imran/Malik's UAT on tomorrow's real card orders.**

Original file list (8 code files; STATE.md and this file went in the same commit):
`backend/app/{api/v1/public.py,schemas/public_order.py,services/public_order_service.py,services/stripe_service.py}`,
`backend/tests/{test_stripe_payments.py,test_public_tenant_routing.py}`,
`frontend/src/{pages/online-orders/OnlineOrdersPage.tsx,services/onlineOrdersApi.ts}`.
Backend-only + tablet — **no `storefront/` changes, so `git push` alone ships it**; no Cloudflare
deploy needed this time. ⚠️ Commit by explicit filename: the tree also carries unrelated uncommitted
work (`QUICKBOOKS_PLAYBOOK.md`, `StaffManagementPage.tsx`, untracked `seed_demo_kitchen.py`, and the
~119-file doc reorg) that must NOT be swept in.

</details>

**⚠️ Standing note for the whole OI-61 → OI-65 → OI-66 → OI-68 chain.** Four incidents, three days,
one root cause each time: a rule expressed in one place and not the others (the pending query but not
All; the queue but not the reports; the counter but not the letter). Before adding any rule about
what counts as a real/valid/payable order, check whether
`backend/app/services/order_visibility.py` should own it.

---

**OI-64 🔵 NEW, NOT BUILT — Imran feedback, 2026-08-03 (text via Malik, same day as OI-61/62/63,
while the OI-61 stress-test plan is being run separately).** Two asks:
1. **Show delivery last-order cut-off times on the website itself.** Right now `SHOP.deliveryCloseTime`
   (21:30) and `DeliveryArea.closeTime` (Garelochhead 21:45, `storefront/src/data/menu.ts`) only
   surface *reactively* — the pre-order banner (`Checkout.tsx`/`OrderConfirmation.tsx`) only mentions
   a cut-off once a customer is already past it. There is no static "last orders for delivery: X"
   copy anywhere a browsing customer would see it upfront. The only existing hours string at all is
   `Checkout.tsx:458`, "Open daily {openTime}–{closeTime}." — general shop hours, not delivery-specific,
   and only shown at checkout, not the homepage. Small, well-scoped frontend-only display change once
   picked up — no backend/DB involved, values already exist in config.
2. **Delivery gets its own earliest window: 16:30. Collection stays at 16:00.** Resolved by Malik
   asking Imran directly (WhatsApp, 2026-08-03 14:12–14:13): "pre-orders delivery starts from 16:30 -
   what about collection orders? do they start from 16:00 or 16:30" → Imran: **"Collections 16:00"**.
   Confirms this is NOT the `// INFERRED — confirm` `SHOP.openTime` value moving — `openTime` (16:00)
   stays correct for collection. This is a genuinely new, delivery-specific early-side concept that
   doesn't exist in the code yet: `delivery.ts`'s `orderTiming()` already has a delivery-specific LATE
   cutoff (`deliveryCloseTimeFor`/`SHOP.deliveryCloseTime`) but no EARLY one — right now collection and
   delivery share one single `from` threshold (`orderFromTime`/`openTime`). Needs a new
   `SHOP.deliveryOpenTime = "16:30"` plus a new `closedReason` (e.g. `"delivery_not_open_yet"`) so a
   delivery order placed between 14:00–16:30 is correctly labelled a pre-order with "delivery opens at
   16:30" messaging, while an identical collection order in that same window still reads as immediate,
   unchanged. **Building now** — parallel stress-test session wrapped up, storefront files are clear.

---

**OI-62 🔵 NOT BUILT, needs discussion (session S, 2026-08-03).** Two ideas raised while fixing OI-61,
deliberately not built tonight — see git history / this conversation for full reasoning:
1. **Malik's suggestion:** don't show a card order to staff at all until Stripe's checkout fully
   succeeds, with 3-4 retry attempts then a cash-on-delivery fallback. The "don't show until
   confirmed" half is exactly what OI-61 already built (the pending-queue gate). The retry/fallback
   half needs replacing Stripe's hosted Checkout redirect with embedded Stripe Elements for enough
   control over the retry UX — a real, multi-day integration change, not safe to rush on a live
   payments system under the same night's time pressure. Worth scoping properly later if wanted.
2. **Imran's suggestion (voice note 2026-08-03):** a manual on/off toggle so staff can temporarily
   stop taking online orders (too busy, closed unexpectedly). He explicitly asked for advice rather
   than directing a build. Straightforward if wanted: an `accepting_orders` bool on
   `restaurant_configs`, checked by the storefront's ordering-eligibility check alongside the
   existing hours logic, with a button on `OnlineOrdersPage`.

**OI-63 🔵 FOUND, NOT FIXED — pre-existing, unrelated to OI-61 (session S, 2026-08-03).** 13 backend
test failures exist independent of anything built tonight (confirmed via a clean git-stash
comparison before touching any code): `test_online_reports.py` (9 — prepaid-vs-COD, rejected-orders,
Stripe-reconciliation all return empty/zero for orders that should match a "today" date-range query,
in `online_report_service.py`), `test_public_tenant_routing.py` (2 — same shape, a 3-days-ago order
not found by an explicit `date`/`date_from`/`date_to` query), plus the 2 already-documented
session-O failures (`test_p1a_features`, `test_pay_first`). The first 11 look like the same root
cause (a date-boundary/timezone issue distinct from the already-known `func.cast(..., Date)` SQLite
bug, OI-59) but were not investigated further — out of scope for an urgent live-payments fix. Backend
suite: 476 passed / 13 failed with all of OI-61 built, same 13 with none of it — zero new regressions.

---

**OI-61 ✅ BUILT, TESTED, DEPLOYED AND VERIFIED LIVE (session S, 2026-08-03), commit `f06979f`.**
Structural fix (card orders now hidden from the pending decision queue until Stripe authorises, or a
5-minute grace window passes) + defense-in-depth (ticket poll-diff invalidation, 3-state card/cash
badge on the tablet, "accepted" email re-sent on late capture, `_payment_status_text` keyed off
`stripe_checkout_session_id` not `stripe_payment_intent_id`). Also shipped in the same commit: 70p
service fee (all orders, separate line, Chick Shack only), dip-tub modifiers consolidated into one
section before the cook list, ZReportPage currency-on-direct-landing fix.
476 passing, 18 new tests, 13 pre-existing failures confirmed unrelated (clean-HEAD comparison
before touching anything). `pg_dump` backup taken first (`pre_oi61_20260803_045556.dump`).
**Verified beyond the green Action**: backend commit hash matches on the server, migration applied
(`orders.service_fee`/`restaurant_configs.service_fee` exist, Chick Shack backfilled to 70), new code
grepped directly out of the running container (`PENDING_QUEUE_PAYMENT_GRACE`, `DIP_TUB_SUFFIX`,
`CARD PROCESSING`, `is_card_order`), tablet frontend bundle byte-identical to the local build, and the
storefront bundle (Cloudflare, separate pipeline) also byte-identical and containing the new "Service
Fee" checkout line. **Original incident, for reference:** Imran reported (voice notes, 2026-08-02/03)
that a card-paid customer's ticket and confirmation email both said NOT PAID/collect cash because
they were built from the payment state at Accept time; staff took payment again on the shop's own
card machine and Imran had to refund it. Checked against production before fixing: 6 of 11 card
orders that day (55%) hit the same race between Accept and Stripe's authorisation landing.

<details><summary>Original diagnosis, kept for reference</summary>

Imran reported
(voice note, 2026-08-02 21:51): kitchen ticket prints "not paid" after Accept on card orders, and the
customer's own email says "collect cash on delivery" despite paying by card at checkout. Confirmed
with photo evidence (order `260802-004`, Allan Scott, £34.95) cross-checked against Stripe's dashboard
(payment Succeeded, same PaymentIntent id in the metadata) and the production DB directly.

- **Root cause, confirmed against real data, not guessed.** `260802-004`: `created_at` 16:25:56,
  `accepted_at` 16:26:09 (staff accepted in 13s), `payment_authorized_at` 16:26:21 (card 3DS/bank
  round-trip landed 12s *after* Accept), `payment_captured_at` 16:26:24. Audit log confirms:
  `stripe_captured — "Captured 3495 for 260802-004 via a late-arriving authorisation (order was
  already accepted)"` — this is `reconcile_late_authorization()` (built session Q, `dfc88e9`,
  2026-08-02), the exact race-window mechanism designed for this. **The money side works correctly —
  `payment_status` does end up `paid`, capture is real, nothing lost.** But two customer/staff-facing
  artifacts are generated using the payment state *at Accept time* (still unpaid, because the card
  hadn't finished authorising yet) and **nothing re-corrects them once the late capture lands a few
  seconds later**:
  1. **Kitchen ticket** — `OnlineOrdersPage.tsx`'s `invalidateTicket(order.id)` is called from exactly
     three places: `onAccept`, and cash/mark-paid handover (`runLifecycle`). All three are
     client-initiated actions. There is **no call anywhere** tied to a server-side/webhook-driven
     payment change, so a ticket invalidated right after Accept (correctly "NOT PAID" at that instant)
     is never invalidated again when `reconcile_late_authorization` captures the payment 5-180s later.
     Print sends the stale cached URL.
  2. **"Accepted" customer email** — `accept_online_order` (`public.py`) calls
     `notify_customer(..., "accepted")` synchronously right after `accept_order()` returns. In the race
     case `accept_order()` never captured (intent didn't exist yet), so `_payment_status_text()`
     (`email_service.py:138`) falls to `"Payable on {collection/delivery}."`. `reconcile_late_authorization`
     never re-sends or corrects this email once payment_status flips to `paid`.
- **Scope, not a rare edge case: 6 of 11 card orders today (55%) raced** (`payment_authorized_at >
  accepted_at`) — `260802-002` (+89s), `-003` (+179s), `-004` (+12s), `-008` (+5.5s), `-009` (+16s),
  `-012` (+29s). Staff tap Accept fast; Stripe's own authorisation (3DS/bank confirmation) routinely
  takes longer than that. This will keep happening on close to half of all live card orders until
  fixed, not just occasionally. `260802-011` checked separately and is **not** an instance of this —
  Stripe checkout was opened but abandoned, correctly settled as cash-on-handover via `mark_order_paid`.
- **Fix (two parts, same root cause — reconcile updates the DB but never re-fires the two downstream
  side effects that a normal on-time capture gets for free):**
  1. Ticket: have the tablet's poll loop diff each order's `payment_status`/`payment_captured_at`
     against what it last saw, and call `invalidateTicket(order.id)` on any change — not just on the
     three user-initiated actions. Reuses the existing polling architecture (`OnlineOrdersPage.tsx` has
     no WebSocket for this page, pure poll), no new server event needed.
  2. Email: `reconcile_late_authorization`'s "already accepted, capture now" branch should call
     `notify_customer(db, tenant_id, order, "accepted")` again once the late capture succeeds, so the
     customer gets a corrected email ("Paid by card") instead of the stale one. Needs checking where the
     webhook handler that calls `reconcile_late_authorization` has a `db`/`notify_customer` path
     available (`public.py` webhook route).
  3. **Prevention, general rule for this codebase going forward:** any function that changes
     `payment_status` outside a direct staff tap (i.e. any future webhook-driven reconciliation) must
     re-fire the same "payment changed" side effects a normal synchronous change gets — ticket
     invalidation + customer notification — not just persist to the DB and audit log. Right now that
     wiring exists only for the 3 client-initiated call sites; the async path was missed when it was
     built, and the audit-trail work from session Q didn't close this gap since it wasn't in scope then.
All of the above is now built and deployed — see the summary at the top of this entry.

**Separate ask, same voice notes:** Imran wants a 70p "platform service fee" added to every order
(his own wording: "add it on as platform service fee... that way we can charge the 70 pence") — this
roughly matches Stripe's own processing fee shown on the `260802-004` payment (£0.72). Malik's
decision (2026-08-03): applies to **all orders**, card and cash alike, shown as its own line — now
built and deployed.

</details>

---

**OI-60 🟡 IN PROGRESS (session Q, 2026-08-02) · Production logs vanish on every deploy — fix
backend now, nginx is separate/deferred.** Malik asked to check why yesterday's order-email activity
couldn't be verified, and traced it to this: `backend`, `frontend`, `nginx` are all `read_only: true`
with only `tmpfs` (memory-backed) writable paths, so there is currently **zero persistent place for
logs to live.** `docker logs` reads Docker's own `json-file` log, which is stored per-container-
INSTANCE on the host — when a container is recreated (which `backend` and `nginx` both are, on
**every** `git push origin main` per `docs/DEPLOYMENT_PLAYBOOK.md`), the old instance's log file is
gone with it. This repo deploys multiple times a day, so log retention today is really "since the
last deploy" — sometimes a couple of hours. Confirmed live 2026-08-02: `pos-system-backend-1`,
recreated that afternoon, had exactly 121 log lines total; everything from the day before (including
the email activity Malik asked about) was already gone. Disk is not the constraint — 38GB free/22%
used on the droplet at the time this was checked; memory is the box's usual tight constraint but
file-based logging costs negligible RAM.

**Design (applies to both halves, OI-60a built this way, OI-60b should match unless nginx's specific
mount/user situation forces a difference — re-check, don't assume):**
- **Bind-mount a real host directory**, not a named Docker volume — inspectable directly
  (`tail -f`/`grep`) without going through `docker exec`, matching how this repo already bind-mounts
  nginx config from the host rather than baking it into the image.
- **Plain append-mode `FileHandler`, not a rotating one, inside the app.** `backend` runs
  `--workers 4` (`Dockerfile` CMD) — four separate OS processes. Python's in-process rotating
  handlers (`TimedRotatingFileHandler`/`RotatingFileHandler`) are not safe when multiple *processes*
  share one file: the rotation step itself (rename/reopen) races across processes. Plain append-mode
  writes to one shared file ARE safe across processes on Linux (`O_APPEND` writes are serialized by
  the kernel for ordinary log-line sizes) — so the app only ever appends, and rotation is delegated
  to **host-level `logrotate` with `copytruncate`**, which truncates the file in place rather than
  renaming it, so it needs no cooperation from the four running processes.
- **`posapp`'s container UID pinned to `1000`** in the Dockerfile (previously whatever `useradd -r`
  auto-assigned, non-deterministic) so the host directory's ownership can be set to a known value
  instead of `chmod 777`-ing something the app writes into.
- uvicorn's `--log-config` points at a JSON dictConfig that is **purely additive** to uvicorn's own
  real default config (confirmed by importing `uvicorn.config.LOGGING_CONFIG` from the actual
  installed `uvicorn==0.34.0`, not assumed from memory) — existing console (`docker logs`) output is
  unchanged, a new `file` handler is added to the root logger and to `uvicorn`/`uvicorn.error`/
  `uvicorn.access`. Also fixes a separate, smaller pre-existing gap found while designing this: the
  app has never called `logging.basicConfig()` anywhere, so the root logger had **no handler at
  all** — every `logger.info(...)` call across the codebase (`stripe_service.py`,
  `public_order_service.py`, `email_service.py`, etc. — exactly the kind of line that would have
  answered Malik's email question directly) was going nowhere, silently. Only `WARNING`+ was ever
  visible, via Python's stderr "handler of last resort". The new root-logger config sets `level:
  INFO` with both a console and a file handler, so these were previously invisible even live, not
  just non-persistent.
- Retention: daily rotation, 30 kept, gzip compressed — trivial size at this app's actual volume
  (low tens of MB/month at worst, against 38GB free).

- 🟡 **OI-60a — backend, session Q, PAUSED mid-build 2026-08-02 — all 6 files WRITTEN, NOTHING
  committed/pushed/deployed. Working tree has the uncommitted edits below; resume by reviewing them,
  not by redoing them.**
  - [x] `backend/Dockerfile` — pinned `posapp` UID/GID to 1000 (uncommitted)
  - [x] `backend/logging_config.json` — new file, written (uncommitted, untracked)
  - [x] `backend/scripts/start.sh` — added `--log-config logging_config.json` to the uvicorn invocation (uncommitted)
  - [x] `docker-compose.demo.yml` — bind-mounted `/root/pos-system/logs/backend:/app/logs` into `backend` (uncommitted)
  - [x] `docker/logrotate/pos-backend.conf` — new file, written (uncommitted, untracked)
  - [x] `scripts/deploy-remote.sh` — added idempotent `mkdir -p`/`chown`/logrotate-install step, mirroring
        the existing `voice.conf` pattern (self-healing, not a hard refuse) (uncommitted)
  - [x] **Config correctness spot-checked**, not full-stack tested: loaded `logging_config.json` for
        real via `logging.config.dictConfig()` (not just eyeballed) and fired one log line through each
        of `app.*`, `uvicorn`, `uvicorn.error`, `uvicorn.access` — confirmed exactly one line per call in
        the file output (the `uvicorn.error` duplicate-write bug an earlier draft of this config had —
        handlers on both itself AND its parent `uvicorn` — was caught and fixed here, before it ever
        reached a container). One cosmetic artifact in that same test run: manually firing a bare
        `logger.info()` at `uvicorn.access` (not going through uvicorn's real request-logging code)
        crashed ONLY the console `AccessFormatter` because the hand-built record lacked the 5-tuple args
        uvicorn's own access-log call always supplies — the file handler still wrote its line correctly.
        Believed to be a test-harness artifact, not a real config bug, **but not yet proven** against a
        real request through a real running server.
  - [ ] **NOT done — pick up here:** build the actual `backend/Dockerfile` locally and run it against a
        real Postgres+Redis (`docker-compose.yml`'s local dev stack uses `Dockerfile.dev`, a DIFFERENT
        file — it will NOT exercise these changes; a throwaway `docker run` against real Postgres/Redis
        containers, or a temporary edit to point dev compose at the prod Dockerfile, is needed instead).
        Confirm: image builds clean with the UID pin, `/app/logs/backend.log` actually populates when a
        host directory is mounted, a REAL request through the app produces one correctly-formatted
        `uvicorn.access` file line (resolves the open cosmetic question above), and — most importantly —
        console output (`docker logs`) is unchanged from before this change (regression check).
  - [ ] Not committed, not pushed, not deployed. Do this only after the local test above passes AND
        Malik has separately confirmed commit/push/deploy, same pattern as the Stripe fix this session.
  - [ ] Post-deploy: verify the log file survives a SECOND `backend` recreation, not just that it
        exists once after the first deploy — that's the actual point of this whole exercise.
- [ ] **OI-60b — nginx, deferred, NOT started.** Same shape of problem (nginx is also `read_only:
      true`, also recreated on every deploy, its default image symlinks access/error logs to
      stdout/stderr so it has the identical loss-on-recreation issue) but deliberately **not**
      bundled with OI-60a. nginx is shared with Orbit CRM (`voice.conf` mounted in) and this box has
      **two prior nginx-recreation outages** on record (`memory/server-deployment-rules.md`) — treat
      as an isolated change, own verification pass (`docker inspect pos-system-nginx-1` mounts first,
      then confirm BOTH `eats.sitaratech.info`/`pos-demo.duckdns.org`/`chickshackg84.com` **and**
      `orbit-voice.duckdns.org` after any nginx recreation, per that memory file's mandatory rule).
      Do not assume OI-60a's exact design (UID pin, FileHandler specifics) transfers 1:1 — nginx's
      alpine image's log-writing user/mechanism is different from `posapp` and hasn't been checked
      yet. Re-derive at the start of whichever session picks this up.

---

**Last updated:** 2026-08-01 (session P) — **OI-57 and OI-58 both BUILT, curl-verified against real
local dev Postgres data, committed, pushed and DEPLOYED to production** (commit `55ac6de`, Malik
explicitly said "commit and push" first). Deploy independently verified live — not just a green
Action: server's `git log` matches the commit, all 6 new `/reports/online/*` routes genuinely
registered in the running backend, the live frontend bundle's `OnlineReportsPage` chunk is
byte-identical to the local build, and all 5 new/changed endpoints called for real over
`eats.sitaratech.info` (the actual public domain) came back correct. `tsc`/`vite build`/eslint
clean for `frontend/`; backend suite 470 passed, same pre-existing failures as session O (2 flagged
unrelated, 12 QB-Desktop/parked) plus this session's own 19 new passing tests. Browser
click-through of the UI was **not possible** — Chrome extension still not connecting, consistent
with every session this week — verified via build output + real API calls instead.
**Only Malik's own UAT remains.**

**OI-59 🔵 LOW PRIORITY, NOT SCHEDULED · The backend test suite cannot verify ANY date-ranged
report's actual numbers.** Discovered while building OI-58a's tests, 2026-08-01 (session O) — see
`ERROR_LOG.md` same date for the full root-cause writeup. `report_service.py`/`dashboard_service.py`
filter dates with `func.cast(Order.created_at, Date) >= date_from`; under this suite's in-memory
SQLite DB that CAST returns the leading-digit-run as an INTEGER (e.g. `2026`) rather than a real
date, and SQLite's storage-class ordering makes an INTEGER always compare less than a TEXT date
bound — so the WHERE clause matches **zero rows for any date range, on every report that uses this
pattern** (item performance, hourly breakdown, void report, z-report, payment method report, waiter
performance — grep `func.cast(.*Date)` in both files). Production is unaffected (real Postgres casts
correctly); this is purely a test-harness gap, but it means none of these reports' actual aggregation
math has ever really been verified by `pytest` — every passing test either uses zero orders or never
touches a date filter. Fixing it means switching every one of those call sites to a plain
`Order.created_at >= / <` datetime-range comparison (the pattern OI-58c's new reports already use,
specifically to avoid this). Not scheduled — flagging so it isn't independently rediscovered.

**OI-57 ✅ BUILT + DEPLOYED 2026-08-01 (session P), commit `55ac6de` · Online-orders queue: date filter,
pagination, sort.** Requested 2026-08-01, Malik: *"would need date wise filters, toggle buttons
across pending active all tab - so previous day orders dont reflect in today orders - need
pagination - sorted from most recent to oldest (add a sort button too)."*

**Built exactly per the spec below, all judgment calls kept as documented.** Backend:
`list_merchant_orders` (`public_order_service.py`) now takes `date`/`date_from`/`date_to`/`offset`/
`sort`, using the shop's own timezone (`get_timezone` helper, same fallback-to-UTC pattern as
`print_service._offset_minutes`) to compute local-day bounds; `MerchantQueueResponse` gained
`total_count`/`offset`/`limit`/`sort`. Frontend: `OnlineOrdersPage.tsx` gained a date picker
(Pending/Active), a from/to range (All), pagination controls, and a sort toggle for Active/All —
Pending's FIFO default is untouched, exactly as flagged below. 8 new backend tests (all passing)
reproduce the exact bug (a 3-day-old order polluting today's Pending) and prove it's fixed.
**Curl-verified against the real local dev Postgres DB** (not just pytest): today-with-orders,
today-zero-orders, an explicit past date, a date range on All, page 2 of a paginated result, and
both sort directions — every response hand-checked against the known 7-orders-from-2026-07-28
dataset, matching exactly (5 pending on that date, 7 total, pagination boundaries correct, sort
correctly reversed). `tsc`/`vite build`/eslint clean. **Malik has not yet UAT'd this — do so before
considering it closed**, per his own "confirm only once curl-tested... I will then do UAT" bar.

<details><summary>Original spec (still accurate, kept for reference)</summary>



Current state, confirmed by reading the actual code (not assumed):
- `GET /public/manage/orders` (`backend/app/api/v1/public.py:392`) accepts exactly two query
  params: `state` (pending/active/all) and `limit` (1-200, default 50). **No date filter, no
  offset/cursor, no sort param exist today.**
- `list_merchant_orders` (`backend/app/services/public_order_service.py:806-848`) hardcodes the
  order per state: **pending** = `accepted_at IS NULL AND rejected_at IS NULL`, oldest-first
  (`created_at.asc()`) — deliberately FIFO, "work the queue in the order it arrived." **active** =
  accepted-but-not-finished, newest-first. **all** = every online order ever, newest-first. **None
  of the three branches has any date/time bound in its WHERE clause** — `created_at` is used only
  for ordering, never for scoping to "today."
- Proven concretely in the local dev DB: **7 total online orders exist for chick-shack, all dated
  2026-07-28.** 5 of them are still `confirmed` with no `accepted_at`/`rejected_at` — i.e. today
  (08-01), the Pending tab already shows 3-day-old test orders mixed in, with nothing to age them
  out or separate them from anything genuinely new. This is the exact bug Malik is describing,
  reproducible right now, not a hypothetical future-volume concern.
- `MerchantOrderSummary.placed_at` (`backend/app/schemas/public_order.py:223`) is the timestamp
  field already on the response — use this, don't add a duplicate.

**Scope to build:**
1. **Date scoping.** Pending and Active should default to **today only**, in the shop's local
   timezone (the existing `utc_offset_minutes`/timezone-resolution pattern already used by
   `print_service.py`/`email_service.py` for Chick Shack — reuse it, don't invent a second
   timezone mechanism). Add an explicit date param (`date: date | None` — default today) so staff
   can still look at a specific past day if they need to, and a `date_from`/`date_to` range for the
   "All" tab specifically (it's documented as "a log," so range browsing makes sense there in a way
   it doesn't for a live work queue).
2. **Pagination.** Add `offset` alongside the existing `limit`, and have `MerchantQueueResponse`
   return a `total_count` (or `has_more` boolean) so the frontend can render actual page controls,
   not just silently truncate at 50/200.
3. **Sort.** Add a `sort: "asc" | "desc"` param and a toggle button in `OnlineOrdersPage.tsx`.
   **Judgment call made here, not yet confirmed by Malik — flag this explicitly during the UAT
   walkthrough rather than silently deciding it's obviously right:** Pending's current oldest-first
   FIFO order is a deliberate, already-correct design (you serve the oldest ticket first) and
   should **stay the default** even though Malik's message reads as "sorted from most recent to
   oldest" — that phrasing most likely describes Active/All (the log-style views, where newest-first
   is already the default and just needs a user-facing toggle to flip it), not a request to break
   the queue-work-order for Pending. Build the toggle for Active/All; leave Pending's default alone
   unless Malik says otherwise on UAT.
4. Backend: `list_merchant_orders` (service + route), `MerchantQueueResponse` schema.
5. Frontend: `onlineOrdersApi.ts`'s `listOnlineOrders` signature, a date picker + pagination
   controls + sort toggle in `OnlineOrdersPage.tsx`. Keep the existing "Enable sound"/new-order-watch
   logic untouched — it already runs its own independent `pending`-scoped poll and must keep working
   exactly as it does today regardless of what date/page/sort the visible tab is showing.

**Definition of done (Malik's own bar, don't skip):** curl-test the new endpoint directly with a
real JWT (log in as `imran@chickshackg84.com` or `malik@sitaratech.info` via `POST /auth/login`)
across at least: today with orders, today with zero orders, a past date, a date range on "all,"
page 2 of a paginated result, both sort directions — confirm each response shape and count by hand
against the DB, not just a 200. `tsc`+`vite build`+eslint clean. Only then deploy and confirm to
Malik.

</details>

---

**OI-58 ✅ BUILT + DEPLOYED 2026-08-01 (session P), commit `55ac6de` · Chick Shack reporting: lean branded
reports tab.** Requested 2026-08-01,
Malik: *"the native POS already has reporting - just need to reflect reports/dashboards tab here
as well. Chick Shack headers. lean format. Daily Orders/Sales Report (custom date range) - Prepaid
vs Cash on Delivery Report | Rejected Orders Report | maybe a stripe specific report to
reconcile?"*

**Built exactly in the priority order given below, all four reports.** Mechanism fixed first,
platform-wide: `get_sales_summary` now returns `online_revenue`/`online_orders` (was silently
computed then discarded), `get_live_operations` gained an `online` bucket, and the 3-hardcoded-
channel arrays in `ReportsPage.tsx`/`AdminDashboard.tsx` now include Online — benefits every future
`online_ordering_only` tenant, not just this one. New lean route `/online-orders/reports`
(`OnlineReportsPage.tsx`), styled with the same ink/flame/ember palette as the branded emails, shop
NAME pulled from `useConfigStore` (never hardcoded "Chick Shack") — reachable via a new "Reports"
button on `/online-orders`. Daily Sales reuses the now-fixed `/reports/sales-summary` (+CSV)
directly rather than duplicating it. Prepaid vs Cash-on-Delivery and Rejected Orders are new,
dedicated queries in a new `online_report_service.py`/`online_reports.py` (route prefix
`/reports/online/`), each with its own CSV export. Stripe reconciliation (built last, as flagged
"maybe") added `stripe_service.retrieve_payment_intent` (read-only, never mutates) and reports a
lookup failure as an error row rather than crashing the whole report — confirmed live against local
dev, where Stripe isn't configured, without a 500.

⚠️ **A real, separate bug was found and deliberately NOT fixed here** (out of scope, logged instead):
this project's whole `func.cast(Order.created_at, Date)` date-filter pattern (used by
`get_sales_summary` and every other report in `report_service.py`) is silently unverifiable by the
backend's own pytest suite — see **OI-59** above and `ERROR_LOG.md` 2026-08-01. Production is fine
(real Postgres casts correctly, confirmed by curl against local dev), but the new OI-58c/d report
queries were deliberately written with plain `Order.created_at >= / <` comparisons instead, so they
don't inherit it and stay genuinely tested by pytest, not just structurally.

**Curl-verified against the real local dev Postgres DB**, not just pytest: created a prepaid order,
a cash-on-delivery order and a rejected order, hand-checked every report's numbers against them
(online_revenue/orders, prepaid/cod split, rejected count and reason, Stripe reconciliation's
graceful "not configured" error row), and downloaded + read every CSV's actual content, not just its
status code. 19 new backend tests, all passing (9 in `test_online_channel_reports.py` +
`test_online_reports.py`'s 9, plus 1 more from the fixture change). `tsc`/`vite build`/eslint clean.
Browser click-through of the new page was **not possible** — Chrome extension still won't connect —
verified via the build output and the exact same API calls the page makes instead.
**Malik has not yet UAT'd this — do so before considering it closed.**

<details><summary>Original spec (still accurate, kept for reference)</summary>

**Access is NOT the gap — confirmed by reading the actual routing code.** `online_ordering_only`
(`DashboardPage.tsx:73-75`) only redirects `/` → `/online-orders`; it does not gate `/admin/reports`
in any way (`AdminLayout.tsx` only checks `isAuthenticated` + role, never this flag).
`imran@chickshackg84.com` and `malik@sitaratech.info` are both already seeded as `admin` role
(`seed_chick_shack.py:409-430`) and could log into the existing `/admin/reports` today with zero new
code. **The real gap is that online orders are invisible inside the existing reports, and the
existing reports page is the wrong shape for a single-channel, no-tables, no-waiters tenant.**

Confirmed gaps, by reading `report_service.py`/`zreport_service.py`/`ReportsPage.tsx`/
`AdminDashboard.tsx`/`dashboard_service.py` directly:
- `get_sales_summary` (`report_service.py:15-124`) computes a per-`order_type` breakdown internally
  (`channels` dict, DOES include an `"online"` key for Chick Shack) but then **only reads out
  `dine_in`/`takeaway`/`call_center`** in its return statement — `channels["online"]` is silently
  discarded. `SalesSummary` (`schemas/report.py`) has no `online_revenue`/`online_orders` field.
  The **top-level** `total_revenue`/`total_orders` in the same response is NOT channel-filtered, so
  it already includes online revenue — it just never appears broken out anywhere.
- `ReportsPage.tsx:73-99`'s channel-breakdown card and `AdminDashboard.tsx:453-472`'s live-ops
  columns both **hardcode exactly 3 channels** (dine_in/takeaway/call_center) — an online row would
  not render even if the backend field existed. `dashboard_service.py:114-118` filters online orders
  out of every live-ops bucket entirely.
- `zreport_service.py`'s `by_channel` (`:278-281`) is genuinely channel-agnostic and would already
  show `{"channel": "online", ...}` correctly — worth building the new lean report off this
  function's pattern rather than `get_sales_summary`'s, or fixing `get_sales_summary` to match it.
- **No prepaid-vs-COD report exists anywhere.** Nothing in `report_service.py`/`zreport_service.py`
  references `payment_status`, `stripe_payment_intent_id`, or `service_type`. Needs new logic:
  bucket online orders (excluding `status == 'voided'`, matching the existing void-report
  convention) by whether `stripe_checkout_session_id IS NOT NULL` (prepaid/card) vs `NULL`
  (cash/pay-on-delivery), summed revenue + count each way, for a custom date range.
- **Rejected orders are counted but not reported on directly.** `get_void_report` DOES include
  rejected online orders in its `total_voids`/`total_voided_value` (since `reject_order` sets
  `status = "voided"`), but its `by_reason` breakdown reads `OrderStatusLog.note`, which
  `reject_order` (`public_order_service.py:760-798`) never sets — so every rejected online order
  currently shows "No reason provided" even though the real reason sits on `Order.rejection_reason`,
  right there unread. **Don't try to retrofit the generic void report** — build the "Rejected Orders
  Report" as its own direct query on `Order.rejected_at IS NOT NULL AND rejection_reason` for
  `order_type='online'` in the date range; simpler and correct for what's actually being asked.
  (Optionally also fix `reject_order` to set `OrderStatusLog.note = reason` while in there, so the
  *general* void report stops showing "No reason provided" for online rejections too — small,
  same-mechanism fix, worth doing since it's a two-line change once you're already in that
  function, but the dedicated Rejected Orders Report does not depend on it.)
- **No Stripe reconciliation exists.** Every Stripe call in `stripe_service.py` (582 lines, read in
  full) is single-order, keyed off an ID we already have — no `list()` call anywhere. Malik flagged
  this one with "maybe," so build it **last, and only after the other three are solid** — for a date
  range, pull our own DB's online orders with `stripe_payment_intent_id` set, then
  `PaymentIntent.retrieve` each one individually (NOT a blind account-wide `PaymentIntent.list`,
  which isn't tenant-scoped and would mix in any other Stripe account activity) and diff DB
  `payment_status`/`payment_captured_at` against Stripe's actual `status`/`amount_received`. This is
  the same manual check done by hand for OI-41 tonight, made repeatable.

**Scope to build:**
1. **Fix the mechanism first, platform-wide** (per this project's own established rule — a narrow
   Chick-Shack-only patch would leave the same gap for the next online-ordering tenant): add
   `online_revenue`/`online_orders` to `SalesSummary`, stop discarding `channels.get("online")` in
   `get_sales_summary`, extend the 3-hardcoded-channel arrays in `ReportsPage.tsx`/
   `AdminDashboard.tsx`/`dashboard_service.py` to include online. This benefits the whole platform,
   not just Chick Shack.
2. **A new lean, branded route** — e.g. `/online-orders/reports`, sibling to the existing
   `/online-orders` page, no `AdminLayout` sidebar/dine-in/waiter-performance clutter. Style it with
   the same ink/flame/ember palette already used for Chick Shack's branded emails
   (`tailwind.config.js`), but pull the shop NAME from `restaurant_configs`/config store rather than
   hardcoding the string "Chick Shack" — this tenant won't be the only `online_ordering_only` one
   for long (see [[new-uk-referral-pipeline]] in memory), and the whole point of building it once,
   correctly, is that it should just work for the next one too.
3. Reports to include, in this priority order: (a) Daily Orders/Sales, custom date range — use the
   fixed `online_revenue`/`online_orders` fields; (b) Prepaid vs Cash-on-Delivery — new; (c)
   Rejected Orders — new, dedicated query as described above; (d) Stripe reconciliation — new,
   explicitly lower priority ("maybe"), build last.
4. CSV/download for each, matching the existing `sales-summary/csv` pattern — Malik explicitly
   wants downloaded reports checked for formatting before this is called done.

**Definition of done (Malik's own bar, don't skip):** every new/changed endpoint curl-tested with a
real JWT against real data — verify counts/sums by hand against the DB for at least one date with
known orders. Every downloadable report actually downloaded and opened, formatting checked, not
just "the request returned 200." `tsc`+`vite build`+eslint clean, backend test suite green (new
tests for the new report logic, not just manual curl). Only once ALL of the above is true — Malik's
own words, "2000% done" — confirm back to him. He does UAT after that, not before.

</details>

**Previously, same day (session H/I):** **OI-45(a) and (b) BUILT and deployed to
production**: meal deal modifiers as real Meal products, matching Imran's till exactly. Two
silent rename-related bugs found and fixed during rollout (stale duplicate item, stale
modifier-group links) — see OI-45 and `ERROR_LOG.md`. OI-45(c) turned out to already be built
(stale "not built" note corrected). Storefront testing-mode banner (added earlier 2026-07-30/31)
confirmed still live through both deploys.

**OI-56 ✅ CLOSED 2026-07-31 (session J) · Chunky-chicken source photos integrated.**
Malik approved 15 of 16 photos sourced from chunky-chicken.uk (via `AskUserQuestion`,
2026-07-31 session I), minus one with the competitor's own brand name baked into the image.
This session re-verified every proposed mapping in
`_context/clients/chick-shack-uk/refs/2026-07-31_chunky-chicken-source-photos/CLASSIFICATION.md`
against the actual item `description` strings in `storefront/src/data/menu.ts` before wiring
anything in, per Malik's explicit "make sure products and pictures match, don't want a
screwup." Rejected 6 of the 15 rather than force a weak fit — two for a reason the first-pass
classification had missed entirely: `menuitem-6.jpg` has a genuine Coca-Cola can in frame
(Chick Shack sells Pepsi, not Coke) and `menuitem-8.jpg` has a third-party "Chicken" box with
its own rooster logo, prominent and unmistakably not Chick Shack's packaging. Also rejected:
a text-and-collage composite, a fried-chicken photo that would misrepresent a *grilled* peri
item, a multi-item table spread that isn't a photo of any single product, and a near-duplicate
frame from the same shoot as an image already used. 9 photos used — 4 swapped in place at
existing basenames (`burger-chicken`, `burger-beef`, `wraps`, `wings-spicy`), 5 wired as new
explicit per-item overrides (`burger-double`, `burger-big-shack`, `wrap-hot-chick`,
`kids-popcorn`, `kids-nuggets`). Each cropped separately to 240×180 (thumb, 4:3) and 720×480
(hero, 3:2) via ffmpeg/libwebp — not scaled from one another. The nuggets photo's plain white
cutout background (would show as a stark white patch against the site's dark "ink" theme) was
fixed with a tight crop + soft vignette after a colorkey/chromakey attempt produced ugly dark
fringing around the breading texture. Peri Peri Burger/Wrap and their Double variants keep
inheriting the existing (imperfect — fried-style photo for a grilled item) category fallback,
Malik's explicit call over nulling out 4 items' photos entirely. `tsc --noEmit` clean, deployed
via `cd storefront && npm run deploy` (separate Cloudflare pipeline), and verified against the
**live** site, not the deploy log: fetched the actual hashed JS bundle and confirmed all 5 new
basenames appear in it, then fetched all 9 `/img/thumb/*.webp` and `/img/hero/*.webp` URL pairs
(18 total) and confirmed `200 image/webp` — one (`hero/burger-big-shack.webp`) came back as a
transient `200 text/html` on the first check seconds after deploy, resolved on retry, re-swept
all 18 clean after. Testing-mode banner text and phone number reconfirmed present in the live
bundle post-deploy. Commit `a361fc8`, pushed to `main`.

**Previously, 2026-07-29 (session F):** OI-51…OI-54 all BUILT (three ticket copies, daily
number large, `/orders` Accept + online trimming, per-tenant landing) and a real hole closed
underneath OI-53: the generic transition could cook an online order without accepting it. Same
day (session E): Stripe hardening done except H-6 → **OI-49** (webhook, a dashboard step for
Malik). **OI-55 email egress** resolved 2026-07-30.

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
**Full step-by-step in `_context/clients/chick-shack-uk/EMAIL_SETUP_RUNBOOK.md`.**

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

**OI-45 · Menu items need real modifier prompts. THREE separate asks, do not conflate them.**

✅ **(45a) and (45b) BUILT and DEPLOYED 2026-07-31 (session H/I).** The 2026-07-31 voice note
+ WhatsApp texts + 5 fresh till photos were the QC pass this was parked on — requirement
confirmed stable and byte-identical to the 2026-07-29 walkthrough across both sessions.
Full build record: `_context/clients/chick-shack-uk/voice-notes/2026-07-31_imran_meal-modifiers-and-photos.md`.

**(45c) is ALREADY BUILT** — the "not built" note below is **stale**, left over from
2026-07-29. Verified against actual code 2026-07-31: `EXCLUSIONS` tick-list in
`storefront/src/data/menu.ts` (No Onion/Lettuce/Tomato/Salad/Mayo/Ketchup/Salsa/Algerian
Sauce), offered via `exclusionsFor()` on burgers/wraps/peri-grilled/fried-chicken, travels on
the line's `notes`, prints bold on the ticket. Proven live — a real customer already used it
("no salsa" on 2 double chicken fillet wraps, per Malik's own screenshot).

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

**What actually shipped, 2026-07-31 (commits `0e0b177`, `c6b03b0`, storefront deploy
`e3ea6f27`):** 25 items got a `"<Name> Meal"` sibling product (+£3/variant) carrying the real
drink + upgrade groups; solo items lost the flat tick entirely. `HEAT` renamed/reordered to
match his till ("Peri-Peri Heat" / Hot Heat / Mild Heat). 7 burger/wrap items renamed for
kitchen clarity (Chicken Fillet → Chicken Fillet Burger, etc — item (v) from the 07-31
WhatsApp list). Verified end to end against the **production** API: 87 items, zero duplicate
names, every meal item carries exactly one drink group + the upgrade group.

⚠️ **Two silent bugs found and fixed along the way**, both from the same root cause —
`seed_chick_shack.py` matches by name and only ever ADDS, never removes: renaming an item or a
group's display name doesn't rename the DB row, it creates a duplicate and leaves the old one
(and its item links) live. Fixed with two one-time, idempotent scripts
(`rename_chick_shack_items_2026_07_31.py`, `fix_chick_shack_stale_groups_2026_07_31.py`) that
edit rows in place rather than delete, so no historical order FK breaks. **If anyone renames an
item or a shared group's `name` in `menu.ts` again, run a matching fix before/instead of
relying on a plain reseed** — full write-up in `ERROR_LOG.md`.

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

## 🔴 From Imran's live walkthrough, 2026-07-29 (session E) — build these first

**OI-51 ✅ BUILT 2026-07-29 (session F) · Three copies per accepted order.** The repeat
rides **inside the ESC/POS payload** (`print_service` renders N cut slips; the endpoint
takes `copies`, the tablet asks for 3) — one `rawbt:` navigation, exactly as the item
recommended. Tests assert 3 cuts, 3 bodies, one navigation-sized URL. **Paper not yet
verified on Imran's printer** — that is the next walkthrough's first check.

**OI-52 ✅ BUILT 2026-07-29 (session F) · Daily number large on every copy.** Each slip
now leads with `#NNN` (extracted from the existing `YYMMDD-NNN` — **no new counter was
built**) at double size + bold — the largest size this exact printer has proven on paper —
plus "COPY n OF 3". Verified in the byte stream and preview; paper pending like OI-51.

**OI-53 ✅ BUILT 2026-07-29 (session F) · `/orders` can answer an online order.** Pending
online orders show **Accept** (routes to `/online-orders`, where accept + ETA + capture +
the prefetched print gesture already live — one accept path, not two); online orders drop
the generic Send-to-Kitchen / Pay / Refund / Void and show "Awaiting Accept"; active ones
link to the queue. **Found and closed underneath it:** the generic `confirmed→in_kitchen`
transition would have bypassed accept entirely (no ETA, no Stripe capture, no notification,
no ticket) — the server now refuses it for online orders, tested in both directions.

**OI-54 ✅ BUILT 2026-07-29 (session F) · Per-tenant landing.** New
`restaurant_configs.online_ordering_only` flag: when true the POS lands on
`/online-orders` instead of the three-channel selector. **Per-tenant, not global** —
demo-restaurant keeps the full selector (verified). The migration backfills chick-shack
by slug so **the deploy itself flips production**; the seed also sets it for reseeds.

**OI-55 · ✅ RESOLVED 2026-07-30 — real order delivered, SPF/DKIM/DMARC all PASS.**
Brevo account created, domain authenticated in Cloudflare, `BREVO_API_KEY` deployed to the
server and verified inside the container. One snag along the way: Brevo requires **its own**
DMARC record present to flip `authenticated`, which the runbook hadn't anticipated (its rule
was "never touch DMARC," written before this gate was known) — conflicted with Imran's
existing single `_dmarc` record. Fixed by **editing** that one record's value in place to
`v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com` (same `p=none` policy, zero enforcement
change) rather than adding a second record, which would have broken DMARC entirely. Proof:
order `260729-003`, confirmation email delivered in 2 seconds, Gmail "Show original" shows
SPF PASS, DKIM PASS (`d=chickshackg84.com`), DMARC PASS. Two real test orders
(`260729-002`, `-003`) were placed on the live storefront in the process; voided through the
app's own `reject_order` (not a raw DB delete), DB backed up first each time.
**Original session F build-out below, superseded by the above:**
The egress facts stand (measured from the droplet, session E): SMTP **25/465/587 time out**,
**2525 resets**, **`api.mailjet.com:443` TLS-resets** — and session F measured the regional
variants (`api.eu.mailjet.com`, `api.us.mailjet.com`) dead too, so Mailjet is unusable from
this box in every form. **Do not re-test SMTP ports — settled.**
Session F measured the alternatives **from the droplet**: Resend, Brevo, Postmark, Mailgun,
SendGrid all handshake fine. **Chosen: Brevo** — 300/day free (Resend's 3,000/month is tight
at ~4 emails/order), plain HTTPS JSON API, contract verified against its docs.
**Built and merged:** `BREVO_API_KEY` config (API wins over SMTP when both set — tested),
`email_service._send_via_brevo`, `email_configured` accepts key-only, key declared in
`docker-compose.demo.yml` (two-places rule), 11 new tests including a **strict fake that
refuses what the real API refuses** — mutation-checked by renaming `textContent` and
watching 4 tests fail. Never-fail-an-order guards re-proven for the API path.
**Found and fixed underneath it:** the inline `await` on the send was adding **~15 silent
seconds to every live checkout and tablet tap** while the dead SMTP config sat on the
server — `notify_customer` is now fire-and-forget (tested). See `ERROR_LOG.md` session F.
**Remaining (Malik, ~20 min): `_context/clients/chick-shack-uk/EMAIL_SETUP_RUNBOOK.md`** — rewritten for Brevo:
account, domain auth records in Cloudflare (**additive only, never touch MX/SPF/livemail***),
`BREVO_API_KEY` onto the server env, deploy, **read the value back inside the container**,
then a real order with a real inbox as the only accepted proof.

**OI-50 · The storefront has NO test framework.** `package.json` has dev/build/preview/
type-check/deploy and nothing else. The timezone bug that made the shop read as closed 24/7
and labelled every order a pre-order shipped to real customers and was caught by eye. Any
storefront logic with branches deserves a test; there is nowhere to put one.

---

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
