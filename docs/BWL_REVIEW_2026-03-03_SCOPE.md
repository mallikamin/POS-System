# BWL Client Review Scope - March 3, 2026

## Context
- Source: Client feedback from `POS.docx` (BPO World Limited).
- Branch: `wip/BWL3rdMarchChanges`.
- Goal: Convert client review into an implementation-ready scope with priority and technical decisions.

## Confirmed Current State

### Exists
- Split/partial payments and payment ledger tracking.
- Refund flow with parent payment linkage.
- Z-report cash reconciliation.
- Item/category reporting.
- Role-gated admin actions (void/refund endpoints).

### Partial
- `payment_flow` config exists but is not enforced in order runtime behavior.
- Void data appears in status/audit logs, but no dedicated void-reason report.
- Payment method breakdown exists in Z-report, not in general daily summary reports.
- `customer_name` exists on orders but no default walk-in behavior outside call-center flow.

### Missing
- Modifier/add-on price breakdown on receipt.
- Tax-by-payment-mode support (cash vs card) and dual-total bill preview.
- Typed discount engine (bank promo/ESR/customer/manual categories).
- Dine-in table session consolidation (single final bill per open table session).
- Table number visibility on order cards/list views.
- Waiter assignment and waiter-wise reporting.
- Mandatory void reason and password re-auth before void.

## Client Review Master Checklist (21 Points)
1. Separate rates for extras/add-ons on receipt. Status: Missing. Planned: P0.
2. Tax percentages vary by payment mode. Status: Missing. Planned: P1-A.
3. Correct tax rates (cash 16%, card 5%). Status: Missing/Config gap. Planned: P0 (seed/config correction) + P1-A (method-specific logic).
4. Split cash/card payment reflected on bill. Status: Exists.
5. Show both billing options (cash total vs card total). Status: Missing. Planned: P1-A.
6. Multiple discount types (bank promo, ESR, customer, etc.). Status: Missing. Planned: P1-B.
7. Dine-in table remains open with consolidated final bill. Status: Missing. Planned: P1-B.
8. Support both pay-after-eat and pay-before-eat models. Status: Partial. Planned: P3 full enforcement (plus P1-B session groundwork).
9. Display table number clearly on order screen. Status: Missing. Planned: P0.
10. Assign waiter/server per order. Status: Missing. Planned: P2.
11. Waiter-wise report. Status: Missing. Planned: P2.
12. Customer profile/name with default Walk-in Customer. Status: Partial. Planned: P2 (with default behavior surfaced from backend/frontend).
13. Void transactions in reports with reasons. Status: Partial. Planned: P2.
14. Mandatory comment before void. Status: Missing. Planned: P1-A.
15. Password authorization before void. Status: Missing. Planned: P1-A.
16. Refund option with complete tracking. Status: Exists.
17. Shift closing report with cash reconciliation. Status: Exists.
18. Access controls for sensitive actions (discount/void/refund). Status: Partial. Planned: P3 (fine-grained permission checks).
19. Payment-mode-wise daily sales report. Status: Partial. Planned: P2.
20. Item-wise and category-wise sales reports. Status: Exists.
21. Full daily summary (cash+credit, tax, net sale). Status: Partial. Planned: P2.

## Manual Verification Status - March 7, 2026
- Pending manual client-review verification:
  - #16 Refund option with complete tracking
  - #17 Shift closing report with cash reconciliation
  - #18 Access controls for sensitive actions (discount, void, refund)
- Adjacent follow-up checks to verify after the items above:
  - #8 Pay-before-eat runtime enforcement
  - #19 Payment-mode-wise daily sales report
  - #21 Full daily summary (cash, credit, tax, net sale)

## Agreed Technical Decisions

1. Tax by payment mode
- Keep order creation tax-neutral for method-specific billing.
- Add payment-time total preview endpoint:
  - `cash_total` using configured cash tax rate.
  - `card_total` using configured card tax rate.
  - split allocation preview for mixed payments.
- Final tax posting occurs at payment settlement.

2. Table consolidation model
- Introduce `table_sessions` entity:
  - `id`, `tenant_id`, `table_id`, `status` (`open|closed`), `opened_at`, `closed_at`, `opened_by`, `closed_by`.
- Orders reference `table_session_id` (nullable for non-dine-in).
- Final bill is aggregated over all unpaid orders in open session.

3. Void authorization
- Enforce non-empty reason at API validation layer.
- Add `POST /auth/verify-password` for re-auth before high-risk actions.
- Require successful verification token in void request.

4. Receipt visibility first
- Add modifier price lines to receipt schema/UI as early quick win.

## Priority Plan

## P0 (Immediate, low risk, high visibility)
1. Modifier prices on receipt.
2. Tax rate correction validation in config/UI (ensure 16% cash baseline visible and applied where current single tax is still used).
3. Table number display on order cards/list/payment context.

## P1 (Core business behavior)
1. Dual totals and tax-by-payment-mode previews.
2. Table session consolidation for pay-after-eat.
3. Mandatory void reason + password re-auth flow.
4. Discount engine (typed discounts + API + admin UI + receipt/report integration).

## P2 (Operational completeness)
1. Waiter assignment and waiter-wise report.
2. Walk-in customer default for dine-in/takeaway.
3. Dedicated void report with reason analytics.
4. Enhanced daily summary: cash/card split, tax, discount, net sale.

## P3 (Hardening and policy)
1. Enforce `payment_flow` behavior end-to-end (`order_first` vs `pay_first`).
2. Move from role-only checks to permission-based policy checks for sensitive actions.

## Implementation Workstreams

### WS1: Data model and migrations
- Add `table_sessions` table.
- Add `orders.table_session_id` and `orders.assigned_waiter_id`.
- Add tenant payment tax config fields:
  - `cash_tax_rate_bps`, `card_tax_rate_bps`.
- Add discount tables:
  - `discount_types`, `order_discounts` (or equivalent normalized structure).
- Add void authorization metadata fields/tables as needed.
- Ensure `Walk-in Customer` default behavior is consistently represented in order create/update flows.
- Surface existing `OrderItemModifier.price_adjustment` in receipt response contracts.

### WS2: Backend APIs/services
- Receipt service/schema: modifier price detail lines.
- Payment preview API for dual totals and split allocations.
- Table session APIs:
  - open/get active/add order/close/settle summary.
- Order APIs: include table label/number and waiter info in response payloads.
- Auth verify-password endpoint and void enforcement.
- Reporting APIs for waiter summary, payment-mode daily summary, void reasons.

### WS3: Frontend
- Receipt modal: show add-on names with price adjustments.
- Orders cards/pages: table number display.
- Payment page: dual totals, split-tax clarity.
- Dine-in flow: open table session UX and consolidated bill settle flow.
- Void modal: reason mandatory + password confirmation.
- Admin reports: waiter report, void report, enhanced daily summary.

### WS4: Tests and QA
- Unit/integration tests for:
  - payment-mode tax preview and settlement.
  - table session aggregation correctness.
  - void reason/password enforcement.
  - discount calculations and report totals.
- UAT addendum checklist for all client review items.

## Suggested Delivery Sequence
1. P0 in one same-day short release.
2. P1 split into 2 releases:
   - Release A: tax preview + void hardening.
   - Release B: table sessions + discount engine.
3. P2 reporting and waiter features.
4. P3 policy hardening.

## P0 Immediate Clarification
- P0 tax correction includes seed/config baseline fix from 17% to 16% where applicable (seed defaults and environment/demo defaults), while method-specific tax behavior remains in P1-A.

## Out of Scope for this batch
- QuickBooks deep remapping changes unless impacted by discount/tax posting schema changes.
- Broad RBAC redesign beyond sensitive-action enforcement.

## Acceptance Criteria (High Level)
- Receipt clearly itemizes base item and each add-on/modifier charge.
- Billing screen shows cash total and card total before payment, including split scenario.
- Dine-in table can accumulate multiple orders into one final settlement.
- Void cannot proceed without reason and password verification.
- Reports include payment-mode daily split and net-sale view.
