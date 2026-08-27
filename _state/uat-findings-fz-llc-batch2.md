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

---

# DEPLOY — 2026-08-27 08:27-08:31 UK, commit `e4a3d2e`

Run `33054102173`, **success, 3m22s**, every step green. Deployed at **08:27 UK**, well
outside Chick Shack's 16:00-22:00 trading window (7.5 hours of clear air).

**Verified on the box, not from the green Action:**
- Server HEAD = **`e4a3d2e`**.
- 🟢 **Chick Shack byte-identical**, measured the same tenant-scoped way before and after:
  **233 orders / newest `2026-08-26 19:40:58` / 166 customers / 219 payments / 642087 total
  / 87 menu items** - unchanged at both measurements.
- 🟢 **`compute_tax` executed INSIDE the running production backend**, not merely deployed:
  ```
  martin-fz    3 x AED 9.00 @5% incl -> (129, 2700)   was (135, 2835)
  chick-shack  rate 0, inclusive     -> (0, 642087)
  chick-shack  rate 0, exclusive     -> (0, 642087)   identical, as required
  playbook     AED 100.00 @5% incl   -> (476, 10000)  the promised 4.76
  exclusive    AED 27.00 @5%         -> (135, 2835)   other convention intact
  ```
- All hostnames 200 (`pos-demo`, `eats`, `parkcity`), `/api/v1/health` 200.
- Orbit CRM untouched and healthy.
- **Pre-deploy backup:** `/root/backups/pos_pre_taxfix_20260827T082602Z.sql.gz`, 380K,
  56 table data blocks.

⚠️ **A grep for the old label found `Tendered (PKR)` in 50 bundle files and it was a false
alarm** - worth recording because it would fool anyone. Only ONE bundle of each page is
reachable from the entry chunk, and both are clean:
`PaymentPage-D6brofwI.js` and `SessionPaymentPage-DhaWx52G.js`. The other 50 are orphans.
**Verify the bundle the entry chunk actually references, never the directory.**

## F20 — the deploy never prunes old hashed assets
**What:** `/usr/share/nginx/html/assets` holds **52 payment-page bundles** where 2 are live.
Every deploy uploads new content-hashed files and removes nothing, so the directory
accumulates one orphan set per deploy, forever.
**Why it matters, in order:**
1. It makes post-deploy verification actively misleading - a grep for old code "finds" it and
   suggests the deploy failed when it did not. That cost time on this very deploy.
2. Disk on a **2GB** box that also hosts Orbit CRM.
**Not urgent** - orphans are unreachable and harmless to users.
**Fix (later):** the deploy already uploads a complete `dist`; it should sync with deletion
scoped to `assets/` only. ⚠️ **Never `rsync --delete` at the site root here** - that rule
exists for a reason. Scope it to the assets directory and nothing above it.
**Status:** OPEN, deferred - logged as a follow-up, not a blocker for Martin.

## F21 — Exercise 8 of the playbook tells Martin to look for stock that has not moved yet
**Where:** `UAT_PLAYBOOK_FZ_LLC.md`, Exercise 8 ("Take an order, and watch stock move").
**What it says:** ring up 3 x Butter Croissant, take payment as cash, "go back to **Stock**...
**What you should see:** Croissant Dough has gone down."
**What actually happens:** nothing moves. Stock is deducted **only when the order reaches
`completed`** (`order_service.py:556` -> `_apply_inventory_and_commission`). An order that
has been sent to the kitchen and not yet closed has consumed nothing.
**Proved in UAT, not reasoned about:** order `#260827-001` was completed and its consumption
is in the ledger (`-0.36 kg`, "Sold 3 x Butter Croissant", 12:56:34, performer *System*).
Order `#260827-002` was rung up and left In Kitchen - **no consumption row exists for it**,
and the dough balance still reads 34.64 kg rather than 34.28 kg.
⚠️ We chased this as a possible regression from the same-day deploy, because #001 was
pre-deploy and #002 post-deploy. It was coincidence. Recording that so nobody re-chases it.
**The design is right and should NOT change.** Deducting at ring-up would consume stock for
orders that are later voided, and `_apply_inventory_and_commission` is deliberately written
so a stock problem can never block a sale from closing. **The document is what is wrong.**
**Fix:** Exercise 8 must tell the reader to complete the order first, and say plainly that
stock moves on completion, not on ring-up. Same class of error as the Exercise 4 movement
-history problem in batch 1: **the walkthrough describes behaviour nobody walked through.**
**Status:** OPEN - must be fixed in the PDF re-render, which is already on the list.

---

# Second round, same session — three more found while verifying the first deploy

## F22 — the same screen contradicted itself about VAT
**Where:** Payment screen, Transactions list, after paying order `#260827-002`.
**What:** "Order Total ... Tax (5%) **AED 1.29**" sat directly above
"Cash (payment) ... Tax @ 5% **AED 1.35**". Two different VAT figures for one sale, on one
screen, four lines apart.
**Root cause:** `PaymentPage.tsx:860` computed `payment.amount * rate / 10000` - a **fourth**
copy of the tax rule, in the frontend, still using the exclusive formula. F19 fixed the cart
and both previews and missed this one.
**The real lesson:** the rule had been written out by hand at four call sites, so fixing
three of them produced a document that disagreed with itself - arguably worse than the
original bug, because it looks like a system that cannot add up.
**Fix applied:** a single `frontend/src/utils/tax.ts` (`splitTax` / `taxPortion` /
`payableTotal`) mirroring `order_service.compute_tax`. `CartPanel`, `PaymentPage` and
`SessionPaymentPage` all now call it; the local duplicates are deleted, so there is no
fourth copy left to drift.
**Status:** FIXED LOCALLY, typecheck clean.

## F23 — "Print Bill" printed a screenshot of the application
**Found by:** Malik. **What:** the print preview showed the whole payment page in landscape -
nav bar, discount form, cash-drawer panel, buttons - instead of a bill.
**Root cause:** `PaymentPage.handlePrintBill()` was `window.print()` on the document, with no
print stylesheet.
**The annoying part:** a correct 80mm thermal `ReceiptModal` already existed and
**`SessionPaymentPage` has used it all along.** The single-order payment screen was simply
never moved over. Malik's read was right - it *was* fixed elsewhere.
**Fix applied:** `PaymentPage` now opens `ReceiptModal`, which clones only the receipt node
into a print window under `@media print { body { width: 80mm } }`, and renders the tenant's
own `receipt_header` / `receipt_footer` - so the bill carries the client's branding.
**Status:** FIXED LOCALLY, typecheck clean.

## F24 — 🔴 the printed customer bill was hardcoded to rupees
**Where:** `ReceiptModal.tsx:57`, found while wiring F23.
**What:** ``formatAmount`` was
``return `Rs. ${(paisa / 100).toLocaleString("en-PK", { minimumFractionDigits: 0 })}` `` -
hardcoded symbol, hardcoded Pakistani locale, and **zero decimal places** - on the printed
tax receipt, the one document a customer keeps.
**The receipt payload has carried a `currency` field all along** (`ReceiptData.currency`,
`schemas/receipt.py:62`). It was simply never used.
**What Martin's bill would have printed:** `Rs. 27` for AED 27.00. Wrong symbol, wrong
locale, and the fils dropped.
**Fix applied:** both helpers now take the code and defer to currency-aware `formatMoney`;
all **15** call sites thread `receipt.currency` through.
**Status:** FIXED LOCALLY, typecheck clean.

## F25 — there is no frontend test suite at all
**What:** `frontend/package.json` has no `test` script, and there are no test files anywhere
under `frontend/src`. No vitest, no jest.
**Why it matters here:** F14, F15, F17, F18, F22, F23 and F24 were **all** frontend defects,
and every one reached production. The backend has 824 tests; the half of the system the
client actually looks at has none. `utils/tax.ts` is now a pure, trivially testable module
holding money math with zero tests on it.
**Deliberately NOT fixed now:** adding a test runner changes the build pipeline, and the
deploy pipeline is what puts Chick Shack's live tablet at risk. Not something to introduce
hours before a client demo.
**Status:** OPEN - should become a formal open item (OI) after Martin.

---

# Comprehensive sweep — 2026-08-27, after Malik called out the one-at-a-time approach

**Malik's criticism, recorded because it changed how this was run:** *"why do we have to stop
at every step fix it... you could have literally fixed everything before we initiated the
UAT... i want a comprehensive sweep. i dont want even martin to find petty issues."*

He was right. F18 was fixed in the cart and reappeared on the receipt; F19 was fixed in three
places and a fourth kept the old formula. Fixing instances while the class survives is how
both of those happened. What follows is the class-level sweep that should have come first.

## What was swept, mechanically rather than by eye

| Sweep | Method | Result |
|---|---|---|
| Currency symbols in literals | regex over `frontend/src` + `backend/app` | **F26** — 3 of 4 backend symbol tables missing AED |
| Date/number locales | regex, all `.ts/.tsx/.py` | **F27** — 7 hardcoded locales |
| Tax NAME (GST vs VAT) | regex + per-jurisdiction review | **F18 completed** — 2 more in `receipt_service` |
| Tax formula ignoring `tax_inclusive` | regex for `* rate / 10_000` | clean — only the 2 inside `compute_tax` itself |
| `Decimal` on response schemas | AST-ish scan of all schemas + `response_model` usage | **F28** — 68 more annotations across 2 modules |
| Every GET route | enumerated from the app, driven as `martin-fz` | **67 routes, 0 server errors** |
| Exercises 11-15 write flows | driven end to end via the API | **32 assertions, 0 failures** |
| Exercises 9, 10, 13 | driven end to end via the API | clean (2 false alarms in my own test) |

## F26 — three client-facing document generators could not render AED
`print_service` had the only correct currency table. `purchase_order_document`,
`quotation_document` and `email_service` each carried their own copy **without AED**, and each
fell back to an **empty string** — so a UAE supplier's purchase order, a customer's quotation
and an order confirmation email would each have rendered `380.00` with no currency on the
document at all. Now one table in `app/utils/money.py`; the fallback is the ISO code plus a
space, ugly but never silent. **Verified all four agree:** `AED 380.00 / £380.00 / Rs.380.00 /
XYZ 380.00`. GBP output is unchanged, so Chick Shack's printing is untouched.

## F27 — seven hardcoded date locales
`en-PK` on the printed receipt, the Z-report and the staff list; `en-GB` on the order lists and
online reports. A UAE client's own tax receipt carried a Pakistani date format, and adjacent
screens in the same build disagreed with each other. New `currencyLocale()` derives it from the
tenant's currency. Also fixed: `SyncTab` formatted money as `Rs.${…en-PK}`, and Settings told
every tenant *"Discounts > Rs N need approval"*.

## F28 — 68 more Decimal fields that would have broken a screen
`inventory.py` was fixed when `/admin/ingredients` crashed (F14). The identical fault sat in
**`location.py` (20)** and **`procurement.py` (48)** — the stock, supplier, purchase-order,
receiving and order-planner screens, i.e. exactly where Martin goes next. Several only survived
because JS coerces strings in `*`, `/` and `>`; each was one `.toFixed()` away from the same
white screen. Also **`AIUsageSummary.by_kind` was `list[dict]`** — an untyped container the
serializer could not reach into, so its cost went out as a string while the sibling field on
the same object went out as a number. Now `AIUsageKindRow`.
**Proved, not assumed:** 119 Decimal-typed fields across the 3 modules dumped to JSON —
**all 119 numeric**, none string.

## The runtime sweep — what actually runs

**67 GET routes enumerated from the app and driven as the `martin-fz` admin: zero 5xx.** Two
flagged for string-numbers; one was the real `AIUsageSummary` bug, the other a false positive
(my regex matched "rate" inside `tax_registration_number`).

**Exercises 11, 12, 14, 15 driven end to end — 32 assertions, all passing**, including the two
that are easy to get backwards and that the playbook promises Martin in writing:
- **VAT ADDED on a purchase order** (a supplier quotes net) — 625,000 + 31,250 = 656,250.
- **VAT INSIDE a quotation total** (the selling side is inclusive) — 395,000 total, 18,810 of
  VAT contained in it.
- blank PO price fills itself from the catalogue; partial receipt raises stock by exactly what
  arrived, leaves the balance owed, and writes the price actually paid back to the catalogue;
- the order planner **makes the dough in-house rather than buying it**;
- a quotation with a non-menu line **refuses to convert, and for the right reason** (verified
  explicitly — an earlier run passed this for the wrong reason, on a status error);
- a menu-only quotation converts **at the quoted price, not the current menu price**, and the
  resulting order's total equals its subtotal, so the F19 fix holds through conversion.

## F29 — the Profitability report is empty for this tenant
`/locations/reports/profitability` returns **0 rows**. Six channels are configured with
sensible commissions (Talabat 15%, Careem 15%, noon 12%, Website 2.5%, WhatsApp 0, B2B 0), but
no completed order carries channel data, so the report Martin specifically asked for — *"the
one you said nobody had given you"* — renders blank.
**Not a code fault.** Commission is frozen onto an order at completion (by design, so
renegotiating a rate later does not move last year's reported profit), and this tenant's demo
orders predate that. **Needs demo data seeded before the video**, or Exercise 10 shows Martin
an empty screen.
**Status:** OPEN — must be fixed before the recording.

## F30 — `martin-fz` has no kitchen stations
Converting a quotation logged *"No active kitchen stations — skipping ticket creation"*. Benign
today (no dine-in, no KDS in scope), but if the demo shows an order going "to the kitchen",
nothing will appear on a kitchen screen because there is no station to route to.
**Status:** OPEN — decide before the video whether the demo mentions the kitchen at all.

## Not bugs, recorded so they are not re-chased
- `/api/v1/locations` flagged for a "numeric string": it was `tax_registration_number`, whose
  value is legitimately a digit string. My regex matched "rate" inside "regist**rat**ion".
- "Invoice names the tax GST" failed in one run: my assertion was case-sensitive and the
  payload uses `vat_rate_bps` in lowercase. The real value is `tax_label = 'VAT'`, no GST.
- OCR (Exercise 13) returns **HTTP 503 with a plain-language message**, which is the documented
  expected behaviour when it has not been switched on for a client.
- The newest completed order `FZ-0001` carries **tax = 0** — old seed data written before the
  F19 fix. New orders are correct; that row is not.
