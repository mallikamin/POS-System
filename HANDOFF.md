# HANDOFF - continue this project in this fresh session

You are the continuation of a paused session. Work through these steps in order.
Quality first. No scope drift.

## 1. Refresh context (do not skip)
- Invoke the /refresh skill for this project (this directory).
- It reads STATE.md (authoritative), then dated files newest to oldest including the
  latest PAUSE_CHECKPOINT, reconciles them, and flags any contradiction out loud.
- ⚠️ There are TWO checkpoints dated 2026-08-26. **`PAUSE_CHECKPOINT_2026-08-26-B.md` is
  the newer one and the one to resume from.** The unsuffixed file is the morning session.

## 2. Absorb the operating context
- Read ERROR_LOG.md. Do not repeat known mistakes. **Five new entries were added 2026-08-26
  (evening)**, including a 100x unit-conversion bug that a unit test actively confirmed rather
  than caught, and the standard recipe for running a one-off script against production.
- Read _context/ if present: CREDENTIALS.md (STRUCTURE only, never echo values),
  INFRA.md, SCHEMA.md, VERIFIED.md. Verify infra and schema against actual state
  before any DB, deploy, or credential action (zero-trust).
- Re-read this project's CLAUDE.md deployment rules: staged paths not `git add .`,
  no secrets in commits, correct repo and branch. Honor the global CLAUDE.md
  (credential safety, shell discipline, no em dashes).
- Relevant memory auto-loads via MEMORY.md. Check this project's memory pointers,
  especially: fz-llc-pricing-and-build-posture, recipe-module-tz-bug-and-test-gap,
  universal-system-admin-login, server-deployment-rules, data-integrity.

## 3. Continue the work
- Open `PAUSE_CHECKPOINT_2026-08-26-B.md`. Resume from its "Pending" section.
- **Read `_context/clients/fz-llc-uae/plan-and-todo_2026-08-26.md` FIRST.** Its top section
  carries Malik's full standing directive verbatim, including the framing that this is also a
  chance to fine-tune the product and open upsell avenues for other clients.
- Goal (unchanged): Build every remaining item in Martin's written scope, then produce three
  deliverables: a demo video script for Malik's UAT recording, a UAT playbook PDF for Martin
  and his partners, and a two-tier quotation with third-party integration and payment gateway
  research. **Deadline Friday 2026-08-28** so Martin reviews over the weekend.
- Priority next step: **Supplier master + purchase order workflow + email PO sending.** Nothing
  exists for it yet, it is the largest unbuilt block, and OCR receiving and the AI-assisted PO
  suggestion both build directly on top of it.
- ⚠️ Before writing ANY code that calls an LLM (the AI-assisted PO suggestion), consult the
  `api-cost-playbook` skill first. Do not improvise cost handling.

## What is already live and must not regress
- Both FZ locations are live and verified on production at
  `https://eats.sitaratech.info/login?shop=martin-fz` (credentials in
  `backend/app/scripts/seed_fz_llc.py`, which is deliberately NOT in git).
- HEAD `815a21e` = origin/main = server. 0 unpushed.
- **Chick Shack baseline to re-check after any deploy: 227 orders, newest
  `2026-08-25 20:03:19.780197+00`, 172 customers, 222 payments, 0 locations.**

## Guardrails
- No scope drift. Same goal, nothing new.
- No compromise on quality.
- Verify before any load-bearing DB, infra, credential, or deploy action.
- Never echo credential or secret values anywhere.
- Zero interference with Chick Shack. It is a live business on the same shared server, behind
  the same nginx. Verify it explicitly before and after every deploy, never assume.
