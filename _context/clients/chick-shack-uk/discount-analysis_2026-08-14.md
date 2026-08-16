# Chick Shack: Imran's "10% off over £50" proposal, analysed

**Date:** 2026-08-14 (query run), written up 2026-08-15 PK
**Open item:** OI-82
**Status:** ANALYSED. Nothing built, nothing authorised, nothing sent to Imran.
**Artifact (plain-English page):** https://claude.ai/code/artifact/5fc8f9a0-9683-41f9-b45a-9d9c845f2a98

---

## The ask

Imran proposed, via Malik, 2026-08-14: **10% off any online order over £50.**

## The verdict in one line

**Don't run it as proposed.** £50 sits above the 93rd percentile of his own baskets. It pays a
guaranteed ~£42 a fortnight to seven customers who already spend that much, and the pool of people
close enough to be pulled up to £50 is **three orders**, averaging **£2.73** short. If a threshold
offer is wanted at all, **£40 is the mathematically best line and £50 is the worst on the board**.
But the real opportunity is not at the top end at all.

---

## 1. Data source and method

Read-only query against the **production** database (`159.65.158.26`,
`pos-system-postgres-1`), tenant `chick-shack` = `8b2b6223-7db9-443b-8ace-34dd115a9275`.
No writes, no schema change, no restart.

Orders counted with the system's own `is_real_order()` predicate
(`backend/app/services/order_visibility.py`): cash-on-delivery, or Stripe authorised, or already
accepted/rejected by the shop. Then **rejected and voided rows removed**. From a raw table of 116
that excludes **4 abandoned/declined card checkouts, 4 rejected, 4 voided**.

All figures are **food subtotal** (`orders.subtotal`) unless stated. Delivery fee, platform fee and
tip are excluded, because a discount would sensibly apply to food only.

⚠️ **The dataset is live and moves while you query it.** Counts crept 108 → 109 → 110 → 111 across
the session as real orders landed. Each table below states the count it was computed at. Re-run
before quoting to a client.

**Period covered: 31 Jul to 14 Aug 2026, the whole trading history of the online channel.**

---

## 2. Headline shape (110 orders)

| Metric | Value |
|---|---|
| Orders | 110 |
| Food revenue | £2,750.44 |
| Average order | **£25.00** |
| Median order | £22.95 |
| 75th percentile | £32.06 |
| 90th percentile | **£38.15** |
| Orders over £50 | **7 (6.4%)** |
| Orders per trading day | ~7.2 |

**The 90th-percentile order is £38.15.** Nine customers in ten never come within £12 of £50.

### Band breakdown (as requested)

| Band | Orders | % of orders | Money | % of money | Avg in band |
|---|---:|---:|---:|---:|---:|
| Under £25 | 66 | **60.0%** | £1,092.89 | 39.7% | £16.56 |
| £25 to £38 | 32 | **29.1%** | £1,018.27 | 37.0% | £31.82 |
| £38 to £50 | 5 | 4.5% | £218.27 | 7.9% | £43.65 |
| £50 and over | 7 | 6.4% | £421.01 | 15.3% | £60.14 |

**89% of orders are under £38.** There is no gentle on-ramp to £50; the £40 to £45 band is
completely empty.

### By channel

| Channel | Orders | Avg | Median | Over £50 | Avg delivery fee |
|---|---:|---:|---:|---:|---:|
| Delivery | 68 | £27.17 | £24.37 | 6 | £3.78 |
| Collection | 40 | £21.07 | £21.22 | 1 | n/a |

Delivery baskets run ~£6 larger and hold 6 of the 7 orders over £50. Delivery fee bands actually
charged: £3.00 (45 orders), £4.00 (7), £4.50 (12), £6.00 (1), £7.00 (1), **£10.00 (3)**. Any
free-delivery offer needs a cap because of the rural £10 drops.

---

## 3. The two groups the offer splits into

### Group 1: the 7 who already qualify. Pure giveaway.

| Order | Date | Type | Food | 10% off |
|---|---|---|---:|---:|
| 260807-D007 | 7 Aug | delivery | £65.72 | £6.57 |
| 260804-003 | 4 Aug | delivery | £65.12 | £6.51 |
| 260812-D006 | 12 Aug | delivery | £64.65 | £6.47 |
| 260804-D008 | 4 Aug | delivery | £59.91 | £5.99 |
| 260804-002 | 4 Aug | delivery | £57.72 | £5.77 |
| 260814-C001 | 14 Aug | collection | £56.43 | £5.64 |
| 260802-001 | 2 Aug | delivery | £51.46 | £5.15 |
| | | | **£421.01** | **£42.10** |

**£42.10 per fortnight, ~£85/month, ~£1,020/year**, handed to people who needed no persuading.
This cost is certain.

### Group 2: the 5 who could conceivably be moved.

| Order | Date | Food | Short of £50 | Would receive |
|---|---|---:|---:|---:|
| 260813-D003 | 13 Aug | £49.91 | £0.09 | £5.00 |
| 260812-D009 | 12 Aug | £46.00 | £4.00 | £5.00 |
| 260811-D005 | 11 Aug | £45.90 | £4.10 | £5.00 |
| 260803-005 | 3 Aug | £38.42 | £11.58 | £5.00 |
| 260807-D006 | 7 Aug | £38.04 | £11.96 | £5.00 |

**The top three add less than they receive.** Everyone else, 98 of 110 orders, is too far away
to care.

---

## 4. The break-even arithmetic

**⚠️ ASSUMPTION, not measured fact: 65% food gross margin.** Industry-typical for a UK chicken
takeaway. **Only Imran has his real food cost.** Every figure in this section moves with it, and
this is the first question to put to him.

Nudging a basket from `S` up to `£50`:

```
gross profit gained = (50 - S) x 0.65
discount paid       = 50 x 0.10 = £5.00
pays only if        (50 - S) x 0.65 > 5.00   ->   S < £42.31
```

**A nudge only pays if the customer was going to spend under £42.31 and you move them the full
way to £50**, i.e. they must add at least **£7.70** of food. The three orders in the £45 to £50
band average £47.27, so each is at roughly **minus £3.20**.

Sensitivity: at 55% margin the break-even is `S < £40.91`; at 75%, `S < £43.33`. **The conclusion
holds across the whole range** because the nudge pool is 3 to 5 orders either way.

Volume break-even, `N` extra £50 baskets per 15 days, solving `N(50-S)(0.65) = 42.10 + 5N`:

| Each jumping from | N needed |
|---|---:|
| £40 (a £10 jump) | **28** |
| £35 (a £15 jump) | **9** |

The entire £30 to £50 pool contains **24 orders**. The first case is arithmetically impossible;
the second needs 43% of every mid-sized basket in the shop to grow by half.

---

## 5. Where the line SHOULD go, if there is to be one

For each candidate threshold: who gets it free, what 10% costs, and how many sit close enough
below to be tempted.

| Line at | Get it free | Cost of 10% | Pool within £8 below | **Pool per giveaway** |
|---:|---:|---:|---:|---:|
| £20 | 66 | £216.21 | 24 | 0.36 |
| £22 | 60 | £203.60 | 23 | 0.38 |
| £25 | 44 | £165.76 | 33 | 0.75 |
| £28 | 40 | £154.89 | 26 | 0.65 |
| £30 | 32 | £131.48 | 28 | 0.88 |
| £32 | 27 | £115.78 | 22 | 0.81 |
| £35 | 17 | £82.32 | 25 | 1.47 |
| **£40** | **10** | **£56.28** | **17** | **1.70** |
| £45 | 10 | £56.28 | 4 | 0.40 |
| £50 | 7 | £42.10 | 3 | **0.43** |

**£40 is the peak. £50 is the worst line on the board**, worse than putting it at £25. Too low and
everyone qualifies free; too high and nobody can reach. Imran picked the far side of the peak.

### Costed offer variants, same 15 days of real orders

| Offer | Orders hit | Cost / 15 days | ≈ / month | Note |
|---|---:|---:|---:|---|
| 10% over £50 *(as proposed)* | 7 | **£42.10** | £85 | Almost pure giveaway |
| 5% over £50 | 7 | £21.05 | £43 | Halves bleed and pull; too weak to notice |
| 10% over £40 | 10 | £56.28 | £113 | Best ratio, higher cost |
| 10% over £35 | 17 | £82.32 | £165 | Reaches real customers, double the cost |
| £3 off over £35 | 17 | £51.00 | £102 | Fixed, so a big basket can't run up the bill |
| Free delivery over £40 | 9 | £41.00 | £82 | Strong hook, but the £10 rural fees bite |
| Free delivery over £35, capped £4.50 | 15 | £57.00 | £114 | Caps rural exposure; delivery only |
| **Free can over £35** | **17** | **≈ £7** | **≈ £14** | £1.79 perceived, ~40p cost |
| Free side over £40 | 10 | ≈ £12 | ≈ £24 | ~£1.20 cost vs £5.63 for the 10% |

⚠️ **A percentage costs MORE the bigger the basket** (10% of £65 = £6.50 vs £5.00 at £50), so it
pays out most to the customers who needed convincing least. **A capped give is structurally
better**: a free side costs the same at £50 and at £65.

**Free-item costs (~40p a can, ~£1.20 a side) are estimates.** Confirm against Imran's actual
purchase prices before quoting them to him.

---

## 6. THE ACTUAL OPPORTUNITY: the bottom of the menu, not the top

### Items per order (111 orders)

| Items | Orders | Share | Avg order |
|---:|---:|---:|---:|
| **1** | 27 | 24.3% | **£12.39** |
| **2** | 32 | 28.8% | **£19.70** |
| 3 | 22 | 19.8% | £28.38 |
| 4 | 16 | 14.4% | £30.99 |
| 5 | 4 | 3.6% | £44.87 |
| 6 | 5 | 4.5% | £49.47 |
| 7 | 3 | 2.7% | £46.29 |
| 9 | 1 | 0.9% | £46.00 |
| 13 | 1 | 0.9% | £64.65 |

**53% of orders are one or two items averaging under £20.** That is 59 orders a fortnight against
7 over £50. **The block being ignored is eight times larger than the block being discounted.**

### Attach gaps by band (111 orders)

| Band | Orders | No side | No drink | No dip | **None of the three** |
|---|---:|---:|---:|---:|---:|
| Under £25 | 67 | 57 | 59 | 64 | **50** |
| £25 to £38 | 32 | 13 | 31 | 31 | 13 |
| £38 to £50 | 5 | 0 | 4 | 4 | 0 |
| £50+ | 7 | 1 | 7 | 5 | 1 |

**50 orders a fortnight are a burger or a piece of chicken and nothing else.** Note the contrast:
in the £25 to £38 band only 13 of 32 lack a side, so customers who order a bit more already know
to add chips. **The small orders are where the attach behaviour is missing.**

Only **10 of 111** orders contain a standalone drink (£23.27 total). Dips: 7 orders (£12.87),
though dip tubs sell better as modifiers (Garlic Mayo 32x = £31.68, Peri Peri 11x = £10.89).

### What a lift is worth, against what the discount costs

| | Per fortnight |
|---|---:|
| Cost of 10% over £50 | **minus £42** |
| +£1 on every order | plus £111 |
| +£2 on every order | **plus £222** |
| +£4 on every order | **plus £444** |

### Repeat behaviour (94 unique phones, 111 orders)

| Times ordered | Customers | Total spend | Avg lifetime |
|---:|---:|---:|---:|
| Once | **81** | £2,191.97 | £27.06 |
| Twice | 10 | £424.10 | £42.41 |
| Three times | 2 | £91.64 | £45.82 |
| Four times | 1 | £53.72 | £53.72 |

**81 of 94 customers ordered once and never came back (86%).** A two-time customer is worth
£42.41 against £27.06. **Converting 20 of the 81 is roughly £500**, twelve times what the
discount gives away.

---

## 7. Menu context

### Top items by revenue

| Item | Units | Revenue |
|---|---:|---:|
| Chick Shack Fillet Tower Burger Meal | 18 | £214.06 |
| Fried Tenders Meal | 15 | £169.74 |
| Double Chicken Burger Meal | 12 | £153.19 |
| Fried Chicken Meal | 11 | £112.80 |
| Fried Chicken | 14 | £104.85 |
| 2 Boneless Breast | 8 | £100.36 |
| Fried Tenders | 10 | £86.87 |
| Chicken Fillet Burger Meal | 8 | £82.49 |
| Spicy Fried Wings | 12 | £81.88 |
| Popcorn Chicken Meal | 11 | £80.86 |

### By category

| Category | Orders containing | Revenue |
|---|---:|---:|
| Burgers | 51 | £800.27 |
| Fried Chicken | 44 | £629.85 |
| Peri Peri Grilled | 31 | £401.40 |
| Wraps | 26 | £350.09 |
| Sides | 38 | £277.21 |
| Kids | 27 | £195.19 |
| Drinks | 10 | £23.27 |
| Dips | 7 | £12.87 |

### Structural facts worth keeping

- **A £50+ basket is 7.86 items; a sub-£50 basket is 2.72.** That is a bigger household, not an
  upsell. A discount does not turn two people into five.
- **Paid modifier upgrades already work**: chips upgrades alone have earned ~£42 (Peri Peri Fries
  20x £19.80, Large Peri Peri 11x £13.09, Large Fries 11x £8.69), plus wing portion upsizes
  (~£142 across 3pc to 16pc). **The same amount as the entire discount scheme would cost.**
  Upselling at the point of choosing is proven here; discounting has never been tried.
- **Weekday pattern**: Tue busiest (24 orders across 2 Tuesdays), Fri highest average (£29.38),
  Sat quietest (10 orders). Two weeks only, so treat as indicative.
- **Cheapest add-ons available**: dips 79p to 99p, Fruit Shoot / Water £1.49, cans £1.79,
  Gravy (8oz) £2.49.

---

## 8. Recommendation, ranked

1. **Checkout add-on prompt.** "Add chips £2.49 / a can £1.79 / a dip 99p." 50 orders a fortnight
   have none of the three. A quarter of them attaching one item is ~£30/fortnight at full price,
   no discount, compounding as orders grow. **Cheapest change on the list.**
2. **Attack the one-item order.** 27 orders, avg £12.39, when meal versions exist a couple of
   pounds up. A "make it a meal" prompt. The menu is already built for it.
3. **Repeat-purchase voucher.** 81 one-time customers. The review email that already fires 3h
   after every accepted order is the rail; a "£3 off your next order" code only costs anything
   when it works, and it targets the 81 rather than the 7.
4. **If a threshold offer is insisted on: £40, and a free item, not a percentage.**
   "Free side over £40" costs ~£1.20 a time instead of £5.63.

**Do not run 10% over £50.**

---

## 9. Open questions for Imran

1. **What is his actual food gross margin / food cost?** Everything in section 4 moves with it.
2. **What does a can and a portion of chips actually cost him?** The free-item costings are
   estimates.
3. **What is he actually trying to fix?** A bigger average order, more orders, or more repeat
   customers? These have different answers and he has proposed a tool for the first while his
   biggest gap is the third.

---

## 10. Build reality check

⚠️ **This is development work, not a setting.**

- `discount_amount=0` is **hardcoded** at `backend/app/services/public_order_service.py:572`.
- The storefront has **no promo/discount/voucher UI at all**: grep of `storefront/src` for
  `promo`, `discount`, `coupon` returns **zero hits**.
- Any version touches: storefront basket + checkout UI, server-side price calculation, the Stripe
  line items, `print_service.py` (the ticket), `email_service.py`, the tablet order card, and the
  reports/CSV.
- **Two deploy pipelines**: `git push origin main` for the backend + tablet, and
  `cd storefront && npm run deploy` (Cloudflare) for the customer site. See
  [[chick-shack-two-deploy-pipelines]].
- The checkout add-on prompt (recommendation 1) is **storefront-only and far cheaper** than any
  discount mechanism. It should be priced separately and probably done first.

---

## 11. Re-running this analysis

Working SQL is kept in this folder as `discount-analysis_queries.sql`. To run:

```bash
scp discount-analysis_queries.sql root@159.65.158.26:/tmp/q.sql
ssh root@159.65.158.26 "docker cp /tmp/q.sql pos-system-postgres-1:/tmp/q.sql && \
  docker exec pos-system-postgres-1 sh -c 'psql -U \$POSTGRES_USER -d \$POSTGRES_DB -f /tmp/q.sql'"
```

Read-only. Gotchas hit while writing it:
- `round(double precision, int)` does not exist in PostgreSQL. Cast: `round(x::numeric, 2)`.
  Bites on every `percentile_cont`.
- The modifier price column is **`price_adjustment`**, not `price`.
- Quoting nested SQL through `ssh` + `docker exec sh -c` breaks. **Upload a file, do not inline.**
