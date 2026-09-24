# Danny's Restaurant Faisalabad: client index

Prospect, first contact 2026-09-24. Full-service restaurant, Sitara Villas, Canal Expressway,
Faisalabad (Google: 4.2 stars, 271 reviews). Interested in the complete module, **inventory and
recipe management above all**. Demo tenant on https://eats.sitaratech.info, slug `dannys`.

Everything for this client lives in this folder. Nothing about Danny's belongs in another
client's folder or only in the repo root.

## What is where

| File | What it holds |
|---|---|
| `INDEX.md` | This file |
| `CREDENTIALS_dannys-demo.txt` | Demo logins to hand to the client. Created by Malik by hand (the cred-guard hook refuses it to Claude). **Keep it out of git** |
| `backend/app/scripts/seed_dannys.py` (repo) | The seed that builds the demo tenant, idempotent. Its `USERS` list is the source of truth for the three demo logins |

Login link: https://eats.sitaratech.info/login?shop=dannys

## What the demo tenant holds (seeded 2026-09-24)

* **Menu:** 60 items in 16 categories, names and prices from Danny's own published menu
  (Instagram story, 2026-09). A subset of the card, not all of it. Half/Full karahis and
  Local/Imported steaks are separate items, so each has its own recipe.
* **Inventory chain, end to end:** 41 raw ingredients, 4 suppliers with catalogues, 3 purchase
  orders (one received, one sent, one draft), 7 in-house sub-recipes produced through the real
  production service (Karahi Masala Base, Naan Dough, Tikka and Malai marinades, Garlic Mayo,
  White Sauce, Black Pepper Sauce), 27 menu recipes costed from them.
* **Sales:** 11 completed orders over 4 days across dine-in, takeaway, phone and Foodpanda, each
  with a cash payment and a real stock deduction. Mozzarella sits below its reorder point on
  purpose, so the low-stock alert has a row.
* **Floor:** Main Hall (10 tables) and Outdoor Terrace (6). One kitchen station.
* **Tax:** PRA, 16% cash / 5% card, shown on top of menu prices.

## Standing facts and assumptions (unverified with the client)

* Recipes, quantities and ingredient costs are **placeholders**, not Danny's real ones.
* Tax-exclusive pricing is an assumption. Pakistani menus usually are; not confirmed.
* Foodpanda commission is a representative 25%, not their contract rate.
* Food photos are generic public Unsplash images, not Danny's. Five items (breads, kunafa) have
  no photo because no correct one was found; they show the plain placeholder.
* Mutton Karahi costs out at ~51% food cost at these placeholder prices. That is a talking
  point for the demo (costliest dish), not a claim about their real margin.

## Found while building this

A dine-in order that was served and then paid in full auto-completed **without deducting
stock** (`payment_service._sync_order_payment_status`). Fixed 2026-09-24 with a regression test
(`tests/test_dine_in_paid_deducts_stock.py`). It only bites a tenant that has locations
configured AND settles dine-in orders after serving; Martin's tenant has no dine-in.
