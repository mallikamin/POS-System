# QuickBooks Desktop Setup Guide

**Version:** 1.0
**Date:** 2026-03-25
**For:** Sitara POS System

---

## Overview

This guide walks through setting up QuickBooks Web Connector (QBWC) to sync your Sitara POS system with QuickBooks Desktop.

**What You'll Need:**
- QuickBooks Desktop (Pro, Premier, or Enterprise)
- QBWC Client (free download from Intuit)
- Admin access to QuickBooks Desktop
- Sitara POS admin account

**Time Required:** 15-20 minutes

---

## Step 1: Download QBWC Client

### Option A: Direct Download
Visit: https://qbwc.qbn.intuit.com/

### Option B: From QuickBooks Website
1. Go to https://quickbooks.intuit.com/
2. Navigate to: Support → Downloads → Web Connector
3. Download the installer (QBWebConnector.exe)

**System Requirements:**
- Windows 7 or later
- QuickBooks Desktop 2016 or later
- .NET Framework 4.5 or later
- 50 MB free disk space

---

## Step 2: Install QBWC

1. Run `QBWebConnector.exe` installer
2. Follow installation wizard
3. Accept license agreement
4. Choose installation directory (default: `C:\Program Files\Intuit\QuickBooks Web Connector\`)
5. Complete installation
6. Launch QBWC (should start automatically)

**Default QBWC Location:**
```
C:\Program Files\Intuit\QuickBooks Web Connector\QBWebConnector.exe
```

---

## Step 3: Generate QWC File from POS

### 3.1 Login to Sitara POS Admin
1. Go to https://pos-demo.duckdns.org (or your POS URL)
2. Login with admin credentials
3. Navigate to: **Admin** → **Integrations** → **QuickBooks**

### 3.2 Setup Desktop Connection
1. Click **"Setup Desktop Connection"** button
2. Fill in connection details:
   - **Connection Name:** `My Restaurant - QB Desktop`
   - **Company Name:** Your QuickBooks company file name
   - **Username:** Choose a username (e.g., `pos_admin`)
   - **Password:** Create a strong password (save this!)
   - **QB Version:** Select your QB Desktop version
3. Click **"Save Connection"**

### 3.3 Download QWC File
1. After saving, click **"Download QWC File"** button
2. Save file as: `sitara-pos-qbwc.qwc`
3. **Important:** Keep the username and password - you'll need them!

---

## Step 4: Import QWC into QBWC Client

### 4.1 Add Application
1. Open **QuickBooks Web Connector** (QBWC.exe)
2. Click **"Add an Application"** button (or File → Add an Application)
3. Browse to your downloaded `sitara-pos-qbwc.qwc` file
4. Click **"Open"**

### 4.2 Grant Access
QBWC will prompt:
> "Do you want to allow this application to access your QuickBooks company?"

1. Click **"Yes, always"**
2. Choose certificate level: **"Yes, allow access"**
3. Select your QuickBooks company file from the dropdown
4. Click **"Continue"**

### 4.3 Enter Credentials
1. **Username:** Enter the username you created in Step 3.2
2. **Password:** Enter the password you created in Step 3.2
3. Check **"Save password"** (recommended)
4. Click **"OK"**

---

## Step 5: Open QuickBooks Desktop

**CRITICAL:** QuickBooks Desktop MUST be open for QBWC to work.

1. Open QuickBooks Desktop
2. Open your company file
3. Login as **Admin** or a user with **full permissions**
4. Keep QuickBooks Desktop **open in the background**

**Important Notes:**
- QBWC cannot connect if QB Desktop is closed
- Single-user mode works best for initial setup
- Multi-user mode is supported but may have delays

---

## Step 6: Configure QBWC Settings

### 6.1 Set Auto-Run
1. In QBWC, select your Sitara POS application
2. Click the **"Auto-Run"** checkbox
3. This enables automatic syncing every 15 minutes

### 6.2 Adjust Update Interval (Optional)
1. Click **"Edit"** next to your application
2. Change **"Every __ minute(s)"** dropdown
   - Minimum: 1 minute (for testing)
   - Default: 15 minutes (recommended for production)
   - Maximum: 60 minutes
3. Click **"Update"**

---

## Step 7: First Sync (Test)

### 7.1 Manual Sync
1. In QBWC, select your Sitara POS application
2. Click **"Update Selected"** button
3. Watch the status column:
   - **"Connecting..."** - Authenticating with POS server
   - **"Sending data..."** - Fetching QBXML from POS
   - **"Receiving data..."** - Sending QBXML to QB Desktop
   - **"Done"** - Sync completed successfully

### 7.2 Check Sync Log
1. Click **"View Last Error"** button (should show "No errors")
2. Click **"View Log"** to see detailed sync activity
3. Look for:
   ```
   Authenticated successfully
   Received request: SalesReceiptAddRq
   Sent response: Status OK
   ```

### 7.3 Verify in QB Desktop
1. Switch to QuickBooks Desktop
2. Go to: **Customers** → **Create Sales Receipts**
3. You should see new sales receipts from your POS orders
4. RefNumber will match POS order numbers (e.g., `240325-001`)

---

## Step 8: Create Test Order in POS

### 8.1 Create an Order
1. Go to POS: https://pos-demo.duckdns.org
2. Login as cashier/admin
3. Navigate to **Dine-In** or **Takeaway**
4. Add some items to cart
5. Complete the order and mark as **"Completed"**
6. Note the order number (e.g., `240325-005`)

### 8.2 Verify Queued for Sync
1. Login to POS admin panel
2. Go to: **Admin** → **Integrations** → **QuickBooks** → **Sync Queue**
3. You should see your order queued:
   - **Job Type:** `create_sales_receipt`
   - **Status:** `pending`
   - **Order Number:** `240325-005`

### 8.3 Wait for QBWC Poll
- QBWC will automatically fetch this job on next poll (every 15 min)
- OR trigger manual sync: Click **"Update Selected"** in QBWC

### 8.4 Verify in QB Desktop
1. After sync completes, switch to QB Desktop
2. Go to: **Customers** → **Sales Receipts**
3. Find the sales receipt with RefNumber `240325-005`
4. Verify:
   - Customer: Walk-In Customer (or customer name)
   - Items: Match your POS order
   - Amounts: Match your POS order
   - Tax: Calculated correctly

---

## Troubleshooting

### Error: "Could not connect to QuickBooks"
**Cause:** QuickBooks Desktop is not open

**Solution:**
1. Open QuickBooks Desktop
2. Open your company file
3. Keep it open in background
4. Try QBWC sync again

---

### Error: "Authentication failed"
**Cause:** Username/password mismatch

**Solution:**
1. In QBWC, right-click your application
2. Select **"Edit"**
3. Re-enter username and password from Step 3.2
4. Save and try again

---

### Error: "Certificate not valid"
**Cause:** SSL certificate issue

**Solution:**
1. Remove application from QBWC
2. Re-download QWC file from POS
3. Re-import QWC file
4. Accept certificate when prompted

---

### Error: "Company file not found"
**Cause:** QB Desktop company file path changed

**Solution:**
1. Ensure QB Desktop is open with correct company file
2. In QBWC, edit application settings
3. Verify company file path is correct

---

### Sync Queue Shows "Failed"
**Cause:** QBXML error (item not found, duplicate, etc.)

**Solution:**
1. In POS admin, go to Sync Queue
2. Click failed job to see error details
3. Common fixes:
   - **"Item not found"** → Create the menu item in QB Desktop first
   - **"Customer not found"** → Use "Walk-In Customer" or create customer
   - **"Duplicate RefNumber"** → Order already synced, check QB Desktop

---

## Best Practices

### Daily Operations
1. **Open QB Desktop FIRST** before starting POS operations
2. Keep QB Desktop **open all day** (minimize, don't close)
3. QBWC can run in background (system tray)
4. Check sync status at end of day

### Account Mapping
1. Setup account mappings in POS admin:
   - **Income Account:** Food Sales, Beverage Sales
   - **COGS Account:** Cost of Food, Cost of Beverages
   - **Tax Account:** FBR GST Payable, PRA PST Payable
   - **Deposit Account:** Cash Drawer, Bank Account
2. This ensures transactions post to correct accounts

### Menu Item Sync
1. **Best Practice:** Create menu items in QB Desktop FIRST
2. Then sync them to POS (future feature)
3. Ensures items have correct accounts assigned
4. Avoids "Item not found" errors

### Customer Management
1. Use **"Walk-In Customer"** for dine-in/takeaway orders
2. Create named customers in QB Desktop for call-center orders
3. Sync customer phone/email from POS to QB (future feature)

---

## Performance Tips

### Sync Frequency
- **Testing:** 1 minute (fast feedback)
- **Low Volume:** 15 minutes (default)
- **High Volume:** 5 minutes (real-time feel)
- **Overnight:** 60 minutes (reduce server load)

### QB Desktop Performance
- Close unnecessary QB windows (improves sync speed)
- Run QB Desktop in single-user mode during peak hours
- Multi-user mode works but adds ~2-3 seconds per request

### Network Issues
- QBWC requires stable internet to POS server
- If internet drops, sync will retry on next poll
- Jobs remain queued until successfully processed

---

## Security Notes

### Username & Password
- **NEVER share** your QBWC username/password
- Change password if compromised
- Each user should have their own QBWC account (future)

### Company File Access
- QBWC user needs **Admin** or **Full Access** permissions
- Cannot sync with restricted user accounts
- Review QB audit log periodically

### SSL/HTTPS
- All POS ↔ QBWC communication is encrypted (HTTPS)
- QB Desktop ↔ QBWC communication is local (no encryption needed)

---

## Support

### Need Help?
- **Email:** support@sitarainfotech.com
- **Phone:** [Your support number]
- **Hours:** 9 AM - 6 PM PKT (Mon-Fri)

### Escalation
For urgent issues:
1. Check QBWC log file: `C:\ProgramData\Intuit\QBWebConnector\Logs\`
2. Screenshot error message
3. Email to support with:
   - Error message
   - Order number
   - QBWC log file
   - QB Desktop version

---

## Appendix A: QBWC File Locations

### Windows 10/11
```
Program Files:     C:\Program Files\Intuit\QuickBooks Web Connector\
Logs:              C:\ProgramData\Intuit\QBWebConnector\Logs\
QWC Files:         C:\Users\[Username]\Documents\
QB Company Files:  C:\Users\Public\Documents\Intuit\QuickBooks\Company Files\
```

### QBWC Logs
```
QBWebConnectorLog.txt          - Main activity log
QBWebConnectorSOAPLog.txt      - SOAP request/response details
```

---

## Appendix B: QB Desktop Versions Supported

| Version | Supported | Notes |
|---------|-----------|-------|
| QB Enterprise 2024 | ✅ Yes | Recommended |
| QB Enterprise 2023 | ✅ Yes | |
| QB Premier 2024 | ✅ Yes | |
| QB Premier 2023 | ✅ Yes | |
| QB Pro 2024 | ✅ Yes | |
| QB Pro 2023 | ✅ Yes | |
| QB 2022 or older | ⚠️ Partial | May have compatibility issues |
| QB Mac | ❌ No | QBWC is Windows-only |
| QB Online | ✅ Yes | Use QB Online integration instead |

---

## Appendix C: QBXML Request Types

| POS Entity | QBXML Request | QB Desktop Entity |
|------------|---------------|-------------------|
| Order | SalesReceiptAddRq | Sales Receipt |
| Customer | CustomerAddRq / CustomerModRq | Customer |
| Menu Item | ItemNonInventoryAddRq | Item (NonInventory) |
| Payment | ReceivePaymentAddRq | Receive Payment |
| Refund | CreditMemoAddRq | Credit Memo |
| Ingredient | ItemInventoryAddRq | Item (Inventory) |
| Recipe | ItemInventoryAssemblyAddRq | Inventory Assembly |

---

**End of Guide**

For latest updates, visit: https://docs.sitarainfotech.com/qb-desktop
