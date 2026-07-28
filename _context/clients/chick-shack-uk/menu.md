# Chick Shack — menu, branding and shop details

> # ❌ THIS MENU IS WRONG — DO NOT USE FOR GO-LIVE
>
> Imran said so directly in a voice note on 2026-07-27:
> *"chick-shack.com, the menu is wrong. You need to pull the menu off our Google page… in the
> pictures the menu is on there."* He added that there are **extra items not on that menu either**,
> and that the previous developers *"should not have put the menu"* on chick-shack.com at all.
>
> **Replace with:** the menu photos on their Google Business listing
> (`https://maps.app.goo.gl/aUXuGUZCR1JTp7ew7`, or Google "Chick Shack Garelochhead G84").
> It is an **image**, so it must be read off photos — not scraped.
>
> Kept below only as a structural reference: the *shape* (categories, size variants with absolute
> prices, Mild/Hot, +£3 Meal) is almost certainly still right even though the items and prices are
> not. `storefront/src/data/menu.ts` currently holds this wrong data and must be regenerated.
>
> See `voice-notes-2026-07-27.md`.

**Source:** scraped from the client's own live site `https://chick-shack.com` (`/` and `/menu`),
2026-07-27. **Superseded — see the box above.**

---

## Brand

- **Name:** Chick Shack
- **Tagline:** *"Flame-grilled. Crispy fried. Unforgettable."*
- Positioning line: *"Premium fried chicken & peri peri — crafted fresh in Garelochhead"*
- Instagram: `@chickshack_`
- Existing site is built in **Next.js** (so almost certainly deployed on Vercel — this is very likely
  the same developer who left the `_vercel` records on `chickshackg84.com`). It is a competent
  brochure site. Our storefront must not look worse than it.

## Shop details

| | |
|---|---|
| Address | Main Street, **Garelochhead, Helensburgh, G84 0AN** (Scotland) |
| Phone | 07719 566 889 · 01436 653 143 |
| Opening hours | **7 days, 16:00–22:00** |
| Service model (per their own site) | **"Collection only at the moment"** |

> 💡 **The domain name is explained:** `chickshackg84.com` — **G84** is the Garelochhead postcode
> district. Not a random string.

## ⚠️ CONTRADICTION — must be resolved before building checkout

The live site says **collection only, no delivery**. But on the call Imran described delivery:
*"we'll give you a lead time on how long it's going to take to **deliver**"* and *"the customer can
choose to **pay on delivery**."* The proposal we sent quotes collection **and** delivery.

This materially changes scope. Delivery needs address capture, a delivery area, delivery charge,
minimum order, and a driver/dispatch step. Collection-only needs none of it.

**Ask Imran directly: is this launching collection-only, or is delivery starting with the new site?**

---

## Menu

Prices in GBP. `+£3 Meal` = meal upgrade modifier. `Mild/Hot` = required choice on peri peri items.

### Fried Chicken
| Item | Sizes / prices | Options |
|---|---|---|
| Fried Chicken | 2pc £4.99 · 3pc £6.99 · 4pc £7.99 | +£3 Meal |
| Fried Chicken + Wings | 2pc £6.99 · 3pc £9.99 · 4pc £11.99 | +£3 Meal |
| Spicy Fried Wings | 4pc £4.99 · 6pc £5.99 · 8pc £6.99 · 10pc £7.99 · 12pc £8.99 · 16pc £9.99 | — |
| Fried Tenders | 4pc £5.99 · 6pc £7.99 · 8pc £8.99 · 10pc £9.99 | +£3 Meal |

*Fried Chicken description: "Hand-coated in our signature spice blend, fried golden and crisp."*

### Peri Peri
| Item | Sizes / prices | Options |
|---|---|---|
| Peri Peri Wings | 3pc £6.99 · 5pc £7.99 | Mild/Hot · +£3 Meal · served with salad & coleslaw |
| Peri Tenders | 3pc £6.99 · 5pc £7.99 · 7pc £8.99 | Mild/Hot · +£3 Meal |
| Peri Peri Grilled Chicken — Half | Rice £10.99 · Chips £9.99 · Half-Half £10.49 | Mild/Hot |
| Peri Peri Grilled Chicken — Full | Rice £14.49 · Chips £13.49 · Half-Half £13.99 | Mild/Hot |
| Boneless Peri Peri Breast — 2pc | Rice £12.49 · Chips £11.49 · Half-Half £11.99 | Mild/Hot |
| Boneless Peri Peri Breast — 4pc | Rice £19.49 · Chips £18.49 · Half-Half £18.99 | Mild/Hot |

### Burgers  *(all +£3 Meal)*
| Item | Price | Options |
|---|---|---|
| Chicken Fillet | £6.99 | |
| Double Chicken | £8.99 | |
| Chick Shack Fillet Tower | £7.99 | |
| Peri Peri Burger | £7.99 | Mild/Hot |
| Double Peri Peri | £10.99 | Mild/Hot |
| ¼ Cheese Burger | £5.99 | |
| ½ Cheese Burger | £7.99 | |
| Veggie Burger | £5.99 | |
| Fish Burger | £5.99 | |
| **The Big Shack** | £10.99 | signature item |

### Wraps  *(all +£3 Meal)*
| Item | Price | Options |
|---|---|---|
| Chicken Fillet Wrap | £6.99 | |
| Double Chicken Fillet Wrap | £8.99 | |
| Peri Peri Wrap | £7.99 | Mild/Hot |
| Double Peri Peri Wrap | £10.99 | Mild/Hot |
| Veggie Wrap | £5.99 | |
| The Hot Chick | £6.99 | |

### Sides
| Item | Price | | Item | Price |
|---|---|---|---|---|
| Regular Chips | £3.49 | | Chilli Cheese Bites | £4.99 |
| Large Chips | £3.99 | | Corn on the Cob | £2.99 |
| Peri Chips | £4.29 | | Beans (8oz) | £2.49 |
| Onion Rings | £5.99 | | Gravy (8oz) | £2.49 |
| Plain Wedges | £4.29 | | Coleslaw (8oz) | £2.49 |
| Peri Wedges | £4.79 | | Spicy Rice | £3.99 |
| Hash Brown | £2.99 | | Salad Box | £2.99 |

### Kids  *(all +£3 Meal)*
| Item | Sizes / prices |
|---|---|
| Popcorn Chicken | Reg £3.99 · Lrg £4.99 |
| Nuggets | 4 £3.99 · 8 £7.99 · 12 £9.99 · 16 £11.99 |
| Mozzarella Sticks | 3 £3.99 · 6 £5.99 · 9 £7.99 |

### Dips  *(2oz tubs)*
Ketchup £0.79 · Mayo £0.79 · Garlic Mayo £0.99 · BBQ £0.99 · Burger Sauce £0.99 ·
Chilli Sauce £0.99 · Peri Peri Sauce £0.99 · Salsa Sauce £0.99 · Algerian Sauce £0.99

### Drinks
Pepsi £1.79 · Pepsi Max £1.79 · Fanta Orange £1.79 · 7up £1.79 · Fanta Pineapple Grapefruit £1.79 ·
Irn Bru £1.79 · Diet Irn Bru £1.79 · Water £1.49 · Fruit Shoot £1.49

---

## How this maps onto the existing POS menu engine

| Menu concept | POS model |
|---|---|
| 8 categories above | `categories` |
| Each named dish | `menu_items` |
| `2pc / 3pc / 4pc`, `Reg / Lrg`, `Half / Full` | **required, single-select** `modifier_group` with price *overrides* — note these are different base prices, not deltas |
| `Rice / Chips / Half-Half` | **required, single-select** `modifier_group`, price varies per choice |
| `Mild / Hot` | **required, single-select**, £0 |
| `+£3 Meal` | **optional, single-select** `modifier`, +£3.00 (300 pence) |
| Dips | ordinary items, also usable as optional add-on modifiers |

⚠️ Note the size variants carry **absolute prices, not increments** (e.g. Fried Chicken 2pc £4.99 →
4pc £7.99). Modelling them as additive modifiers would compute the wrong totals. They need either
price-override modifiers or separate items.

All prices go in as **integer pence** (£4.99 → `499`).
