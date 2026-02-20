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
- `/dine-in`
- `/takeaway`
- `/floor-editor`
- `/payment/:orderId` (must show post payment + print bill path)
- `/call-center`
- `/kitchen`
