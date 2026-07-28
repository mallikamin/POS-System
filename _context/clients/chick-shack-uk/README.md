# Chick Shack UK — client reference folder

> ⚠️ **Current status lives in `_state/chick-shack-uk.md`, not here.**
> This folder is **reference material**: who the client is, what was agreed, the meeting transcript,
> the proposal, the menu source, the DNS record dump, voice notes.
>
> On 2026-07-27 this file's status section was a day stale and contradicted its own build table
> 60 lines further down. Status was moved out for that reason. **Do not re-add status here.**

---

## Who

| | |
|---|---|
| Business | **Chick Shack UK** — takeaway (chicken / peri peri / wraps / burgers), UK, GBP |
| Contact | **Imran R** — +44 7909 313456 |
| Introduced by | **Faizan** (+92 300 9458890) — also the TastyBites contact |
| Our side | **Malik Amin**, Sitara Infotech — amin@sitaratech.info |
| Incumbent | **EposNow** on an Android till. Contract started **June 2026**, runs to ~**June 2027** |

⚠️ A third name, **"Rizwan"**, is referenced on the call recording and in its filename. Imran R is the
confirmed contact (Malik, 2026-07-27). Rizwan appears to be a separate attendee. Not fully resolved.

## Status as of 2026-07-27 (corrected — this section was a day stale)

**Proposal sent. Fasthosts access working. Menu received and verified. Build is UNDERWAY.**

- **Storefront built and deployed** → `https://chick-shack-storefront.mallikamiin.workers.dev`.
  See "Build progress" below for exactly what is and is not wired up.
- **Custom domain `chickshackg84.com` is blocked** on two dead Vercel DNS records that still occupy
  the hostname in Cloudflare. See "Custom domain blocker" below.
- **Public ordering API and Stripe are not started.** Checkout does not place a real order yet.
- Nothing is owed by the client until go-live.

> This section previously read *"Awaiting the menu. Build has NOT started — no code written"*, which
> its own build table below already contradicted. Corrected 2026-07-27.

## Custom domain — ✅ LIVE (resolved 2026-07-27)

**https://chickshackg84.com** and **https://www.chickshackg84.com** both serve the storefront.
HTTP 200, Cloudflare-issued SSL, `Server: cloudflare`. Worker version `d02f7fa5`.

The printed menus advertise `WWW.CHICKSHACKG84.COM`, so this replaces the 404 customers were hitting.

**What the blocker was.** Two dead Vercel records occupied the hostname, so `wrangler deploy` failed
with `Hostname 'chickshackg84.com' already has externally managed DNS records ... [code: 100117]`.
Deleting exactly `A @ → 216.198.79.1` and `CNAME www → b00d3203a061e681.vercel-dns-017.com` cleared
it. Nothing else was touched.

✅ **Email re-verified intact afterwards** — MX, SPF, `_dmarc` and all four `livemail1-4._domainkey`
DKIM CNAMEs still resolving.

The two `_vercel` domain-verify TXT records were **deliberately left**. They sit on a different
hostname so they never conflicted, and deleting them revokes the previous developer's claim on the
domain — a separate decision while ownership is unresolved.

> ⚠️ **Gotcha worth remembering.** After the change, this machine's resolver kept serving the dead
> `216.198.79.1` for several minutes, so plain `curl` reported `Server: Vercel /
> DEPLOYMENT_NOT_FOUND` well after the site was genuinely live — and `ipconfig /flushdns` did not
> clear it. Verify against the authoritative nameserver (`nslookup ... daisy.ns.cloudflare.com`) or
> with `curl --resolve host:443:<edge-ip>`, not your local resolver.

### Fasthosts access (WORKING, verified 2026-07-27)

- Panel: **https://login.admin.fasthosts.co.uk** (two-step form: username, then password).
- Account **`uk1517237781`**, user Malik Amin, role **Regular**.
- **Credentials: `_context/secrets/fasthosts.env`** (gitignored, verified). Raw handover file kept
  alongside as `fasthosts-access.txt`. Never paste these into chat or commit them.
- ✅ **Password already rotated** 2026-07-27, so the one Imran sent over WhatsApp is dead.
- ✅ **Two-factor authentication ENABLED** 2026-07-27. (Was flagged inactive; now done.)
- Initial access failed because Imran granted it against a mistyped email. Resolved 2026-07-27.
- **Target domain: `chickshackg84.com`** — expiry 27-Mar-2027. The one Imran authorised:
  *"Only work on domain: Chickshackg84.com"*.
- ⚠️ **There is NO web hosting on it.** The package is **"Email and Web Forwarding"** (ID
  `1129367388`) — no webspace, no FTP, no file manager. `https://chickshackg84.com` returns 404.
  **No SSL certificate.**
- ⚠️ **The domain is already wired to Vercel** by someone else — `www` CNAMEs to `vercel-dns-017.com`
  and there are two `_vercel` domain-verify TXT records. Probably the developer Imran said had been
  *"messing me around."* Ownership needs settling.
- ⚠️ **Live email on this domain** (livemail.co.uk MX + 4 DKIM CNAMEs + SPF + DMARC). When repointing
  the site, change **only** the root A record and the `www` CNAME. Touching anything else kills his
  email.
- **Full DNS record set and deployment options: `hosting-dns-reference.md`** in this folder. It is
  transcribed from the panel so nobody needs to open Fasthosts again — it is painfully slow.
- ~~**Deployment decision: host the storefront on our own VPS** behind the POS nginx.~~
  **SUPERSEDED 2026-07-27.** Storefront ships to **Cloudflare Workers** (static assets, own
  `wrangler.toml`, same toolchain as `etisalat-shop`); only the **API** stays on the DigitalOcean
  box. The zone was moved to Cloudflare, so DNS and SSL for the custom domain are handled by
  Cloudflare rather than by pointing an A record at our nginx.
- ⚠️ **Scope discipline:** the account also exposes `chickanas.com`, `chick-shack.com`,
  `chickshackg84.co.uk`, `supra-security.co.uk` and `supra-security.com`. Access is technically
  visible but **not authorised**. Touch only `chickshackg84.com`.
- ⚠️ **Worth raising with Imran:** `chick-shack.com` is also on the account and is a far better
  customer-facing URL than `chickshackg84.com`. His call, but customers will be typing this.

## The deal in one paragraph

This is **not** an EposNow displacement. Imran keeps EposNow for all in-house trade and wants an
**online ordering channel alongside it**: his own website with checkout, plus a tablet in the shop
showing live online orders. His analogy: *"a bit like a Uber Eats tablet or a Just Eat order pad."*
The two systems run side by side and are **deliberately not reconciled** — he was shown the
split-books consequence and accepted it.

## Commercials (decided, sent)

| Item | Price |
|---|---|
| Website build + setup | **£300** one-time |
| Ongoing service | **£35 / month** |
| Payment | **Nothing upfront.** £300 due on go-live. Monthly starts at go-live |
| Timeline | **2 weeks** from receiving menu + hosting access |

Concerns about this pricing were raised and overruled by Malik. They are logged once in `STATE.md`
— do not re-litigate them each session.

## Build progress

**Branch: `feat/chick-shack-storefront`** (created 2026-07-27 off `main` @ `22150c5`).
Not committed yet — pre-existing doc churn (~86 files) is also in the tree; stage selectively.

| # | Item | Status |
|---|---|---|
| 1 | **Multi-currency / GBP** | ✅ **DONE** — `frontend/src/utils/currency.ts` rewritten, `configStore` wired |
| 5 | **Storefront (menu, cart, checkout, delivery)** | ✅ **BUILT** — `storefront/`, `npm run build` clean, 173 KB JS / 55 KB gzip |
| 2 | `online` order_type + public order endpoint | ⬜ next |
| 3 | Accept / reject + ETA on the order | ⬜ |
| 4 | Stripe Checkout + webhook | ⬜ |
| 6 | Order-queue tablet view | ⬜ |

### Storefront — what exists (`storefront/`)

Own Vite + React + TS + Tailwind app, deployed separately from the POS. Cloudflare Workers static
assets (`wrangler.toml`), same pattern as `etisalat-shop`.

Menu browse with sticky category rail · item configurator (absolute-priced size variants, required
Mild/Hot, +£3 meal, paid dips) · basket persisted to localStorage · checkout with collection/delivery,
contact capture, area-priced delivery, card-or-cash choice, allergen notice.

⚠️ **Checkout is not wired to a backend.** `place()` in `Checkout.tsx` fakes a reference and clears
the basket. No order is created and no payment is taken until items 2–4 land. **Do not present it to
the client as working.**

### Menu — real data now in place

`storefront/src/data/menu.ts` is transcribed from the client's **official printed menu boards**
(photographed from their Google Business listing, artwork dated 05/2026). This replaced the
chick-shack.com scrape, which Imran confirmed was wrong.

### ⚠️ Delivery is priced BY VILLAGE, not by postcode

Straight off the printed board — and this would have been a real money bug:

| Area | Fee | | Area | Fee |
|---|---|---|---|---|
| Garelochhead | £3.00 | | Rosneath | £4.50 |
| Greenfields Camp | £3.00 | | Caravan Park | £6.00 |
| Southgate & Shanden | £4.00 | | Kilcreggan & Cove | £7.00 |
| Mambeg, Clynder & Rahane | £4.00 | | Helensburgh | £10.00 |
| Portincaple | £4.00 | | Arrochar | £15.00 |
| Rhu | £4.50 | | | |

Nearly all of these sit in the **same G84 outward code**, so the postcode-prefix model built first
would have quoted £3.00 for a £15.00 Arrochar run. Checkout now uses an area picker instead — which
is also how the shop and its drivers already think about it.

### Other facts confirmed off the printed board

- **The board already advertises `WWW.CHICKSHACKG84.COM`** — the domain is on printed material in
  customers' hands. It currently 404s.
- **"HOME DELIVERY OR COLLECTION"** — printed. Delivery is not speculative.
- Opening hours **Monday–Sunday 16:00–22:00**, 7 days. Phones 01436 653 143 / 07719 566 889.
- Allergen notice is printed and is now shown at checkout.

### Menu verified against the official artwork

Imran supplied the print-ready A4 PDF on 2026-07-27 — saved as
`refs/2026-07-27_chick-shack-official-menu-A4.pdf` (artwork dated 05/2026, printurmenu.com).
**Every section was checked against `storefront/src/data/menu.ts` and all items and prices match.**
The transcription is confirmed correct, not merely assumed.

One judgement call: the print spells three areas *Potiancapl*, *Rosneth*, *Helensbrough*. These are
rendered as **Portincaple, Rosneath, Helensburgh** in the app. Flag to Imran — cheap to revert if he
wants the board wording kept verbatim.

### Resolved with Imran (2026-07-27)

- ✅ **Extra items:** drinks only — **remove Fanta Pineapple Grapefruit**, **add Rubicon Passionfruit
  and Levi Roots Caribbean Crush, both £1.79**. Applied and deployed.
- ✅ **Delivery minimum: £5.00.** Applied (`deliveryMinimum: 500`).

### Still to confirm with Imran

1. The board says *"A service fee may be applied for long distance deliveries"* — is that **on top of**
   the area fees, or already included?
2. Whether prices have moved since the 05/2026 print run (the PDF is the newest artefact we have).
3. Area name spellings (see above).

### Note on item 1 — a real bug was found, not just a rename

The old `formatPKR` used `maximumFractionDigits: 0`. That is correct for PKR convention but would
have rendered **£8.50 as £9** on a live checkout. The rewrite separates two things that were
conflated:

- `minorExponent` — minor units per major unit (100 paisa per rupee, 100 pence per pound). Arithmetic.
- `displayDecimals` — decimal places shown. PKR 0, GBP 2.

For PKR these differ; using one for the other is a money bug. The table holds **PKR and GBP only** —
the two currencies this product actually serves. Do not speculatively add others.

`formatPKR` is kept as a deprecated, currency-aware alias so all 140 call sites work untouched.
Verified: PKR output unchanged (`Rs. 1,800`, `Rs. 650`); GBP correct (`£8.50`, `£1,000.00`);
`tsc --noEmit -p tsconfig.app.json` exit 0.

**Still outstanding for item 1:** ~173 hardcoded `Rs.` string literals in `frontend/src` that bypass
the formatter entirely. Not yet swept.

## What has to be built

Reuse as-is: menu engine, orders, customers (phone lookup + history), admin dashboard / reports,
WebSockets.

New work:
1. **Public storefront** — menu, cart, checkout. Consumes the existing menu API.
2. **Public order endpoint** (no auth) + `online` added to `order_type`.
3. **Stripe** — Checkout Session + webhook. `PaymentGateway` is an abstract stub today; this is the
   only genuinely from-scratch piece. Cash-on-delivery is the same order left unpaid.
4. **Accept / reject + lead time (ETA)** — not in the order state machine today.
5. **Order-queue tablet view** — the existing KDS is close; point it at online orders.
6. **GBP** — replace `formatPKR()` (140 call sites) with a config-driven formatter.

Explicitly **not** wanted: KDS as such, QuickBooks or any accounting integration, EposNow
integration, sales reconciliation between the two systems.

## Waiting on Imran

1. ✅ ~~FastHost access~~ — **received and working** 2026-07-27.
2. ✅ ~~Menu: items, prices, sizes, options~~ — **received** (official A4 PDF) and verified item by
   item against `storefront/src/data/menu.ts`.
3. ✅ ~~Delivery rules~~ — taken off the printed board: by-village pricing, £5.00 minimum.
   Still to confirm: the *"service fee for long distance deliveries"* wording (see below).
4. ✅ ~~Opening hours~~ — Mon–Sun 16:00–22:00, printed. Pre-ordering still not discussed.
5. ⬜ **Stripe account connected** — **now blocking.** He says he has one; we need to know whether it
   is verified and live, and get it connected. This gates the whole payment path.
6. ⬜ Logo / food photos.
7. ⬜ Tablet Android + Chrome version (he shared a photo of the back only — see `screenshots/`).
8. ⬜ Spare printer make / model / connection type.

## Still unanswered

- **"Which database is it?"** — Imran asked this directly on the call and never got an answer.
  Answer it unprompted: PostgreSQL 16.
- **How the customer receives the ETA** — never discussed. Recommended default: on-screen
  confirmation + email. No SMS gateway, no recurring cost.
- Spare printer make / model / connection.
- Whether the Stripe account is verified and live, or newly created.

## Commercial upside

Imran offered to introduce **3–4 other UK operators**, plus his uncle (**Ali Fish and Chips** — no
EPOS at all, pen and paper + a separate online-order tablet, currently being *"messed around"* by a
local developer), plus *"another two people."* Up to ~6 sites.

⚠️ Unqualified, and offered **before** he saw a price. He will quote his own price to them, so
£300/£35 anchors the whole pipeline.

---

## Files here

| File | What it is |
|---|---|
| `discovery.md` | Requirements + hardware discovery. Top section is pre-call WhatsApp notes; **MEETING OUTCOMES at the bottom is what governs.** |
| `meeting-transcript_2026-07-26.md` | Full transcript of the 13m 39s video call. Machine-transcribed, no diarisation — speaker labels are inferred. |
| `meeting-prep_2026-07-27_SPENT.md` | Pre-call prep. **Historical only** — written against the displacement premise that turned out to be wrong. Kept for the record. |
| `proposal/2026-07-27_proposal.md` | Proposal source of truth. **Edit here**, then regenerate the PDF. |
| `proposal/2026-07-27_proposal.pdf` | **The version sent to the client, 2026-07-27.** |
| `proposal/2026-07-27_proposal.html` | Print stylesheet used to render the PDF. |
| `screenshots/2026-07-26_tablet-back.png` | Back of the tablet Imran will use. Dolby Audio branding + UKCA mark; model not legible. |
| `screenshots/2026-07-27_whatsapp-fasthost-access.png` | WhatsApp exchange agreeing the FastHost user-invite route. |

**Source recording:** `C:\Users\Malik\Videos\rizwan uk meeting.mp4` (699 MB, left in place, not copied
into the repo).

## Regenerating the proposal PDF

Edit the `.md`, mirror the change into the `.html`, then:

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=new --disable-gpu `
  --no-pdf-header-footer `
  --print-to-pdf="<...>\proposal\2026-07-27_proposal.pdf" `
  "file:///<...>/proposal/2026-07-27_proposal.html"
```

Client-facing style rules Malik set: **no em dashes**, no marketing language, plain short sentences.
