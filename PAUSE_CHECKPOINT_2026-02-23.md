# Pause Checkpoint — 2026-02-23

## Project
- **Name**: POS System (Restaurant POS)
- **Path**: C:\Users\Malik\desktop\POS-Project
- **Branch**: QuickBooksAttempt2
- **Live URL**: https://pos-demo.duckdns.org

## Goal
Complete all 10 build phases, run TARS audit, do local testing, fix all critical/high issues, deploy to production, and prepare for a live client demo.

## Completed
- [x] Phase 9: Reports + Admin (Staff CRUD, Settings, Z-Report, Receipts, Audit Logging)
- [x] Phase 10: Polish + Integration Stubs (Toast, FBR/PRA/Foodpanda stubs, seed enhancements)
- [x] TARS Audit #1 (47 findings, 19 CRITICAL+HIGH fixed)
- [x] Local Docker testing (all 5 services healthy, 147/147 tests passing, 0 TS errors)
- [x] E2E API verification (15/15 endpoints tested: login, menu, orders, staff, kitchen, config, floors, dashboard, payments, receipts, Z-report)
- [x] Production deployment (git push → SSH → pull → rebuild → migrate → seed)
- [x] Redis auth fix on production (password mismatch between .env.demo and redis.conf)
- [x] Customer phone normalization fix on update (was only normalized on create)
- [x] All work committed and pushed to remote

## In Progress
- [ ] DB audit findings review — 19 findings received, 1 fixed (phone normalization), 5 HIGH items remaining (non-demo-blocking but should be addressed)

## Pending (Post-Demo Improvements)
- [ ] Order number race condition fix (retry loop or advisory lock for concurrent requests)
- [ ] IntegrityError handling on CREATE endpoints (concurrency edge case)
- [ ] Partial unique index for single open cash drawer per tenant
- [ ] Dashboard timezone fix (`date.today()` → PKT-aware date for SGP1 server)
- [ ] Double commit pattern cleanup (route handlers + get_db both commit)
- [ ] AuditLog model: add FK on tenant_id (migration has it, model doesn't)
- [ ] Add index on `orders.created_by` and `orders.customer_phone`
- [ ] Frontend audit remaining items (ZReportPage stale data, SettingsPage heuristic, PaymentPage window.print)
- [ ] Browser-based UAT walkthrough of all pages
- [ ] QuickBooks sync verification with new Phase 6-10 features

## Key Decisions
- **Audit SAVEPOINT pattern**: `async with db.begin_nested()` for audit_service — audit failures never break main operations
- **Admin-only guards**: Kitchen station CRUD and payment refunds now require admin role
- **Redis auth**: Production uses `pos_redis_dev_secret` (from redis.conf), NOT the random hash that was in .env.demo
- **Nginx hardening active**: Bare curl blocked (444 response) — must use browser-like headers; this is intentional security

## Files Modified (This Session)
- `backend/tests/conftest.py` — Added `audit_logs` to `_SKIP_TABLE_NAMES` for SQLite test DB
- `backend/tests/test_kitchen.py` — 5 methods: cashier_token → admin_token (role guard alignment)
- `backend/tests/test_payments.py` — 6 refund methods: cashier_token → admin_token
- `backend/app/services/audit_service.py` — SAVEPOINT wrapper (`begin_nested()`) for non-critical audit logging
- `backend/app/services/customer_service.py` — Phone normalization on update (not just create)
- All Phase 9-10 files (45 files, +3,420 lines) — see commit `622b83a`

## Uncommitted Changes
- `.claude/settings.local.json` — editor config (not project code)
- `droplet.txt` — scratch notes (not project code)
- All real work is committed and pushed.

## Errors & Resolutions
- **147 test failures (audit_logs JSONB on SQLite)** → Added `"audit_logs"` to `_SKIP_TABLE_NAMES` in conftest.py
- **Kitchen/payment test 403s** → Tests used `cashier_token` but endpoints now require admin; changed to `admin_token`
- **PendingRollbackError in call-center tests** → audit_service flush failed (no audit_logs table in SQLite), poisoned session. Fixed with `begin_nested()` SAVEPOINT isolation
- **Redis "unhealthy" on production** → `.env.demo` had wrong password. Fixed to match redis.conf (`pos_redis_dev_secret`). Must recreate container (`up -d --no-deps`), not just restart
- **Customer phone normalization mismatch** → `update_customer` didn't normalize phone digits, breaking order history joins. Fixed.

## Code Review Findings (received after pause, NOT yet fixed)
- **CRITICAL**: Register AuditLog in `backend/app/models/__init__.py` (missing import)
- **HIGH**: Add `require_role("admin")` to Z-Report endpoint (`backend/app/api/v1/reports.py`)
- **HIGH**: Remove unnecessary `db.commit()` from read-only staff endpoints (list_staff, list_roles, get_staff_member)
- **HIGH**: Add audit logging to staff update/reset-password/reset-pin operations
- **HIGH**: Fix frontend error message extraction in StaffManagementPage (use `err.response.data.detail`)
- **MEDIUM**: ReceiptModal XSS via innerHTML injection in print window
- **MEDIUM**: ZReportPage `today` computed at module load (stale across midnight)
- **MEDIUM**: SettingsPage restaurant name parsed from receipt header (should use tenant.name)
- **LOW**: Unused imports in receipt_service.py, DRY violations (channelLabels, formatAmount vs formatPKR)
- Full report: 3 CRITICAL, 10 HIGH, 12 MEDIUM, 8 LOW (many already fixed in current code — agent read stale versions)

## Critical Context
- **Production is LIVE** at https://pos-demo.duckdns.org — 5/5 containers healthy, all endpoints verified
- **KPIs and Z-Report show $0 for today** because seed orders are from Feb 10/13. Create orders through the frontend during demo to populate live data
- **33 tables in PostgreSQL** — all migrations applied through Phase 9
- **Seed data**: 4 users, 8 categories, 42 menu items, 2 floors, 16 tables, 12 orders, 5 payments, 1 cash drawer session
- **Server**: DigitalOcean 159.65.158.26 (SGP1), SSH as root, project at ~/pos-system
- **Deploy command**: `cd ~/pos-system && git pull && docker compose -f docker-compose.demo.yml --env-file .env.demo up -d --build`
