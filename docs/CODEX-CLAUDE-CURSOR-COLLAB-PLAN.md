# Codex-Claude-Cursor Collaboration Plan

## Command Model
- Codex is the orchestrator and final approver for implementation direction.
- Claude executes scoped feature slices and backend-heavy tasks.
- Cursor executes UI-heavy slices, rapid local iteration, and verification passes.
- All changes merge through Codex-reviewed PRs with explicit task IDs.

## Execution Order
1. Pre-Phase 6 stabilization (must pass before any new phase scope).
2. Phase 7 Payments (core payment data model + order integration).
3. Phase 8 Call Center (customer lookup + channel workflow).
4. Phase 6 KDS (kitchen tickets + station workflows) aligned to completed payment/call-center flows.

## Workstream Ownership
- Codex:
  - Owns architecture boundaries, phase gates, final API contracts.
  - Resolves integration conflicts between frontend/backend slices.
  - Maintains release checklist and go/no-go decisions.
- Claude:
  - Backend domain implementation and migrations.
  - Service-layer logic, state transitions, API schema contracts.
  - Automated tests for service and API routes.
- Cursor:
  - Frontend pages, stores, API wiring, and interaction polish.
  - Visual QA and UX regression checks for POS flows.
  - Fast patch loops from Codex bug triage.

## Active Sprint: Pre-Phase 6

### Target Fixes
- Floor Editor reliability (`/floor-editor`)
- Dine-In flow reliability (`/dine-in`)
- Takeaway flow reliability (`/takeaway`)
- Table reservation mechanism in FloorGrid with backend persistence

### Tasks
- [x] Add reserve/unreserve controls in FloorGrid and persist table status.
- [x] Stabilize Dine-In table/cart synchronization when selection changes.
- [x] Validate Floor Editor interactions end-to-end (load, drag, save, add, delete).
- [x] Validate Takeaway ordering flow end-to-end.
- [x] Capture any newly discovered defects in `ERROR_LOG.md`.

### Phase Gate
- [x] Pre-Phase 6 closure complete (including floor-editor toast noise reduction patch).

## Phase 7: Payments (Next)

### Backend
- Add tables/models: `payment_methods`, `payments`, `cash_drawer_sessions`.
- Add migration and constraints for split payments and refunds.
- Add endpoints: create payment, split payment, refund, drawer open/close/session report.
- Wire payment flow toggle (`order_first` / `pay_first`) to order lifecycle rules.

### Frontend
- Upgrade `PaymentPage` to real payment workflows (cash/card/mobile/split).
- Add cashier cash calculator and payment confirmation UX.
- Add drawer session controls and status visibility.

### Exit Criteria
- No order can incorrectly bypass configured payment flow.
- Split + partial payment works and updates order `payment_status`.
- Payment records are queryable in reports.

## Phase 8: Call Center (Then)

### Backend
- Add `customers` model and migration.
- Add APIs for phone search, customer CRUD, recent orders, and repeat-order helpers.

### Frontend
- Upgrade `CallCenterPage` with live phone lookup and customer selection.
- Persist customer data onto call-center orders.
- Add repeat-order flow from previous order history.

### Exit Criteria
- Phone lookup works within 2-3 keystrokes.
- Call-center order can be created with linked customer + address.

### Phase Gate
- [x] Core scope closed (integration smoke + compile/lint clean).

## Phase 6: KDS (After Call Center)

### Kickoff Status
- [x] Kickoff opened after Phase 8 gate pass.

### Backend
- Add kitchen station/ticket tables and routing logic.
- Add station queue APIs and item/ticket status transitions.
- Emit kitchen events via WebSocket channels.

### Frontend
- Build station-centric KDS board (new/in-progress/ready).
- Add timers, bump/recall actions, and alert hooks.

### Exit Criteria
- Confirmed orders generate station tickets correctly.
- KDS state transitions are reflected in order lifecycle without drift.

## Coordination Rules
- One owner per task at a time; handoff includes:
  - changed files,
  - API changes,
  - migration notes,
  - test evidence.
- Codex keeps a single source of truth checklist in this file.
- Any blocker >30 minutes is escalated back to Codex for reassignment.

## Current Resume Point
- Implementation status: complete through Pre-Phase 6 + Phase 7 + Phase 8 + Phase 6 KDS realtime.
- Deployment status: paused pending manual browser UAT.
- Resume from: execute manual checklist, capture PASS/FAIL, patch only failing flows, then deploy.
