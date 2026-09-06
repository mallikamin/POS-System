# FZ LLC — error log

Faults found on this client's tenant (`martin-fz`), what caused them and what fixed them.
Tenant-scoped on purpose: the repo-root `ERROR_LOG.md` keeps the lessons that generalise, this
file keeps everything that happened to Martin.

---

## 2026-09-06 — browser UAT of round 3. Eleven faults, none of which the API or the database could see.

Round 3 (M9-M13) was deployed at `b4505fa`, verified on the production database and walked over
the live API. Every check passed. **Then it was clicked in a browser for the first time and
eleven faults appeared.** Fixed in `d95c0f4` and `f907239`, re-checked on production.

Full record with screenshots: `UAT_RESULTS_2026-09-06.md`. Client copy of the report:
`_files/2026-09-06/uat-round3/UAT_FZ_LLC_2026-09-06.pdf`.

### 1. The till priced in rupees for a UAE tenant

* **Seen:** Butter Croissant "Rs. 9" on the phone. The same screen on a laptop, same minute,
  same build: "AED 9.00".
* **Cause:** `formatMoney` reads a module-level `activeCode` in `frontend/src/utils/currency.ts`
  that starts at `"PKR"` and is corrected only when `configStore.fetchConfig` calls
  `setActiveCurrency`. It is not reactive, so a component that has already painted a price never
  repaints. A phone on mobile data loses the race, a laptop on wifi wins it.
* **Fix:** `POSLayout` and `AdminLayout` hold their children until the config resolves, with
  `configError` as an escape hatch so a failed call degrades instead of trapping the user.
* **Note:** this is the same class as F15 (2026-08-28), which was patched by ISSUING the fetch
  earlier. Issuing is not enough; the fetch has to arrive.

### 2. Two channel tiles unreachable on a phone

* **Seen:** Pick up and Call Center could not be tapped, portrait or landscape.
* **Cause:** `POSLayout.tsx` header is `h-14 shrink-0`, a fixed 56 px, and the restaurant name
  inside it had no truncation. "FZ LLC — Bakery & Cafe (Demo)" wrapped to three lines and
  painted over the tiles.
* **Fix:** truncate the name (`min-w-0` on the flex child), `shrink-0` on the controls, clock and
  operator name hidden below `sm`.

### 3. The call centre could not take an order on a phone

* **Seen:** the customer was found, no menu ever appeared.
* **Cause:** the customer panel was `w-full shrink-0` and the menu was its flex-row sibling, so
  the menu was laid out off-screen with no width to give it.
* **Fix:** below `lg` the two swap, with a "Change" control to return to the search.

### 4. A deleted ingredient held its category hostage

* **Seen:** delete the only ingredient in a category and the category still reads "1 ingredient"
  with its delete disabled, forever, with nothing on screen to explain why.
* **Cause:** ingredient delete is a SOFT delete (`recipe_service.delete_ingredient` sets
  `is_active = False`); the in-use count in `ingredient_category_service` counted every row.
* **Fix:** active-only counts in the guard, the display and the orphan self-heal. Rename still
  moves every row but reports only the active ones. Covered by
  `test_a_deleted_ingredient_does_not_hold_its_category_hostage`, confirmed to fail without the
  service change.

### 5. The production preview went stale after a run

* **Cause:** `handleRefresh` reloaded only the run history and nothing refetched the preview, so
  the on-hand figures, and therefore the shortfall warning, kept the pre-run values.
* **Fix:** a `stockNonce` re-runs the preview after a run and on Refresh.

### 6. Tall dialogs cropped with unreachable buttons

* **Seen:** New purchase order was usable only at 67% browser zoom.
* **Cause:** the shared `DialogContent` is fixed and centred with no max-height and no overflow.
  Every tall dialog in the product was affected.
* **Fix:** `max-h-[calc(100dvh-2rem)]`, `overflow-y-auto`, `overscroll-contain`, once, centrally.

### 7. The cart showed one line at a time

* **Cause:** the lines region is `flex-1` between a header and a footer that grew with the M13
  switch. **Two attempts:** raising the floor to 120 px did nothing because a cart line is about
  100 px tall.
* **Fix:** compact the line itself at `lg` (36 px stepper, tighter padding) and raise the floor to
  9.5rem. Two full rows, with a visible scrollbar utility.

### 8-11. The smaller ones

* The fulfilment switch and the action button both read "Send to kitchen". Switch now reads
  "To kitchen / Print & deduct" under a caption.
* The ingredient form opened on a category called "General" that this tenant does not have, and
  saving created it. It now opens on the tenant's first real category.
* The call centre printed "No customer found" directly above the customer it had found: the
  no-results block was missing the `!selectedCustomer` guard the results block already had.
* The Z-Report said "Takeaway" where round 1 renamed the channel to "Pick up". It now reads
  `config.takeaway_label`.

### Also corrected on this tenant

* The seeded category **"Produced"** sat one letter from **"Produce"**, the fresh-veg category.
  Renamed to "Made In-House".
* **Deliveroo** was missing from Sales Channels and was added, at 5% as a placeholder.

---

## 2026-09-06 — a verification harness that read a schema, not the server

* **Seen:** the first API verification of Martin's twelve asks reported 14 failures. Eleven were
  false.
* **Cause:** production does not expose `/openapi.json`; the SPA answered 200 with `index.html`,
  `.json()` threw, and every field check returned False for the same wrong reason.
* **Rule:** verify against the running server's behaviour, not its description of itself. And when
  eleven checks fail across six unrelated features, suspect the harness.

## 2026-09-06 — "every channel is on 0% commission" was recorded and was false

* The API check recorded every sales channel at 0%. Read in a browser the same day: Careem, KEETA
  and noon at 30%, card at 3% plus AED 1, wholesale at a flat AED 30.
* Retracted in `API_VERIFICATION_2026-09-06.md`. **It never reached Martin.**
* ⚠️ **KEETA carries the code `talabat`**, being a rename of the seeded row. A channel code cannot
  change once orders reference it, so a future real Talabat channel needs a different code.

## 2026-09-04 — a Pydantic response default hid a wrong number

* A goods receipt reported `units_per_purchase_unit: 1.0` while Postgres held `400.0000`. The
  hand-built response model carried `= 1` as a default and the builder never passed the field.
* **Rule:** a response schema built field by field must not give its fields defaults. Full entry
  in the repo-root `ERROR_LOG.md`.
