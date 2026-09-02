# Martin's feedback, round 1 (received 2026-09-02)

Source: Martin Zubeldia (FZ LLC), written feedback after his review of the demo tenant
`martin-fz` on https://eats.sitaratech.info. Quoted verbatim below, then broken into
numbered items with status. Status key: OPEN · BUILT (local, untested on prod) ·
DEPLOYED (live, verified) · ANSWERED (no build needed, reply sent).

## Verbatim

> Ingredients. There is no difference between bought items (flour, coca cola cans, fruits)
> which have a price and ingredients manufactured by us, whre the price needs to be
> calculated by the system
>
> purchase order
> needs to have a section with ''additional comments'' same as there is delivery
> instructions
>
> receipt settings. need to have option to either print a vertical receipt or an a4 format
>
> pos
> there is only option for take away or call center
> there should be
> pick up / call center / deliveroo / careem / keeta / noon
>
> need to have option to add charges (such as delivery fees for exmaple)
>
> i didnt see a menu in back office with crm options (where i can add customer
> name/phone/contact details/ trn if it is a company)

> Also, on the laptop works perfect. On the phone you can't really enter the sections of
> the admin portal

## Items

| # | Area | Martin's ask | Status |
|---|------|--------------|--------|
| M1 | Ingredients | Distinguish bought items (price entered) from items we manufacture (price calculated from the recipe) | BUILT 2026-09-03 |
| M2 | Purchase order | "Additional comments" field alongside delivery instructions | BUILT 2026-09-03 |
| M3 | Receipt settings | Choose vertical (thermal roll) or A4 receipt format | BUILT 2026-09-03 |
| M4 | POS channels | Pick up / Call center / Deliveroo / Careem / Keeta / Noon instead of only Takeaway / Call center | BUILT 2026-09-03 |
| M5 | Charges | Add charges to an order, e.g. delivery fee | BUILT 2026-09-03 |
| M6 | CRM | Back-office customer screen: name, phone, contact details, TRN for companies | BUILT 2026-09-03 |
| M7 | Mobile | Admin portal sections cannot be entered on a phone | BUILT 2026-09-03 |

BUILT = in the working tree with route-level tests green (`backend/tests/test_martin_round1.py`,
11 tests) and the frontend type-check and lint clean. Not yet deployed, not yet seen on a screen.
Update this table to DEPLOYED only after the production walk.

## What was built, item by item (for the reply to Martin)

**M1 Ingredients.** The distinction always existed in the data (`ingredients.is_produced`,
set by the recipe engine when a sub-recipe produces the ingredient); the Ingredients screen
never showed it, and let a calculated cost be typed over. Now:
- A **Source** column on every row: "Bought" or "Made in-house", the latter with the name
  of the recipe that makes it, or "No recipe yet. Build one" when there is none.
- A source filter (bought only / made in-house only).
- Create form: a Bought / Made in-house switch. Made in-house hides the cost and supplier
  fields and explains the cost will come from the recipe.
- Edit form: for a made-in-house ingredient the cost is read-only and says "Calculated from
  recipe. Edit the recipe to change it." The server also drops any cost sent for a produced
  ingredient, and refuses to flip one back to "bought" while an active recipe makes it.
- Cost roll-up itself is unchanged: snapshot on recipe save (a parent recipe picks up a new
  sub-recipe cost the next time it is saved). Worth saying to Martin plainly.

**M2 Purchase orders.** An "Additional comments" box under Delivery instructions on the
create form. Stored in the PO's existing `notes` column, shown on the order detail, and
printed on the supplier document (text and HTML) under its own heading, below the delivery
instructions. Previously `notes` was internal-only and printed nowhere.

**M3 Receipt format.** Settings > Receipt Template now has "Vertical (80mm roll)" or
"A4 page". Stored per tenant (`restaurant_configs.receipt_format`). The receipt preview is
the same; Print opens either the 80mm slip (unchanged from today) or an A4 page with a
proportional font and page margins. Also on Settings: "Name for the walk-in channel",
which is set to "Pick up" for martin-fz by the migration.

**M4 Channels on the POS.** Deliveroo, Careem, Keeta, Noon are *sales channels* (they carry
a commission, which is what the profitability report needs), not order types. Each sales
channel with "Show on the POS" ticked (Sales Channels screen, new switch, default on) gets
its own tile on the channel screen beside Pick up and Call Center. Tapping one opens the
walk-in till with the sale attributed to that channel; the header badge and the order card
then read "Careem Now" rather than "Takeaway". The website channel is switched off by the
migration because those orders arrive through the storefront. **Martin's tenant today has
Talabat, Careem Now, noon Food, Website, WhatsApp/Direct, B2B Wholesale. He adds Deliveroo
and Keeta himself on the Sales Channels screen; they appear as tiles at once.**

**M5 Charges.** On the cart, "Add charges (delivery fee, service charge)" opens two amount
boxes. Both print as their own lines on the receipt and the payment screen, and are kept
through payment-mode re-totals and discounts. **Decision to state to Martin: charges sit
outside the VAT**, exactly as the online channel has always treated its delivery and
service fees. If FZ LLC needs VAT charged on delivery fees (UAE FTA treats delivery as a
taxable supply), that is a follow-up, not a default I chose silently.

**M6 Customers.** New admin screen: Admin > Customers. List with search (name, company,
phone, TRN), create and edit, with a "This customer is a company" switch that reveals
Company name and TRN. Address, city, alternative contact, notes, and (on edit) the
normal / high-risk / blocked status. A tax invoice issued to a company customer now names
the company and prints its TRN (and its address, which was silently never printed before).

**M7 Phone.** Three real defects in the admin drawer below 1024px: the dim overlay painted
over the drawer so every tap closed it; the drawer pushed the page instead of floating over
it; nothing closed it after navigating. All three fixed, the menu button is a proper 44px
target, and the content padding is smaller on a phone. The pinch-zoom lock in the viewport
meta was left alone (deliberate POS choice).

## Notes

- M1: the system already has sub-recipes (Croissant Dough is one, cost rolls up from the
  recipe). What Martin is saying is that the Ingredients screen does not *show* the
  difference, and lets a manufactured item's cost be typed over.
- M6: TRN = UAE Tax Registration Number, needed on tax invoices to companies.
- M7: "works perfect on the laptop" is his first positive line. The phone finding matches
  batch-2 F10 territory (AdminLayout nav), not a backend issue.
- Two pre-existing bugs found on the way and fixed in the same batch (see `ERROR_LOG.md`
  2026-09-03): applying a discount re-totalled the order as `subtotal + tax - discount`
  regardless of the tenant's tax convention (double-charging VAT for a tax-inclusive
  tenant), and the tax invoice read the customer address from a field that does not exist.
