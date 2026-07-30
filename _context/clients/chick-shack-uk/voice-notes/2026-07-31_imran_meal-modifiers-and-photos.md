# Imran — meal modifiers, allergen notice, photos (voice note + WhatsApp, 2026-07-31)

**Sources, all 2026-07-31:**
- `2026-07-31_imran_meal-modifiers-and-photos.ogg` (WhatsApp voice note, 01:45) — transcript in
  the sibling `.transcript.txt`
- Malik's own WhatsApp "Things to do" summary to Imran, screenshotted — `refs/2026-07-31_eposnow-meal-modifiers/malik-summary-whatsapp-1.png`
- Imran's printed-board photo, sent with *"Can you put an allergy message on the website such
  as this"* — `refs/2026-07-31_eposnow-meal-modifiers/imran-allergen-board-photo.png`
- 5 fresh photos of the real EposNow till (Adults/Kids Meal Deal Drink, Meal Deal Upgrade ×2,
  Peri-Peri Heat) — same `refs/` folder, `*-meal-deal-*.png` / `peri-peri-heat.png`

**Purpose of this file:** a single checklist to cross-check at UAT. Every ask below is marked
against the actual code, with file:line evidence — not assumed.

---

## The six things Malik listed back to Imran, checked one by one

**i) "Make it a meal" needs modifiers — drink, regular/upgraded chips.**
🔴 **Confirmed still not built.** This is OI-45(b), already fully specified from the
2026-07-29 walkthrough and re-confirmed today by five fresh till photos — the drink list,
upgrade list and prices are byte-identical across both sessions. **This is the one real build
below.**

**ii) Notification alert for orders received.**
✅ **Already built.** `chime()` — WebAudio oscillator beep — fires on every new pending order
in the poll loop. `frontend/src/pages/online-orders/OnlineOrdersPage.tsx:141-185`. Imran has
never opened the real tablet page yet (OI-36), so he has never heard it. Nothing to build;
tell him to open `/online-orders` and place a real test order to hear it.

**iii) Allergy notice / comments box (Malik already flagged this exists).**
✅ **Both already built, end to end.**
- Free-text "Notes for the kitchen" box at checkout — `Checkout.tsx:333-338`
- Allergen line shown at checkout — `Checkout.tsx:423`, text **already word-for-word
  identical** to the photo he just sent: *"Please inform a member of staff of any allergies
  or dietary requirements before placing your order. While we take care, we cannot guarantee
  the absence of allergens due to shared preparation areas."* (`storefront/src/data/menu.ts:427-428`)
- Notes render on the tablet card (`OnlineOrdersPage.tsx:485-488`) and print on the physical
  ticket (`print_service.py:175-183`)
- **Proven live**: Malik's own screenshot shows a real customer already used this box —
  "no salsa" on 2 double chicken fillet wraps.

⚠️ **The real gap here is presentation, not content.** His board shows the allergen text
inside a boxed, high-contrast "Allergen Notice!" callout with a green "ALLERGY AWARENESS"
banner graphic. The website currently shows the same words as a plain inline sentence
("**Allergens.** ..."). Worth a small visual upgrade (bordered/tinted callout box) so it
reads with the same weight it has on his printed board — flagged in the build plan below.

**iv) Remove-selections: no lettuce, no tomato, no salsa, no Algerian sauce, no mayo.**
✅ **Already built**, verbatim. `EXCLUSIONS` tick-list in `storefront/src/data/menu.ts:491-500`
includes all five plus three more (No onion, No salad, No ketchup); offered on burgers, wraps,
peri-grilled and fried-chicken categories (`menu.ts:512-521`) — free, travel on `notes`, bold
on the kitchen ticket. Nothing to build.

**v) Wraps/Burgers clearly mentioned — add "Burger" to items like "Chicken Fillet".**
🟡 **Genuinely new, trivial.** Wraps already all say "Wrap" in the name. Burgers category
items **missing** an explicit "Burger" suffix, per `menu.ts:249-273`:
- Chicken Fillet → Chicken Fillet Burger
- Double Chicken → Double Chicken Burger
- Peri Peri → Peri Peri Burger
- Double Peri Peri → Double Peri Peri Burger
- (optional, already unambiguous) Chick Shack Fillet Tower, The Big Shack

**vi) Pictures from https://www.chunky-chicken.uk/**
🟡 **Genuinely new.** Malik has confirmed the go-ahead 2026-07-31 ("they have used generic
photos too, so just put the pictures its fine") after the copyright concern was raised —
logged as a settled decision, not re-argued further. Current images are self-hosted stock
WebP with a documented swap-in path (`types.ts:26-40`, one basename per item).

---

## Also from today's photos: exact Peri-Peri Heat wording

Current build already has a required Hot/Mild group on **every** peri-named item across
burgers, wraps, wings and tenders (`peri-half`, `peri-full`, `peri-breast-2/4`, `peri-wings`,
`peri-tenders`, `b-peri`, `b-double-peri`, `w-peri`, `w-double-peri` — `menu.ts:130-283`) —
**coverage already matches Imran's "for all peri items: burgers, wraps, grilled section,
wings and tenders" exactly.** Only the wording differs from his till: ours is `"Mild or Hot"`
/ `Mild`, `Hot` (`menu.ts:30-39`); his EposNow modal is titled **"Peri-Peri Heat"** with
**"Hot Heat"** listed before **"Mild Heat"**. Cosmetic rename only, no schema change — will
match his exact wording and order while doing the meal-modifier reseed anyway.

---

## The one real build: OI-45(b), meal → separate product

**Settled model (his own screen recording, 2026-07-29, not being re-argued):** EposNow makes
Solo and Meal **separate products** in sibling sub-categories — picking the meal product
opens a modal with the drink + upgrade groups already attached; picking solo does not. No
conditional-modifier logic, no schema change.

**What this means concretely:** every item that currently carries the flat `MEAL` tick
(+£3, one option) gets a **new sibling menu item** — `"<Name> Meal"`, priced at solo + £3 —
carrying the real modifier groups instead. The old flat tick is retired from these items.
**25 items are affected** (`menu.ts` grep for `MEAL`):

| Category | Items with the flat MEAL tick today | Drink group |
|---|---|---|
| Peri Grilled | Peri Peri Wings, Peri Tenders | Adults |
| Fried Chicken | Fried Chicken, Combo Fried Chicken w/2 Wings, Spicy Fried Wings, Fried Tenders | Adults |
| Burgers | Chicken Fillet, Double Chicken, Fillet Tower, Peri Peri, Double Peri Peri, ¼ Cheese, ½ Cheese, Veggie, Fish, The Big Shack | Adults |
| Wraps | Chicken Fillet Wrap, Double Chicken Fillet Wrap, Peri Peri Wrap, Double Peri Peri Wrap, Veggie Wrap, The Hot Chick | Adults |
| Kids | Popcorn Chicken, Nuggets, Mozzarella Sticks | **Kids** (2 Fruit Shoot flavours only) |

**New shared modifier groups needed** (all verified against fresh till photos, 2026-07-31):
- `Adults Meal Deal Drink` — required, choose 1, £0 each: 7UP, Fanta Orange, Levi Roots
  Caribbean Crush, Pepsi Max, Water, Diet Irn Bru, Irn Bru, Pepsi, Rubicon Passion Fruit
- `Kids Meal Deal Drink` — required, choose 1, £0 each: Fruit Shoot Blackcurrant, Fruit Shoot
  Orange **only** — confirmed twice now, no other drinks
- `Meal Deal Upgrade` — optional, up to 1: Regular Chips (£0, included), Large Fries (£0.79),
  Peri Peri Fries (£0.99), Large Peri Peri Fries (£1.19), Wedges (£1.39), Peri Peri Wedges
  (£1.59) — **identical for adults and kids**, confirmed by the kids-till photo

Peri-relevant meal items (Peri Peri Wings/Tenders/burger/wrap variants) also carry the
renamed `Peri-Peri Heat` group on the new Meal sibling, same as their Solo counterpart.

**Cost of this**: ~25 new menu items, `storefront/scripts/export-menu.ts` re-run,
`data/chick_shack_menu.json` regenerated, `seed_chick_shack.py` re-run (additive/idempotent,
**`pg_dump` first per `memory/data-integrity.md`, no exceptions** — this is live production
data with real orders on it right now). Category pages roughly double in card count for
Burgers/Wraps/Fried Chicken/Kids/Peri Grilled — needs an actual mobile + desktop check in
browser once built, not just a `tsc` pass, per the standing UI-change rule.

---

## Open items this raises (logged, not yet in `_state/open-items.md` until confirmed)

- **New:** item renames (v) — cheap, doing alongside the reseed.
- **New:** photo sourcing from chunky-chicken.uk (vi) — cheap in principle, needs the actual
  fetch + mapping + self-hosting as WebP done carefully; go-ahead confirmed by Malik.
- **New, small:** allergen notice presentation (boxed callout) to match the weight of his
  printed board, not just the wording (already correct).
- **Reconfirmed, ready to build:** OI-45(a) heat rename + OI-45(b) meal-as-separate-product.
  No longer "parked pending QC" — today's photos are that QC pass.
