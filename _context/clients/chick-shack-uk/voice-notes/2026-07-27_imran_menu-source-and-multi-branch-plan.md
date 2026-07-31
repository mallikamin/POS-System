# Imran — WhatsApp voice notes, 2026-07-27 ~02:52

Machine-transcribed (faster-whisper `medium`) from two `.ogg` voice notes.
**These override several earlier assumptions.** Source files were in `C:\Users\Malik\Downloads\`.

---

## Note 1 (58s) — the menu, and delivery

> Assalamu alaikum. So **chick-shack.com, the menu is wrong.** You need to **pull the menu off our
> Google page**. If you Google "Chick Shack, Garelochhead, G84", our Google page will come up — **in
> the pictures the menu is on there.** So if you pull the menu off there… but there are **a few items
> that you need to add alongside that menu** [that they] have also added at the moment, which is not
> on the menu.
>
> chick-shack.com says **collection only because obviously we don't have a live website for online
> ordering at the moment. Once you put chickshackg84.com live, then the "collection only" I will have
> that changed.**

## Note 2 (51s) — what each domain is for

> **chick-shack.com is only an information website only.** The people that built this website, they
> put the menu on there and stuff, but **they should not have the menu** — it should only just be
> information. Because in the future, **once I want to franchise** or do something with it, then that
> would be **the main website for franchising** etc.
>
> **chickshackg84.com will be assigned to this branch for online orders.** If, inshallah, I open
> another branch, then they'll be like, for example, **chickshackg81 or g73** or something, according
> to the area and the location. So this is how I'm planning on doing this.

---

## What this changes

| Earlier assumption | Corrected |
|---|---|
| Menu scraped from chick-shack.com is usable | ❌ **WRONG MENU.** Client says so explicitly. Real menu is in the **photos on their Google Business listing**. Plus extra items not on it. |
| Collection-only vs delivery was ambiguous | ✅ **DELIVERY IS IN SCOPE.** "Collection only" is only there because they have no online ordering. He will change it at go-live. |
| chick-shack.com is their main site | It is **information only**, and is earmarked to become the **franchise** site. |
| chickshackg84.com is just "the second domain" | It is **this branch's ordering site**. Future branches get their own: `chickshackg81`, `g73`, etc. |

## ⚠️ Strategic implication — this is a multi-branch plan, not a one-off

He intends to **franchise and open more branches, one ordering domain per branch, named by postcode
district.** That is a repeatable per-branch deployment, not a single site.

Two consequences:
1. **Do not hard-code this as a one-shop site.** Branch identity (name, address, phones, postcode,
   delivery zones, menu) must be configuration, not literals baked through the code.
2. Our POS is already multi-tenant (`tenant_id` on every table), so each branch maps to a tenant. The
   storefront needs to become branch-parameterised to match.

Commercially this is a bigger opportunity than the £300 + £35/mo suggests — but it also means the
£35/mo anchors **every future branch**, on top of the ~6 referrals already anchored. Worth Malik
knowing before branch two.

## Immediate actions

1. **Get the real menu** from the Google Business listing photos (Google "Chick Shack Garelochhead
   G84", or the Maps link Imran sent: `https://maps.app.goo.gl/aUXuGUZCR1JTp7ew7`). The menu is an
   **image**, so it needs reading off photos, not scraping.
2. **Ask Imran for the extra items** that aren't on the Google menu either.
3. **Ask Imran to confirm prices** — the Google photos could be as stale as the website.
