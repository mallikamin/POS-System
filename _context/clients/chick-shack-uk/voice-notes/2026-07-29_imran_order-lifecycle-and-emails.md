# Imran voice note — 2026-07-29 02:32 PKT (21:32 UK, 2026-07-28)

**Source:** `WhatsApp Ptt 2026-07-29 at 2.32.59 AM.ogg`, 2m08s.
**Transcribed** locally with faster-whisper (`small`, CPU). Language detected `en` at p=0.83.
Lightly punctuated; wording is his. Transcription is machine-made — treat exact phrasing as
approximate, the substance as reliable.

**Why it matters:** this is the first time the client has described the *whole* order lifecycle
end to end, unprompted. It answers OI-29 (how the ETA reaches the customer) and independently
confirms the served/delivered gap Malik had already spotted.

---

## Transcript

> Assalamu alaikum. Okay. So basically when a customer places an order through the website, first
> of all, if they're new to the website, they go through the checkout process, they will then need
> to input their details into the website. So they have to put their email address, their address,
> the contact number, etc.
>
> Anyway, so once the order is sent through and it comes to the takeaway, the guys here will then
> either accept or reject. If the order is accepted, the customer then gets a confirmation email to
> say the order has been confirmed and it will be delivered between this time.
>
> So let's say the customer places an order at 2pm, they put a pre-order in because we open at 4pm.
> Let's say they place an order at 2pm, they'll receive an email to say, as soon as they've placed
> an order, a confirmation email. And then when we come in at 3.30 or 3 o'clock and we accept the
> order, then we'll give a lead time between 30 minutes to an hour, depending on the location of the
> delivery, or if it's a collection, depending on how quickly the boys can get it ready. Then that
> confirmation will then get sent to the customer's email to confirm the order has been confirmed by
> Chick Shack and it will be delivered between this time, or it'll be ready for collection at this
> time.
>
> Now, when the boys start making the order and it's ready for delivery, they will need to be a
> button on the tablet that would say "market for delivery" [mark for delivery] — so it would say
> "out for delivery" and then just need to press that button. So the customer's notified that,
> listen, the food's on its way.
>
> If you think this is the simple way of doing it fair enough, if you think we can do without the
> out for delivery button fair enough, your thoughts will be highly appreciated. Thank you.

---

## What he is asking for

1. **Two emails, not one.**
   - On placement: "we've got your order".
   - On accept: "confirmed by Chick Shack, delivered between X, or ready for collection at X."
2. **Pre-orders are a primary use case, not an edge case.** His own worked example is an order placed
   at 14:00 for a shop that opens at 16:00, accepted by staff at 15:00-15:30.
3. **An "Out for delivery" button on the tablet**, pressed when the food leaves, notifying the customer.
4. He explicitly invites pushback on point 3: *"if you think we can do without the out for delivery
   button fair enough, your thoughts will be highly appreciated."*

## What he did NOT mention

- **Payment.** Not once, in a full description of the lifecycle. Consistent with cash on
  delivery/collection and with `cardPaymentEnabled = false` (OI-41). Do not read it as approval of
  card payment being absent, but it is not what he is asking for either.
- **SMS.** He said email every time. Email is the channel.

## Assessment against what is built (2026-07-29)

| What he described | Reality |
|---|---|
| Customer enters email, address, phone at checkout | ✅ Built — **but email is optional, and is discarded** (see below) |
| Shop accepts or rejects | ✅ Built |
| Pre-order at 14:00, accepted at 15:30 | ✅ **Already works.** Orders sit `confirmed` until staff act; nothing is time-gated |
| Lead time set at accept, 30-60 min | ✅ Built — the tablet's one-tap ETA is 15-90 min |
| Email on placement | ❌ **Not built.** No email exists anywhere in this system |
| Email on accept, carrying the lead time | ❌ **Not built.** The customer only sees it by keeping the tab open |
| "Out for delivery" button | ❌ **Not built.** This is the served/delivered gap |

⚠️ **`customer_email` is accepted by `POST /public/{tenant}/orders` and then silently dropped.**
`Order` has no email column and `_link_customer` never sets `Customer.email`, though that column
exists. Nothing can be emailed to anyone today even if a sender existed.

⚠️ **His main scenario defeats the current design.** The confirmation screen learns the ETA by
polling, and gives up after 20 minutes. Nobody keeps a tab open from 14:00 to 15:30. So for the
pre-order case he describes as normal, **the customer would never learn their order was accepted.**
Email is therefore a go-live blocker, not a refinement.
