# HANDOFF - continue this project in this fresh session

You are the continuation of a paused session. Work through these steps in order.
Quality first. No scope drift.

## 1. Refresh context (do not skip)
- Invoke the /refresh skill for this project (this directory).
- It reads STATE.md (authoritative), then dated files newest to oldest including the
  latest PAUSE_CHECKPOINT, reconciles them, and flags any contradiction out loud.

## 2. Absorb the operating context
- Read ERROR_LOG.md. Do not repeat known mistakes.
- Read _context/ if present: CREDENTIALS.md (STRUCTURE only, never echo values),
  INFRA.md, SCHEMA.md, VERIFIED.md. Verify infra and schema against actual state
  before any DB, deploy, or credential action (zero-trust).
- Re-read this project's CLAUDE.md deployment rules: staged paths not `git add .`,
  no secrets in commits, correct repo and branch. Honor the global CLAUDE.md
  (credential safety, shell discipline, no em dashes).
- Relevant memory auto-loads via MEMORY.md. Check this project's memory pointers.
- Also read `memory/server-deployment-rules.md` before touching the server. It lives at
  `C:\Users\Malik\.claude\projects\C--Users-Malik-desktop-pos-project\memory\`, NOT in the
  repo. nginx is shared with Orbit CRM; a careless container operation takes down
  someone else's site.

## 3. Continue the work
- Open the latest PAUSE_CHECKPOINT_*.md in this directory
  (`PAUSE_CHECKPOINT_2026-07-29-B.md`). Resume from its "In Progress" and "Pending" sections.
- Goal (unchanged): Chick Shack UK's complete online ordering channel - customer orders on
  the website, the order reaches Imran's tablet, he accepts it with a lead time, a ticket
  prints on his existing EposNow printer, the customer is emailed at every step, and the
  order can be driven through to delivered and paid.
- Malik's standing instruction: **build the whole thing, stop asking for confirmation on
  each piece, keep replies short.** Imran confirmed the scope on 2026-07-29 03:06:
  *"You've got it, exactly what I'm looking for, thanks."*
- Priority next step: **the tablet lifecycle buttons.** The backend endpoints exist and are
  committed (`c7ec832`) but nothing calls them. In
  `frontend/src/pages/online-orders/OnlineOrdersPage.tsx` and
  `frontend/src/services/onlineOrdersApi.ts` add: "Out for delivery" / "Ready for
  collection" (one button, wording follows `service_type`) -> `POST
  /public/manage/orders/{id}/ready`; "Delivered" / "Collected" -> `/complete` with
  `mark_paid: true` when the order is unpaid cash; and a separate "Mark paid" -> `/paid`.
  Completed orders must leave the Active tab. Then make email required on the storefront
  checkout and surface ready/completed/paid on `OrderConfirmation.tsx`. Then run the
  backend test suite, which has not been run against any of this.

## 4. New client request, received 2026-07-29 03:08 (after the checkpoint was written)

Imran, on WhatsApp, verbatim:
> "In the menu the make it a meal needs modifiers"
> "For each make it a meal item"

Today "Make it a meal" is a single flat +£3.00 tick (`MEAL` in `storefront/src/data/menu.ts`,
one option, `min 0 / max 1`). He wants choosing it to then ask **what comes in the meal** -
almost certainly the drink, probably the side - per item.

**Ask him to confirm before building**, because it decides the data model:
1. Which choices does a meal include - drink only, or drink **and** side?
2. Which drinks are included at the £3.00 price, and are any an upcharge (the board lists
   cans at £1.79, so a bottle may cost more)?
3. Is the side always chips, or is there a choice?

Note this is **not** just a storefront change. The choices have to exist as rows so the
order endpoint accepts them, so it means new modifier groups in `seed_chick_shack.py` and a
re-seed. The awkward part is conditionality: the POS modifier model has no concept of a
group that only applies **when another modifier is selected**, and this needs exactly that
(no drink choice unless the meal upgrade is taken). Options are (a) fold it into one
required "Meal choice" group whose first option is "No meal" - simple, no schema change, and
the customer sees one list; or (b) add real conditional groups - correct, but a schema and
UI change on both front ends. **(a) is the recommendation**; do not start (b) without
Malik agreeing to the cost.

Tracked as **OI-45** in `_state/open-items.md`.

## Guardrails
- No scope drift. Same goal, nothing new.
- No compromise on quality.
- Verify before any load-bearing DB, infra, credential, or deploy action.
- Never echo credential or secret values anywhere.
- Imran's tablet URL is `https://eats.sitaratech.info/online-orders?shop=chick-shack`.
  Never hand out the `pos-demo.duckdns.org` demo URL to a client.
- Stay on `feat/storefront-checkout-wiring`. **A push to `main` triggers
  `deploy-production.yml`**, which redeploys the box and leaves nginx 502-ing on
  `eats.sitaratech.info` until it is recreated by hand. Merge only in a supervised window.
- Publishing the storefront (`cd storefront && npm run deploy`) is the UAT trigger, not a
  build step: real customers can order the moment it lands. Malik times it with Imran.
