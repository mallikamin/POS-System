# HANDOFF - continue this project in this fresh session

You are the continuation of a paused session. Work through these steps in order.
Quality first. No scope drift.

## 1. Refresh context (do not skip)
- Invoke the /refresh skill for this project (this directory).
- It reads STATE.md (authoritative), then dated files newest to oldest including the
  latest PAUSE_CHECKPOINT, reconciles them, and flags any contradiction out loud.
- `PAUSE_CHECKPOINT_2026-07-31-F.md` is the newest of six same-day checkpoints
  (`.md`, `-B`, `-C`, `-D`, `-E`, `-F`) — read `-F` in full before anything else. It ends
  mid-investigation of a live, unresolved bug — do not treat it as a completed session.

## 2. Absorb the operating context
- Read ERROR_LOG.md, especially the two newest entries (2026-07-31, session M) — one is
  the exact unresolved bug you're picking up, the other is a lesson about verifying visual
  claims at full resolution, not thumbnail size.
- Read `docs/STRIPE_HARDENING_CHECKLIST.md` before touching anything payment-related — the
  H-1...H-10 history and the exact test plan currently being run live one.
- Re-read this project's CLAUDE.md deployment rules: staged paths not `git add .`,
  no secrets in commits, correct repo and branch. Honor the global CLAUDE.md
  (credential safety, shell discipline).
- `memory/server-deployment-rules.md` before touching the server, `memory/data-integrity.md`
  before any DB op — `pg_dump` first, no exceptions.

## 3. Continue the work
- Open `PAUSE_CHECKPOINT_2026-07-31-F.md` in this directory and resume from its "In
  Progress" section — that IS the priority, not a side item.
- Goal (unchanged): Chick Shack UK online ordering. Prove the Stripe **sandbox**
  card-payment flow end to end (OI-41) with Imran, who is standing by ready to re-test the
  moment this is fixed, then switch to **live** Stripe keys for one real transaction.
- Priority next step: **A real sandbox test just failed** — order `260731-001` was card-
  authorised correctly at checkout, but after Imran accepted it on the tablet, the tablet,
  all 3 printed receipts, and the confirmation email all still showed unpaid. Root cause is
  NOT yet found. The checkpoint's "In Progress" section lists the exact diagnostics already
  tried (and their results) and the 6 concrete next steps, in order — start there rather
  than re-deriving the investigation from scratch. Also confirm first thing whether commit
  `e3bc6ea` (an unrelated email-copy fix, pushed just before the incident) actually finished
  deploying — its GitHub Action was mid-run when this session was interrupted.

## Guardrails
- No scope drift. Same goal, nothing new.
- No compromise on quality.
- **Do not move to live Stripe keys until the sandbox capture-on-accept bug is fully
  understood, fixed, covered by a test that would have caught it, and retested clean with
  Imran.** This was Malik's own explicit two-step plan.
- Verify before any load-bearing DB, infra, credential, or deploy action — this project's
  established pattern is to verify against the live API/bundle/database, never the deploy
  log or script exit code alone.
- DB and Stripe are ground truth for payment state; the tablet/receipt/email are just three
  renderings of whatever they were told — if all three agree and are all wrong, look for
  one shared upstream cause, not three separate bugs.
- Never echo credential or secret values anywhere.
- Before running `/pause` or `/handoff` again today, check for an existing
  `PAUSE_CHECKPOINT_2026-07-31*.md` and suffix (`-G`, etc.) rather than overwrite.
