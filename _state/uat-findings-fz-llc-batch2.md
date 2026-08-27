# UAT findings — FZ LLC (martin-fz), batch 2

Batch 1 was findings 1-9, fixed and deployed in `f3c6759` on 2026-08-27.
This file is batch 2: everything found from exercise 5 onward, run on production
(`https://eats.sitaratech.info`) as Martin Zubeldia (admin).

Status key: OPEN = not started · FIXED = in a commit · DEPLOYED = live and verified.

---

## F10 — Admin sidebar is not collapsible
**Where:** every `/admin/*` page. Observed on `/admin/recipes`.
**What:** the left nav is a fixed-width column that is always expanded. On a 1920px
window it eats roughly 300px permanently; on a tablet in landscape it is a much larger
share. The Recipe Builder in particular is a three-column screen (nav / ingredient list /
editor) and the editor is the one that needs the room.
**Wanted:** a collapse/minimise toggle that shrinks the nav to an icon rail, with the
choice remembered per device.
**Nature:** UX / screen real estate. Not a correctness bug.
**Status:** OPEN

## F11 — Recipe Builder ingredient list has no search
**Where:** `/admin/recipes`, the **Ingredients** column.
**What:** the only filter is the "All Ingredient Categories" dropdown. The list is a
scrolling column, so finding a specific ingredient means scrolling it. With a real
bakery's ingredient count this does not scale.
**Wanted:** a search box above the list. Typing `Cro` should narrow it to
**Croissant Dough**. Substring match, case-insensitive, matching on ingredient name.
**Nature:** UX / missing control on a screen the client will use daily.
**Status:** OPEN

## F12 — "Restaurant" slug field is visible on a first-time device
**Where:** `/login` in a clean browser profile (incognito), no `?shop=` on the URL.
**What:** the login screen shows a **Restaurant** text field with placeholder
`e.g. chick-shack` and helper text "Leave blank if this server only hosts one restaurant."
A real client should never be asked to type our internal tenant slug, and the placeholder
names a *different* client.
**Verified in code** (`frontend/src/pages/auth/LoginPage.tsx:42-43`): the field only
renders when the device has no remembered slug (`showShop = !getTenantSlug()`). Once
signed in it collapses to "Signing in to `<slug>` — change restaurant". Martin is sent a
`/login?shop=martin-fz` link, so in the intended flow he never types it. So this is
**cosmetic exposure on a cold device, not a broken flow.**
**Wanted (to decide):** at minimum, drop the `e.g. chick-shack` placeholder — it leaks
another client's name. Better: hide the field entirely unless the URL or a `?switch`
route asks for it.
**Nature:** UX / client-facing polish, plus a small cross-client information leak in the
placeholder text.
**Status:** OPEN

---

## Exercise log

| Ex | Subject | Result |
|----|---------|--------|
| 1-4 | sign-in, locations, per-site stock, manual adjustment | done 2026-08-27, 9 findings, all fixed in `f3c6759` |
| 5 | recipes, sub-recipes, cost roll-up | in progress |

### Exercise 5 observations (running)
- Croissant Dough is present and correctly badged **Sub-recipe**, AED **10.19 per kg**.
- Yield **5.00 kg** per batch, prep 40 min, cook time blank. Matches the playbook.
- Ingredient lines read correctly: Flour 2.500 kg @ **2.00% waste** = AED 8.92,
  Butter 1.200 = 33.60, Yeast 0.050 = 2.25, Salt 0.040 = 0.06, Sugar 0.150 = 0.60.
  Milk below the fold.
- The waste % is per **ingredient line**, which is the thing the playbook explicitly asks
  Martin to challenge (he may want it per batch).

## F13 — Food Cost % is calculated against the VAT-inclusive selling price
**Where:** `/admin/recipes`, the cost summary panel on any **menu item** recipe.
Observed on **Butter Croissant**.
**What:** the screen reports Food Cost **13.58%** for a cost per serving of AED 1.22
against a menu price of AED 9.00. That divides by the shelf price, which for this tenant
**includes 5% VAT**. VAT is not FZ LLC's revenue - it is collected on behalf of the FTA.
**Verified in code, not inferred:**
- `frontend/src/pages/admin/RecipeBuilderPage.tsx:308-311` -
  `foodCostPct = (costPerServing / selectedMenuItem.price) * 100`. No VAT extraction.
- `backend/app/scripts/seed_fz_llc.py:345-346` - `tax_inclusive=True`,
  `default_tax_rate=500` (5%). So AED 9.00 = AED 8.5714 net + AED 0.4286 VAT.
- `backend/app/models/restaurant_config.py:35` - `tax_inclusive` defaults to `True`, so
  this affects every tax-inclusive tenant, not only this one.
**Correct figure:** 1.2228 / 8.5714 = **14.26%**. Reported: 13.58%. The screen understates
food cost by ~0.7 points absolute, ~5% relative, on every costed item.
**Why it matters here specifically:** per-channel net profitability is one of the four
things Martin actually asked for. A costing screen that quietly counts the tax authority's
money as revenue is the wrong foundation for it. The error scales with the VAT rate, so it
is small at 5% and would be large for a UK tenant at 20%.
**Fix:** divide by the net price when `tax_inclusive` is true -
`price / (1 + default_tax_rate/10000)`. Needs `tax_inclusive` and `default_tax_rate` on the
config the page already loads. Label the line "Food Cost % (of net revenue)" so the basis
is stated rather than assumed.
**Nature:** 🔴 correctness. Wrong number presented confidently to a client.
**Status:** OPEN

## F14 — 🔴 `/admin/ingredients` crashes to a white error screen
**Where:** `/admin/ingredients` as Martin (admin) on production.
**What:** the page does not degrade, it dies:
`Something went wrong — t.current_stock.toFixed is not a function`. The whole
Ingredients module is unreachable, which also blocks Exercise 5's last instruction
("change the price of Flour and watch the dough cost move").
**Root cause, verified in code:**
- `backend/app/schemas/inventory.py:50` declared `current_stock: Decimal`. **Pydantic v2
  serialises `Decimal` to a JSON string**, so the API sent `"12.500"`, not `12.5`.
- `frontend/src/types/inventory.ts:22` declares it `number`, and
  `frontend/src/pages/admin/IngredientManagementPage.tsx:369` calls `.toFixed(2)` on it.
  A string has no `.toFixed`, so React unmounted the tree.
**This was a class of bug, not one line.** The same mismatch sat under `reorder_point`
(next line, would have thrown immediately after), and under **39 Decimal fields** in that
schema module: every recipe cost, every variance figure, `shortage`, `balance_after`,
`food_cost_percentage`. Several call sites survived only because JS coerces strings in
`*`, `/` and `>` - working by accident, one `.toFixed` away from the same crash.
**Fix applied (local):** a `Num` annotated type in `backend/app/schemas/inventory.py`
(`Annotated[Decimal, PlainSerializer(float, when_used="json")]`) applied to all 39
annotations. It changes the **outbound representation only** - validation still runs
through `Decimal`, so request precision and the `ge=0`/`gt=0` constraints are untouched,
and no money is computed in float on the server.
**Proved, not assumed** - run inside the running backend container:
`cost_per_unit=350.0 (float)`, `current_stock=12.5 (float)`, `reorder_point=4.167 (float)`;
inbound `"350.55"` still arrives as `Decimal('350.55')`; a negative cost is still rejected.
**Status:** FIXED LOCALLY - not yet on production. Martin's URL still crashes until deployed.

---

## Amendment to F13 — VAT must be Martin's to change, not ours
Malik's instruction: *"be flexible about VAT so it can be easily changed altered by Martin."*
So F13's fix is **not** to hardcode 5%. Requirements:
1. The Food Cost % divisor reads `default_tax_rate` from the tenant's own
   `restaurant_configs` row - already a per-tenant column
   (`backend/app/models/restaurant_config.py`), so no schema change.
2. `tax_inclusive` likewise drives *whether* VAT is stripped at all. A tenant priced
   exclusive of tax must not have anything removed.
3. Both must be **editable by Martin himself** in Admin → Settings, not a value we set in
   a seed script. If the FTA changes the rate, or he opens in a jurisdiction that is not
   5%, that is a settings change and not a support ticket.
4. The label states the basis - "Food Cost % (of net revenue)" - so the number is never
   ambiguous on a screen he shows an accountant.

## F15 — 🔴 Admin pages never load the tenant config, so a UAE client sees Pakistani rupees
**Where:** any `/admin/*` page reached without passing through the POS layout - a deep
link, a hard refresh, a bookmark, a second tab. Observed on `/admin/stock`: the
**Cost per unit** column read **"Rs. 28", "Rs. 14", "Rs. 10", "Rs. 4"** for a tenant whose
currency is AED.
**Ruled out first, rather than assumed:** the stored data is correct. Settings shows
Currency **AED**, tax 5%, tax-inclusive on, Asia/Dubai; `seed_fz_llc.py:343` seeds
`currency="AED"`; `tenant.py:32` returns `currency` in the config response; and the local
source for `StockPage.tsx` and `currency.ts` is identical to HEAD, so production runs this
exact code. The value was right the whole way to the browser.
**Root cause:** `fetchConfig()` was called by **`POSLayout` only**. `AdminLayout` never
called it. `setActiveCurrency()` runs *inside* `fetchConfig`, so on an admin-only entry the
currency module stayed on its module-level default `"PKR"` (`currency.ts:51`). Because
`activeCode` is a plain module global and not React state, nothing re-renders it back to
the truth afterwards - the wrong currency sticks for the life of the page.
**The tell that this was known and never fixed properly:** three pages had already patched
around it individually - `OnlineOrdersPage:489`, `OnlineReportsPage:95`, `ZReportPage:89` -
each carrying its own comment about deep links skipping POSLayout's `fetchConfig`. The
workaround was written three times; the layout was never fixed once.
**Why it mattered now:** the demo video involves refreshing and deep-linking admin screens.
Any one of those would have put "Rs." in front of a UAE client's costs on camera.
**Fix applied (local):** `AdminLayout` now issues `fetchConfig()` when authenticated and
config is null. Guarded on `!config` and idempotent in the store (`isLoading` short-
circuits), so admin-to-admin navigation adds no requests. The three per-page guards stay -
they also cover non-admin deep links.
**Status:** FIXED LOCALLY, typecheck clean. Behaviour not yet re-verified - needs deploy.

## F16 — AED was never a defined currency, it worked by falling through the error path
**Where:** `frontend/src/utils/currency.ts`.
**What:** `CURRENCIES` contained PKR and GBP only. AED reached `fallbackFor()`, the branch
whose stated job is "unknown codes fall back to this rather than throwing mid-render". It
happened to emit `"AED 28.00"`, which is correct - but by luck, from the error path.
**Why it is worth fixing even though the output looked right:** the fallback also means a
typo'd or renamed code renders as though it were valid, so nothing ever surfaces a
misconfigured tenant. A live client's currency should be a decision in the table, not a
survivable accident.
**Fix applied (local):** AED added explicitly - symbol `"AED "`, locale `en-AE`,
`minorExponent: 2`, `displayDecimals: 2` (the dirham has 100 fils and UAE retail quotes
both places).
**Status:** FIXED LOCALLY

## F17 — 17 hardcoded "(PKR)" labels, including on the payment screens
**Where:** seven files. Malik spotted the Settings one directly: Discount Approval →
**"Fixed Threshold (PKR)"**.
**What:** these are literal text, not formatted output, so they were untouched by any
currency logic and said PKR for every tenant regardless:
| File | Count | Examples |
|---|---|---|
| `PaymentPage.tsx` | 6 | "Amount (PKR)", "Tendered (PKR)" |
| `SessionPaymentPage.tsx` | 5 | "Amount (PKR)", "Tendered (PKR)" |
| `IngredientManagementPage.tsx` | 2 | "Cost per Unit (PKR)" |
| `MenuManagementPage.tsx` | 2 | "Price (PKR) *", "Price Adjustment (PKR)" |
| `DiscountTypesPage.tsx` | 1 | "Amount (PKR)" |
| `SettingsPage.tsx` | 1 | "Fixed Threshold (PKR)" |
⚠️ **This was not only Martin's problem.** The payment screens are the ones **Chick Shack
staff use every trading day**, and they have been asking for amounts in "(PKR)" for months.
Nobody reported it, which is its own lesson about what UAT catches and daily use does not.
**Fix applied (local):** a new `useCurrencyCode()` hook
(`frontend/src/hooks/useCurrencyCode.ts`) reads the tenant currency from `configStore`, so
labels are reactive rather than depending on the non-reactive module global; it falls back
to `getActiveCurrency()` so a mid-fetch screen never renders empty brackets. All 17 labels
now interpolate it. `SettingsPage` deliberately uses its own form state instead, so the
label tracks the value being edited.
**Verified:** `tsc --noEmit -p tsconfig.app.json` **clean**.
**Status:** FIXED LOCALLY, typecheck clean. Not yet visually re-verified - needs deploy.

## F18 — The cart called it "GST". The UAE levies VAT.
**Where:** the POS cart totals line: **"Tax (5% GST)"**.
**What:** GST is India, Australia, Singapore, New Zealand and Canada. The Emirates levy
**VAT**. Pakistan is the one jurisdiction in this system's history where "GST" was right,
which is why it was hardcoded. Naming the wrong tax on the screen a customer pays against
is not a typo, it is the wrong tax named on a financial document.
**Fix applied (local):** `taxName(currency)` in `utils/currency.ts` - VAT for AED and GBP,
GST for PKR, plain "Tax" for anything unmapped. The line also now says **", included"** when
the tenant prices inclusive of tax, so the figure's basis is stated rather than guessed.
**Status:** FIXED LOCALLY

## F19 — 🔴🔴 THE SERIOUS ONE. Tax charged twice on tax-inclusive prices.
**Found by:** Malik, ringing up 3 x Butter Croissant in Exercise 8.
**Symptom:** subtotal AED 27.00, tax AED 1.35, **total AED 28.35**. The menu board says
AED 9.00 an item. The customer should pay **27.00**.
**Root cause:** `restaurant_configs.tax_inclusive` has existed since Phase 2, defaults to
True, and was read by **exactly one service** (`tax_invoice_service`). The order path never
consulted it and unconditionally did `tax = subtotal * rate; total = subtotal + tax`, which
is correct only when prices EXCLUDE tax. Same in the online-order path, the payment preview,
the session preview and the split-payment retax.
**Consequence beyond the overcharge:** `tax_invoice_service` DID back the VAT out, so the
A4 tax invoice and the amount actually taken **disagreed for the same sale** - which is
precisely what Exercise 9 asks Martin to check, in writing ("on 100.00 at 5% the VAT shown
should be 4.76, not 5.00").
**Blast radius, measured rather than assumed:**
- **Martin (AED, 5%, inclusive): overcharged 5% on every order.** Fixed.
- 🟢 **Chick Shack: NOT affected, and no live customer was ever overcharged.**
  `seed_chick_shack.py:137` sets `default_tax_rate = 0` deliberately, because nobody had
  confirmed a VAT registration. At rate 0 both formulas return `(0, subtotal)`, so their
  totals are **provably identical** before and after this change. There is a test pinning
  that, using their real payments total as the input.
**Fix applied (local):** one owner for the rule - `order_service.compute_tax(subtotal,
rate_bps, prices_include_tax)`. When prices include tax the tax is derived by SUBTRACTION
(`subtotal - round(subtotal / (1 + rate))`), never as `net * rate`, so `net + tax == subtotal`
exactly and no rounding remainder can appear or vanish. Wired into: `create_order`,
`public_order_service`, the order payment preview, the session payment preview, and both
split-payment retax paths. Frontend `CartPanel` mirrors it so the quoted total cannot differ
from the charged total; `taxInclusive()` on the payment pages - a helper that ADDED tax
while being named for the opposite convention - is renamed `payableTotal()` and now takes
the flag.

### Why 765 tests did not catch F19 - the part worth keeping
1. 🔴 **No test created an order.** Not via `order_service.create_order`, not via
   `POST /api/v1/orders`. Verified by grep across `backend/tests` before writing the new
   file: **zero hits for either.** Every order in the suite was a hand-built ORM row with a
   literal `tax_amount=800` / `=1379` / `=0`. The most important write path in a POS had
   never been executed by a test.
2. **The tests that did assert totals encoded the bug.** `test_p1b_discounts.py:238` carries
   the comment `# total = subtotal + tax - discount`. `test_p1a_features.py` declared
   `tax_inclusive=True` on its fixture and then asserted the tax was ADDED - the fixture
   contradicted its own assertions and passed anyway, because the code ignored the flag.
   A test written from the code, after the code, asserts whatever the code does.
3. **No tenant had ever combined `tax_inclusive=True` with a non-zero rate.** Chick Shack is
   rate 0; the Pakistan demo is priced exclusive-style. FZ LLC is the first, so FZ LLC is
   where it surfaced. A single-tenant test suite cannot find a multi-tenant bug.

### Tests added
`backend/tests/test_tax_inclusive_pricing.py` - **48 tests**:
- both conventions, and an explicit assertion that they **differ** (so the flag cannot be
  quietly turned back into a no-op);
- the 4.76-not-5.00 figure promised to Martin in the playbook;
- `net + tax == subtotal` swept across 10 subtotals x 3 rates;
- 🔴 **the Chick Shack safety proof**: rate 0 identical under both conventions, anchored to
  their real 642,087 payments total;
- **three orders created through the real service** - the test that did not exist. The first
  asserts `order.total == 2700`, which is exactly what the old code got wrong.

### Suite result
**824 passed, 10 failed, 2 errors** (baseline at clean HEAD: 765 / 12 / 2).
**+59 passing, two FEWER failures, no regressions.** All 10 remaining were inspected
individually and are unrelated: 8 QuickBooks Desktop QBXML parsing/adapter, 1 stale
error-message string in `test_pay_first`, 1 HTTP 401 in `TestVoidHardening`.

⚠️ **Five test fixtures were edited to STATE their tax convention** rather than inherit one.
Each was relying on an unstated default while asserting exclusive arithmetic. None had its
assertions weakened - the Pakistan differential-tax fixtures are now explicitly
`tax_inclusive=False` (a per-payment-method total only makes sense when tax is added on
top), and the online-storefront fixtures are explicitly `default_tax_rate=0` (like the real
GBP tenant), which makes their tip/service-fee arithmetic independent of tax convention
entirely - which is what they always meant to test.
