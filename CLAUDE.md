# POS System - Project Guide

## What Is This?
Pakistan-based Restaurant POS System — custom-built for a restaurant chain client.
Replaces their slow tech team's existing web app with a modern, Docker-deployed, AWS-hosted solution.

## Client Requirements
- **5 Order Channels**: Dine-In (table map), Takeaway (token system), Call Center (phone lookup), Delivery (rider GPS), Foodpanda (API integration)
- **Prototype Scope**: Dine-In + Takeaway + Call Center (core 3)
- **Kitchen**: KDS (Kitchen Display System) + thermal printer support, configurable per station
- **Payment Flow**: Configurable — order-first (traditional dine-in) OR pay-first (QSR like KFC)
- **Tax**: FBR (Federal Board of Revenue) + PRA (Punjab Revenue Authority) integration ready
- **Accounting**: QuickBooks integration (Online + Desktop) — future phase
- **Deployment**: Docker → AWS ECS Fargate (client's previous team couldn't deploy on Azure)
- **Pain Point**: Current tech team is too slow, poor deployment, client not getting priority service

## Tech Stack
| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui + Zustand |
| Backend | FastAPI + SQLAlchemy 2.0 (async) + Alembic + Pydantic v2 |
| Database | PostgreSQL 16 (uuid-ossp, pg_trgm) + Redis 7 |
| Auth | JWT (access 8hr + refresh 30d) + PIN-based fast login |
| Real-time | WebSockets (FastAPI native) + Redis pub/sub for multi-worker scaling |
| Deploy | Docker (nginx, frontend, backend, postgres, redis) → AWS ECS Fargate |
| CI/CD | GitHub Actions (lint+test on PR, auto-deploy staging on merge to main) |

## Architecture Decisions
- **Multi-tenant ready**: All DB tables have UUID PK + `tenant_id` column from day one. Single tenant for now, zero schema changes needed to go multi-tenant.
- **Order State Machine**: `draft → confirmed → in_kitchen → ready → served → completed` (+ `voided` from any state, manager only)
- **Payment Flow**: `restaurant_configs.payment_flow` = `order_first` or `pay_first`. Kitchen won't fire in pay-first mode until payment is collected.
- **Currency**: Integer math in paisa (1 PKR = 100 paisa) to avoid floating-point errors
- **Multi-cart**: Zustand store uses `Record<string, Cart>` so dine-in servers can switch between multiple open tables instantly
- **Kitchen Routing**: Category-level + item-level station mapping. One `kitchen_ticket` per station per order. Combos decomposed and routed independently.
- **Integration Adapters**: Abstract base classes for QuickBooks, FBR/PRA, Foodpanda, PaymentGateway — swap implementations without architecture changes

## Project Structure
```
POS-Project/
├── frontend/                   # React 18 + TypeScript + Vite
│   ├── src/
│   │   ├── pages/              # 13 page components (lazy-loaded)
│   │   │   ├── auth/           # LoginPage (PIN + password)
│   │   │   ├── dashboard/      # Channel selector (3 cards)
│   │   │   ├── dine-in/        # Floor plan + order panel
│   │   │   ├── takeaway/       # Token-based quick orders
│   │   │   ├── call-center/    # Phone lookup + delivery
│   │   │   ├── kitchen/        # KDS (standalone fullscreen)
│   │   │   ├── payment/        # Cash/card/split payment
│   │   │   ├── floor-editor/   # Drag-and-drop table layout
│   │   │   └── admin/          # Menu, Staff, Settings, Reports
│   │   ├── components/
│   │   │   ├── ui/             # shadcn/ui (Button, Card)
│   │   │   ├── pos/            # POS-specific (NumberPad, MenuGrid, CartPanel, OrderCard, TableCard)
│   │   │   └── layout/         # POSLayout, AdminLayout
│   │   ├── stores/             # Zustand (auth, ui, menu, cart, order, table, kitchen, etc.)
│   │   ├── hooks/              # Custom hooks (useWebSocket, useMenu, useOrders, etc.)
│   │   ├── services/           # API layer, WebSocket client, printing
│   │   ├── types/              # TypeScript interfaces
│   │   ├── lib/                # utils.ts (cn), axios.ts (JWT interceptor)
│   │   └── utils/              # PKR formatting, tax calc, phone validation
│   ├── Dockerfile / Dockerfile.dev
│   └── nginx/default.conf
│
├── backend/                    # FastAPI + SQLAlchemy 2.0
│   ├── app/
│   │   ├── main.py             # FastAPI app, CORS, lifespan
│   │   ├── config.py           # Pydantic BaseSettings (.env)
│   │   ├── database.py         # Async engine, session, get_db dependency
│   │   ├── models/             # SQLAlchemy ORM models (base.py has BaseMixin)
│   │   ├── schemas/            # Pydantic request/response (common.py has pagination)
│   │   ├── api/v1/             # Route handlers (thin → delegate to services)
│   │   ├── services/           # Business logic (order state machine, kitchen routing, etc.)
│   │   ├── websockets/         # ConnectionManager, room-based broadcasting
│   │   ├── integrations/       # Abstract adapters (QuickBooks, FBR, Foodpanda, Payment)
│   │   ├── middleware/         # Tenant context, request logging
│   │   └── utils/              # security.py (JWT, bcrypt), pagination, order number gen
│   ├── alembic/                # Database migrations
│   ├── scripts/                # start.sh, migrate.sh
│   ├── Dockerfile / Dockerfile.dev
│   └── requirements.txt / requirements-dev.txt
│
├── docker/
│   ├── nginx/                  # Reverse proxy (dev + prod with SSL, rate limiting, WebSocket)
│   ├── postgres/init.sql       # Extensions: uuid-ossp, pg_trgm
│   └── redis/redis.conf        # 256MB, LRU eviction
│
├── scripts/
│   ├── setup-local.sh          # One-command local setup
│   ├── deploy.sh               # AWS ECS deployment
│   └── run-tests.sh            # Dockerized test runner
│
├── .github/workflows/
│   ├── ci.yml                  # Lint + test on push/PR
│   └── deploy-staging.yml      # Auto-deploy on merge to main
│
├── docker-compose.yml          # Local dev (5 services)
├── docker-compose.prod.yml     # Production overrides
├── docker-compose.test.yml     # Test runner
├── Makefile                    # 20+ developer shortcuts
├── .env.example                # All env vars with defaults
└── .gitignore
```

## Key Commands
```bash
# First-time setup
bash scripts/setup-local.sh

# Daily dev
make dev                        # Start all services (attached)
make dev-d                      # Start detached
make down                       # Stop
make logs                       # Tail all logs
make logs-backend               # Backend logs only

# Database
make migrate                    # Run migrations
make migrate-new MSG="add X"    # Create new migration
make migrate-down               # Rollback last migration
make seed                       # Seed sample data
make psql                       # PostgreSQL shell

# Testing
make test                       # Run tests in Docker
make lint                       # Ruff + ESLint

# Production
make build-prod                 # Build prod images
make deploy-staging             # Deploy to AWS staging
make deploy-prod                # Deploy to AWS production
```

## Database Schema (25 tables planned)
All tables: UUID PK + `tenant_id` + `created_at` + `updated_at`

| Domain | Tables |
|--------|--------|
| Tenant | tenants, restaurant_configs |
| Auth | roles, permissions, role_permissions, users, refresh_tokens |
| Floor | floors, tables (pos_x, pos_y, width, height, rotation for drag-drop) |
| Menu | categories, menu_items, modifier_groups, modifiers, menu_item_modifier_groups, combos, combo_groups, combo_group_items |
| Orders | orders, order_items, order_item_modifiers, order_taxes, order_status_log |
| Payment | payment_methods, payments, cash_drawer_sessions |
| Kitchen | kitchen_stations, kitchen_station_categories, kitchen_station_menu_items, kitchen_tickets, kitchen_ticket_items |
| Tax | tax_groups, tax_rates (FBR/PRA ready) |
| System | customers, audit_logs, integration_sync_log |

## API Endpoints Pattern
- All under `/api/v1/`
- Routes are thin — business logic in `services/` layer
- Auth via JWT Bearer token in Authorization header
- PIN login: `POST /api/v1/auth/login/pin`
- Password login: `POST /api/v1/auth/login`
- Health: `GET /api/v1/health`

## WebSocket Channels
- `floor` — table status changes
- `kitchen:{station_id}` — per-station ticket events
- `kitchen:all` — all kitchen events
- `orders` — new/updated orders
- `notifications` — system alerts

## Build Phases & Progress

### Phase 1: Foundation ✅ COMPLETE
- [x] Git repo initialized
- [x] Project structure (all folders)
- [x] Backend: FastAPI skeleton, health endpoint, CORS, JWT utils, DB setup, Alembic
- [x] Frontend: Vite + React + TS + Tailwind skeleton, routing (13 pages), auth store, NumberPad, login page, dashboard
- [x] Docker: all Dockerfiles, docker-compose (dev/prod/test), nginx configs
- [x] Infrastructure: Makefile, .env.example, .gitignore, CI/CD pipelines, deploy scripts
- **Files created**: 82

### Phase 2: Auth + Tenant + Config ✅ COMPLETE
- [x] DB models: tenants, users, roles, permissions, role_permissions, refresh_tokens, restaurant_configs (7 tables)
- [x] Alembic migration (`626f009d4555_phase2_auth_tenant_config.py`)
- [x] API: POST /auth/login (password), POST /auth/login/pin (PIN), POST /auth/refresh, POST /auth/logout, GET /auth/me, GET /config/restaurant
- [x] Auth service: password auth, PIN auth (bcrypt iterate), token creation, token rotation, token revocation
- [x] `_resolve_tenant_id()` helper: auto-detects single active tenant so frontend doesn't need to send tenant_id
- [x] Frontend: axios with JWT interceptor (auto-refresh on 401), authStore (Zustand persist), configStore, POSLayout auth guard
- [x] Frontend: LoginPage wired to real API (PIN + password modes), redirect to dashboard on success
- [x] Seed script: 1 demo tenant, 15 permissions, 3 roles (admin/cashier/kitchen), 3 users
- [x] Backend fully tested via curl — all endpoints working
- **Pending**: Frontend browser testing (login flow, redirect, logout)

#### Seed Data (for testing)
| User | Email | Password | PIN | Role |
|------|-------|----------|-----|------|
| Admin User | admin@demo.com | admin123 | 1234 | admin |
| Cashier User | cashier@demo.com | cashier123 | 5678 | cashier |
| Kitchen User | kitchen@demo.com | kitchen123 | 9012 | kitchen |

### Phase 3: Menu Engine ✅ COMPLETE
- [x] DB models: categories, menu_items, modifier_groups, modifiers (5 tables)
- [x] Alembic migration (`02577b9f3600_phase3_menu_engine.py`)
- [x] API: full menu CRUD + GET /menu/full
- [x] Frontend: Admin MenuManagementPage (3 tabs: Categories, Items, Modifier Groups)
- [x] Frontend: MenuGrid (POS item cards with images) + ModifierModal (modifier selection with min/max)
- [x] Frontend: CartPanel + cartStore (multi-cart, modifier price support, integer tax math)
- [x] Seed: 9 categories, 42 Pakistani menu items with images, 4 modifier groups, 16 tables
- [x] Bug fixes: React Router v7 future flags, max_selections=0 as unlimited, Half serving -Rs.400
- [x] Code review: EMPTY_CART sentinel, direct Zustand selectors, type migration to @/types/cart

### Phase 4: Floor Plan + Tables ✅ COMPLETE
- [x] DB models: floors, tables (pos_x/y, width/height, rotation, shape, status, label)
- [x] Alembic migration (`b23ab0200c28_phase4_floor_plan.py`)
- [x] API: CRUD for floors/tables + bulk position update + status board
- [x] Frontend: FloorGrid + TableCard (color-coded status, shape-aware rendering)
- [x] Frontend: FloorEditorPage (drag-and-drop canvas, add/delete tables, property panel)
- [x] DineInPage: table selection → per-table cart switching (`table-{uuid}`)
- [x] Seed: 2 floors (Ground Floor + Terrace), 16 tables with positions
- **Pending**: WebSocket table status events (Phase 5+ integration)

### Phase 5: Orders + Dashboard + Reports ✅ COMPLETE
- [x] DB models: orders, order_items, order_item_modifiers, order_status_log (4 tables)
- [x] Alembic migration (`ee03acd94262_phase5_orders.py`)
- [x] Order service: state machine (draft→confirmed→in_kitchen→ready→served→completed + voided), YYMMDD-NNN numbering, server-side price+tax calc, table auto-status
- [x] API: POST/GET/PATCH /orders, POST /orders/{id}/void, GET /dashboard/kpis, GET /dashboard/live, GET /reports/* (summary, items, hourly, CSV)
- [x] Frontend: OrdersPage (filter tabs, 15s refresh), OrderCard (action buttons), OrderTicker (live bar on POS pages)
- [x] Frontend: AdminDashboard rewritten (KPI cards, live operations, CSS charts, 30s polling)
- [x] Frontend: ReportsPage rewritten (date picker, summary cards, item tables, hourly chart, CSV export)
- [x] CartPanel wired to real API (createOrderFromCart → clear cart → update table)
- [x] Seed: 10 sample orders (4 dine-in, 3 takeaway, 2 call center, mixed statuses), tables auto-occupied
- [x] TypeScript compiles cleanly (all TS errors fixed)
- **New files**: 18 (backend: 10, frontend: 8)
- **Modified files**: 9 (CartPanel, App, POSLayout, DineInPage, TakeawayPage, AdminDashboard, ReportsPage, router, seed)

### Pre-Phase 6: Bug Fixes & Missing Features ✅ COMPLETE
- [x] **Floor Editor fixed** (`/floor-editor`) — load, drag, save, add/delete tables working
- [x] **Dine-In POS fixed** (`/dine-in`) — table/cart sync, order submission working
- [x] **Takeaway POS fixed** (`/takeaway`) — token-based ordering flow working
- [x] **Table Reservation mechanism** — reserve/unreserve in FloorGrid with backend persistence

### Phase 6: Kitchen (KDS) ✅ COMPLETE
- [x] DB models: kitchen_stations, kitchen_station_categories, kitchen_station_menu_items, kitchen_tickets, kitchen_ticket_items
- [x] Alembic migration (`d5e6f7a8b9c0_phase6_kitchen_kds.py`)
- [x] API: station CRUD, ticket status transitions (bump/recall), queue endpoints
- [x] Frontend: KDS fullscreen Kanban board (new/preparing/ready/served columns, elapsed timers, audio alerts, station filter)
- [x] WebSocket: `kitchen.ticket.created` + `kitchen.ticket.updated` events via `kitchen:{station_id}` + `kitchen:all` rooms
- [x] Degraded polling fallback when WebSocket unavailable
- [x] Tests: 31 kitchen tests passing

### Phase 7: Payments ✅ COMPLETE
- [x] DB models: payment_methods, payments, cash_drawer_sessions
- [x] Alembic migration (`4f7e5a9c1b21_phase7_payments.py`)
- [x] API: create payment, split payment, refund, cash drawer open/close/session report
- [x] Frontend: Payment screen (cash calculator, card, split, print bill)
- [x] Payment flow toggle wired to config (`order_first` / `pay_first`)
- [x] Tests: 40 payment tests passing

### Phase 8: Call Center ✅ COMPLETE
- [x] DB models: customers
- [x] Alembic migration (`c8d9e0f1a2b3_phase8_call_center_customers.py`)
- [x] API: customer search, CRUD, order history, repeat-order helpers
- [x] Frontend: phone lookup, customer create/edit, history, repeat-order flow
- [x] Order validation for call-center customer fields
- [x] Tests: 27 customer + 11 call-center tests passing

### Phase 9: Reports + Admin ⬜
- [ ] API: sales summary, Z-report, item sales, cash drawer report
- [ ] Frontend: Admin reports, staff management, settings
- [ ] Receipt generation

### Phase 10: Polish + Integration Stubs ⬜
- [ ] Integration adapter interfaces
- [ ] Audit logging
- [ ] Touch optimization audit
- [ ] Error handling, loading states
- [ ] CI/CD pipeline finalization
- [ ] Demo seed data

## Port Assignments (avoid conflicts with other Docker projects)
| Service | Internal | External (Host) |
|---------|----------|-----------------|
| nginx (reverse proxy) | 80 | **8090** |
| PostgreSQL | 5432 | **5450** |
| Redis | 6379 | **6390** |
| Backend (FastAPI) | 8000 | internal only |
| Frontend (Vite dev) | 5173 | internal only |

Access the app at `http://localhost:8090`. API docs at `http://localhost:8090/api/docs`.

## Known Fixes & Gotchas
- **Pydantic-settings v2 + `list[str]` env vars**: Does NOT work. EnvSettingsSource tries JSON decode before validators run. Fix: use `CORS_ORIGINS: str` field + `@property cors_origins_list` that splits on commas. `main.py` uses `settings.cors_origins_list`.
- **Shell scripts on Windows→Linux containers**: Must have LF line endings. `.gitattributes` handles this automatically.
- **Frontend Dockerfile.dev**: Uses `npm install` (not `npm ci`) because Docker volume may be empty on first run. CMD has safety net: `npm install --prefer-offline && npm run dev`.
- **tenant_id in login requests**: Optional (`uuid | None`). `_resolve_tenant_id()` in `auth.py` auto-detects the single active tenant. Frontend sends no tenant_id.
- **SQLAlchemy async flush-before-FK**: Always `await db.flush()` after adding parent before creating children with parent FK references.
- **SQLAlchemy MissingGreenlet**: After mutating an ORM object, `db.expunge(obj)` then re-fetch via `selectinload()`. Do NOT use `db.expire()` (triggers sync lazy load).
- **SQLAlchemy Date cast**: `func.cast(col, Date)` with `from sqlalchemy import Date`. NOT `func.DATE`.
- **TS noUncheckedIndexedAccess**: `.split("T")[0]` returns `string | undefined`. Add `?? ""` or use `!`.

## Environment Variables
All in `.env.example`. Key ones:
- `SECRET_KEY` — JWT signing (MUST change in production)
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection
- `CORS_ORIGINS` — Allowed frontend origins
- `VITE_API_URL` / `VITE_WS_URL` — Frontend API/WebSocket endpoints

## Coding Conventions
- **Backend**: Routes are thin, delegate to services. All models inherit BaseMixin. Async everywhere.
- **Frontend**: All pages lazy-loaded. Zustand for state (no Redux). shadcn/ui for components. `cn()` for class merging.
- **Naming**: snake_case (Python), camelCase (TypeScript), kebab-case (file/folder names in frontend)
- **Touch targets**: Minimum 48px general, 56px POS buttons, 72px number pad
- **Currency**: Always integer paisa, format with `formatPKR()` util for display

## AWS Target Architecture
- **Compute**: ECS Fargate (no server management)
- **Database**: RDS PostgreSQL 16 (managed, Multi-AZ for prod)
- **Cache**: ElastiCache Redis 7
- **Load Balancer**: ALB (SSL termination, WebSocket support)
- **SSL**: ACM (free, auto-renewal)
- **Secrets**: SSM Parameter Store
- **CI/CD**: GitHub Actions → ECR → ECS
- **Region**: me-south-1 (Bahrain, closest to Pakistan)
- **Estimated staging cost**: ~$127/month
