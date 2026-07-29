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

## 🔴 Blocking — do not enable card payment until these are done

### H-1 · nginx's bot filter may silently eat every Stripe webhook
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

### H-2 · No `livemode` check — a test event can drive production
`stripe_service.verify_webhook` proves an event came from Stripe. It does **not** prove it
came from the *right mode*. Anyone can point a **test-mode** webhook at the production
endpoint; the signature is different per endpoint secret, so this is low risk, but the
assertion costs one line and removes the question entirely.

**Do:** assert `event["livemode"]` matches `STRIPE_SECRET_KEY.startswith("sk_live_")`.
Reject with 400 on mismatch and log loudly.

### H-3 · The webhook resolves an order without checking the tenant
`public.stripe_webhook` does `db.get(Order, order_id)` using the id from event metadata.
Every other route in that file is scrupulously tenant-scoped; this one is not. The metadata
also carries `tenant_id`, so the check is free.

**Do:** compare `order.tenant_id` against the event's `tenant_id` metadata and ignore the
event on mismatch.

### H-4 · Capture is not bounded by the current order total
`accept_order` calls `stripe_service.capture(intent_id)` with **no amount**, which captures
the full authorised amount. If the order is edited downward between authorisation and
acceptance, **the customer is charged the original, higher amount.**

**Do:** capture `min(order.total, amount_capturable)` via `amount_to_capture`. Stripe
releases the remainder automatically on a partial capture (confirmed in their docs). Refuse
to capture and surface an error if `order.total` is **greater** than `amount_capturable`,
because that is undercharging in the shop's favour and must be a human decision.

### H-5 · `payment_status` may not actually flip to `paid`
`_record_card_payment` writes a `Payment` row through `payment_service.create_payment`,
which is the right route. **Not yet verified** that this flips `orders.payment_status` to
`paid` for an online order. If it does not, the tablet keeps showing its loud unpaid banner
on an order that has been charged, and staff will chase money they already have.

**Do:** assert it in a test, end to end, not by reading the code.

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

### H-7 · Currency is never checked against the Stripe account
The account is GBP. `create_checkout_session` passes the *tenant's* configured currency. A
tenant misconfigured to PKR would fail at Stripe with a confusing error at the worst
possible moment.

**Do:** validate the tenant currency is GBP (or the account's default) before creating the
session, and fail with a clear internal error rather than a Stripe one.

### H-8 · Unset return URLs surface as a 502
`STRIPE_SUCCESS_URL` / `STRIPE_CANCEL_URL` unset raises `StripeError` → **502 Bad Gateway**,
which reads as "our server is broken" when it is really "not configured". Should be the same
**503 "card payment is not available"** the missing-key path returns.

### H-9 · Rate limiting on an unauthenticated endpoint that calls a paid API
`POST /public/{tenant}/orders/{id}/checkout-session` needs no auth. The order id is an
unguessable UUID4 and the Stripe call is idempotent per order, so abuse is bounded — but it
is still an anonymous endpoint that makes an outbound API call.

**Do:** confirm the nginx `/api/` rate limit zone actually covers `/public/`, and that the
limit is sane for a shop's traffic.

### H-10 · No event-id ledger
Duplicate webhook deliveries are currently handled by **every branch being a no-op when the
state already matches**, which is genuinely idempotent for the events handled today. It stops
being sufficient the moment a branch does something non-idempotent (writing a Payment row,
sending an email).

**Do:** if any such branch is added, log processed `event["id"]`s and skip repeats. Stripe
explicitly warns events can arrive more than once.

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
