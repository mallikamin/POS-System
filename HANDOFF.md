# HANDOFF - continue this project in this fresh session

You are the continuation of a paused session. Work through these steps in order.
Quality first. No scope drift.

## 1. Refresh context (do not skip)
- Invoke the /refresh skill for this project (this directory).
- It reads STATE.md (authoritative), then dated files newest to oldest including the
  latest PAUSE_CHECKPOINT, reconciles them, and flags any contradiction out loud.
- `PAUSE_CHECKPOINT_2026-08-01.md` is the newest checkpoint — read it in full before
  anything else. OI-41 (Stripe capture-on-accept) is PROVEN and fixed this time,
  verified directly against Stripe and the DB on a real order — do not re-investigate
  that. Everything left is four specific, well-scoped UX/polish fixes, none of them
  payment-correctness bugs.

## 2. Absorb the operating context
- Read ERROR_LOG.md, especially the two entries updated/added 2026-08-01 (session N):
  the capture-on-accept bug is now marked RESOLVED with its full root cause and fix, and
  a new entry covers the stale-print-ticket-cache bug found in the same live retest.
- Re-read this project's CLAUDE.md deployment rules: staged paths not `git add .`,
  no secrets in commits, correct repo and branch. Honor the global CLAUDE.md
  (credential safety, shell discipline).
- `memory/server-deployment-rules.md` before touching the server, `memory/data-integrity.md`
  before any DB op — `pg_dump` first, no exceptions. (Nothing in the 4 pending items
  needs a DB op or server touch besides a normal `git push` deploy, but read them anyway
  before assuming that stays true.)

## 3. Continue the work
- Open `PAUSE_CHECKPOINT_2026-08-01.md` in this directory and build its 4 "Pending"
  items, in the order listed — each one has the exact file, root cause hypothesis (where
  relevant), and what "done" looks like already written out.
- Goal (unchanged): Chick Shack UK online ordering. OI-41 (Stripe capture-on-accept) is
  proven and fixed; build the 4 remaining UX fixes surfaced by Malik's live retest with
  Imran — the "order received" email wrongly reads "Payable on delivery" for a prepaid
  card order, the receipt's "PAID ONLINE" line is too small/unbold, the "COPY n OF 3"
  line needs removing from the printed ticket entirely, and the new-order chime is still
  too quiet even at max device volume and needs a genuinely different technique (not
  just a bigger gain number — see the checkpoint's exact reasoning: square wave,
  layered oscillators, shorter envelope, a compressor to allow it safely).
- Priority next step: build all 4 in the order listed in the checkpoint (email wording
  is most customer-visible; the louder-chime item is last since it needs real-device
  confirmation from Malik/Imran that no amount of local testing can substitute for). Test
  each properly (pytest for the two backend items, tsc+vite build+eslint for the two
  frontend items), commit, push, and **verify the live artifact directly** — this
  project's own standing rule, restated because a recent deploy's own health check threw
  a transient, self-resolved false alarm (see ERROR_LOG.md 2026-08-01) that had to be
  independently checked rather than trusted either way. Do not tell Malik anything is
  fixed until you've confirmed it in the actual running container/bundle.
- Once all 4 are built and deployed, ask Malik/Imran for one more live retest — the
  chime volume specifically cannot be confirmed any other way.

## Guardrails
- No scope drift. Same goal, nothing new. OI-41 itself is closed — do not reopen or
  re-verify the payment mechanism unless something concrete suggests it broke again.
- No compromise on quality.
- Verify before any load-bearing DB, infra, credential, or deploy action — this project's
  established pattern is to verify against the live API/bundle/database, never the deploy
  log or script exit code alone.
- Never echo credential or secret values anywhere.
- Before running `/pause` or `/handoff` again today, check for an existing
  `PAUSE_CHECKPOINT_2026-08-01*.md` and suffix (`-B`, etc.) rather than overwrite.
