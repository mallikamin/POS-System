# 🚀 BOM Module — Quick Reference Card

**Last Updated:** 2026-03-26

---

## 🔐 Login Credentials (Local Testing)

### YK Online (No BOM)
```
admin@ykonline.com    | PIN: 1111
cashier@ykonline.com  | PIN: 2222
```

### YK Desktop (With BOM)
```
admin@ykdesktop.com   | PIN: 3333
cashier@ykdesktop.com | PIN: 4444
youniskamran@ykdesktop.com | PIN: 9999
```

---

## 🛠️ Quick Start Commands

```bash
# Fresh setup (wipes database!)
docker compose down -v
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed_multi_tenant_bom

# Check logs
docker compose logs -f backend
docker compose logs -f frontend

# Access URLs
http://localhost:8090/login        # POS login
http://localhost:8090/admin/ingredients  # Ingredient mgmt
http://localhost:8090/admin/recipes      # Recipe builder
```

---

## 📍 BOM Module URLs

| Page | URL | Purpose |
|------|-----|---------|
| **Ingredients** | `/admin/ingredients` | Manage raw materials, costs, stock |
| **Recipes** | `/admin/recipes` | Build recipes, calculate food cost % |

---

## 🍽️ Sample Data (Auto-Seeded)

### 19 Ingredients
- **Proteins:** Chicken (bone-in/boneless), Mutton, Beef
- **Grains:** Basmati Rice, Wheat Flour
- **Dairy:** Yogurt, Ghee
- **Vegetables:** Onions, Tomatoes, Ginger, Garlic, Green Chilies
- **Spices:** Biryani, Karahi, Nihari, BBQ Masala, Salt
- **Oil:** Cooking Oil

### 6 Recipes
1. Chicken Biryani → **55.7%** food cost (⚠️ high)
2. Mutton Karahi → **109%** food cost (🔴 loss)
3. Chicken Tikka → **113%** food cost (🔴 loss)
4. Seekh Kebab → **118%** food cost (🔴 loss)
5. Nihari → **137%** food cost (🔴 massive loss)
6. Chicken Karahi → **100%** food cost (🔴 break-even)

> **KEY INSIGHT:** 5 out of 6 dishes are underpriced!

---

## 🎨 Food Cost % Color Guide

| Range | Color | Status | Action |
|-------|-------|--------|--------|
| **<25%** | 🟢 Green | Excellent | Maintain |
| **25-35%** | 🟡 Yellow | Acceptable | Monitor |
| **>35%** | 🔴 Red | High | Increase price or reduce portions |

**Industry Standard:** 25-35% for full-service restaurants

---

## 📧 Quick Email to Younis Team

**Subject:** Need 3-5 Menu Items for Recipe Demo

**Body:**
```
Hi Younis,

For Tuesday's demo, can you share:

For 3-5 dishes:
1. Name + Price (e.g., Chicken Biryani - Rs. 850)
2. Ingredients + Quantities (e.g., 0.5kg chicken @ Rs. 650/kg)
3. Yield servings (e.g., 1 plate)

Example:
Chicken Biryani (Rs. 850)
- 0.5 kg chicken @ Rs. 650/kg
- 0.25 kg rice @ Rs. 180/kg
- 0.08 L oil @ Rs. 420/L

We'll calculate their actual food cost % and show them
if they're profitable or losing money.

Thanks!
```

---

## 🐛 Troubleshooting

### BOM Links Not Visible
- ✅ Check: Logged in as `admin@ykdesktop.com`?
- ✅ Check: Seed ran successfully?
- ✅ Clear browser cache

### Cost Not Calculating
- ✅ Check: Ingredients have `cost_per_unit` > 0?
- ✅ Check: Recipe items linked to valid ingredients?

### Seed Script Fails
```bash
# Check logs
docker compose exec backend python -m app.scripts.seed_multi_tenant_bom

# If error, drop DB and retry
docker compose down -v
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed_multi_tenant_bom
```

---

## 📊 Demo Talking Points

**Problem:**
"Most restaurants fail because they don't know their actual costs. They think Rs. 850 biryani is profitable, but the data shows it costs Rs. 480 to make — only Rs. 370 profit before overhead!"

**Solution:**
"Our system calculates exact food cost % for every dish. Once you see the numbers, pricing decisions become obvious."

**Proof:**
"Look at this sample data — 5 out of 6 dishes are losing money. This is real market prices from Lahore. Imagine what your clients will discover about their menu!"

---

## ✅ Pre-Demo Checklist

- [ ] Run seed script successfully
- [ ] Test login for both tenants
- [ ] Verify 19 ingredients visible
- [ ] Open at least 3 recipes
- [ ] Edit one recipe → verify cost recalculates
- [ ] Save recipe → verify "Version 2" toast
- [ ] Practice demo flow (10 min)
- [ ] Prepare talking points
- [ ] Have sample data request email ready

---

## 🔗 Key Documents

| File | Purpose |
|------|---------|
| `PHASE3_COMPLETE_SUMMARY.md` | Full implementation details |
| `docs/TWO_TENANT_BOM_SETUP.md` | Setup guide + architecture |
| `BOM_IMPLEMENTATION_STATUS.md` | Technical status doc |
| `QUICK_REFERENCE_BOM.md` | This file |

---

**Print this card and keep it handy for Tuesday's demo!** 🎯
