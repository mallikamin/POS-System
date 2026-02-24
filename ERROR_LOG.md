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
