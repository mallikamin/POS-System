# PAUSE CHECKPOINT — 2026-08-30

**Session:** Chick Shack Google Ads. Started as `/refresh` ("any order?"), became a keyword
overhaul, then a conversion-tracking diagnosis, then a two-pipeline deploy.
**Ended:** 2026-08-30 ~06:45 UTC. Shop shut, opens 16:00 UK.
**Git:** HEAD `9f45217` = `origin/main` = server. Two commits this session, both pushed.
**`STATE.md` carries the full detail. This file is the resume point.**

---

## RESUME HERE — the one thing outstanding

🔴 **`orders.ads_consent` is deployed but NOT proven.** No real order has written it yet.
**The first Chick Shack online order after 16:00 UK today is the test.** Read it back:

```sql
SELECT order_number, gclid, click_type, ads_consent,
       created_at AT TIME ZONE 'Europe/London' AS uk
FROM orders
WHERE tenant_id = '8b2b6223-7db9-443b-8ace-34dd115a9275'
  AND created_at >= '2026-08-30'
ORDER BY created_at;
```

Run via `ssh root@159.65.158.26` →
`docker exec pos-system-postgres-1 psql -U pos_admin -d pos_system -c "..."`.
Until a row comes back with `granted` or `denied`, this is **deployed, not working**.

---

## What was found (the substance)

**1. The first ad-attributed order exists.** `260829-D005`, £29.47, delivery, paid, 17:20 UK on
08-29, carrying a real `gclid`. First non-NULL `gclid` since F34.
⚠️ **The buyer was a RETURNER**, not a new customer — same phone `447526539001` ordered
`260827-C008` on 08-27. The ad re-bought someone who already knew the shop. **Do not present this
to Imran as customer acquisition.**

**2. 100% of the £19.14 spend went to BRAND terms.** Confirmed from the search terms report, not
inferred. Non-brand took **13 impressions in six days and zero clicks** — that is a demand ceiling
in a town of ~15k (Garelochhead ~1.5k), not a targeting or copy failure.

**3. Google reports 0 conversions BY DESIGN, not because anything is broken.** `index.html` defaults
consent to denied (UK PECR) and sets `ads_data_redaction`, which strips the click id when
`ad_storage` is denied. The tag itself is live and correct. Full reasoning in
`memory/google-ads-zero-conversions-is-consent.md`.

---

## What changed in the Google Ads account (CS-Ad1)

Malik drove all of this himself, step by step.

| # | Change |
|---|---|
| 1 | Negatives added: `indian`, `chinese`, `pizza`, `kebab`, `jobs`, `recipe` |
| 2 | **All six brand keywords paused** — `[chick shack]`, `"chick shack helensburgh"`, `"chick shack"`, `"chick shack menu"`, `"chick shack garelochhead"`, `"chick shack order online"` |
| 3 | Everything paused, then **ten re-enabled**: `"takeaway helensburgh"`, `"takeaway near me"`, `"food delivery helensburgh"`, `"takeaway garelochhead"`, `"fried chicken helensburgh"`, `"fried chicken near me"`, `"peri peri near me"`, `"chicken burger near me"`, `"best takeaway helensburgh"`, `"takeaway open now"` |
| 4 | RSA rewritten — four headlines swapped so the ad actually contains "takeaway" and "Helensburgh". **Ad strength Poor → Good.** Saved. |

**97 keywords → 10.** They were all in ONE ad group, which is why `"takeaway helensburgh"` (11 impr)
and `"takeaway near me"` (4 impr) both sat at *Limited / low quality* and took no clicks.

⚠️ **Watch on resume:** the brand pause is a live experiment. If online orders dip noticeably over
the coming week, the brand click was doing something and it goes back on.

---

## What shipped in code

`28d36df` — `orders.ads_consent`, the cookie-banner choice recorded on **every** order (the
denominator is the point). Migration `a9b0c1d2e3f4`. Also fixed `analytics.ts` calling `markFired`
when `gtag` was absent, retiring an order from reporting without sending anything.

`9f45217` — committed the F34 consent code that **was already live but had never been committed**
(`ConsentBar.tsx`, `consent.ts` untracked; `index.html`, `App.tsx` modified in the working tree).
A clean checkout would have rebuilt the storefront with no cookie banner and no Google Ads tag.

**Verified on the box, not assumed:** server HEAD `9f45217`, `alembic_version = a9b0c1d2e3f4`,
`orders.ads_consent` in `information_schema`. `pg_dump` taken first
(`/root/backups/pre-ads-consent-*.sql.gz`, `gzip -t` OK), deployed 01:26 UK with the shop shut.

🔴 **The two-pipeline trap fired and the bundle check caught it.** After the backend deploy the live
JS was **still `index-CAgFhDWT.js`** with zero hits for `ads_consent` — backend accepting a field the
browser had no code to send. `cd storefront && npm run deploy` produced **`index-Dclr8gPp.js`**;
`ads_consent` present, conversion id `xy0DCPb1kOccEL3z7slE` still present, `AW-18408520125` still in
`index.html`, site 200. **An unchanged bundle hash means nothing deployed.**

---

## Open, in the order I would take them

1. 🔴 **Prove `ads_consent` writes** on tonight's first order (query above).
2. 🔴 **`chick-shack.com` is organic #1 for the brand name and it is Imran's OLD site.** Its snippet
   pushes a phone number, and **Imran himself said its menu is wrong** (voice note 2026-07-27,
   `_context/clients/chick-shack-uk/menu.md`). The top free result serves customers wrong prices and
   bypasses online ordering. **Not ours to touch** — `_context/clients/chick-shack-uk/README.md:91`
   says touch only `chickshackg84.com`. This is one ask to Imran, and it bundles with the standing
   note that `chick-shack.com` is the better customer-facing URL. **Worth more than the whole ad
   budget and free to fix.**
3. ⚠️ **Where the GBP "Order pickup / Order delivery" buttons point.** Malik is a Manager on the
   profile and can set them. Unverified.
4. 🟡 **The offline conversion upload (OCI) from `orders.gclid`.** Malik parked it 2026-08-30:
   *"i dont know buddy. we'd upload the list in a couple of days when we have sufficient data pts."*
   **Blocked on a decision, not on code:** may we upload a click id for someone who declined
   advertising cookies? `ads_consent` now collects the evidence. **`NULL` is not `denied`.**
5. 🔵 **Auction Insights** — whether anyone else bids on the brand name is still unanswered. The
   incognito SERP check does NOT answer it: Malik searched from Pakistan (`rlz=…PK1133`) against a
   Helensburgh-geo-targeted campaign, so no ad would serve to him at all.
6. 🔵 Sitelinks — the only unticked item left on Google's own recommendation list.

---

## Corrections made this session, so they are not re-made

- I said the conversion tag "doesn't appear to be firing." **Wrong** — it is live in the bundle and
  fires. The cause is consent redaction.
- I said the `markFired` bug was a likely cause. **Overstated** — `index.html:37` declares `gtag`
  inline so it effectively always exists. Fixed anyway; it will not by itself produce conversions.
- I said the SERP screenshot showed no competitor bidding on the brand. **It cannot show that** —
  geo-targeting means no ads at all served to a Pakistani IP.
