# Checkpoint - 2026-02-20 (Pre-UAT)

## Status Summary
- Code implementation for major scope is complete and committed.
- Remaining work before deployment is manual browser UAT using the checklist.
- Deployment was intentionally paused until manual UAT pass.

## Built and Completed
- Pre-Phase 6 stabilization:
  - Floor Editor fixes
  - Dine-In flow fixes
  - Takeaway flow fixes
  - Table reservation/unreservation flow
- Phase 7 Payments:
  - Backend models, migrations, APIs, services, tests
  - Frontend payment screen integration
  - Posting payment flows (cash/card/split)
  - Drawer open/close
  - Print bill action on payment screen
- Phase 8 Call Center:
  - Backend customers domain + APIs + tests
  - Frontend phone lookup, customer create/edit, history, repeat-order flow
  - Order validation for call-center customer fields
- Phase 6 KDS:
  - Backend kitchen domain + APIs + tests
  - WebSocket event plumbing (`kitchen.ticket.created`, `kitchen.ticket.updated`)
  - Frontend KDS board with realtime update handling and degraded polling fallback

## Validation Completed
- Backend tests in Docker: `147 passed`.
- Frontend TypeScript check: pass.
- Frontend scoped eslint for changed feature files: pass.
- Frontend production build in Docker: pass.

## Explicitly Pending
- Manual browser UAT execution with checklist.
- Only after UAT pass: staging/production deployment.

## Resume Instructions
1. Run manual browser checklist and record PASS/FAIL per section.
2. Fix any UAT defects found.
3. Re-run targeted checks for touched areas.
4. Deploy to target environment after UAT sign-off.

## Key Pages to Verify in UAT
- `/login` (PIN mode + password mode, redirect to dashboard on success)
- `/dashboard` (channel selector cards render, navigation to each channel works)
- `/dine-in` (table selection, cart switching, order submission, table status update)
- `/takeaway` (token-based order, cart, submit)
- `/floor-editor` (load floors, drag tables, save positions, add/delete tables)
- `/payment/:orderId` (cash calculator, card, split payment, print bill, drawer open/close)
- `/call-center` (phone lookup, customer create/edit, address selection, repeat order)
- `/kitchen` (KDS board renders, station filter, bump/recall, timers, audio toggle)
- `/orders` (order list, status filter tabs, 15s auto-refresh)
- `/admin` (menu management — categories/items/modifiers)
- `/admin/dashboard` (KPI cards, live operations, charts)
- `/admin/reports` (date picker, summary, item table, hourly chart, CSV export)
- WebSocket connectivity: open `/kitchen` in two tabs, bump a ticket in one, verify the other updates in real-time
