# EposNow integration — research brief (OI-87)

**Raised by Malik, 2026-08-17. Research task, nothing built, nothing promised to the client.**

## The problem, in Imran's terms

Chick Shack runs **EposNow** as its till for in-house, dine-in and phone/call-centre orders. We
supply the **online channel only** (website, Stripe checkout, order tablet). The two do not talk.

**So every online order is typed into EposNow by hand**, by his team, purely so the till shows it as
paid and the day reconciles. That is double entry on every single order: slow, error-prone during
service, and it scales badly — at ~8-10 online orders a night it is already a chore, and the whole
point of the online channel was to add revenue without adding work.

**What we want to find out: can we push our orders into EposNow automatically, and if so how.**

## What is already established, and must not be re-litigated

- 🔴 **This is NOT an EposNow displacement and never was.** Settled on the 2026-07-26 call and
  recorded in `docs/history/README.md` as a superseded framing. He keeps EposNow; we added a
  channel. **Any integration must respect that**: we push into their system, we do not replace it,
  and nothing we propose should read as a land-grab. The commercial deal is £300 build + £35/month
  for the online channel.
- **The receipt printer is already shared.** Ethernet, TCP:9100, and TCP queues jobs from multiple
  systems, so our tickets and EposNow's coexist on one printer today
  (`PAUSE_CHECKPOINT_2026-07-27-B.md`). Precedent that the two systems can share hardware.
- **We have a transcribed walkthrough of his actual EposNow menu setup**, with frames:
  `_context/clients/chick-shack-uk/voice-notes/2026-07-29_imran_eposnow-menu-walkthrough.md` and
  `refs/eposnow-menu/`. **Read this before asking him anything** — it may already answer questions
  about how his products, meals and modifiers are structured, which matters for mapping.
- **EposNow runs on Android** in his shop (`PAUSE_CHECKPOINT_2026-07-26.md`).
- Our order numbers already carry a collection/delivery marker (`260817-C001`, `260817-D002`), added
  at Imran's request on 2026-08-04.

## The lead worth chasing first

📌 **Malik, from memory and therefore UNVERIFIED:** Imran wanted receipt customisation showing the
`C001` / `D001` style numbering "as we have done", and **one of his EposNow account managers, named
Sam, did some technical plumbing and delivered that customisation.**

**Why this matters more than it looks:**
1. It suggests EposNow will do bespoke technical work for this account, and that there is a named
   person who has already done some.
2. **Sam is a warm technical contact inside EposNow** — far better than a cold support ticket for
   establishing what the API can actually do on Imran's specific plan.
3. Whatever Sam changed may itself indicate the integration surface available (an API, a webhook, a
   back-office import, or something cruder).

⚠️ **Verify this before acting on it.** It is Malik's recollection, not a record. Confirm with Imran:
Sam's surname, their role, and what exactly was customised.

## What the research needs to answer

**A. Capability — what can EposNow actually do?**
1. Does EposNow expose a **public API** for creating transactions/orders, and on which plan or
   tier? Is it included in what Imran pays, or an add-on with a fee?
2. Can an externally-created order be pushed in **already marked as paid**, with the payment method
   and the tender split, so it reconciles without a human touching it?
3. Are there **webhooks** the other way (so we could learn about EposNow-side events)?
4. Is there an **existing marketplace/integration** for online ordering (Deliveroo, Just Eat,
   Uber Eats and others integrate with EposNow) — and if so, **can we present as one**? That is
   frequently the cheapest path: a documented, supported route that already exists, rather than a
   bespoke build.
5. What are the **rate limits, sandbox availability and auth model** (OAuth, API key, per-device)?

**B. Mapping — will the data actually line up?**
6. Our menu and his EposNow menu are **separate catalogues**. A pushed order references products by
   EposNow's ids, so something must map ours to his. How is that maintained when either side changes
   an item? **This is the part that quietly rots**, and it is worth more design thought than the
   transport.
7. **Meals vs solo items are separate products in EposNow, not conditional modifiers** — established
   from the 07-29 walkthrough. Our storefront models them with modifier groups. That mismatch is
   real and needs a mapping strategy.
8. Tips, the platform fee and delivery fee: where do they land in EposNow so the numbers reconcile?
9. What happens on a **refund, void or rejected order** after it has been pushed?

**C. Commercial and practical**
10. Who pays for the API access if it costs money, and does it change the £35/month?
11. **Is this in scope of the current deal at all, or is it a new paid piece of work?** Malik's call,
    but the research should say what it would cost us to build and maintain.
12. What is the fallback if EposNow's API is closed, expensive or crippled? Candidates worth costing:
    a CSV end-of-day export he imports, a shared report that makes manual entry faster rather than
    unnecessary, or accepting the manual step and reducing it to a daily batch rather than per order.

## Constraints to design within

- 🔴 **`chickshackg84.com` is live and taking real orders.** Nothing experimental touches the live
  path. Trading hours 16:00-22:00 UK; deploy only when shut.
- **Never send credentials into chat or commit them.** EposNow API keys go in
  `INFRASTRUCTURE_CREDENTIALS_REFERENCE.md` and `.env.demo` only, same as QuickBooks.
- **Do not repeat the QuickBooks Desktop mistake**: that was scoped at six weeks, built to 33%, and
  parked. **Establish that the API exists and works on Imran's actual account before designing
  anything**, and prefer a documented existing integration route over a bespoke one.
- ⚠️ **Verify vendor claims against EposNow's own current documentation, never from memory**, and
  record the URL and the date checked. Same standing rule as the Brevo and what3words research.

## Suggested order of work

1. Read the 07-29 EposNow walkthrough and frames already in this folder.
2. Research EposNow's developer documentation: API existence, auth, order creation, payment
   marking, plan requirements, sandbox. Record URLs and dates.
3. Check whether an online-ordering partner/marketplace route exists that we could use.
4. Only then, draft the questions for Imran — and specifically the ask to introduce us to **Sam**.
5. Write up options with effort and cost, and a recommendation. **Do not build.**

## Deliverable

A written recommendation in this folder, plus an OI-87 entry in `_state/open-items.md`. Nothing
built, nothing sent to Imran without Malik approving it first.
