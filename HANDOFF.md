# HANDOFF - continue this project in this fresh session

You are the continuation of a paused session. Work through these steps in order.
Quality first. No scope drift.

## 1. Refresh context (do not skip)
- Invoke the /refresh skill for this project (this directory).
- It reads STATE.md (authoritative), then dated files newest to oldest including the
  latest PAUSE_CHECKPOINT, reconciles them, and flags any contradiction out loud.

## 2. Absorb the operating context
- Read `ERROR_LOG.md`. Do not repeat known mistakes. **The two newest entries (2026-07-29)
  are the ones that will catch you**: an env key written to the production env file that
  never reached the container, and `StripeObject` having no `.get()` while every mocked
  test passed.
- Read `docs/DEPLOYMENT_PLAYBOOK.md` before any deploy. **Merging to `main` IS the deploy**
  and it recreates nginx itself; there is no hand-fixing step.
- Read `docs/STRIPE_HARDENING_CHECKLIST.md` — that is the next task, written up in full.
- `_context/INDEX.md` documents why there is no `CREDENTIALS.md` / `SCHEMA.md` / `INFRA.md`
  here (deliberate: `INFRASTRUCTURE_CREDENTIALS_REFERENCE.md` at root is the master, and
  `_context/secrets/` is gitignored). Verify infra and schema against actual state before
  any DB, deploy, or credential action.
- Re-read this project's CLAUDE.md deployment rules: staged paths not `git add .`,
  no secrets in commits, correct repo and branch. Honor the global CLAUDE.md
  (credential safety, shell discipline).
- Also read `memory/server-deployment-rules.md` before touching the server — it lives in
  the Claude project memory dir, NOT the repo. **It is 124 days old and its server
  inventory is known-incomplete (OI-14)**; the deployment playbook is newer and wins.
- **cred-guard** blocks any command containing `.env.demo` and refuses to read/edit `.env*`.
  That is by design. Use a glob (`.env.dem[o]`), and write commit messages to a file for
  `git commit -F`. Malik: *"cred guard is here so u dont echo back secrets, rest u have
  all access."*

## 3. Continue the work
- Open `PAUSE_CHECKPOINT_2026-07-29-D.md` in this directory. Resume from its
  "In Progress" and "Pending" sections.
- Goal (unchanged): Chick Shack UK's complete online ordering channel - customer orders on
  the website, the order reaches Imran's tablet, he accepts it with a lead time, a ticket
  prints on his existing EposNow printer, the customer is emailed at every step, and the
  order can be driven through to delivered and paid.
- Malik's standing instruction: **build the whole thing, stop asking for confirmation on
  each piece, keep replies short.** When he is doing something himself in a browser,
  **give one short step per reply and stop** - he asked for that directly.

### 🔴 State to know before you do anything

**FOUR COMMITS ARE UNPUSHED ON PURPOSE.** `b884b0e`, `8ff61ce`, `889d5ad`, `9ebf896`.
Pushing IS deploying, and they change `accept_order` - the exact path Imran's UAT
exercises. **Push them only after the UAT passes.** The deploy will then run migration
`p2q3r4s5t6u7` (four nullable columns on `orders`; additive, already applied locally).

**ORDERING IS LIVE 24/7** on `chickshackg84.com`; every order lands on Imran's tablet at
`https://eats.sitaratech.info/online-orders?shop=chick-shack`.

**Email is configured and verified but has never sent a real message.** That happens in the
UAT. Mailjet, DKIM verified, `orders@chickshackg84.com` sends and receives (Fasthosts
forwarder to the shop's Gmail).

**Stripe is built, 20 tests, verified against the real sandbox** - but not deployed, and
`cardPaymentEnabled` is still `false`.

### Priority next step

1. **The 16:00 UK UAT with Imran** - order, email, tablet, print, accept, out for delivery.
2. **Then push the four held commits** and watch the deploy.
3. **Then Stripe hardening: `docs/STRIPE_HARDENING_CHECKLIST.md`, H-1 through H-10.**
   Malik asked for this explicitly - *"no threats please... dont want any surprises later
   on that oh we didnt wire this or that."* **H-1 is the one that will actually bite:**
   nginx blocks bad-bot user agents above every location, and Stripe calls webhooks with a
   `Stripe/1.0` UA - if it matches, every webhook is silently dropped as a 444.

## Guardrails
- No scope drift. Same goal, nothing new.
- No compromise on quality.
- Verify before any load-bearing DB, infra, credential, or deploy action. **Verify the
  effect, never the exit code** - a green deploy has twice now done nothing.
- Never echo credential or secret values anywhere. Test keys sit in
  `C:\Users\Malik\Downloads\stripe-test.txt` and Mailjet SMTP creds in
  `C:\Users\Malik\Downloads\DKIM.txt` - read them, never print them, and remind Malik to
  delete both once the values are on the server.
- **Never hand out `pos-demo.duckdns.org`** to the client - it works, but it is a demo URL.
- Never `git add .` here - the production env file is tracked and holds live secrets. The
  ~99 dirty paths in the tree are a pre-existing bulk markdown edit, not current work.
- **An env key must be added in TWO places** - the server env file *and* the backend's
  `environment:` list in `docker-compose.demo.yml`. `STRIPE_WEBHOOK_SECRET` is next.
- nginx returns **444 to curl/wget user agents by design**. Pass a browser `-A`. A 444 is
  the bot filter, not an outage - do not debug it.
- The DigitalOcean box is **shared with Orbit CRM**. `docker ps -a` and inspect volume
  mounts before any container operation.
- The Chrome extension is disconnected (OI-12), so browser automation is unavailable.
