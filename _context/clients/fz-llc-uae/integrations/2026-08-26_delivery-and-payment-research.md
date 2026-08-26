# FZ LLC — UAE Delivery Platform & Payment Gateway Research

Date: 2026-08-26. Sources are cited inline; anything not confirmed from an official/primary
page is flagged **unverified**.

## Correction to the client's own example

The scope doc uses **Deliveroo** as its worked example for channel-commission profitability, but
Deliveroo is a UK-native platform. In the actual UAE market the dominant channels are **Talabat**,
**Careem NOW/Food**, and **noon Food**. Deliveroo does still operate in the UAE (DoorDash completed
its acquisition of Deliveroo UAE in Oct 2025 and confirmed normal continued operation), so it's a
valid fourth channel, not a mistaken one — but Talabat should be the primary reference case, not
Deliveroo. **Uber Eats does not operate in the UAE** — confirmed: Uber Eats exited the UAE in
May 2020 and transferred its business to Careem, which now runs food delivery as Careem
NOW/Careem Food. Any "Uber Eats" integration in a UAE aggregator's feature list is generic/regional
marketing copy, not a live UAE channel.

## Platform-by-platform

### Talabat — best-documented path
Official developer portal (`developer.talabat.com`) and integration docs
(`integration.talabat.com`) exist and are public-facing. Verified process: sign an NDA → generate a
PGP keypair → submit a credential request with your public key → a Talabat partner contact reviews
and approves → encrypted credentials are issued → authenticate via a Login API for token-based
access to the rest. API covers accept/reject/pickup/prepared order status, webhook order
notifications, and full menu CRUD (create/update/delete items, availability, centralized-kitchen
support). No published pricing for API access — **unverified**, but the NDA + manual approval gate
means budget realistic effort at **2–4 dev-weeks** once approved, plus unknown approval wait time.
Commission: multiple secondary sources converge on **~25–30% standard UAE rate**, with negotiated
5.3% + flat AED 8.40/order available only through group programs like the Dubai/UAE Restaurants
Group Digital Growth Program — **treat exact number as unverified** until Martin's own Talabat
account manager confirms his actual rate.

### Careem NOW / Careem Food
Official partner FAQ page confirms POS-integrated restaurants get orders auto-accepted, but
discloses **no** commission rate, integration requirements, or approval criteria — that detail sits
behind partner sign-up, not public docs. A UAE partner-support email exists
(partnerssupport.uae@careem.com) for non-urgent issues. Since Uber Eats folded into Careem in the
UAE, Careem is effectively the second must-have channel after Talabat. Direct API access terms are
**unverified from public sources** — needs direct outreach to Careem's partner team.

### noon Food
Noon runs both a direct-integration path ("integrate with Noon's set of APIs") and a
partnered-integrator model, per Noon's own partner support KB. No public pricing or commission
figures found. Smaller GMV share than Talabat/Careem in most UAE F&B commentary — **lower priority**
unless Martin's locations specifically see noon Food volume.

### Deliveroo UAE
Confirmed still live in 2026 post DoorDash acquisition (Oct 2025), even launching new features
(Reservations, Feb 2026). Integration/commission terms not independently checked here — **treat as
unverified**, lower priority than Talabat/Careem given UAE market share.

### Aggregator middleware (Deliverect, and similar)
Deliverect has existing production integrations with Talabat, Careem, noon Food, and Deliveroo in
the UAE/MENA specifically — this is a real, mature option, not vaporware. It gives **one
integration** (Deliverect ↔ your POS) instead of building and maintaining N direct platform
integrations, each with its own NDA/credential process and its own breaking changes over time.
Deliverect does not publish UAE pricing — sales-quote-only, **unverified** cost. Industry-typical
aggregator pricing (from general market knowledge, not confirmed for Deliverect UAE specifically)
runs per-location monthly SaaS fees rather than per-order commission on top of the platforms' own
commission — this needs a direct quote before it can be compared against direct-integration
dev-cost.

## Payment gateways (UAE)

| Gateway | Settlement | Card-present | Card-not-present | Fee (verified where noted) | Notes |
|---|---|---|---|---|---|
| **Network International (N-Genius)** | AED | Yes (own POS terminal + cloud API) | Yes | Fixed-fee tier example found: AED 229+VAT/month per AED 10,000 processed; also a zero-upfront "Business POS" bundle | Local UAE acquirer, most restaurant-native option; percentage-based standard rate not found — unverified |
| **Telr** | AED | No (online-first) | Yes | ~2.49–2.69% + AED 1/txn + ~AED 149/month (tiered by volume) | Established UAE gateway, monthly fee is the tradeoff vs Ziina |
| **PayTabs** | AED | Limited | Yes | From ~2.85% + AED 1/txn | Settlement T+2 days typical, weekly batch at low volumes |
| **Ziina** | AED | No | Yes | 2.6% + AED 1/txn (+1.5% extra for non-AED/foreign cards) | No setup/monthly fee — cheapest to start, but newer/lighter-weight than the others |
| **Stripe** | Confirmed available in UAE (`stripe.com/global`, direct registration link for AE) | Not primary use case | Yes | Not verified for UAE-specific rate | Full availability per Stripe's own page, but Stripe is not a natural fit for in-person/card-machine flow |

None of these were checked for a documented POS-reconciliation API (matching a gateway transaction
back to a specific order for channel-commission net-profit reporting) — that would need a follow-up
technical check with whichever gateway is shortlisted, since it directly affects Section 8's net
profit calculation.

## Recommendation

The client's own brief treats all of this as "nice to have," with cash as the assumed default — that
scoping is right for an MVP. Recommended sequencing:

1. **MVP (Phase 1): cash + a single manual/CSV-based channel-commission field.** Let staff tag an
   order's channel and enter/adjust a commission % per channel manually in settings. This delivers
   Section 8's net-profit-by-channel reporting requirement **without** touching any external API —
   zero integration risk, ships with the rest of the MVP.
2. **Phase 2, if delivery volume justifies it: one aggregator (Deliverect) over direct integrations.**
   Building direct Talabat + Careem + noon integrations independently means three NDA/approval
   cycles, three credential-rotation and breaking-change surfaces to maintain forever, for a
   two-person team already carrying the core POS build. A single Deliverect integration trades a
   recurring SaaS fee (needs a real quote) for that maintenance burden — very likely the better
   trade unless order volume through delivery channels is large enough to justify owning the direct
   integrations.
3. **Payment gateway: defer until card acceptance is actually requested.** If/when needed,
   Network International is the most "restaurant POS native" (own terminals + cloud API, AED
   settlement, UAE-local support) and Ziina the cheapest/fastest to stand up for card-not-present
   only. Neither is urgent for an MVP that assumes cash.

Everything with a percentage commission or API cost above should be re-verified directly with each
platform's partner team before it goes into a client-facing proposal — public secondary sources
disagree on Talabat's exact rate, and Careem/noon disclose no figures publicly at all.
