# QB Template Demo Plan — All 41 Templates

## How Each Demo Works
For each template:
1. **Clear** old POS mappings (keeps QB accounts, cleans slate for new template)
2. **Apply** new template → creates QB accounts + POS mappings
3. **Validate** mappings (must show `is_valid: true`)
4. **Create** test order(s) via API with relevant menu items
5. **Sync** order to QB → SalesReceipt created
6. **Verify** SalesReceipt in QB (items, tax, income account, customer)
7. **User screen-records** QB showing the receipt
8. **User confirms** → proceed to next

## Scenarios Per Template
- **Scenario A**: Completed Dine-In (cash) → SalesReceipt
- **Scenario B**: Completed Takeaway (card, discount applied) → SalesReceipt
- **Scenario C** (select templates): Multi-category order → per-category income routing

---

## GROUP 1: Pakistani Restaurants (6 templates)
Most relevant to client — 3 scenarios each.

| # | Template Key | Name | Mappings | Scenarios |
|---|-------------|------|----------|-----------|
| 1 | `pakistani_restaurant` | Pakistani Restaurant (Full-Service) | 31 | A, B, C |
| 2 | `pakistani_bbq_specialist` | Pakistani BBQ Specialist | ~25 | A, B, C |
| 3 | `biryani_house` | Biryani House | ~25 | A, B, C |
| 4 | `pakistani_street_food` | Pakistani Street Food | ~25 | A, B |
| 5 | `nihari_paye_house` | Nihari & Paye House | ~25 | A, B |
| 6 | `pakistani_sweets_bakery` | Pakistani Sweets & Bakery | ~25 | A, B |

## GROUP 2: Regional Pakistani (2 templates)

| # | Template Key | Name | Mappings | Scenarios |
|---|-------------|------|----------|-----------|
| 7 | `karachi_seafood` | Karachi Seafood | ~25 | A, B |
| 8 | `lahore_food_street` | Lahore Food Street | ~25 | A, B |

## GROUP 3: International Cuisine (6 templates)

| # | Template Key | Name | Mappings | Scenarios |
|---|-------------|------|----------|-----------|
| 9 | `international_restaurant` | International Restaurant | ~25 | A, B |
| 10 | `chinese_restaurant` | Chinese Restaurant | ~25 | A, B |
| 11 | `japanese_sushi` | Japanese Sushi | ~25 | A, B |
| 12 | `thai_restaurant` | Thai Restaurant | ~25 | A, B |
| 13 | `italian_restaurant` | Italian Restaurant | ~25 | A, B |
| 14 | `steakhouse` | Steakhouse | ~25 | A, B |

## GROUP 4: Fast Food / QSR (4 templates)

| # | Template Key | Name | Mappings | Scenarios |
|---|-------------|------|----------|-----------|
| 15 | `qsr` | Quick Service Restaurant | ~25 | A, B |
| 16 | `burger_joint` | Burger Joint | ~25 | A, B |
| 17 | `pizza_chain` | Pizza Chain | ~25 | A, B |
| 18 | `fried_chicken_chain` | Fried Chicken Chain | ~25 | A, B |

## GROUP 5: Cafe & Casual (6 templates)

| # | Template Key | Name | Mappings | Scenarios |
|---|-------------|------|----------|-----------|
| 19 | `cafe` | Cafe | ~25 | A, B |
| 20 | `fine_dining` | Fine Dining | ~25 | A, B |
| 21 | `buffet_restaurant` | Buffet Restaurant | ~25 | A, B |
| 22 | `food_court_vendor` | Food Court Vendor | ~25 | A, B |
| 23 | `food_truck` | Food Truck | ~25 | A, B |
| 24 | `breakfast_spot` | Breakfast Spot | ~25 | A, B |

## GROUP 6: Specialty (6 templates)

| # | Template Key | Name | Mappings | Scenarios |
|---|-------------|------|----------|-----------|
| 25 | `juice_bar` | Juice Bar | ~25 | A, B |
| 26 | `ice_cream_parlor` | Ice Cream Parlor | ~25 | A, B |
| 27 | `dessert_parlor` | Dessert Parlor | ~25 | A, B |
| 28 | `tea_house` | Tea House | ~25 | A, B |
| 29 | `shawarma_wrap_shop` | Shawarma & Wrap Shop | ~25 | A, B |
| 30 | `bakery_wholesale` | Bakery Wholesale | ~25 | A, B |

## GROUP 7: Special Operations (5 templates)

| # | Template Key | Name | Mappings | Scenarios |
|---|-------------|------|----------|-----------|
| 31 | `cloud_kitchen` | Cloud Kitchen | ~25 | A, B |
| 32 | `catering_company` | Catering Company | ~25 | A, B |
| 33 | `hotel_restaurant` | Hotel Restaurant | ~25 | A, B |
| 34 | `bar_lounge` | Bar & Lounge | ~25 | A, B |
| 35 | `resort_restaurant` | Resort Restaurant | ~25 | A, B |

## GROUP 8: Multi-Location (4 templates)

| # | Template Key | Name | Mappings | Scenarios |
|---|-------------|------|----------|-----------|
| 36 | `multi_branch_chain` | Multi-Branch Chain | ~35 | A, B, C |
| 37 | `franchise_operation` | Franchise Operation | ~30 | A, B |
| 38 | `multi_brand_operator` | Multi-Brand Operator | ~35 | A, B |
| 39 | `multi_franchise_pakistani` | Multi-Franchise Pakistani | 62 | A, B, C |

## GROUP 9: Niche Models (2 templates)

| # | Template Key | Name | Mappings | Scenarios |
|---|-------------|------|----------|-----------|
| 40 | `subscription_meal_service` | Subscription Meal Service | ~30 | A, B |
| 41 | `marketplace_heavy` | Marketplace Heavy | ~30 | A, B |

---

## Progress Tracker

| # | Template | Scenario A | Scenario B | Scenario C | Notes |
|---|----------|-----------|-----------|-----------|-------|
| 1 | pakistani_restaurant | | | | |
| 2 | pakistani_bbq_specialist | | | | |
| 3 | biryani_house | | | | |
| 4 | pakistani_street_food | | | | |
| 5 | nihari_paye_house | | | | |
| 6 | pakistani_sweets_bakery | | | | |
| 7 | karachi_seafood | | | | |
| 8 | lahore_food_street | | | | |
| 9 | international_restaurant | | | | |
| 10 | chinese_restaurant | | | | |
| 11 | japanese_sushi | | | | |
| 12 | thai_restaurant | | | | |
| 13 | italian_restaurant | | | | |
| 14 | steakhouse | | | | |
| 15 | qsr | | | | |
| 16 | burger_joint | | | | |
| 17 | pizza_chain | | | | |
| 18 | fried_chicken_chain | | | | |
| 19 | cafe | | | | |
| 20 | fine_dining | | | | |
| 21 | buffet_restaurant | | | | |
| 22 | food_court_vendor | | | | |
| 23 | food_truck | | | | |
| 24 | breakfast_spot | | | | |
| 25 | juice_bar | | | | |
| 26 | ice_cream_parlor | | | | |
| 27 | dessert_parlor | | | | |
| 28 | tea_house | | | | |
| 29 | shawarma_wrap_shop | | | | |
| 30 | bakery_wholesale | | | | |
| 31 | cloud_kitchen | | | | |
| 32 | catering_company | | | | |
| 33 | hotel_restaurant | | | | |
| 34 | bar_lounge | | | | |
| 35 | resort_restaurant | | | | |
| 36 | multi_branch_chain | | | | |
| 37 | franchise_operation | | | | |
| 38 | multi_brand_operator | | | | |
| 39 | multi_franchise_pakistani | | | | |
| 40 | subscription_meal_service | | | | |
| 41 | marketplace_heavy | | | | |

## Total Estimated: ~92 scenarios (41×2 base + 10 extra Scenario C)
