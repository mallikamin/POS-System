# UK payment gateway options for a new restaurant client who won't use Stripe

**Context, 2026-08-01:** Imran (Chick Shack) is referring a second UK restaurant. Client is UK-based,
does not want Stripe ("has some issue," not yet specified), and named two banks he'd prefer:
Bank of Scotland/Lloyds, and Clydesdale Bank. This note is the research on what those two actually
are, plus alternatives, done before we know the client's name — move into their `_context/clients/
<slug>/` folder once Malik has it.

## The two banks he named

**Bank of Scotland and Lloyds Bank are the same product.** Both are Lloyds Banking Group, and both
sell merchant card acceptance through the same brand, **Cardnet®**. There is no separate "Bank of
Scotland gateway" — asking either bank gets you Cardnet.

- Online integration is **Cardnet's Integrated Payment Page**: a hosted/redirected payment page, or
  an embedded option ("Payment.JS") that keeps the card form on our own checkout page. The core
  protocol is an **older XML-based API**; some newer web-service/REST endpoints exist but the
  primary developer path is XML, not a clean JSON REST API like Stripe's. Ready-made plugins exist
  for WooCommerce/Magento/PrestaShop/OpenCart (via a third party, Autify Digital) — irrelevant here
  since this storefront is custom-built, not one of those platforms, so we'd integrate the raw
  Cardnet API ourselves.
- **Pricing seen:** flat **1.25% per transaction + £15/month minimum**, better rates for merchants
  who already bank with Lloyds/Bank of Scotland.
- Verdict: usable, but more integration effort than Stripe for a custom app, older-feeling API.

**Clydesdale Bank does not run its own payment gateway at all.** Clydesdale (which mostly trades as
Virgin Money since 2019) resells **Worldpay** for all online/phone/card-machine payments. If the
client signs up with "Clydesdale," they are actually signing up with Worldpay underneath, just
billed via Clydesdale.

- Worldpay's actual developer product ("Access Worldpay") is a **modern JSON REST API**, plus a
  **Hosted Payment Pages API**, a client-side Checkout SDK, and explicit **authorise → capture**
  support with a sandbox/simulation mode for testing before going live. This is a much closer match
  to how Stripe's API feels than Cardnet is.
- Verdict: since "Clydesdale" and "Worldpay" are the same integration either way, there's no reason
  to route through the Clydesdale relationship specifically unless it gets the client a better rate
  — worth asking, but technically go straight to Worldpay's docs.

## A third option worth mentioning: Opayo (Elavon)

Opayo is the rebranded Sage Pay, UK/Ireland business, owned by Elavon since 2020. Long track record
specifically in UK hospitality/restaurants. "Direct" integration gives full API control — authorise,
capture, void, refund — all remotely callable, no dependency on their hosted admin panel. 24/7
phone support. Similar shape to Stripe's manual-capture flow (this project already builds against
that exact pattern for Chick Shack), so it would be a comparably-sized integration effort to
Worldpay, not a redesign.

## What does NOT fit this project's payment model: Open Banking / "Pay by Bank"

TrueLayer and GoCardless (Instant Bank Pay / Pay by Bank) let a customer pay directly from their
bank app — popular in the UK, no card network involved, often cheaper per-transaction, and could
plausibly be what someone means by "avoiding Stripe's issues" if the actual objection is card-network
risk scoring.

**But it does not support this project's core payment rule.** Chick Shack's whole flow — and every
other online-ordering tenant we build the same way — authorises the card at checkout and only
**captures on Accept, cancels on Reject**, so a rejected order never actually takes the customer's
money. Open Banking payments are **instant and final**: the money moves the moment the customer
pays, there is no "hold it, then decide" step. Rejecting an order would mean manually refunding a
completed bank transfer, not cancelling a hold — a materially different (and slower, no automatic
release) customer experience for anyone the shop turns down. This is a real trade-off, not just an
integration detail — worth deciding deliberately, not defaulting into.

## Why a restaurant might genuinely have "an issue" with Stripe (context, not confirmed for this client)

Common pattern for small/new food-service merchants: Stripe holds a **reserve** (10-25% of each
transaction, released ~90 days later) or delays payouts when it flags a business as higher-risk —
triggers include a chargeback ratio above ~1%, a sudden change in sales volume, or landing in a
high-risk MCC bucket that restaurants can fall into. If that's this client's actual complaint, it's
worth knowing **any card acquirer (Cardnet, Worldpay, Opayo included) does similar risk-based
underwriting** — switching away from Stripe doesn't automatically avoid it. Open Banking is the one
option here that sidesteps card-network risk assessment entirely, at the cost described above.

## Open question before building anything

**What specifically went wrong with Stripe for this client?** The right recommendation depends on
the answer:
- KYC/onboarding rejected, or a reserve/hold on funds → any card gateway may hit the same wall;
  Open Banking is the one option that's architecturally different, but means redesigning the
  accept/reject flow around instant, non-reversible payments.
- Personal preference / already banks with Lloyds or Clydesdale → Cardnet or Worldpay both work
  fine as a like-for-like swap for the existing Stripe integration shape (authorise, capture on
  accept, cancel on reject) — Worldpay's API is the more modern of the two to build against.
- Cost → get real quotes; Cardnet's advertised 1.25%+£15/mo is a starting point, Stripe/Worldpay/
  Opayo all need a like-for-like quote for this specific client's expected volume.

Sources:
- [Integrated payment page | Cardnet | Lloyds Bank Business](https://www.lloydsbank.com/business/take-payments-with-cardnet/online-payments/integrated-payments.html)
- [Online payments | Cardnet | Lloyds Bank Business](https://www.lloydsbank.com/business/take-payments-with-cardnet/online-payments.html)
- [Developers | Lloyds Bank Cardnet](https://www.lloydsbank.com/business/take-payments-with-cardnet/online-payments/developers.html)
- [Merchant Services | Bank of Scotland Business](https://business.bankofscotland.co.uk/3m-25m-turnover/payment-services/merchant-services.html)
- [Take payments with Cardnet | Bank of Scotland Business](https://business.bankofscotland.co.uk/payment-services/cardnet.html)
- [Bank of Scotland Merchant Services Reviews: UK Fees & Pricing — Merchant Machine](https://merchantmachine.co.uk/bank-of-scotland-merchant-services/)
- [Payment solutions | Clydesdale Bank and Yorkshire Bank Merchant Services](https://www.cybmerchantservices.co.uk/payment-solutions/)
- [Clydesdale Bank Merchant Services Reviews: UK Fees & Pricing — Merchant Machine](https://merchantmachine.co.uk/clydesdale-bank-merchant-services/)
- [Get started with our Payments API — Worldpay Developer Hub](https://docs.worldpay.com/access/products/card-payments/v5/get-started)
- [Authorise, capture and settle — Worldpay Developer Hub](https://docs.worldpay.com/apis/wpg/apms/authorise-capture-and-settle)
- [Hosted Payment Pages (HPP) API — Worldpay Developer](https://developer.worldpay.com/products/access/hosted-payment-pages/openapi)
- [Hosted API payment — Elavon UK](https://www.elavon.co.uk/accept-payments/online/hosted-api-payment.html)
- [Types of integrations — Opayo — Elavon UK](https://www.elavon.co.uk/customer-centre/help-with-your-solutions/opayo/integrations/types-of-integrations.html)
- [Sage Pay — Wikipedia](https://en.wikipedia.org/wiki/Sage_Pay)
- [Reserves — Frequently Asked Questions — Stripe Help & Support](https://support.stripe.com/questions/reserves-frequently-asked-questions)
- [Stripe Account on Reserve UK | Why It Happens & What To Do](https://www.wetranxact.co.uk/stripe-account-on-reserve-uk/)
- [Pay by Bank & open banking payments | TrueLayer](https://truelayer.com/payments/)
- [Pay by Bank – Support Centre | GoCardless](https://support.gocardless.com/hc/en-gb/articles/4411785453714-Instant-Bank-Pay)
