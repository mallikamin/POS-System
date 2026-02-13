# POS SYSTEM — MASTERPLAN

**Document:** Post-Prototype Strategic Roadmap
**Author:** Malik Amin
**Date:** February 10, 2026
**Status:** Draft — Pending Client Approval
**Scope:** Full platform vision — from restaurant POS to enterprise operating system

---

## Table of Contents

1. [Executive Vision](#1-executive-vision)
2. [Platform Architecture](#2-platform-architecture)
3. [Foundation — What's Already Built](#3-foundation--whats-already-built)
4. [Core Completion — Phases 6-10](#4-core-completion--phases-6-10)
5. [Tier 1 — Revenue & Financial Operations](#5-tier-1--revenue--financial-operations)
6. [Tier 2 — Customer Experience & Engagement](#6-tier-2--customer-experience--engagement)
7. [Tier 3 — Intelligence & Automation](#7-tier-3--intelligence--automation)
8. [Tier 4 — Communication & Marketing](#8-tier-4--communication--marketing)
9. [Tier 5 — Supply Chain & Kitchen Intelligence](#9-tier-5--supply-chain--kitchen-intelligence)
10. [Tier 6 — Enterprise & Scale](#10-tier-6--enterprise--scale)
11. [Integration Architecture Map](#11-integration-architecture-map)
12. [Technology Stack Evolution](#12-technology-stack-evolution)
13. [Database Schema Projection](#13-database-schema-projection)
14. [Deployment & Infrastructure Roadmap](#14-deployment--infrastructure-roadmap)
15. [Risk Register](#15-risk-register)
16. [Rollout Strategy](#16-rollout-strategy)

---

## 1. Executive Vision

This is not a POS system. This is a **restaurant operating system**.

The prototype (Phases 1-5) proves the core: take orders, route to kitchen, track status, report revenue. That's table stakes. Every POS does that.

What we're building after the prototype is what separates this from Toast, Square, Clover, and every other off-the-shelf solution:

- **Financial brain** — QuickBooks integration so deep the accountant never manually enters a sales receipt again
- **Customer memory** — CRM that knows every customer's order history, preferences, and lifetime value
- **Kitchen intelligence** — Bill of Materials that tells you exactly how much chicken you should have used vs how much you actually did, and where the variance went
- **Vendor control** — Portal where suppliers see their ledgers, submit invoices, and the restaurant pays on their terms
- **AI copilot** — Demand forecasting, menu optimization, natural language reporting ("show me last Friday's revenue by channel")
- **Voice ordering** — ElevenLabs-powered phone agent that takes call center orders in Urdu/English without a human
- **WhatsApp commerce** — Customers order, track, and reorder through the app they already use 3 hours a day
- **Franchise-ready** — Central HQ controls menu and pricing, individual branches operate independently, royalty auto-calculated

The endgame: a restaurant chain operator opens one dashboard and sees everything — every location, every order, every rupee, every customer, every rider, every vendor, every kitchen station — in real time. No switching between 8 different tools. One system. One login. One truth.

---

## 2. Platform Architecture

```
                            ┌──────────────────────────────────────────┐
                            │            LOAD BALANCER (ALB)           │
                            │         SSL + WebSocket Upgrade          │
                            └──────────┬───────────┬──────────────────┘
                                       │           │
                    ┌──────────────────┘           └──────────────────┐
                    ▼                                                  ▼
         ┌─────────────────┐                              ┌─────────────────┐
         │  FRONTEND APPS  │                              │   BACKEND API   │
         │  (React + Vite) │                              │    (FastAPI)    │
         ├─────────────────┤                              ├─────────────────┤
         │ POS Terminal    │                              │ REST API (v1)   │
         │ KDS Display     │◄────── WebSocket ──────────►│ WebSocket Hub   │
         │ Owner Mobile    │                              │ Background Jobs │
         │ Customer Portal │                              │ Event Bus       │
         │ Vendor Portal   │                              └────────┬────────┘
         │ QR Order Page   │                                       │
         │ Admin Dashboard │                              ┌────────┴────────┐
         └─────────────────┘                              │                 │
                                                ┌─────────┴──┐     ┌───────┴───────┐
                                                │ PostgreSQL │     │     Redis      │
                                                │  (Primary) │     │ Cache + PubSub │
                                                ├────────────┤     │ + Job Queue    │
                                                │ Read       │     └───────────────┘
                                                │ Replicas   │
                                                └────────────┘
                                                          │
                              ┌────────────────────────────┼────────────────────────────┐
                              │                            │                            │
                    ┌─────────┴────────┐       ┌──────────┴─────────┐      ┌──────────┴─────────┐
                    │  INTEGRATIONS    │       │   AI / ML LAYER    │      │  COMMUNICATION     │
                    ├──────────────────┤       ├────────────────────┤      ├────────────────────┤
                    │ QuickBooks API   │       │ Claude API         │      │ WhatsApp Business  │
                    │ Foodpanda API    │       │ Demand Forecasting │      │ ElevenLabs Voice   │
                    │ FBR / PRA Tax    │       │ Menu Optimization  │      │ SMS Gateway        │
                    │ Payment Gateway  │       │ NLP Query Engine   │      │ Email (Transact.)  │
                    │ Google Maps API  │       │ Anomaly Detection  │      │ Push Notifications │
                    └──────────────────┘       └────────────────────┘      └────────────────────┘
```

---

## 3. Foundation — What's Already Built

### Phases 1-5: COMPLETE

| Phase | What | Status |
|-------|------|--------|
| 1. Foundation | Project structure, Docker, FastAPI skeleton, React skeleton, CI/CD | Done |
| 2. Auth + Tenant | JWT auth, PIN login, roles/permissions, multi-tenant schema, refresh tokens | Done |
| 3. Menu Engine | Categories, items, modifiers, menu grid, cart system, modifier modal | Done |
| 4. Floor Plan | Floors, tables (drag-drop editor), shape/status rendering, dine-in integration | Done |
| 5. Orders + Dashboard | Order state machine, YYMMDD numbering, dashboard KPIs, reports, CSV export, order ticker | Done |

**Current database:** 20+ tables, all UUID PK + tenant_id
**Current API:** 30+ endpoints under `/api/v1/`
**Current frontend:** 13 lazy-loaded pages, Zustand state, real-time polling

---

## 4. Core Completion — Phases 6-10

These phases complete the prototype into a shippable product.

---

### Phase 6: Kitchen Display System (KDS)

**Priority:** CRITICAL — This is the #1 gap in the prototype
**Estimated effort:** 2 weeks
**Dependencies:** Phase 5 (orders) — DONE

#### What It Does
Dedicated fullscreen kitchen screens showing live order tickets. Each station sees only their items. Cooks bump tickets when done. Entire restaurant sees real-time kitchen progress.

#### Database Tables
| Table | Purpose |
|-------|---------|
| `kitchen_stations` | Station definitions (Grill, Fryer, Beverage, Dessert) with display_order, color |
| `kitchen_station_categories` | Which menu categories route to which station |
| `kitchen_station_menu_items` | Item-level overrides (specific item → specific station) |
| `kitchen_tickets` | One ticket per station per order (status: pending → in_progress → completed) |
| `kitchen_ticket_items` | Line items on each ticket with quantities and modifiers |

#### Routing Logic
1. Order confirmed → system checks each item's category
2. Category → station mapping determines which station gets which items
3. Item-level overrides take priority over category-level
4. One `kitchen_ticket` created per station per order
5. Combo items decomposed and routed independently
6. When ALL tickets for an order are completed → order auto-transitions to `ready`

#### API Endpoints
```
POST   /api/v1/kitchen/stations              Create station
GET    /api/v1/kitchen/stations              List stations
PUT    /api/v1/kitchen/stations/{id}         Update station
DELETE /api/v1/kitchen/stations/{id}         Delete station
POST   /api/v1/kitchen/stations/{id}/categories   Assign categories
GET    /api/v1/kitchen/tickets               List tickets (filter by station, status)
PATCH  /api/v1/kitchen/tickets/{id}/bump     Bump ticket to next status
PATCH  /api/v1/kitchen/tickets/{id}/recall   Recall a bumped ticket
GET    /api/v1/kitchen/tickets/{id}/timing   Get timing data for a ticket
```

#### Frontend: KDS Page
- **Fullscreen mode** — no nav bar, no distractions, F11-style
- **Kanban columns** — Pending | In Progress | Completed (or configurable)
- **Ticket cards** — order number, table/channel, items with modifiers, elapsed timer
- **Color-coded urgency** — green (<8 min), yellow (8-15 min), red (>15 min) — thresholds configurable
- **BUMP button** — large (100px+), easy to tap with wet/greasy hands
- **Recall button** — bring back a bumped ticket if something was wrong
- **Audio alert** — chime on new ticket arrival (configurable sound)
- **Station selector** — dropdown or tabs to switch station view, plus "All Stations"
- **Auto-scroll** — oldest tickets always visible, auto-scroll as new ones arrive
- **WebSocket-driven** — instant updates, no polling delay

#### WebSocket Events
```
kitchen:{station_id}  → new_ticket, ticket_updated, ticket_bumped
kitchen:all           → all kitchen events (for manager view)
orders                → order status change propagated to POS screens
```

---

### Phase 7: Payments

**Priority:** CRITICAL — Can't go live without payments
**Estimated effort:** 2 weeks
**Dependencies:** Phase 6 (KDS)

#### What It Does
Full payment processing — cash, card, mobile wallet, split checks, tips, refunds, cash drawer management. Supports both `order_first` (dine-in) and `pay_first` (QSR) flows via `restaurant_configs.payment_flow`.

#### Database Tables
| Table | Purpose |
|-------|---------|
| `payment_methods` | Configured payment types (Cash, Visa, JazzCash, Easypaisa, etc.) |
| `payments` | Individual payment records linked to orders (amount, method, tip, reference) |
| `cash_drawer_sessions` | Open/close sessions with expected vs actual cash, variance |

#### Key Features
- **Cash calculator** — enter amount tendered, auto-calculate change
- **Split payment** — pay partially with card, rest with cash (unlimited splits)
- **Tip handling** — on-screen prompt (10%, 15%, 20%, custom) or manual entry
- **Pay-first flow** — for QSR: payment collected before kitchen fires (configurable per restaurant)
- **Refunds** — full or partial, linked to original payment, requires manager PIN
- **Cash drawer** — open session at shift start, close with count at shift end, variance report
- **Receipt generation** — thermal printer format with restaurant logo, itemized list, tax breakdown, payment method

#### Payment Flow: order_first vs pay_first
```
ORDER FIRST (Traditional Dine-In):
  Order created → Kitchen fires → Food served → Bill requested → Payment collected → Order completed

PAY FIRST (QSR / Fast Casual):
  Order created → Payment collected → Kitchen fires → Food ready → Customer picks up → Order completed
```

---

### Phase 8: Call Center Channel

**Priority:** HIGH — One of the 3 core channels
**Estimated effort:** 1.5 weeks
**Dependencies:** Phase 7 (payments)

#### What It Does
Phone rings → agent looks up customer by phone number → sees order history → takes new order → assigns to delivery or pickup → tracks through completion.

#### Database Tables
| Table | Purpose |
|-------|---------|
| `customers` | Phone, name, addresses (JSON array), order history stats, notes, loyalty tier |
| `customer_addresses` | Normalized addresses with GPS coordinates, delivery zone, landmark |

#### Key Features
- **Phone lookup** — type phone number, instant customer match (pg_trgm fuzzy search)
- **New customer** — quick-add form (name + phone + address in under 30 seconds)
- **Order history** — last 10 orders shown, "reorder" button for any previous order
- **Address book** — customer can have multiple saved addresses, default highlighted
- **Delivery zone validation** — auto-check if address is within delivery radius
- **Order assignment** — create order with delivery/pickup flag, assign to rider or mark for pickup
- **Customer notes** — "allergic to peanuts", "always wants extra chutney", "VIP — owner's friend"

---

### Phase 9: Reports + Admin

**Priority:** HIGH — Owner/manager daily necessity
**Estimated effort:** 2 weeks
**Dependencies:** Phase 8

#### What It Does
Comprehensive reporting suite + admin management panels for staff, menu, settings, and configuration.

#### Reports
| Report | Description |
|--------|-------------|
| **Z-Report (End of Day)** | Total sales, tax collected, payment method breakdown, voids, discounts, cash drawer variance |
| **Sales Summary** | Revenue by channel, by hour, by day, by category — with comparison periods |
| **Item Sales** | Every item sold with quantity, revenue, avg modifiers, food cost % (when BOM available) |
| **Staff Performance** | Orders per server, avg ticket value, avg time to close, voids initiated |
| **Table Turnover** | Avg time per cover, turnover rate by table, peak occupancy times |
| **Channel Mix** | Dine-in vs takeaway vs call center vs Foodpanda — revenue and order count split |
| **Tax Report** | FBR/PRA-ready tax summary by rate, by category, by period |
| **Discount & Void Report** | Every discount/void with who authorized it, reason, amount — fraud detection |
| **Hourly Heatmap** | Visual grid showing order volume by hour × day of week |

#### Admin Panels
- **Staff Management** — CRUD users, assign roles, reset PINs, view activity log
- **Menu Management** — already built (Phase 3), enhanced with bulk edit, import/export
- **Restaurant Settings** — business info, tax rates, payment flow, receipt template, operating hours
- **Floor Editor** — already built (Phase 4), enhanced with reservation overlay

#### Export Formats
- **PDF** — branded, print-ready, with restaurant logo and date range
- **Excel (.xlsx)** — raw data with formulas, pivot-ready
- **CSV** — for QuickBooks import or data analysis
- **Email** — scheduled daily/weekly reports to owner's email

---

### Phase 10: Polish + Integration Stubs

**Priority:** MEDIUM — Final prototype hardening
**Estimated effort:** 1.5 weeks
**Dependencies:** Phase 9

#### What It Does
Production readiness — error handling, loading states, offline resilience, touch optimization, accessibility, and abstract adapter interfaces for all future integrations.

#### Checklist
- [ ] Error boundaries on every page (graceful crash recovery)
- [ ] Loading skeletons (not spinners) for every data fetch
- [ ] Toast notifications for all user actions (order created, payment received, etc.)
- [ ] Touch target audit — minimum 48px general, 56px POS buttons, 72px number pad
- [ ] Keyboard shortcuts for power users (N = new order, P = payment, K = kitchen view)
- [ ] Network error handling — retry with exponential backoff, offline queue
- [ ] Audit log table — every significant action logged with user, timestamp, before/after
- [ ] Integration adapter interfaces — abstract base classes for QuickBooks, FBR, Foodpanda, Payment Gateway, WhatsApp, Voice
- [ ] Performance pass — lazy loading, virtualized lists for large datasets, image optimization
- [ ] Security audit — OWASP top 10 review, rate limiting, input sanitization, SQL injection check
- [ ] Demo seed data — complete restaurant setup for sales demos

---

## 5. Tier 1 — Revenue & Financial Operations

Post-prototype modules that directly impact revenue tracking, accounting, and financial control.

---

### Module 5.1: QuickBooks Integration

**Priority:** CRITICAL — Client's #1 integration requirement
**Estimated effort:** 3-4 weeks
**Dependencies:** Phase 7 (payments), Phase 9 (reports)

#### Overview
Bidirectional sync between POS and QuickBooks (Online + Desktop). Every sale, tax, payment, void, and refund flows into QB automatically. The accountant never manually enters a sales receipt again.

#### Supported QuickBooks Versions
| Version | Integration Method | Sync Type |
|---------|-------------------|-----------|
| **QB Online** (Simple Start, Essentials, Plus, Advanced) | REST API via OAuth 2.0 | Real-time or batched |
| **QB Desktop** (Pro, Premier, Enterprise) | Web Connector (QBWC) via SOAP/XML | Scheduled sync (every 15 min) |

#### What Syncs: POS → QuickBooks

| POS Event | QB Object Created | Details |
|-----------|------------------|---------|
| Order completed | **Sales Receipt** | Line items, quantities, modifiers as sub-items, discount as line |
| Payment received | **Payment** (linked to Sales Receipt) | Method (Cash/Card/Wallet), amount, tip as separate line |
| Void / Refund | **Refund Receipt** or **Credit Memo** | Linked to original Sales Receipt, reason captured |
| Daily close (Z-Report) | **Journal Entry** (optional) | Summarized daily sales if client prefers summary over per-order |
| Tax collected | Mapped to **Tax Codes / Tax Rates** | FBR/PRA tax rates mapped to QB tax codes |
| Tips collected | **Other Current Liability** or **Expense** | Based on client's tip handling preference (pooled vs individual) |
| Cash drawer variance | **Expense** entry | Over/short posted to designated account |

#### What Syncs: QuickBooks → POS

| QB Data | POS Usage |
|---------|-----------|
| Chart of Accounts | Account mapping UI — income, tax, expense accounts |
| Vendors | Populate vendor list in Vendor Portal module |
| Items / Products | Optional — sync QB inventory items as menu items |
| Tax Codes | Validate POS tax configuration matches QB |

#### Account Mapping UI
Elite admin interface where the restaurant owner (or their accountant) maps POS categories to QB accounts:

```
┌─────────────────────────────────────────────────────────────┐
│  QUICKBOOKS ACCOUNT MAPPING                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Food Sales (Dine-In)      →  [Sales > Food Revenue    ▼]  │
│  Food Sales (Takeaway)     →  [Sales > Food Revenue    ▼]  │
│  Food Sales (Delivery)     →  [Sales > Delivery Rev    ▼]  │
│  Food Sales (Foodpanda)    →  [Sales > 3P Marketplace  ▼]  │
│  Beverage Sales            →  [Sales > Beverage Rev    ▼]  │
│  FBR Tax Collected         →  [Liability > FBR Tax     ▼]  │
│  PRA Tax Collected         →  [Liability > PRA Tax     ▼]  │
│  Tips Collected            →  [Liability > Tips Payable▼]  │
│  Cash Over/Short           →  [Expense > Cash Variance ▼]  │
│  Discounts Given           →  [Expense > Discounts     ▼]  │
│  Foodpanda Commission      →  [Expense > 3P Commission ▼]  │
│                                                             │
│  Sync Mode:  ○ Per-Order (real-time)  ● Daily Summary       │
│  Last Sync:  Feb 10, 2026 11:42 PM  ✅ Success             │
│                                                             │
│  [ Test Connection ]  [ Force Sync Now ]  [ View Sync Log ] │
└─────────────────────────────────────────────────────────────┘
```

#### Sync Engine Architecture
```
POS Order Event
     │
     ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Event Bus   │────►│  Sync Queue  │────►│  QB Adapter  │
│  (Redis)     │     │  (Redis)     │     │  (Abstract)  │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
                                    ┌─────────────┴─────────────┐
                                    │                           │
                             ┌──────┴──────┐            ┌──────┴──────┐
                             │  QB Online  │            │ QB Desktop  │
                             │  REST API   │            │ Web Connect │
                             │  OAuth 2.0  │            │ SOAP/XML    │
                             └─────────────┘            └─────────────┘
```

#### Resilience
- **Retry queue** — if QB API is down, events queue in Redis and retry with exponential backoff
- **Idempotency** — every sync event has a unique ID; re-sending the same event is safe
- **Sync log** — every sync attempt logged with status, QB response, error detail
- **Manual retry** — admin can view failed syncs and retry individually
- **Conflict resolution** — POS is source of truth for sales data; QB is source of truth for chart of accounts

#### QB Desktop Specifics
- Uses **QuickBooks Web Connector (QBWC)** — a small app installed on the client's QB Desktop machine
- POS exposes a SOAP endpoint that QBWC polls every 15 minutes
- Supports: Sales Receipts, Payments, Refunds, Journal Entries, Vendor Bills
- Limitations: no real-time sync, no webhook capability, requires the QB Desktop machine to be on
- Migration path: if client moves from Desktop to Online, flip the adapter — zero POS changes

---

### Module 5.2: FBR / PRA Tax Integration

**Priority:** HIGH — Legal requirement for Pakistani restaurants
**Estimated effort:** 2 weeks
**Dependencies:** Phase 7 (payments)

#### Overview
Federal Board of Revenue (FBR) and Punjab Revenue Authority (PRA) require POS-integrated tax reporting for restaurants above the revenue threshold. Every invoice must be reported, and an FBR/PRA fiscal ID must be printed on each receipt.

#### Database Tables
| Table | Purpose |
|-------|---------|
| `tax_groups` | Named tax group (e.g., "Standard GST", "Reduced Rate") |
| `tax_rates` | Individual rates within a group (FBR 17%, PRA 16%, etc.) with authority reference |
| `tax_invoices` | Fiscal invoice records submitted to FBR/PRA with response codes |

#### Integration Flow
```
Order Completed + Payment Received
     │
     ▼
Generate Tax Invoice (POS-side)
     │
     ▼
Submit to FBR API / PRA API
     │
     ▼
Receive Fiscal Invoice Number (FIN)
     │
     ▼
Print FIN + QR Code on Customer Receipt
     │
     ▼
Log in tax_invoices table (audit trail)
```

#### Features
- **Dual authority support** — FBR (federal) and PRA (Punjab provincial) calculated independently
- **Tax-inclusive pricing** — menu prices include tax; system back-calculates tax amount
- **Tax exemptions** — certain items exempt (e.g., uncooked food items)
- **Fiscal receipt** — QR code on receipt linking to FBR/PRA verification portal
- **Monthly tax summary** — report matching FBR/PRA portal totals for accountant reconciliation
- **Sandbox mode** — test against FBR/PRA sandbox before going live

---

### Module 5.3: Foodpanda Integration

**Priority:** HIGH — Significant revenue channel
**Estimated effort:** 2-3 weeks
**Dependencies:** Phase 6 (KDS), Phase 7 (payments)

#### Overview
Foodpanda orders appear in the POS automatically — same kitchen pipeline, same reporting, same everything. No more separate Foodpanda tablet sitting on the counter.

#### Integration Flow
```
Customer orders on Foodpanda App
     │
     ▼
Foodpanda API → Webhook to POS Backend
     │
     ▼
POS creates order (channel = "foodpanda", auto-confirmed)
     │
     ▼
Kitchen ticket generated → KDS shows Foodpanda badge
     │
     ▼
Kitchen bumps → POS notifies Foodpanda: "Ready for pickup"
     │
     ▼
Foodpanda rider picks up → POS marks delivered
     │
     ▼
Revenue recorded (minus Foodpanda commission) → Syncs to QB
```

#### Features
- **Auto-accept or manual accept** — configurable per restaurant
- **Menu sync** — POS menu pushes to Foodpanda (prices, availability, photos)
- **Availability toggle** — mark items as unavailable on Foodpanda from POS
- **Prep time broadcast** — tell Foodpanda estimated prep time so rider arrives on time
- **Commission tracking** — Foodpanda's commission auto-calculated and shown in reports
- **Separate reporting** — Foodpanda revenue tracked independently for P&L clarity
- **Busy mode** — temporarily increase prep time or pause Foodpanda orders during rush
- **Order aggregation** — Foodpanda orders show alongside dine-in/takeaway in unified order list

#### Future: Multi-Aggregator
Same architecture extends to other platforms:
- Cheetay
- Careem Food (if available)
- Any future aggregator with webhook/API support

---

### Module 5.4: Internal Delivery Fleet + Rider GPS

**Priority:** HIGH — Restaurant's own delivery channel
**Estimated effort:** 3 weeks
**Dependencies:** Phase 8 (call center/customers)

#### Overview
Restaurant's own riders tracked via GPS. Dispatch, route optimization, real-time tracking, proof of delivery. The customer and call center agent both see where the rider is.

#### Database Tables
| Table | Purpose |
|-------|---------|
| `riders` | Rider profile (name, phone, vehicle, status: online/offline/on_delivery) |
| `rider_locations` | GPS pings (lat, lng, timestamp, accuracy) — time-series |
| `deliveries` | Delivery assignment (order_id, rider_id, pickup_time, delivery_time, status) |
| `delivery_zones` | Polygon definitions for delivery area boundaries + delivery fee rules |

#### Rider Mobile Interface
Riders get a lightweight mobile web app (not a native app — runs in any browser):
- **Accept/reject** delivery assignment
- **Navigation** — one-tap Google Maps/Waze integration
- **Status updates** — "Picked up" → "On the way" → "Delivered"
- **Proof of delivery** — photo capture or customer OTP confirmation
- **Earnings tracker** — today's deliveries, distance, tips

#### Dispatch Logic
```
New Delivery Order
     │
     ▼
Find available riders (status = online, not on delivery)
     │
     ▼
Rank by: distance to restaurant → current location → delivery count today
     │
     ▼
Auto-assign (or manual assign by dispatcher)
     │
     ▼
Rider gets push notification → Accepts → Timer starts
```

#### Live Tracking Map
- **Call center agent** sees rider's live dot on map while customer is on phone
- **Customer** gets WhatsApp link with live tracking (like Careem/Uber)
- **Manager dashboard** shows all active riders with status badges
- **Geofence alerts** — rider enters restaurant zone → "rider arriving" notification
- **Historical routes** — replay any delivery path for dispute resolution

---

## 6. Tier 2 — Customer Experience & Engagement

Modules that directly improve the customer's experience and drive repeat visits.

---

### Module 6.1: Customer Loyalty & Rewards Engine

**Priority:** HIGH — Proven ROI in restaurant industry
**Estimated effort:** 2-3 weeks
**Dependencies:** Phase 8 (customers)

#### Overview
Points-based loyalty system where customers earn on every order and redeem for discounts, free items, or upgrades. Tiered membership drives higher spending.

#### Tier Structure
| Tier | Requirement | Perks |
|------|-------------|-------|
| **Member** | Sign up | Earn 1 point per Rs.100 spent |
| **Silver** | 500 points lifetime | 1.25x earn rate, birthday reward |
| **Gold** | 2,000 points lifetime | 1.5x earn rate, priority delivery, monthly surprise |
| **Platinum** | 5,000 points lifetime | 2x earn rate, free delivery, exclusive menu items, owner's table reservation |

#### Database Tables
| Table | Purpose |
|-------|---------|
| `loyalty_tiers` | Tier definitions (name, threshold, earn multiplier, perks JSON) |
| `loyalty_accounts` | Customer's current points balance, lifetime earned, tier, join date |
| `loyalty_transactions` | Every earn/redeem/adjust with order reference and timestamp |
| `loyalty_rewards` | Redeemable rewards catalog (free item, discount %, flat discount) |

#### Features
- **Auto-earn** — points calculated and credited on order completion (no staff action needed)
- **Earn on all channels** — dine-in, takeaway, call center, online (not Foodpanda — they have their own loyalty)
- **Redeem at POS** — cashier types phone number → sees points → applies reward
- **Points expiry** — configurable (12 months of inactivity)
- **Referral bonus** — share code, both get bonus points
- **Birthday auto-reward** — CRM triggers free dessert/discount on birthday month
- **SMS/WhatsApp notification** — "You earned 50 points! 120 more to unlock Gold tier"

---

### Module 6.2: QR Code Table Ordering

**Priority:** HIGH — Modern restaurant standard
**Estimated effort:** 2 weeks
**Dependencies:** Phase 6 (KDS), Phase 7 (payments)

#### Overview
Each table has a unique QR code. Customer scans with phone camera → sees the full menu → orders and pays from their phone → kitchen receives the order automatically. Zero app download required.

#### Flow
```
Customer scans QR code (printed on table tent / sticker)
     │
     ▼
Opens web page: order.restaurant.com/table/T-05
     │
     ▼
Sees full menu with photos, descriptions, prices
     │
     ▼
Adds items to cart, selects modifiers
     │
     ▼
Submits order (optional: pay now or pay later)
     │
     ▼
POS receives order → table status updates → kitchen ticket fires
     │
     ▼
Customer sees order status on phone: "Preparing..." → "Ready!"
```

#### Features
- **No app download** — pure web (PWA), works in any phone browser
- **Multi-language** — Urdu + English toggle
- **Photos for every item** — high-res, appetizing
- **Allergen info** — tags on each item (nuts, dairy, gluten)
- **Reorder / Add more** — scan again to add items to existing table order
- **Call waiter** — button to request server attention (shows alert on POS)
- **Bill request** — request bill from phone, pay via JazzCash/Easypaisa/card
- **Upsell prompts** — "Add a drink for Rs.150?" based on cart contents
- **QR generation** — admin can generate and print QR codes for all tables

---

### Module 6.3: Online Ordering Portal (Branded)

**Priority:** HIGH — Eliminate aggregator commission
**Estimated effort:** 3-4 weeks
**Dependencies:** Phase 7 (payments), Module 5.4 (delivery)

#### Overview
Client's own branded website for direct orders. Customer orders from `restaurant.pk` — same menu, same kitchen pipeline, zero Foodpanda commission. Saves 25-30% per order.

#### Pages
| Page | Description |
|------|-------------|
| **Landing** | Restaurant hero banner, featured items, location/hours, "Order Now" CTA |
| **Menu** | Full menu with categories, search, dietary filters, photos |
| **Cart + Checkout** | Item customization, delivery/pickup toggle, address, payment |
| **Order Tracking** | Real-time status + rider GPS (for delivery) |
| **Account** | Order history, saved addresses, loyalty points, reorder |

#### Features
- **Delivery + Pickup** — customer chooses; pickup shows estimated ready time
- **Delivery fee calculation** — based on distance (Google Maps API) and delivery zone rules
- **Minimum order** — configurable per zone
- **Promo codes** — apply discount codes at checkout
- **Guest checkout** — no account required (phone number only)
- **Payment** — JazzCash, Easypaisa, credit/debit card, cash on delivery
- **SEO-optimized** — server-side rendered menu pages, Google My Business integration
- **Responsive** — phone-first design, works on desktop too

---

### Module 6.4: Table Reservation System

**Priority:** MEDIUM — Important for fine-dining / premium restaurants
**Estimated effort:** 1.5 weeks
**Dependencies:** Phase 4 (floor plan), Phase 8 (customers)

#### Overview
Customers reserve tables via phone, WhatsApp, or online. Reservations show on the floor plan. When guests arrive, reservation converts to active dine-in order.

#### Database Tables
| Table | Purpose |
|-------|---------|
| `reservations` | Customer, date/time, party size, table (optional), status, special requests |

#### Features
- **Floor plan overlay** — reserved tables shown with time badge ("Reserved 7:30 PM - Ahmed, 4 guests")
- **Auto-assign table** — system suggests best table based on party size and availability
- **Confirmation** — auto-send WhatsApp/SMS confirmation with details
- **Reminder** — 2-hour-before reminder via WhatsApp
- **No-show tracking** — mark no-shows, flag repeat offenders in CRM
- **Waitlist** — when fully booked, add to waitlist with estimated wait time
- **Walk-in priority** — distinguish reserved vs walk-in for capacity planning
- **CRM integration** — returning customer? System knows their preferred table, last visit, order history

---

### Module 6.5: Customer-Facing Display (CFD)

**Priority:** MEDIUM — Trust builder + upsell opportunity
**Estimated effort:** 1 week
**Dependencies:** Phase 5 (orders)

#### Overview
Second screen at the counter showing the customer their order as it's rung up. Also displays promos, specials, and restaurant branding during idle time.

#### Display Modes
| Mode | When | Shows |
|------|------|-------|
| **Idle** | No active transaction | Restaurant logo, rotating promos, social media handles, WiFi password |
| **Active** | Order being built | Live cart — items, modifiers, running total, tax |
| **Payment** | Payment screen | Total due, payment method, tip prompt |
| **Confirmed** | Order placed | Order number, estimated time, "Thank you!" |

#### Features
- **Separate browser window** — runs on a second monitor, no extra hardware cost
- **Promo rotation** — admin uploads images/videos that cycle during idle
- **Tip prompt** — optional on-screen tip selection (shown to customer, not cashier)
- **Multi-language** — switches between Urdu and English

---

### Module 6.6: Digital Menu Boards

**Priority:** MEDIUM — Professional restaurant feel
**Estimated effort:** 1.5 weeks
**Dependencies:** Phase 3 (menu engine)

#### Overview
TV screens in the restaurant showing the menu, synced with POS. Prices, item availability, and promos update in real-time. No more printing menus when prices change.

#### Features
- **POS-synced** — menu changes in admin reflect on screens within seconds
- **Availability** — sold-out items auto-grayed-out when marked unavailable in POS
- **Day-parting** — show breakfast menu in morning, lunch in afternoon, dinner in evening (auto-scheduled)
- **Promo zones** — designated areas on screen for rotating promotional content
- **Multi-screen** — different screens can show different categories (Screen 1: Mains, Screen 2: Beverages & Desserts)
- **Template system** — pre-designed layouts (grid, list, featured hero) — admin picks from templates
- **Branding** — restaurant colors, logo, fonts applied automatically
- **Hardware** — any smart TV with a browser, or Chromecast/Fire Stick, or dedicated signage player

---

## 7. Tier 3 — Intelligence & Automation

AI/ML-powered modules that make the restaurant smarter over time.

---

### Module 7.1: AI Copilot (Claude API / LLM Integration)

**Priority:** HIGH — Major differentiator
**Estimated effort:** 3-4 weeks
**Dependencies:** Phase 9 (reports), all data-generating modules

#### Overview
An AI assistant embedded in the POS that the restaurant owner/manager can talk to in plain English (or Urdu). Ask questions, get insights, receive proactive recommendations.

#### Capabilities

**Natural Language Reporting**
```
Owner: "How did we do last Friday compared to the Friday before?"

AI: "Last Friday (Feb 7) revenue was Rs.487,200 — that's 12% higher than Jan 31 (Rs.435,000).
     The increase was driven by dine-in (+18%) while takeaway was flat.
     Your top seller was Chicken Biryani (89 orders, up from 71).
     Kitchen avg time improved to 11.2 minutes (was 13.8).
     Recommendation: you were understaffed on the beverage station —
     drink orders took 40% longer than food orders."
```

**Menu Optimization**
```
Owner: "Which items should I consider removing from the menu?"

AI: "Based on last 90 days:
     - Dal Makhani: 12 orders total, 0.3% of revenue, Rs.180 food cost (47% food cost ratio)
     - Fish Fingers: 8 orders, consistently slow prep (14 min avg), 2 complaints
     - Chocolate Lava Cake: 5 orders, requires specialized prep, ingredient waste

     Removing these 3 items would simplify kitchen ops and save ~Rs.12,000/month
     in ingredient waste. Consider replacing with items similar to your top 5."
```

**Anomaly Detection**
```
AI Alert: "Unusual activity detected: 4 voids in last hour by cashier Amir (avg is 0.5/hour).
          Total voided: Rs.8,400. This exceeds the 3-sigma threshold.
          Manager review recommended."
```

**Demand Prediction**
```
Owner: "What should I prep for tomorrow?"

AI: "Tomorrow is Saturday + PSL match day. Based on historical patterns:
     - Expected orders: 180-210 (normal Saturday: 150)
     - Chicken demand: +35% (biryani and tikka surge during matches)
     - Beverage demand: +60% (cold drinks spike)
     - Prep recommendation: 25kg chicken (vs usual 18kg),
       extra drinks stock, consider calling in 1 additional kitchen staff"
```

#### Technical Architecture
```
User query (text or voice)
     │
     ▼
┌──────────────┐
│ Context      │ ← Pulls relevant data: recent orders, KPIs,
│ Builder      │   menu items, staff schedule, weather, events
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Claude API   │ ← System prompt with restaurant context
│ (Opus/Sonnet)│   + function calling for live data queries
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Response     │ ← Formatted for display: text, charts,
│ Renderer     │   actionable buttons ("Apply recommendation")
└──────────────┘
```

#### Function Calling Tools (for Claude API)
| Tool | What It Does |
|------|-------------|
| `query_sales` | Get sales data by date range, channel, category, item |
| `query_inventory` | Check current stock levels, predicted usage |
| `query_staff` | Staff schedules, performance metrics |
| `query_customers` | Customer segments, loyalty data, order patterns |
| `query_kitchen` | Ticket times, station performance, bottlenecks |
| `create_report` | Generate a formatted report on-the-fly |
| `send_alert` | Push notification to manager's phone |

---

### Module 7.2: ElevenLabs Voice Integration

**Priority:** MEDIUM-HIGH — Innovative differentiator
**Estimated effort:** 3 weeks
**Dependencies:** Module 7.1 (AI copilot), Phase 8 (call center)

#### Overview
AI voice agent that answers the restaurant's phone, takes orders in natural Urdu/English, and feeds them directly into the POS. Reduces call center staffing needs by handling routine orders automatically.

#### Flow
```
Customer calls restaurant
     │
     ▼
IVR greeting: "Welcome to [Restaurant]. Press 1 to order, 2 for reservations, 0 for staff"
     │
     ▼ (Press 1)
ElevenLabs Voice Agent activates
     │
     ▼
Voice Agent: "Assalam o alaikum! What would you like to order today?"
     │
     ▼
Customer: "Mujhe 2 chicken biryani chahiye aur 1 seekh kebab, extra spicy"
     │
     ▼
Speech-to-Text (Whisper/ElevenLabs) → Text
     │
     ▼
Claude API parses intent → maps to menu items + modifiers
     │
     ▼
Voice Agent: "Sure! 2 Chicken Biryani and 1 Seekh Kebab with extra spice.
              Your total is Rs.2,850. Delivery or pickup?"
     │
     ▼
Customer confirms → Order created in POS → Kitchen fires
     │
     ▼
Voice Agent: "Your order #240210-015 will be ready in 25 minutes.
              We'll send you a WhatsApp update. Shukriya!"
```

#### Voice Personas
| Persona | Language | Accent | Use Case |
|---------|----------|--------|----------|
| **Ayesha** | Urdu | Pakistani | Primary — most customers |
| **Ali** | English | Pakistani English | English-speaking customers |
| **Bilingual** | Mixed | Code-switching | Handles Urdu-English mix naturally |

#### Features
- **Natural conversation** — handles interruptions, corrections, "wait, change that to..."
- **Menu knowledge** — knows every item, modifier, combo, price, availability
- **Customer recognition** — phone number lookup → "Welcome back! Would you like your usual — 2 Biryani and 1 Raita?"
- **Upsell** — "Would you like to add a drink? We have a special on Lassi today"
- **Handoff to human** — if confused or customer requests, seamlessly transfers to call center agent
- **Call recording** — every call recorded and transcribed for quality/dispute resolution
- **Analytics** — call volume, avg duration, successful orders, handoff rate, peak hours

#### Fallback Hierarchy
1. Voice agent handles the call
2. If confidence drops below threshold → "Let me connect you with our team"
3. Transfer to call center agent with full context (customer name, what they've said so far)
4. If no agent available → "Can I take your number and have someone call you back in 5 minutes?"

---

### Module 7.3: AI Demand Forecasting

**Priority:** MEDIUM — High value for operations
**Estimated effort:** 2 weeks
**Dependencies:** Module 7.1 (AI copilot), Module 9.1 (BOM)

#### Overview
Uses historical order data, day-of-week patterns, weather, events (PSL matches, Eid, Ramadan), and trends to predict demand at the item level. Outputs prep recommendations and staffing suggestions.

#### Prediction Outputs
| Output | Granularity | Horizon |
|--------|-------------|---------|
| **Order volume** | Per hour | Next 7 days |
| **Item demand** | Per item | Next 3 days |
| **Ingredient needs** | Per ingredient (via BOM) | Next 3 days |
| **Staff recommendation** | Per station | Next 7 days |
| **Revenue forecast** | Daily | Next 30 days |

#### Data Sources
- Historical orders (minimum 3 months for reliable predictions)
- Day of week + time of day patterns
- Weather API (hot days → more cold drinks)
- Pakistan event calendar (Eid, Ramadan, PSL, holidays)
- Promotional calendar (if running a discount, demand spikes)
- Recent trends (is biryani demand increasing or decreasing week-over-week?)

#### Display
- **Prep Sheet** — printed or displayed: "Tomorrow's prep: 25kg chicken, 10kg rice, 5kg daal..."
- **Dashboard widget** — "Expected: 180 orders, Rs.450K revenue, Peak: 1-2 PM"
- **Alert** — "Chicken stock may run out by 8 PM based on current consumption rate"

---

### Module 7.4: Dynamic Pricing & Promotions Engine

**Priority:** MEDIUM — Revenue optimization
**Estimated effort:** 2 weeks
**Dependencies:** Phase 3 (menu), Phase 5 (orders)

#### Overview
Rules-based engine that automatically adjusts prices, creates deals, and runs promotions based on configurable triggers. No manual intervention needed once rules are set.

#### Rule Types
| Rule | Example | Trigger |
|------|---------|---------|
| **Happy Hour** | 20% off beverages 3-5 PM | Time of day |
| **BOGO** | Buy 1 Biryani, get Raita free | Item combination |
| **Combo Deal** | Burger + Fries + Drink = Rs.750 (save Rs.200) | Bundle |
| **Slow Day Boost** | 15% off all dine-in on Tuesdays | Day of week |
| **Minimum Order** | Free delivery on orders over Rs.2,000 | Cart total |
| **Channel Special** | Extra 10% off on online orders | Order channel |
| **Flash Sale** | 50% off desserts for next 2 hours (manager activates) | Manual trigger |
| **Surge Pricing** | Delivery fee +Rs.100 during rain/peak hours | External condition |
| **Loyalty Exclusive** | Gold tier gets 10% off every order | Customer tier |

#### Features
- **Rule builder UI** — admin creates rules with conditions and actions (no code)
- **Stack control** — configure whether promotions can combine or are mutually exclusive
- **Budget limits** — "run this promo until Rs.50,000 in discounts given, then auto-stop"
- **A/B testing** — run two promo variants, measure which drives more revenue
- **Analytics** — per-promotion ROI: revenue lift vs discount cost

---

## 8. Tier 4 — Communication & Marketing

Modules that handle customer communication, marketing, and brand presence.

---

### Module 8.1: WhatsApp Business API Integration

**Priority:** HIGH — Pakistan's #1 communication channel
**Estimated effort:** 3 weeks
**Dependencies:** Phase 8 (customers), Module 5.4 (delivery)

#### Overview
WhatsApp is how Pakistan communicates. This module turns WhatsApp into a full ordering, tracking, and marketing channel. Customers order, track, get receipts, and receive promos — all inside WhatsApp.

#### Capabilities

**Transactional Messages (Triggered Automatically)**
| Event | WhatsApp Message |
|-------|-----------------|
| Order confirmed | "Your order #240210-015 is confirmed! Estimated time: 25 min" |
| Kitchen ready | "Your order is ready! Pick up at counter 2" |
| Rider assigned | "Ahmed is on the way! Track: [live tracking link]" |
| Delivered | "Delivered! Rate your experience: [feedback link]" |
| Reservation confirmed | "Table for 4 confirmed: Feb 14, 7:30 PM. See you there!" |
| Loyalty milestone | "Congrats! You've reached Gold tier! Enjoy 1.5x points on every order" |
| Birthday | "Happy Birthday! Here's a free dessert on us. Show this message at checkout" |

**WhatsApp Bot (Conversational)**
```
Customer: "Menu"
Bot: Shows interactive menu with category buttons

Customer: Taps "Biryani"
Bot: Shows biryani options with photos and prices
     [Chicken Biryani - Rs.850] [Mutton Biryani - Rs.1,200] [Veg Biryani - Rs.650]

Customer: Taps "Chicken Biryani"
Bot: "How many? Any special instructions?"

Customer: "2, extra raita"
Bot: "2x Chicken Biryani with extra raita = Rs.1,700
      Delivery or pickup?"

Customer: "Delivery"
Bot: "Send your location or type your address"

Customer: Shares GPS location
Bot: "Delivery to [address]. Total: Rs.1,850 (Rs.150 delivery fee)
      Pay: [JazzCash] [Cash on Delivery] [Card on Delivery]"

Customer: Taps "Cash on Delivery"
Bot: "Order placed! #240210-015. Estimated delivery: 35 min.
      I'll send you updates. Reply TRACK anytime to check status."
```

**Marketing Broadcasts**
- **Template messages** — pre-approved by WhatsApp (required for bulk sends)
- **Segmented** — send promos to specific customer segments (Gold tier, inactive 30+ days, etc.)
- **Scheduled** — set up campaigns to send at optimal times
- **Opt-in/out** — compliant with WhatsApp Business policy
- **Analytics** — delivery rate, read rate, response rate, orders generated

#### Technical Architecture
```
┌───────────────┐          ┌──────────────┐          ┌──────────────┐
│ WhatsApp      │◄────────►│ WhatsApp     │◄────────►│ POS Backend  │
│ Business API  │ Webhooks │ Gateway      │  Events  │ (FastAPI)    │
│ (Meta Cloud)  │          │ (our server) │          │              │
└───────────────┘          └──────────────┘          └──────────────┘
                                                            │
                                                     ┌──────┴──────┐
                                                     │ Claude API  │
                                                     │ (NLU for    │
                                                     │  free-text) │
                                                     └─────────────┘
```

---

### Module 8.2: CRM — Customer Relationship Management (Orbit-Style)

**Priority:** HIGH — Central nervous system for customer data
**Estimated effort:** 4-5 weeks
**Dependencies:** Phase 8 (customers), Module 6.1 (loyalty)

#### Overview
A custom-built CRM integrated directly into the POS — not Zoho, not Salesforce, but a bespoke system modeled after Orbit/Radius2 that's purpose-built for restaurant operations. Knows every customer, every visit, every preference, every complaint.

#### Database Tables
| Table | Purpose |
|-------|---------|
| `customers` | Core customer record (name, phone, email, DOB, photo, VIP flag) |
| `customer_addresses` | Multiple addresses per customer with GPS, zone, landmark |
| `customer_interactions` | Every touchpoint: call, order, complaint, feedback, WhatsApp msg |
| `customer_segments` | Dynamic segments (VIP, Dormant, New, High-Value, At-Risk) |
| `customer_preferences` | Dietary preferences, favorite items, allergies, special occasions |
| `customer_notes` | Free-text notes by staff ("Wife prefers window table", "Corporate account") |

#### Customer 360 View
```
┌────────────────────────────────────────────────────────────────────┐
│  CUSTOMER: Ahmed Khan                                    VIP ⭐   │
│  Phone: 0321-1234567  |  Email: ahmed@company.pk                  │
│  Member since: Jan 2025  |  Tier: GOLD (2,340 pts)               │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  LIFETIME                                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐             │
│  │ 87       │ │ Rs.74K   │ │ Rs.851   │ │ 4.2/5    │             │
│  │ Orders   │ │ Spent    │ │ Avg Order│ │ Rating   │             │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘             │
│                                                                    │
│  FAVORITE ITEMS              PREFERENCES                           │
│  1. Chicken Biryani (34x)    Diet: Non-veg                        │
│  2. Seekh Kebab (28x)        Spice: Extra spicy                   │
│  3. Mango Lassi (22x)        Allergies: None                      │
│  4. Raita (19x)              Seating: Window table                 │
│                                                                    │
│  ADDRESSES                                                         │
│  🏠 Home: 45-B, DHA Phase 5, Lahore (3.2 km — Zone A)            │
│  🏢 Office: 12th Floor, Arfa Tower, Lahore (7.1 km — Zone B)     │
│                                                                    │
│  RECENT ACTIVITY                                                   │
│  Feb 9  — Dine-in, Table 7, Rs.2,850 (Biryani x2 + Kebab)       │
│  Feb 5  — Delivery, Rs.1,200 (Biryani + Lassi), rated ⭐⭐⭐⭐     │
│  Jan 28 — Call center, Rs.3,400 (Family deal), "late by 15 min"   │
│  Jan 21 — Takeaway, Rs.850 (Biryani), used 200 loyalty points     │
│                                                                    │
│  NOTES                                                             │
│  - Corporate client, often orders for office lunch (10-15 pax)     │
│  - Wife's birthday: March 15 — send offer                         │
│  - Complained about cold food on Jan 28 — resolved with discount   │
│                                                                    │
│  [Place Order] [Send WhatsApp] [Add Note] [View Full History]     │
└────────────────────────────────────────────────────────────────────┘
```

#### Segmentation Engine
| Segment | Rule | Auto-Action |
|---------|------|-------------|
| **VIP** | >50 orders OR >Rs.100K lifetime | Priority delivery, manager notification on visit |
| **At Risk** | No order in 30+ days, previously active | WhatsApp: "We miss you! Here's 15% off" |
| **New** | First order in last 7 days | WhatsApp: welcome message + loyalty enrollment |
| **High Value** | Avg order >Rs.2,000 | Suggest premium menu items, invite to events |
| **Dormant** | No order in 90+ days | Re-activation campaign (deep discount) |
| **Corporate** | Tagged by staff | Invoice capability, bulk order discount |

#### Features
- **Phone number is the key** — no login needed, instant lookup by phone
- **Order-triggered enrichment** — every order auto-updates customer profile
- **Duplicate detection** — fuzzy match on phone + name to prevent duplicates
- **Merge customers** — combine duplicate profiles with full history preservation
- **Data export** — full customer list export for external marketing tools
- **GDPR-style compliance** — customer can request data deletion (soft-delete with audit trail)
- **Staff attribution** — which server/agent created the customer, who interacts most

---

### Module 8.3: Media Library & Promotional Hub

**Priority:** MEDIUM — Brand consistency across locations
**Estimated effort:** 2 weeks
**Dependencies:** Phase 3 (menu), Module 6.6 (digital menu boards)

#### Overview
Centralized asset management for all restaurant promotional materials — menu photos, promo banners, video content, seasonal catalogs. Shared across all tenants (locations) with access control.

#### Features
- **Asset types** — images (JPEG/PNG/WebP), videos (MP4), PDFs (catalogs), templates (Canva-style)
- **Folder structure** — organized by category: Menu Photos, Promos, Seasonal, Social Media, Print
- **Tagging** — tag assets with item names, categories, seasons, campaigns
- **Version control** — upload new version of a photo, old versions preserved
- **Distribution** — push assets to: digital menu boards, QR ordering page, online portal, WhatsApp broadcasts, CFD screens
- **Cross-tenant sharing** — HQ uploads new promo → all branches receive it automatically
- **Usage tracking** — which promos are displayed where, click-through rates
- **Template builder** — simple drag-and-drop editor for creating promo banners from templates
- **Auto-resize** — upload once, system generates sizes for: menu board (1920x1080), social (1080x1080), POS card (300x200), WhatsApp (800x800)
- **CDN-backed** — assets served from CloudFront for fast loading across all screens

---

### Module 8.4: Customer Feedback & Review Management

**Priority:** MEDIUM — Service quality monitoring
**Estimated effort:** 1.5 weeks
**Dependencies:** Module 8.1 (WhatsApp), Module 8.2 (CRM)

#### Overview
Automated post-meal feedback collection via WhatsApp/SMS. Responses feed into CRM. Bad reviews trigger instant manager alerts. Good reviews auto-prompt Google/Facebook review.

#### Flow
```
Order completed → 30 min delay → WhatsApp message:
"How was your meal at [Restaurant]? Rate 1-5 ⭐"
     │
     ├── ⭐⭐⭐⭐⭐ → "Thank you! Would you mind leaving us a Google review? [link]"
     ├── ⭐⭐⭐⭐ → "Thanks! Anything we could improve?" → log response
     ├── ⭐⭐⭐ → "Sorry it wasn't perfect. What happened?" → log + alert staff
     ├── ⭐⭐ → ALERT: Manager notified immediately → personal follow-up
     └── ⭐ → CRITICAL: Owner notified → call customer within 1 hour
```

#### Features
- **Auto-trigger** — no staff action needed, fires after every completed order
- **Channel-specific timing** — dine-in: 30 min after, delivery: 15 min after delivery
- **Rich feedback** — star rating + free-text comment + optional photo
- **Sentiment analysis** — Claude API categorizes feedback (food quality, speed, service, cleanliness)
- **Trends dashboard** — weekly satisfaction score, trending complaints, best-rated items
- **Resolution tracking** — complaint → assign to manager → resolution → follow-up → close
- **Google Review boost** — happy customers funneled to leave public reviews (huge for SEO)

---

## 9. Tier 5 — Supply Chain & Kitchen Intelligence

Modules that control costs, reduce waste, and optimize the back-of-house.

---

### Module 9.1: Kitchen Bill of Materials (BOM) & Stock Reconciliation

**Priority:** CRITICAL — The #1 cost control tool in any restaurant
**Estimated effort:** 4-5 weeks
**Dependencies:** Phase 3 (menu), Phase 5 (orders)

#### Overview
Every menu item has a recipe. Every recipe lists ingredients with exact quantities. When an order is placed, the system knows exactly what should have been consumed. Compare that against actual inventory counts → the variance is your waste, theft, or measurement error. This is where restaurants save 5-15% on food costs.

#### Database Tables
| Table | Purpose |
|-------|---------|
| `ingredients` | Raw materials (chicken, rice, oil, etc.) with unit, cost per unit, supplier |
| `recipes` | Template linking menu_item → list of ingredients with quantities |
| `recipe_items` | Individual ingredient line in a recipe (ingredient_id, qty, unit, waste_factor) |
| `recipe_versions` | Version history when recipes change (effective_date, created_by) |
| `inventory_stock` | Current stock level per ingredient per location |
| `inventory_transactions` | Every stock movement: purchase, consumption, waste, adjustment, transfer |
| `stock_counts` | Physical count records (count_date, counted_by, items JSON) |
| `purchase_orders` | PO sent to vendor (items, quantities, prices, status) |

#### Recipe Template System
```
┌────────────────────────────────────────────────────────────────┐
│  RECIPE: Chicken Biryani                                       │
│  Menu Price: Rs.850  |  Yield: 1 serving  |  Food Cost: Rs.285│
│  Food Cost %: 33.5%  |  Target: <35%  ✅                      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  INGREDIENTS                                                    │
│  ┌───────────────┬──────────┬────────┬──────────┬────────────┐ │
│  │ Ingredient    │ Quantity │ Unit   │ Cost     │ Waste %    │ │
│  ├───────────────┼──────────┼────────┼──────────┼────────────┤ │
│  │ Chicken       │ 250      │ grams  │ Rs.125   │ 5%         │ │
│  │ Basmati Rice  │ 200      │ grams  │ Rs.60    │ 2%         │ │
│  │ Cooking Oil   │ 50       │ ml     │ Rs.25    │ 0%         │ │
│  │ Onions        │ 100      │ grams  │ Rs.15    │ 10%        │ │
│  │ Yogurt        │ 50       │ grams  │ Rs.12    │ 0%         │ │
│  │ Spice Mix     │ 15       │ grams  │ Rs.18    │ 0%         │ │
│  │ Saffron       │ 0.5      │ grams  │ Rs.30    │ 0%         │ │
│  ├───────────────┼──────────┼────────┼──────────┼────────────┤ │
│  │ TOTAL         │          │        │ Rs.285   │            │ │
│  └───────────────┴──────────┴────────┴──────────┴────────────┘ │
│                                                                │
│  [Edit Recipe] [View History] [Duplicate] [Cost Simulator]     │
└────────────────────────────────────────────────────────────────┘
```

#### Theoretical vs Actual Reconciliation
```
STOCK RECONCILIATION — Week of Feb 3-9, 2026

┌───────────────┬────────────┬────────────┬────────────┬────────────┬──────────┐
│ Ingredient    │ Opening    │ Purchased  │ Theoretical│ Actual     │ Variance │
│               │ Stock      │ This Week  │ Usage      │ Count      │          │
├───────────────┼────────────┼────────────┼────────────┼────────────┼──────────┤
│ Chicken       │ 50 kg      │ 100 kg     │ 82 kg      │ 61 kg      │ -7 kg    │
│               │            │            │            │ (remaining)│ (8.5%)   │
│               │            │            │            │            │ ⚠️ HIGH  │
├───────────────┼────────────┼────────────┼────────────┼────────────┼──────────┤
│ Basmati Rice  │ 80 kg      │ 50 kg      │ 65 kg      │ 63 kg      │ -2 kg    │
│               │            │            │            │ (remaining)│ (3.0%)   │
│               │            │            │            │            │ ✅ OK    │
├───────────────┼────────────┼────────────┼────────────┼────────────┼──────────┤
│ Cooking Oil   │ 30 L       │ 20 L       │ 16 L       │ 31 L       │ -3 L     │
│               │            │            │            │ (remaining)│ (8.8%)   │
│               │            │            │            │            │ ⚠️ HIGH  │
└───────────────┴────────────┴────────────┴────────────┴────────────┴──────────┘

FORMULA: Variance = Opening + Purchased - Theoretical Usage - Actual Remaining
         Negative variance = more was used than recipes predicted (waste/theft/measurement)
         Positive variance = less was used than expected (under-portioning — also bad)

COST IMPACT: Total unexplained variance this week = Rs.12,400 (2.8% of food cost)
             Target: <2%  ⚠️ ABOVE TARGET

ALERT: Chicken variance has been >7% for 3 consecutive weeks → investigation recommended
```

#### Features
- **Recipe builder** — drag ingredients, set quantities, auto-calculate cost
- **Bulk recipe import** — upload CSV/Excel with all recipes at once
- **Sub-recipes** — "Biryani Masala Mix" as a sub-recipe used in multiple items
- **Portion scaling** — define recipe for 1 serving, system scales for any quantity
- **Waste factor** — built into each ingredient (chicken has 5% bone/trim waste)
- **Cost simulator** — "if chicken price goes from Rs.500/kg to Rs.600/kg, how does it affect my menu margins?"
- **Auto-deduct** — every order automatically deducts theoretical ingredients from stock
- **Low stock alerts** — "Chicken stock will run out by tomorrow at current consumption rate"
- **Stock count interface** — staff does physical count on tablet, system calculates variance
- **Count scheduling** — auto-remind for weekly/monthly counts by category

---

### Module 9.2: Vendor Portal & Procurement

**Priority:** HIGH — Financial control over supply chain
**Estimated effort:** 3-4 weeks
**Dependencies:** Module 9.1 (BOM), Module 5.1 (QuickBooks)

#### Overview
A dedicated portal for the restaurant's vendors (suppliers). Vendors log in, see their ledger, view purchase orders, submit invoices, track payments. The restaurant manages all procurement from one place. Data flows to QuickBooks for accounting.

#### Vendor Portal (Vendor's View)
```
┌────────────────────────────────────────────────────────────────┐
│  VENDOR PORTAL — Premium Meats Co.                             │
│  Account #: V-0034  |  Since: March 2024                      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ACCOUNT SUMMARY                                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │ Rs.245,000   │ │ Rs.180,000   │ │ Rs.65,000    │           │
│  │ Total Billed │ │ Paid         │ │ Outstanding  │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
│                                                                │
│  RECENT TRANSACTIONS                                            │
│  Feb 8  — PO #287: 50kg Chicken Breast @ Rs.500/kg = Rs.25,000│
│  Feb 6  — Payment received: Rs.45,000 (Cheque #1234)          │
│  Feb 3  — PO #281: 30kg Mutton @ Rs.1,200/kg = Rs.36,000     │
│  Feb 1  — Invoice #INV-0089 submitted: Rs.61,000              │
│                                                                │
│  [View Full Ledger]  [Download Statement]  [Submit Invoice]    │
└────────────────────────────────────────────────────────────────┘
```

#### Restaurant's Procurement Dashboard
```
┌────────────────────────────────────────────────────────────────────┐
│  PROCUREMENT DASHBOARD                                             │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  THIS MONTH                                                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐             │
│  │ Rs.890K  │ │ Rs.650K  │ │ Rs.240K  │ │ 12       │             │
│  │ Ordered  │ │ Paid     │ │ Payable  │ │ Active   │             │
│  │          │ │          │ │          │ │ Vendors  │             │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘             │
│                                                                    │
│  PENDING APPROVALS                                                 │
│  ⏳ PO #290 — Fresh Produce Co. — Rs.28,000 — [Approve] [Reject] │
│  ⏳ PO #289 — Spice World — Rs.15,000 — [Approve] [Reject]       │
│                                                                    │
│  VENDOR LEADERBOARD                                                │
│  1. Premium Meats — Rs.310K/month — 98% on-time — ⭐4.8           │
│  2. Fresh Produce — Rs.180K/month — 92% on-time — ⭐4.5           │
│  3. Dairy Direct — Rs.95K/month — 85% on-time — ⭐4.0             │
│                                                                    │
│  PRICE ALERTS                                                      │
│  ⚠️ Chicken: Rs.520/kg (up 4% from last month)                    │
│  ⚠️ Cooking Oil: Rs.480/L (up 8% — consider alternate supplier)   │
│  ✅ Rice: Rs.280/kg (stable)                                       │
│                                                                    │
│  [Create PO] [View All Vendors] [Payment Schedule] [QB Sync Log]  │
└────────────────────────────────────────────────────────────────────┘
```

#### Database Tables
| Table | Purpose |
|-------|---------|
| `vendors` | Vendor profile (name, contact, bank details, payment terms, rating) |
| `vendor_contacts` | Multiple contacts per vendor (sales rep, accounts, owner) |
| `purchase_orders` | PO header (vendor, date, status: draft/sent/received/invoiced/paid) |
| `purchase_order_items` | Line items (ingredient, qty, unit price, received qty) |
| `vendor_invoices` | Invoices submitted by vendor against POs |
| `vendor_payments` | Payment records (amount, method, reference, date) |
| `vendor_ledger` | Running balance ledger (debit/credit/balance) |
| `price_history` | Historical prices per ingredient per vendor (trend analysis) |

#### Features
- **Purchase order workflow** — Draft → Approved → Sent to Vendor → Goods Received → Invoiced → Paid
- **3-way matching** — PO quantity vs Received quantity vs Invoice amount (discrepancies flagged)
- **Auto-PO generation** — when stock falls below reorder point, auto-draft PO to preferred vendor
- **Vendor scoring** — on-time delivery %, quality rejection %, price competitiveness
- **Price comparison** — same ingredient from multiple vendors, side-by-side pricing
- **Payment scheduling** — "pay this vendor every 15th" or "pay when outstanding >Rs.100K"
- **QB sync** — every PO and payment auto-syncs to QuickBooks (Vendor Bills + Bill Payments)
- **Vendor self-service** — vendors log in to check their balance, download statements, submit invoices

---

## 10. Tier 6 — Enterprise & Scale

Modules for multi-location operations, franchise management, and executive oversight.

---

### Module 10.1: Franchise Management

**Priority:** HIGH (when expanding) — Build when second location opens
**Estimated effort:** 4-5 weeks
**Dependencies:** Multi-tenant architecture (already built), all Tier 1-5 modules

#### Overview
Central HQ controls the brand. Individual locations operate independently within guardrails. HQ sets the menu, pricing, and standards. Branches execute.

#### HQ Dashboard
```
┌────────────────────────────────────────────────────────────────────────┐
│  FRANCHISE COMMAND CENTER                        [All Locations ▼]     │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  TODAY ACROSS ALL LOCATIONS                                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ Rs.1.2M  │ │ 487      │ │ 12.4 min │ │ 4.3/5    │ │ 34%      │   │
│  │ Revenue  │ │ Orders   │ │ Avg KDS  │ │ Cust Sat │ │ Food Cost│   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│                                                                        │
│  LOCATION PERFORMANCE                                                  │
│  ┌──────────────┬──────────┬────────┬──────────┬──────────┬─────────┐ │
│  │ Location     │ Revenue  │ Orders │ Avg Time │ Rating   │ Status  │ │
│  ├──────────────┼──────────┼────────┼──────────┼──────────┼─────────┤ │
│  │ DHA Lahore   │ Rs.485K  │ 198    │ 11.2 min │ 4.5/5   │ 🟢 Live │ │
│  │ Gulberg      │ Rs.392K  │ 156    │ 13.8 min │ 4.1/5   │ 🟢 Live │ │
│  │ Johar Town   │ Rs.341K  │ 133    │ 14.5 min │ 4.3/5   │ 🟢 Live │ │
│  └──────────────┴──────────┴────────┴──────────┴──────────┴─────────┘ │
│                                                                        │
│  ⚠️ ALERTS                                                             │
│  Gulberg: Kitchen avg time exceeding 13 min target (13.8 min)         │
│  Johar Town: Chicken stock projected to run out by 7 PM               │
│  DHA: 3 negative reviews today (avg is 1) — manager notified          │
│                                                                        │
│  ROYALTY SUMMARY (This Month)                                          │
│  DHA: Rs.48,500 (5% of Rs.970K)                                       │
│  Gulberg: Rs.35,200 (5% of Rs.704K)                                   │
│  Johar Town: Rs.29,100 (5% of Rs.582K)                                │
│  TOTAL ROYALTY: Rs.112,800                                             │
│                                                                        │
│  [Menu Management] [Pricing Control] [Staff Directory] [Compliance]    │
└────────────────────────────────────────────────────────────────────────┘
```

#### Features
- **Centralized menu** — HQ defines menu; branches can't add/remove items (optional local specials with approval)
- **Centralized pricing** — HQ sets prices; branches can request adjustments (approval workflow)
- **Brand guardrails** — receipt templates, promo materials, display themes locked by HQ
- **Per-location config** — each branch has own floors, tables, staff, kitchen stations, operating hours
- **Royalty engine** — configurable royalty % (flat or tiered), auto-calculated, visible to both HQ and branch
- **Cross-location transfers** — transfer stock between locations, tracked in BOM
- **Benchmarking** — compare locations on every metric (revenue, speed, satisfaction, food cost)
- **HQ-pushed promos** — HQ creates promo → pushed to all locations simultaneously
- **Compliance audits** — HQ defines checklists (food safety, cleanliness), branches self-report, HQ verifies

---

### Module 10.2: Mobile Owner App

**Priority:** HIGH — Owners live on their phones
**Estimated effort:** 3-4 weeks
**Dependencies:** Phase 9 (reports), Module 7.1 (AI copilot)

#### Overview
React Native (or PWA) app for the restaurant owner/operator. Real-time visibility from anywhere. Approve voids, check revenue, get AI insights — all from their phone.

#### Screens
| Screen | Features |
|--------|----------|
| **Home** | Today's KPIs (revenue, orders, active, satisfaction), trend sparklines |
| **Live View** | Active orders across all locations, floor plan, kitchen status |
| **Revenue** | Daily/weekly/monthly charts, channel breakdown, location comparison |
| **Alerts** | Push notifications: voids, complaints, stock alerts, anomalies |
| **AI Chat** | Talk to the AI copilot (text or voice) — "How's Gulberg doing today?" |
| **Approvals** | Pending void approvals, PO approvals, discount overrides |
| **Staff** | Who's clocked in, overtime alerts, performance snapshots |
| **Reports** | Downloadable Z-reports, weekly summaries, tax reports |

#### Push Notifications (Configurable)
| Alert | Default | Customizable |
|-------|---------|-------------|
| Void over Rs.2,000 | ON | Threshold adjustable |
| Negative review (1-2 stars) | ON | Can turn off |
| Daily revenue summary (11 PM) | ON | Time adjustable |
| Stock running low | ON | Per-ingredient toggle |
| Anomaly detected | ON | Sensitivity adjustable |
| Hourly revenue update | OFF | Can turn on |

---

### Module 10.3: Employee Scheduling & Attendance

**Priority:** MEDIUM — Operational efficiency
**Estimated effort:** 2-3 weeks
**Dependencies:** Phase 2 (users/roles)

#### Overview
Shift planning, clock-in/clock-out via POS (PIN or biometric), overtime tracking, attendance reports. Feeds payroll data to QuickBooks.

#### Features
- **Shift builder** — drag-and-drop weekly schedule by role (cashier, cook, server, rider)
- **Availability** — staff submits availability, manager builds schedule around it
- **Clock in/out** — PIN entry at POS terminal, timestamp logged
- **Break tracking** — clock out for break, clock back in, break duration tracked
- **Late alerts** — staff more than 10 min late → manager notified
- **Overtime rules** — configurable thresholds, auto-calculate OT hours and cost
- **Swap requests** — staff can request shift swaps, manager approves
- **Payroll export** — hours + OT → CSV for QuickBooks payroll or manual processing
- **Labor cost %** — real-time labor cost as % of revenue (target: <30%)
- **Schedule templates** — save common patterns ("Eid schedule", "PSL match day")

---

## 11. Integration Architecture Map

Every external system and how it connects:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          POS CORE SYSTEM                                │
│                    (FastAPI + PostgreSQL + Redis)                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  FINANCIAL                  ORDERING                COMMUNICATION       │
│  ─────────                  ────────                ─────────────       │
│  ┌──────────┐              ┌──────────┐            ┌──────────────┐    │
│  │QuickBooks│ REST/SOAP    │Foodpanda │ Webhooks   │WhatsApp Bus. │    │
│  │Online    │◄────────────►│API       │◄──────────►│API (Meta)    │    │
│  │/Desktop  │              └──────────┘            └──────────────┘    │
│  └──────────┘              ┌──────────┐            ┌──────────────┐    │
│  ┌──────────┐              │Online    │ REST       │ElevenLabs    │    │
│  │FBR API   │◄────────────►│Ordering  │◄──────────►│Voice API     │    │
│  │(Tax)     │              │Portal    │            └──────────────┘    │
│  └──────────┘              └──────────┘            ┌──────────────┐    │
│  ┌──────────┐              ┌──────────┐            │SMS Gateway   │    │
│  │PRA API   │◄────────────►│QR Order  │◄──────────►│(Twilio/local)│    │
│  │(Tax)     │              │Pages     │            └──────────────┘    │
│  └──────────┘              └──────────┘                                 │
│                                                                         │
│  INTELLIGENCE               LOGISTICS              VENDOR               │
│  ────────────               ─────────              ──────               │
│  ┌──────────┐              ┌──────────┐            ┌──────────────┐    │
│  │Claude API│ Function     │Google    │ Geocoding  │Vendor Portal │    │
│  │(Anthropic│ Calling      │Maps API  │ + Routing  │(Self-Service)│    │
│  │)         │◄────────────►│          │◄──────────►│              │    │
│  └──────────┘              └──────────┘            └──────────────┘    │
│  ┌──────────┐              ┌──────────┐            ┌──────────────┐    │
│  │Weather   │ Demand       │Rider GPS │ WebSocket  │Payment       │    │
│  │API       │ Forecasting  │Tracking  │◄──────────►│Gateway       │    │
│  └──────────┘              └──────────┘            └──────────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 12. Technology Stack Evolution

How the stack grows as modules are added:

| Layer | Prototype (Now) | Post-Prototype | Enterprise |
|-------|----------------|----------------|------------|
| **Frontend** | React + Vite + Tailwind + shadcn/ui | + React Native (Mobile App) | + Micro-frontends per module |
| **Backend** | FastAPI (single service) | + Background workers (Celery/ARQ) | + Event-driven microservices |
| **Database** | PostgreSQL 16 | + Read replicas | + Sharding by tenant |
| **Cache** | Redis 7 | + Redis Streams (event bus) | + ElastiCache cluster |
| **Search** | pg_trgm (fuzzy) | + Full-text search | + Elasticsearch (if needed) |
| **File Storage** | Local / Docker volume | S3 (media library, receipts) | + CloudFront CDN |
| **Job Queue** | None (sync) | Redis Queue (ARQ) | + Dead letter queue, retry policies |
| **AI/ML** | None | Claude API (copilot, NLU) | + Fine-tuned models, embeddings |
| **Voice** | None | ElevenLabs API | + On-premise Whisper for transcription |
| **Messaging** | None | WhatsApp Business API | + Multi-channel (SMS, Email, Push) |
| **Monitoring** | Docker logs | Sentry + Prometheus + Grafana | + PagerDuty alerts, SLA tracking |
| **CI/CD** | GitHub Actions | + Staging auto-deploy | + Blue-green deployments, canary |
| **Hosting** | Docker Compose (single server) | AWS ECS Fargate | + Multi-region, auto-scaling |

---

## 13. Database Schema Projection

Current: ~20 tables. Projected at full build: **65-75 tables**.

| Domain | Current Tables | Added Tables | Total |
|--------|---------------|-------------|-------|
| **Tenant** | 2 | 0 | 2 |
| **Auth** | 5 | 0 | 5 |
| **Floor** | 2 | 1 (reservations) | 3 |
| **Menu** | 5 | 0 | 5 |
| **Orders** | 4 | 1 (delivery assignments) | 5 |
| **Kitchen** | 0 | 5 (stations, routing, tickets) | 5 |
| **Payments** | 0 | 3 (methods, payments, drawer sessions) | 3 |
| **Tax** | 0 | 3 (groups, rates, invoices) | 3 |
| **Customers/CRM** | 0 | 6 (customers, addresses, interactions, segments, preferences, notes) | 6 |
| **Loyalty** | 0 | 4 (tiers, accounts, transactions, rewards) | 4 |
| **Inventory/BOM** | 0 | 8 (ingredients, recipes, stock, counts, etc.) | 8 |
| **Vendor** | 0 | 8 (vendors, contacts, POs, invoices, payments, ledger, prices) | 8 |
| **Delivery** | 0 | 4 (riders, locations, deliveries, zones) | 4 |
| **Promotions** | 0 | 3 (rules, usage, budgets) | 3 |
| **Media** | 0 | 3 (assets, folders, distributions) | 3 |
| **Feedback** | 0 | 2 (reviews, resolutions) | 2 |
| **Staff** | 0 | 3 (shifts, clock records, schedules) | 3 |
| **Integration** | 0 | 3 (sync log, QB mappings, webhook log) | 3 |
| **TOTAL** | **~20** | **~55** | **~75** |

---

## 14. Deployment & Infrastructure Roadmap

### Phase A: Prototype (Current)
```
Single Docker Compose on developer machine
├── nginx (reverse proxy) → port 8090
├── frontend (Vite dev server)
├── backend (FastAPI + Uvicorn)
├── postgres (single instance) → port 5450
└── redis (single instance) → port 6390
```

### Phase B: Staging (Post-Approval)
```
AWS ECS Fargate — Bahrain Region (me-south-1)
├── ALB (SSL termination, WebSocket support)
├── ECS Service: frontend (Nginx + static React build)
├── ECS Service: backend (FastAPI + Gunicorn, 2 tasks)
├── ECS Service: worker (background jobs, 1 task)
├── RDS PostgreSQL 16 (db.t3.medium, single-AZ)
├── ElastiCache Redis 7 (cache.t3.micro)
├── S3 (media library, receipts, exports)
├── CloudFront (static assets + media CDN)
├── SSM Parameter Store (secrets)
└── CloudWatch (logs + basic monitoring)

Estimated cost: ~$150-200/month
```

### Phase C: Production (Go-Live)
```
AWS ECS Fargate — Multi-AZ
├── ALB (SSL, WAF, rate limiting)
├── ECS Service: frontend (3 tasks, auto-scaling)
├── ECS Service: backend (3 tasks, auto-scaling 2-10)
├── ECS Service: worker (2 tasks)
├── ECS Service: voice-agent (1 task, GPU if needed)
├── RDS PostgreSQL 16 (db.r6g.large, Multi-AZ, read replica)
├── ElastiCache Redis 7 (cache.r6g.large, cluster mode)
├── S3 + CloudFront (media CDN)
├── SES (transactional email)
├── SNS (push notifications)
├── Sentry (error tracking)
├── Prometheus + Grafana (metrics)
└── Automated backups (RDS snapshots, S3 versioning)

Estimated cost: ~$400-600/month (single location)
Per additional location: +~$50-100/month (shared infra, incremental DB load)
```

### Phase D: Enterprise (Multi-Location)
```
Add:
├── RDS read replicas per region (if expanding beyond Pakistan)
├── Global Accelerator (for international access)
├── DynamoDB (for high-write time-series: GPS pings, analytics events)
├── SageMaker (demand forecasting models — if moving beyond Claude API)
├── Multi-account AWS Organization (prod/staging/dev separation)
└── Terraform / CDK (Infrastructure as Code)
```

---

## 15. Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| QuickBooks Desktop API is deprecated by Intuit | HIGH | MEDIUM | Build QB Online as primary, Desktop as secondary. Migration path documented. |
| Foodpanda changes API without notice | MEDIUM | HIGH | Version-pin API, webhook signature validation, alert on failure, manual fallback |
| WhatsApp Business API policy rejection | MEDIUM | LOW | Pre-approved message templates, strict opt-in, compliance review |
| ElevenLabs voice quality insufficient for Urdu | MEDIUM | MEDIUM | Fallback to human agent, test extensively before go-live, consider alternatives (Azure Speech) |
| FBR/PRA API downtime during peak hours | HIGH | MEDIUM | Queue fiscal invoices, submit when API recovers, receipt prints with "pending" status |
| Data breach / security incident | CRITICAL | LOW | Encryption at rest + transit, WAF, regular pen testing, no card data stored, SOC 2 roadmap |
| Key person dependency (single developer) | HIGH | MEDIUM | Comprehensive documentation, clean code standards, CI/CD so anyone can deploy |
| Client's internet goes down at restaurant | HIGH | MEDIUM | Offline mode for core POS operations, sync when back online (Phase 10) |
| Scope creep — client keeps adding features | MEDIUM | HIGH | This masterplan as the contract scope. Change requests priced separately. |
| Vendor portal adoption — vendors refuse to use it | LOW | MEDIUM | Keep phone/WhatsApp ordering as fallback, incentivize portal use (faster payments) |

---

## 16. Rollout Strategy

### Recommended Build Sequence (Post-Prototype Approval)

**Wave 1: Core Completion** (Weeks 1-8)
> Finish the prototype into a shippable product

| Week | Module | Why First |
|------|--------|-----------|
| 1-2 | Phase 6: KDS | Kitchen can't operate without it |
| 3-4 | Phase 7: Payments | Can't go live without payments |
| 5-6 | Phase 8: Call Center + Customers | Third core channel |
| 6-7 | Phase 9: Reports + Admin | Owner needs reports from day 1 |
| 7-8 | Phase 10: Polish + Stubs | Production hardening |

**Wave 2: Revenue & Financial** (Weeks 9-16)
> Connect the money flow, go live with first location

| Week | Module | Why Now |
|------|--------|--------|
| 9-11 | QuickBooks Integration | Accountant needs this before go-live |
| 11-12 | FBR/PRA Tax Integration | Legal compliance required |
| 13-15 | Foodpanda Integration | Immediate revenue channel |
| 15-16 | CRM (Customer 360) | Foundation for everything in Wave 3 |

**Wave 3: Customer Experience** (Weeks 17-24)
> Drive more orders, build customer relationships

| Week | Module | Why Now |
|------|--------|--------|
| 17-18 | WhatsApp API + Bot | Highest-impact communication channel in Pakistan |
| 19-20 | Loyalty & Rewards | Drive repeat visits |
| 20-21 | QR Code Table Ordering | Modernize dine-in experience |
| 22-24 | Online Ordering Portal | Eliminate Foodpanda commission on direct orders |

**Wave 4: Intelligence** (Weeks 25-30)
> Make the restaurant smarter

| Week | Module | Why Now |
|------|--------|--------|
| 25-27 | AI Copilot (Claude API) | Owner starts getting AI-powered insights |
| 27-28 | Demand Forecasting | Reduce waste, optimize prep |
| 29-30 | Dynamic Pricing + Promotions | Revenue optimization |

**Wave 5: Supply Chain** (Weeks 31-38)
> Control costs, manage vendors

| Week | Module | Why Now |
|------|--------|--------|
| 31-35 | BOM + Stock Reconciliation | The #1 cost saver — needs enough order history to be meaningful |
| 35-38 | Vendor Portal + Procurement | Full supply chain visibility |

**Wave 6: Scale & Experience** (Weeks 39-48)
> Expand, delight, dominate

| Week | Module | Why Now |
|------|--------|--------|
| 39-41 | Delivery Fleet + Rider GPS | Launch own delivery (reduce Foodpanda dependency) |
| 41-42 | ElevenLabs Voice Agent | Automate call center |
| 43-44 | Mobile Owner App | Owner convenience |
| 44-45 | Table Reservations + CFD + Digital Menu Boards | Premium experience |
| 45-46 | Media Library + Feedback System | Brand consistency + quality monitoring |
| 46-47 | Employee Scheduling | Operational efficiency |
| 47-48 | Franchise Management | Ready for location #2 |

---

### Total Timeline: ~48 weeks (12 months) from prototype approval to full platform

### Total Projected Tables: ~75
### Total Projected API Endpoints: ~200+
### Total Projected Frontend Pages: ~40+

---

*This document is a living roadmap. Priorities may shift based on client feedback, market conditions, and operational learnings. Each wave should be re-evaluated before starting based on what was learned in the previous wave.*

*The prototype (Phases 1-5) proves we can build. This masterplan proves we can think.*

---

**Prepared by:** Malik Amin
**Date:** February 10, 2026
**Version:** 1.0
