# Discovery notes — FZ LLC (Martin Zubeldia), UAE

Source documents:
- `refs/2026-08-24_client-scope-of-work.docx` — client's own scope-of-work document, "Requirement Discussion: 24 August 2026" (verbatim copy at `refs/2026-08-24_client-scope-of-work.md`)
- `voice-notes/2026-08-26_martin_pos-workflow-walkthrough.mp4` — ~18-minute recorded walkthrough, transcript pending

## Who

| | |
|---|---|
| Business | Not yet named in the scope doc — signed "FZ LLC" (likely a generic UAE free-zone entity suffix, not the trading name) |
| Client contact | **Martin Zubeldia** |
| Sector | Bakery/restaurant, per Malik — **no dine-in** (takeaway/delivery/procurement-driven operation) |
| Location | UAE |
| Prepared by | FZ LLC (client's own doc header — needs clarifying, see Open Questions) |

## What they asked for (from the scope-of-work doc)

A **web-based POS + Inventory + Procurement system**, deliberately narrow — explicitly *not* a
full CRM/marketing platform. Two interconnected modules: POS and Inventory & Procurement, with
sales automatically deducting from the relevant location's inventory.

1. **POS module** — menu-based order entry, items/modifiers linked to inventory ingredients,
   automatic deduction on sale, location-based sales/stock, tax-invoice-compliant A4 invoices
   (VAT + full company name) as well as ticket printing, back-office quotations, light B2C CRM
   (name/phone/address, non-mandatory), and per-channel sales recording for profitability.
2. **Inventory management** — item/ingredient master, current + location-wise stock, auto
   deduction on sale / auto addition on receipt, authorized manual adjustments, low-stock alerts,
   movement history, inter-location transfers.
3. **Recipe, sub-recipe & production management** — inventory *conversion*, not just purchased
   stock: Raw Ingredients → Sub-Recipe → Intermediate Product → Final Product, multiple production
   layers, auto-deduct ingredients on production, auto-add produced quantity, link POS products to
   recipes. This is the client's core differentiator vs. off-the-shelf POS.
4. **Supplier & procurement** — supplier master + item association + purchase history; PO workflow
   (Location → Supplier → Items → Create PO → Send PO by email → Receive Goods → Update Inventory);
   **AI-assisted PO suggestion** — given a weekly production target, AI suggests what/how much to
   order based on current stock + recipes.
5. **OCR-based goods receiving** — upload/scan a receiving doc, OCR-extract line items, user
   review/correct, confirm, update inventory.
6. **Multi-location** — location-specific inventory/POS/PO/transfers/reporting, sale deducts from
   the selling location only.
7. **Sales-channel net profitability** — the client's stated key customization: net profit =
   Selling Price − Product Cost − **Channel Commission**, commission % configurable per sales
   channel (their doc's own example is Deliveroo, a UK platform — see Open Questions, the real
   UAE channel set needs confirming).
8. **Dashboards/reports** — kept deliberately simple: daily/monthly revenue, sales by
   location/channel, top items, most-consumed ingredients, modifier report, stock position/low
   stock, purchase/receiving/transfer history, product cost + channel commission, net profit.
   Final KPIs to be confirmed at MVP review.
9. **User & access management** — auth + role-based access (Administrator, POS/User,
   Inventory/Procurement User, Management/Reporting User indicative; final permissions at MVP
   stage).

## Fit against our existing POS

Directly reusable / already-built pieces (see `BOM_IMPLEMENTATION_STATUS.md` at repo root for
exact current state):
- Multi-tenant architecture (UUID PK + `tenant_id` on every table) — proven pattern, not
  theoretical.
- Recipe/BOM costing module (`backend/app/models/inventory.py`,
  `backend/app/services/recipe_service.py`, `frontend/src/pages/admin/RecipeBuilderPage.tsx`) —
  ingredient master, recipe versioning, cost snapshots. Directly relevant to their Section 4, but
  built for a single-layer recipe (item → ingredients), **not** the multi-layer
  raw→sub-recipe→intermediate→final chain the client explicitly asked for. Needs a gap check
  before quoting.
- Multi-location floor/table model exists for dine-in, but this client is **no dine-in** — the
  location concept here means separate kitchens/branches for stock and PO purposes, not table
  service. Needs its own review of what "location" maps to in our schema for a non-dine-in tenant.
- Existing order-channel and payment-flow config precedent (`restaurant_configs.payment_flow`)
  is architecturally similar to what channel-commission tracking would need, but channel
  commission-by-percentage is new — no equivalent field/table exists yet.

Net-new for this client, not built anywhere yet:
- Multi-layer recipe/sub-recipe production chain.
- Purchase order workflow + supplier master + email PO sending.
- OCR-based goods receiving.
- AI-assisted PO quantity suggestion.
- Per-channel commission % configuration feeding into net-profit reporting.
- Formal quotation issuance from back office.
- A4 tax-invoice template (VAT-compliant, full company name) — different from our existing
  thermal ticket receipt.

## Open questions (from the doc alone, before the video is absorbed)

- What is the business's actual trading name? (Only "FZ LLC" appears, which reads like a generic
  free-zone company suffix.)
- What sales channels does the client actually sell through in the UAE — the doc's own example is
  Deliveroo, but Deliveroo's live-in-UAE status needs checking (research in flight, see
  `integrations/` folder once the research note lands).
- Is a card/online payment gateway required for MVP, or is cash the only channel to build for at
  launch (Malik's brief says "assume cash" unless gateway research changes that)?
- Number of locations at launch, and whether "location" here means multiple kitchens/branches or
  a single kitchen with multiple sales channels.
- OCR receiving — any existing OCR vendor preference, or open to whichever we recommend?

## Call walkthrough notes (video, first ~9 of 18 minutes transcribed so far)

This is a sales/scoping call between Malik and Martin, Malik demoing the existing platform live.
Key points beyond the scope doc:

- **Confirmed delivery/collection-only, no dine-in, no KDS needed** — Martin's own words: "I don't
  have tables, so it's delivery-only, my restaurant." Channels: call center + third-party apps.
  Business described once as "cafeteria" and once as "restaurant" — bakery framing came from
  Malik's brief to me, not yet confirmed in the client's own words; still needs the trading name.
- **Third-party integration reality check, discussed live:** Martin named **Noon, Careem, Deliveroo,
  and Uber Eats**. Research (`integrations/2026-08-26_delivery-and-payment-research.md`) confirms
  **Uber Eats does not operate in the UAE** (exited 2020, folded into Careem) — worth a gentle
  correction to Martin, since Careem now covers that ground. Three real fallback paths were
  discussed on the call if a platform won't grant API access: (1) their own tablet running
  alongside the POS — the aggregators' default, deliberately keeps control on their side; (2) an
  AI agent reading their order portal instead of a real API. Malik flagged this needs checking
  against each platform's ToS/security posture before relying on it — portals built for
  human/business use routinely block or rate-limit automated access, so treat as a fallback to
  validate, not a default plan; (3) the real API, gated behind partner approval, which is the
  actual goal per Martin ("I want the orders to avoid manual interaction of my stuff").
- **Website ordering: undecided.** Martin is weighing Shopify + integration vs. Malik building and
  integrating it directly — "it depends," he wants advice. Malik showed a **live reference build**
  (a UK delivery/collection-only restaurant — this is Chick Shack UK's online-ordering channel):
  Stripe checkout on the website → order populates on the POS screen → kitchen accepts/rejects →
  cash vs. card status shown → 3-copy ticket printing (reception/kitchen/customer), template
  customizable. This is the direct precedent to reuse/adapt for FZ LLC if they go custom-build
  instead of Shopify.
- **Recipe-based costing was told to Martin as "fully built in."** Internally, our recipe module
  today is single-layer (item → ingredients); the client's ask is a multi-layer chain (raw →
  sub-recipe → intermediate → final). Per Malik's 2026-08-26 direction
  ([[fz-llc-pricing-and-build-posture]]), this is scoped as work to build to match what was
  described on the call, not flagged as a gap in client-facing conversation — tracked here purely
  as an internal build item so the demo/MVP actually delivers what was promised live.

## Call walkthrough notes, part 2 (minutes 9–18, transcript now complete)

**⚠️ Hard deadline: Martin expects a full written quote by Monday 2026-08-31.** Call happened
Wednesday 2026-08-26; Martin explicitly asked to reconnect "Monday" and said he does not want it
pushed to Tuesday/Wednesday — he's planning his next two months starting the 1st and wants the
number in hand before that call.

- **Two-location model, refining the earlier "no dine-in" note:**
  - **Location 1 — production/wholesale.** Where items are produced (recipes/sub-recipes run
    here). Sells **B2B**, needs proper **A4 tax invoices**, explicitly **not** a thermal/vertical
    ticket.
  - **Location 2 — delivery only.** Sells via call center, third-party apps, and e-commerce.
  - **Inventory transfers between the two locations** — matches Section 7 of the scope doc, now
    concretely: 2 locations, not a placeholder count.
- **Quote must be two-tier: with e-commerce, and without.** Martin wants to see the delta so he
  can decide if the e-commerce build is worth it — he already knows he could stand up a Shopify
  store himself for ~1,000 AED and API-connect it to any POS. He pushed hard on "what's the actual
  difference between your custom e-commerce and Shopify-connected-to-your-POS" — the honest answer
  given on the call was **"no difference, they'd be the same"** if both are equally connected to
  the POS. **Do not oversell the custom e-commerce build over Shopify** — Martin already knows
  they're functionally equivalent when integrated; the value proposition should live elsewhere.
- **Quote must include:** timeline (assessment → deployment → review week-by-week), and the
  ongoing cost structure explicitly broken out — software/subscription, annual hosting, and
  minimum maintenance are three separate things Martin wants to see named separately, not bundled
  silently into one number.
- **Martin is price-sensitive and has been burned before:** "I already have three bad experiences
  with POS." His own ceiling logic: if a custom build costs the equivalent of ~4 years of a
  subscription alternative, he won't do it. This is the direct rationale behind
  [[fz-llc-pricing-and-build-posture]]'s 225 AED/month, near-zero-upfront target — keep the
  proposal's math visibly cheap against that "N years of subscription" mental model.
- **Wants proof specific to the restaurant industry**, not just any built software — his own
  words: "I need to see what you build for a restaurant so my partners can decide." Sitara offered
  to create a **login for Martin and his partners** to explore the existing platform/demo
  themselves (not the final product, framed as "play around and navigate"). This is a concrete
  action item — get him demo credentials, ideally to the existing restaurant-industry build
  (pos-demo / Chick Shack-pattern), not necessarily a bespoke FZ LLC tenant yet.
- **Integration ask, concrete:** Sitara needs to obtain, per platform, either API documentation or
  a named technical contact for **Noon, Careem ("Karim" in the transcript), and Uber Eats**.
  Martin's own suggestion: search "<platform> UAE API" — each has a public docs/manuals page.
  **Correction needed for Martin:** Uber Eats does not operate in the UAE (confirmed exited 2020,
  folded into Careem) — the research file substitutes **Talabat** as the real third major
  platform. This should be raised with Martin directly rather than silently substituted, since he
  named Uber Eats himself and may not know it's not live there.
- **Pricing framing Martin explicitly confirmed as separate scopes:** whether or not the delivery
  API integrations happen changes the quote — "if the API integration is to be done or if the API
  integration isn't to be done then both of them are different scopes of work and they'll be
  charged differently." The quote can and should go out **before** API confirmations come back
  from Noon/Careem/Talabat — Martin does not want to wait 4-5 days for that just to get a price.
- **UAE presence:** Sitara has a UAE office; Martin doesn't need a visit for now, a call is enough.

**Action items arising directly from this call are folded into `plan-and-todo_2026-08-26.md`.**
