# Imran — EposNow menu walkthrough (screen recording, 2026-07-29 03:15)

**Source:** `WhatsApp Video 2026-07-29 at 3.15.15 AM.mp4` — 3:25, 576×1024, filmed
handheld off his own EposNow till (`Imzy`, TILL 1) during closing, 28 Jul 23:10–23:13.
**Transcript:** `faster-whisper small`, CPU, en. Frames every 4s at native resolution.
Ordering-relevant frames archived in `../refs/eposnow-menu/`.

⚠️ **Whisper mis-hears consistently.** "Perry"/"Perry Perry" = **Peri / Peri Peri**.
"milder hop" and "mild or hot" = **Mild or Hot**. Read with that substitution.

This is the follow-up to his 03:08 WhatsApp line *"In the menu the make it a meal needs
modifiers. For each make it a meal item."* — he recorded the till to show exactly what he
meant. **It is a complete requirements spec, not a suggestion**, and it supersedes the
guesswork in `HANDOFF.md` §4. Tracked as **OI-45**.

---

## The single most important finding

**EposNow does not use conditional modifiers. Solo and Meal are SEPARATE PRODUCTS.**

The category tree is `HOME > PERI PERI > PERI PERI WINGS`, and that splits into two
sibling sub-categories:

- **PERI PERI WING MEALS**
- **PERI PERI WINGS SOLO**

Picking the *meal* product opens a modal that already carries the drink and chips groups.
Picking the *solo* product does not. There is no "only ask this if they ticked that",
because the question never arises.

> *"These are solo items without making it meal. So if you click on mozzarella sticks,
> comes up as just solo item, but when you click on a meal…"* — 02:24

**This kills the hard part of OI-45.** The open-items register weighed (i) a required
"Meal choice" group whose first option is "No meal" against (ii) a real conditional-group
schema change. **Neither is needed.** Mirroring his till needs **no schema change at all** —
our `ModifierGroup` already has `required` / `min_selections` / `max_selections`, and
groups are attached per item. This is also the model he already trains staff on.

---

## The modifier modal, exactly as configured

Groups render as **tabs** in one modal, with a `PREVIOUS` / `DONE` wizard, a `CLOSE`, and a
red validation line under the options. Groups attach **per product** — the Fish Burger Meal
modal has only two tabs because a fish burger has no heat choice.

### 1. `Peri-Peri Heat` — required, "Please choose 1"
| Option | Price |
|---|---|
| Hot Heat | £0.00 |
| Mild Heat | £0.00 |

### 2. `Adults Meal Deal Drink` — required, "Please choose 1", all £0.00
7UP · Fanta Orange · Levi Roots Caribbean Crush · Pepsi Max · Water ·
Diet Irn Bru · Irn Bru · Pepsi · Rubicon Passion Fruit

### 3. `Meal Deal Upgrade` — optional, "Please choose up to 1"
| Option | Price |
|---|---|
| Regular Chips | £0.00 *(what the meal includes)* |
| Upgrade to Large Fries | £0.79 |
| Upgrade to Peri Peri Fries | £0.99 |
| Upgrade to Large Peri Peri Fries | £1.19 |
| Upgrade to Wedges | £1.39 |
| Upgrade to Peri Peri Wedges | £1.59 |

### 4. Kids — a DIFFERENT drink group
> *"we only give the kids an option between Fruit Shoot Blackcurrant or Fruit Shoot Orange.
> There's no other option of any fizzy drinks or any like canned drinks."* — 02:46

Two options only. Kids meals still get the chips upgrade group: *"some kids here they want
to upgrade to Peri Peri."* Kids solo is **£3.99** and the meal adds **£3.00** (02:19–03:19).

### 5. Per-line notes — he asked for this explicitly
> *"They need to have this option, like a notes option whether if they don't want any like
> no onion or lettuce, no salsa, no Algerian sauce, no ketchup… They want just a plain,
> only with chicken and a wrap, no salad no sauce. And make our life a lot easier if that
> was to happen."* — 01:56

His till offers free text plus **"Popular Notes"** quick-picks: `No Onion`, `No Lettuce`,
`No Tomato`, `No Mayo`. He named a wider set: onion, lettuce, salsa, Algerian sauce,
ketchup. The till also has per-line **NOTE** and **DISCOUNT** buttons.

---

## He is asking the website to be BETTER than his till, in one place

> *"in burgers you go into a double Peri Peri burger, it should ask you if it's mild or hot.
> But obviously this configuration doesn't ask you but it would usually should ask you —
> so on the website I'm asking if you could add on if you want a mild or hot at no extra
> cost."* — 01:11

**His own EposNow does not prompt for heat on the double peri peri burger, and he considers
that a defect.** He wants ours to ask. So this is not "copy the till" — it is "copy the
till, and fix the bit that annoys him."

His 03:10 WhatsApp list of what needs the heat prompt: **peri burgers, peri wraps (both
single and double), peri wings, and peri tenders.**

Wraps are his reference implementation: *"like on the wraps it does work… I click on double
Peri wrap, it comes up as hot or mild… mild, 7UP, regular chips."* (01:43)

---

## Worked example he narrates end to end (00:00–01:03)

1. Peri Wings **solo**, 3 pieces → asks heat → Mild → added. Done.
2. Peri Wings **meal** → asks heat (Mild) → asks drink (7UP) → comes with Regular Chips,
   at the **+£3.00** make-it-a-meal cost → optional upgrade to Large Peri Peri Fries (£1.19).

> *"That's what it would come up as on the EposNow. But the website would need to be kind of
> configured so it's similar."* — 00:59

---

## Still unanswered — do not invent these

1. **The full item list per group.** We have the peri list from WhatsApp, but not which
   exact products are "meal" variants, nor the meal price for every category (wings meal
   showed ~£10.9x; kids £3.99 + £3.00).
2. **Is the £3.00 uplift uniform** across wings / burgers / wraps / tenders, or per item?
3. **Is Hot/Mild the whole heat scale?** The modal showed exactly two. His printed board
   may carry more (Medium / Extra Hot) — the recording does not settle it.
4. **Kids chips upgrade prices** — assumed same as adult; not shown.
5. Whether the exclusion notes should be **priced £0 modifiers** (so they print as ticket
   lines and are unambiguous) or **free text**. His till does both; ours should probably do
   the tick-list, because free text on a kitchen ticket is read by a human at speed.
