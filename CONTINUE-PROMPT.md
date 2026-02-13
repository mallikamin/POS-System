# Continue Prompt — Phase 6: Kitchen Display System (KDS)

Copy everything below this line and paste as your first message in a new chat:

---

Continue building the POS System project at `C:\Users\Malik\desktop\POS-Project`. Read `CLAUDE.md` and `.claude/projects/C--Users-Malik-desktop-POS-Project/memory/MEMORY.md` for full context.

## Current Status — Phases 1-5 COMPLETE

All Docker services are running (nginx:8090, postgres:5450, redis:6390, backend:8000, frontend:5173).

- **Phase 1**: Full project scaffold (82 files), Docker, CI/CD
- **Phase 2**: Auth (JWT + PIN), tenants, roles, permissions, restaurant_config (tax 1600bps, payment_flow)
- **Phase 3**: Full menu engine — 9 categories, 42 items with images, 4 modifier groups, cart system (multi-cart, modifier prices, integer tax), CartPanel, ModifierModal
- **Phase 4**: Floor plan — 2 floors (Ground Floor 10 tables, Terrace 6 tables), drag-drop editor, DineInPage wired with FloorGrid → table-based cart switching (`table-{uuid}`)
- **Phase 5**: Orders + Dashboard + Reports — COMPLETE:
  - Backend: Order models (4 tables), state machine service (draft→confirmed→in_kitchen→ready→served→completed + voided), YYMMDD-NNN numbering, server-side price+tax, table auto-status
  - Backend: Dashboard KPIs endpoint, live operations endpoint, reports (sales summary, item performance, hourly breakdown, CSV export)
  - Frontend: CartPanel wired to real API (createOrderFromCart → POST /orders → clear cart → update table)
  - Frontend: OrdersPage (filter tabs, 15s auto-refresh), OrderCard (action buttons), OrderTicker (live bar on POS pages)
  - Frontend: AdminDashboard rewritten (4 KPI cards, live operations, CSS charts, 30s polling)
  - Frontend: ReportsPage rewritten (date picker, summary cards, item tables, hourly chart, CSV export)
  - Seed: 10 sample orders (4 dine-in, 3 takeaway, 2 call center, mixed statuses), 3 tables auto-occupied
  - TypeScript compiles cleanly (0 errors)

## What to Build Now — Phase 6: Kitchen Display System (KDS)

### 6A: Kitchen Station Models + Migration
DB models needed:
- `kitchen_stations` — name, display_order, is_active (e.g., "Grill Station", "Curry Station", "Drinks")
- `kitchen_station_categories` — station_id FK, category_id FK (which food categories route to which station)
- `kitchen_station_menu_items` — station_id FK, menu_item_id FK (item-level override for routing)
- `kitchen_tickets` — order_id FK, station_id FK, status (pending→preparing→ready→served), priority, notes
- `kitchen_ticket_items` — ticket_id FK, order_item_id FK, quantity, status

### 6B: Kitchen Routing Service
- When order is sent to kitchen (status → in_kitchen), decompose into station-level tickets:
  - For each order item, determine its station: item-level mapping > category-level mapping > default station
  - Create one kitchen_ticket per station per order
  - Each ticket gets the relevant items routed to that station
- Service functions: create_tickets_for_order, bump_ticket (move to next status), recall_ticket

### 6C: Kitchen API Routes
- `GET /kitchen/stations` — list stations with config
- `GET /kitchen/tickets?station_id=&status=` — tickets filtered by station and/or status
- `PATCH /kitchen/tickets/{id}/bump` — advance ticket status
- `PATCH /kitchen/tickets/{id}/recall` — move ticket back one status
- Admin: CRUD for station management and routing config

### 6D: Kitchen Display Frontend (KitchenPage.tsx — standalone fullscreen)
The KitchenPage already exists as a skeleton at `frontend/src/pages/kitchen/KitchenPage.tsx`.
- Standalone fullscreen layout (no POSLayout header)
- Kanban columns: New → Preparing → Ready
- Each ticket card: order number, table/takeaway, item list with quantities, elapsed timer (color-coded: green <10m, yellow 10-20m, red >20m)
- Bump button on each card to advance status
- Audio alert on new ticket arrival
- Station selector (dropdown or tabs) to filter by station
- Auto-refresh: polling every 5 seconds (or WebSocket if time permits)

### 6E: WebSocket Integration (Stretch Goal)
- WebSocket room `kitchen:{station_id}` for real-time ticket push
- Room `kitchen:all` for supervisors
- Emit on: new ticket, status change, ticket recall
- If time is tight, polling is acceptable for now

### Key Existing Files
- `frontend/src/pages/kitchen/KitchenPage.tsx` — skeleton to rewrite
- `frontend/src/App.tsx:63` — Kitchen route already exists: `<Route path="/kitchen" element={<KitchenPage />} />`
- `backend/app/api/v1/router.py` — register new kitchen router
- `backend/app/models/__init__.py` — register new kitchen models
- `backend/app/services/order_service.py` — hook ticket creation into order transition

### Architecture Constraints
- All DB models inherit BaseMixin (UUID PK + tenant_id + timestamps)
- Backend services are async, routes are thin → delegate to services
- Frontend: Zustand stores, lazy-loaded pages, shadcn/ui components
- Kitchen user auth: kitchen@demo.com/kitchen123/PIN:9012
- Seed users: admin@demo.com/admin123/PIN:1234, cashier@demo.com/cashier123/PIN:5678
- WebSocket channels defined in CLAUDE.md

### Implementation Order
1. Backend: Kitchen station models + migration
2. Backend: Kitchen routing service + ticket creation on order transition
3. Backend: Kitchen API routes
4. Frontend: kitchenApi.ts + kitchenStore.ts
5. Frontend: KitchenPage rewrite (fullscreen Kanban)
6. Seed: kitchen stations + routing config + generate tickets for existing orders
7. (Optional) WebSocket integration

Start by planning, then build incrementally. Each step should produce working functionality.

---
