# Martin's feedback, round 2 (received 2026-09-04, 12:25-12:26 GST)

Source: Martin Zubeldia (FZ LLC), WhatsApp, after reviewing the round-1 build on tenant
`martin-fz` at https://eats.sitaratech.info. He sent a screenshot of the **Create Ingredient**
modal (the round-1 screen) and three messages against it.

Status key: OPEN · BUILT (local, untested on prod) · DEPLOYED (live, verified) ·
ANSWERED (no build needed, reply sent).

## Verbatim

> [screenshot: Create Ingredient modal - Name, Photo, Category, Unit, Source (Bought /
> Made in-house), Cost per unit (AED)]
>
> Ingredients bought Need to have 2 units and a conversion.The unit you buy, the unit you
> store)use in recipes
>
> Dfor example, I buy tomato cans..so in the purchase order I will request 2 cans
>
> But in my recipes I use grams

Malik's reply, 12:28: "Hey martin. Thanks for this. I am noting all your feedback - will
send u a detailed update once all is ready and tested"

## Items

| # | Area | Martin's ask | Status |
|---|------|--------------|--------|
| M8 | Ingredients | A bought ingredient needs **two units and a conversion**: the purchase unit (can) and the stock/recipe unit (g). Purchase orders are placed in purchase units, recipes consume stock units, and the cost converts between them. | BUILT (local) |

## What this actually means in the data

Today an ingredient has exactly one `unit` and one `cost_per_unit`, and that single unit is
used by recipes, stock on hand, purchase order lines, goods receipts and the supplier
catalogue alike. Martin's tomato can breaks that: he orders 2 **cans**, the kitchen consumes
**grams**, and the cost of a gram is only knowable from the price of a can divided by the
grams in it.

`supplier_items.pack_size` is NOT this. It is "25 kg per sack", a rounding aid expressed in
the *same* unit, scoped to one supplier. Martin's conversion is a property of the ingredient
itself and changes the unit the number is expressed in.

Everything downstream of a purchase has to convert: goods receipt books stock in stock units,
the ingredient's cost per stock unit is derived not typed, and the reorder suggestion has to
turn "we are 900 g short" into "order 3 cans".

## Commercial follow-ups from round 1 (not build items)

Carried over from the 2026-09-02 messages, still open:

- "once this changes are done lets have a demo call with my partners"
- "ideally instead of demo call my partners will prefer a meeting in your dubai office"

So the round-1 + round-2 build closing out is the trigger for a partner meeting, and Martin's
partners want it **in person in Dubai**, not a call. That is a scheduling and logistics
question for Malik, not a build item, and it should be answered in the same reply that
confirms the build.

## What was built (for the reply to Martin)

An ingredient now keeps the unit it is **stocked and cooked in** (`unit`, unchanged) and,
optionally, the unit it is **bought in**, with the number of stocking units in one of them.
Martin's tomatoes: stocked in `g`, bought by the `can`, 400 g per can, AED 8.50 a can.

- **Ingredients screen.** The unit field is relabelled "Unit I store and cook in". Under the
  Bought / Made in-house switch there is a checkbox, "I buy this in a different unit from the
  one I cook with". Off, the form is the single cost box it has always been. On, it asks what
  he buys it in, how many stocking units are in one, and what one costs, then shows the cost
  per stocking unit as a computed line. That computed cost is **not typeable**: the price of a
  can is the input and the cost of a gram falls out of it, so the two can never disagree.
- **Purchase orders** are written in purchase units. The ingredient reads "(can)" in the
  dropdown, the quantity box says "Qty (can)", and typing 2 shows "= 800 g" underneath.
- **The supplier document** asks for "2 can" and prints "= 800 g" under it, so whoever checks
  the delivery in can see the weight without doing arithmetic.
- **Goods receipts** book stocking units. Two cans received puts 800 g on the shelf at the
  cost of a gram, not two units at the cost of a can.
- **Recipes** are unchanged. They are still written and costed in grams.
- **The order planner** converts a shortfall in grams into a whole number of cans, rounding
  up, because you cannot buy a quarter of a can.
- **Cost rates gained two decimal places.** 8.50 for a 400 g can is 2.125 fils a gram, and at
  two places that rounded to 2.13, restating the can at 8.52. Widened to four places on the
  ingredient cost, the recipe snapshot and the stock movement. Money actually charged stays at
  two.

### A limit to state, not to let him find

The conversion belongs to the **ingredient**, not to the supplier. One tomato can is 400 g
whoever sells it. If two suppliers ship genuinely different can sizes for the same
ingredient, that is a follow-up, not something this build handles.

### Proof so far

- `backend/tests/test_martin_round2.py`, 12 route-level tests, green. 147 green across every
  touched backend suite. Frontend type-check clean; lint unchanged from its prior state.
- **Migration `e5f6a7b8c9d0` run against real Postgres 16 locally**, parented on production's
  head `d2e3f4a5b6c7`. Columns landed at the right precision, the conversion check constraint
  refuses zero, and downgrade/upgrade round-trips. Nothing already in the database moved:
  all 16 ingredients came out with no purchase unit and a conversion of 1.
- **The tomato example walked end to end over the real API on Postgres**, not just SQLite:
  2.125 fils a gram stored exactly, a PO priced at AED 17.00 for two cans, 800 g booked into
  stock, and the cost per gram unchanged after receiving.
- One bug found and fixed on the way: the goods-receipt response builder did not pass the new
  conversion field, and the schema's default of 1 filled it in silently while the database
  held 400. See `ERROR_LOG.md`, 2026-09-04.

**Not verified: the pixels.** Nothing has been clicked in a browser, and nothing is on
production. `UAT_FZ_LLC_2026-09-04.md` in this folder is the step-by-step script to walk
after deploying, covering M1-M8.
