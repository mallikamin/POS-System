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

## 3. Continue the work
- Open the latest PAUSE_CHECKPOINT_*.md in this directory. Resume from its
  "In Progress" and "Pending" sections.
- Goal (unchanged): advise Malik on OI-76, Imran's request for exact delivery
  locations in rural Argyll, then reply to Imran. Nothing is mid-build.
- Priority next step: research the options for OI-76 and discuss them with Malik
  before writing any code. Imran asked for ADVICE, not a build ("I don't know if
  you think this is a good idea"). Read
  `_context/clients/chick-shack-uk/voice-notes/2026-08-10_imran_what3words.md`
  first. what3words is a commercial product, so its licensing and API pricing must
  be checked against current published terms and never quoted from memory. The free
  alternative Imran has not considered is capturing the customer's device GPS at
  checkout and attaching a maps link to the order.

## Guardrails
- No scope drift. Same goal, nothing new.
- No compromise on quality.
- Verify before any load-bearing DB, infra, credential, or deploy action.
- Never echo credential or secret values anywhere.
- The Google review email went live TODAY and tonight is its first fully automatic
  run. `chick-shack` is ON, the other two tenants OFF. `review_email_sent_at` on
  `orders` is the audit trail: populated means asked, NULL means not.
- Any storefront change is a Cloudflare deploy (`cd storefront && npm run deploy`),
  NOT `git push`. A green Action proves nothing about the storefront.
- Do NOT `git add -A`: the tree carries OI-60's never-build-tested `backend/Dockerfile`
  and `backend/scripts/start.sh`. Stage by explicit filename.
