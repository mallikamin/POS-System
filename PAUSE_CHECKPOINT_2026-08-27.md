# Pause Checkpoint - 2026-08-27

First checkpoint of 2026-08-27. The three checkpoints dated 2026-08-26 are history and
`PAUSE_CHECKPOINT_2026-08-26-C.md` is now superseded by this one. Do not overwrite any of them.

## Project
- **Name**: POS System (Sitara Infotech) - FZ LLC UAE build
- **Path**: `C:\Users\Malik\desktop\pos-project`
- **Branch**: main. **HEAD `f486642` = `origin/main` = server. 0 unpushed.**

## Goal (unchanged)
Get the finished FZ LLC build in front of Martin Zubeldia by **Friday 2026-08-28**: a demo video,
a walkthrough PDF and a two-tier quotation, so he and his partners review over the weekend and
reconnect Monday 08-31.

## 🔴 DO THIS FIRST TOMORROW, BEFORE ANY WORK

**Rotate the Anthropic API key.** During this session the key was echoed in full by a docker
compose error (a byte-order mark landed in front of the variable name and compose printed the
offending line back verbatim). **It is Thrive Timesheet's LIVE PRODUCTION key** and it is now in
this session's transcript. Nothing public, nothing hostile, but a credential that has appeared in
logs should be rotated on principle.

Rotating means re-issuing it in **two** places:
1. Thrive Timesheet's droplet (that is where it actually earns its living).
2. `/root/pos-system/.env.demo` here, then recreate backend and nginx (see the runbook below).

⚠️ **Do not skip step 1.** Revoking the old key without replacing it on Thrive breaks Thrive's
daily draft job silently.

## Where things stand

### Shipped and verified on production today
- **`c23b574`** procurement, PO workflow, OCR receiving, ordering engine, quotations.
- **`a874fb9`** AI spend guardrails: a **USD daily cap** (`AI_DAILY_COST_CAP_USD_PER_TENANT`,
  set to **5.00**), a **per-tenant allowlist** (`AI_ENABLED_TENANT_SLUGS`, set to **martin-fz**),
  and the production compose AI passthrough that was **completely missing** (a key in
  `.env.demo` would never have reached the container, silently).
- **`f3c6759`** the nine UAT findings, including the **stock movement history** that never had a
  reader, per-tenant UI visibility, and four session/identity bugs.
- **`f486642`** docs.

Three production deploys, all green. **Chick Shack measured before and after every one and
identical at all five measurements**: 233 orders, newest `2026-08-26 19:40:58`, 166 customers,
219 payments, 642087 total, 87 menu items.

### AI is LIVE for Martin only, and that was proved, not assumed
Read out of the running container: `ai_configured=True`, model `claude-opus-5`, cost cap `5.00`,
`tenants allowed: ['martin-fz']`. Then an actual call was made on the box:

```
martin-fz       -> LIVE CALL OK, model said: ready
chick-shack     -> refused (correct)
demo-restaurant -> refused (correct)
cosa-nostra     -> refused (correct)
usage martin-fz : 1 call, 243 units, $0.001455
```

That settles the three things config alone cannot: the credential is accepted, **this droplet can
actually reach the Anthropic API** (its egress is restricted - SMTP is blocked, which is why email
goes via Brevo over HTTPS), and the tenant gate holds.

⚠️ **Billing note Malik raised:** the key is Thrive's live one, so Martin's demo spend lands on
Thrive's invoice and the Anthropic console cannot separate them. Our own `ai_usage_log` **can**,
per tenant, so reconciliation is possible from this side. Worst case is bounded by the cap at
**$5/day, $150/month**, and only one tenant can reach it.

## Pending

- [ ] 🔴 **Rotate the key** (above).
- [ ] 🔴 **Finish UAT: exercises 5 to 15.** Exercises 1-4 are done. Malik drives, ONE STEP PER
      MESSAGE (`C:/Brain/hooks/step-guard.py` is armed and sticky). Source material is
      `_context/clients/fz-llc-uae/proposal/UAT_PLAYBOOK_FZ_LLC.md` - **convert it into one step
      at a time, do not paste it at him.**
- [ ] Fix whatever UAT turns up, redeploy, re-verify Chick Shack each time.
- [ ] **One clean screen recording.** Shot list at `proposal/DEMO_VIDEO_SCRIPT_2026-08-26.md`; it
      has a 4-minute pre-flight section, make him do it.
- [ ] **One PDF** - `proposal/FZ_LLC_System_Walkthrough.pdf`. ⚠️ **It must be re-rendered**:
      exercise 4 told the reader to open a movement history that did not exist until today, and
      several screens named in it have changed.
- [ ] **Then, last, the proposal/pricing discussion.** Malik: *"then finally we discuss the
      proposal to share."* Do not raise pricing before the video and the PDF are done.

## Tomorrow, in order

1. Rotate the key, both places, verify with the live-call script (below).
2. UAT exercises 5 to 15, one step at a time, fixing in run time.
3. Batch and deploy any fixes; re-measure Chick Shack around the deploy.
4. Pre-flight the recording, then Malik records **one clean take**.
5. Re-render the walkthrough PDF against the *fixed* system.
6. Only then, the proposal.

## Open decisions still owned by Malik

1. **The placeholder TRN `100123456700003`** prints on the A4 VAT invoice. Either get Martin's real
   TRN before recording, or say plainly on the call that it is dummy data. Do not let it pass
   unmentioned on a legal tax document.
2. **Uber Eats does not operate in the UAE.** Martin named it himself. Raise it directly; the real
   three are Talabat, Careem and noon Food.
3. **Tier B e-commerce delta of AED 120/month** is below the Chick Shack precedent (£35/mo) for
   comparable functionality. Flagged, not resolved.
4. Whether Chick Shack's online reports header should keep showing "Chick Shack" (it did show the
   generic "Online Orders" until today, a side effect of fixing the `restaurant_name` type bug).
   Revertible.

## Runbook: changing the AI key on production

Do not fight the shell quoting; it wasted time tonight. Write a script, `scp` it, run it.

1. Write the two lines to a temp file **without a BOM**:
   `[IO.File]::WriteAllText($p, $text, (New-Object System.Text.UTF8Encoding($false)))`.
   ⚠️ A BOM in front of a variable name makes docker compose **print the whole offending line**,
   which is exactly how the key ended up in a transcript tonight.
2. `scp` it, then on the box: back up `.env.demo`, delete existing `ANTHROPIC_API_KEY` and
   `AI_ENABLED_TENANT_SLUGS` lines, append the new pair, remove the temp file.
3. `docker compose -f docker-compose.demo.yml --env-file .env.demo config` first - it is the
   cheapest gate and it catches a malformed file before anything restarts.
4. `up -d --no-deps backend` (**never `restart`** - env is not hot-reloaded), wait for healthy.
5. Assert `/root/orbit-crm/voice.conf` is a **file**, then
   `up -d --no-deps --force-recreate nginx`, then `nginx -t`. nginx caches upstream IPs at
   startup; the backend has a new one.
6. Verify with `scratchpad/prove_ai.sh` shape: a real call for `martin-fz`, refusals for every
   other tenant, and a usage row. **`docker exec` needs `-i`** or the interpreter reads EOF and
   prints nothing while exiting 0.

## Gotchas that cost time tonight, so they do not cost it again

- **`cred-guard` blocks the Bash tool on anything naming a `.env` path**, including
  `--env-file .env.demo`. Use the PowerShell tool, or put the commands in a script and `scp` it.
  **Do not work around the guard.**
- **PowerShell strips inner double quotes** when passing a command string to `ssh`, which turned
  `sed -i "expr" file` into `sed -i expr` and lost the filename. Write scripts instead.
- **PowerShell 5.1 has no `&&` and no `<` redirection.** `shell-guard` denies the first.
- Piping a string to `ssh` stdin from PowerShell did not deliver. `scp` the file.

## Critical context carried forward

- **Server `159.65.158.26`, `~/pos-system`, shared nginx with Orbit CRM.** Read
  `memory/server-deployment-rules.md` and `memory/data-integrity.md` before touching it.
  `pg_dump` first, no exceptions.
- **`git push origin main` IS the deploy.** It recreates the shared nginx. Chick Shack trades
  **16:00-22:00 UK, 7 days** - deploy after close unless Malik explicitly clears it.
- **Measure Chick Shack the same way before and after every deploy.** A scare tonight turned out
  to be tenant-scoped numbers compared against unscoped ones. Nothing was lost.
- **The server returns 444 to curl.** Pass a browser `-A`. Not an outage.
- **`CI` and `Deploy to Staging` are red at clean HEAD.** OI-80, known, no signal.
  `Deploy to Production` is the one that matters.
- **Backups taken tonight**: `/root/backups/pos_pre_procurement_20260826T204142Z.sql.gz` and
  `/root/backups/pos_pre_uatfixes_20260826T225944Z.sql.gz`, plus several `.env.demo.bak.*`.
- 🔴 **Do not commit `_context/clients/fz-llc-uae/proposal/`.** The repo is PUBLIC and
  `_context/clients/` is tracked. It carries pricing and a live negotiation. Malik has not decided.
- **Must stay untracked** (plaintext credentials, public repo):
  `backend/app/scripts/{system_admin,sync_system_admin,seed_fz_llc,seed_demo_kitchen}.py` and the
  four `verify_*.py` scripts, which are the verification evidence for the procurement work.
- **`.env.example` was updated locally but left uncommitted** - `cred-guard` blocks git operations
  naming that path and the guard was not worked around. The same documentation exists in
  `config.py` and both compose files, so nothing is lost.

## Open items opened tonight
- **OI-92** deployment hygiene: a deploy needs a closed-shop window and that does not survive a
  fifth tenant. Measured, ranked fix in `_state/open-items.md`. **Deferred until after Martin.**
- **OI-93** there is no per-tenant module entitlement; every tenant's admin can reach every module
  ever built. Commercial exposure, not a data leak - isolation is proven. **Deferred until after
  Martin.** ⚠️ Not the same thing as `hidden_ui_modules`, which is presentation only.
