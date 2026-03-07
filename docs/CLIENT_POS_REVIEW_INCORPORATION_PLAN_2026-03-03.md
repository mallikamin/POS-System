# Client POS Review Response Plan - March 3, 2026

## Purpose
This document maps every client POS review point to:
1. What exists today.
2. What we will implement to incorporate the request.

## Status Legend
- `Exists`: already implemented and usable.
- `Partial`: some support exists, but not complete to client expectation.
- `Missing`: not implemented yet.

## Point-by-Point Incorporation Plan

| # | Client Review Point | Current State | What Exists Today | What We Will Do to Incorporate |
|---|---|---|---|---|
| 1 | Show separate rates for extras/add-ons on receipt | Missing | Modifiers appear by name, but price is rolled into line item total | Add modifier price adjustments to receipt API and render each add-on with signed amount on receipt UI (P0). |
| 2 | Tax percentage should vary by payment mode | Missing | One flat `default_tax_rate` is used | Add payment-mode tax configuration and billing preview/service logic for mode-specific tax (P1-A). |
| 3 | Correct tax to 16% cash and 5% card | Partial | Single baseline tax is configurable; method-specific rates do not exist | Keep baseline at 16% where single-rate path applies (P0), then implement explicit cash/card tax rate config and application (P1-A). |
| 4 | Split cash/card payment should reflect clearly on bill | Exists | Split payments are stored and shown as separate payment lines | Keep behavior; improve display clarity alongside dual-total preview (P1-A polish). |
| 5 | Show both billing options (cash total and card total) | Missing | Single `order.total` only | Add dual-total preview API/UI so cashier can show both totals before payment (P1-A). |
| 6 | Support discount types (bank promo, ESR, customer, etc.) | Missing | Only one numeric `discount_amount` field | Build typed discount engine (types, rules, UI, receipt/report integration) (P1-B). |
| 7 | Dine-in table remains open with one consolidated final bill | Missing | Each send-to-kitchen creates a new order | Introduce `table_sessions` and aggregate unpaid orders into one final settlement flow (P1-B). |
| 8 | Support both pay-after-eat and pay-before-eat models | Partial | `payment_flow` setting exists but runtime behavior is not fully enforced | Enforce `payment_flow` end-to-end in order/payment behavior (P3, with groundwork in P1-B). |
| 9 | Show table number clearly on order screen | Missing | Order has `table_id`, but table number/label is not consistently surfaced | Include table label/number in order responses and display on Orders/Payment UI (P0). |
| 10 | Assign waiter/server to each order | Missing | No waiter assignment field/workflow | Add order waiter assignment field, APIs, and UI selection (P2). |
| 11 | Waiter-wise order report | Missing | No waiter dimension available for reporting | Add waiter performance report endpoint + admin UI report (P2). |
| 12 | Customer name/profile with Walk-in default | Partial | `customer_name` exists; call-center has customer flow | Default dine-in/takeaway orders to `Walk-in Customer` while allowing named customer override (P2). |
| 13 | Void transactions in reports with reason | Partial | Void status and reason are logged in status/audit logs | Add dedicated void report including reasons/counts/amount impact (P2). |
| 14 | Mandatory comment before void | Missing | Void reason is optional currently | Make void reason required at API validation and UI level (P1-A). |
| 15 | Password authorization before void | Missing | Role check only (admin) | Add re-auth verify-password flow before void action (P1-A). |
| 16 | Proper refund option with tracking | Exists | Refund flow exists with traceable payment links | Keep existing behavior and align in reporting/authorization policy where needed. |
| 17 | Shift closing report with cash reconciliation | Exists | Z-report includes opening, in/out, expected, counted, variance | Keep and include in rollout verification/UAT evidence. |
| 18 | Access control for discount/void/refund | Partial | Role-based gates exist for void/refund | Move sensitive actions to fine-grained permission checks and policy alignment (P3). |
| 19 | Payment-mode-wise daily sales report | Partial | Z-report includes method breakdown; general reports do not | Add dedicated payment-mode daily report + export in reports module (P2). |
| 20 | Item-wise and category-wise sales report | Exists | Item and category performance endpoints/UI exist | Keep and include in client walkthrough. |
| 21 | Full daily sale summary (cash+credit, tax, net sale) | Partial | Sales summary has revenue/orders/tax, but no full cash-vs-credit/net layout | Extend summary model and report UI/export to include cash, card/credit, discount, and net sale lines (P2). |

## Delivery Plan

### P0 (Immediate - same day)
1. Receipt add-on/modifier pricing breakdown.
2. Tax baseline verification/fix for 16% where single-rate path is still used.
3. Table number/label visibility on orders and payment context.

### P1-A
1. Dual totals and payment-mode tax preview.
2. Mandatory void reason.
3. Password re-auth before void.

### P1-B
1. Table session consolidation for final dine-in billing.
2. Typed discount engine.

### P2
1. Waiter assignment and waiter reports.
2. Walk-in customer default behavior.
3. Void report with reasons.
4. Enhanced daily summary and payment-mode daily reports.

### P3
1. Strict `payment_flow` runtime enforcement.
2. Fine-grained permission system for sensitive actions.

## Implementation Notes
- P0 will avoid DB migrations (low-risk visible improvements).
- P1-B is the major structural phase (table sessions + discounts).
- Existing working features (refunds, reconciliation, item/category reporting) remain intact and will be validated during regression testing.
