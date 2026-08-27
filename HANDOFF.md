# HANDOFF - continue this project in this fresh session

You are the continuation of a paused session. Work through these steps in order.
Quality first. No scope drift.

## 1. Refresh context (do not skip)
- Invoke the /refresh skill for this project (this directory).
- It reads STATE.md (authoritative), then dated files newest to oldest including the
  latest PAUSE_CHECKPOINT, reconciles them, and flags any contradiction out loud.
- ⚠️ The newest checkpoint is **`PAUSE_CHECKPOINT_2026-08-27-B.md`**, not the unsuffixed
  one from the same day. The `-B` file supersedes; the 04:20 file is history and must not
  be overwritten.

## 2. Absorb the operating context
- Read ERROR_LOG.md. Do not repeat known mistakes. Three entries were added on 2026-08-27
  and all three matter: the double-charged tax and why 765 tests missed it; fixing the
  instance while the class survives; and three verification traps specific to this server.
- Read _context/ if present: INFRA.md, SCHEMA.md, VERIFIED.md, and the credential
  reference by NAME only - never echo a value. Verify infra and schema against actual
  state before any DB, deploy, or secret-touching action (zero-trust).
- Re-read this project's CLAUDE.md deployment rules: staged paths not `git add .`,
  no secrets in commits, correct repo and branch. Honor the global CLAUDE.md
  (secret safety, shell discipline, no em dashes).
- Relevant memory auto-loads via MEMORY.md. Check this project's memory pointers.

## 3. Continue the work
- Open **`PAUSE_CHECKPOINT_2026-08-27-B.md`** and resume from it. The full finding
  register is `_state/uat-findings-fz-llc-batch2.md` (21 findings, F10-F30).
- Goal (unchanged): get the finished FZ LLC build in front of Martin Zubeldia - a demo
  video, a walkthrough PDF and a two-tier quotation - so he and his partners review over
  the weekend and reconnect Monday 2026-08-31.
- Priority next step: **run UAT step by step from Exercise 9, with Malik driving.**
  ONE STEP PER MESSAGE (`step-guard.py` is armed and sticky). Exercises 1-8 were done by
  hand; 9-15 have been verified **by script only, never seen in a browser**.
  Then one clean demo video, then a lean UAT guide.

### Before anything is recorded
1. 🔴 **Fix F29** - the Profitability report returns **0 rows** because no completed order
   carries channel data. That is the report Martin specifically asked for and it currently
   renders blank. Seed demo data.
2. **Decide the TRN.** `100123456700003` is a placeholder and it prints on the A4 tax
   invoice at both locations. Get Martin's real one, or say plainly on the call that it is
   dummy data. Do not let it pass unmentioned on a legal tax document.
3. **Re-render the walkthrough PDF** - Exercise 8 is factually wrong (F21: it tells the
   reader to check stock right after ringing up, but stock only moves on completion).
4. **Clean `martin-fz`'s order list** of UAT and script test orders.

### State at handoff
- **HEAD `af962c0` = origin = server, 0 unpushed.** Four green production deploys today.
- **Chick Shack byte-identical through every one**: 233 orders / 166 customers / 219
  payments / 642087 total / 87 menu items, measured tenant-scoped before and after each.
- **Test baseline: 824 passed, 10 failed, 2 errors.** The 10 are pre-existing and
  unrelated (8 QuickBooks Desktop, 1 stale message string, 1 HTTP 401). **10/2 means
  nothing regressed.**
- 15 findings fixed and live; 7 still open, listed in the checkpoint with the two that
  affect the video called out.

## Guardrails
- No scope drift. Same goal, nothing new.
- No compromise on quality.
- Verify before any load-bearing DB, infra, secret, or deploy action.
- Never echo credential or secret values anywhere.
- **Sweep for the class, not the instance.** That rule was bought expensively today.
- Do not make Malik the bug-finder. You hold the API access - drive the flows yourself
  and hand him a working system to review.
