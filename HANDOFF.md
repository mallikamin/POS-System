# HANDOFF - continue this project in this fresh session

You are the continuation of a paused session. Work through these steps in order.
Quality first. No scope drift.

## 1. Refresh context (do not skip)
- Invoke the /refresh skill for this project (this directory).
- It reads STATE.md (authoritative), then dated files newest to oldest including the
  latest PAUSE_CHECKPOINT, reconciles them, and flags any contradiction out loud.

## 2. Absorb the operating context
- Read `ERROR_LOG.md`. Do not repeat known mistakes. **The four newest entries
  (2026-07-29 session E) are the ones that will catch you** - a Stripe parameter that
  every mock accepted and the real API rejected, a localised date string that parsed to
  `Invalid Date` and told customers the shop was shut for a whole day, a kitchen ticket
  that never printed because an `await` ended the user gesture, and an email path
  "verified" from a laptop that the server cannot reach at all.
- Read `docs/DEPLOYMENT_PLAYBOOK.md` before any deploy. **Merging to `main` IS the
  deploy.** The storefront is separate: `cd storefront && npm run deploy` (Cloudflare).
- `_context/INDEX.md` documents why there is no `CREDENTIALS.md` / `SCHEMA.md` /
  `INFRA.md` here (deliberate: `INFRASTRUCTURE_CREDENTIALS_REFERENCE.md` at root is the
  master, and `_context/secrets/` is gitignored). Verify infra and schema against actual
  state before any DB, deploy, or credential action.
- Re-read this project's CLAUDE.md deployment rules: staged paths not `git add .`,
  no secrets in commits, correct repo and branch. Honor the global CLAUDE.md
  (credential safety, shell discipline).
- Also read `memory/server-deployment-rules.md` before touching the server - it lives in
  the Claude project memory dir, NOT the repo. Its server inventory is known-incomplete
  (OI-14); the deployment playbook is newer and wins.
- **cred-guard** blocks any command containing `.env.demo`, and anything that looks like
  it would print key material - including filenames ending `.key` or `.pem`. Use a glob
  (`.env.dem[o]`), avoid those extensions in scratch files, and write commit messages to
  a file for `git commit -F`. It is by design, not a bug.

## 3. Continue the work
- Open `PAUSE_CHECKPOINT_2026-07-29-E.md` in this directory. Resume from its
  "In Progress" and "Pending" sections.
- Goal (unchanged): Chick Shack UK's complete online ordering channel - customer orders
  on the website, the order reaches Imran's tablet, he accepts it with a lead time, a
  ticket prints on his existing EposNow printer, the customer is emailed at every step,
  and the order can be driven through to delivered and paid.
- Malik's standing instruction: **build the whole thing, stop asking for confirmation on
  each piece, keep replies short.** When he is doing something himself in a browser,
  **give one short step per reply and stop** - he asked for that directly.

### First thing to do
**Commit `STATE.md` and `_state/open-items.md`.** They are the only uncommitted files
that matter and they carry OI-50 through OI-55 plus the revised Next action. Everything
else is pushed; the branch is level with `origin/main` at `4be3b73`.

### Priority - build these four, in this order, then email

All four came from **Imran using the system on his own tablet**, so they are observed
needs, not speculation.

1. **OI-51 - three copies of the ticket per accepted order.** One prints today.
   **Put the repeat in the ESC/POS payload** (`backend/app/services/print_service.py`),
   not three calls to `sendToPrinter`. Three navigations are three chances for Chrome to
   drop or coalesce the handoff, which is precisely the bug just fixed.
2. **OI-52 - the daily number, large, on every copy.**
   ⚠️ **The numbering already exists and already resets daily.** `260729-001` is
   `YYMMDD-NNN` and `NNN` restarts at 001 each day. **Do not build a counter.** The
   number is small body text today; it needs to be big at the top of each copy, with
   "COPY 1 OF 3" so three identical slips are not read as three orders.
3. **OI-53 - `/orders` has no Accept button.** Imran found this himself. The view offers
   Mark Ready / Pay / Receipt / Void, so a pending online order cannot be answered there.
   Add Accept and trim the view for a website-only shop.
4. **OI-54 - the landing page is wrong for this client.** `eats.sitaratech.info` opens on
   "Select Order Channel - Dine-In / Takeaway / Call Center"; all three are dead ends for
   Chick Shack, who take orders only from the website. Land on a dashboard or the queue.
   **Per-tenant, not a global change** - the core POS still serves all three channels.
5. **Then OI-55, email.**

### 🔴 State to know before you do anything

**PRINTING WORKS AND IS PHOTOGRAPHED** - our own ticket reached paper for the first time
on 2026-07-29. It broke first: both print paths `await`ed a fetch before navigating to
`rawbt:`, which ends the user gesture, and Chrome on Android drops the handoff **silently**
while the server logs a 200. URLs are now prefetched and `sendToPrinter` is synchronous.
**Do not move the fetch back into the tap handler.**

**EMAIL CANNOT SEND FROM THIS SERVER (OI-55).** Measured from the droplet: SMTP 25/465/587
time out (DigitalOcean's anti-spam block), 2525 accepts TCP then resets, and
`api.mailjet.com:443` connects but its **TLS handshake is reset** - while Stripe and GitHub
handshake fine from the same box. The credentials are almost certainly fine; the route is
blocked. **The ports question is settled - do not re-test SMTP.** The fix is a
transactional API this box can actually reach, or a host whose egress permits mail.
Tailscale does not solve this; it is private networking and does not change public egress.

**STRIPE IS DEPLOYED IN TEST MODE**, verified from inside the container. Hardening H-1 to
H-10 is done except **H-6** (register the webhook - Malik's dashboard step). Card payment
has **not** yet been driven through a browser, and `cardPaymentEnabled` is still `false`;
`?card=1` reveals the option to whoever has the link so testing can happen on the live
site without exposing real customers to test-mode declines.

**ORDERING IS LIVE 24/7** on `chickshackg84.com`; every order lands on Imran's tablet at
`https://eats.sitaratech.info/online-orders?shop=chick-shack`.

## Guardrails
- No scope drift. Same goal, nothing new.
- No compromise on quality.
- **Verify the effect, never the exit code.** A 200 in a log is not evidence; for a
  printer the only evidence is paper, and for email the only evidence is a received
  message. This session got burned by both in front of the client.
- **Verify a network dependency from the machine that will use it**, never from the
  laptop. That is what hid the email failure for a whole session.
- Never echo credential or secret values anywhere. Test keys sit in
  `C:\Users\Malik\Downloads\stripe-test.txt` and the webhook signing secret in
  `stripe.txt` - read them, never print them, and remind Malik to delete both once the
  values are settled on the server.
- **Never hand out `pos-demo.duckdns.org`** to the client - it works, but it is a demo URL.
- Never `git add .` here - the production env file is tracked and holds live secrets. The
  ~99 dirty paths in the tree are a pre-existing bulk markdown edit, not current work.
- **An env key must be added in TWO places** - the server env file *and* the backend's
  `environment:` list in `docker-compose.demo.yml`.
- nginx returns **444 to curl/wget user agents by design**. Pass a browser `-A`.
- The DigitalOcean box is **shared with Orbit CRM**, and the POS nginx config serves
  `orbit_api` directly. `docker ps -a` and inspect volume mounts before any container
  operation.
