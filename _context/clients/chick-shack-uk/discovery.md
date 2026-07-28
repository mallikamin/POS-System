# Chick Shack UK — Hardware & Requirements Discovery

**Date:** 2026-07-26
**Source:** WhatsApp group "CHICK SHACK UK" — Imran R (+44 7909 313456), Faizan (+92 300 9458890), Malik
**Status of facts below:** client-stated (verbal/chat), NOT independently verified. Printer model still pending.

> ## ⚠️ SUPERSEDED IN PART — read the meeting section at the bottom first
>
> A video call took place **2026-07-26 15:27** (a day earlier than the planned 07-27 meeting).
> Transcript: `docs/CHICK_SHACK_UK_MEETING_TRANSCRIPT_2026-07-26.md`.
>
> **The deal is no longer an EposNow displacement.** The client is keeping EposNow for all in-house
> trade and wants only a **website + online ordering channel** running alongside it on a separate
> tablet. The WhatsApp-era hardware findings below (his two EposNow printers, the locked-till
> question, hardware ownership) describe **equipment we will no longer touch** and are now largely
> moot. See "MEETING OUTCOMES" at the end of this document for what actually governs the build.

## Client

- **Chick Shack UK** — UK takeaway (chicken / peri peri / wraps / burgers). Currency **GBP**.
- Incumbent: **EposNow**, Android till, active **subscription**.
- Contact: Imran R. Faizan (TastyBites contact, +92) is in the group — Imran says *"It's the same system as tasty bites"*, i.e. TastyBites also runs EposNow. Same displacement playbook may serve both leads.

## Confirmed by client

| Item | Client answer | Impact on our build |
|---|---|---|
| Till OS | **Android** | Browser-based SPA is fine *if* the till isn't locked. Not yet tested. |
| Receipt printers | **Two**: one **integrated** (front counter), one **separate for kitchen** | Two print targets, not one. |
| Kitchen printer connection | **Ethernet** | ✅ Best case. Network ESC/POS over TCP:9100 — no print bridge needed for kitchen. |
| Integrated counter printer | **Model info pending** ("tomorrow") | ⚠️ Open. If USB into a locked Android till, not reachable — see Open Questions. |
| Hardware ownership | **12-month contract, then they own the equipment** | ⚠️ They do NOT own it yet. Contract start date unknown — see Open Questions. |
| Card machine | **Separate / standalone** (not integrated with EposNow) | ✅ No integration to lose when switching. Cashier already keys amounts manually today, so no regression. |
| Delivery platforms (Just Eat / Deliveroo / Uber Eats) | **"No platforms at the moment"** | Website ordering would be their **only** online channel, not a commission-free supplement. No existing volume to migrate (lower risk) but also no proven online demand. |
| Website | **"A fresh website will need to be built with checkout"** | Full build, not an integration into an existing site. |
| Payment gateway | **"I already have stripe account"** | ✅ Removes merchant-onboarding delay. Stripe is the path for online checkout. |
| Kitchen display (KDS) | **"Don't need one just a printer Is ok"** | ⚠️ Inversion: our fully-built KDS is not wanted; kitchen ticket **printing** — which we have not built — is required. |

## What Malik committed to in chat

- Website with checkout, integrated with POS — *"Ok. We'll do that and integrate with POS"*
- Payment gateway + API integration if they want card integrated — *"Will have to setup a payment gateway and API with POS if u want to intregrate that"*
- Separate tablet if the existing till is locked — *"if no other browser/app can be opened on the existing till/tablet - we'll have to get a separate tablet"*
- Printers — non-committal, appropriately: *"Printers are usually configurable. we'll see onto that"*

Nothing over-promised. No claim was made that printing or online ordering already exists.

## Open questions (not yet asked)

1. **When did the 12-month contract start?** Commercially the most important unanswered question. If they are early in the term, leaving EposNow means paying two subscriptions or paying an exit penalty. This sets the realistic go-live date and may push the whole deal out by months.
2. **Integrated counter printer: make/model + connection type?** (Pending from Imran.) Ethernet → trivial. USB into the locked Android till → they need a separate device we control, plus a local print bridge.
3. **Can they open a browser on the existing EposNow till and load any URL?** One-minute test, decides whether they buy a tablet.
4. Is the cash drawer kicked by the counter printer? If yes, our ESC/POS work covers it at no extra cost.
5. Order volume on a busy night / peak hour — sizes print throughput.
6. Internet reliability at the shop — we have **no offline mode**; if the line drops the till stops.
7. Number of sites — one shop or more?

## Build implications

Required for this client, in dependency order:

1. **Multi-currency (GBP)** — ~1-2 days. Without it any demo shows Rupees. Blocks even showing them the system credibly.
2. **Network ESC/POS printing** — kitchen printer is Ethernet, so the clean TCP:9100 path is viable. Needs printer config (IP/port per station), ESC/POS builder, and **kitchen ticket routing to a printer** rather than only to the KDS screen.
3. **Counter receipt printing** — blocked on the pending model/connection answer.
4. **Website + checkout + Stripe** — full storefront build. Stripe account already exists.

Not needed for this client: KDS (built, unwanted), Foodpanda/aggregator integration (no platforms), FBR/PRA (UK, not Pakistan).

---

# MEETING OUTCOMES — video call 2026-07-26 15:27

**Everything above this line predates the call.** Where the two conflict, this section wins.
Full transcript: `docs/CHICK_SHACK_UK_MEETING_TRANSCRIPT_2026-07-26.md`.
All facts here are **client-stated on a recorded call** — stronger evidence than the WhatsApp
notes above, but still not independently verified.

## 1. The scope changed shape — this is NOT a POS displacement

The client stated it twice, unprompted and unambiguously:

> *"Just to clarify, I'm looking to **keep the current system I have for the in-house**. All I'm
> looking to do at the moment is I'm looking to **activate online ordering for the takeaway**."*

Target architecture, in his own analogy — *"a bit like a **Uber Eats tablet or a Just Eat order pad**"*:

| | System | Owner |
|---|---|---|
| In-house / counter / phone orders | **EposNow** (unchanged) | Incumbent, stays |
| Online orders from his website | **Ours** — website + checkout + order-view tablet | New build |

The two run **side by side, deliberately unreconciled**. He was explicitly walked through the
split-books consequence (£15k on EposNow + £3k on ours = £18k real, EposNow records only £15k)
and accepted it: *"That's fine, I'm happy to keep it separate."*

## 2. ANSWERED: the #1 open question — EposNow contract

> *"It started in **June**, so I've got another year left."*

Contract runs to approximately **June 2027**. But this **no longer gates go-live**, because we are
not displacing anything. It only sets the earliest date for the in-house upsell. Sitara advised him
to see the term out rather than eat a double subscription — correct advice, and it costs us nothing
now that the online channel can ship independently.

## 3. Confirmed requirements

| Requirement | Client's words | Status in our code |
|---|---|---|
| Full menu on the ordering website | *"it'll have the full menu on there"* | ❌ No storefront |
| **Merchant accept / reject** each order | *"we can accept or reject"* | ❌ **Does not exist.** No accept/reject gate in the state machine |
| **Lead time / ETA sent to customer** | *"then we'll give you a lead time on how long it's going to take to deliver"* | ❌ **Does not exist.** No ETA field, no customer notification channel |
| Pay online via **Stripe** | *"you need to set up a payment gateway through Stripe, which I've already made"* | ❌ `PaymentGateway` is an abstract stub |
| **Cash on delivery** as customer choice | *"or the customer can choose to pay on delivery. It will be up to them"* | ❌ Needs unpaid-order path through checkout |
| **Delivery** (not collection-only) | *"how long it's going to take to deliver"* | ❌ No addresses/zones/fees in storefront |
| Live order feed on a tablet | *"all the tablet has to do is open a link… you'd see live orders flowing in"* | ⚠️ Closest existing thing is the **KDS he declined** |
| **Owner backend dashboard** on its own login | *"daily sales… how many orders I had… my percentages"* | ✅ **We already have this** — AdminDashboard KPIs, Reports, Z-report |
| WhatsApp-based change requests | *"I'd message them and say could you please change this"* | ⚠️ Sitara committed: *"exactly the same case… I'd be your point of contact"* |

## 4. EXPLICITLY DECLINED — do not put these in the proposal

- **Accounting integration of any kind.** *"I've not integrated EposNow with any QuickBooks or any
  accounting software. I'm not intending to do that either… I don't want to give them too much
  information and I don't want any kind of another app or something to record my sales."*
  Our QuickBooks Online integration — the single largest integration investment in this product —
  **has no value to this client.** Sitara offered cross-system P&L aggregation; he refused it.
- **Reconciling the two systems' sales figures.** Refused, knowingly.
- **KDS.** Previously declined in chat; the call did not revisit it. Note the irony: the "tablet
  showing live orders" he *does* want is KDS-shaped.

## 5. Hardware — the earlier findings are now moot

He will supply his own, from stock on hand:

> *"I have got a **spare tablet** and I've got a **spare printer** somewhere which I can find."*

- Any basic Android tablet is fine — Sitara set that expectation on the call and he agreed.
- **The spare printer is an unknown quantity** — no make, model, or connection type. This replaces
  the earlier "integrated counter printer, model pending" question, which is now irrelevant since
  we are not touching the EposNow till or its printers at all.
- **The locked-till question is dead.** He is buying/using a separate tablet regardless, so whether
  a browser opens on the EposNow terminal no longer matters.

## 6. Domain & hosting

- **Domain: owned already**, registered at **FastHost**. *"I've bought the domain out."*
- **Hosting: does not exist yet.** *"We're gonna need to get hosting."*
- ⚠️ Sitara committed to *"build something in the coming week **once I have the domain and hosting
  access**"* — so hosting is a **blocking dependency on a commitment already made**.
- ⚠️ **Technical note not raised on the call:** FastHost's standard shared hosting is LAMP-style and
  will not run our React + FastAPI + Postgres stack. Realistically we point his FastHost **DNS** at
  our own infrastructure. Only DNS access is actually needed — not "hosting access". This needs
  correcting with him before it becomes a misunderstanding.

## 7. Commercial

Pricing structure floated on the call (no numbers given):
1. One-time — website build + hosting setup
2. One-time — POS implementation at the restaurant
3. *"Minimal"* monthly maintenance fee

**Sitara committed to returning with commercials — *"give us a couple of days"*** (i.e. by ~2026-07-28).

### Referral pipeline — the main commercial upside

> *"If obviously this is gonna be good to go, I can put you in touch with **three or four other
> people in the UK** who are looking to move away from their current supplier… we can then move
> **my uncle** over as well and I can give you another two people."*

- **Ali Fish and Chips** — his uncle, nearby. Currently pen-and-paper + cash register + a separate
  online-order tablet. No EPOS at all. Was using a local UK developer who *"has been messing me
  around."* This is the reference model the client wants copied — and a warm lead.
- Total implied pipeline: **the uncle + 3–4 others + 2 more = up to ~6 UK sites.**
- ⚠️ Treat as **unqualified and unpriced**. These were offered *before* seeing a quote, which is when
  referrals are cheapest to promise. Do not discount this deal against them — structure any referral
  benefit to pay out on signature, not on introduction.

## 8. Unanswered / new open questions

1. **"Which database is it?"** — the client asked this directly at 11:05 and **it was never answered**;
   the call moved straight to costing. He is more technical than the earlier notes assumed. Answer it
   unprompted (PostgreSQL 16), it costs nothing and builds credibility.
2. **How does the customer receive the ETA?** SMS, email, on-screen, WhatsApp? Not discussed. Has a
   real cost (SMS gateway) and a real build implication.
3. **Delivery mechanics** — zones, radius, delivery fee, minimum order? He said "deliver" but no rules.
4. **Menu** — who supplies it, in what form, how many items/modifiers? Nobody asked.
5. **Spare printer make/model/connection.**
6. **Opening hours / order scheduling** — can customers pre-order for later? Not discussed.
7. **Who owns the Stripe account and is it verified/live?** He has "an account"; unclear if activated.
8. **Name ambiguity, unresolved:** the recording is filed as `rizwan uk meeting.mp4`, but the contact
   of record in the WhatsApp notes is **Imran R**, and at 13:06 Sitara asks whether *"Fizan… or
   **Rizwan**"* has questions — implying Rizwan is a **third** person on the call, not the client.
   "Rizwan" appears nowhere else in this repo. **Confirm who is who before any document goes out
   with a name on it.**

