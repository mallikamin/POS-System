# Martin's feedback, round 3 (received 2026-09-06)

Source: Martin Zubeldia (FZ LLC), WhatsApp, after reviewing the round-1 and round-2 builds on
tenant `martin-fz` at https://eats.sitaratech.info.

Status key: OPEN · BUILT (local, untested on prod) · DEPLOYED (live, verified) ·
ANSWERED (no build needed, reply sent).

## Verbatim

Message 1, 12:56 GST:

> I forgot to mention here.
>
> There is no production menu where I can produce subrecipes (example, producing tomato
> sauce or dough or anything) and then this will be added as stock (+ sauce) and at same
> time the ingredient reduced (-tomato raw item)
>
> There is no expenses menu to attach the invoices of my expenses (not the ones from
> suppliers which are already in the receiving of ingredients, but other expenses such as
> rent, salaries etc...)

Message 2, 13:00 GST:

> Ingredients
> Theres a fixed set of Categories. Don't see a menu or drop-down menu where I can add a
> category

Message 3, 13:04 GST, with a screenshot of the Takeaway till on his phone (a tall empty
white area above a cart squeezed into the bottom fifth of the screen):

> How it looks on the phone still bad

Message 4, 13:10 GST, with a screenshot of the cart footer arrowed at the total and the
"Send to Kitchen" button:

> Need to have option here to either send to kitchen / then ready / then dispatched as it is
> now. And at that time is deducted from inventory OR directly print and deducted from stock

## Items

| # | Area | Martin's ask | Status |
|---|------|--------------|--------|
| M9 | Production | A production screen: make a sub-recipe batch, add the output to stock, deduct the inputs | BUILT |
| M10 | Expenses | An expenses screen with invoice attachments, for non-supplier costs (rent, salaries) | BUILT |
| M11 | Ingredients | Add and manage ingredient categories | BUILT |
| M12 | Mobile | Admin portal AND the till still look bad on a phone, after M7 | BUILT |
| M13 | POS checkout | A choice at the cart: run the kitchen flow as today, or print and deduct stock straight away | BUILT |

🔴 **BUILT, not DEPLOYED, and not seen.** Everything above is proven on a real Postgres
locally and by 25 route-level tests. **Nothing has been clicked in a browser.** The
step-by-step script is `UAT_FZ_LLC_2026-09-06.md` in this folder. Do not reply to Martin
until it has been walked, on a laptop AND on a phone.

## What each one actually means against the code

### M9 — the engine exists, the screen does not

**Verified by reading the code, not assumed.** `backend/app/services/production_service.py`
already does exactly what Martin describes: `run_production` consumes every input at the
recipe's quantity plus its waste factor, adds `yield_servings x batches` of the produced
ingredient, and writes both sides through `stock_service.move_stock`, so no balance can move
without a movement row explaining it. It is exposed at `POST /locations/production/run` and
covered by tests in `test_location_service.py`.

**So Martin is not asking for the mechanism. He is telling us he could not find it**, and he
is right: it is a button on the Stock screen, not an entry in the admin menu, and there is no
Production item in `AdminLayout`'s nav at all. Three real gaps behind the complaint:

1. **No menu entry.** Nothing in the sidebar says the word "Production".
2. **No history.** A run leaves two `inventory_transactions` rows sharing a `PROD-...`
   reference and nothing lists them, so there is no answer to "what did we make yesterday".
3. **It asks for "batches", not for an amount.** A chef thinks "make 5 kg of tomato sauce",
   not "run the recipe 2.5 times". The dialog only accepts the second.

### M10 — genuinely absent

There is no expense model, table, endpoint or screen anywhere in the backend. Grepping the
whole of `backend/app` for "expense" returns only QuickBooks account-mapping code, which
classifies *QuickBooks* expense accounts and stores nothing of its own.

Martin has drawn the boundary himself and it is the right one: **money paid to a supplier for
ingredients already has a home** (purchase order, goods receipt, stock movement, cost per
unit). What has no home is every other cost that hits the P&L: rent, salaries, utilities,
licences, marketing, maintenance. He wants those captured with the invoice attached.

### M11 — the set is not fixed, but nothing says so

**The category is a free-text box today**, not a fixed list:
`IngredientManagementPage.tsx` renders `<Input placeholder="e.g., Meat, Grains, Spices">` on
both the create and the edit form, and `ingredients.category` is a plain `String(100)`.
Typing anything at all creates that category.

So the literal claim is wrong, and the complaint is still correct. There is no list of
categories anywhere, no dropdown, and no screen that manages them. The only thing that looks
like a set is the filter at the top of the Ingredients screen, which is built from the
distinct values already in use, so it reads as a closed list. And a free-text box across
forty ingredients guarantees "Dairy", "dairy" and "Diary" all become real categories.

### M12 — M7 fixed the door, not the room

**M7 was not oversold, but it was narrower than it sounded.** Martin's round-1 words were
*"on the phone you can't really enter the sections of the admin portal"*, and that is a
navigation complaint. M7 fixed three real defects in the navigation drawer: the overlay
painted over it so every tap closed it, it pushed the page instead of floating above it, and
nothing closed it after a tap. Those are fixed. **Nothing was ever done to the pages
themselves**, and STATE.md has said since 2026-09-02 that the pixels were never seen in a
browser.

Three concrete faults, all read from the code rather than guessed:

1. 🔴 **The page cannot be zoomed.** `frontend/index.html` ships
   `maximum-scale=1.0, user-scalable=no`. That was a deliberate POS choice, to stop a
   double-tap zoom mid-service on a till. On the admin portal it is the single worst thing
   on the list: when a table is too wide to read, the phone will not let him pinch out to
   read it either.
2. 🔴 **`w-full` inside `overflow-x-auto` never scrolls, it crushes.** A table told to be
   exactly its container's width cannot overflow that container, so the scroller wrapping it
   does nothing and eight columns are squeezed into 360 px of slivers. This is the pattern on
   Ingredients, Customers, Staff, Stock, Suppliers, Profitability and more.
3. 🔴 **Several tables have no scroller at all** (Roles, Reports, Purchase Orders,
   Quotations, Order Planner, Z-Report), so they push the whole page sideways.

The fix is not decoration. It is: let the phone zoom, give every wide table a real minimum
width so its scroller works, and give the screens Martin actually opens a stacked card
layout below `sm` instead of a table nobody can read.

## What is NOT in this round

Nothing from rounds 1 and 2 is reopened. M1-M7 are deployed at `36ae70f`, M8 at `218ac8e`,
both verified on the production database.

## Commercial follow-ups, still open

Unchanged from round 2, and now three rounds deep:

- "once this changes are done lets have a demo call with my partners"
- "ideally instead of demo call my partners will prefer a meeting in your dubai office"

Malik's instruction for this round: **build everything, then walk a step-by-step UAT, then
reply to Martin once** with the whole set confirmed.

## What was built, item by item (for the reply to Martin)

**M9 Production.** A **Production** entry in the admin menu, between Stock and Transfers.
Pick what you are making, pick the site, and say either how much you want or how many
batches; typing one fills in the other, because a chef thinks "5 kg of sauce", not "6.25
runs of the recipe". Before you press anything the screen shows what will go onto the shelf
and every ingredient that will come off it, with what is on hand and what is short. The
arithmetic is done on the server by the same two lines the run itself uses, so the preview
and the result cannot disagree. Below that, a history of what has been made, each run showing
its inputs. A shortfall is shown in red but does **not** block the run: a kitchen that has
already made the sauce needs the system to record it, not refuse it.

**M10 Expenses.** A new **Expenses** screen. Each expense carries a date, who was paid, a
category, the invoice total, the VAT inside that total, their invoice number, how it was
paid, and a status of unpaid, paid or draft. The invoice itself is attached as a PDF or a
photograph and opens from the list. Four totals across the top for the period: total, net of
VAT, still to pay, and the biggest category. Ten categories are there from the start (Rent,
Salaries & Wages, Utilities, Marketing, Repairs & Maintenance, Licences & Government Fees,
Transport & Delivery, Professional Fees, Insurance, Other) and more can be added from the
form itself.

Three decisions worth stating to him rather than letting him find:

- **The amount is the whole invoice and the VAT box is the part of it that is VAT**, not an
  extra added on top. That is how a UAE invoice reads, and it is what the recoverable input
  VAT figure comes from. Entering a VAT larger than the total is refused.
- **A draft expense is excluded from every total.** A half-entered invoice is not money owed.
- **Nothing here touches stock.** Ingredient purchases stay where they already are, on the
  purchase order and the goods receipt. Putting them here too would double-count the food
  cost in every report that adds the two together.

**M11 Ingredient categories.** The category field is now a dropdown of what exists, with
"New category" beside it. A category typed there joins the list on save. A **Categories**
button on the Ingredients header opens the full list, showing how many ingredients each holds;
from there a category can be renamed, which moves every ingredient filed under it at the same
time, or removed once nothing uses it. Typing "dairy" when "Dairy" already exists files under
"Dairy" rather than creating a second one. The filter at the top of the screen now reads the
same list; it used to be built from whatever happened to be on screen, so choosing a category
collapsed the dropdown to that one entry.

**M12 The phone.** Three real faults, all fixed:

1. **The page could not be zoomed.** The app shipped `user-scalable=no`, a deliberate choice
   for a till, where a double tap must not zoom the button grid mid-service. On the admin
   portal it was the worst thing on the list: when a table was too wide to read, the phone
   would not let him pinch out to read it either. Zoom is back; double-tap zoom is still
   suppressed on buttons and inputs, which is what the lock was really for.
2. **Wide tables were crushed, not scrollable.** A table told to be exactly its container's
   width cannot overflow it, so the scroller wrapped around it did nothing and eight columns
   became slivers. Every admin table now has a readable minimum width and a scroller that
   works. Fifteen tables that had no scroller at all were given one. Print is unaffected --
   the scrollers are switched off on paper, or the Z-report would print with its right-hand
   columns clipped.
3. **The till was a three-column desktop layout on a 360px screen.** That is the screenshot he
   sent: a fixed 320px cart beside a fixed 256px floor plan leaves the menu nothing. On a
   phone the menu now fills the screen and the order is a sheet that opens from a bar at the
   bottom. On a laptop or a landscape tablet nothing changed at all.

**M13 Kitchen or straight through.** A two-way switch above the submit button on the till.
"Send to kitchen" is the default and is exactly what happens today: the order goes to the
kitchen board and stock comes off when it is completed. "Print & deduct now" completes the
order in the same action, opens the receipt, writes no kitchen ticket, and takes the stock off
immediately. It is per order, not per restaurant, because the same till takes a wholesale line
that never sees a kitchen and a pick-up order that does. **The switch is hidden in pay-first
mode**, where payment is what releases an order and completing it at the till would book stock
against a sale nobody has paid for.

## Proof so far

- `backend/tests/test_martin_round3.py`, 25 route-level tests, green.
- 1009 green across the whole backend suite. The 11 failures and 2 errors that remain
  reproduce identically on a clean worktree at HEAD, so none of them are new.
- Frontend type-check clean, production build clean, lint back at its pre-existing baseline.
- Migration `f6a7b8c9d0e1` run against real Postgres 16 locally: four new tables, the CHECK
  constraints in place, downgrade drops them, re-upgrade backfills identically, and all 16
  local ingredients came through untouched.
- **Walked over the real API on Postgres, not only SQLite:** the tomato-sauce example both
  ways with the preview proven to write nothing; a rent invoice with its VAT carved out, its
  PDF attached and read back byte-for-byte, refused to an unauthenticated caller; and a direct
  sale completing and deducting stock on the spot while a normal order still landed in the
  kitchen and deducted nothing. Every probe row was removed afterwards.

🔴 **Not verified: the pixels.** See `UAT_FZ_LLC_2026-09-06.md`.

## Limits to state, not to let him find

- **A production run does not cascade.** Producing croissants consumes dough; it does not
  quietly produce more dough first. If the dough has run out that shows as a negative dough
  balance for a human to act on, which is the honest answer.
- **Expenses do not yet feed the profitability report.** That report is food cost against
  sales; rent and salaries are a P&L line above it. Wiring the two together is a decision
  about what "profit" means on that screen, not a bug.
- **An expense invoice is stored in the database like every other uploaded file**, and is
  capped at 5 MB by nginx.
