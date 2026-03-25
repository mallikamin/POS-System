# QuickBooks Online - Company Not Appearing in OAuth Popup

**Issue**: When clicking "Connect to QuickBooks", only sandbox company shows up. Younis Kamran's company is missing.

## Date: 2026-03-25
**Status**: Under investigation

---

## Possible Causes

### 1. Wrong Intuit Account (MOST LIKELY)
- You're logged into your personal/sandbox Intuit account
- Younis team invited a **different email address**
- That email must be logged in for the company to appear

### 2. Access Revoked by Younis Team
- They may have removed you as a user from their QB company
- Or the app authorization was revoked

### 3. Invitation Expired
- Intuit invitations can expire if not accepted within a timeframe
- Needs to be re-sent

---

## Troubleshooting Steps

### ✅ Step 1: Check Which Intuit Account You're Using

1. Go to: https://pos-demo.duckdns.org
2. Admin → QuickBooks
3. Click "Connect to QuickBooks"
4. **In the OAuth popup**, look at the **top-right corner**
5. **What email address is shown?**

**Expected**: The email that Younis team invited (ask them which email they used)

**If wrong email**:
- Click "Sign in with a different account"
- Use the correct email
- You should then see Younis company in the list

---

### ✅ Step 2: Verify You Have Access to Younis QB Company

**Outside of our app**, log into QuickBooks Online directly:

1. Go to: https://qbo.intuit.com
2. Log in with the email Younis team invited
3. **Can you see their company in your company list?**
   - ✅ YES → Proceed to Step 3
   - ❌ NO → You don't have access (ask Younis to re-invite you)

---

### ✅ Step 3: Check If App Is Authorized

1. While logged into Younis QB company (https://qbo.intuit.com)
2. Click **Settings (⚙️)** → **Manage Your Apps**
3. Look for our app: **"Sitara Infotech POS"** (or whatever name was used in Intuit developer portal)

**Expected states**:
- ✅ **App is listed** → Good, proceed to Step 4
- ❌ **App is NOT listed** → Authorization was revoked, needs re-authorization
- ❓ **App is listed but shows "Disconnected"** → Re-authorize needed

---

### ✅ Step 4: Ask Younis Team to Verify

Contact Mr. Younis Kamran and confirm:

1. **Which email did they invite?** (must match what you're using)
2. **Is the invitation still active?** (not expired)
3. **Can they see you listed as a user** in their QB company?
   - Settings → Manage Users → [Your Email] should be there
4. **Did they authorize the app?** (Admin must approve app connections)

---

## Quick Fix: Force Re-Authorization

If you have access to Younis company but app isn't showing:

### Option A: Re-invite via Intuit App Center
1. Younis team goes to: https://appcenter.intuit.com
2. Search for our app (if published)
3. Click "Connect" → Select their company → Authorize
4. This forces re-authorization

### Option B: Manual App Authorization (if app is private/dev)
Since our app is likely in **development mode**, Younis team needs to:
1. Log into their Intuit Developer account
2. Go to: https://developer.intuit.com/app/developer/dashboard
3. Find our app (they should be added as a "test user" or "authorized user")
4. If not, we need to **add their Intuit account as a test user** in our app settings

---

## Next Steps (based on what you find)

| What You Find | Action |
|---------------|--------|
| Wrong email in OAuth popup | Log in with correct Intuit account |
| Can't see Younis company in QBO directly | Ask Younis to re-invite you as user |
| App not in "Manage Your Apps" | Ask Younis to authorize app OR we add them as test user |
| Still stuck | Check with Younis: which email, is invite active, are they admin |

---

## Developer Notes (for us)

### Our QB App Details
- **Client ID**: [in `.env.demo` on server]
- **Redirect URI**: `https://pos-demo.duckdns.org/api/v1/quickbooks/callback`
- **Environment**: Sandbox (during dev) → Production (once approved)
- **Scope**: `com.intuit.quickbooks.accounting`

### How Intuit OAuth Works
1. User clicks "Connect" → we generate auth URL with state token
2. User logs into Intuit → sees list of **companies their account has access to**
3. User selects company → Intuit sends us: `code`, `state`, `realmId`
4. We exchange code for tokens → store in DB with `realmId`

**Critical**: The Intuit account must:
- Have user access to the target QB company
- Have authorized our app (either via App Center or as dev test user)

---

## Log This Investigation

**Date**: 2026-03-25
**Reporter**: Malik
**Issue**: Younis Kamran QB company not appearing in OAuth popup
**Current Status**: Awaiting user to verify Intuit account email + QB access
**Next Meeting**: Tuesday (demo QB Online to Younis team)
**Urgency**: HIGH (need this working before Tuesday demo)

---

## Resolution (to be filled once fixed)

**Root Cause**: [TBD]
**Fix Applied**: [TBD]
**Verified By**: [TBD]
**Date Resolved**: [TBD]
