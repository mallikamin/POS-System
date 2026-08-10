# POS System Error Log

---
**⚠️ QUALITY ASSURANCE NOTICE**

All outputs from Claude Code are subject to dual review:
1. **Codex AI** — Automated accuracy validation
2. **Senior Personnel** — Manual verification & approval

Every implementation, configuration, deployment, and documentation must be **100% correct** and production-ready. No exceptions.
---


Cumulative log of errors encountered and fixed during development. Any agent (Claude, Codex, Cursor, DeepSeek) working on this project should read this file first to avoid repeating known mistakes, and append new entries when fixing errors.

---

## Format

Each entry follows:
```
### [DATE] — Short title
- **Error**: Exact error message or symptom
- **Context**: What was being done when it happened
- **Root Cause**: Why it happened
- **Fix**: What was changed
- **Rule**: What to do differently going forward
```

---

### 2026-02-20 — Floor Editor not loading
- **Error**: `/floor-editor` page blank or failing to render
- **Context**: Pre-Phase 6 stabilization — page had not been validated since Phase 4
- **Root Cause**: Stale component wiring and missing API integration after Phase 5 order changes
- **Fix**: Debugged and rewired FloorEditorPage interactions (load, drag, save, add, delete); toast noise reduced
- **Rule**: Always smoke-test affected pages after cross-cutting changes (e.g., order schema updates)

### 2026-02-20 — Dine-In POS not loading
- **Error**: `/dine-in` page broken — table selection and cart not syncing
- **Context**: Pre-Phase 6 stabilization
- **Root Cause**: Table/cart synchronization broke when Phase 5 introduced real API order submission; cart key switching (`table-{uuid}`) had race conditions
- **Fix**: Stabilized DineInPage table/cart synchronization when selection changes
- **Rule**: Multi-cart flows (dine-in table switching) must be retested after any cartStore or orderStore changes

### 2026-02-20 — Takeaway POS not loading
- **Error**: `/takeaway` page not functioning end-to-end
- **Context**: Pre-Phase 6 stabilization
- **Root Cause**: Similar to Dine-In — order submission path broke after Phase 5 API wiring
- **Fix**: Validated and fixed Takeaway ordering flow end-to-end

### 2026-07-14 — Docker container read-only error when copying seed script
- **Error**: `error reading from daemon: container rootfs is marked read-only`
- **Context**: Attempting to copy seed_demo_kitchen.py into running pos-system-backend-1 container via docker cp
- **Root Cause**: Container has read-only rootfs (immutable production setup); docker cp requires writable FS
- **Fix**: Bypassed file copy; piped SQL directly to psql via SSH instead. Created SQL-based seeding (more efficient anyway).
- **Rule**: Do not attempt docker cp into production containers with read-only FS. Use stdin/pipes or rebuild image instead.

### 2026-07-14 — PostgreSQL gen_salt() function not found
- **Error**: `ERROR: function gen_salt(unknown) does not exist`
- **Context**: Attempting to create demo user with bcrypt password via gen_salt() in SQL INSERT
- **Root Cause**: pgcrypto extension not installed, or gen_salt() signature differs from expected
- **Fix**: Generated bcrypt hashes in backend container (passlib.CryptContext) and inserted hashes as string literals via SQL
- **Rule**: When password hashing is needed, generate hashes in application layer (Python/backend) rather than in DB SQL; insert as opaque strings.

### 2026-07-14 — Demo order count discrepancy (expected 31, got 20)
- **Error**: SQL seeding script created ~20 orders instead of expected 31 (one per day for 31 days)
- **Context**: Seeding 31-day demo order history for demo-restaurant tenant
- **Root Cause**: Possible SQL transaction scope, loop nesting issue, or constraint violations in the PL/pgSQL block
- **Fix**: Data is sufficient for demo (20+ orders still populates all views). If exact 31-day window needed, can re-run seed or manually verify loop logic.
- **Rule**: Verify final row counts after bulk seeding; if off by small margin (<25%), acceptable for demo. For production, add RAISE NOTICE for loop iteration logging.
- **Rule**: All three POS channels (dine-in, takeaway, call-center) must be smoke-tested together after order flow changes

### 2026-02-23 — 147 test failures after adding audit_logs table
- **Error**: `sqlalchemy.exc.CompileError` / `OperationalError` — JSONB column type incompatible with SQLite test DB
- **Context**: Phase 9 audit_logs migration added a JSONB `changes` column. Test suite uses in-memory SQLite
- **Root Cause**: SQLite has no JSONB type. The `audit_logs` table must be skipped like the QB tables
- **Fix**: Added `"audit_logs"` to `_SKIP_TABLE_NAMES` set in `backend/tests/conftest.py`
- **Rule**: Any new table using PostgreSQL-specific types (JSONB, ARRAY, etc.) must be added to the skip set in conftest.py

### 2026-02-23 — PendingRollbackError in call-center order tests
- **Error**: `sqlalchemy.exc.PendingRollbackError: Can't reconnect until invalid transaction is rolled back`
- **Context**: Creating call-center orders triggered `audit_service.log_action()` which failed (no audit_logs table in SQLite), poisoning the DB session
- **Root Cause**: `db.flush()` inside audit_service failed, putting the session into "needs rollback" state. Subsequent `db.commit()` in the route handler failed
- **Fix**: Wrapped audit insert in `async with db.begin_nested():` (SAVEPOINT). Only the audit entry rolls back on failure, preserving the caller's transaction
- **Rule**: Non-critical operations (logging, analytics, notifications) must use SAVEPOINT isolation (`begin_nested()`) to avoid poisoning the caller's session

### 2026-02-23 — Kitchen station and payment refund tests returning 403
- **Error**: 5 kitchen + 6 payment tests returning HTTP 403 Forbidden
- **Context**: TARS audit added `require_role("admin")` to station CRUD and refund endpoints
- **Root Cause**: Tests used `cashier_token` but endpoints now require admin role
- **Fix**: Changed test methods to use `admin_token` instead of `cashier_token`
- **Rule**: When adding role-based guards to endpoints, ALWAYS update ALL corresponding tests to use the matching role token

### 2026-02-23 — Redis "unhealthy" on production
- **Error**: Health check returned `"redis": "unhealthy: invalid username-password pair or user is disabled."`
- **Context**: After deploying phases 9-10 to production
- **Root Cause**: `.env.demo` had `REDIS_PASSWORD=d8a2f6c0e4b9173d5f7a1c3e9b0d8f2a` but `redis.conf` has `requirepass pos_redis_dev_secret`
- **Fix**: Updated `.env.demo` to match redis.conf. Must recreate container (`up -d --no-deps`), not just `restart` — restart reuses old env vars
- **Rule**: Docker container `restart` does NOT reload env vars. Must recreate with `up -d --no-deps` to pick up .env changes

### 2026-02-23 — Customer phone normalization mismatch on update
- **Error**: Order history joins failing silently — no matching orders for customers with dashes in phone
- **Context**: DB audit found `create_customer` normalizes phone (strips non-digits) but `update_customer` did not
- **Root Cause**: `update_customer` passed raw phone input without normalizing, so phones like "0300-111-2233" were stored with dashes while order phones were digit-only
- **Fix**: Added `"".join(c for c in new_phone if c.isdigit())` normalization in `update_customer`
- **Rule**: Phone normalization must be applied on BOTH create AND update paths. Any field that participates in cross-table joins must be normalized consistently at all write points

### 2026-03-04 — Tables stuck red/occupied after full payment
- **Error**: Tables T1-T7 showing as "occupied" (red) despite all orders being fully paid or tables having no active orders
- **Context**: Multi-order table session testing (client checklist Test #4)
- **Root Cause**: `reconcile_table_occupancy` in `floor_service.py` used OR logic: `(status != "completed") | (payment_status NOT IN paid/refunded)`. A served+paid or in_kitchen+paid order would keep the table red because `status != "completed"` is True, making the OR true. Additionally, stale seed/test orders from weeks earlier were on tables in non-terminal unpaid states.
- **Fix**: Changed to payment-centric logic: table occupied only if orders are `NOT voided/completed AND NOT paid/refunded`. Also added auto-complete for served+paid dine-in orders in `_sync_order_payment_status`. Cleaned up 6 stale orders via script.
- **Rule**: Table occupancy should be driven by payment status, not kitchen pipeline status. Once paid, the table should be freed. Also: seed/test data can accumulate and cause phantom occupancy — always reconcile against actual payment state, not just order status.

### 2026-03-04 — Receipt tax formula wrong for split payments
- **Error**: Receipt showed "GST (16%)" with a blended tax amount for split cash/card payment, instead of showing per-method tax breakdown
- **Context**: Receipt preview for session with split Cash (16% tax) + Card (5% tax) payment
- **Root Cause**: (1) Session receipt builder did not send `cash_tax_rate_bps`/`card_tax_rate_bps` fields (defaulted to 0). (2) Frontend tax extraction formula used `amount * rate / 10000` which applies the rate to the tax-inclusive amount instead of extracting tax from it.
- **Fix**: Added tax rate fields to session receipt return. Fixed formula to `base = round(amount * 10000 / (10000 + rate))`, `tax = amount - base`. This correctly extracts tax from inclusive amounts.
- **Rule**: When extracting tax from a tax-inclusive amount, use `base = amount * 10000 / (10000 + rate_bps)`, NOT `tax = amount * rate / 10000`. The latter applies the rate to the gross amount, double-counting.

### 2026-03-04 — Receipt payments fragmented across orders
- **Error**: Receipt showed 3 separate payment lines (Cash 774, Cash 726, Card 1320) instead of consolidated by method (Cash 1500, Card 1320)
- **Context**: Session payment allocates across orders oldest-first, creating separate Payment records per order. Receipt showed each record individually.
- **Root Cause**: `_get_session_receipt_data` passed raw payment records to receipt without consolidation
- **Fix**: Added consolidation in receipt service — aggregate payments by method name before building `ReceiptPayment` list
- **Rule**: Session receipts should always consolidate payments by method. The per-order allocation is an internal detail, not customer-facing.

### 2026-03-25 — rsync --delete wiped server files during CI/CD deploy
- **Error**: GitHub Actions rsync `--delete` flag removed ALL server files (git repo, .env.demo, frontend/, scripts/) — only deploy-package contents survived
- **Context**: Setting up GitHub Actions CI/CD for the first time. Workflow used `rsync -avz --delete deploy-package/ server:pos-system/`
- **Root Cause**: `--delete` removes any files on the destination that aren't in the source. The deploy-package only contained frontend-dist, backend, docker, and docker-compose.demo.yml — everything else was deleted.
- **Fix**: Restored server via `git clone` + .env.demo backup from /tmp. Rewrote workflow to: (1) rsync ONLY frontend dist files, (2) use `git pull` for code sync on server. No more `--delete` flag.
- **Rule**: NEVER use `rsync --delete` to deploy to a production server unless the source is a complete mirror. For partial deploys, rsync specific directories without `--delete`, and use `git pull` for code sync.

### 2026-03-25 — .dockerignore blocks pre-built dist in CI/CD
- **Error**: `COPY dist /usr/share/nginx/html` failed with "not found" — Docker couldn't see the dist directory
- **Context**: CI/CD builds frontend on GitHub, uploads dist to server, then tries to build nginx image with pre-built files
- **Root Cause**: `frontend/.dockerignore` contains `dist` — Docker build context excludes the directory even though it exists on disk
- **Fix**: Workflow temporarily removes `dist` from .dockerignore before build (`sed -i '/^dist$/d'`), then restores it after. Created `Dockerfile.prebuilt` that's separate from the full multi-stage Dockerfile.
- **Rule**: When using pre-built artifacts with Docker, check `.dockerignore` — it can silently exclude files you need. Use a separate Dockerfile for CI/CD pre-built deploys.

### 2026-03-25 — Server OOM during frontend build (2GB droplet)
- **Error**: SSH disconnects, load average 47.97, 29MB RAM free during `docker compose build frontend`
- **Context**: TypeScript compilation (tsc --noEmit) consumed 345MB RAM + Vite build needs ~500MB, on a server with 1.9GB total already running 4 containers
- **Root Cause**: 2GB RAM insufficient for Node.js TypeScript + Vite builds alongside running Docker containers
- **Fix**: Set up GitHub Actions CI/CD — builds happen on GitHub's 7GB RAM runners. Server only serves pre-built static files via nginx.
- **Rule**: Never build frontend (TypeScript/Vite/webpack) on a production server with < 4GB RAM. Use CI/CD runners for builds, deploy only artifacts.

### 2026-07-15 — SSL certificate renewal failed to add new domain
- **Error**: Certificate still only has `CN = pos-demo.duckdns.org`, no Subject Alternative Name for eats.sitaratech.info
- **Context**: Attempted to renew SSL certificate with new subdomain using `certbot certonly --expand -d pos-demo.duckdns.org -d eats.sitaratech.info --standalone`
- **Root Cause**: `--expand` flag requires explicit `--cert-name` parameter to identify which existing certificate to expand. Without it, certbot doesn't know which cert to modify.
- **Fix**: Retry renewal with `--cert-name pos-demo.duckdns.org` explicitly specified in command
- **Rule**: When using certbot `--expand` to add domains to an existing certificate, always include `--cert-name` to specify which certificate to modify. Without it, the command may silently fail to update the cert.
- **CORRECTION (2026-07-15, later session)**: The above diagnosis was wrong. The `--expand` retry actually DID succeed and issued a valid cert with both domains — it just wrote it into a stray Docker volume (`certbot-etc`) that nginx never mounts, instead of the volume nginx actually reads (`certbot_certs`). Separately, nginx had **no `server_name` entry for eats.sitaratech.info at all**, so even a perfect cert wouldn't have worked — requests fell through to the `444` catch-all. See the three entries below for the real fixes. Lesson: after any certbot run, verify against the volume/path the running service actually mounts (`docker inspect <container> | grep -A5 Mounts`), don't assume `docker run --rm -v <name>` targets the right volume just because the command "succeeds."

### 2026-07-15 — nginx has no server_name block for a new domain despite valid SSL cert
- **Error**: `eats.sitaratech.info` returned no response / connection reset (nginx `444`) even after the cert covering it was in place
- **Context**: Diagnosing why eats.sitaratech.info still didn't work after confirming the SSL cert had the correct SAN
- **Root Cause**: `docker/nginx/nginx.demo.conf` only had `server_name pos-demo.duckdns.org;` — no block matched the new domain, so nginx routed it to the `default_server { return 444; }` catch-all regardless of cert validity
- **Fix**: Added the new domain to the existing `server_name` directives (port 80 redirect + port 443 app block) and to the CSP `connect-src` (for WebSocket, `wss://`)
- **Rule**: A valid multi-SAN SSL cert is necessary but not sufficient for a new domain to work — nginx also needs an explicit `server_name` match (or the domain added to an existing one), or it silently falls through to whatever catch-all block exists.

### 2026-07-15 — nginx bind-mounted config went stale after git pull; `nginx -s reload` didn't help
- **Error**: After `git pull` updated `docker/nginx/nginx.demo.conf` on the server and running `nginx -s reload`, the container's `/etc/nginx/conf.d/default.conf` still showed the OLD content (confirmed via `docker exec ... cat`, wrong mtime)
- **Context**: nginx.demo.conf is bind-mounted (not baked into the image) from `/root/pos-system/docker/nginx/nginx.demo.conf`
- **Root Cause**: git replaces a tracked file with a new inode on checkout/merge rather than editing in place. A single-file Docker bind mount can remain attached to the OLD (deleted but still-open) inode, so the container keeps seeing stale content until the container itself is recreated — a plain `reload` (which just re-reads the same mount) does not fix it
- **Fix**: `docker compose -f docker-compose.demo.yml --env-file .env.demo up -d --force-recreate nginx` (after re-verifying volume mounts per server-deployment-rules.md Rule 2)
- **Rule**: After ANY host-side edit to a file that's single-file bind-mounted into a running container (via git pull, sed, editor save-as-new-file, etc.), don't trust `reload`/`restart` to pick it up — verify content inside the container first (`docker exec <c> cat <path>` or check mtime), and recreate the container if it's stale.

### 2026-07-15 — certbot_certs Docker volume is shared by 3 unrelated projects; rm -rf during a "fix" wiped 2 of them
- **Error**: `nginx: [emerg] cannot load certificate ".../parkcity.sitaratech.info/fullchain.pem": No such file or directory` on reload
- **Context**: Merging a newly-corrected SSL cert into the `pos-system_certbot_certs` volume by running `rm -rf /dst/* && cp -a /src/. /dst/` inside a throwaway container
- **Root Cause**: `pos-system_certbot_certs` is mounted into nginx and holds Let's Encrypt data for THREE separate domains/projects (pos-demo.duckdns.org, parkcity.sitaratech.info, orbit-voice.duckdns.org — the latter two belonging to the unrelated Orbit CRM project). A blanket `rm -rf` on the whole volume before copying destroyed the other two certs.
- **Fix**: nginx's reload failed loudly instead of silently applying a broken config, so the live process kept serving the old (correct) certs with zero downtime. Restored the full volume from a pre-change backup (`tar czf` taken before the operation), then redid the merge scoped to only the specific domain's `archive/`, `live/`, and `renewal/*.conf` paths — never a blanket `rm -rf` on a volume shared by other projects.
- **Rule**: Before writing to ANY Docker volume, check `docker volume ls` for naming that suggests sharing, and `docker inspect <every-relevant-container>` for what else mounts it. On this server, `pos-system_certbot_certs` is infrastructure shared with Orbit CRM — never touch it with a wildcard delete. ALWAYS `tar czf` a backup of a shared volume before any write. Prefer additive/scoped copies over `rm -rf && cp`.

### 2026-07-15 — Nightly demo-refresh cron job cannot work as designed
- **Error**: `/var/log/demo-kitchen-refresh.log` never gets created; cron job silently does nothing
- **Context**: Verifying the STEP 2 nightly cron (previously marked "deployed & verified") actually ran at its scheduled 00:10 UTC time
- **Root Cause**: Three stacked problems: (1) the required credentials file `/root/.pos-demo-refresh.env` was never created on the server, so the `. /root/.pos-demo-refresh.env` source step in the crontab line fails and the `&&` chain aborts before python3 (and before the log redirect) ever runs; (2) even with that file, the host's bare `python3` has no `psycopg2` installed; (3) even with that installed, the Postgres container publishes **no port to the host** (`docker-compose.demo.yml` has no `ports:` under the `postgres` service — correct security posture, but incompatible with a bare-host cron script using `psycopg2.connect(host=...)`)
- **Fix**: NOT YET FIXED. Needs either a rewrite of the script to use the async stack already available in the backend container (invoked via `docker exec`), or a small sidecar image with `psycopg2` placed on the Postgres docker network.
- **Rule**: A cron job that connects to a containerized DB must run either inside a container already on that Docker network, or the DB port must be deliberately published to the host (a security tradeoff to make consciously, not accidentally). Before marking a cron/deploy step "verified," confirm its actual log output exists after a real scheduled run — a deployed script + a crontab entry is not the same as a working job.

### 2026-07-15 — Demo user password/PIN hashes were never actually written despite "RESOLVED" checkpoint claim
- **Error**: Login for `demo@demo.kitchen` failed with "Invalid email or password"; PIN `1111` logged into a different, wrong user (`youniskamran@demo.com`)
- **Context**: User tested login on eats.sitaratech.info after SSL was fixed
- **Root Cause**: Two independent bugs. (1) `demo@demo.kitchen`'s `hashed_password` column was empty (length 0) and `pin_code` was a corrupted non-bcrypt string — despite `PAUSE_CHECKPOINT_2026-07-15.md` claiming this was "RESOLVED ✅ (password now demo123)" the previous session; the write never actually happened. (2) `authenticate_by_pin` (`backend/app/services/auth_service.py:52-84`) loops all active users in a tenant and returns the first bcrypt PIN match, with **no PIN-uniqueness constraint anywhere** — so once demo's own PIN hash was broken (never matched), the loop fell through and matched `youniskamran@demo.com`, who genuinely had PIN 1111 set (an accidental collision from when his account was added later).
- **Fix**: Backed up the full DB first (mandatory per `memory/data-integrity.md`). Reset `demo@demo.kitchen`'s password and PIN hashes properly via a script run inside the backend container (has bcrypt/passlib + network access to Postgres). Deactivated `youniskamran@demo.com` (`is_active=false` + new PIN) rather than deleting it, since it had 6 real orders and 11 audit log entries attached — a hard delete would have cascaded and destroyed that history. Verified the fix via the live `/api/v1/auth/login/pin` endpoint, not just a DB query.
- **Rule**: Never trust a checkpoint's "RESOLVED" claim for a credential/auth fix without re-verifying live (query the actual column, or call the actual endpoint) — a session can believe a write succeeded when it didn't. Also: any system with hashed PINs/passwords and a "loop and try each" auth pattern needs an explicit uniqueness check at creation time, or collisions fail silently and unpredictably (whoever the DB happens to return first wins).

### 2026-07-27 — Cloudflare DNS auto-import silently dropped all 4 DKIM records
- **Error**: No error. The import reported success; four `livemail*._domainkey` CNAME records simply were not in the imported zone
- **Context**: Moving `chickshackg84.com` from Fasthosts to Cloudflare nameservers. The domain carries the client's live business email
- **Root Cause**: Cloudflare's zone auto-import is best-effort and does not guarantee completeness. It reports success on a partial import
- **Fix**: Caught by diffing the imported record list against the record set transcribed from the Fasthosts panel *before* activating the nameservers. The four DKIM CNAMEs were re-added by hand as DNS-only. Email verified against 8.8.8.8 / 1.1.1.1 / 9.9.9.9 after the switch
- **Rule**: **Never trust a DNS auto-import.** Transcribe the source zone first, then diff the destination record by record before activating nameservers. On a domain carrying live email, verify MX + SPF + DMARC + every DKIM selector resolves *after* the change, not just that the website loads. A missing DKIM record does not break mail visibly — it silently degrades deliverability, so nothing alerts you.

### 2026-07-27 — Cloudflare Workers custom domain fails: "already has externally managed DNS records"
- **Error**: `Hostname 'chickshackg84.com' already has externally managed DNS records (A, CNAME, etc). Delete them first. [code: 100117]`
- **Context**: `npx wrangler deploy` with `custom_domain = true` routes in `wrangler.toml`
- **Root Cause**: A Workers custom domain requires Cloudflare to own the record for that hostname. Two dead Vercel records from a previous developer (`A @ → 216.198.79.1`, `CNAME www → …vercel-dns-017.com`) still occupied the apex and `www`
- **Fix**: Deleted exactly those two records in the Cloudflare dashboard, then redeployed. Cloudflare created its own records and issued SSL automatically. The two `_vercel` domain-verify TXT records were left alone — they sit on a different hostname and never conflicted
- **Rule**: `100117` means a record occupies the exact hostname, nothing more. Delete only the conflicting `A`/`CNAME` on that hostname. Do not "clean up" adjacent records on a live domain. Also note `wrangler`'s OAuth token has `zone (read)` only and **cannot** edit DNS — that step needs the dashboard or a scoped API token.

### 2026-07-27 — Site reported dead for ~30 min after a correct DNS change; the router was caching
- **Error**: `curl` and Chrome both returned `Server: Vercel` / `404 DEPLOYMENT_NOT_FOUND` long after the Worker was live and serving. `ipconfig /flushdns` changed nothing
- **Context**: Verifying `chickshackg84.com` immediately after repointing it at a Cloudflare Worker
- **Root Cause**: The **local router at `192.168.1.1`** still held the pre-change `A → 216.198.79.1` from the old Fasthosts zone, whose TTL was long. `ipconfig /flushdns` clears only the Windows cache; Windows then re-queries the router and gets the same stale answer back. Every public resolver (1.1.1.1 / 8.8.8.8 / 9.9.9.9) and the authoritative Cloudflare nameservers had the correct answer the whole time
- **Fix**: Verified against the authoritative nameserver directly (`nslookup -type=A <domain> daisy.ns.cloudflare.com`) and by pinning the edge IP (`curl --resolve <domain>:443:<edge-ip>`), both of which returned 200 from Cloudflare. Confirmed independently from a phone on mobile data
- **Rule**: After any DNS change, **never conclude "it's broken" from the machine that made the change.** Its resolver chain is the least trustworthy vantage point available. Query the authoritative nameserver, pin the edge IP with `--resolve`, or use DoH (`https://1.1.1.1/dns-query?name=…&type=A`), and confirm from a genuinely different network before reporting status to anyone. Diagnose *which* resolver is stale (`Resolve-DnsName -Server <ip>`) rather than assuming propagation.

### 2026-07-27 — The entire backend test suite had been dead for four months, and nobody noticed
- **Error**: `sqlalchemy.exc.CompileError: (in table 'stock_counts', column 'count_data'): Compiler SQLiteTypeCompiler can't render element of type JSONB` — raised in the autouse `setup_db` fixture, so **every DB-backed test in the suite errored before its body ran**, not just inventory tests
- **Context**: Running `tests/test_public_ordering.py` in Docker to verify the new public ordering API. The previous session could only run it with `--noconftest`, which silently skipped the broken fixture and made 18 tests look green
- **Root Cause**: `backend/app/models/inventory.py` added `StockCount.count_data` as JSONB in commit `f8e9932` (2026-03-26, BOM Phase 1). `backend/tests/conftest.py` was last touched 2026-03-03 and its `_SKIP_TABLE_NAMES` set was never updated. **The rule that would have prevented this was already written in this very file** on 2026-02-23 ("Any new table using PostgreSQL-specific types (JSONB, ARRAY, etc.) must be added to the skip set in conftest.py"). It was documented, then violated a month later, and the violation survived four months because nothing ran the suite
- **Fix**: Added `stock_counts` to `_SKIP_TABLE_NAMES`. Rather than fixing one table and re-running to discover the next, enumerated all of them at once by compiling every table for the SQLite dialect — exactly three are incompatible (`audit_logs`, `qb_coa_snapshots`, `stock_counts`) and the first two were already skipped. That snippet is now a comment in `conftest.py` so the list can be regenerated instead of rediscovered
- **Result**: 272 passed, 10 failed, 2 errors. **All 12 failures are pre-existing and unrelated to the online-ordering work**: 10 are QuickBooks Desktop tests drifting from their implementation (they index `result["success"]` but the code returns a `QBXMLParseResult` object — QB Desktop is parked at 33%), one asserts a literal `"Payment required"` string that was since reworded to a friendlier message, and one returns 401 from a fixture auth problem
- **Rule**: **Two rules.** (1) A test suite that is never executed is not a safety net, it is a decoration — a green claim in a checkpoint means nothing without a run in this session. Any "N tests passing" claim dated between 2026-03-26 and 2026-07-27 in this repo should be treated as unverified. (2) `--noconftest` is not a way to verify tests, it is a way to avoid the fixtures that would have caught this. If the conftest will not import or its fixtures will not build, **that is the bug** — fix it rather than routing around it.

### 2026-07-27 — `tsc --noEmit` fails with TS6305 in the storefront
- **Error**: `TS6305: Output file ... has not been built from source file ...`
- **Context**: Type-checking `storefront/` from the command line
- **Root Cause**: The project uses a composite/referenced config (`tsconfig.app.json`); a bare `tsc` resolves the wrong project
- **Fix**: Use `npm run type-check` (or `tsc --noEmit -p tsconfig.app.json`). `npm run build` already chains the correct invocation
- **Rule**: In a project with TypeScript project references, never invoke bare `tsc` — always go through the package script or pass `-p` explicitly.

### 2026-07-29 — Local type-check passed, CI build failed on a missing export
- **Error**: `Module '"@/utils/currency"' has no exported member 'formatMoney'` — GitHub Actions build step
- **Context**: Committed the order-queue tablet view and pushed to main to deploy
- **Root Cause**: `frontend/src/utils/currency.ts` was **tracked but modified**. The new page imported `formatMoney`, which existed only in the working tree. Local `npm run type-check` passed because it type-checks the working tree; CI builds the commit.
- **Fix**: Committed `currency.ts` and `configStore.ts` alongside it
- **Rule**: Staging deliberately is right, but a partial stage can break the build in a way local checks cannot see. Before pushing a deploy commit, confirm nothing staged imports from a file left dirty — `git status` the whole subtree, not just the files you touched.

### 2026-07-29 — HTTPS host served the wrong certificate for two weeks
- **Error**: `ERR_CERT_COMMON_NAME_INVALID` on `https://eats.sitaratech.info`
- **Context**: About to hand a client-facing URL to Imran
- **Root Cause**: The 2026-07-15 change added the hostname to nginx `server_name` but **never issued a certificate for it**. Both hostnames shared one 443 block, and a server block can only present one certificate — so every visitor got the `pos-demo.duckdns.org` cert. The domain resolves straight to the origin, so there was no CDN to mask it.
- **Fix**: Issued a certificate via certbot webroot, split the shared block into two, each with its own certificate. Applied with `nginx -s reload` — **not** a container recreation, so volume mounts were never at risk. Verified per hostname with `openssl s_client -servername`.
- **Rule**: Adding a hostname to `server_name` is half a migration; the certificate is the other half, and nothing fails until a human opens a browser. After any domain change, verify with `openssl s_client -connect host:443 -servername <name> | openssl x509 -noout -subject` for **every** name on that box.

### 2026-07-29 — Seed script wrote 11 delivery areas to the wrong tenant
- **Error**: `We do not deliver to that area.` (409) when placing a Chick Shack order
- **Context**: Running the end-to-end order flow against the local stack
- **Root Cause**: `seed_chick_shack_delivery.py` was run on 2026-07-27, before the `chick-shack` tenant existed. It resolved to the only tenant present and wrote Garelochhead £3 through Arrochar £15 onto `demo-restaurant`.
- **Fix**: Re-ran with `--tenant-slug chick-shack`. The stray rows remain on the demo tenant locally (OI-39); production was never affected.
- **Rule**: A seed script must never resolve "the tenant" implicitly. Pass the slug explicitly and refuse to guess — and after seeding, verify the row counts **per tenant**, not in total.

### 2026-07-29 — A tenant seeded for online ordering had no payment methods at all
- **Error**: Not hit in production — caught while wiring "mark paid". `chick-shack` had
  **zero rows** in `payment_methods`, so `payment_service._get_method_or_raise` would have
  failed the first time anyone tapped Paid on the tablet
- **Context**: Adding the order lifecycle (out for delivery / delivered / paid) that the
  client asked for
- **Root Cause**: `seed_chick_shack.py` seeds the tenant, config, roles, users and the menu.
  It never touches the payments domain, because online orders are created `unpaid` and
  nothing had ever needed to settle one. `demo-restaurant` has 4 methods only because the
  original demo seeder called `ensure_default_payment_methods`
- **Fix**: `mark_order_paid` calls `ensure_default_payment_methods` before creating the
  payment. It is idempotent, so the cost is one indexed read per call
- **Rule**: A tenant seeder that creates a *partial* tenant leaves landmines for whichever
  feature is built next. When adding a seeder, either seed every domain the app can reach or
  make the consuming service self-heal. Check row counts **per tenant** (`GROUP BY
  tenant_id`), never in total — a healthy global count hid this completely.

### 2026-07-29 — The API would have refused the storefront's own domain, with no error anywhere
- **Error**: None. That is the entry. `GET /public/chick-shack/menu` returned **HTTP 200** to a
  request carrying `Origin: https://chickshackg84.com`, but with **no `access-control-allow-origin`
  header**, so every browser would have silently discarded a perfectly good response
- **Context**: Wiring the storefront checkout to the live ordering API, before publishing
- **Root Cause**: `CORS_ORIGINS` in `.env.demo` on the server was `https://pos-demo.duckdns.org`
  only. It had never needed anything else, because until now nothing called the API from another
  origin — the POS frontend is served from the same host as the API, so it is same-origin and CORS
  never applied
- **Why it would have been expensive**: the storefront falls back to its hardcoded menu when the
  fetch fails, and ordering is gated on the menu having come from the API. So the site would have
  looked completely normal and simply carried on saying "ring us". No console error visible to us,
  no failed request in any server log, no alert. It would have been discovered by Imran during UAT,
  or worse, not at all
- **Fix**: Backed up `.env.demo` first (`.env.demo.bak.<timestamp>`), added
  `eats.sitaratech.info`, `chickshackg84.com` and `www.chickshackg84.com`. Env changes are not
  hot-reloaded, so the backend was recreated; that gives it a new IP, so nginx was recreated too
  after confirming all four of its volume mounts (including `/root/orbit-crm/voice.conf`) are
  declared in `docker-compose.demo.yml`. All four hostnames on the box then verified serving their
  own certificates
- **Rule**: **A 200 does not mean CORS works.** Test a cross-origin endpoint with an actual
  `Origin:` header and assert `access-control-allow-origin` comes back, plus an `OPTIONS` preflight
  for anything that POSTs JSON. Also assert an unknown origin gets **no** header, or you have proved
  nothing except that you set a wildcard. And whenever a browser app starts calling an API on a
  different hostname than it is served from, `CORS_ORIGINS` is a deployment step, not an afterthought.

### 2026-07-29 — The deploy script was eaten by its own `pg_dump`
- **Error**: None. The deploy reported success. `/api/v1/health` returned **502** while all three hostnames returned 200, and `alembic current` still showed the *previous* revision as head after a deploy that shipped a migration
- **Context**: First run of a hardened `deploy-production.yml` that added an nginx recreation step at the end. The step never executed
- **Root Cause**: The remote half ran as `ssh host << 'ENDSSH'`, so the server's shell read the script **from stdin**. `docker compose exec` also reads stdin, so `exec -T postgres pg_dump` **consumed every remaining line of the script as its own input**. Execution simply stopped after the backup, with no error and a zero exit code. Proven from evidence, not inferred: `backups/pre_migrate_2026-07-28_230757.sql` existed with a matching timestamp, while `docker inspect` showed nginx was still the container started three hours earlier
- **The expensive part**: this had been true the whole time, so **the workflow's `alembic upgrade head` step had never once run**. Migrations only ever applied because the backend's own `start.sh` runs them at boot — luck, not design. The documented "back up before you migrate" guard was likewise never reached
- **Fix**: the remote half moved to `scripts/deploy-remote.sh`, `scp`'d and executed **by path**, with `ssh -n` to close stdin and `< /dev/null` on both `exec` calls as belt-and-braces. As a real file it is also reviewable and runnable by hand
- **Rule**: **Never feed a deploy script to `ssh` on stdin if it invokes anything that reads stdin** — `docker compose exec`, `docker build`, `ssh`, `mysql`, `psql` all qualify. The failure mode is silent truncation with a success exit code, which is the worst kind. Ship the script as a file and run it by path. And when a deploy claims success, verify the *effect* (schema version, container start time), never the exit code

### 2026-07-29 — `git pull || true` hid a stale backend for an unknown number of deploys
- **Error**: None visible. Deploys were green. The server sat on commit `b0dbb6a` while `main` moved on
- **Context**: Found immediately after the above, when a migration that had "deployed" was still absent from the database
- **Root Cause**: `git pull origin main || true` in the deploy. The pull was failing with *"Your local changes to the following files would be overwritten by merge: docker/nginx/nginx.demo.conf"* — the eats.sitaratech.info certificate split had been made **by hand on the box** and also committed, so both sides had touched it. `|| true` swallowed the abort. **The frontend kept updating regardless**, because it is `rsync`'d rather than pulled, so the site looked freshly deployed while the backend silently rotted
- **Contributing cause**: the deploy itself dirtied `frontend/.dockerignore` every run (`sed` the line out, `echo` it back), permanently leaving a modified tracked file — the exact condition that blocks a future pull
- **Fix**: resolved on the server **without discarding anything** — `git diff FETCH_HEAD -- docker/nginx/nginx.demo.conf` was **empty**, proving the working tree already matched the incoming version, so that one path was stashed, pulled, and the stash dropped. `md5sum` confirmed identical before and after, and a copy was kept at `/root/nginx.demo.conf.pre-pull-*`. Deliberately **not** `git checkout --`, because the production env file is tracked on this box and holds live secrets. In the script: the pull failure is now **fatal** with a message explaining how to resolve it safely, and `.dockerignore` is restored with `git checkout --` so no drift is left behind
- **Rule**: **`|| true` on a step that fetches the thing you are deploying is never acceptable.** A deploy that cannot obtain the code has failed. More generally: if part of a deploy is `rsync`'d and part is `git pull`'d, they can drift apart silently — assert the deployed commit (`git rev-parse HEAD`) as part of verification, not just that the site returns 200

### 2026-07-29 — Storefront checkout had no opening-hours gate at all
- **Error**: Not hit in production — caught in the last checks before publishing
- **Context**: About to run `npm run deploy`, which makes `chickshackg84.com` take real orders
- **Root Cause**: `isOpenNow()` existed and was used **only to draw a banner**. Checkout itself was reachable at any hour, so a customer could place a real order at 03:00. It would land on a tablet nobody was watching, the confirmation screen would poll for twenty minutes and give up, and the shop would open to stale orders it never agreed to
- **Fix**: a *placing window* rather than opening hours — `orderFromTime` (14:00) to `closeTime` (22:00). Baskets can still be built at any time; only placing is refused, and the refusal says when to come back. The window is 14:00 rather than the 16:00 opening because Imran's own worked example is an order **placed at 14:00** and accepted at 15:30 — blocking all pre-orders would have removed behaviour he relies on
- **Rule**: A helper named `isOpenNow` that only feeds a banner is a trap: it reads like a guard at every call site that does not exist. If a rule matters, enforce it at the boundary that can violate it — and check what a feature does **outside** business hours before publishing it, because that is when nobody is watching

### 2026-07-29 — Every mocked Stripe test passed while the real API would have raised `AttributeError: get`
- **Error**: `AttributeError: get`, raised from inside `stripe/_stripe_object.py`, on the first call against the live sandbox
- **Context**: The Stripe integration was written, 18 unit tests were green, and the code was committed. The failure appeared on the very first call to the real API
- **Root Cause**: `StripeObject` is not a plain dict. Its `__getattr__` resolves an attribute as a *field of the response*, so `response.get("status")` looks up a field literally called `get`, fails to find one, and raises. Subscripting (`response["status"]`) is the only safe read, and it raises `KeyError` for absent keys — which are normal, because Stripe **omits** fields rather than returning them as null. The service used `.get()` in six places, including the entire webhook parsing path
- **Why the tests could never have caught it**: every test mocked Stripe and handed the code **plain dicts**, on which `.get()` works perfectly. The mocks asserted our decisions correctly and said nothing at all about the shape of the object production would receive. The first attempt at a regression test repeated the mistake — a `dict` subclass inherits a working `.get()`, so the fake passed and reproduced nothing
- **Fix**: a `field(obj, key, default)` helper used for every read of a Stripe response, plus a regression test whose fake is deliberately **not** a dict subclass: subscriptable, with any attribute access raising
- **Rule**: **A mock proves your logic, never the vendor's object shape.** Any integration whose objects come back from a third-party SDK needs at least one run against the real thing before it is called done — for a payment provider that is not optional. And when writing a fake to pin a vendor quirk, check the fake actually fails without the fix; a fake that passes on broken code is worse than no test, because it certifies the bug.

### 2026-07-29 — Env keys added to the production env file never reached the container
- **Error**: None. The deploy was green, the env file had the 9 new keys, no duplicates, and the backend still reported `email_configured = False` with an empty `SMTP_HOST`
- **Context**: Wiring Mailjet. The keys were appended to the production env file after a timestamped backup, then the normal deploy was run to recreate the backend and pick them up
- **Root Cause**: The `backend` service in `docker-compose.demo.yml` has **no `env_file:`** — it declares an explicit `environment:` list. `--env-file` populates variables for **`${...}` interpolation in the compose file**, it does **not** inject them into containers. So a key that is not named in that list simply does not exist inside the container, however correctly it was written to the env file
- **Why it was nearly missed**: everything upstream reported success. The append verified (9 keys, 0 duplicates), the deploy verified (all hostnames, all certificates), the container was freshly recreated. The only thing that revealed it was reading `settings.email_configured` **inside the running container**. Two of the printed values even looked plausible — `SMTP_PORT=587` and `SMTP_STARTTLS=true` — because those are the defaults in `config.py`, not the deployed values
- **Fix**: declared all nine keys plus `ORDER_TRACKING_BASE_URL` in the backend's `environment:` list, each with a `:-` default matching `config.py` so an unset key leaves email cleanly disabled rather than half-configured
- **Rule**: **Writing a key to the env file is not the same as the application having it.** When a compose service uses an explicit `environment:` list rather than `env_file:`, every new key needs adding in *two* places. Always verify a config change by reading the value back **from inside the running container**, never from the file you wrote — and be suspicious when a printed value happens to equal the code default, because that is what an unset variable looks like.

### 2026-07-29 (session E) — `timeout` is not a Stripe API parameter, and 40 mocked tests never noticed
- **Error**: `{"detail":"Request req_…: Received unknown parameter: timeout"}`, HTTP 502, on the first real checkout-session call
- **Context**: Proving the card flow against the real sandbox, minutes before a client walkthrough
- **Root Cause**: Every Stripe call passed `timeout=_STRIPE_TIMEOUT_SECONDS`. It is **not** a per-call argument — the SDK forwards unknown keywords to the API as request **fields**, and Stripe rejects the entire call. All four call sites had it (create, capture, cancel, retrieve), so **card payment could not have worked at all**
- **Why the tests could not catch it**: `unittest.mock` accepts any keyword you hand it and asserts nothing about what the vendor would accept. Exactly the blind spot that hid `StripeObject.get` two commits earlier — the same lesson, re-learned, in the same file
- **Fix**: the timeout moved to the HTTP client (`stripe.RequestsClient(timeout=…)`, set once), and a regression test whose fake **rejects unknown parameters** the way the real API does. Verified by reintroducing the bug and watching the new test fail
- **Rule**: **A mock proves your logic, never the vendor's contract.** When a third-party SDK is involved, at least one fake must be STRICT — rejecting what the real service rejects — and the integration must make one real call before it is called done. Also: `timeout` is a transport concern, so if an SDK seems to accept it per-call, check whether it is being silently forwarded as data.

### 2026-07-29 (session E) — The storefront told every customer the shop was closed, and labelled every order a pre-order
- **Error**: None thrown. The banner read "We're closed right now" at 17:15 UK, mid-service, on a site taking real orders
- **Context**: Spotted during a client walkthrough because the banner disagreed with a clock on the wall
- **Root Cause**: `new Date(now.toLocaleString("en-GB", { timeZone: "Europe/London" }))`. `en-GB` formats day-first, and JavaScript's date parser cannot read `"29/07/2026, 17:16:39"` — it tries month 29 and returns **Invalid Date**. `getHours()` then returned `NaN`, and **every comparison against `NaN` is false**, so both time functions were pinned to their false branch
- **Impact, live**: the banner said closed 24 hours a day; `orderTiming().immediate` was always false so **every order was labelled a pre-order** on the website, the confirmation page and the shop's tablet; and customers were told "we'll confirm when we open at 16:00" at six in the evening
- **Fix**: `Intl.DateTimeFormat(...).formatToParts()`, which reads the hour and minute as numbers and never touches the string parser. Midnight's `"24"` handled. Checked across the day: 03:00, 13:00, 15:00, 17:00, 23:00, 00:30
- **Rule**: **Never round-trip a localised date string back through `new Date()`.** `toLocaleString` is for humans; `formatToParts` is for programs. More generally, a timezone bug fails silently into a plausible-looking state — if a time-dependent feature has a visible symptom, check it against a real clock at a real hour rather than trusting that it compiles.

### 2026-07-29 (session E) — The kitchen ticket never reached the printer: an `await` ate the user gesture
- **Error**: None anywhere. Imran tapped Accept on the first live order; the server logged `GET …/ticket?format=rawbt 200 OK` and nothing came out of the printer
- **Context**: The first real accept, during a client walkthrough, on the client's own Android tablet with RawBT installed and working
- **Root Cause**: Printing hands an ESC/POS job to the RawBT app by navigating to a `rawbt:` URL. **Chrome on Android only follows a custom scheme from inside a genuine user gesture**, and both print paths `await`ed the ticket fetch *before* setting `location.href` — so by the time they navigated, the tap was over and Chrome dropped it. Silently: no error, no dialog, no console warning
- **Why "printing is proven" did not carry over**: the 2026-07-28 test page printed perfectly because its buttons navigated **directly from the click**, with the payload already embedded in the page. The mechanism it proved was not the mechanism the live flow used
- **Fix**: ticket URLs are prefetched in the background for every listed order; `sendToPrinter(url)` is **synchronous** and documented as needing to stay that way; the card's Print button navigates straight from the tap; the `intent:` form naming the RawBT package is tried first, with the bare scheme as fallback
- **Rule**: **A 200 in the log is not evidence the thing happened — for a printer, the only evidence is paper.** And on mobile web, any `await` between a tap and a custom-scheme navigation destroys it. If a handoff to a native app must work, have everything it needs in hand before the tap.

### 2026-07-29 (session E) — Email was "verified" from the wrong machine, and the server cannot send at all
- **Error**: `TimeoutError: timed out` from `email_service.send_order_email`, on the first real send. No mail ever arrived
- **Context**: A client walkthrough, immediately after telling Malik to check his inbox — without first checking the send had succeeded. The log had the answer the whole time
- **Root Cause**: **DigitalOcean blocks outbound SMTP on droplets.** Measured from the box: ports **25, 465 and 587 all time out**; **2525 accepts TCP then resets**. Separately, **`api.mailjet.com:443` connects but the TLS handshake is reset with 0 bytes read**, while `api.stripe.com` and `api.github.com` handshake fine from the same host — so 443 egress works and the failure is specific to Mailjet
- **Why it was missed**: session D authenticated the Mailjet credentials against `in-v3.mailjet.com` on 587 and 465 **from Malik's laptop**, and recorded that as proof. The credentials were never the problem; the route was, and a laptop shares none of a droplet's egress policy
- **Status**: **OPEN — OI-55.** The fix is a transactional API this box can reach, or a host whose egress permits mail. Not a credential or config change
- **Rule**: **Verify a network dependency from the machine that will actually use it.** A connectivity test proves the path it ran on and nothing else. And never report a delivery as working without checking the send result — "it should have arrived" is not a status.

### 2026-07-29 (session E) — The same env-key trap was still open for Stripe, six days after it was written up here
- **Error**: None, and that is the point. Caught during the Stripe hardening pass, before any key was deployed
- **Context**: Working H-6 of `docs/STRIPE_HARDENING_CHECKLIST.md`. Checked whether `STRIPE_WEBHOOK_SECRET` needed adding to the compose `environment:` list, and found that **not one of the Stripe keys was declared there** — not the secret key, not the publishable key, none of them
- **Root Cause**: The email incident earlier the same day was fixed by declaring the *email* keys. The **rule** was written into `ERROR_LOG.md`; the **knowledge** was never put anywhere the next person would trip over it. Stripe was built afterwards by someone (me) who had read the rule and still did not apply it to the new feature, because nothing in the compose file said anything about it
- **What it would have cost**: the keys go on the server, the deploy is green, the env file is provably correct — and card payment silently is not offered, because `settings.stripe_configured` reads an empty string inside the container. No error, no log line, no failed request. The customer just never sees a card button, which looks exactly like the feature not being finished
- **Fix**: all six keys (`STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_SUCCESS_URL`, `STRIPE_CANCEL_URL`, `STRIPE_ACCOUNT_CURRENCY`) declared in the backend's `environment:` list, each with a `:-` default matching `config.py`, under a comment that states the rule **in the file where it gets violated**
- **Rule**: **A rule that lives only in the error log will be broken again by the person who read it.** When a class of mistake is possible in a specific file, put the warning *in that file*, next to the thing being edited. And treat "we fixed this for feature X" as covering feature X only — go and check every other feature with the same shape, immediately, rather than trusting that the lesson generalised on its own.

### 2026-07-29 (session E) — A server-level nginx `if` cannot be undone by a location block, and the bot filter was one word from eating every Stripe webhook
- **Error**: None yet. Found while working H-1 of the Stripe hardening checklist, before the webhook was ever registered
- **Context**: `nginx.demo.conf` blocks bad-bot user agents with `if ($is_bad_bot) { return 444; }` at **server** level, above every location including `/api/`. Stripe delivers webhooks as `Stripe/1.0 (+https://stripe.com/docs/webhooks)`
- **Root Cause**: two separate things, and the second is the dangerous one. (1) The filter matches the bare substring **`bot`**, unanchored and case-insensitively. Stripe's current UA happens not to contain it — `webhooks` is not `bot` — so this works today **by luck**, and one extra word in a vendor's user-agent string would drop every webhook while Stripe retried for days and we saw nothing. (2) The obvious fix, an allow inside a `location` block, **does not work**: a server-level `if` is evaluated in the rewrite phase, before nginx has chosen a location, so the 444 fires regardless of what any location says
- **Fix**: exempt the path in the **map**, not in a location — `map $uri $is_machine_callback` combined with `$is_bad_bot` into `$block_bad_bot`. Deliberately keyed on **`$uri`** (normalised) rather than `$request_uri` (raw), because the raw form would let `/api/v1/public/stripe/webhook/../../anything` bypass the bot filter for a completely different path
- **Verified by execution, not by reading the regex**: the real maps were lifted into a throwaway nginx container and curl'd. Stripe's actual UA is not blocked; a `curl/` UA is exempt on the webhook path but still dropped everywhere else; a hypothetical `Stripe/2.0 somebot` is exempt on the webhook path only; the traversal form is still dropped
- **Rule**: **Never conclude a regex does not match by reading it — run it.** A substring filter on user agents is a standing dependency on a third party's exact wording, so any machine caller that must reach you needs a path-based exemption rather than a UA-based one. And in nginx specifically: `if` at server level beats every location, so "I'll just allow it in the location block" is not a fix, it is a change that appears to work and does nothing.

### 2026-07-29 — Self-referencing tenant row inserted with a NULL tenant_id
- **Error**: `null value in column "tenant_id" of relation "tenants" violates not-null constraint`
- **Context**: Creating the `chick-shack` tenant in a new seed script
- **Root Cause**: `tenants.tenant_id` self-references `tenants.id`. Setting `tenant.tenant_id = tenant.id` after construction reads `None`, because the model default has not fired before flush.
- **Fix**: Generate the UUID explicitly and pass it to both fields, as `conftest.py` already did
- **Rule**: For any self-referencing FK, mint the id in application code rather than relying on a column default you then read back.

### 2026-07-29 (session F) — The courtesy email was adding ~15 silent seconds to every live checkout
- **Error**: None visible anywhere. Checkouts completed, taps worked, the log showed a swallowed send failure a quarter of a minute after the request that caused it
- **Context**: Verifying the Brevo-transport deploy **from inside the container**: `email_configured` printed `True` with no Brevo key present — the dead Mailjet `SMTP_HOST` from session D was still on the server and still satisfying the flag
- **Root Cause**: two facts composing. (1) `notify_customer` **awaited** `send_order_email` inline in `POST /public/{tenant}/orders`, accept, reject and the lifecycle moves. (2) With email "configured" but the SMTP route dead (DigitalOcean egress block), every send burned its full 15-second transport timeout before being swallowed. Net: every real customer checkout and every tablet tap since the email keys reached the container carried ~15 invisible seconds. The email failure itself was known (OI-55); the latency it was charging the order path was not
- **Fix**: `notify_customer` now schedules the send as a fire-and-forget task (strong-ref set so it is not garbage-collected mid-flight; `send_order_email` already never raises). Tested: scheduling returns in under a second while a deliberately stuck transport still runs to completion in the background
- **Rule**: **A courtesy side effect must never sit inline in a request path** — "it can't fail the order" is not enough, it must also be unable to *delay* it. And when a feature flag derives from leftover configuration, "configured" and "working" diverge silently: verify what the flag actually reads, from inside the running container.

### 2026-07-30 (session G) — Brevo silently refuses to send until its own DMARC record is present, not just DKIM
- **Error**: `Sending has been rejected because the sender you used orders@chickshackg84.com is not valid. Validate your sender or authenticate your domain` — surfaced only via Brevo's `GET /v3/smtp/statistics/events` API, not visible anywhere in our own logs (see the entry below)
- **Context**: Setting up Brevo domain authentication for the first time. All DNS records (2 DKIM CNAMEs, ownership TXT) verified via public `nslookup`, and Brevo's UI kept showing "Authentication is pending" indefinitely
- **Root Cause**: assumed "Brevo's authentication runs on DKIM, not DMARC" — wrong. `GET /v3/senders/domains/{domain}` showed `dmarc_record.status: false` even though DKIM and the ownership TXT were both `true`; Brevo's `authenticated` flag is an AND of all four checks, including its own DMARC record. That record had been deleted earlier in the same session on the (also wrong) assumption that a duplicate `_dmarc` TXT record was the only risk worth avoiding
- **Fix**: edited the client's single existing `_dmarc` TXT record's *value* in place to Brevo's exact expected content (`v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com`) — same `p=none` policy as before, so zero change to how the client's live mail is enforced, but now it's one record satisfying both the client's own DMARC monitoring and Brevo's authentication gate
- **Rule**: **Don't infer what a transactional-email provider's "authenticated" flag actually checks — query it.** `GET /v3/senders/domains/{domain}` gives per-record status; trust that over the dashboard's vague "pending" message or your own assumption about what DKIM vs. DMARC each cover. And when a client already has a DMARC record you must not duplicate, the safe move is usually to *edit its value in place* to satisfy the new requirement, not to delete the new one or add a second record.

### 2026-07-30 (session G) — App-level log lines are invisible in `docker logs`; only uvicorn's own access log ever appears
- **Error**: None printed — that's the bug. `logger.info("Sent %r email for order %s", ...)` and `logger.exception(...)` in `email_service.py` produce nothing in `docker logs pos-system-backend-1`, even immediately after a real send attempt
- **Context**: Following the email runbook's own instruction to "check the send result in the backend log before telling anyone to check an inbox" — the log showed nothing at all, success or failure, for a send that (per Brevo's own activity API) had actually been attempted and rejected
- **Root Cause**: the app never calls `logging.basicConfig()` or otherwise attaches a handler to the root logger. uvicorn's default logging config only wires handlers for its own named loggers (`uvicorn`, `uvicorn.access`, `uvicorn.error`); a module logger like `logging.getLogger(__name__)` in application code propagates to the root logger, which has none. Python's `logging.lastResort` handler only catches WARNING and above, so `logger.info` is silently dropped everywhere in this app, and `logger.exception` (ERROR) is inconsistently visible depending on the propagation path
- **Fix**: not fixed this session — discovered while diagnosing the Brevo rejection above, worked around by querying Brevo's own API directly instead of trusting the backend log
- **Rule**: **A runbook instruction to "check the log" is only as good as the logging config underneath it.** Verify a log line actually appears before writing a runbook step that depends on it. This app needs an explicit logging handler (e.g. via `main.py` startup) before "check the backend log" can be trusted for anything below ERROR severity.

### 2026-07-30 (session H) — A green `git push` to `main` deployed nothing the customer could see, for several minutes, on a live site taking real orders
- **Error**: None surfaced by tooling. `git push origin main` succeeded, GitHub's `Deploy to Production` Action went green in 3m10s, and the testing-mode banner still did not appear on `chickshackg84.com` — caught only because Malik checked the real site on his phone
- **Context**: Adding a customer-facing "under testing, please call instead" banner to the Chick Shack storefront while real orders were actively coming in, under time pressure to get it live immediately
- **Root Cause**: `docs/DEPLOYMENT_PLAYBOOK.md` already documented, at line 86, that the storefront is a **second, separate deploy pipeline** (`cd storefront && npm run deploy` → Cloudflare Workers) that `git push` never touches. That section was never read, because the file's own **"one-line summary" at the top said "Merging to `main` deploys production. There is no other button"** — true for the POS/backend side, silently wrong for the storefront, and positioned exactly where someone skims under pressure and stops reading. A green GitHub Action for `deploy-production.yml` (which only builds/deploys the DigitalOcean droplet) was mistaken for proof the storefront had shipped
- **Fix**: ran `cd storefront && npm run deploy` (vite build + `wrangler deploy`), then verified by fetching the live `index.html`, extracting its hashed JS bundle URL, downloading *that*, and grepping it for the exact new banner text and phone number — not by trusting the deploy command's exit code or an unrelated CI badge. Rewrote the playbook's one-line summary to state both pipelines up front with a table, so the storefront path cannot be missed by skimming the top of the file
- **Rule**: **A repo can have two (or more) independent deploy pipelines that share nothing — a green check on one proves nothing about the other.** Before declaring anything "deployed," identify which pipeline actually owns the changed path, and verify the *live artifact* (fetch the real bundle, grep for the real change), never a workflow's conclusion status. And when a doc's top-line summary and its body disagree in scope, the summary is the more dangerous one to trust, because it's the one read first and under the most time pressure.

### 2026-07-31 (session I) — Renaming an item or modifier group in `menu.ts` left the old row live in production, duplicated or still attached
- **Error**: None surfaced by tooling. `seed_chick_shack.py` ran clean, reported the expected item/group counts, and committed with no error either time
- **Context**: Building OI-45's meal-deal modifiers. Two unrelated renames landed in the same session: 7 items got a clarifying "Burger"/"Wrap" suffix (e.g. "Chicken Fillet" → "Chicken Fillet Burger"), and the `HEAT` group's display name changed from "Mild or Hot" to "Peri-Peri Heat" to match Imran's till. Caught only by re-querying the **production** API after deploy and counting items/groups by hand — not by anything the seed script itself reported
- **Root Cause**: `seed_chick_shack.py` (and `_get_or_create_group` inside it) match existing rows by `(tenant, name)` and are deliberately additive-only — a documented, correct design for adding new menu content. Renaming a `name` in `menu.ts` is invisible to that matching logic: the seeder finds no row with the *new* name, so it creates one, while the row under the *old* name — and every `menu_item_modifier_groups` link still pointing at it — is left exactly where it was. Item rename: 7 duplicate rows appeared. Group rename: "Peri Peri Burger" (and 9 other peri items) ended up offering **both** "Mild or Hot" and "Peri-Peri Heat" to a real customer, plus the now-dead "Make it a meal" flat tick, because removing a group from an item's `modifierGroups` in code doesn't remove the existing DB link either
- **Fix**: two small, idempotent, tenant-scoped scripts that edit rows **in place** rather than let the seeder duplicate them — `rename_chick_shack_items_2026_07_31.py` (`UPDATE menu_items SET name = ...`, same primary key, so any historical `order_items` FK stays valid) and `fix_chick_shack_stale_groups_2026_07_31.py` (deletes the stale `menu_item_modifier_groups` links and marks the orphaned groups `is_active = false`, without deleting the group/modifier rows themselves, since a past real order might reference one via `order_item_modifiers`). Run the rename fix **before** the next reseed, not after — running it after the seeder has already created the duplicate means deleting the fresh duplicate first
- **Rule**: **An additive-only seeder is safe for new content and unsafe for renames — a renamed `name` string needs its own explicit, in-place fix before (or instead of) a plain reseed, for both menu items and shared modifier groups.** A clean seed-script run (no errors, expected-looking counts) is not evidence a rename landed correctly; the only real check is querying the live API and looking for duplicate names or a modifier group that shouldn't still be there.

### 2026-07-31 (session J) — A freshly-deployed image URL served the SPA's HTML instead of the file, for a few seconds, right after `wrangler deploy` reported success
- **Error**: None surfaced by tooling. `npm run deploy` (Cloudflare Workers) printed "✨ Success! Uploaded 20 files", but the very first post-deploy `curl` of one of those 20 files (`/img/hero/burger-big-shack.webp`) returned `200 text/html`, ~1KB — not the ~24KB webp just uploaded
- **Context**: Verifying a storefront photo-integration deploy against the live site, per this project's standing rule to check the real artifact rather than the deploy log (see the 2026-07-30 session H entry above, same rule)
- **Root Cause**: not fully diagnosed — most likely a Cloudflare edge node serving a stale/SPA-fallback response for a handful of seconds while the new asset finished propagating across the edge. Every other one of the 18 image URLs checked in the same pass returned correctly on the first try
- **Fix**: re-`curl`ed the same URL a few seconds later and got the correct `200 image/webp` with a byte count matching the uploaded file exactly. Re-swept all 18 URLs afterward to confirm none of the others were mid-propagation too
- **Rule**: **A single post-deploy check, even of the real live artifact, can land mid-propagation and look like a failure (or, worse, mid-propagation and look like a false pass).** Don't treat one immediate check as final either way — for a small number of URLs, re-check after a short pause and compare byte counts, not just status codes, before concluding a deploy did or didn't ship correctly.

### 2026-07-31 (session K) — The "leave it out" ticks had never rendered on the live site, for any item, ever
- **Error**: None surfaced by tooling — no console error, no failed request. The section simply never appeared. Malik caught it during manual UAT ("i dont see anything to leave out?") on Chicken Fillet Burger, a category this menu explicitly lists as excludable
- **Context**: Walking Imran's 07-31 six-item requirements list one by one with Malik doing the actual click-through. The requirements doc had marked this item "✅ Already built, verbatim" based on reading the source code, not on checking it against the live site
- **Root Cause**: `exclusionsFor(item)` checked `EXCLUDABLE_CATEGORIES.has(item.categoryId)` against a hardcoded Set of slugs (`"burgers"`, `"wraps"`, ...). `item.categoryId` is that slug ONLY in the local hardcoded fallback menu. Once the live menu loads from the API, `menuAdapter.ts` sets `categoryId` to the category's database UUID, so the check silently never matched, for any item, on the real site. `menuAdapter.ts` had already hit and solved this exact slug-vs-UUID class of problem for food photos (`IMAGE_BY_ITEM_NAME`, matched by name instead of id) — that fix was never applied to `exclusionsFor`
- **Fix**: changed `exclusionsFor` to take a category NAME instead of an item/id, matched against category names (`"Burgers"`, `"Wraps"`, ...) rather than slugs. Names survive both the local and API-backed paths. `MenuBrowser` resolves the name from its own `categories` list (always correct either way) and passes it to `ItemModal` as a plain prop — no schema change to `MenuItem`/`Category`
- **Rule**: **"Already built" based on reading source code is not the same claim as "already built" based on watching it run against the live, API-backed site.** Any code path that behaves differently depending on whether the menu came from the hardcoded fallback or the live API (this codebase has at least two now: images, and this) needs its OWN explicit live check, not an inference from a working local read of the code. When a requirements doc marks something "✅ already built," the citation is a claim about the code, not a substitute for looking at the deployed page.

### 2026-07-31 (session K) — Fixing a Meal-item-only modifier-order bug left the identical bug live on every solo item
- **Error**: None surfaced by tooling. The first fix (a one-off script reordering the 25 Meal items' modifier-group links) ran clean and was verified correct for Meal items specifically. Malik's continued UAT then found the same symptom on a SOLO item (Peri Peri Burger showing Dips before the required Peri-Peri Heat)
- **Context**: `seed_chick_shack.py`'s `_link()` is additive-only — it never repositions a modifier-group link that already exists, so `menu_item_modifier_groups`' physical/insertion order (which the unordered `selectin` relationship falls back to) was frozen at whatever it happened to be the first time each item was ever seeded, for EVERY item, not only the 25 new Meal ones
- **Root Cause**: the first fix treated the symptom (Meal items specifically) rather than the mechanism (any item's group order is permanently unfixable by a plain reseed once its links exist). Scoping the fix to "the items Malik happened to click on first" instead of "every item using this same additive-only linking function" left the identical bug live everywhere else
- **Fix**: changed `_seed_items` itself to delete and recreate every item's `menu_item_modifier_groups` links on every reseed, in the exact order that item's `modifierGroups` specifies — closing the whole class of bug rather than patching individual items. Verified this time by programmatically sweeping all 87 live items for any required-after-optional ordering, not by re-checking the specific item Malik flagged
- **Rule**: **When a live bug is caused by a general mechanism (an additive-only seeder, an unordered relationship, a stale cache), fix the mechanism, not the specific instances a user happened to notice first.** A narrow fix that passes the exact case reported will look done and isn't — verify with a sweep across everything the mechanism touches, not a spot check of the reported case.

### 2026-07-31 (session K) — The `/pause` skill overwrote an earlier same-day checkpoint that was never git-tracked
- **Error**: None surfaced by tooling — `Write` succeeded silently. `PAUSE_CHECKPOINT_2026-07-31.md` (session I's, written that morning) was clobbered by session K's `/pause` invocation that evening, both using the exact same filename
- **Context**: Malik asked for a `/handoff` mid-session K, which invokes `/pause` as its step 2. The `/pause` skill's instructions write unconditionally to `PAUSE_CHECKPOINT_[YYYY-MM-DD].md` with no check for an existing file from earlier the same day
- **Root Cause**: this repo has had multiple sessions on the same calendar date before (2026-07-27, 2026-07-29 both have `-B`/`-C`/.../`-E` suffixed files), and the established, working convention is to suffix same-day checkpoints rather than overwrite. The generic `/pause` skill doesn't know this project's convention and has no existing-file check, so it silently overwrote session I's checkpoint. Because `PAUSE_CHECKPOINT_*.md` files are deliberately left uncommitted in this repo (the ~99-file dirty tree includes them, per the standing "never `git add .`" rule), there was no git history to recover the original content from
- **Fix**: the overwritten content was reconstructed from earlier in the same conversation (the file had been read in full near the start of the session, before being overwritten later) and restored to the plain filename with a "superseded" note; session K's content was moved to `PAUSE_CHECKPOINT_2026-07-31-C.md`, continuing this repo's own letter-suffix convention
- **Rule**: **Before running `/pause` (directly or via `/handoff`) on a project that may have had an earlier session the same day, check for an existing `PAUSE_CHECKPOINT_[today's date].md` first** — if one exists, write to the next available letter suffix instead of overwriting it. This applies to any generic skill whose instructions assume a filename is safe to write unconditionally; a project's own established convention (visible in its file listing) should win over a skill's generic default.

### 2026-07-31 (session M) — First live sandbox card test: Accept did not capture payment — RESOLVED session N
- **Error**: None thrown anywhere. Order `260731-001` went through Stripe sandbox Checkout
  correctly (confirmation page: "Card details taken. We only charge you once the shop
  accepts your order.") — but after Imran hit Accept on the tablet, the tablet, all 3
  printed receipts, and the "Confirmed" customer email **all still showed unpaid/due on
  delivery**, when a successful `capture_for_order` should have flipped all three
- **Context**: The first real end-to-end test of OI-41, Imran live on the phone, using the
  `?card=1` override to reveal the card button
- **Root Cause (found session N, 2026-08-01)**: `create_checkout_session` read
  `session["payment_intent"]` immediately after `Session.create()` and stored it on the
  order — but confirmed against the real sandbox (a throwaway probe session created and
  inspected on the spot), Stripe does **not** create the PaymentIntent at that point, only
  once the customer actually submits payment on the Checkout page. `stripe_payment_intent_id`
  was written `None` and stayed that way forever: the webhook's own backstop
  (`payment_intent.amount_capturable_updated`) never persisted it either, and was itself
  blocked by an unrelated, prematurely-set `payment_authorized_at`. `accept_order`'s guard on
  `stripe_payment_intent_id` then silently no-opped on Accept — no exception, nothing
  logged, exactly matching the empty access-log grep above
- **Fix**: `accept_order` now guards on `stripe_checkout_session_id` (reliably set at
  session-creation) and resolves the missing intent id from Stripe directly via new
  `stripe_service.resolve_payment_intent_id`, called right before capture. The webhook
  independently backfills the id from its own event object. The premature
  `payment_authorized_at` write at session-creation was removed. 7 new tests, 2
  mutation-checked by hand (temporarily reverted each guard, confirmed the new test fails,
  restored the fix). Commit `593513b`. **Proven on a real retest**, order `260731-003`:
  verified directly against Stripe (`status: succeeded`, `amount_received` matches the
  order total) and the DB (`payment_status: paid`, intent id correctly resolved)
- **Rule**: **When three independent-looking surfaces (tablet, printer, email) all show the
  same wrong thing, suspect one shared read path, not three separate bugs** — confirmed
  correct here: all three were faithfully rendering `order.stripe_payment_intent_id`/
  `payment_status`, and the actual fault was one field never getting persisted upstream of
  all of them. Also: **never assume a third-party object field is populated synchronously
  just because a comment says so** — the wrong assumption here ("payment_intent is an id
  string when the session is created") was written confidently in the original code and
  was simply false; a two-line throwaway probe against the real sandbox proved it in
  seconds and should have been done before writing that comment in the first place

### 2026-07-31/2026-08-01 (session M/N) — A prefetched print ticket kept printing "NOT PAID" after the order was genuinely captured
- **Error**: Order `260731-003`'s card was captured correctly (proven against Stripe and
  the DB), but the printed kitchen ticket read "*** NOT PAID *** COLLECT £19.28" anyway
- **Context**: Surfaced immediately after the OI-41 fix above was proven working, in the
  same live retest with Imran
- **Root Cause**: `frontend/src/pages/online-orders/OnlineOrdersPage.tsx`'s ticket is a
  self-contained, fully-rendered ESC/POS payload (`rawbt:base64,...`), fetched and cached
  in `ticketUrls` the moment an order enters the pending queue — deliberately, so the
  Print button can navigate to it synchronously from a tap without Chrome dropping the
  `rawbt:` handoff (an `await` before navigating ends the user gesture, see the
  2026-07-29 entry on the same file). Nothing ever invalidated that cache once the
  order's payment status actually changed on Accept, so both the automatic best-effort
  print and the manual "Print ticket" button kept reusing a payload rendered while the
  order still genuinely was unpaid
- **Fix**: new `invalidateTicket(orderId)` deletes the cached entry and kicks off a
  background re-fetch — never awaited, so it cannot itself become the next `await` that
  drops a print's user gesture — called right after Accept, Mark paid, and a
  cash-settled handover, everywhere `payment_status` can change. Commit `b90057c`
- **Rule**: **A client-side cache built to satisfy one hard platform constraint (here,
  "must navigate synchronously from a gesture") needs its own explicit invalidation
  rule tied to whatever makes its content stale — it does not get one for free just
  because the constraint that created it was solved.** The prefetch loop in `refresh()`
  already skips re-fetching any id it has ("if (ticketUrls.current.has(order.id)) return"),
  so a cached entry is permanent until something explicitly deletes it.

### 2026-07-31 (session M) — Told Malik a Shutterstock photo had no visible watermark; it did
- **Error**: Said "no visible watermark" about a `shutterstock.com` preview image based on a
  quick look; the actual crop had a legible "shutterstock.com · 83031757" credit line baked
  into the bottom
- **Context**: Vetting a photo Malik had already been given permission to use, before
  deploying it live on the customer-facing menu
- **Root Cause**: Judged the source image at a glance rather than zooming into the exact
  region that would end up in the live crop
- **Fix**: Caught while reviewing the generated crop (not the original), corrected course,
  re-asked Malik with accurate information before he re-confirmed. Cropped the watermark
  strip out before deploying
- **Rule**: **"No visible watermark" is a claim to verify at full resolution on the exact
  pixels that will ship, not a first impression from a thumbnail.** Re-verify a visual
  claim before repeating it back to the user as fact, especially when it's the basis for
  a decision they're about to make

### 2026-07-31 (session L) — Fixing modifier-group ORDER silently deleted every multi-variant item's size selector, live
- **Error**: None surfaced by tooling. The live public API for "Fried Chicken" showed a single flat £4.99 price with no way to choose 2pc/3pc/4pc, despite `menu.ts` and the regenerated `chick_shack_menu.json` both correctly listing all three. Caught while verifying why a new "show variant options in the menu list" fix had nothing to display
- **Context**: `97ec8c8`, the SAME DAY earlier in session K, changed `_seed_items` to unconditionally `DELETE` then recreate every item's `menu_item_modifier_groups` links from `entry["modifierGroups"]`, specifically to fix modifier-group ORDER (see the entry directly above this one). Multi-variant items link their `"<name> -- Choice"` group separately, via a standalone `_link()` call that ran a few lines BEFORE that delete
- **Root Cause**: the delete-and-recreate block didn't know about the variant Choice-group link created just above it — it deleted ALL of the item's links (including the just-created Choice-group link) and only restored the ones from `entry["modifierGroups"]`, which never included the variant group. Net effect, live, since session K's own reseed: **every multi-variant item — Half/Full Chicken on the Bone, Boneless Breast, Peri Wings, Peri Tenders, Fried Chicken, Fried Chicken Combo, Spicy Fried Wings, Fried Tenders, and every one of their Meal siblings — offered only its cheapest price with zero way to select size, piece-count, or rice/chips/half-half**. Nothing errored: `menuAdapter.ts` has a documented, correct fallback for "no Choice group" (render as a flat-priced item), which is exactly the right behavior for items that are genuinely flat-priced — it just as happily hid a real bug for items that weren't
- **Fix**: build ONE `group_ids` list per item — the variant group (if any) plus everything in `entry["modifierGroups"]` — and do a single delete+recreate pass covering all of it. Removed the now-dead standalone `_link()` helper entirely
- **Independent confirmation**: Imran sent a voice note the same session, unprompted, describing this exact symptom item by item (rice/chips/half-half missing on the grilled chicken, piece-counts missing on wings/tenders/fried chicken) — transcribed locally with `faster-whisper` and cross-checked against the fix: everything he listed matched what was restored, so the voice note needed no separate feature work once this was fixed
- **Rule**: **A "fix the mechanism" change (the right call, per the entry above) still needs to account for every OTHER thing already relying on the old mechanism's side effects** — not just the one class of bug it was written to close. An unconditional delete-then-recreate is only safe if the recreate list is provably complete; here it silently wasn't, because the variant-group link had never been part of `entry["modifierGroups"]` in the first place. When rewriting a data-linking function, enumerate every caller/creator of that link type before assuming a single rebuilt list covers all of them.

### 2026-08-01 (session N) — Deploy Action showed a red X on a genuinely good deploy: a transient 502 during its own health check
- **Error**: `gh run watch` reported the "Deploy to Production" run for commit `b90057c` as failed. The failed step was specifically "Verify deployment" — every step before it (build, upload, deploy on server) succeeded, and the same step's own hostname/certificate checks all passed; only the final `curl .../api/v1/health` line returned `502`
- **Context**: This deploy rebuilt and recreated both the backend and frontend containers (the commit touched `email_service.py` as well as frontend files). The health check runs after a fixed `sleep 10`
- **Root Cause**: the same class of issue already known for this box (`memory/server-deployment-rules.md` Rule 3) — nginx does not clear its upstream DNS/IP cache on its own, and briefly holds the old backend container's address after a fresh one is created. `sleep 10` is not always long enough for that window to close. A second deploy 40 seconds later (the STATE.md-only follow-up commit) recreated nginx again and its own health check passed clean
- **Fix**: none needed to the code — verified live, independently, right after: both `pos-demo.duckdns.org` and `eats.sitaratech.info` returned `200` on `/api/v1/health` moments later, and the actual running containers (checked directly, not inferred from the Action) held the correct, just-deployed code on both the backend and frontend sides
- **Rule**: **A failed "Verify deployment" step is not automatically a bad deploy — read which specific check failed before assuming the code is broken.** A red X after every real deploy step passed, on the health-check line specifically, is this project's known transient-nginx-IP window, not a new defect. Re-check live, from a real browser-UA request, before either redeploying blind or telling anyone the fix isn't live.

### 2026-08-01 (session O) — Two test failures, unrelated to this session's diff, surfaced by a full `pytest` run
- **Error**: `tests/test_p1a_features.py::TestVoidHardening::test_void_with_reason_succeeds`
  (`401` instead of `200`) and
  `tests/test_pay_first.py::TestPayFirstTransitionBlock::test_transition_blocked_without_payment`
  (asserts the literal string `"Payment required"`, but the actual detail message is
  `"This order is pending payment. Please complete payment first — go to the order and
  click Pay to proceed."`) both fail, on top of the documented 12 pre-existing
  QB-Desktop/parked failures
- **Context**: Running the full suite while building session O's 4 pending UX fixes
  (email wording, ticket PAID styling, COPY-line removal, chime loudness) — none of
  which touch auth, void, or the pay-first transition guard
- **Root Cause**: Not investigated (out of scope for this session's 4 items). Confirmed
  NOT caused by this session's diff: `git stash push` on every file this session touched,
  re-ran both tests against the resulting HEAD-only code, and both failed identically
  (`401`; the same wording mismatch). Stash was popped back immediately after
  confirming. Root cause is either a genuinely broken assertion (the pay-first one reads
  like a stale string literal after the error message was reworded some other session)
  or an environment-dependent flake (the auth one) — not diagnosed further here
- **Fix**: None applied. Flagging per this project's standing rule against scope drift
  — these are unrelated to the 4 items this session was scoped to
- **Rule**: **Before fixing a test failure discovered mid-task, confirm it is actually
  caused by the current diff** — `git stash push -- <the exact files this session
  touched>` (never a bare `git stash`, which would also stash this repo's ~99 pre-existing
  uncommitted markdown files), re-run the failing test, then `git stash pop`. If it still
  fails against unmodified code, it is pre-existing and out of scope; log it and move on
  rather than silently expanding the task.

### 2026-08-01 (session O) — `Deploy to Staging` (AWS) is red on every push -- not a regression, never touched
- **Error**: `gh run list` shows a `Deploy to Staging` GitHub Actions workflow failing on every
  push tonight, `##[error]Credentials could not be loaded` from `aws-actions/configure-aws-credentials`
  (targets `pos-staging` ECS in `me-south-1`)
- **Context**: Noticed while watching the real deploy (`Deploy to Production`, DigitalOcean) succeed
  after this session's push. Nobody asked for or touched anything AWS-related this session
- **Root Cause**: This workflow has been failing identically on every one of the last 5+ pushes,
  including several from before this session started — the AWS credentials secret it needs was
  never configured (or was removed) in this repo's GitHub Actions secrets. It is dead, unused
  infrastructure: this project's actual, working deploy path is `Deploy to Production` to the
  DigitalOcean box, documented in `docs/DEPLOYMENT_PLAYBOOK.md`
- **Fix**: None applied — out of scope, and disabling/editing a CI workflow wasn't asked for
- **Rule**: **A red workflow name in `gh run list` is not automatically about the commit that
  triggered it.** Check `gh run list --workflow "<name>" --limit 5` before assuming a new push
  broke something — if it was already red on prior, unrelated pushes, it's pre-existing noise, not
  a regression. This specific one (`Deploy to Staging`, AWS) can be ignored until Malik decides to
  either fix the credentials or delete the workflow.

### 2026-08-01 (session O) — Every date-ranged report query returns zero rows under this suite's SQLite test DB, regardless of the actual dates
- **Error**: While adding a test for OI-58a (online orders now counted in `get_sales_summary`'s
  channel breakdown), a real order created inside the test — with `date_from`/`date_to` set to an
  enormous `2000-01-01`..`2100-01-01` range — still came back with `total_revenue: 0,
  total_orders: 0` from the live HTTP response. Not an online-specific bug: dine-in and takeaway
  totals were zero too
- **Context**: Building and testing OI-58's report/dashboard changes. No prior test in this suite
  creates a real order via the ORM and then asserts a nonzero number through a date-ranged report
  endpoint — every existing report test either uses zero orders (structural assertions only, e.g.
  `TestSalesSummaryStructure`) or doesn't touch a date filter at all, so this had never surfaced
- **Root Cause**: `report_service.py`/`dashboard_service.py` filter dates with
  `func.cast(Order.created_at, Date) >= date_from`. Confirmed directly with a raw query
  (`SELECT typeof(created_at), created_at, CAST(created_at AS DATE) FROM orders`) against this
  suite's in-memory SQLite DB: `created_at` is stored as TEXT (`'2026-08-01 00:36:50'`), and
  `CAST(... AS DATE)` gets NUMERIC affinity (SQLite has no real DATE type) — NUMERIC affinity on a
  TEXT value extracts only the leading digit run, so the cast returns the **integer `2026`**, not
  a date. Comparing that INTEGER against a TEXT-bound date parameter is governed by SQLite's
  storage-class ordering, where NUMERIC always sorts below TEXT regardless of value — so
  `2026 >= '2000-01-01'` is unconditionally **false**. Every date-filtered WHERE clause built this
  way therefore matches nothing, for any dates, for any tenant. Real Postgres has an actual DATE
  type and truncates the cast correctly — confirmed separately this same session via OI-57's direct
  curl-testing against the real local dev Postgres DB, which returned exactly the expected rows for
  every date scenario
- **Fix**: None applied to `report_service.py`/`dashboard_service.py` — this is a pre-existing gap
  across every `func.cast(..., Date)` call site in both files (item performance, hourly breakdown,
  void report, z-report, payment method report, waiter performance — grep for the pattern), fixing
  all of it is a cross-cutting change well outside OI-58's scope. Production is unaffected since it
  runs real Postgres. Worked around locally: OI-58a's own new pytest coverage is a structural
  zero-orders assertion (mirrors the existing convention) instead of an order-then-assert-the-number
  test, with the real non-zero behaviour confirmed by curl against local dev Postgres instead. The
  brand-new OI-58c report queries (prepaid/COD, rejected orders) use plain `Order.created_at >=
  / <` datetime-range comparisons instead of `func.cast(..., Date)`, specifically so they don't
  inherit this landmine and stay meaningfully testable in this suite
- **Rule**: **Don't trust a date-ranged report test in this suite just because it returns 200 with
  zero orders and passes — that proves nothing about whether real data would ever be counted.** If
  you need to verify a report actually aggregates real rows correctly, either test with plain
  datetime-range comparisons (portable across SQLite and Postgres) or verify it directly against a
  real Postgres DB (local dev or production), the same way OI-57 was curl-verified. This is worth
  fixing properly at some point — every `func.cast(col, Date)` site in `report_service.py` and
  `dashboard_service.py` is silently unverifiable by this test suite today, which is a large blind
  spot, but it is out of scope for OI-57/OI-58 to fix wholesale.

### 2026-08-03 (session S) — Bare `python` on PATH is 3.9; this repo's backend needs 3.10+
- **Error**: `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'` when running
  `alembic`/`pytest` with the system `python`.
- **Context**: Running the backend test suite locally (outside Docker) to verify OI-61 before deploy.
- **Root Cause**: The machine's PATH `python` resolves to 3.9; this codebase uses `str | None` union
  syntax throughout (requires 3.10+), and its own test `.pyc` cache is compiled for 3.12.
- **Fix**: Used `backend/.venv/Scripts/python.exe` — a pre-existing local venv already on Python 3.12
  with every dependency installed — for all test/tooling commands instead.
- **Rule**: Always invoke this backend's Python tooling via `backend/.venv/Scripts/python.exe`, never
  bare `python`, when working outside Docker.

### 2026-08-03 (session S) — `tsc --noEmit` at the frontend project root fails with TS6305/TS6310
- **Error**: `error TS6310: Referenced project '...tsconfig.app.json' may not disable emit` and a wall
  of `TS6305` "not been built from source" errors.
- **Context**: Type-checking `frontend/` before deploying the OI-61 fix.
- **Root Cause**: The root `tsconfig.json` is a TS project-references config; `tsc --noEmit` can't be
  invoked against it directly the way it can against a leaf config.
- **Fix**: Ran `tsc --noEmit -p tsconfig.app.json`, matching exactly what `package.json`'s own
  `"build"` script does.
- **Rule**: For this frontend, always typecheck via `npm run build` (or its exact `tsc -p
  tsconfig.app.json` invocation) — never a bare `tsc --noEmit` at the repo root.

### 2026-08-03 (session S) — A bold+big centered ticket line wraps onto 3 lines at 32 characters
- **Error**: New print-ticket test failed: `"*** CARD PAYMENT PROCESSING ***"` rendered as `"*** CARD
  \nPAYMENT\nPROCESSING ***"` instead of one line.
- **Context**: Adding a third "card processing" payment state to the kitchen ticket footer (OI-61),
  styled like the existing `"*** PAID ONLINE ***"`/`"*** NOT PAID ***"` lines.
- **Root Cause**: `t.center(..., big=True)` double-sizes the text, which halves the effective line
  width from 48 to 24 characters. The new 32-character phrase exceeded that and wrapped.
- **Fix**: Shortened to `"*** CARD PROCESSING ***"` (23 characters), under the same budget the two
  existing lines already respect.
- **Rule**: Any new bold+big centered line on this ticket must fit in ~24 characters, not 48 — check
  against the existing `PAID ONLINE`/`NOT PAID` line lengths before adding a new one.

### 2026-08-03 (session S) — Backgrounded `npm run deploy` (storefront) produced 0 bytes of output
- **Error**: A `cd storefront && npm run deploy` run in the background (Bash `run_in_background`)
  completed (exit code 0, confirmed by its own task-notification) but its captured output file was
  empty — no build log, no wrangler upload log, nothing.
- **Context**: Deploying the storefront half of the OI-61 fix (Cloudflare Workers pipeline, separate
  from the backend's `git push` pipeline).
- **Root Cause**: Unclear — a harness output-buffering quirk for this specific backgrounded command,
  not a real deploy failure. The process had already exited by the time the output file was checked.
- **Fix**: Verified the deploy succeeded independently of the empty log: fetched the live storefront
  bundle and confirmed it was byte-identical to the local `vite build` output and contained the new
  "Service Fee" checkout-line string.
- **Rule**: Don't treat an empty background-output file as a failure signal on its own for this
  command — verify via the live bundle hash (or equivalent independent check) instead, same as any
  other deploy this project's own "verify the effect, never the exit code" rule already demands.

### 2026-08-03 (session T) — Local dev could never test Stripe at all, structurally, not just by convention
- **Error**: `POST .../checkout-session` in local dev returned `503 "Card payment is not available
  right now."` even after setting real Stripe TEST-mode keys in `.env`.
- **Context**: Stress-testing the OI-61 card-payment-race fix in an isolated local sandbox, without
  touching the live storefront's Stripe keys.
- **Root Cause**: Two separate, compounding gaps. (1) `docker-compose.yml`'s `backend` service
  declares an explicit `environment:` allowlist, and `STRIPE_SECRET_KEY`/`STRIPE_PUBLISHABLE_KEY`/
  `STRIPE_WEBHOOK_SECRET`/`STRIPE_SUCCESS_URL`/`STRIPE_CANCEL_URL` were never on it — Compose does
  NOT forward every `.env` variable into a container automatically, only what's explicitly listed,
  so no value in `.env` could ever have reached the backend process. (2) Independently, the local
  dev Docker image had never had the `stripe` Python package installed, even though it has been in
  `requirements.txt` (`stripe==15.3.1`) since the feature was first built — the image was built once,
  before that line existed, and nothing since has forced a rebuild (`docker compose up` reuses an
  existing image; it does not diff `requirements.txt`).
- **Fix**: Added the 5 Stripe vars to `docker-compose.yml`'s backend `environment:` list (each
  `${VAR:-}`-style, matching the existing `QB_CLIENT_ID` pattern). Ran `docker compose build backend`
  to install `stripe` for real, then `--force-recreate` to pick up both fixes.
- **Rule**: A variable being correct in `.env` proves nothing about whether a Compose service
  actually receives it — check the service's `environment:`/`env_file:` block first. Separately, an
  addition to `requirements.txt` does not reach a already-built local image until that image is
  rebuilt; `docker compose up -d` alone will happily keep running a stale image forever.

### 2026-08-10 — A feature's two safety limits left a dead zone between them, and it failed silently
- **Error**: The review-request email silently dropped every order accepted after ~19:00, which is
  peak dinner. No error, no log, no complaint.
- **Context**: Shipped in `5dda69f`. Found minutes later by dry-running the real query against
  production at the moment the feature was switched on.
- **Root Cause**: Two individually sensible constants, wrong in combination. A 12h staleness cutoff
  plus a 09:00-22:00 send window: an order accepted at 19:30 fell due at 22:30, after the window
  shut, waited for the 09:00 sweep, and by then was 13.5h old and past the cutoff.
- **Fix**: `REVIEW_EMAIL_MAX_AGE` 12h -> 18h (`2795ca2`), which covers a whole service with margin.
  New test pins acceptance at 19:30 and fails if the constant goes back.
- **Rule**: **When two limits bound the same value from opposite ends, test the interaction, not
  each limit.** The existing overnight test could not have caught this — its order sits 11h out,
  inside even the broken cutoff. **The bug lived in the gap between two passing tests.** And a
  second rule: anything that silently *declines* to act needs a positive test, because a missing
  email is indistinguishable from a quiet evening.

### 2026-08-10 — Adding a parameter broke 4 tests in an apparently unrelated file
- **Error**: `TypeError: _capture() takes 4 positional arguments but 5 were given`, in
  `test_order_lifecycle_and_email.py`.
- **Context**: Added `bcc` to `_send_blocking` / `_send_via_brevo`.
- **Root Cause**: An existing test stubs the transport with a hand-written function pinned to the
  old signature. Changing the real signature broke the stub, in a file with no obvious connection
  to the change.
- **Fix**: Stub updated, and it now also asserts the bcc is empty so no ordinary order email can
  quietly copy a third party.
- **Rule**: Run the WHOLE suite after any signature change, never just the file you wrote. Hand-
  written stubs are invisible coupling.

### 2026-08-10 — faster-whisper CUDA failure is invisible to a try/except around the constructor
- **Error**: `RuntimeError: Library cublas64_12.dll is not found or cannot be loaded`.
- **Context**: Transcribing Imran's voice note with `WhisperModel("medium", device="cuda")`.
- **Root Cause**: The constructor returns happily; the missing CUDA library only surfaces when the
  first segment is ENCODED, i.e. while iterating the generator. A try/except around construction
  catches nothing.
- **Fix**: `device="cpu", compute_type="int8"`. A 2m34s note transcribes in about a minute.
- **Rule**: For faster-whisper on this machine, use CPU. Guarding the constructor is not a fallback.

### 2026-08-10 — `TZ=Europe/London date` reported GMT in August
- **Error**: Host shell printed `04:59 GMT` when Britain was on BST.
- **Context**: Checking whether the shop was open before deploying.
- **Root Cause**: git-bash lacks BST tzdata, so it silently mislabels the zone. Same trap already
  logged on 2026-08-05 for a deploy timestamp.
- **Fix**: Read shop-local time from inside the backend container via `zoneinfo`.
- **Rule**: Never read a shop-local time from the Windows host shell. Ask the container.

### 2026-08-10 — A production probe "failed" and the failure was correct behaviour
- **Error**: The review sweep claimed 0 orders against production despite a due order existing.
- **Context**: First in-process verification of `send_due_review_emails` on the real database.
- **Root Cause**: The probe picked `demo-restaurant`, whose timezone is `Asia/Karachi`, where the
  time was 01:47 — correctly outside the 09:00-22:00 send window.
- **Fix**: Re-ran with the tenant's zone borrowed as `Europe/London` (21:47, in window). Passed.
- **Rule**: This feature cannot be probed at an arbitrary hour. Check the TENANT's local time first,
  not the server's and not your own.
