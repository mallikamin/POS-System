# Stripe hardening — what must be true before a real card is taken

**Written 2026-07-29 (session D).** The integration is built, tested (20 tests) and
**verified against the real sandbox** — authorise, capture, cancel and a declined card all
behave. What follows is the gap list between "works" and "safe to point at real money".

Malik's instruction, verbatim: *"proper security guardrails… we dont want any
unauthenticated errors, api errors… dont want any surprises later on that oh we didnt wire
this or that."*

**Nothing below is speculative.** Each item is a specific thing that is currently unwired,
unverified, or wired in a way that will bite. Ordered by what hurts most.

---

## Status — 2026-07-29 (session E)

**H-1 to H-5 and H-7 to H-10 are DONE. H-6 is the only one left, and it is Malik's to do
in the Stripe dashboard.** Suite is **34 Stripe tests**, up from 20.

| # | State | Proven by |
|---|---|---|
| H-1 | ✅ Fixed | A throwaway nginx was run and **curl'd**, not reasoned about. Stripe's real UA reaches `/`; a bad UA is exempt only on the webhook path; the same bad UA is still dropped elsewhere; `…/webhook/../../evil` is still dropped |
| H-2 | ✅ Fixed | 4 parametrised cases; **mutation-checked** — replacing the guard with `if False:` makes the test fail |
| H-3 | ✅ Fixed | Driven through the real route with a foreign tenant id; **mutation-checked** |
| H-4 | ✅ Fixed | `capture_for_order` — 4 tests (bounded, refuses when the order exceeds the hold, retry is not a second charge, expired hold raises); **mutation-checked** |
| H-5 | ✅ Proven | End-to-end assertion that `payment_status` flips to `paid` **and** one `Payment` row is written with the intent as its reference; **mutation-checked** |
| H-6 | ⏳ **Outstanding — dashboard step** | Code half is done: all six Stripe keys are now declared in `docker-compose.demo.yml` |
| H-7 | ✅ Fixed | `STRIPE_ACCOUNT_CURRENCY`, checked before the session is created |
| H-8 | ✅ Fixed | Now `StripeNotConfigured` → **503**, not 502 |
| H-9 | ✅ Verified | Replicated the real location set in nginx and curl'd it: `/api/v1/public/…` lands in `location /api/`, so the `api_limit` zone (30 r/s, burst 60, 10 conns/IP) does cover it. No regex location steals it |
| H-10 | ✅ Sufficient, pinned | A test replays the same event three times and asserts the timestamp never moves. **No ledger, deliberately** — see the note on H-10 below |

> ⚠️ **Found while doing H-6:** the backend service in `docker-compose.demo.yml` declared
> **none** of the Stripe keys. The keys would have been written to the server env file and
> **never reached the container** — card silently not on offer, deploy green. Exactly the
> failure written up in `ERROR_LOG.md` for the email keys, six days after that lesson. All
> six are now declared.

**Still true and still blocking real money:** none of this is deployed, the webhook is not
registered (H-6), and `cardPaymentEnabled` is still `false`. The test plan at the bottom of
this file has not been run.

---

## 🔴 Blocking — do not enable card payment until these are done

### H-1 · nginx's bot filter may silently eat every Stripe webhook ✅
`nginx.demo.conf` blocks bad-bot user agents **at server level, above every location
including `/api/`**, returning `444`. Stripe calls webhooks with a UA of roughly
`Stripe/1.0 (+https://stripe.com/docs/webhooks)`.

**If that pattern matches, every webhook is dropped and Stripe retries for days while we
see nothing.** This is exactly the class of failure this project keeps hitting — a green
deploy and a silently dead path.

**Do:** read the actual bad-bot regex in `docker/nginx/nginx.demo.conf`, confirm `Stripe/`
does not match, and add an explicit allow for the webhook location if there is any doubt.
Then verify with a real event from the Stripe dashboard's "Send test webhook", not by
reasoning about the regex.

**✅ Done (session E).** The regex was read *and* the behaviour was executed: the real maps
were lifted out of `nginx.demo.conf` into a throwaway nginx and curl'd.

- Stripe's current UA, `Stripe/1.0 (+https://stripe.com/docs/webhooks)`, is **not** blocked
  today — `webhooks` contains no `bot`. Confirmed by request, not by squinting.
- It was one word away from being blocked. The second pattern blocks the bare substring
  `bot`, so a future `Stripe/2.0 (+…) bot` would have silently killed every webhook.
- **A location block cannot fix this.** The `if` is at *server* level and runs in the
  rewrite phase, before a location is chosen. The exemption therefore has to live in the
  map, which is where it now is: `$is_machine_callback` → `$block_bad_bot`.
- Matched on **`$uri`, not `$request_uri`** — the raw form would let
  `/api/v1/public/stripe/webhook/../../anything` slip past the bot filter for a different
  path. Verified: that request is still dropped.
- The exemption removes the **user-agent** check on one path only. Rate limiting still
  applies (H-9) and the signature check still fails closed. The bot filter was never what
  protected this endpoint.

**Still to do at go-live:** send a real test event from the Stripe dashboard once H-6 is
done. The local proof covers nginx; only a real delivery covers the whole chain.

### H-2 · No `livemode` check — a test event can drive production ✅
`stripe_service.verify_webhook` proves an event came from Stripe. It does **not** prove it
came from the *right mode*. Anyone can point a **test-mode** webhook at the production
endpoint; the signature is different per endpoint secret, so this is low risk, but the
assertion costs one line and removes the question entirely.

**Do:** assert `event["livemode"]` matches `STRIPE_SECRET_KEY.startswith("sk_live_")`.
Reject with 400 on mismatch and log loudly.

**✅ Done (session E).** The check lives *inside* `verify_webhook`, not in the route, so it
cannot be forgotten by a future caller. `StripeError` there already maps to 400. Four
parametrised cases cover both matching modes and both mismatches.

### H-3 · The webhook resolves an order without checking the tenant ✅
`public.stripe_webhook` does `db.get(Order, order_id)` using the id from event metadata.
Every other route in that file is scrupulously tenant-scoped; this one is not. The metadata
also carries `tenant_id`, so the check is free.

**Do:** compare `order.tenant_id` against the event's `tenant_id` metadata and ignore the
event on mismatch.

**✅ Done (session E).** `tenant_id_from_event()` added alongside `order_id_from_event()`;
the route ignores a mismatch and returns 200 so Stripe does not retry forever. An event
carrying **no** tenant metadata is still accepted -- older intents predate the field, and
failing those would be a regression, not a guard. Tested through the real route.

### H-4 · Capture is not bounded by the current order total ✅
`accept_order` calls `stripe_service.capture(intent_id)` with **no amount**, which captures
the full authorised amount. If the order is edited downward between authorisation and
acceptance, **the customer is charged the original, higher amount.**

**Do:** capture `min(order.total, amount_capturable)` via `amount_to_capture`. Stripe
releases the remainder automatically on a partial capture (confirmed in their docs). Refuse
to capture and surface an error if `order.total` is **greater** than `amount_capturable`,
because that is undercharging in the shop's favour and must be a human decision.

**✅ Done (session E).** New `stripe_service.capture_for_order(intent_id, order_total)`,
which reads the intent back before deciding. Four outcomes, all tested: already `succeeded`
is a no-op (a retried Accept tap is not a second charge); nothing capturable raises with
the expiry explained; total above the hold **refuses** rather than quietly undercharging;
otherwise it captures the order total exactly. `accept_order` now calls this instead of the
unbounded `capture()`.

### H-5 · `payment_status` may not actually flip to `paid` ✅
`_record_card_payment` writes a `Payment` row through `payment_service.create_payment`,
which is the right route. **Not yet verified** that this flips `orders.payment_status` to
`paid` for an online order. If it does not, the tablet keeps showing its loud unpaid banner
on an order that has been charged, and staff will chase money they already have.

**Do:** assert it in a test, end to end, not by reading the code.

**✅ Done (session E).** It does flip -- but that is now asserted, not read. The test accepts
a card order and then re-reads from the database: `payment_status == "paid"`, exactly one
`Payment` row, the right amount, and the PaymentIntent id as its reference so the row is
traceable back to Stripe. **Mutation-checked**: stubbing `_record_card_payment` out makes it
fail, so the test is load-bearing rather than decorative.

---

## 🟠 Before go-live, not before testing

### H-6 · The webhook is not registered and has no secret
`STRIPE_WEBHOOK_SECRET` is unset everywhere, so the endpoint currently **refuses everything**
— which is the correct fail-closed behaviour, but means nothing arrives.

**Do:** register `https://eats.sitaratech.info/api/v1/public/stripe/webhook` in the Stripe
dashboard, subscribe to `payment_intent.succeeded`, `payment_intent.canceled`,
`payment_intent.payment_failed`, `payment_intent.amount_capturable_updated`, then put the
signing secret in the server env **and declare it in `docker-compose.demo.yml`** — see the
2026-07-29 ERROR_LOG entry, an env key not named in the compose `environment:` list never
reaches the container.

**⏳ Half done (session E).** The **code half is complete** — all six keys
(`STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`,
`STRIPE_SUCCESS_URL`, `STRIPE_CANCEL_URL`, `STRIPE_ACCOUNT_CURRENCY`) are now declared in
the backend's `environment:` list, each with a default that leaves the feature cleanly off
when unset.

> ⚠️ **They were not declared at all before this.** Writing them to the server env file would
> have done **nothing**: card silently not on offer, deploy green, no error anywhere. That is
> the same failure as the email keys on 2026-07-29, and it was still latent six days later —
> which says the lesson needed to be *in the compose file*, not only in the error log.

**The remaining half is Malik's, in order:**

1. In the Stripe dashboard (**sandbox first**), add the endpoint above and subscribe to the
   four events.
2. Copy the signing secret (`whsec_…`) — **never paste it into chat.**
3. Append it to the server env file **and** the other five keys, after a timestamped backup.
4. Deploy, then **read the values back from inside the running container**, not from the
   file that was written. A printed value that happens to equal the code default is exactly
   what an unset variable looks like.
5. Send a test event from the dashboard. That is what actually proves H-1 end to end.

### H-7 · Currency is never checked against the Stripe account ✅
The account is GBP. `create_checkout_session` passes the *tenant's* configured currency. A
tenant misconfigured to PKR would fail at Stripe with a confusing error at the worst
possible moment.

**Do:** validate the tenant currency is GBP (or the account's default) before creating the
session, and fail with a clear internal error rather than a Stripe one.

**✅ Done (session E).** New `STRIPE_ACCOUNT_CURRENCY` setting, default `gbp`, checked
before the session is created. **Not** derived by an API call to Stripe on purpose: that
would put a network round trip in front of every checkout and add a way for checkout to fail
that has nothing to do with the payment. Raises `StripeNotConfigured`, so the customer sees
"card payment is not available" (503) rather than a Stripe error on the payment page.

### H-8 · Unset return URLs surface as a 502 ✅
`STRIPE_SUCCESS_URL` / `STRIPE_CANCEL_URL` unset raises `StripeError` → **502 Bad Gateway**,
which reads as "our server is broken" when it is really "not configured". Should be the same
**503 "card payment is not available"** the missing-key path returns.

### H-9 · Rate limiting on an unauthenticated endpoint that calls a paid API ✅
`POST /public/{tenant}/orders/{id}/checkout-session` needs no auth. The order id is an
unguessable UUID4 and the Stripe call is idempotent per order, so abuse is bounded — but it
is still an anonymous endpoint that makes an outbound API call.

**Do:** confirm the nginx `/api/` rate limit zone actually covers `/public/`, and that the
limit is sane for a shop's traffic.

**✅ Verified (session E), by request rather than by reading.** The real location set was
replicated in a throwaway nginx and curl'd: `/api/v1/public/stripe/webhook` and
`/api/v1/public/<shop>/orders` both resolve to `location /api/`, so they are covered by
`api_limit` -- **30 r/s, burst 60, 10 connections per IP**. That is far above a takeaway's
real traffic and far below anything that would cost money in Stripe calls. The regex
scanner-block location, which would otherwise take precedence over a prefix location,
matches none of these paths.

### H-10 · No event-id ledger ✅
Duplicate webhook deliveries are currently handled by **every branch being a no-op when the
state already matches**, which is genuinely idempotent for the events handled today. It stops
being sufficient the moment a branch does something non-idempotent (writing a Payment row,
sending an email).

**Do:** if any such branch is added, log processed `event["id"]`s and skip repeats. Stripe
explicitly warns events can arrive more than once.

**✅ Sufficient as-is, and now pinned (session E).** A test delivers the same event three
times through the route and asserts `payment_captured_at` never moves. **No ledger was
added** -- it would be infrastructure guarding a property the code already has, and unused
guards rot.

🔺 **The trigger to revisit this is specific:** the moment any webhook branch does something
non-idempotent -- writes a `Payment` row, sends an email, fires a kitchen ticket -- the
replay test stops being sufficient and the event-id ledger becomes necessary. The test's
docstring says so, next to the code that would change.

---

## ✅ Already correct — do not "fix" these

- **Amounts are never taken from the client.** Every figure is recomputed server-side from
  the database, and the Stripe basket is summed and checked against `order.total`, falling
  back to a single line for the exact total if they ever disagree.
- **Integer minor units throughout.** No float touches money anywhere in this path.
- **The webhook verifies its signature before trusting the body**, and **fails closed** when
  no secret is configured.
- **Accept blocks on a Stripe failure; reject does not.** Deliberate and tested — the first
  stops food being cooked unpaid, the second stops the shop being trapped.
- **A capture writes a `Payment` row in a SAVEPOINT**, so bookkeeping failure cannot undo a
  capture that already took the customer's money.
- **The whole feature is inert without a secret key** — no key means card is not offered and
  the shop keeps taking cash on handover. That is production's current state.
- **A rejected order is never charged**, so there is no refund path by design. If you find
  yourself adding one, check whether the charge has drifted back to placement.

---

## Test plan before real money

1. Sandbox end to end **through the storefront**, not just the API: place → pay with
   `4242 4242 4242 4242` → accept on the tablet → confirm captured in Stripe.
2. Reject path: place → pay → reject → confirm the intent shows `canceled` and
   `amount_received` is 0.
3. Declined card `4000 0000 0000 0002` → the order must remain placeable/unpaid, not wedged.
4. A real webhook delivered and processed (H-1 is what this proves).
5. Only then swap sandbox keys for live keys, and re-run 1 and 2 with a real card for a
   small amount.
