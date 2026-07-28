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
- Also read `memory/server-deployment-rules.md` before touching the server. nginx is
  shared with Orbit CRM; a careless container operation takes down someone else's site.

## 3. Continue the work
- Open the latest PAUSE_CHECKPOINT_*.md in this directory
  (`PAUSE_CHECKPOINT_2026-07-29.md`). Resume from its "In Progress" and "Pending" sections.
- Goal (unchanged): Get Chick Shack UK's online ordering channel working end to end -
  customer orders on the website, order lands in the POS, Imran accepts it on the tablet
  with a lead time, kitchen ticket prints on his existing EposNow printer.
- Priority next step: **Build UAT run 2 - wire the storefront checkout to the live public
  ordering API.** The storefront renders a hardcoded menu whose IDs are slugs
  (`peri-half`), while `POST /public/chick-shack/orders` validates UUIDs, so no real order
  can be placed today. Fetch `GET /public/chick-shack/menu` so baskets carry real IDs,
  make `place()` in `storefront/src/components/Checkout.tsx` post the order (IDs and
  quantities only - a price returns 422 by design), poll
  `GET /public/chick-shack/orders/{id}/status` on the confirmation screen, and only then
  flip `SHOP.orderingEnabled` to `true`. Then run both UAT runs with Imran together.

## Guardrails
- No scope drift. Same goal, nothing new.
- No compromise on quality.
- Verify before any load-bearing DB, infra, credential, or deploy action.
- Never echo credential or secret values anywhere.
- Imran's tablet URL is `https://eats.sitaratech.info/online-orders?shop=chick-shack`.
  Never hand out the `pos-demo.duckdns.org` demo URL to a client.
