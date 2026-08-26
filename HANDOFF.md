# HANDOFF - continue this project in this fresh session

You are the continuation of a paused session. Work through these steps in order.
Quality first. No scope drift.

## 1. Refresh context (do not skip)
- Invoke the `/refresh` skill for this project (this directory).
- It reads STATE.md (authoritative), then dated files newest to oldest, reconciles them, and
  flags any contradiction out loud.
- **The newest checkpoint is `PAUSE_CHECKPOINT_2026-08-27.md`. Resume from it.** The three
  checkpoints dated 2026-08-26 are history; `-C` is superseded.

## 2. Absorb the operating context
- Read `ERROR_LOG.md`. **Three entries were added 2026-08-27**, and two are about the same
  failure family worth internalising before you write anything: a test that reported a result it
  had not established, and a credential that was handled carefully and still ended up in a log.
- Read `_context/INDEX.md`. Verify infra and schema against actual state before any DB, deploy or
  credential action.
- Re-read this project's `CLAUDE.md` deployment rules: staged paths not `git add .`, no secrets in
  commits, correct repo and branch. Honour the global `CLAUDE.md` too.
- Memory pointers that matter here: `server-deployment-rules`, `data-integrity`,
  `chick-shack-two-deploy-pipelines`, `live-shop-hours-working-rules`,
  `terse-step-by-step-guidance`.

## 3. 🔴 FIRST ACTION, BEFORE ANYTHING ELSE

**Rotate the Anthropic API key.** It was echoed in full by a docker compose error during the
2026-08-27 session (a BOM in front of the variable name; compose quotes the whole `name=value`
pair when it cannot parse the name). **It is Thrive Timesheet's live production key.**

Re-issue it in **two** places, in this order:
1. **Thrive Timesheet's droplet first.** Revoking before replacing there breaks its daily draft
   job silently.
2. `/root/pos-system/.env.demo` here, then recreate backend and nginx.

The runbook, the shell gotchas that wasted an hour, and the verification script shape are all in
`PAUSE_CHECKPOINT_2026-08-27.md`. Do not improvise the env-file edit; write a script and `scp` it.

## 4. Then continue the work

Goal unchanged: the finished FZ LLC build in front of Martin Zubeldia by **Friday 2026-08-28** -
a demo video, a walkthrough PDF and a two-tier quotation - so he and his partners review over the
weekend and reconnect Monday 08-31.

Malik's own order for the day: *"we manually do the UAT, fix any pending bugs in run time. then 1
clean video screenrecording, 1 pdf and then finally we discuss the proposal to share."*

1. **UAT exercises 5 to 15** on production. Exercises 1-4 are done and passed. **Malik drives; you
   give ONE STEP PER MESSAGE.** `C:/Brain/hooks/step-guard.py` is armed and sticky: one action,
   one thing to report back, then stop and wait. No roadmap tables, no sub-steps, no multi-item
   asks. Source material is `_context/clients/fz-llc-uae/proposal/UAT_PLAYBOOK_FZ_LLC.md` -
   **convert it into one step at a time, do not paste it at him.**
2. **Fix what UAT turns up, in run time.** Batch the fixes, deploy once, and measure Chick Shack
   the same way before and after every deploy.
3. **One clean screen recording.** Shot list at `proposal/DEMO_VIDEO_SCRIPT_2026-08-26.md`. It has
   a 4-minute pre-flight section - make him do it. Do not hand him a one-shot recording on an
   unverified path.
4. **One PDF.** `proposal/FZ_LLC_System_Walkthrough.pdf` **must be re-rendered**: it described a
   stock movement history screen that did not exist until 2026-08-27, and other screens have
   changed.
5. **Then, last, the proposal.** Do not raise pricing before the video and the PDF are done.

## Guardrails
- No scope drift. Same goal, nothing new.
- Verify before any load-bearing DB, infra, credential or deploy action. Say "verified" or
  "untested", never "should work".
- **Never echo a credential** - and note that handling one carefully is not the same as it staying
  secret. See the 2026-08-27 ERROR_LOG entry.
- **Zero interference with Chick Shack.** Live business, same server, same shared nginx. It trades
  **16:00-22:00 UK, 7 days**; deploy after close unless Malik explicitly clears it. Verify their
  order count, newest order, customers and payments **before and after** every deploy, measured
  the same way both times.
- 🔴 **Do not commit `_context/clients/fz-llc-uae/proposal/`.** The repo is PUBLIC and
  `_context/clients/` is tracked; it carries pricing and a live negotiation. Malik has not decided.
- **Two open items are deferred until after Martin, by Malik's instruction:** OI-92 (deployment
  hygiene) and OI-93 (no per-tenant module entitlement). Do not start either.
