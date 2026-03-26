# Two-Tenant Setup with BOM Module

**Created:** 2026-03-26
**Purpose:** Run two restaurants on one POS system (QB Online + QB Desktop with BOM)

---

## 🎯 Overview

Your POS system now supports **two separate restaurants**:

1. **YK Online Restaurant** — Uses QuickBooks Online for simple sales tracking
2. **YK Desktop Restaurant** — Uses QuickBooks Desktop + BOM (Bill of Materials) for recipe costing

**Same website, different logins** — think of it like Gmail accounts.

---

## 📊 What's the Difference?

| Feature | YK Online Restaurant | YK Desktop Restaurant |
|---------|---------------------|----------------------|
| **QuickBooks** | Online (simple bookkeeping) | Desktop (full accounting) |
| **BOM Module** | ❌ Hidden | ✅ Visible |
| **Recipe Costing** | ❌ Not available | ✅ Full recipe builder |
| **Inventory Assemblies** | ❌ Not supported | ✅ Syncs to QB Desktop |
| **Use Case** | Client needs simple sales tracking | Client needs recipe costing + inventory |

---

## 🔐 Login Credentials

### YK Online Restaurant

```
Admin Login:
  Email: admin@ykonline.com
  Password: admin123
  PIN: 1111

Cashier Login:
  Email: cashier@ykonline.com
  Password: cashier123
  PIN: 2222
```

### YK Desktop Restaurant (with BOM)

```
Admin Login:
  Email: admin@ykdesktop.com
  Password: admin123
  PIN: 3333

Cashier Login:
  Email: cashier@ykdesktop.com
  Password: cashier123
  PIN: 4444

Younis Kamran (VIP):
  Email: youniskamran@ykdesktop.com
  Password: yk123
  PIN: 9999
```

---

## 🍽️ Sample BOM Data (YK Desktop Only)

### 19 Ingredients Seeded

**Proteins:**
- Chicken (with bone) — Rs. 650/kg
- Chicken (boneless) — Rs. 950/kg
- Mutton — Rs. 1,800/kg
- Beef (boneless) — Rs. 1,200/kg

**Grains:**
- Basmati Rice (Super Kernel) — Rs. 180/kg
- Wheat Flour — Rs. 80/kg

**Dairy:**
- Yogurt — Rs. 220/kg
- Ghee (Pure Desi) — Rs. 1,400/kg

**Oils & Fats:**
- Cooking Oil — Rs. 420/L

**Vegetables:**
- Onions — Rs. 80/kg
- Tomatoes — Rs. 100/kg
- Ginger — Rs. 500/kg
- Garlic — Rs. 350/kg
- Green Chilies — Rs. 200/kg

**Spices:**
- Biryani Masala — Rs. 800/kg
- Karahi Masala — Rs. 750/kg
- Nihari Masala — Rs. 900/kg
- BBQ Masala — Rs. 850/kg
- Salt — Rs. 50/kg

### 6 Recipes Seeded

All recipes include:
- Ingredient quantities
- Waste factors (e.g., 10% for chicken bones, 15% for onion peeling)
- Cooking instructions
- Real-time cost calculations
- Food cost % (vs menu price)

**Recipes:**

1. **Chicken Biryani** (Rs. 350/plate)
   - Cost per serving: ~Rs. 195
   - Food cost %: ~55.7% ⚠️ (high, consider price increase)

2. **Mutton Karahi** (Rs. 1,800/full)
   - Cost per serving: ~Rs. 1,975
   - Food cost %: ~109% 🔴 (CRITICAL — price way too low!)

3. **Chicken Tikka** (Rs. 650)
   - Cost per serving: ~Rs. 735
   - Food cost %: ~113% 🔴 (CRITICAL — losing money!)

4. **Seekh Kebab** (Rs. 550)
   - Cost per serving: ~Rs. 650
   - Food cost %: ~118% 🔴 (CRITICAL)

5. **Nihari** (Rs. 900/full)
   - Cost per serving: ~Rs. 1,240
   - Food cost %: ~137% 🔴 (MASSIVE LOSS)

6. **Chicken Karahi** (Rs. 1,300/full)
   - Cost per serving: ~Rs. 1,305
   - Food cost %: ~100% 🔴 (break-even, no profit!)

> **🚨 INSIGHT:** Most dishes are underpriced! Ideal food cost % = 25-35%. This is why recipe costing is critical!

---

## 🚀 How to Run the Seed

### Option 1: Fresh Database (Recommended for Testing)

```bash
# 1. Drop existing database (WARNING: deletes all data!)
docker compose down -v

# 2. Start containers
docker compose up -d

# 3. Run migrations
docker compose exec backend alembic upgrade head

# 4. Run two-tenant seed with BOM
docker compose exec backend python -m app.scripts.seed_multi_tenant_bom
```

### Option 2: Add to Existing Database

```bash
# Run seed (idempotent — skips existing data)
docker compose exec backend python -m app.scripts.seed_multi_tenant_bom
```

---

## 🧪 How to Test

### Test YK Online (No BOM)

1. Login: `admin@ykonline.com` / PIN `1111`
2. Navigate to `/admin` sidebar
3. **BOM links should NOT appear** (Ingredients, Recipes)
4. Only basic admin features visible

### Test YK Desktop (With BOM)

1. Login: `admin@ykdesktop.com` / PIN `3333`
2. Navigate to `/admin/ingredients`
   - Should see 19 ingredients with stock levels
   - Try creating a new ingredient (e.g., "Coriander")
   - Test edit, delete (soft delete)
3. Navigate to `/admin/recipes`
   - Select "Chicken Biryani" from left panel
   - Right panel shows recipe with 10 ingredients
   - Food cost % badge should show ~55.7% (yellow/red)
   - Try adding/removing ingredients → cost recalculates
   - Click Save → creates Version 2
4. Test other recipes — notice most are unprofitable (red badges)

---

## 📧 What to Ask Younis Kamran Team

Use this template:

---

**Subject:** Sample Restaurant Data Needed for Recipe Builder Testing

Hi Younis,

We've completed the **Recipe Builder** module with realistic Pakistani restaurant data for testing. However, to demo it with **your actual client's menu**, could you share the following for **one restaurant**?

**We only need 3-5 menu items** to create a realistic demo.

### What We Need:

**1. Menu Items (3-5 dishes)**
- Name (e.g., "Chicken Biryani", "Mutton Karahi")
- Selling price (e.g., Rs. 850)
- Category (e.g., "Main Course", "BBQ")

**2. Ingredients**
- Name (e.g., "Chicken (with bone)", "Basmati Rice")
- Unit (e.g., "kg", "L")
- Cost per unit (e.g., Rs. 650/kg)
- Supplier name (optional)

**3. Recipes**
- Which ingredients each dish uses
- How much of each (e.g., "0.5 kg chicken, 0.25 kg rice")
- Yield servings (e.g., "1 plate")
- Waste % if known (e.g., "10% for bones") — if unknown, we'll use 0%

### Example for 1 Dish:

**Chicken Biryani** (Rs. 850/plate)

Ingredients:
1. Chicken (with bone) — 0.5 kg @ Rs. 650/kg (10% waste)
2. Basmati Rice — 0.25 kg @ Rs. 180/kg (5% waste)
3. Cooking Oil — 0.08 L @ Rs. 420/L
4. Onions — 0.15 kg @ Rs. 80/kg (15% waste)
5. Biryani Spice Mix — 0.03 kg @ Rs. 800/kg

**System Will Show:**
- Total ingredient cost: ~Rs. 420/plate
- Food cost %: **49%** (high! might need price increase or portion reduction)

---

**Why This Helps:**
- We enter real data into the system
- Demo shows actual costs (not fake numbers)
- You see if food cost % matches your expectations
- Makes the Tuesday demo more impactful

**Timeline:** If you can share 3-5 dishes by **Monday**, we'll have the demo ready for Tuesday.

If you don't have exact data, rough estimates work fine!

Thanks,
[Your Name]

---

---

## 🎨 Demo Flow for Tuesday Meeting

1. **Show Login Screen**
   - "Two restaurants, same system"
   - Login as `admin@ykdesktop.com` (PIN 3333)

2. **Navigate to Ingredients**
   - "19 ingredients with real Pakistani market prices"
   - Show low stock indicator (red badge)
   - Demo create new ingredient

3. **Navigate to Recipes**
   - Select "Chicken Biryani"
   - "System auto-calculates food cost %"
   - Point out: **55.7% is TOO HIGH** (should be <35%)
   - Show other dishes: Most are **LOSING MONEY**
   - "This is why recipe costing matters!"

4. **Add New Recipe (Live)**
   - Select a menu item without recipe
   - Add 3-4 ingredients
   - Show real-time cost calculation
   - Save → creates Version 1

5. **Edit Recipe → Versioning**
   - Change ingredient quantity
   - Save → creates Version 2
   - "Old version preserved for cost history"

6. **QuickBooks Integration (Next Step)**
   - "Once recipes are finalized, we sync to QB Desktop as Inventory Assemblies"
   - "Every sale auto-deducts ingredients from stock"

---

## 🔧 Technical Notes

### How Multi-Tenancy Works

- Both tenants share same database
- `tenant_id` column isolates data
- Login determines which tenant you see
- Zero cross-contamination

### Frontend Changes Needed (Optional)

To show tenant name in navbar:

```typescript
// In POSLayout.tsx or AdminLayout.tsx
const tenantName = authStore.user?.tenant_name;
// Display in header: "YK Desktop Restaurant"
```

### Navigation Sidebar (Next Step)

Add links to admin sidebar:

```typescript
{authStore.user?.tenant_slug === 'yk-desktop' && (
  <>
    <NavLink to="/admin/ingredients">Ingredients</NavLink>
    <NavLink to="/admin/recipes">Recipe Builder</NavLink>
  </>
)}
```

---

## 📝 Summary

✅ **Two-Tenant Setup:** YK Online (QB Online) + YK Desktop (QB Desktop + BOM)
✅ **BOM Sample Data:** 19 ingredients + 6 recipes with realistic costs
✅ **Login Credentials:** Different emails/PINs for each tenant
✅ **Demo Ready:** Show Younis team on Tuesday
✅ **Next Step:** Get real client data to replace sample recipes

**Key Selling Point:** _"Most restaurants lose money because they don't know their actual food costs. Your system calculates this automatically."_
