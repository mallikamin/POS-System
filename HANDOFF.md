# HANDOFF - continue this project in this fresh session

You are the continuation of a paused session. Work through these steps in order.
Quality first. No scope drift.

## 1. Refresh context (do not skip)
- Invoke the /refresh skill for this project (this directory).
- It reads STATE.md (authoritative), then dated files newest to oldest including the
  latest PAUSE_CHECKPOINT, reconciles them, and flags any contradiction out loud.

## 2. Absorb the operating context
- Read ERROR_LOG.md. Do not repeat known mistakes. **Three new entries from 2026-07-29
  are about the deploy pipeline** - read those before touching CI or the server.
- Read `docs/DEPLOYMENT_PLAYBOOK.md` before any deploy. Merging to `main` IS the deploy
  and it now recreates nginx itself; there is no hand-fixing step any more.
- Read `_context/` if present: CREDENTIALS.md (STRUCTURE only, never echo values),
  INFRA.md, SCHEMA.md, VERIFIED.md. Verify infra and schema against actual state
  before any DB, deploy, or credential action (zero-trust).
- Re-read this project's CLAUDE.md deployment rules: staged paths not `git add .`,
  no secrets in commits, correct repo and branch. Honor the global CLAUDE.md
  (credential safety, shell discipline, no em dashes).
- Also read `memory/server-deployment-rules.md` before touching the server. It lives at
  `C:\Users\Malik\.claude\projects\C--Users-Malik-desktop-pos-project\memory\`, NOT in the
  repo. **It is 124 days old and its inventory is known-incomplete (OI-14)** - verify
  against reality. nginx is shared with Orbit CRM; a careless container operation takes
  down someone else's site.
- **cred-guard** blocks commands containing `--env-file .env.demo` and refuses to
  read/edit `.env*`. That is by design. Split commands, or write commit messages to a
  file and use `git commit -F`. Malik: *"cred guard is here so u dont echo back secrets,
  rest u have all access."*

## 3. Continue the work
- Open `PAUSE_CHECKPOINT_2026-07-29-C.md` in this directory. Resume from its
  "In Progress" and "Pending" sections.
- Goal (unchanged): Chick Shack UK's complete online ordering channel - customer orders on
  the website, the order reaches Imran's tablet, he accepts it with a lead time, a ticket
  prints on his existing EposNow printer, the customer is emailed at every step, and the
  order can be driven through to delivered and paid.
- Malik's standing instruction: **build the whole thing, stop asking for confirmation on
  each piece, keep replies short.**

### 🔴 State to know before you do anything
**ORDERING IS LIVE.** `chickshackg84.com` was published 2026-07-29 ~00:30 UK and takes real
orders **24/7** (out-of-hours ones are labelled pre-orders). Every order goes to Imran's
tablet at `https://eats.sitaratech.info/online-orders?shop=chick-shack`.
**Imran has not been told, and has never opened that page on his real tablet.**

### Priority next step
**Email setup - `orders@chickshackg84.com` via Mailjet free.** The code side is done
(`e0168c4` added `Reply-To`); nothing sends because no provider is configured.
**Follow `docs/EMAIL_SETUP_RUNBOOK.md` exactly.** Malik does the DNS and asked for exact
records. It is **one additive TXT record - nothing existing is modified**, because DMARC
passes on DKIM alignment alone and the single live SPF record must not be edited on a
domain carrying the client's business email.

Then: Malik's own end-to-end test, then prompt Imran, then UAT.

## Guardrails
- No scope drift. Same goal, nothing new.
- No compromise on quality.
- Verify before any load-bearing DB, infra, credential, or deploy action.
- Never echo credential or secret values anywhere.
- **Never hand out `pos-demo.duckdns.org` to the client** - it works, but it is a demo URL.
- Never `git add .` here - the production env file is tracked and holds live secrets. The
  ~99 dirty paths in the tree are a pre-existing bulk markdown edit, not current work.
- nginx returns **444 to curl/wget user agents by design**. Pass a browser `-A`. A 444 is
  the bot filter, not an outage - do not debug it.
- The DigitalOcean box is **shared with Orbit CRM**. `docker ps -a` and inspect volume
  mounts before any container operation.
