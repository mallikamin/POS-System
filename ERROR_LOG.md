# POS System Error Log

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
