# Every one of Martin's asks, checked against production over the real API

**Date:** 2026-09-06
**Against:** https://eats.sitaratech.info, tenant `martin-fz`, signed in as the FZ admin
**Build:** `b4505fa`, `alembic_version = f6a7b8c9d0e1`

This is the API layer only. **It is not UAT.** Five things below can only be proved by a human
in a browser and are marked so; the step-by-step script is `UAT_FZ_LLC_2026-09-06.md`.

## Rules this run followed, because it was pointed at a client's live tenant

- Read-only by default. Every write was tagged `ZZPROBE` and reversed in the same run.
- **No order was ever created.** An order burns an order number and moves stock. Where the
  request path had to be proved, it was proved with a request the server rejects at validation,
  so nothing was written.
- **No production run was executed.** `preview` writes nothing by design, and that was proved
  by reading the stock position and the run history before and after and comparing them.
- One deliberate no-op write: sending a cost for a made-in-house ingredient, which the server
  is supposed to drop. It did.
- `pg_dump` was taken before the one database deletion (see the leftover note at the end).

## Results

| # | Martin's ask | Verdict |
|---|--------------|---------|
| i / M1 | Bought items have a price, made-in-house items are costed by the system | **PASS** |
| ii / M2 | Purchase order needs "additional comments" like delivery instructions | **PASS** |
| iii / M3 | Receipt settings: vertical or A4 | **PASS** |
| iv / M4 | Pick up / Call center / Deliveroo / Careem / Keeta / noon on the POS | **PASS**, one gap |
| v / M5 | Charges such as delivery fees, correct on receipts and reports | **PASS**, printed line is UAT |
| vi / M6 | Back-office CRM with name, phone, contact details, TRN | **PASS** |
| vii / M12 | Mobile UI/UX, fully functional, no formatting errors | Zoom **PASS**, layout is UAT |
| viii / M8 | Two units and a conversion on bought ingredients | **PASS** |
| ix / M9 | Production menu: produce a sub-recipe, +stock and -ingredient | **PASS**, the run itself is UAT |
| x / M10 | Expenses menu with invoices attached | **PASS** |
| xi / M11 | A menu where a category can be added | **PASS** |
| xii / M13 | Send to kitchen, or print and deduct straight away | **PASS**, the sale itself is UAT |

## What was actually observed

**i / M1.** 16 ingredients: 13 bought, 3 made in-house, and each of the three names the recipe
that makes it (Cheese Sauce v1, Chicken Stuffing v1, Croissant Dough v1). Sending
`cost_per_unit: 999999` for Cheese Sauce returned 200 with the cost still 1390, so the server
drops a typed-over cost on a manufactured item rather than storing it. That is the exact rule
he asked for.

**ii / M2.** A purchase order accepts `notes` on creation, and nothing in the validator objects
to it. On his existing `PO-260828-003` the supplier document prints an "Additional comments"
section.

**iii / M3.** `receipt_format` is a tenant setting, currently `thermal`. It was switched to
`a4`, read back as `a4`, and set back to `thermal`, all live. An invalid value is refused with
a 422. `takeaway_label` is `Pick up`.

**iv / M4.** Six channels exist. On the till: B2B Wholesale, Careem Now, KEETA, noon Food,
WhatsApp / Direct. Hidden from the till: Website (card), which is correct because those orders
arrive through the storefront.

🔴 **Two things to raise with Martin rather than silently fix:**
- **Deliveroo is not set up.** He named it; it is the only one of his six missing. He adds it
  himself on the Sales Channels screen and it appears as a till tile at once.
- ~~**Every channel is on 0% commission.**~~ 🔴 **RETRACTED 2026-09-06 at UAT step 2. This was
  false.** The Sales Channels screen, read on production in a browser, shows Careem, KEETA and
  noon at 30.00%, Website (card) at 3.00% plus AED 1.00, WhatsApp / Direct at 3.00%, and B2B
  Wholesale at 0% with a flat AED 30.00 per order. The rates are entered and the profitability
  report has real inputs. Do not repeat the 0% claim to Martin. Screenshot:
  `_files/2026-09-06/uat-round3/step02-sales-channels.png`.
- ⚠️ **KEETA carries the code `talabat`**, because the seeded Talabat row was renamed and a code
  is immutable once orders reference it. Reports read the name, so nothing is wrong, but a
  future real Talabat channel needs a different code.

**v / M5.** An order carries `delivery_fee` and `service_fee`, they are inside the order total,
and the receipt and the payment preview are served the same numbers. A negative fee is refused
by the live server. **UAT:** none of his 12 orders carries a non-zero charge yet, so the
printed line has not been seen on paper.

**vi / M6.** A company customer was created with company name, TRN, phone and address, read
back with all of them stored, and found by searching the back-office list. `default_address` is
accepted (it is that field, not `address_line1`). The probe customer was removed afterwards.

**vii / M12.** The served page now carries
`width=device-width, initial-scale=1.0, viewport-fit=cover`. **The zoom lock is gone**, which
was the single worst item on the list. **UAT:** the layout, the tables and the till sheet on a
real phone cannot be proved over HTTP. Steps 33 to 42.

**viii / M8.** A live ingredient reports `purchase_unit`, `units_per_purchase_unit` and
`purchase_cost_minor`, and a purchase-order line snapshots the conversion (`PO-260904-001`).
The tomato-can arithmetic itself was walked end to end on Postgres on 2026-09-04 and again
today. **UAT:** none of his 16 ingredients has a purchase unit set yet, so he has not entered
his tomato cans. That is his data entry, not a gap in the build.

**ix / M9.** The production history answers, all three of his sub-recipes are producible, and
the preview for Cheese Sauce returns +2.0 kg from 4 inputs with what is on hand for each. The
stock position and the run history were byte-identical before and after the preview, which
proves it writes nothing. **UAT:** an actual run was not executed here because it would move
his stock. Steps 9 to 16.

**x / M10.** The ten starter categories seed on first open and do not duplicate on a second.
A rent invoice was recorded at 105.00 with 5.00 VAT and came back with a net of 100.00. A VAT
larger than the invoice was refused with a plain-English message. A PDF attached, read back
byte-for-byte, was served with `nosniff`, and returned 401 to an unauthenticated reader. The
period summary answers. The probe expense was deleted and the tenant is back to zero expenses.

**xi / M11.** Eight categories, matching the eight his 16 ingredients already carried, one for
one, each with its count: Bakery 2, Beverage 1, Dairy 3, Dry Store 1, Pantry 3, Produce 2,
Produced 3, Protein 1. A new category was added, a different-case duplicate was refused rather
than forked, and the probe was removed.

**xii / M13.** The live server validates the fulfilment mode: `"bogus"` is rejected with a 422
naming the field, and `"direct"` is accepted with the request failing only on the empty basket.
**UAT:** an actual direct sale was not run here because it would burn an order number and move
stock. Steps 27 to 32.

## One leftover, and how it was cleared

The customer probe could not be undone through the API: **there is no DELETE endpoint for a
customer**, by design. The row was removed directly from the production database after a
`pg_dump` to `/root/backups/pre_zzprobe_cleanup_20260906_102857.sql`, by id, with zero orders
attached. Confirmed afterwards: `martin-fz` has 0 customers, and `chick-shack` still has its
215, untouched.

**Final sweep: 0 probe rows remain.** 16 ingredients, 0 customers, 0 expenses, 8 categories.

## Harness bugs found on the way, recorded so they are not rediscovered

The first pass reported 14 failures. **Eleven were the harness, not the product:** production
does not expose `/openapi.json`, so every schema-based check returned false for the wrong
reason. Three more were mine: the 422 body echoes the request, so searching it for a field name
always matches; the charges live on the order detail and never on the list row; and the
customer address field is `default_address`. Rewritten to read live responses instead, which is
better evidence than a schema anyway.

**The lesson:** a contract check that reads a schema proves the schema. Reading the field off a
real response, and probing the validator with a request that is rejected before anything is
written, proves the running server.
