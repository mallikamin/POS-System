# QuickBooks Online Account Mapping - Review Document

**Date Completed**: 2026-03-25
**Mapped By**: Sitara Infotech (POS System)
**QuickBooks Company**: Younis Kamran (Realm ID: 9341456151192096)
**Status**: ✅ Complete — Awaiting Client Review

---

## Summary

✅ **19 POS accounting categories** mapped to QuickBooks
✅ **6 new QB accounts created** in your Chart of Accounts
✅ **13 mapped to existing QB accounts**
✅ **0 skipped** — Full coverage achieved

**Next Step**: Please review the mappings below and let us know if any changes are needed.

---

## What We Did

The POS system analyzed your QuickBooks Chart of Accounts (80 accounts) and automatically matched each POS accounting need to the best QB account. Where no suitable match existed, we created new accounts in your QuickBooks.

**You can verify the new accounts by going to**: Settings → Chart of Accounts in QuickBooks Online.

---

## Account Mappings

### ✅ Revenue Accounts (Income)

| POS Category | Mapped To | QB Account ID | Action |
|--------------|-----------|---------------|--------|
| **Food Sales Income** | Sales | QB 80 | Mapped to existing |
| **Beverage Sales Income** | Beverage Sales Income | QB 82 | **Created new** |
| **Service Charge** | Revenue - General | QB 19 | Mapped to existing |
| **Delivery Fee Income** | Revenue - General | QB 19 | Mapped to existing |

**Notes:**
- Food and beverage sales are now tracked separately for reporting
- Service charges and delivery fees both use "Revenue - General" — let us know if you want separate accounts

---

### ✅ Cost of Goods Sold (COGS)

| POS Category | Mapped To | QB Account ID | Action |
|--------------|-----------|---------------|--------|
| **Cost of Goods Sold** | Change in inventory - COS | QB 43 | Mapped to existing |
| **Discounts Given** | Discounts given - COS | QB 42 | Mapped to existing |

**Notes:**
- Direct food/ingredient costs go to "Change in inventory - COS"
- Customer discounts mapped to "Discounts given - COS" (typically discounts are contra-revenue, not COGS — please confirm if this is correct for your accounting)

---

### ✅ Assets (Bank & Cash)

| POS Category | Mapped To | QB Account ID | Action |
|--------------|-----------|---------------|--------|
| **Bank / Deposit Account** | Bank / Deposit Account | QB 84 | **Created new** |
| **Cash on Hand** | Cash and cash equivalents | QB 32 | Mapped to existing |
| **Mobile Wallet Account** | Mobile Wallet Account | QB 85 | **Created new** |

**Notes:**
- "Bank / Deposit Account" — where card/bank payments are deposited (specify your actual bank name if you'd like us to rename)
- "Mobile Wallet Account" — for JazzCash, Easypaisa, SadaPay deposits
- "Cash on Hand" — physical cash in register/drawer

---

### ✅ Liabilities (Money Owed)

| POS Category | Mapped To | QB Account ID | Action |
|--------------|-----------|---------------|--------|
| **Sales Tax Payable** | Sales Tax Payable | QB 83 | **Created new** |
| **Tips / Gratuity** | Accrued liabilities | QB 35 | Mapped to existing |
| **Gift Card Liability** | Deferred Revenue | QB 81 | Mapped to existing |

**Notes:**
- "Sales Tax Payable" — GST/FBR (17%), PRA/PST (16%) collected from customers
- Tips collected from customers, owed to staff
- Gift cards — liability until customer redeems

---

### ✅ Operating Expenses

| POS Category | Mapped To | QB Account ID | Action |
|--------------|-----------|---------------|--------|
| **Platform Commission Expense** | Uncategorised Expense | QB 3 | Mapped to existing |
| **Rent / Occupancy** | Rent or lease payments | QB 60 | Mapped to existing |
| **Salaries & Wages** | Payroll Expenses | QB 75 | Mapped to existing |
| **Utilities** | Utilities | QB 66 | Mapped to existing |
| **Packaging & Disposables** | Supplies | QB 67 | Mapped to existing |

**Notes:**
- Platform commissions (Foodpanda, Cheetay, etc.) mapped to "Uncategorised Expense" — suggest renaming to "Platform Commissions" or "Delivery Platform Fees" for clarity

---

### ✅ Adjustments & Variances

| POS Category | Mapped To | QB Account ID | Action |
|--------------|-----------|---------------|--------|
| **Rounding Adjustment** | Rounding Adjustment | QB 86 | **Created new** |
| **Cash Over/Short** | Cash Over/Short | QB 87 | **Created new** |

**Notes:**
- Rounding — small differences on cash transactions (paisa rounding)
- Cash Over/Short — discrepancies in cash drawer counts

---

## New Accounts Created in Your QuickBooks

These 6 accounts were created automatically because no suitable match existed:

| Account Name | Type | Detail Type | QB ID |
|--------------|------|-------------|-------|
| Beverage Sales Income | Income | SalesOfProductIncome | 82 |
| Sales Tax Payable | Other Current Liability | GlobalTaxPayable | 83 |
| Bank / Deposit Account | Bank | CashAndCashEquivalents | 84 |
| Mobile Wallet Account | Bank | CashAndCashEquivalents | 85 |
| Rounding Adjustment | Other Expense | OtherMiscellaneousExpense | 86 |
| Cash Over/Short | Other Expense | OtherMiscellaneousExpense | 87 |

**To verify:** Log into QuickBooks Online → Settings → Chart of Accounts → Look for these 6 accounts.

---

## Review Checklist

Please review the mappings above and let us know:

### 1. ✅ Required Changes (if any)

- [ ] Any accounts need to be renamed? (e.g., "Bank / Deposit Account" → "Allied Bank - Checking")
- [ ] Any mappings incorrect? (e.g., Service Charge should go to a different account)
- [ ] Any accounts should be merged? (e.g., combine Cash on Hand + Mobile Wallet)

### 2. ⚠️ Items Flagged for Your Review

**A. Discounts Given → "Discounts given - COS" (COGS account)**
- Question: Are customer discounts part of Cost of Goods Sold in your accounting?
- Standard practice: Discounts are usually "contra-revenue" (reduces sales), not COGS
- Action needed: Confirm this is correct OR suggest alternate mapping

**B. Service Charge + Delivery Fee → both use "Revenue - General"**
- Question: Is it OK to combine these, or do you want separate tracking?
- If separate: We can create "Service Charge Income" and "Delivery Fee Income" accounts

**C. Platform Commission → "Uncategorised Expense"**
- Suggestion: Rename to "Platform Commissions" or "Delivery Platform Fees" for clearer reporting
- Action: Let us know if you want us to rename this account

### 3. ✅ Approval

Once you've reviewed:
- [ ] **Approve as-is** → We'll proceed to test sync
- [ ] **Request changes** → Share the changes, we'll update mappings

---

## What Happens Next

### Step 1: Your Review (This Document)
- Review mappings above
- Check the 6 new accounts in your QuickBooks
- Share any requested changes with Sitara Infotech

### Step 2: Adjustments (if needed)
- We'll update mappings based on your feedback
- Rename/reassign accounts as requested

### Step 3: Test Sync
- Create a sample order in POS
- Push to QuickBooks as a Sales Receipt
- Verify all data appears correctly in QB
- Confirm account assignments are accurate

### Step 4: Go-Live
- Enable automatic sync for all orders
- POS transactions will flow to QuickBooks in real-time
- Monthly reconciliation support

---

## Technical Details (for reference)

**Mapping Method**: Fuzzy matching algorithm (90+ accounts analyzed, 19 mapped)
**API Integration**: QuickBooks Online API v3 (OAuth 2.0)
**Sync Frequency**: Real-time (orders sync immediately after payment)
**Data Format**: Sales Receipts (for paid orders), Invoices (for credit sales if needed)

**Database**: All mappings stored in `qb_account_mappings` table
**Reversible**: Mappings can be changed anytime without data loss

---

---

**Document Version**: 1.0
**Generated**: 2026-03-25
**Last Updated**: 2026-03-25
**File**: `docs/QB_ONLINE_ACCOUNT_MAPPING_REVIEW.md`
