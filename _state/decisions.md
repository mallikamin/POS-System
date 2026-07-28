# Decision log

**Last updated:** 2026-07-27 (04:12 PKT)

Decisions that are **made**, with the reasoning that produced them — including the ones where a
concern was raised and overruled.

**The point of the "overruled" entries is to stop them being re-argued every session.** They are
recorded once, honestly, with the risk named. A future session should read them, not reopen them.
If circumstances change, add a NEW entry that supersedes the old one; do not edit history.

---

## D-01 · Chick Shack is an added channel, not an EposNow replacement
**2026-07-26, from the client call.**
The client keeps EposNow for all in-house trade. We supply an online ordering channel alongside it:
website with checkout, plus a tablet showing live orders. The two systems run side by side and are
**deliberately not reconciled** — he was shown the split-books consequence and accepted it
(*"I'm happy to keep it separate"*).

Consequences: offline mode drops sharply in risk (if the tablet dies, only the online channel stops
and the till keeps trading). **QuickBooks — our largest integration asset — is worth zero here**; he
refused any accounting integration outright. KDS is declined, though the "tablet showing live
orders" he wants is KDS-shaped and may be repurposable.

## D-02 · Storefront on Cloudflare Workers, API stays on the existing DigitalOcean box
**2026-07-27, Malik.**
Storefront is static React on Workers (same toolchain as `etisalat-shop`). Not Fasthosts, whose
package has no webspace at all. Not Vercel.

⚠️ **Concern raised and overruled.** Putting a live UK payment-taking API on the shared SGP1 box
means: blast radius shared with Orbit and parkcity (an nginx recreation already took orbit-voice
down for 20 minutes once); Singapore-to-UK latency on every checkout call; and 2 GB of RAM already
carrying three projects and documented as unable to build the frontend. The recommendation was a
dedicated London droplet.
**Malik's call: ship on existing infrastructure now, migrate once revenue arrives.** Commercially
reasonable. **Revisit at go-live, and before any referral client is onboarded.**

## D-03 · Payments via Stripe hosted Checkout, confirmed by webhook only
**2026-07-27.**
Card data never touches our infrastructure (PCI SAQ A). Payment is confirmed by a
**signature-verified, idempotent webhook** — **never** by the browser redirect, which a customer can
forge or simply never complete. Prices are always computed server-side. Cash on delivery is the same
order left unpaid.

## D-04 · Pricing £300 build + £35/month, all payable at go-live
**2026-07-27, Malik.**

⚠️ **Concerns raised and overruled.** Opening suggestion was £1,200 build with tiered monthly, then
£550/£40. Landed at £300/£35.
- **Effort vs price:** the scoped build is realistically ~3-4 weeks (storefront, Stripe + webhooks,
  COD, delivery rules, accept/reject + ETA, order tablet, GBP sweep, deployment, onboarding).
- **Anchoring:** the client offered ~6 UK referrals and will quote his own price to them, so £300/£35
  prices the whole pipeline rather than one job. It also caps headroom for the June-2027 in-house
  upsell.
- **Payment 100% on go-live** means zero protection if the client walks mid-build.
**Malik's rationale:** the client already has a working mechanism via EposNow, so the perceived delta
of our work is small and an upfront charge would not fly.

## D-05 · Ordering stays switched OFF until the backend is real
**2026-07-27.**
`SHOP.orderingEnabled = false`. Checkout shows the basket total and asks the customer to phone.
The printed menus already advertise the domain, so a browsable menu beats the 404 customers were
getting — but **a fake order confirmation would be worse than either.**

## D-06 · Delivery priced by village, not by postcode
**2026-07-27.**
Straight off the printed board. Nearly all these villages share the **same G84 outward code**, so the
postcode-prefix model built first quoted £3.00 for a £15.00 Arrochar run. An area picker is also how
the shop and its drivers already think about it. **This was a real money bug caught before launch.**

## D-07 · DNS: delete only the two dead Vercel records, nothing else
**2026-07-27.**
The domain carries the client's live email (MX, SPF, DMARC, four DKIM CNAMEs). Only
`A @ → 216.198.79.1` and `CNAME www → …vercel-dns-017.com` were removed. Email was verified intact
afterwards.
The two `_vercel` domain-verify TXT records were **deliberately kept**: they sit on a different
hostname so never conflicted, and removing them revokes the previous developer's claim on the domain
— a separate call while ownership is unresolved.

## D-08 · Storefront images are self-hosted stock, with an explicit opt-out
**2026-07-27.**
Every item shows a photo, sourced per category with per-item overrides. Images are **self-hosted**
(not hotlinked) so there is no third-party runtime dependency, and split into lazy-loaded 240px
thumbnails plus on-demand 720px heroes — 168 KB of thumbnails for the whole menu instead of 668 KB.

Two things were deliberate:
- **They are stock photos, not his food.** Marked as such in `types.ts`. Real photography is still
  wanted from the client; swapping a photo is a one-line change.
- **Items can opt OUT** with `image: null`. The Fish, Veggie and Veggie Wrap items do, because
  inheriting the category photo would show a fried chicken burger to someone ordering fish. Kids,
  Dips and Drinks have no category photo at all — a stock picture of a sauce tub adds nothing.
  Those render a branded monogram tile, which reads as intentional rather than broken.

## D-09 · Printing does not block launch
**2026-07-27.** See `printing.md` for the full reasoning. The client's existing Bluetooth printer
cannot be shared with EposNow, and a browser cannot drive a Bluetooth printer at all. Hardware facts
are still contradictory. The live-order tablet is what he actually asked for and is screen-first, so
printing follows once the hardware is known — rather than buying the wrong printer now.

*(Superseded in its premises 2026-07-28: the printer is Ethernet, not Bluetooth, and it now prints
from the tablet. The conclusion — printing is not the launch blocker — still holds.)*

## D-10 · Public routes name their tenant in the path; PIN login never searches across tenants
**2026-07-28. Malik raised the collision risk and offered to drop PIN login entirely; kept after
checking the code.**

The question was whether two tenants sharing a PIN would collide. Checked rather than assumed, and
the answer was worse than the question. `authenticate_by_pin` was always correctly scoped to
`User.tenant_id` — but the **route** looped every active tenant and returned the first user whose PIN
matched. That is not a failed login, it is the *wrong* login, and the demo tenant ships PINs
1234 / 5678 / 9012, so a new shop issued 1234 would have landed inside another restaurant's data
holding a valid token for it.

**Decision: keep the PIN, fix the resolution.** Dropping it would have removed the good UX — four
digits on a greasy kitchen tablet is the entire reason POS systems have PINs — while leaving the
actual defect untouched.

- PIN login now requires a tenant, `tenant_slug` preferred over `tenant_id` because a person can
  type it. It falls back to the single active tenant **only when exactly one exists**, which keeps
  the existing POS demo working, and otherwise returns 400 rather than guessing.
- An unknown slug returns **401, not 404**. A distinct status would let anyone enumerate the
  restaurants on the box.
- Password login keeps its cross-tenant search: a collision there needs the same email *and* the
  same password, not four matching digits.
- The same `SELECT ... WHERE is_active LIMIT 1` (no `ORDER BY`) also sat in `public.py`. Storefront
  routes are now `/public/{tenant_slug}/menu` and `/public/{tenant_slug}/orders` — a path segment
  rather than a header, because a custom header forces a CORS preflight on every request and cannot
  be opened in a browser to debug.

Covered by `tests/test_pin_tenant_isolation.py` + `tests/test_public_tenant_routing.py` (24 tests)
and verified against the running API: Chick Shack's PIN is rejected by `demo-restaurant`.

## D-11 · Chick Shack's menu is seeded into the database; variants become a required Choice group
**2026-07-28.**

The storefront rendered its menu from `storefront/src/data/menu.ts`, compiled into the Worker bundle,
with slug IDs like `peri-half`. `POST /public/{slug}/orders` validates against `menu_items.id`, a
UUID — so the storefront could never have placed a real order, whatever else was built. The menu is
now seeded: 8 categories, 62 items, 3 shared modifier groups.

The data is **exported, not retyped**. `storefront/scripts/export-menu.ts` dumps the real objects to
JSON and `seed_chick_shack.py` consumes that, because `MENU_ITEMS` is assembled by helper functions
and reading 62 items by eye is exactly how a price gets mistyped.

**Every item has variants and no top-level price** — "with Chips" £9.99, "Half & Half" £10.49,
"with Rice" £10.99 — while the POS `MenuItem` carries one price. So each item takes its **cheapest
variant as the base price** and the remaining variants become a **required single-select modifier
group**, with the difference as `price_adjustment`. That mirrors how the storefront already presents
them, keeps one row per dish, and reuses the "Half serving −400" pattern already in this codebase.

⚠️ **Tax is seeded at 0, not 20% UK VAT.** Menu prices come off the printed board and are what the
customer pays; under `tax_inclusive` the totals match either way, but a non-zero rate would assert a
VAT registration nobody has confirmed. **Open question for Imran before go-live.**
