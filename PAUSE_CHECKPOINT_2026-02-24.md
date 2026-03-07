# Pause Checkpoint — 2026-02-24

## Project
- **Name**: POS System (Restaurant POS)
- **Path**: C:\Users\Malik\desktop\POS-Project
- **Branch**: QuickBooksAttempt2
- **Live URL**: https://pos-demo.duckdns.org

## Goal
Complete hardening (3 tiers of code review + DB audit fixes), generate a full UAT checklist, deploy to production, and begin end-to-end UAT testing of all POS features.

## Completed
- [x] Tier 1 CRITICAL/HIGH: Audit logging on staff update/reset-password/reset-pin
- [x] Tier 1: Verified 4 other findings were already fixed (AuditLog import, Z-Report guard, read-only commits, frontend error extraction)
- [x] Tier 2 MEDIUM: ReceiptModal XSS fix (document.write+innerHTML → safe DOM cloneNode)
- [x] Tier 2: ZReportPage stale "today" fix (module-level const → lazy getToday() function)
- [x] Tier 2: SettingsPage restaurant name fix (receipt header parsing → API restaurant_name field from tenant)
- [x] Tier 3 DB: Partial unique index for single open cash drawer per tenant (migration-only, not in model to avoid SQLite test breakage)
- [x] Tier 3 DB: Order number race condition fix (retry loop with SAVEPOINT, 3 attempts)
- [x] Tier 3 DB: IntegrityError handling on staff create + cash drawer open
- [x] Tier 3 DB: Added indexes on orders.created_by and orders.customer_phone
- [x] New migration: f2a3b4c5d6e7_hardening_indexes_constraints
- [x] All 147/147 backend tests passing, 0 TypeScript errors
- [x] Committed and pushed (387bf55)
- [x] Deployed to production (5/5 containers healthy, migration applied, 3 indexes verified)
- [x] Generated 99-case UAT checklist (UAT_CHECKLIST.md) across 17 modules
- [x] Health check passing: database healthy, redis healthy

## In Progress
- [ ] End-to-end UAT testing — NOT YET STARTED, everything is deployed and ready

## Pending
- [ ] Execute UAT checklist (99 test cases across 17 modules) — start with Auth (UAT-001-009), then order flows
- [ ] Fix any bugs found during UAT
- [ ] QuickBooks OAuth reconnection (was disconnected for demo, needs re-auth via onboarding tool)
- [ ] Browser-based walkthrough of all pages
- [ ] Remaining low-priority items: double commit pattern cleanup, AuditLog model FK, dashboard timezone

## Key Decisions
- Partial unique index (uix_one_open_drawer_per_tenant) lives ONLY in migration, not in SQLAlchemy model — because postgresql_where degrades to a plain unique index on SQLite, breaking tests
- Order number retry uses SAVEPOINT (begin_nested) so IntegrityError doesn't poison the outer transaction
- restaurant_name added to RestaurantConfigResponse by querying Tenant.name separately (not a DB schema change, just API response enrichment)
- UAT execution order: Auth → Dine-In → Takeaway → Call Center → KDS → Orders → Payments → Receipts → Reports → Admin features

## Files Modified (This Session)
- `backend/app/api/v1/staff.py` — Added audit logging to update/reset-password/reset-pin + IntegrityError handling on create
- `backend/app/api/v1/payments.py` — IntegrityError handling on cash drawer open
- `backend/app/api/v1/config.py` — Include tenant name in GET /config/restaurant response
- `backend/app/schemas/tenant.py` — Added restaurant_name field to RestaurantConfigResponse
- `backend/app/models/payment.py` — Comment documenting partial unique index (migration-only)
- `backend/app/models/order.py` — Added indexes on created_by and customer_phone
- `backend/app/services/order_service.py` — Retry loop for order number race condition
- `backend/alembic/versions/f2a3b4c5d6e7_hardening_indexes_constraints.py` — NEW migration
- `frontend/src/components/pos/ReceiptModal.tsx` — Safe DOM API for print (no innerHTML XSS)
- `frontend/src/pages/admin/ZReportPage.tsx` — Lazy getToday() for midnight freshness
- `frontend/src/pages/admin/SettingsPage.tsx` — Use restaurant_name from API
- `UAT_CHECKLIST.md` — NEW: 99-case UAT checklist
- `ERROR_LOG.md` — Updated with session errors

## Uncommitted Changes
- `.claude/settings.local.json` — editor config only (not project code)
- `PAUSE_CHECKPOINT_2026-02-23.md` — previous checkpoint (kept for history)
- `droplet.txt` — scratch notes
- All real work is committed and pushed (387bf55).

## Errors & Resolutions
- **SQLite partial unique index breaks tests**: `postgresql_where` on Index degrades to plain unique index on SQLite, causing cash drawer tests to fail (409 on reopen). Fixed by keeping index in migration only, not in model `__table_args__`.

## Critical Context
- **Production is LIVE** at https://pos-demo.duckdns.org — all hardening deployed, migration applied
- **3 new indexes verified** on production PostgreSQL: uix_one_open_drawer_per_tenant, ix_orders_created_by, ix_orders_customer_phone
- **Migration at head**: f2a3b4c5d6e7
- **Seed data**: Orders are from Feb 10/13. Today's KPIs will show $0 until fresh orders are created through the frontend during UAT
- **Server**: DigitalOcean 159.65.158.26 (SGP1), SSH as root, project at ~/pos-system
- **Deploy command**: `cd ~/pos-system && git pull && docker compose -f docker-compose.demo.yml --env-file .env.demo up -d --build`
- **QB OAuth**: Disconnected — needs reconnection post-UAT via the onboarding tool
- **Test credentials**: admin@demo.com/admin123 (PIN 1234), cashier@demo.com/cashier123 (PIN 5678), kitchen@demo.com/kitchen123 (PIN 9012)
- **UAT Checklist**: `UAT_CHECKLIST.md` in project root — 99 test cases, 17 modules, execution order defined
