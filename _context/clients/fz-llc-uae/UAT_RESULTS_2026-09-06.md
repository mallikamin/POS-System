# UAT results — Martin round 3 (M9-M13), production, 2026-09-06

Walked against https://eats.sitaratech.info on tenant `martin-fz`, build `b4505fa`.
Script: `UAT_FZ_LLC_2026-09-06.md`. Screenshots live in
`_files/2026-09-06/uat-round3/` and are named by the step that produced them.

A step is PASS only if it was seen on screen. Anything not walked is recorded as
NOT WALKED, never as a pass.

---

## Step 1 — the two new menu entries are there. PASS.

Signed in on the laptop in an incognito window as Martin Zubeldia (Demo) on
FZ LLC — Bakery & Cafe (Demo).

* **Production** is in the admin menu, directly under Stock.
* **Expenses** is in the admin menu, directly above Sales Channels.

Both are the M9 and M10 discoverability asks, and both were the specific thing
Martin said did not exist.

![Admin menu, upper half](../../../_files/2026-09-06/uat-round3/step01-admin-menu-top.png)
![Admin menu, lower half showing Production and Expenses](../../../_files/2026-09-06/uat-round3/step01-admin-menu-bottom.png)

### Unplanned finding on the same screen: the commission rates are NOT all zero

The order-channel screen shows live commission on each tile:

| Channel | Commission shown on the tile |
|---|---|
| Careem Now | 30% |
| KEETA | 30% |
| noon Food | 30% |
| WhatsApp / Direct | 3% |
| B2B Wholesale | No commission |

🔴 **This contradicts `API_VERIFICATION_2026-09-06.md`, which recorded every channel at 0%.**
Someone has entered rates since that check, or the check read the wrong thing. Do not put
"every channel is on 0% commission" in the reply to Martin until the Sales Channels screen
has been opened and read directly. Chased at the Sales Channels step below.

**Deliveroo is still absent**, confirmed on the tiles: seven tiles, and Deliveroo is not one
of them. Pick up and Call Center are order types rather than sales channels, so the channel
tiles are B2B Wholesale, Careem Now, KEETA, WhatsApp / Direct and noon Food.

![Order channel tiles](../../../_files/2026-09-06/uat-round3/step01-order-channel-tiles.png)

---

## Step 2 — Sales Channels read directly. The "0% commission" claim was FALSE.

`eats.sitaratech.info/admin/channels`, read on screen:

| Channel | Code | Commission | Fixed fee | On the POS |
|---|---|---|---|---|
| B2B Wholesale | `b2b` | 0.00% | AED 30.00 | Own tile |
| Careem Now | `careem` | 30.00% | AED 0.00 | Own tile |
| KEETA | `talabat` | 30.00% | AED 0.00 | Own tile |
| Website (card) | `website` | 3.00% | AED 1.00 | Hidden |
| WhatsApp / Direct | `direct` | 3.00% | AED 0.00 | Own tile |
| noon Food | `noon` | 30.00% | AED 0.00 | Own tile |

🔴 **`API_VERIFICATION_2026-09-06.md` said every channel was on 0% commission. It is not true
and it must not reach Martin.** Real rates are in: the three aggregators at 30%, card at 3%
plus AED 1, wholesale at a flat AED 30 per order and no percentage. These are also not our seed
values (the seed wrote 15/15/12/2.5%), so they were entered by hand on this tenant. **The
profitability report has real inputs.** Correction applied to that file and to `STATE.md`.

⚠️ **KEETA carries the code `talabat`.** The seed created Talabat; the row was renamed to KEETA
and the code cannot be changed after creation, by design, because orders already reference it.
Nothing is broken: reports read the name. Two consequences worth telling Martin. Any order ever
rung up under the old Talabat tile is now counted as KEETA, and if he ever wants Talabat back as
its own channel it must take a different code.

**Deliveroo confirmed absent** on the screen itself, not only on the tiles.

![Sales Channels](../../../_files/2026-09-06/uat-round3/step02-sales-channels.png)

---

## Step 3 — Deliveroo added on production. PASS, with two notes.

"Sales channel created", the row is in the table, and **the tile appears on the order-channel
screen immediately with no redeploy**. That is the M4 promise proven live: a channel added in
the back office becomes a till tile at once.

![Add Sales Channel form](../../../_files/2026-09-06/uat-round3/step03-add-deliveroo-form.png)
![Sales Channels after saving](../../../_files/2026-09-06/uat-round3/step03-channels-after-deliveroo.png)
![Order channel tiles, Deliveroo present](../../../_files/2026-09-06/uat-round3/step03-till-tiles-with-deliveroo.png)

⚠️ **Note 1: it was saved at 5.00%, which is a guessed rate.** Martin's other three aggregators
are on 30.00%, which is the normal UAE band. 5% is not a rate anyone here has seen on his
Deliveroo contract, and it will understate that channel's cost in the profitability report while
looking deliberate. Commission is editable at any time, so this is a one-field fix, but it must
either carry his real rate or sit at 0 so it reads as "not set yet".

⚠️ **Note 2: the code was typed `Deliveroo`, capitalised.** Every other code on the tenant is
lower case (`b2b`, `careem`, `talabat`, `website`, `direct`, `noon`), and **a code cannot be
changed once created**. Checked in the source: nothing routes on the channel code. Orders carry
`sales_channel_id`, and the tiles and reports read the name, so this is cosmetic. The one real
consequence is that the duplicate check at creation is case-sensitive
(`location_service.py:142`), so a second channel with the code `deliveroo` could later be
created alongside this one. There is no DELETE route for a channel by design, so recreating it
lower case would leave a dead row behind. **Left as it is deliberately.**

**Decision, Malik, 2026-09-06: the 5% stays.** It is display-only demo data on a channel with
no orders behind it, and Martin sets his own rate the moment he has a contract. Note 1 above is
closed, not outstanding.

---

## Steps 4-6 — M11 categories, the read-only half. PASS (script steps 2, 3 and 5).

**Script step 2, the Category filter is populated.** The Ingredients page carries three filters
and a **Categories** button in the header. The category dropdown lists all eight:
Bakery, Beverage, Dairy, Dry Store, Pantry, Produce, Produced, Protein. This is the list Martin
said did not exist.

![Ingredients page](../../../_files/2026-09-06/uat-round3/step04-ingredients-page.png)
![Category filter open](../../../_files/2026-09-06/uat-round3/step04-category-filter-open.png)

**Bonus, round 1 M1 re-confirmed on the same screen.** The source filter offers Bought and made
in-house / Bought only / Made in-house only, and every row carries a Bought or Made in-house
badge.

![Source filter open](../../../_files/2026-09-06/uat-round3/step04-source-filter-open.png)

**Script step 5, the Categories dialog shows counts.** Bakery 2, Beverage 1, Dairy 3, Dry Store
1, Pantry 3, Produce 2, Produced 3, Protein 1. That totals **16, which matches the 16
ingredients on the tenant exactly**, so the count is real and not an estimate. Each row has a
rename pencil and a delete bin.

![Ingredient categories dialog](../../../_files/2026-09-06/uat-round3/step05-categories-dialog.png)

**Script step 3, the create form has a dropdown with + New category.**

![Create Ingredient, category dropdown](../../../_files/2026-09-06/uat-round3/step06-create-ingredient-category-dropdown.png)

**Bonus, round 2 M8 re-confirmed.** "I buy this in a different unit from the one I cook with"
is on the same form, which is the two-units-and-a-conversion ask.

![Create Ingredient, purchase unit checkbox](../../../_files/2026-09-06/uat-round3/step06-create-ingredient-purchase-unit.png)

### 🟠 Defect found: the create form opens on a category that does not exist

The Category dropdown opens showing **General**. There is no General category on this tenant;
the eight real ones are listed above. `IngredientManagementPage.tsx:111` initialises the field
to the literal `"General"` and lines 309 and 376 fall back to it again on save.

**Consequence:** an ingredient saved without touching the category silently creates a ninth
category called General, on the very screen whose whole point was that Martin controls his own
category list. Not data loss, and one line to fix (default to the first real option, or open
blank and require a choice). **Recorded, not fixed. Fixing means another deploy, which reopens
the verification cycle mid-UAT.** Decide after the walk.

---

## Step 7 — a brand-new category created from inside the ingredient form. PASS (script step 4).

`Packaging` was typed into **+ New category** on the Create Ingredient form and saved with the
ingredient in one action. Toast: "Ingredient created".

New row: **Takeaway Box, Bought, Packaging, pcs, AED 1.50, stock 0.00, reorder point 100.00,
Active, Low Stock.** The category is the one typed, so a category and the ingredient that needs
it are created together without a separate trip to a settings screen. That is the M11 ask.

![Ingredient created](../../../_files/2026-09-06/uat-round3/step07-ingredient-created-toast.png)
![Takeaway Box row, category Packaging](../../../_files/2026-09-06/uat-round3/step07-takeaway-box-row.png)

**Not a defect, checked:** typing `packaging` into the search box returns "No ingredients found".
That box searches the ingredient NAME only; the category is the dropdown beside it. The red
triangle beside a name is the low-stock marker (`IngredientManagementPage.tsx:571`), which is
correct on a row with 0 stock against a reorder point of 100.

![Name search does not search categories](../../../_files/2026-09-06/uat-round3/step07-name-search-not-category.png)

---

## Step 8 — rename a category and the ingredients follow. PASS (script step 6).

Renamed `Packaging` to `Packaging & Disposables` from the pencil inside the **Categories**
dialog. Toast: **"Renamed to 'Packaging & Disposables' — 1 ingredient(s) moved with it."**
The count in the toast is the real count, the filter dropdown carries the new name, and the
Takeaway Box row reads the new name without a reload.

![Rename toast naming the count](../../../_files/2026-09-06/uat-round3/step08-rename-toast.png)
![Filter dropdown with the new name](../../../_files/2026-09-06/uat-round3/step08-filter-shows-new-name.png)
![Ingredient row carrying the new name](../../../_files/2026-09-06/uat-round3/step08-row-carries-new-name.png)

⚠️ **UAT friction worth knowing, not a defect.** There are two pencils on this screen and they
do different jobs: the pencil on an ingredient ROW edits the ingredient, and the pencil inside
the Categories dialog edits the category. The first attempt used the row pencil and opened Edit
Ingredient. Martin will make the same mistake once.

**Cosmetic note:** a newly created category is appended to the end of the list rather than
sorted into it. That is deliberate, `ingredient_category_service.py:66-72` gives a new row
`max(sort_order) + 1` and line 113 orders by `sort_order` then name, so the eight seeded
categories read alphabetically and anything Martin adds lands at the bottom.

---

## Step 9 — a category in use cannot be deleted. PASS (script step 7), by prevention.

The bin beside `Packaging & Disposables` is **greyed out and unclickable** while the category
holds an ingredient, and the count sits under the name as "1 ingredient". So there is no
refusal message to read: the UI does not let the request leave.

![Delete disabled while in use](../../../_files/2026-09-06/uat-round3/step09-delete-disabled-in-use.png)

**The script expected a refusal naming the count. What shipped is stricter and quieter.** The
server-side guard exists as well and is the real invariant, not the disabled button:
`ingredient_category_service.py:249-271` counts the ingredients filed under the name and raises
"<name> still has N ingredient(s) in it. Move them to another category first." A category is
then deactivated rather than deleted. Covered by
`backend/tests/test_martin_round3.py:201 test_a_category_in_use_cannot_be_deleted`.

**Deliberate design, worth telling Martin in one line:** deleting a category never reassigns his
ingredients. It refuses, because silently moving twelve ingredients to "General" is a data
change nobody asked for.

---

## Step 10 — 🔴 FAIL (script step 8). A deleted ingredient blocks its category forever.

**Expected:** delete Takeaway Box, then delete `Packaging & Disposables`, and it goes.
**Actual:** the ingredient deleted and left the list. The category's bin is **still greyed out**.

**Root cause, read in the source, not guessed.**

1. Deleting an ingredient is a **soft delete**. `recipe_service.py:270-276` sets
   `is_active = False` and the row stays in the table with its category string intact.
2. The category in-use guard counts **every** ingredient carrying that category name with **no
   active filter**: `ingredient_category_service.py:259-266`.
3. The count shown in the dialog is built the same way, `list_categories` around line 96, so the
   dialog keeps reporting "1 ingredient" for an ingredient the user has already deleted.

**Consequence for Martin.** Any category he ever files an ingredient under can never be removed
once that ingredient is deleted, and the screen gives him no reason why: the ingredient is gone
from the list, yet the category insists something is in it. This is on the exact screen he asked
for in M11.

**Workaround that exists today:** the Ingredients page has a Status filter, so an inactive
ingredient can be found, edited and re-filed under another category, which then releases the old
one. Nothing is stuck permanently, but nobody will discover that unaided.

**Fix, when it is decided.** Filter the counts on `Ingredient.is_active == True` in
`ingredient_category_service.py`, in the guard AND in the display count AND in the orphan
self-heal that rebuilds a missing category from a category string in use. All three read the
same `counts` map, so it is one query. Filtering only the guard would let a category be deleted
and then immediately reappear as a self-healed orphan.

**Not fixed here.** A fix is a deploy, and a deploy mid-UAT invalidates what has been walked.

⚠️ **Tenant hygiene:** `martin-fz` is now carrying an inactive `Takeaway Box` and an empty-looking
`Packaging & Disposables` category. Both are probe residue from this walk and must be cleared
before Martin is told to look, either by the fix above or by re-filing the inactive row.

**Confirmed on screen.** After the ingredient was deleted the dialog still reads "1 ingredient"
and the bin stays disabled, so clicking it does nothing at all. No request is sent and there is
no error to read. The diagnosis above is confirmed from the UI as well as from the source.

![Count still reads 1 after the ingredient was deleted](../../../_files/2026-09-06/uat-round3/step10-count-still-one-after-delete.png)

**Case-insensitive category matching (`dairy` vs `Dairy`) was SKIPPED on production, deliberately.**
Recorded as skipped, not as a pass. Reason: with the count bug above unfixed, every probe
ingredient permanently inflates a category count on Martin's own screen. The behaviour is
covered by `backend/tests/test_martin_round3.py:148
test_case_differences_do_not_fork_a_category`. Re-walk it on production once the count fix ships.

---

## Step 11 — the Production screen exists and previews a run. PASS (script steps 9 and 10).

All three made-in-house items are in "What are you making?": **Cheese Sauce, Croissant Dough,
Chicken Stuffing.** Picking Cheese Sauce filled the right-hand panel with no further input:

* **Onto the shelf:** + 2 kg Cheese Sauce, worth AED 27.80 at AED 13.90 per kg.
* **Off the shelf:** Butter −0.2 kg (60.8 on hand), Flour −0.2 kg (128.75 on hand),
  Milk −1 L (34 on hand), Mozzarella Cheese −0.5 kg (19.5 on hand).

The on-hand figures are per LOCATION (Production & Wholesale), which is why they are lower than
the totals on the Ingredients page. Correct, not a discrepancy.

![Production screen with preview](../../../_files/2026-09-06/uat-round3/step11-production-screen-preview.png)
![The three made-in-house recipes](../../../_files/2026-09-06/uat-round3/step11-production-dropdown.png)

### 🟠 Worth telling Martin: the output is valued at the recipe's SAVED cost, not today's prices

At the prices his own Ingredients page shows right now (Butter 20.00, Flour 3.75, Milk 5.50,
Mozzarella 32.00) those four lines come to **AED 26.25**, not the AED 27.80 the panel states.
The gap is not an arithmetic error. `production_service.py:268-271` values the output at
`recipe.cost_per_serving`, which is written when the recipe is created or updated
(`recipe_service.py:420` and `:444`) and **nothing recalculates it when an ingredient's price
later changes**. There is a what-if, `simulate_recipe_cost`, but no automatic recost.

**Consequence:** every goods receipt at a new price moves the raw ingredient's cost and leaves
the sub-recipe's cost where it was, so the produced item drifts. Re-saving the recipe refreshes
it. For a client whose stated ask is `selling price − product cost − commission`, this is a real
accounting behaviour he should be told about rather than discover. **Candidate improvement, not
this round: recost dependent recipes when an ingredient cost changes.**

---

## Steps 12-13 — quantity and batches drive each other. PASS (script step 11).

**Batches to quantity:** 3 batches gave 6 kg, worth AED 83.40, with Butter −0.6, Flour −0.6,
Milk −3, Mozzarella −1.5. Exactly three times the one-batch figures.

**Quantity to batches:** typing 5 kg gave 2.5 batches, worth AED 69.50, with Butter −0.5,
Flour −0.5, Milk −2.5, Mozzarella −1.25. A half batch is allowed and scales cleanly.

Both directions work, and the money follows the quantity at a constant AED 13.90 per kg. This is
the M9 point that a chef thinks "make 5 kg of sauce", not "run the recipe 2.5 times".

![Batches drive quantity](../../../_files/2026-09-06/uat-round3/step12-batches-drive-quantity.png)
![Quantity drives batches](../../../_files/2026-09-06/uat-round3/step13-quantity-drives-batches.png)

---

## Step 14 — a shortfall is shown, named and allowed. PASS (script step 12).

100 kg of Cheese Sauce, 50 batches. Only the two lines that are actually short went pink and
each names its own gap: **Milk −50 L against 34 on hand, "16 L short"**, and **Mozzarella
Cheese −25 kg against 19.5 on hand, "5.5 kg short"**. Butter and Flour stayed plain, which is
right, 10 kg of each against 60.8 and 128.75 on hand.

Amber note, verbatim: *"There is not enough on hand for this batch. Producing it anyway is
allowed and will leave a negative balance, so the shortage is visible rather than hidden."*

**Produce stays enabled.** That is deliberate. A kitchen that has already made the sauce needs
the system to record it, not refuse it, and a negative balance is the honest way to show that
the books and the shelf disagree.

![Shortfall warning with Produce still enabled](../../../_files/2026-09-06/uat-round3/step14-shortfall-warning.png)

---

## Step 15 — a production run was made on production. PASS (script steps 13 and 14).

2 kg of Cheese Sauce at Production & Wholesale, reference **UAT-2026-09-06** typed deliberately
so the run is identifiable as a test in Martin's history rather than looking like a real batch.

Toast, verbatim: **"Produced 2 kg of Cheese Sauce. 4 ingredient(s) came off the shelf at
Production & Wholesale. Reference UAT-2026-09-06."** It names the quantity, the input count and
the site, which is what the script asked for.

![Produce toast](../../../_files/2026-09-06/uat-round3/step15-produce-toast.png)

⚠️ **The panel still showed the pre-run on-hand figures** at the moment of the toast (Butter
60.8, Milk 34). Whether that is a stale preview or simply the screenshot timing is checked in
the next step with the Refresh button.

⚠️ **This wrote to Martin's tenant:** +2 kg Cheese Sauce and −0.2 Butter, −0.2 Flour, −1 Milk,
−0.5 Mozzarella at Production & Wholesale. Reversible with a stock adjustment if he wants the
demo data pristine.

---

## Step 16 — 🟠 DEFECT: the preview's on-hand figures are stale after a run.

After producing 2 kg and pressing **Refresh**, the right-hand panel still reads Butter 60.8,
Flour 128.75, Milk 34, Mozzarella 19.5, exactly the pre-run figures. Expected 60.6, 128.55,
33 and 19.0.

**Cause, read in the source.** `ProductionPage.tsx:229-241` `handleRefresh` calls `loadRuns()`
and nothing else, so the button reloads the run HISTORY only. `handleRun` at :243 does the same
after a successful run. The preview effect at :173 refetches only when the recipe, the location
or the batch count changes, so nothing re-reads stock after a run.

**Why it matters, and it is more than cosmetic.** The shortfall warning is computed from these
figures. Run the same batch repeatedly without touching the form and the panel keeps quoting the
original stock, so the amber "not enough on hand" note stops appearing at the point it becomes
true. Martin could run himself negative with the screen still saying he has plenty.

**Fix:** re-run the preview after a successful run, and make Refresh do both. Small.

**This does NOT prove the stock failed to move.** The toast reported a completed run; the panel
is a cached read. Proven either way in the next two steps.

![On-hand unchanged after Refresh](../../../_files/2026-09-06/uat-round3/step16-stale-onhand-after-run.png)

---

## Step 17 — Recent production lists the run with its inputs. PASS (script step 15).

Top row: **9/6/2026 6:01:27 PM, Cheese Sauce, +2 kg**, consumed Butter 0.2 kg, Flour 0.2 kg,
Milk 1 L, Mozzarella Cheese 0.5 kg, cost AED 27.80, site Production & Wholesale, reference
UAT-2026-09-06. Below it sit the older runs, three Croissant Dough batches from 26 to 28 August
carrying auto-generated `PROD-...` references.

**This settles the doubt from step 16.** The history has no table of its own; it is
reconstructed from the stock movements themselves (`production_service.py:276-295`). A run that
appears here is a run whose movements were written. **The stock moved. The preview panel was
stale, nothing more.**

![Recent production](../../../_files/2026-09-06/uat-round3/step17-recent-production.png)

⚠️ **Small localisation point for a UAE client:** the timestamp renders US-style, `9/6/2026`
for 6 September. Martin will read that as 9 June. Worth switching the admin screens to a
day-first or short-month format.

---

## Step 18 — the stock actually moved, to the gram. PASS (script step 16). **M9 IS PROVEN.**

Stock at Production & Wholesale, read after the run:

| Ingredient | Expected | On screen |
|---|---|---|
| Butter | 60.6 kg | **60.6 kg** |
| Flour | 128.55 kg | **128.55 kg** |
| Milk | 33 L | **33 L** |
| Mozzarella Cheese | 19 kg | **19 kg** |
| Cheese Sauce | up 2 kg | **8 kg**, badged Produced |

All four inputs match the predicted figure exactly. The output reads 8 kg; its before-value was
not recorded on screen, but the run history shows the +2 kg movement that produced it.

**This is the whole of Martin's M9 sentence** — "added as stock (+ sauce) and at same time the
ingredient reduced (- tomato raw item)" — done in one action, with the preview shown before the
button and the numbers checked after it.

Cheese Sauce is valued at AED 13.90, matching the recipe cost discussed in step 11.

![Stock after the run, part 1](../../../_files/2026-09-06/uat-round3/step18-stock-after-run-a.png)
![Stock after the run, part 2](../../../_files/2026-09-06/uat-round3/step18-stock-after-run-b.png)

---

## Step 19 — the Expenses screen exists and seeds itself. PASS (script step 17).

Opens on the current month, **From 01/09/2026 To 30/09/2026**, with four cards at AED 0.00 and
an empty state that says the right thing: *"Add the rent, the salaries, the electricity bill.
Ingredient purchases stay on the purchase orders where they already are."* That sentence is the
design decision Martin needs to understand, printed where he will read it.

**Ten starter categories are present**, seeded on this first visit: Rent, Salaries & Wages,
Utilities, Marketing, Repairs & Maintenance, Licences & Government Fees, Transport & Delivery,
Professional Fees, Insurance, Other. Before today the `expense_categories` table was empty on
every tenant, so this confirms the lazy seed fires on first open rather than being written to
tenants that never use the screen.

The Add form asks for date, status, who was paid, category with a **+ Add category** link,
invoice total, **VAT inside it**, their invoice number, paid by, and site. The header states the
rule plainly: *"The amount is the whole invoice. The VAT box is the part of it that is VAT, not
an extra on top."*

![Expenses, current month, empty](../../../_files/2026-09-06/uat-round3/step19-expenses-empty-current-month.png)
![Ten seeded expense categories](../../../_files/2026-09-06/uat-round3/step19-expense-categories.png)
![Add an expense](../../../_files/2026-09-06/uat-round3/step19-add-expense-form.png)

⚠️ **Date formats disagree across the product.** These boxes render day-first (06/09/2026), the
production history renders US-style (9/6/2026). One of the two must change; day-first is right
for the UAE.

---

## Step 20 — the VAT-inside arithmetic is shown before saving. PASS (script step 18).

A rent invoice for AED 21,000 with AED 1,000 of VAT inside it shows **"Net of VAT: AED
20,000.00"** live under the boxes, before anything is saved. That is how a UAE invoice reads and
it is the decision recorded in the checkpoint: `amount_minor` is the whole invoice, `tax_minor`
is the VAT within it.

The form also carries Notes and an **Invoice (PDF or photo)** file picker with a
**Record expense** button.

![Net of VAT computed live](../../../_files/2026-09-06/uat-round3/step20-expense-form-net-line.png)
![Attachment picker and Record expense](../../../_files/2026-09-06/uat-round3/step20-expense-form-attachment.png)

---

## Steps 21-22 — VAT guard, save, and the attachment round-trip. PASS (script steps 19, 20, 21).

**The VAT guard refuses in words**, not by silently clamping: setting VAT to 25,000 against a
21,000 invoice put **"The VAT cannot be more than the invoice total."** under the field and the
expense did not save. The same rule is enforced again by a CHECK constraint in migration
`f6a7b8c9d0e1`, so it holds even if a request never touches this form.

**Saved row:** 2026-09-06 · Al Barsha Warehouse Landlord · Rent · UAT-RENT-0906 ·
**NET AED 20,000.00 · VAT AED 1,000.00 · TOTAL AED 21,000.00** · unpaid · View.
Toast: "Expense recorded — Al Barsha Warehouse Landlord · AED 21,000.00".

**The attachment round-trips.** Clicking View fetched the PDF back through the authenticated
route and rendered it in a new tab, byte-identical to the file that went up, right down to the
"UAT TEST INVOICE - NOT A REAL BILL" heading. It arrives as a `blob:` URL, which is the tell
that the browser fetched it as the signed-in user rather than exposing a public link.

![Expense row saved](../../../_files/2026-09-06/uat-round3/step22-expense-row-saved.png)
![Attachment opens from View](../../../_files/2026-09-06/uat-round3/step22-attachment-opens.png)

⚠️ **The date-format inconsistency is now three ways in one product:** `2026-09-06` in this list,
`06/09/2026` in the form input, `9/6/2026` in the production history. Worth one pass to settle
on a day-first UAE format everywhere.

---

## Step 23 — the four period totals. PASS (script step 22).

**Total AED 21,000.00** (1 expense) · **Net of VAT AED 20,000.00** (AED 1,000.00 VAT) ·
**Still to pay AED 21,000.00** · **Biggest category: Rent, AED 21,000.00.**

Still to pay is the whole invoice because the row is unpaid, and the biggest-category card names
the category rather than just a number. The totals honour the From/To period, currently the
whole of September.

![The four expense totals](../../../_files/2026-09-06/uat-round3/step23-expense-totals.png)

---

## Step 24 — marking an expense paid. PASS (script step 23).

Status changed to **paid**, toast "Expense updated", and **Still to pay fell to AED 0.00** while
Total and Net of VAT stayed at 21,000 and 20,000. So the paid flag drives the payable card and
nothing else, which is right.

**How the paid date fills itself, read in the source:** `expense_service.py:438-450`
`_apply_paid_on` sets `paid_on` to the **expense date**, not today, when a row becomes paid with
no date given, and clears it again if the row leaves paid. ⚠️ For an invoice dated the 1st and
settled on the 20th, that records the 1st unless Martin types the real date. Defensible for a
till-side entry, wrong for an aged payable. Worth mentioning to him as a habit, or changing the
default to today.

![Expense marked paid](../../../_files/2026-09-06/uat-round3/step24-expense-paid.png)

---

## Step 25 — a draft expense is listed but counted nowhere. PASS (script step 24).

Second expense added as **Draft**: DEWA, Utilities, net AED 1,428.57, VAT AED 71.43, total AED
1,500.00. The row is visible with a grey `draft` badge, and **every card still reads the rent
invoice alone**: Total AED 21,000.00, "1 expense", Still to pay AED 0.00.

A half-entered invoice is not money owed, so it stays out of the totals until it is confirmed.

![Draft listed but excluded](../../../_files/2026-09-06/uat-round3/step25-draft-excluded-from-totals.png)

---

## Step 26 — a category added from inside the expense form. PASS (script step 25).

`Bank Charges` typed at **+ Add category**, toast "Category "Bank Charges" added", and it was
immediately selected in the form. It also appears in the page-level Category filter with no
reload, so both dropdowns read the same live list.

![Category added from the expense form](../../../_files/2026-09-06/uat-round3/step26-category-added-toast.png)
![New category in the page filter](../../../_files/2026-09-06/uat-round3/step26-category-in-page-filter.png)

---

## Steps 27-28 — deleting an expense. PASS (script step 26). **M10 IS PROVEN.**

The rent invoice was deleted, toast "Expense deleted", and the four cards fell to AED 0.00 and
"0 expenses" while the draft row stayed listed. The DEWA draft was then deleted too, leaving the
period empty again.

**The stored file goes with it**, verified in the source rather than guessed:
`expense_service.py:453-474` is a hard delete, the attachment rows cascade, and the media rows
are then removed explicitly because nothing else points at them. The comment gives the reason a
hard delete is right here: nothing references an expense and a mistyped invoice that could not
be removed would sit in the totals forever.

![Expense deleted, totals back to zero](../../../_files/2026-09-06/uat-round3/step27-expense-deleted.png)

**M10 covers everything Martin asked for**: a place to record rent, salaries and utilities, with
the invoice attached to each one, kept away from stock and ingredient purchasing.

⚠️ **Residue left on his tenant by this block:** the expense category `Bank Charges`. Harmless,
removable, listed here so cleanup is not forgotten.

---

## Steps 29-30 — the M13 switch is on the till, and two UI faults on the same screen.

**The switch is there.** Above the action button sits a two-way control, **Send to kitchen** /
**Print & deduct now**, defaulting to Send to kitchen, with the note "Goes to the kitchen board.
Stock comes off when the order is completed." That is script step 28.

### 🟠 Fault 1: the cart line list is squeezed to about one row on a laptop

The header said "3 items" and the totals were right (subtotal AED 43.00, VAT AED 2.05 included),
but only Butter Croissant was visible. **Nothing is lost.** The lines live in a
`flex-1 overflow-y-auto` region (`CartPanel.tsx:295`) inside a `flex h-full flex-col` column, and
scrolling revealed the other two. The footer beneath it now carries the customer row, site and
channel, the charges row, three total lines, **the new M13 switch and its two-line explanation**,
the action button and Clear Order. On a normal laptop window that leaves the list roughly one
row tall.

**This is the till, the screen used most, and M13 made it worse by adding the tallest new block
to the footer.** Malik's call on seeing it: the panel needs a laptop and mobile pass, and the
scroll affordance has to be obvious. A minimum height on the lines region plus a visible
scrollbar or fade edge is the smallest honest fix.

![Two items, one row visible](../../../_files/2026-09-06/uat-round3/step29-cart-two-items-one-visible.png)
![Three items, one row visible](../../../_files/2026-09-06/uat-round3/step29-cart-three-items-one-visible.png)
![The rest of the lines on scroll](../../../_files/2026-09-06/uat-round3/step30-items-appear-on-scroll.png)

### 🟠 Fault 2: two controls read "Send to kitchen"

The left half of the mode switch and the big action button carry the same words, so the screen
appears to offer the same command twice. The switch chooses the MODE; the button performs it.
Fix by naming them differently, for example a switch reading "To kitchen / Print now" above a
button reading "Place order", or by dropping the words from the button once a mode is chosen.

Both faults are recorded, not fixed. They are cosmetic-to-usability, not correctness, and a
deploy mid-UAT would invalidate what has been walked.

---

## Step 31 — Send to kitchen still behaves exactly as before. PASS (script step 29, first half).

Three items submitted with the switch on Send to kitchen. Confirmation in the panel:
**"Order #260906-002 sent to kitchen!"** and the cart emptied back to "Tap menu items to add
them here". No receipt opened, which is right for this mode.

![Order sent to kitchen](../../../_files/2026-09-06/uat-round3/step31-sent-to-kitchen.png)

---

## Steps 32-33 — kitchen mode moves no stock. PASS (script step 29, second half).

Orders board: **#260906-002, Pick up, In Kitchen, 3 items, AED 43.00, just now**, with Mark
Ready, Pay, Receipt and Void.

Stock at Production & Wholesale immediately afterwards: **Chicken Stuffing 9 kg, Croissant Dough
40 kg**, both unchanged from step 18. Stock comes off at completion, not at submission, exactly
as the note under the switch says.

![Orders board](../../../_files/2026-09-06/uat-round3/step32-orders-board.png)
![Stock unchanged after sending to kitchen](../../../_files/2026-09-06/uat-round3/step33-stock-unchanged.png)

⚠️ **His own data, not a fault:** `#260827-001` has been sitting In Kitchen for 230 hours. Old
demo traffic that nobody bumped. Worth clearing before any partner demo.

---

## Step 34 — a direct sale prints on the spot. PASS (script steps 30 and 31, receipt half).

With the switch on **Print & deduct now**, submitting opened the **Receipt Preview immediately**,
with a Print button, and emptied the cart. The receipt reads:

    FZ LLC - Bakery & Cafe (Demo)
    Order: 260906-003            Pick up
    06/09/2026, 6:42 PM
    Cashier: Martin Zubeldia (Demo)
    1x Butter Croissant          AED 9.00
    Subtotal                     AED 9.00
    VAT (5%)                     AED 0.43
    TOTAL                        AED 9.00

VAT is inside the price, which matches the "VAT (5%, included)" line on the till. The date on the
receipt is day-first, which is right for the UAE.

![Direct sale receipt](../../../_files/2026-09-06/uat-round3/step34-direct-sale-receipt.png)

**Not captured:** the button's label changing to "Print & Complete" before submission. The mode
is proven by its outcome instead, which is the stronger evidence.

---

## Step 35 — the direct sale is already completed. PASS (script step 31).

**Active** lists three orders and #260906-003 is not among them. **All** shows it at the top,
"just now", badged **Pick up · Completed**, AED 9.00, offering only Pay and Receipt. No Mark
Ready, no Void, and it never appeared in the kitchen queue.

![Active tab, direct sale absent](../../../_files/2026-09-06/uat-round3/step35-active-tab-excludes-direct.png)
![All tab, direct sale completed](../../../_files/2026-09-06/uat-round3/step35-all-tab-completed.png)

⚠️ **Worth saying to Martin plainly: a direct sale completes the ORDER, not the PAYMENT.**
`order_service.py:542-554` sets the status to completed and marks the items served; it does not
touch payment, which is why the card still offers Pay. So the cash has to be recorded with that
button or the day's takings will not reconcile against the completed orders. Faithful to what he
asked for, and a habit he needs to know about.

**Also correct and worth knowing:** the same branch refuses outright in pay-first mode, with a
message telling the user to take the payment first, rather than quietly reinterpreting the
request.

---

## Step 36 — the direct sale took the stock off on the spot. PASS (script step 32). **M13 IS PROVEN.**

**Croissant Dough 40 kg → 39.88 kg.** Chicken Stuffing unchanged at 9 kg, correct, that order
held only a croissant.

Movement History for Croissant Dough at Production & Wholesale:

    9/6/2026, 6:42:44 PM   consumption   -0.12 kg   balance 39.88   AED 10.19   value AED 1.22

One line, at the second the receipt appeared, for the 120 g of dough behind one Butter Croissant.
The deduction reaches through the sub-recipe, so selling a finished item consumes the
made-in-house component, which is the same engine M9 fills.

![Stock after the direct sale](../../../_files/2026-09-06/uat-round3/step36-stock-after-direct-sale.png)
![Movement history for the deduction](../../../_files/2026-09-06/uat-round3/step36-movement-history.png)

**M13 answers Martin's sentence exactly:** either send to kitchen, or print and deduct from
stock, chosen per order at the till.

---

## Step 37 — Z-Report prints without clipping. PASS (script step 43).

Printed to PDF, landscape, two pages. **Nothing is cut off on the right**: Summary, Sales by
Channel, By Payment Method, Order Status and the Top 10 Items table all sit inside the page with
the Revenue column intact. The table wrappers added for the phone are correctly switched off for
print, which is exactly what this regression check existed to prove.

![Z-Report on screen](../../../_files/2026-09-06/uat-round3/step37-zreport-screen.png)
![Top 10 items](../../../_files/2026-09-06/uat-round3/step37-zreport-top-items.png)
![Print preview, nothing clipped](../../../_files/2026-09-06/uat-round3/step37-zreport-print-preview.png)

### 🟠 Two content findings on this report

**1. The report says zero revenue while also saying AED 72.00.** Settled Orders 0, Net Revenue
AED 0.00, Net Tax AED 0.00, "No payments recorded", yet Sales by Channel reads "Takeaway, 3
orders — AED 72.00" and Top 10 Items lists five items. Both are true under their own
definitions: the summary counts SETTLED, meaning paid, and nothing was paid today. This is the
direct-sale consequence from step 35 landing on the report Martin would read at close of day.
He will ask why his Z-Report is zero. Either the summary needs a line saying what "settled"
means, or the direct sale needs to record a payment.

**2. The Z-Report still says "Takeaway", not "Pick up".** His round-1 ask renamed the channel
and the till honours it; this report does not. Small, but it is a request he already made once.

---

## PHONE SECTION. Capture note first.

Screenshots and screen recordings are both blocked in Chrome **Incognito** on Android, so the
first attempt produced a 30-second recording that is black end to end (confirmed with ffmpeg
`blackdetect`: `black_start:0 black_end:30.01`). The phone walk was redone in a normal tab.

---

## Step 39 — 🔴 M12 DEFECT: the header covers the first channel tiles on a phone.

**Pick up and Call Center are not reachable on the phone.** The channel list starts at B2B
Wholesale; the green Pick up tile is hidden behind the header entirely and the brown Call Center
tile shows only as a strip under it.

**Cause.** `POSLayout.tsx:77` gives the header `flex h-14 shrink-0`, a fixed 56 px that cannot
grow, and the restaurant name inside it is a link with no truncation. "FZ LLC — Bakery & Cafe
(Demo)" wraps to three lines on a 360 px screen, overflows its own 56 px box and paints over the
content beneath it.

**Fix:** truncate the name on small screens (`min-w-0` on the flex child plus `truncate`), or let
the header grow with `min-h-14 h-auto` and wrap. Truncation is right for a till.

**This lands inside M12**, the ask that said "How it looks on the phone still bad". The zoom
lock, the table scrollers and the cart sheet were all fixed; the channel screen, which is the
FIRST screen on the phone, was not. It must be fixed before the reply to Martin.

![Phone header covering the first tiles](../../../_files/2026-09-06/uat-round3/step39-phone-header-overlap.png)

### Malik's design note, same screen

Tiles and icons are too big on a phone: one tile fills a third of the screen and the icon inside
is 64 px (`DashboardPage.tsx:226-229`, `h-16 w-16` when three channels or fewer). On mobile they
should be smaller and leaner, two per row rather than one, so the whole channel list is visible
without scrolling. The grid at :207 is `grid-cols-1` until the `sm` breakpoint, which is what
forces one tile per row on a phone.

---

## Step 40 — the zoom lock is gone. PASS (script step 33).

Pinch-to-zoom works on a real phone, confirmed by Malik. This was the single biggest item in
M12: `user-scalable=no` meant that a table too wide to read could not be pinched open either.

## Step 41 — Ingredients on the phone. PASS (script step 34).

The header wraps into a usable row (menu, back to POS, user), the page header shortens to an
icon-only Categories button and a compact **+ Add**, the three filters stack instead of
colliding, and **the table scrolls sideways with readable columns** rather than being crushed
into slivers. Rows keep their thumbnails, Bought badges and category text.

![Ingredients on a phone](../../../_files/2026-09-06/uat-round3/step41-phone-ingredients.png)

---

## Steps 42-43 — Expenses on the phone. PASS (script step 35).

Empty state first: the four totals sit two-by-two, the filters stack, the refresh and **+ Add
expense** buttons are reachable, and the empty-state card keeps its explanation.

An expense was then added **on the phone itself**: Phone payee, Utilities, AED 100.00 with AED
4.76 VAT inside. Toast "Expense recorded", the cards updated to Total AED 100.00, Net of VAT AED
95.24, Still to pay AED 100.00, Biggest category Utilities.

**The row renders as a card, not a squashed table**: payee and amount on the first line, date and
category under it, an `unpaid` badge, and full-width Edit and delete controls.

![Expenses on a phone, empty](../../../_files/2026-09-06/uat-round3/step42-phone-expenses-empty.png)
![Expense saved from the phone](../../../_files/2026-09-06/uat-round3/step43-phone-expense-saved.png)
![Expense row as a card](../../../_files/2026-09-06/uat-round3/step43-phone-expense-card.png)

**Note on date formats, corrected:** the phone renders the filter boxes as `09/01/2026` where the
laptop showed `01/09/2026`. Native date inputs follow the DEVICE locale, so those are not ours to
fix. Only the timestamps we render ourselves, like the `9/6/2026` on the production history, are.

---

## Step 45 — Production on the phone. PASS (script step 36).

The form stacks into one column, the preview panel follows underneath it, and **Recent
production renders as cards**: recipe name and quantity on the top line, then timestamp, site
and who ran it, then the full input list, then the cost and the reference. The UAT run is at the
top with its `UAT-2026-09-06` reference.

**Corroboration for the step 16 defect.** On this fresh load the preview reads Butter 60.6,
Flour 128.55, Milk 33, the post-run figures. So the read itself is right and the defect is
precisely what was diagnosed: nothing refetches the preview after a run in the same session.

![Production form on a phone](../../../_files/2026-09-06/uat-round3/step45-phone-production-form.png)
![Preview panel on a phone](../../../_files/2026-09-06/uat-round3/step45-phone-production-preview.png)
![Run history as cards](../../../_files/2026-09-06/uat-round3/step45-phone-production-history.png)

---

## Step 46 — 🔴 THE WORST FIND OF THE WALK: the till shows PKR prices to a UAE client.

The Pick up till on the phone prices **Butter Croissant "Rs. 9"** and **Chicken & Cheese
Croissant "Rs. 16"**. Martin's tenant is in AED. Every other surface, cart, receipt, stock,
expenses, reads AED correctly.

**The till itself is otherwise right on a phone** (script step 37): the menu fills the screen,
category tabs scroll horizontally, items are a two-column grid with photos, and a fixed
**Open order** bar sits at the bottom.

![Rupee prices on the UAE till](../../../_files/2026-09-06/uat-round3/step46-phone-till-rupees.png)

### Cause, traced in the source

`MenuGrid.tsx:147` calls `formatPKR`, which despite its name delegates to `formatMoney` using the
module-level `activeCode` in `utils/currency.ts:81`. That variable **starts as `"PKR"`** and is
only corrected when `configStore` fetches the tenant config and calls `setActiveCurrency`
(`configStore.ts:29`). It is a plain module variable, **not reactive**: a component that has
already painted a price never repaints when the currency later changes.

So a cold load straight into the till paints the menu before the config response arrives, and
those prices stay in rupees for the life of the page.

**This exact class of fault was found in UAT on 2026-08-28 as F15** and fixed by issuing the
config fetch from `AdminLayout` too (`AdminLayout.tsx:112-135`, which spells out that the module
variable is not reactive). The fix made sure the fetch was ISSUED early; it did not make the
currency reactive, so any screen that paints a price before the response still shows rupees.
The till is that screen.

**Fix properly, not with another workaround:** make the currency reactive (read it from the
config store through a hook so a change re-renders), or hold price rendering until config has
resolved. Patching one more component leaves the next one to be found by a client.

🔴 **Client impact: this is the first screen Martin's staff would use, showing the wrong
country's currency. It must be fixed before the reply.**

---

## Step 47 — the same screen on the laptop shows AED. The currency fault is a RACE.

Hard reload of `/takeaway` on the laptop: **AED 9.00** and **AED 16.00**. Same build, same
tenant, same minute. The phone showed Rs. 9 and Rs. 16.

**That settles the diagnosis and makes it worse.** Nothing is hardcoded to rupees; the tenant
config simply has to arrive before the menu paints. A laptop on wifi wins that race, a phone on
mobile data loses it. So the fault is invisible in our own testing and appears for the client, on
the slowest connection, on the busiest screen. Intermittent, not cosmetic.

![Laptop till showing AED](../../../_files/2026-09-06/uat-round3/step47-laptop-till-aed.png)

---

## Steps 48-50 — the phone till, end to end. PASS (script steps 37, 38, 39, 40).

**The currency race resolved itself on the second refresh**: after two reloads the same phone
showed AED. Consistent with the diagnosis, and a reminder that an intermittent fault looks fixed
exactly when you stop looking.

**The cart sheet works.** Tapping the bottom bar slides the cart over the page with a "Current
order" header and an X. Inside it: the line items, site and channel pickers, the charges row, the
totals, the M13 mode switch and the action button, all reachable with a thumb.

**Nothing is lost when the sheet closes.** An item was added, the sheet closed, another item
added, the sheet reopened, and both were there. That is precisely the fault `b4505fa` fixed, the
sheet mounting a second CartPanel and discarding what was typed, confirmed on a real phone.

**An order was submitted from the phone: #260906-004, sent to kitchen.** End-to-end proof on
mobile, which is script step 40.

![Cart sheet on the phone](../../../_files/2026-09-06/uat-round3/step48-phone-cart-sheet.png)

⚠️ **The squeezed line list is on the phone too**: "2 items" with only Butter Croissant visible
before the site and channel block. Same fault as the laptop, same fix.

---

## Steps 51-52 — 🔴 TWO CALL CENTRE DEFECTS (script step 41 FAILS on the phone).

A customer was created on the laptop, `Test UAT / 0563326668`, and searched from both devices.

### Defect A: the panel says "No customer found" while showing the customer it found

On the laptop the left panel reads **"No customer found"** with a **Create New Customer** button,
and directly beneath it displays the selected customer card and the order history. Both at once.

**Cause.** When exactly one result matches the typed number, `CallCenterPage.tsx:166-176`
auto-selects it, and `handleSelectCustomer` at :212 clears `searchResults`. The results block at
:373 is guarded with `&& !selectedCustomer`; **the no-results block at :402 is not**. So the
moment a customer is selected, the empty state appears above their own card.

**The selection itself is fine** — order #260906-005 was placed and attached to the customer, and
the history lists it. Only the message is wrong. **One-line fix:** add `&& !selectedCustomer` to
the condition at :402, matching the block above it.

⚠️ **Design point Malik raised, worth taking seriously:** nothing confirms a selection, so it
"assumes the searched number is the current selection". A named "Selected: Test UAT" state with a
clear way to change it would make the flow legible.

![Laptop panel contradicting itself](../../../_files/2026-09-06/uat-round3/step51-laptop-callcenter-contradiction.png)

### Defect B: on a phone the menu never appears, so no order can be started

Searching works and the customer card renders, but scrolling reveals no menu grid. The call
centre is **unusable on a phone**.

**Cause.** The customer panel is `flex w-full shrink-0 ... lg:w-80` (:336) and the menu section is
its **flex-row sibling** (:609-610), switching from `hidden` to `block` when a customer is
selected. Below `lg` the panel already occupies the full row width and refuses to shrink, so the
menu is laid out off-screen to the right with nothing visible. It is displayed and unreachable.

**Fix:** the two must swap on a phone rather than coexist. Hide the panel once a customer is
selected below `lg` (`selectedCustomer ? "hidden lg:flex" : "flex"`), with a back control to
return to the search.

**This is inside M12.** The comment at :333 states the intent, "full width on a phone... at `lg`
it is the column it was", and the second half, giving the menu the screen after selection, was
never done.

![Customer found on the phone](../../../_files/2026-09-06/uat-round3/step51-phone-callcenter-customer.png)
![No menu on the phone](../../../_files/2026-09-06/uat-round3/step51-phone-callcenter-no-menu.png)

---

## Step 53 — rotation leaves no second cart. PASS (script step 42).

An order was built and submitted from the phone, **#260906-006**, and rotating to landscape and
back left **no second copy of the cart** on screen. The single-instance sheet from `b4505fa`
holds through an orientation change.

⚠️ **Landscape repeats the header overlap.** The restaurant name still wraps to two lines and
still covers the top of the first tile row, so **Pick up and Call Center are half-hidden in
landscape too**. The header fix has to cover both orientations.

![Landscape header overlap](../../../_files/2026-09-06/uat-round3/step53-landscape-header-overlap.png)

---

# VERDICT — 2026-09-06 UAT complete

## What Martin asked for, and whether it works

| Item | Verdict |
|---|---|
| **M9 Production** | **PROVEN.** Menu entry, live preview, shortfall warning, run recorded, stock moved to the gram, history reconstructed from the movements. |
| **M10 Expenses** | **PROVEN.** Seeded categories, VAT-inside arithmetic and its guard, PDF attached and read back, period totals, drafts excluded, delete removes the file. |
| **M11 Categories** | **Works, with one defect.** List, dropdown, inline add, rename that moves the ingredients, delete refused while in use. A deleted ingredient blocks its category forever. |
| **M12 Mobile** | **PART DONE, PART FAILED.** Zoom unlocked, tables scroll, expenses and production are cards, the cart sheet is right. But the header hides two channel tiles, the call centre has no menu on a phone, and the cart list is one row tall. |
| **M13 Direct sale** | **PROVEN.** Switch on the till, kitchen mode unchanged and no stock movement, direct mode prints, completes and deducts on the spot. |

## Defects found, worst first

1. 🔴 **The till shows PKR to a UAE client** on a cold load, a race between the menu and the
   tenant config. Intermittent, invisible on a fast laptop. Step 46-47.
2. 🔴 **Pick up and Call Center are unreachable on a phone**, portrait and landscape: the fixed
   56 px header cannot hold the untruncated restaurant name. Step 39, 53.
3. 🔴 **The call centre cannot take an order on a phone**: the menu is laid out off-screen beside
   a full-width customer panel. Step 52.
4. 🟠 **"No customer found" shows above the customer it found.** One missing guard. Step 51.
5. 🟠 **A deleted ingredient blocks its category permanently**, because the in-use count ignores
   `is_active`. Step 10.
6. 🟠 **The production preview does not refresh after a run**, so the shortfall warning stops
   being true exactly when it starts to matter. Step 16.
7. 🟠 **The cart shows one line at a time** on laptop and phone; the scroll is not discoverable.
   Step 29.
8. 🟠 **Two controls read "Send to kitchen"**, the mode switch and the action button. Step 30.
9. 🟠 **The ingredient form opens on "General"**, a category that does not exist, and saving
   creates it. Step 6.
10. 🟠 **The Z-Report reads zero revenue beside AED 72.00** because nothing was paid, and still
    says "Takeaway" where round 1 asked for "Pick up". Step 37.
11. ⚪ Rendered timestamps are US-style (`9/6/2026`) for a UAE client. Step 17.
12. ⚪ Channel tiles and icons are oversized on a phone; one per row. Malik's design note, step 39.
13. ⚪ `paid_on` defaults to the invoice date, not the day it was paid. Step 24.

## Probe residue left on `martin-fz`

* Orders **#260906-002 to #260906-006** (two in the kitchen queue, one completed).
* One production run, **UAT-2026-09-06**, +2 kg Cheese Sauce against its four inputs.
* Stock moved by that run and by the direct sale: Croissant Dough 39.88 kg.
* Ingredient **Takeaway Box**, soft-deleted, and its category **Packaging & Disposables**.
* Expense category **Bank Charges**.
* Customer **Test UAT / 0563326668** and sales channel **Deliveroo**, both deliberate.

---

# ROUND-1 ITEMS RE-WALKED IN THE BROWSER (they had only been API-verified)

Malik asked which of Martin's earlier asks had actually been SEEN today rather than proven over
the API. Four had not. They are walked below.

## Steps 54-55 — order charges, end to end. PASS. (M5, round 1.)

A service charge of **AED 3.10** was added from the "Add charges (delivery fee, service charge)"
row on the till. It shows on that row, then as **its own line in the totals**, and the arithmetic
holds: subtotal AED 28.00, VAT AED 1.33 included, service charge AED 3.10, **total AED 31.10**.

Submitted as **#260906-007** and the receipt carries the line:

    2x Cappuccino                AED 28.00
    Subtotal                     AED 28.00
    VAT (5%)                     AED  1.33
    Service charge               AED  3.10
    TOTAL                        AED 31.10

**This had never been seen before.** The 2026-09-06 API check recorded that none of Martin's
orders carried a non-zero charge, so the printed line was unproven until now.

![Charge on the till](../../../_files/2026-09-06/uat-round3/step54-charges-in-cart.png)
![Charge on the receipt](../../../_files/2026-09-06/uat-round3/step55-charge-on-receipt.png)

## Steps 56-58 — receipt format A4 vs roll, seen on paper. PASS. (M3, round 1.)

Settings switched to **A4**, the same receipt reopened. The button becomes **Print A4** and the
printed page is a full-width A4 document: the header centred, order line, items and totals laid
across the page rather than down an 80 mm strip, one page. Content is identical, including the
service charge line.

The tenant was **set back to thermal afterwards**, which is how Martin has it.

⚠️ **Worth knowing:** the on-screen preview stays roll-shaped in A4 mode; only the print output
changes. A client who switches the setting and looks at the preview will think nothing happened.

![A4 mode, preview and Print A4 button](../../../_files/2026-09-06/uat-round3/step57-a4-preview.png)
![The A4 page itself](../../../_files/2026-09-06/uat-round3/step57-a4-print.png)

## Step 59 — purchase order additional comments. PASS. (M2, round 1.) Plus a new defect.

**PO-260906-001** was raised for Al Maya Trading, 100 kg of Flour at AED 3.75, VAT 5%, total AED
393.75. The form carries **Delivery instructions** and **Additional comments** as separate boxes,
the list row prints both, and so does the PO document sent to the supplier, under the totals and
beneath FZ LLC's own name, TRN and Dubai address.

![PO form](../../../_files/2026-09-06/uat-round3/step59-po-form-cropped.png)
![PO row showing both notes](../../../_files/2026-09-06/uat-round3/step59-po-row-comments.png)
![The PO document](../../../_files/2026-09-06/uat-round3/step59-po-document.png)

### 🔴 New defect found here: tall dialogs are cropped and cannot be scrolled

**The New purchase order dialog is only usable at 67% browser zoom.** At 100% it is cut off top
and bottom and the **Create order button cannot be reached**, because the page behind a fixed,
centred dialog does not scroll.

**Cause and scope.** `components/ui/dialog.tsx:35`, the shared `DialogContent`, is `fixed` and
centred with **no max-height and no overflow**. That is not one page's bug: every tall dialog in
the product has it, including Create Ingredient and Add expense, and it gets worse on a phone
and on a short laptop screen.

**Fixed in this pass** by giving the shared dialog `max-h-[calc(100dvh-2rem)]`,
`overflow-y-auto` and `overscroll-contain`. `dvh` rather than `vh` so a mobile browser's
retracting address bar is accounted for.

## Step 60 — the back-office Customers screen. PASS. (M6 and M7, round 1.)

`Test UAT` is listed with **phone 0563326668**, Company/TRN showing "Individual", an address
column, **1 order** and spend. Search covers name, company, phone and TRN, and there is an Add
Customer button and a per-row Edit.

⚠️ Spent reads **AED 0.00 against 1 order**, the same paid-versus-placed distinction the Z-Report
showed. Consistent, and another reason to close the loop on payment for direct sales.

![Customers screen](../../../_files/2026-09-06/uat-round3/step60-customers-screen.png)

## Step 61 — bought vs made in-house, and the system-calculated cost. PASS. (M1, round 1.)

Editing **Cheese Sauce**:

* **Made in-house** is selected and **Bought is greyed out**, with the reason printed: *"An
  active recipe makes this ingredient. Delete that recipe first to mark it as bought."*
* **Cost per Unit is not an input.** It reads **AED 13.90** in a disabled box labelled
  *"Calculated from recipe. Edit the recipe to change it."*

That is Martin's sentence answered on screen: a bought item takes the price you pay, a
made-in-house item takes the price the system works out. The API check on 2026-09-06 already
proved the server drops a typed cost on such an item; this is the same rule visible in the UI.

![Made in-house, bought disabled](../../../_files/2026-09-06/uat-round3/step61-made-in-house-source.png)
![Cost calculated from the recipe](../../../_files/2026-09-06/uat-round3/step61-cost-from-recipe.png)

**All five items Malik asked about are now walked in a browser, not merely API-verified.**

---

# RE-VERIFICATION AFTER THE FIXES, on production at `d95c0f4`

Deploy: "Deploy to Production" green on `d95c0f4`. The served entry bundle is byte-identical in
name to the local build (`index-J-UhOo62.js`) and the cart chunk fetched from production contains
`How this order is handled`, `To kitchen` and `scrollbar-visible`, so the new code is the code
being served.

* **Step 63, the category fix, PASS on production.** `Packaging & Disposables` now reads
  **0 ingredients** with a live bin, and deleted. Before the fix it insisted on "1 ingredient"
  for an ingredient already removed and could never be deleted. The list also shows
  **Made In-House, 3 ingredients** after the rename away from "Produced".
* **Step 64, the header fix, PASS on a real phone.** All channel tiles are visible, including
  Pick up and Call Center, which could not be reached at all before.
* **Step 65, the currency race, PASS on the phone.** The till prices read **AED** on a fresh
  load. The fix is structural rather than lucky: the layout does not render its children until
  the tenant config has resolved, so there is no window in which a price can paint in the wrong
  currency.
* **Step 66, the call centre on a phone, PASS.** Tapping the Call Center tile, searching the
  number and selecting the customer now shows the menu.
* **Step 67, the "No customer found" contradiction, PASS on the laptop.** Search box, customer
  card, order history, menu and cart, with no empty-state message anywhere.
* **Step 68, tall dialogs, PASS.** New purchase order is fully usable at 100% zoom; the Create
  order button is reachable.
* **Step 69, the production preview, PASS.** After producing 1 kg the panel moved on its own to
  Butter 60.5, Flour 128.45, Milk 32.5, Mozzarella 18.75, exactly the predicted figures.
* **Steps 70-71, the cart, PASS after a second fix.** The first attempt raised the floor to 120px
  while a cart line was about 100px tall, so it still fitted one row. Shrinking the line itself at
  `lg` (36px stepper, tighter padding) and raising the floor to 9.5rem shows **two full rows**
  with the scrollbar visible. Deployed at `f907239`.
* **Step 72, the Z-Report label, PASS.** Sales by Channel reads **"Pick up", 6 orders, AED
  155.10**, alongside Call Center. His round-1 rename now reaches the report.

## Still open, deliberately not fixed in this pass

1. **The Z-Report reads zero revenue** beside channel totals of AED 164.10, because "settled"
   means paid and nothing was paid. Either the summary explains itself or a direct sale records
   a payment. Needs a decision, not a patch.
2. **Rendered timestamps are US-style** (`9/6/2026`) for a UAE client. Native date INPUTS follow
   the device and are not ours; the rendered ones are.
3. **`paid_on` defaults to the invoice date**, not the day it was paid.
4. **A produced item is valued at the recipe's saved cost**, and nothing recalculates it when an
   ingredient's price changes. Real accounting behaviour for a client whose whole ask is cost
   accuracy.

## Test data left on `martin-fz`

Orders `#260906-002` to `#260906-008`, two production runs (`UAT-2026-09-06` and
`PROD-20260906175404`) with the stock they consumed, `PO-260906-001` as a draft, customer
`Test UAT`, expense category `Bank Charges`, and the `Deliveroo` sales channel. Deliveroo is
meant to stay. The rest is ours to clear before Martin looks.
