# End-to-End UAT Checklist -- POS System

**Application Under Test:** Pakistan-based Restaurant POS System
**Deployment URL:** https://pos-demo.duckdns.org
**Date Prepared:** 2026-02-24

## Test Credentials

| User | Email | Password | PIN | Role |
|------|-------|----------|-----|------|
| Admin User | admin@demo.com | admin123 | 1234 | admin |
| Cashier User | cashier@demo.com | cashier123 | 5678 | cashier |
| Kitchen User | kitchen@demo.com | kitchen123 | 9012 | kitchen |

## Route Reference

| Route | Description |
|-------|-------------|
| `/login` | Login page (PIN or password) |
| `/` | Channel selector dashboard (requires auth) |
| `/dine-in` | Dine-In POS with floor plan |
| `/takeaway` | Takeaway POS |
| `/call-center` | Call Center POS with phone lookup |
| `/orders` | Order management list |
| `/payment/:orderId` | Payment processing page |
| `/floor-editor` | Floor plan editor (admin) |
| `/kitchen` | KDS fullscreen Kanban (standalone) |
| `/admin` | Admin dashboard |
| `/admin/menu` | Menu management |
| `/admin/staff` | Staff management |
| `/admin/settings` | Restaurant settings |
| `/admin/reports` | Sales reports |
| `/admin/z-report` | Z-Report daily settlement |

---

## MODULE 1: Authentication and Login

| ID | Test Case | Steps | Expected Result | Pass/Fail |
|----|-----------|-------|-----------------|-----------|
| UAT-001 | PIN login with valid admin PIN | 1. Navigate to `/login`. 2. Enter `1234` on PIN pad. 3. Submit. | Redirected to `/`. Header shows "Admin User". | |
| UAT-002 | PIN login with valid cashier PIN | 1. Enter `5678` on PIN pad. 2. Submit. | Redirected to `/`. Header shows "Cashier User". | |
| UAT-003 | PIN login with invalid PIN | 1. Enter `0000`. 2. Submit. | Error message. User stays on login page. | |
| UAT-004 | Password login valid | 1. Switch to password mode. 2. Enter `admin@demo.com` / `admin123`. 3. Sign In. | Redirected to `/`. | |
| UAT-005 | Password login wrong password | 1. Enter `admin@demo.com` / `wrong123`. | Error message. Stays on login page. | |
| UAT-006 | Mode toggle PIN <-> Password | 1. Toggle between PIN and password modes via links. | Both modes render correctly. | |
| UAT-007 | Authenticated redirect on login page | 1. Log in. 2. Navigate to `/login`. | Redirected to `/`. | |
| UAT-008 | Logout clears session | 1. Click logout icon in header. | Redirected to `/login`. Protected routes blocked. | |
| UAT-009 | Unauthenticated route protection | 1. Clear localStorage. 2. Navigate to `/dine-in`. | Redirected to `/login`. | |

---

## MODULE 2: Dashboard (Channel Selector)

| ID | Test Case | Steps | Expected Result | Pass/Fail |
|----|-----------|-------|-----------------|-----------|
| UAT-010 | Three channel cards displayed | 1. Log in. 2. View `/`. | Three cards: Dine-In (blue), Takeaway (green), Call Center (accent). | |
| UAT-011 | Dine-In card navigates | Click Dine-In card. | Navigated to `/dine-in`. | |
| UAT-012 | Takeaway card navigates | Click Takeaway card. | Navigated to `/takeaway`. | |
| UAT-013 | Call Center card navigates | Click Call Center card. | Navigated to `/call-center`. | |

---

## MODULE 3: Dine-In Order Flow

| ID | Test Case | Steps | Expected Result | Pass/Fail |
|----|-----------|-------|-----------------|-----------|
| UAT-014 | Floor plan loads with tables | Navigate to `/dine-in`. | Floor tabs visible. Tables rendered with color-coded status. | |
| UAT-015 | Table selection enables menu | Click an available table. | MenuGrid appears with category tabs and item cards. | |
| UAT-016 | Add item to cart | Click a menu item. | Item appears in CartPanel with name, qty, price. Totals update. | |
| UAT-017 | Modifier selection | Click item with modifiers. | ModifierModal opens. Select modifier. Item added with modifier badge. | |
| UAT-018 | Quantity adjustment | Use +/- buttons on cart line. | Quantity and line total update. "-" at qty 1 removes item. | |
| UAT-019 | Remove item from cart | Click X on cart line. | Item removed. Empty cart shows placeholder. | |
| UAT-020 | Send to Kitchen (dine-in) | Add items. Click "Send to Kitchen". | Order created. Cart clears. Table turns occupied (red). | |
| UAT-021 | Multi-table cart switching | Select Table A, add items. Switch to Table B, add items. Switch back to A. | Each table's cart preserved independently. | |
| UAT-022 | Clear Order confirmation | Add items. Click "Clear Order". | Confirmation dialog. "Clear All" empties cart. | |

---

## MODULE 4: Takeaway Order Flow

| ID | Test Case | Steps | Expected Result | Pass/Fail |
|----|-----------|-------|-----------------|-----------|
| UAT-023 | Takeaway page layout | Navigate to `/takeaway`. | MenuGrid + CartPanel. No floor plan. OrderTicker at bottom. | |
| UAT-024 | Submit takeaway order | Add items. Click "Send to Kitchen". | Order created as "takeaway". Cart clears. | |
| UAT-025 | PKR currency verification | Add item at Rs. 650. Check tax/total. | Subtotal Rs. 650, Tax Rs. 104 (16%), Total Rs. 754. | |

---

## MODULE 5: Call Center Order Flow

| ID | Test Case | Steps | Expected Result | Pass/Fail |
|----|-----------|-------|-----------------|-----------|
| UAT-026 | Phone search -- existing customer | Enter known phone digits. | Results appear after 500ms debounce. | |
| UAT-027 | Auto-select single result | Enter phone matching one customer. | Customer auto-selected. Info card + menu + history load. | |
| UAT-028 | Create new customer | Enter unknown phone. Click "Create New Customer". | Dialog opens with phone pre-filled. Create customer. Auto-selected. | |
| UAT-029 | Edit existing customer | Select customer. Click edit icon. Modify. Update. | Customer info card reflects changes. | |
| UAT-030 | Repeat order from history | Select customer with history. Click "Repeat Order". | Cart filled with items from historical order. | |
| UAT-031 | Menu hidden until customer selected | No customer selected. | Center shows "Search for a customer to start ordering". | |
| UAT-032 | Submit call center order | Select customer. Add items. Send to Kitchen. | Order type "call_center" with customer_name and customer_phone. | |

---

## MODULE 6: Kitchen Display (KDS)

| ID | Test Case | Steps | Expected Result | Pass/Fail |
|----|-----------|-------|-----------------|-----------|
| UAT-033 | KDS fullscreen layout | Navigate to `/kitchen`. | Dark Kanban board. 4 columns: New, Preparing, Ready, Served. | |
| UAT-034 | Ticket info display | View tickets. | Order number, type badge, elapsed time (color-coded), items, total. | |
| UAT-035 | Bump ticket (New -> Preparing) | Click "Start" on New ticket. | Ticket moves to Preparing. Column counts update. | |
| UAT-036 | Full lifecycle via bump | Bump: New -> Preparing -> Ready -> Served. | Ticket moves through all columns. | |
| UAT-037 | Recall ticket | Click "Recall". | Yellow highlight + "Recalled" badge. "Clear" removes it. | |
| UAT-038 | Station filter | Select specific station from dropdown. | Only that station's tickets shown. | |
| UAT-039 | Audio toggle | Click Audio button. | Toggles on/off. Beep plays on new ticket when on. | |
| UAT-040 | WebSocket status | Observe badge. | "Realtime" (green) when connected, "Degraded" (red) when not. | |

---

## MODULE 7: Order Management

| ID | Test Case | Steps | Expected Result | Pass/Fail |
|----|-----------|-------|-----------------|-----------|
| UAT-041 | Orders page with filter tabs | Navigate to `/orders`. | 5 tabs: All, Active, In Kitchen, Ready, Completed. | |
| UAT-042 | Filter tabs switch content | Click each tab. | Orders filtered by status. | |
| UAT-043 | Order card info | View order card. | Shows #number, type badge, status, elapsed time, items, total. | |
| UAT-044 | Status transition | Click action button on order card. | Status advances. Badge + button update. | |
| UAT-045 | Void order | Click "Void". Confirm. | Status -> Voided. Red badge. Card faded. | |
| UAT-046 | Navigate to payment | Click "Pay" on unpaid order. | Navigated to `/payment/{orderId}`. | |
| UAT-047 | Receipt preview | Click receipt icon. | ReceiptModal with thermal layout. | |
| UAT-048 | Auto-refresh (15s) | Create order in another tab. Wait 15s. | New order appears without manual refresh. | |
| UAT-049 | Order Ticker on POS pages | View bottom bar on `/dine-in`, `/takeaway`, `/call-center`. | Live ticker of recent orders. | |

---

## MODULE 8: Payments

| ID | Test Case | Steps | Expected Result | Pass/Fail |
|----|-----------|-------|-----------------|-----------|
| UAT-050 | Payment page loads | Navigate to `/payment/{orderId}`. | Due amount, summary card, payment mode tabs. | |
| UAT-051 | Cash payment with change | Cash mode. Amount = total. Tendered = 1000. Post. | Paid updates. Change shown. Due = Rs. 0. | |
| UAT-052 | Card payment | Card mode. Amount = total. Reference filled. Post. | Paid. Transaction shows "card". | |
| UAT-053 | Split payment | Split mode. Cash + Card amounts sum to total. Post. | Both transactions recorded. Due = Rs. 0. | |
| UAT-054 | Cash drawer open/close | Open session. Then close. | Status toggles. Messages confirm actions. | |

---

## MODULE 9: Menu Management (Admin)

| ID | Test Case | Steps | Expected Result | Pass/Fail |
|----|-----------|-------|-----------------|-----------|
| UAT-055 | 3 tabs loaded | Navigate to `/admin/menu`. | Categories, Menu Items, Modifier Groups tabs. | |
| UAT-056 | Create category | Add Category. Fill fields. Create. | New category in list with Active badge. | |
| UAT-057 | Edit category | Click edit. Change name. Update. | Name updates. | |
| UAT-058 | Toggle category active | Click toggle switch. | Badge flips Active/Inactive. | |
| UAT-059 | Delete category | Click trash. Confirm. | Category removed. | |
| UAT-060 | Create menu item | Menu Items tab. Add Item. Fill fields. Create. | New item card with price and category. | |
| UAT-061 | Edit item with modifiers | Edit item. Change price. Toggle modifier groups. Update. | Updates reflected. | |
| UAT-062 | Create modifier group + options | Modifier Groups tab. Add group. Add option. | Group with option visible. Price badge shows. | |
| UAT-063 | Category filter on Items | Use category dropdown filter. | Items filtered to selected category. | |

---

## MODULE 10: Floor Editor (Admin)

| ID | Test Case | Steps | Expected Result | Pass/Fail |
|----|-----------|-------|-----------------|-----------|
| UAT-064 | Floor Editor loads | Navigate to `/floor-editor`. | Floor tabs. Tables on dot-grid canvas. | |
| UAT-065 | Drag and drop table | Drag table to new position. | Table follows mouse. Save button enables. | |
| UAT-066 | Save positions | Click "Save Layout". | Success message. Save button disables. | |
| UAT-067 | Add table | Click "Add Table". Fill fields. Add. | New table on canvas. | |
| UAT-068 | Delete table | Select table. Delete. Confirm. | Table removed. | |
| UAT-069 | Edit table properties | Select table. Change number/shape/capacity/rotation. | Canvas updates in real-time. | |
| UAT-070 | Add new floor | Click "+". Enter name. Create. | New floor tab appears. | |

---

## MODULE 11: Reports (Admin)

| ID | Test Case | Steps | Expected Result | Pass/Fail |
|----|-----------|-------|-----------------|-----------|
| UAT-071 | Reports page loads | Navigate to `/admin/reports`. | Date range inputs. Preset buttons. Export CSV. | |
| UAT-072 | Summary KPI cards | Select date range with data. | Revenue, Orders, Avg Value, Tax cards. | |
| UAT-073 | Channel breakdown | Scroll to channel section. | Bar chart + table per channel. | |
| UAT-074 | Hourly chart | View hourly section. | Bar chart with 24-hour bars. | |
| UAT-075 | Top/Bottom items | Scroll to item tables. | Ranked tables with qty and revenue. | |
| UAT-076 | CSV export | Click Export CSV. | File downloads. | |
| UAT-077 | Date preset switching | Click Yesterday, This Month, etc. | Dates update. Data reloads. | |

---

## MODULE 12: Z-Report (Admin)

| ID | Test Case | Steps | Expected Result | Pass/Fail |
|----|-----------|-------|-----------------|-----------|
| UAT-078 | Z-Report loads for today | Navigate to `/admin/z-report`. | KPIs + Cash Drawer + Channel + Payment + Status + Top Items. | |
| UAT-079 | Date change | Change date picker. | Report reloads for that date. | |
| UAT-080 | Print Z-Report | Click Print. | Browser print dialog. Clean print layout. | |

---

## MODULE 13: Staff Management (Admin)

| ID | Test Case | Steps | Expected Result | Pass/Fail |
|----|-----------|-------|-----------------|-----------|
| UAT-081 | Staff list loads | Navigate to `/admin/staff`. | Table with 3+ seed users. | |
| UAT-082 | Search staff | Type "admin". | List filters after 300ms debounce. | |
| UAT-083 | Create staff | Add Staff. Fill all fields. Create. | Toast success. New row appears. | |
| UAT-084 | Edit staff | Click pencil. Change name/role. Update. | Toast success. Row updates. | |
| UAT-085 | Toggle active/inactive | Click switch. | Status badge flips. Toast confirms. | |

---

## MODULE 14: Settings (Admin)

| ID | Test Case | Steps | Expected Result | Pass/Fail |
|----|-----------|-------|-----------------|-----------|
| UAT-086 | Settings loads with config | Navigate to `/admin/settings`. | 4 cards: General, Tax, Payment Flow, Receipt. | |
| UAT-087 | Change payment flow | Click Pay First. Save. | Active badge moves. Persists on refresh. | |
| UAT-088 | Receipt header/footer with preview | Type header. Preview updates live. Save. | Persists. | |
| UAT-089 | Tax rate change | Change to 17%. Save. | Persists. Basis points shown correctly. | |

---

## MODULE 15: Receipts

| ID | Test Case | Steps | Expected Result | Pass/Fail |
|----|-----------|-------|-----------------|-----------|
| UAT-090 | Receipt modal all sections | Open receipt from Orders page. | Header, items, modifiers, tax, total, payments, footer all present. | |
| UAT-091 | Receipt print window | Click Print in modal. | New window opens with 80mm thermal layout. Print dialog. | |

---

## MODULE 16: Cross-Cutting

| ID | Test Case | Steps | Expected Result | Pass/Fail |
|----|-----------|-------|-----------------|-----------|
| UAT-092 | Toast on success | Save settings or create staff. | Green toast auto-dismisses. | |
| UAT-093 | Toast on error | Create staff with duplicate email. | Red toast with error detail. | |
| UAT-094 | Integer math (no float errors) | Add Rs. 325 item + Rs. 50 modifier, qty 3. | Line = Rs. 1,125. Tax = Rs. 180. Total = Rs. 1,305. No .9999 artifacts. | |
| UAT-095 | PKR formatting everywhere | Browse all pages. | All amounts use "Rs." prefix with comma separators. | |
| UAT-096 | Admin nav links | Click Orders, Admin in header. | Navigate to `/orders`, `/admin`. | |

---

## MODULE 17: Admin Dashboard

| ID | Test Case | Steps | Expected Result | Pass/Fail |
|----|-----------|-------|-----------------|-----------|
| UAT-097 | KPI cards | Navigate to `/admin`. | Revenue, Orders, Avg Value, Table Utilization cards. | |
| UAT-098 | Live Operations | Scroll to Live Operations. | 3 columns: Dine-In, Takeaway, Call Center with active orders. | |
| UAT-099 | Manual refresh | Click refresh icon. | Data reloads. Timestamp updates. | |

---

## Execution Order

1. **Auth** (UAT-001 to 009) -- unlocks everything
2. **Dine-In** (014-022) -- creates orders for downstream tests
3. **Takeaway** (023-025) -- more orders
4. **Call Center** (026-032) -- more orders + customer data
5. **KDS** (033-040) -- verify tickets from orders above
6. **Orders** (041-049) -- manage created orders
7. **Payments** (050-054) -- pay for orders
8. **Receipts** (090-091) -- view paid order receipts
9. **Reports + Z-Report** (071-080) -- now has data to display
10. **Menu** (055-063), **Floor** (064-070), **Staff** (081-085), **Settings** (086-089) -- admin features
11. **Cross-cutting** (092-099) -- verify throughout

## Stop-UAT Criteria

Pause UAT and fix immediately if you encounter:
- Data integrity bugs (totals don't add up)
- Auth/role bypass (cashier accessing admin features)
- Payment/order total mismatches
- Receipt/report calculation errors
- Blank pages or unhandled JS errors in console
