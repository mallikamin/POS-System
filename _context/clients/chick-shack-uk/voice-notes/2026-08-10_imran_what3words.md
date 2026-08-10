# Imran voice note, 2026-08-10 01:56 (UK) — what3words for delivery locations

**Source:** `C:\Users\Malik\Downloads\WhatsApp Ptt 2026-08-10 at 1.56.59 AM.ogg`, 2m34s.
**Transcribed** locally with faster-whisper (medium, CPU). Lightly punctuated below; the wording is
his. Note the model renders "what3words" variously as "WhatThreeWords" and "what free words", and
"PostTag" as "post tag" — those are transcription artefacts, not different products.

## Transcript

> Assalamu alaikum. I wanted to ask you, if I wanted to incorporate something like an app or like a
> route confirmation type of thing into the website.
>
> There's an app called what3words, and what3words basically pinpoints the exact location of where
> you are standing. So for example, wherever you are in Pakistan, wherever you are standing right
> now, it will give you three words. And if you send those three words to someone, they'll need to
> use that app and they can basically pinpoint the exact location of where that person is.
>
> How do we basically influence people to kind of use this kind of app or service, or whatever it's
> called, to kind of pinpoint the exact location? Because the issue we have here is, because we cover
> up to 20 or 25 mile radius for deliveries, and there's not only house numbers but there's also
> names, and then some back roads, or they're in remote areas. Sometimes you may not be able to get a
> signal to obviously work out exactly where this person is.
>
> For example, I've just done a delivery right now, and this person was at this cottage, and they
> basically said "we're at Aston Cottage on Shore Road". When you put this into Google, it doesn't
> come up. When you put it into another app that we use, PostTag, it doesn't come up. We've had to
> physically ask the customer to come out to the road so we can obviously locate them.
>
> Whereas if we were to incorporate what3words — what3words is global and it basically pinpoints, I
> think it's like a square foot of where you physically are.
>
> I don't know if you think this is a good idea, or I don't know if you can advise on this. But for
> the security stuff, we use this app all the time, and it works really, really well. So I don't know
> if you can give me advice on this. Thanks.

## What he is actually reporting

**A real, recurring operational problem, described with a concrete case from that same night.** Not a
feature request dressed up as one:

- Delivery radius is **20 to 25 miles** around Garelochhead. Rural Argyll: named cottages rather than
  numbered houses, back roads, poor mobile signal.
- **"Aston Cottage, Shore Road" was not findable in Google Maps, nor in PostTag**, the tool they
  already pay for. The driver had to phone the customer and ask them to walk out to the road.
- He is **not directing a build.** Twice: *"I don't know if you think this is a good idea"* and
  *"I don't know if you can give me advice on this."* He wants an opinion first.
- His confidence comes from **his security business**, where he uses what3words routinely and it
  works. That is real evidence, but from a different use case: trained staff on both ends, versus a
  hungry member of the public at checkout.

## Open questions to settle before recommending anything

**None of this has been researched yet. Do not answer from memory.**

1. **what3words is a commercial, proprietary product.** Licensing and API pricing must be checked
   against their current published terms, not recalled. There is a free tier for low volume; whether
   a takeaway's checkout qualifies is unverified.
2. **The obvious free alternative was not considered by Imran and should be put to him:** capture the
   customer's device GPS at checkout via the browser Geolocation API and attach a plain
   maps link to the order. No third party, no licence, no app for the customer to install. It is
   accurate to a few metres in the open. Weakness: it only helps if they order **from** the delivery
   address, and it needs a permission prompt.
3. **what3words' own weakness in this exact scenario:** the customer must already have the app or
   visit the site to read their three words. Imran's phrase *"how do we influence people to use
   this"* is the whole problem, and it is a behavioural one, not a technical one.
4. There is documented criticism of what3words around similar-sounding word combinations resolving to
   distant places. Worth surfacing honestly given he wants to rely on it for navigation.
5. **A cheaper first move may beat both:** a free-text "how to find me" note plus a saved location on
   the customer record, so a hard-to-find address is only solved once. Chick Shack already stores
   customers.

## Where it would touch the code

- `storefront/src/components/Checkout.tsx` — the delivery address form.
- `storefront/src/data/menu.ts` — `DeliveryArea` definitions.
- `orders.delivery_address` on the backend; the tablet card and the printed ticket both render it.
- ⚠️ Any storefront change is a **Cloudflare deploy** (`cd storefront && npm run deploy`), not
  `git push`. See [[chick-shack-two-deploy-pipelines]].

**Status: NOTHING BUILT, NOTHING PROMISED.** Registered as OI-76. Next step is a conversation with
Malik about which approach, then a reply to Imran.
