# POS System — Enhancement Backlog

**Purpose:** Consolidated log of all feature ideas, enhancements, and improvements identified during UAT sessions and development. Items here are earmarked for subsequent phases — not blockers for current UAT/prototype.

**Reference:** See `MASTERPLAN.md` for the full post-prototype roadmap (Tiers 1-6, Waves 1-6).

---

## ENH-001: Edit modifiers on existing cart items
- **Logged:** 2026-02-25 (UAT Session 1, MODULE 3: Dine-In, UAT-017)
- **Source:** UAT observation — once an item with modifiers is added to cart, you can't change the modifiers without removing and re-adding
- **Description:** Click a cart line item to re-open the ModifierModal with current selections pre-filled. User can change modifiers and update the cart item in-place.
- **Affected:** `frontend/src/components/pos/CartPanel.tsx`, `frontend/src/components/pos/ModifierModal.tsx`, `frontend/src/stores/cartStore.ts`
- **Priority:** Medium
- **Phase:** Post-UAT polish

---

## ENH-002: Category-to-station kitchen routing
- **Logged:** 2026-02-26 (UAT Session 2, MODULE 6: KDS, UAT-038)
- **Source:** UAT observation — all items currently route to Main Kitchen station regardless of category. Station filter shows Grill and Beverage stations empty.
- **Description:** Wire up `kitchen_station_categories` mapping so items route to the correct station based on their menu category. E.g., beverages go to Beverage Station, grilled items go to Grill Station. The DB tables and API already exist (`kitchen_station_categories`, `kitchen_station_menu_items`), just not populated or used in auto-ticket creation.
- **Affected:** `backend/app/services/order_service.py` (`_auto_create_kitchen_ticket`), seed data, admin station config UI
- **Priority:** High
- **Phase:** Post-UAT, pre-production go-live

---

## ENH-003: Time-window filter for KDS Served column
- **Logged:** 2026-02-26 (UAT Session 2, MODULE 6: KDS, UAT-036)
- **Source:** UAT observation — Served column accumulates all served tickets indefinitely, will become unusable over time
- **Description:** Add a time-window filter (e.g., "Last 1 hour", "Last 2 hours", "Today") for the Served column, or auto-hide served tickets older than a configurable threshold. New/Preparing/Ready columns remain unfiltered.
- **Affected:** `frontend/src/pages/kitchen/KitchenPage.tsx`, `frontend/src/services/kitchenApi.ts`
- **Priority:** Medium
- **Phase:** Post-UAT polish

---

## ENH-004: McKinsey-grade UI/UX polish pass
- **Logged:** 2026-02-26 (UAT Session 2, general observation)
- **Source:** UAT observation — functional but needs premium visual polish for client demo
- **Description:** Comprehensive UX pass covering: lean search results layout, customer profile modal redesign, premium typography (font hierarchy), consistent spacing/padding, subtle animations, loading skeletons instead of spinners, empty state illustrations.
- **Affected:** Global styles, multiple page components
- **Priority:** Low (post-UAT)
- **Phase:** Pre-client demo polish

---

## ENH-005: Order lifecycle timestamp trail & department efficiency metrics
- **Logged:** 2026-02-28 (UAT Session 3, MODULE 7: Order Management, UAT-045)
- **Source:** UAT observation — void action works but order card only shows elapsed time since creation. Need full lifecycle visibility per order.
- **Description:** Surface the `order_status_log` data (already being captured in DB) as a visible timeline on order cards and detail views. Each status transition should show:
  - **Who** performed the action (user name + role)
  - **When** (exact timestamp)
  - **What** changed (from_status -> to_status)
  - **Channel** context (dine_in / takeaway / call_center)

  Example display per order:
  ```
  Order Taken:      Admin User    2:15 PM   (dine_in, Table 7)
  Sent to Kitchen:  Admin User    2:15 PM
  Started Preparing: Kitchen User  2:18 PM   (3 min wait)
  Marked Ready:     Kitchen User  2:29 PM   (11 min prep)
  Served:           Cashier User  2:31 PM   (2 min pickup)
  Completed:        Admin User    2:55 PM   (24 min total)
  ```

  **Dashboard integration (subsequent phase):**
  - Avg time per workflow stage (order-to-kitchen, kitchen-prep, ready-to-served, etc.)
  - Department efficiency metrics (kitchen avg prep time, front-of-house avg serve time)
  - Bottleneck identification (which stage takes longest on average)
  - Staff performance (avg times per user)
  - Peak hour analysis (do times get worse during rush?)

  **Data backbone:** `order_status_log` table already captures `order_id`, `from_status`, `to_status`, `changed_by`, `created_at` for every transition. No schema changes needed — this is purely a frontend/reporting enhancement.
- **Affected:**
  - `frontend/src/pages/orders/OrdersPage.tsx` (timeline view on cards)
  - `backend/app/api/v1/orders.py` (include status_log in order detail response)
  - `frontend/src/pages/admin/AdminDashboard.tsx` (efficiency widgets)
  - `frontend/src/pages/admin/ReportsPage.tsx` (department efficiency report)
- **Priority:** High
- **Phase:** Post-UAT enhancement, dashboard metrics in Wave 2

---

## ENH-006: Back button on KDS (Kitchen Display) page
- **Logged:** 2026-03-07 (Test 9 session)
- **Source:** UAT observation — KDS is fullscreen with no navigation back to POS/dashboard; user must use browser back button
- **Description:** Add a back/home button to the KDS header bar so kitchen staff or managers can navigate back to the dashboard without relying on the browser back button.
- **Affected:** `frontend/src/pages/kitchen/KitchenPage.tsx`
- **Priority:** Medium
- **Phase:** Post-UAT polish

---

## ENH-007: Kitchen View shortcut in Admin panel
- **Logged:** 2026-03-07 (Test 9 session)
- **Source:** UAT observation — no way to reach KDS from the Admin panel; must navigate to dashboard first then open KDS
- **Description:** Add a "Kitchen Display" button/link in the Admin sidebar or dashboard so managers can quickly open the KDS view without leaving the admin context.
- **Affected:** `frontend/src/components/layout/AdminLayout.tsx`
- **Priority:** Medium
- **Phase:** Post-UAT polish

---

## ENH-008: Lean PDF report format (McKinsey-style)
- **Logged:** 2026-03-07 (Reports testing session)
- **Source:** User request — reports should have a clean, professional PDF export format similar to the Radius2 Analytics project (`C:\Users\Malik\desktop\radius2-analytics`)
- **Description:** Add PDF export option to all report sections (sales summary, waiter performance, void report, etc.) with a lean, structured layout: branded header, clean typography, tables with alternating rows, summary KPI cards, and print-optimized CSS. Reference the Radius2 Analytics report templates for style and structure.
- **Affected:** `frontend/src/pages/admin/ReportsPage.tsx`, new print/PDF utility
- **Priority:** Medium
- **Phase:** Post-UAT polish

---

*New items should be added below with sequential ENH-NNN numbering, date, source, and phase assignment.*
