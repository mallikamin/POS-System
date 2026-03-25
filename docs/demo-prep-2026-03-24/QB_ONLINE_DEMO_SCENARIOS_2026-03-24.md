# QuickBooks Online — Demo Scenarios (Click-by-Click)

**Companion to:** `YOUNIS_TEAM_DEMO_PLAN_2026-03-24.md` (main demo plan)
**Date:** March 24, 2026
**Environment:** pos-demo.duckdns.org (production) + QB Sandbox (realm 9341456656951079)
**QB Sandbox URL:** https://app.sandbox.qbo.intuit.com

---

## Setup Before Demo

### Browser Tabs (open before anyone arrives)

1. **Tab 1:** POS login page — `https://pos-demo.duckdns.org`
2. **Tab 2:** QB Sandbox — `https://app.sandbox.qbo.intuit.com` (already logged in, SalesReceipts list open)
3. **Tab 3:** POS Admin → QuickBooks (pre-loaded to show connection status)

### Pre-Check

- [ ] POS loads, admin login works (admin@demo.com / admin123)
- [ ] QB admin page shows "Connected" (green badge, company = "Younis Kamran Demo Restaurant")
- [ ] QB sandbox shows existing SalesReceipts from previous sync
- [ ] At least 1 free dine-in table available
- [ ] At least 1 completed+paid order exists (for refund demo)
- [ ] At least 1 voided order exists (for credit memo demo)

---

## Scenario 1: Dine-In Order → SalesReceipt in QB

**Story:** "A customer sits down, orders food with custom modifiers, pays with split payment. The POS posts this to QuickBooks as a SalesReceipt automatically."

### Step-by-Step in POS

1. **Login** as Admin (admin@demo.com / admin123 or PIN 1234)
2. **Dashboard** → Click **"Dine-In"** card
3. **Floor Plan** → Click a free table (e.g., Table 5 — turns blue/selected)
4. **Menu** → Select category **"BBQ & Grills"**
5. **Add item** → Click **"Chicken Tikka"** (shows in cart with price)
6. **Add item with modifier** → Click **"Seekh Kebab"**
   - Modifier modal appears → Select **"Extra Spicy"** and **"Double Portion"**
   - Click **"Add to Cart"** → Item shows with modifier surcharges
7. **Add one more** → Category **"Rice & Biryani"** → Click **"Chicken Biryani"**
8. **Review cart** → 3 items, modifiers visible, subtotal + tax calculated
9. **Place Order** → Click **"Place Order"** button
   - Order confirmed, ticket sent to kitchen
   - Order number generated (e.g., 260324-001)
10. **Navigate to Orders** → See the new order card with table number, items, status
11. **Advance through kitchen** (optional, for full flow):
    - Open KDS → Bump ticket to Preparing → Ready → Served
    - Or skip to payment if time is tight
12. **Payment** → Click **"Pay"** on the order
    - Shows order total with tax breakdown
    - **Split payment:** Enter PKR 500 as Card, remainder as Cash
    - Click **"Process Payment"**
    - Receipt modal appears — show itemized receipt with tax, payment lines
13. **Order is now Completed** — this is the trigger for QB sync

### What Happens in QB

- POS creates a **SalesReceipt** in QuickBooks
- DocNumber = order number (e.g., `260324-001`)
- Line items: Chicken Tikka, Seekh Kebab (with modifier notes), Chicken Biryani
- Tax: FBR GST + PRA PST breakdown
- Payment: Split — Card (PKR 500) + Cash (remainder)
- Customer: "Walk-In Customer" (default for unnamed dine-in)
- DepositTo: mapped cash drawer / bank account

### Show Proof in QB Sandbox

1. Switch to **Tab 2** (QB Sandbox)
2. Navigate to **Sales → All Sales** (or refresh the page)
3. Find the new SalesReceipt by DocNumber (order number)
4. Open it → Show:
   - Line items match POS order
   - Amounts match
   - Tax is posted
   - Payment method recorded
   - Customer reference

**Say to room:** "This is a real SalesReceipt in QuickBooks. No manual entry, no CSV import. The POS posted it directly through the API."

---

## Scenario 2: Takeaway Order (Cash) → SalesReceipt in QB

**Story:** "A takeaway order paid in cash — simplest flow, shows up in QB the same way."

### Step-by-Step in POS

1. From Dashboard → Click **"Takeaway"**
2. **Menu** → Select **"Karahi & Handi"** → Click **"Chicken Karahi"**
3. **Add another** → **"Beverages"** → Click **"Lassi"**
4. **Place Order** → Gets a takeaway token number
5. **Pay** → Select **Cash**, enter amount tendered
   - Shows change due
   - Click **"Process Payment"**
6. **Order completed** — syncs to QB

### Show Proof in QB Sandbox

1. Switch to QB Sandbox tab
2. New SalesReceipt appears with takeaway order number
3. Payment method = Cash
4. Same line item structure

**Say to room:** "Same accounting treatment whether it's dine-in or takeaway. The POS handles the channel, QuickBooks gets a clean SalesReceipt either way."

---

## Scenario 3: Voided Order → CreditMemo in QB

**Story:** "A manager voids an order — maybe the customer changed their mind or there was an error. The POS reverses it in QuickBooks as a Credit Memo."

### Step-by-Step in POS

1. Go to **Orders** page
2. Find a confirmed/completed order (use one from earlier if available, or use a pre-existing order)
3. Click **"Void"** on the order card
   - Void dialog appears → requires a **reason** (type "Customer cancelled")
   - Requires **password re-authentication** (enter admin password)
   - Click **"Confirm Void"**
4. Order card changes to **Voided** status (red badge)

### What Happens in QB

- POS creates a **CreditMemo** in QuickBooks
- DocNumber = `VOID-{order_number}` (e.g., `VOID-260324-001`)
- Mirrors the original SalesReceipt line items (reverses revenue)
- References the original transaction in the private note field
- Net effect: income account is reduced by the voided amount

### Show Proof in QB Sandbox

1. Switch to QB Sandbox
2. Navigate to **Sales → All Sales** → Filter by Credit Memos
3. Find `VOID-{order_number}`
4. Open it → Show reversed line items

**Say to room:** "The void is not just internal. QuickBooks knows about it. Your books stay clean — no phantom revenue sitting in the ledger."

---

## Scenario 4: Refund → RefundReceipt in QB

**Story:** "A customer brings back a complaint on a completed order. The manager issues a partial refund. QuickBooks records it as a RefundReceipt."

### Step-by-Step in POS

1. Go to **Orders** page → Find a **Completed** order with payment
2. Click **"Refund"** on the order
   - Refund dialog appears
   - Enter refund amount (can be partial — e.g., PKR 350 out of PKR 1,200 total)
   - Enter refund note (e.g., "Cold food complaint")
   - Click **"Process Refund"**
3. Refund recorded — payment status updates to show refund line

### What Happens in QB

- POS creates a **RefundReceipt** in QuickBooks
- DocNumber = `REF-{order_number}` (e.g., `REF-260324-002`)
- For partial refund: single line item with refund amount
- For full refund: mirrors all original line items
- DepositTo: same account as original payment (cash drawer / bank)

### Show Proof in QB Sandbox

1. Switch to QB Sandbox
2. Navigate to Sales → Filter by Refund Receipts
3. Find `REF-{order_number}`
4. Show the refund amount matches what was entered in POS

**Say to room:** "Refunds are tracked end-to-end. The POS knows it, QuickBooks knows it, and management reporting reflects the net revenue correctly."

---

## Scenario 5: Daily Summary / Close → JournalEntry + Deposit in QB

**Story:** "At end of day, the manager runs a daily close. Instead of posting 50 individual SalesReceipts, the POS can post one summary Journal Entry to QuickBooks — cleaner books for high-volume days."

### Step-by-Step in POS

1. Go to **Admin → QuickBooks → Sync** tab
2. In the **Trigger Sync** panel:
   - Select sync type: **"Daily Summary"**
   - Set the **From date** to today's date
   - Click **"Trigger Sync"**
3. Success banner appears: "1 jobs created"
4. **Job Queue** below updates — shows the daily_summary job
5. Job processes (may take a few seconds) → Status changes to **Completed** (green)

### What Happens in QB

Two entities are created:

**1. JournalEntry** (DocNumber: `DAILY-2026-03-24`)
- Double-entry accounting:
  - DEBIT: Bank/Cash account (total collected today)
  - CREDIT: Income account (net revenue minus discounts)
  - CREDIT: Tax Payable account (total tax collected)
- Memo includes order count, subtotals, and summary

**2. Deposit** (companion)
- Moves funds from Undeposited Funds to the business bank account
- Breaks down by payment type (cash vs card)

### Show Proof in QB Sandbox

1. Switch to QB Sandbox
2. Find the JournalEntry: `DAILY-2026-03-24`
3. Show the double-entry lines (debits = credits)
4. Show the deposit if visible

**Say to room:** "This is your daily closeout hitting QuickBooks. One clean journal entry instead of dozens of individual transactions. The accountant sees a reconciled summary, not noise."

---

## Scenario 6: The Admin Control Surface (Walkthrough)

**Story:** "This is where the restaurant owner or accountant manages the QuickBooks connection — no developer needed."

### Click Path

1. **Admin → QuickBooks** (Tab 3 already open)

2. **Connection tab:**
   - Show: Connected status, company name, realm ID, last sync time
   - Show: Chart of Accounts backup section (snapshot count, download button)
   - **Say:** "The connection is OAuth-based, same as logging into any web app. The CoA backup means we always have a reference point."

3. **Account Setup tab:**
   - Show: Match grade (should be "A" with green badge)
   - Show: Coverage percentage (18/18 or similar)
   - Scroll through matched accounts — show green checkmarks
   - **Say:** "We automatically matched your POS accounting needs to your QuickBooks Chart of Accounts. 18 out of 18 matched. Grade A."
   - Show: Health Check button → Click it
   - Show: All healthy (green checks)
   - **Say:** "Health check confirms all mappings are still valid. If something changes in QB, we catch it here."

4. **Mappings tab:**
   - Show: Full mapping table (income, COGS, tax payable, bank, etc.)
   - Click **Validate** → Green banner: "All required mappings configured"
   - **Say:** "Every POS accounting concept has a mapped QB account. This is transparent and editable — the accountant controls where things post."

5. **Sync tab:**
   - Show: Stats cards (total synced, last 24h, pending, failed)
   - Show: Sync-by-type badges (sales_receipts, items, customers, tax_codes)
   - Show: Job Queue table with completed jobs
   - Show: Audit Log — click to switch view
   - Show: Individual log entries with QB entity type, doc number, amount, status, duration
   - **Say:** "Full audit trail. Every sync operation is logged — what was sent, what QB returned, how long it took. If something fails, you see it here and can retry with one click."

---

## Key Messages for the Room

Use these one-liners when transitioning between scenarios:

| After... | Say... |
|----------|--------|
| SalesReceipt proof | "No manual entry. No CSV. It's automatic." |
| CreditMemo proof | "Voids hit QuickBooks too. Your books are always accurate." |
| RefundReceipt proof | "Refunds are tracked end-to-end. Net revenue is always correct." |
| Daily summary proof | "One journal entry per day. Clean books, not clutter." |
| Health check | "If something breaks in QB, we detect it before it causes sync errors." |
| Audit log | "Every transaction has a paper trail. Compliance-ready." |

---

## Fallback: If Live Sync Is Slow

If the QB sandbox is slow or a sync doesn't process during the demo:

1. **Don't wait.** Move on to the next scenario.
2. **Show the Audit Log** tab — point to previously synced entries as proof
3. **Show the QB Sandbox** tab — point to existing SalesReceipts from the pre-demo sync
4. **Say:** "The sync is queued and will process shortly. Here are previous examples showing exactly what it produces."

---

## Fallback: If QB Sandbox Is Unreachable

If Intuit's sandbox is down or slow:

1. Use the **Sync tab's Audit Log** in POS as primary evidence
2. Show log entries with QB entity types, doc numbers, amounts, and "success" status
3. **Say:** "QuickBooks is a third-party service and their sandbox occasionally has latency. Our POS has the full audit trail showing successful sync — and here's the data that landed."

---

## Order of Scenarios (Recommended)

For a 15-minute QB segment, do these in order:

| # | Scenario | Time | Priority |
|---|----------|------|----------|
| 1 | Admin Control Surface (walkthrough) | 4 min | Must show |
| 2 | Dine-In → SalesReceipt (live or reference existing) | 3 min | Must show |
| 3 | Void → CreditMemo | 2 min | Must show |
| 4 | Refund → RefundReceipt | 2 min | Should show |
| 5 | Daily Summary → JournalEntry | 2 min | Should show |
| 6 | Takeaway → SalesReceipt | 1 min | Nice to have |

If time is very tight (10 min), do scenarios 1, 2, and 3 only — then reference the audit log for the rest.

---

## What NOT to Demo

- Do not show OAuth connect/disconnect flow (risky in live demo, and already connected)
- Do not run Account Matching live (it's already done, just show the result)
- Do not attempt to re-apply mappings (destructive if it goes wrong)
- Do not show raw API responses or developer console
- Do not mention QBXML, SOAP, or Web Connector (that's QB Desktop territory)
