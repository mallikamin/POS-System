import type {
  Category,
  ImageName,
  MenuItem,
  ModifierGroup,
  ShopConfig,
} from "../types";

/**
 * Menu transcribed from the client's OFFICIAL PRINTED MENU BOARDS, photographed
 * on their Google Business listing and supplied by Malik 2026-07-27.
 * Print date on the artwork: 05/2026.
 *
 * This supersedes the earlier transcription from chick-shack.com, which Imran
 * confirmed by voice note was wrong and should not have been published.
 *
 * STILL TO CONFIRM WITH IMRAN before go-live:
 *   - the "few extra items" he said are served but are not on this board
 *   - whether any prices have moved since the 05/2026 print run
 *   - whether there is a minimum basket for delivery (not stated on the menu)
 *
 * All prices are integer pence.
 */

// ---------------------------------------------------------------------------
// Shared modifier groups
// ---------------------------------------------------------------------------

/**
 * Required on all peri peri items. Matches Imran's own EposNow till exactly —
 * name and option order verified against till photos, 2026-07-31
 * (`_context/clients/chick-shack-uk/refs/2026-07-31_eposnow-meal-modifiers/peri-peri-heat.png`).
 * IDs kept stable from the old "Mild or Hot" naming; only display text moved.
 */
const HEAT: ModifierGroup = {
  id: "heat",
  name: "Peri-Peri Heat",
  min: 1,
  max: 1,
  options: [
    { id: "heat-hot", name: "Hot Heat", priceDelta: 0 },
    { id: "heat-mild", name: "Mild Heat", priceDelta: 0 },
  ],
};

/**
 * Meal Deal drink choice for adults, and the upgrade-to-larger-sides group —
 * both shared across every adult Meal product. Verified against fresh
 * EposNow till photos, 2026-07-31, byte-identical to the 2026-07-29
 * walkthrough that first specified them.
 */
const ADULT_MEAL_DRINK: ModifierGroup = {
  id: "adult-meal-drink",
  name: "Adults Meal Deal Drink",
  min: 1,
  max: 1,
  options: [
    { id: "amd-7up", name: "7UP", priceDelta: 0 },
    { id: "amd-fanta-orange", name: "Fanta Orange", priceDelta: 0 },
    { id: "amd-levi-roots", name: "Levi Roots Caribbean Crush", priceDelta: 0 },
    { id: "amd-pepsi-max", name: "Pepsi Max", priceDelta: 0 },
    { id: "amd-water", name: "Water", priceDelta: 0 },
    { id: "amd-diet-irn-bru", name: "Diet Irn Bru", priceDelta: 0 },
    { id: "amd-irn-bru", name: "Irn Bru", priceDelta: 0 },
    { id: "amd-pepsi", name: "Pepsi", priceDelta: 0 },
    { id: "amd-rubicon-passion", name: "Rubicon Passion Fruit", priceDelta: 0 },
  ],
};

/**
 * Kids Meal Deal drink — deliberately ONLY these two. Imran was emphatic on
 * the 2026-07-29 walkthrough ("no other option of any fizzy drinks or canned
 * drinks") and the 2026-07-31 till photo confirms the same two options again.
 */
const KIDS_MEAL_DRINK: ModifierGroup = {
  id: "kids-meal-drink",
  name: "Kids Meal Deal Drink",
  min: 1,
  max: 1,
  options: [
    { id: "kmd-fruit-shoot-blackcurrant", name: "Fruit Shoot Blackcurrant", priceDelta: 0 },
    { id: "kmd-fruit-shoot-orange", name: "Fruit Shoot Orange", priceDelta: 0 },
  ],
};

/** Identical for adults and kids meals — confirmed by both till photo sets. */
const MEAL_UPGRADE: ModifierGroup = {
  id: "meal-upgrade",
  name: "Meal Deal Upgrade",
  min: 0,
  max: 1,
  options: [
    { id: "mu-reg-chips", name: "Regular Chips", priceDelta: 0 },
    { id: "mu-large-fries", name: "Upgrade to Large Fries", priceDelta: 79 },
    { id: "mu-peri-fries", name: "Upgrade to Peri Peri Fries", priceDelta: 99 },
    { id: "mu-large-peri-fries", name: "Upgrade to Large Peri Peri Fries", priceDelta: 119 },
    { id: "mu-wedges", name: "Upgrade to Wedges", priceDelta: 139 },
    { id: "mu-peri-wedges", name: "Upgrade to Peri Peri Wedges", priceDelta: 159 },
  ],
};

/**
 * Dips priced as per the DIPS TUBS (2oz) section.
 *
 * Option names carry "(Dip Tub)" — Imran (2026-07-31, via Malik): kitchen
 * staff need the word "dip tub" so a ticket line reads as a separate 2oz tub,
 * not an instruction to put it ON the burger/wrap. This group's own name
 * ("Add a dip (2oz tub)") never reaches the printed ticket — print_service.py
 * prints a bare modifier name with no group context — so the label has to
 * live on each option itself. See `rename_chick_shack_dip_modifiers_2026_07_31.py`
 * for the one-off DB rename this required (additive-only seeder, same class
 * of bug as the item-name renames — a plain reseed would have duplicated
 * every option rather than renaming it).
 */
const DIPS: ModifierGroup = {
  id: "dips",
  name: "Add a dip (2oz tub)",
  min: 0,
  max: 6,
  options: [
    { id: "dip-ketchup", name: "Ketchup (Dip Tub)", priceDelta: 79 },
    { id: "dip-mayo", name: "Mayo (Dip Tub)", priceDelta: 79 },
    { id: "dip-garlic-mayo", name: "Garlic Mayo (Dip Tub)", priceDelta: 99 },
    { id: "dip-bbq", name: "BBQ (Dip Tub)", priceDelta: 99 },
    { id: "dip-burger", name: "Burger Sauce (Dip Tub)", priceDelta: 99 },
    { id: "dip-chilli", name: "Chilli Sauce (Dip Tub)", priceDelta: 99 },
    { id: "dip-peri", name: "Peri Peri Sauce (Dip Tub)", priceDelta: 99 },
    { id: "dip-salsa", name: "Salsa Sauce (Dip Tub)", priceDelta: 99 },
    { id: "dip-algerian", name: "Algerian Sauce (Dip Tub)", priceDelta: 99 },
  ],
};

// ---------------------------------------------------------------------------
// Categories — ordered as the board reads
// ---------------------------------------------------------------------------

/**
 * Category images are the FALLBACK for every item in that category; an item
 * can override with its own via `MenuItem.image`.
 *
 * Kids, Dips and Drinks intentionally have none. A stock photo of a sauce tub
 * or a fizzy can adds nothing and risks misrepresenting the order, so those
 * render a branded fallback tile. See `ImageName` in types.ts.
 */
export const CATEGORIES: Category[] = [
  { id: "peri-grilled", name: "Peri Peri Grilled Chicken", sort: 1, image: "peri-grilled" },
  { id: "fried-chicken", name: "Fried Chicken", sort: 2, image: "fried-chicken" },
  { id: "burgers", name: "Burgers", sort: 3, image: "burger-chicken" },
  { id: "wraps", name: "Wraps", sort: 4, image: "wraps" },
  { id: "sides", name: "Sides", sort: 5, image: "sides-chips" },
  { id: "kids", name: "Kids", sort: 6 },
  { id: "dips", name: "Dips", sort: 7 },
  { id: "drinks", name: "Drinks", sort: 8 },
];

function flat(
  id: string,
  categoryId: string,
  name: string,
  price: number,
  modifierGroups: ModifierGroup[] = [],
  description?: string,
  /** Overrides the category image. Omit to inherit it, `null` to show none. */
  image?: ImageName | null,
): MenuItem {
  return {
    id,
    categoryId,
    name,
    description,
    variants: [{ id: `${id}-std`, name: "", price }],
    modifierGroups,
    image,
  };
}

// ---------------------------------------------------------------------------
// Items
// ---------------------------------------------------------------------------

const BASE_ITEMS: MenuItem[] = [
  // --- Peri Peri Grilled Chicken (all served with salad & coleslaw) --------
  {
    id: "peri-half",
    categoryId: "peri-grilled",
    name: "Half Chicken on the Bone",
    description:
      "Grilled chicken served with a zesty peri peri flavour. Served with salad & coleslaw.",
    variants: [
      { id: "ph-chips", name: "with Chips", price: 999 },
      { id: "ph-halfhalf", name: "Half & Half", price: 1049 },
      { id: "ph-rice", name: "with Rice", price: 1099 },
    ],
    modifierGroups: [HEAT, DIPS],
  },
  {
    id: "peri-full",
    categoryId: "peri-grilled",
    name: "Full Chicken on the Bone",
    description:
      "Grilled chicken served with a zesty peri peri flavour. Served with salad & coleslaw.",
    variants: [
      { id: "pf-chips", name: "with Chips", price: 1349 },
      { id: "pf-halfhalf", name: "Half & Half", price: 1399 },
      { id: "pf-rice", name: "with Rice", price: 1449 },
    ],
    modifierGroups: [HEAT, DIPS],
  },
  {
    id: "peri-breast-2",
    categoryId: "peri-grilled",
    name: "2 Boneless Breast",
    description:
      "2 tender boneless chicken pieces in a zesty peri peri sauce. Served with salad & coleslaw.",
    variants: [
      { id: "pb2-chips", name: "with Chips", price: 1149 },
      { id: "pb2-halfhalf", name: "Half & Half", price: 1199 },
      { id: "pb2-rice", name: "with Rice", price: 1249 },
    ],
    modifierGroups: [HEAT, DIPS],
    image: "boneless-breast",
  },
  {
    id: "peri-breast-4",
    categoryId: "peri-grilled",
    name: "4 Boneless Breast",
    description:
      "4 tender boneless chicken pieces in a zesty peri peri sauce. Served with salad & coleslaw.",
    variants: [
      { id: "pb4-chips", name: "with Chips", price: 1849 },
      { id: "pb4-halfhalf", name: "Half & Half", price: 1899 },
      { id: "pb4-rice", name: "with Rice", price: 1949 },
    ],
    modifierGroups: [HEAT, DIPS],
    image: "boneless-breast",
  },
  {
    id: "peri-wings",
    categoryId: "peri-grilled",
    name: "Peri Peri Wings",
    description: "Grilled wings, a zesty peri flavour.",
    variants: [
      { id: "pw-3", name: "3 pc", price: 699 },
      { id: "pw-5", name: "5 pc", price: 799 },
    ],
    modifierGroups: [HEAT, DIPS],
    image: "peri-wings",
  },
  {
    id: "peri-tenders",
    categoryId: "peri-grilled",
    name: "Peri Tenders",
    description: "Grilled tenders, a zesty peri peri flavour.",
    variants: [
      { id: "pt-3", name: "3 pc", price: 699 },
      { id: "pt-5", name: "5 pc", price: 799 },
      { id: "pt-7", name: "7 pc", price: 899 },
    ],
    modifierGroups: [HEAT, DIPS],
    image: "peri-tenders",
  },

  // --- Fried Chicken -------------------------------------------------------
  {
    id: "fried-chicken",
    categoryId: "fried-chicken",
    name: "Fried Chicken",
    variants: [
      { id: "fc-2", name: "2 pc", price: 499 },
      { id: "fc-3", name: "3 pc", price: 699 },
      { id: "fc-4", name: "4 pc", price: 799 },
    ],
    modifierGroups: [DIPS],
  },
  {
    id: "fried-combo",
    categoryId: "fried-chicken",
    name: "Combo Fried Chicken with 2 Wings",
    variants: [
      { id: "fcb-2", name: "2 pc", price: 699 },
      { id: "fcb-3", name: "3 pc", price: 999 },
      { id: "fcb-4", name: "4 pc", price: 1199 },
    ],
    modifierGroups: [DIPS],
  },
  {
    id: "spicy-wings",
    categoryId: "fried-chicken",
    name: "Spicy Fried Wings",
    variants: [
      { id: "sw-4", name: "4 pc", price: 499 },
      { id: "sw-6", name: "6 pc", price: 599 },
      { id: "sw-8", name: "8 pc", price: 699 },
      { id: "sw-10", name: "10 pc", price: 799 },
      { id: "sw-12", name: "12 pc", price: 899 },
      { id: "sw-16", name: "16 pc", price: 999 },
    ],
    modifierGroups: [DIPS],
    image: "wings-spicy",
  },
  {
    id: "fried-tenders",
    categoryId: "fried-chicken",
    name: "Fried Tenders",
    variants: [
      { id: "ft-4", name: "4 pc", price: 599 },
      { id: "ft-6", name: "6 pc", price: 799 },
      { id: "ft-8", name: "8 pc", price: 899 },
      { id: "ft-10", name: "10 pc", price: 999 },
    ],
    image: "fried-tenders",
    modifierGroups: [DIPS],
  },

  // --- Burgers -------------------------------------------------------------
  flat("b-chicken-fillet", "burgers", "Chicken Fillet Burger", 699, [DIPS],
    "Fried chicken fillet in a seeded bun with crisp lettuce, red onion and creamy mayonnaise.",
    "chicken-fillet-burger"),
  flat("b-double-chicken", "burgers", "Double Chicken Burger", 899, [DIPS],
    "Double fried chicken fillet in a seeded bun with crisp lettuce, red onion and creamy mayonnaise.",
    "burger-double"),
  flat("b-fillet-tower", "burgers", "Chick Shack Fillet Tower Burger", 799, [DIPS],
    "Fried chicken fillet and hashbrown in a seeded bun with crisp lettuce, red onion and creamy mayonnaise."),
  flat("b-peri", "burgers", "Peri Peri Burger", 799, [HEAT, DIPS],
    "Grilled peri chicken fillet, seeded bun, mayonnaise, lettuce, red onion.",
    "peri-burger"),
  flat("b-double-peri", "burgers", "Double Peri Peri Burger", 1099, [HEAT, DIPS],
    "Grilled double peri chicken fillet, seeded bun, mayonnaise, lettuce and red onion."),
  flat("b-quarter-cheese", "burgers", "¼ Cheese Burger", 599, [DIPS],
    "Seeded bun, beef patty, burger sauce, lettuce, cheese, red onion & tomato.",
    "burger-beef"),
  flat("b-half-cheese", "burgers", "½ Cheese Burger", 799, [DIPS],
    "Seeded bun, beef patty, burger sauce, lettuce, cheese, red onion & tomato.",
    "burger-beef"),
  flat("b-veggie", "burgers", "Veggie Burger", 599, [DIPS],
    "Seeded bun with veggie patty, mayo, lettuce, red onion & cheese.", "veggie-burger"),
  flat("b-fish", "burgers", "Fish Burger", 599, [DIPS],
    "Seeded bun with fish patty, mayo, lettuce, red onion & cheese.", "fish-burger"),
  flat("b-big-shack", "burgers", "The Big Shack Burger", 1099, [DIPS],
    "Seeded bun, mayo, Algerian sauce, lettuce, cheese, ¼ beef patty, fried chicken fillet, hashbrown, tomato & red onion.",
    "burger-big-shack"),

  // --- Wraps ---------------------------------------------------------------
  flat("w-chicken-fillet", "wraps", "Chicken Fillet Wrap", 699, [DIPS],
    "Tortilla wrap, fried chicken fillet, red onion, lettuce and salsa sauce.",
    "chicken-wrap"),
  flat("w-double-chicken", "wraps", "Double Chicken Fillet Wrap", 899, [DIPS],
    "Double tortilla wrap, fried chicken fillet, red onion, lettuce and salsa sauce."),
  flat("w-peri", "wraps", "Peri Peri Wrap", 799, [HEAT, DIPS],
    "Tortilla wrap, peri fillet, lettuce, mayonnaise, red onion and salsa sauce.",
    "peri-wrap"),
  flat("w-double-peri", "wraps", "Double Peri Peri Wrap", 1099, [HEAT, DIPS],
    "Double tortilla wrap, peri fillet, lettuce, mayonnaise, red onion and salsa sauce."),
  flat("w-veggie", "wraps", "Veggie Wrap", 599, [DIPS],
    "Tortilla wrap with veggie patty, red onion, lettuce & salsa sauce.", "veggie-wrap"),
  flat("w-hot-chick", "wraps", "The Hot Chick Wrap", 699, [DIPS],
    "Tortilla wrap, fried chicken fillet, lettuce and chilli sauce.",
    "wrap-hot-chick"),

  // --- Sides ---------------------------------------------------------------
  flat("s-chips-reg", "sides", "Regular Chips", 349),
  flat("s-chips-large", "sides", "Large Chips", 399),
  flat("s-peri-chips", "sides", "Peri Chips", 429),
  flat("s-onion-rings", "sides", "Onion Rings (12)", 599, [], undefined, "onion-rings"),
  flat("s-wedges-plain", "sides", "Plain Wedges", 429, [], undefined, "peri-wedges"),
  flat("s-wedges-peri", "sides", "Peri Wedges", 479, [], undefined, "peri-wedges"),
  flat("s-chilli-cheese-bites", "sides", "Chilli Cheese Bites (8)", 499, [], undefined, "chilli-cheese-bites"),
  flat("s-corn-cob", "sides", "Corn Cob", 299, [], undefined, "corn-cob"),
  flat("s-beans", "sides", "Beans (8oz)", 249, [], undefined, "beans"),
  flat("s-gravy", "sides", "Gravy (8oz)", 249, [], undefined, "gravy"),
  flat("s-coleslaw", "sides", "Coleslaw (8oz)", 249, [], undefined, "coleslaw"),
  flat("s-spicy-rice", "sides", "Spicy Rice", 399, [], undefined, "spicy-rice"),
  flat("s-hash-brown", "sides", "Hash Brown", 299, [], undefined, "hash-brown"),
  flat("s-salad-box", "sides", "Salad Box", 299, [], undefined, "salad-box"),

  // --- Kids ----------------------------------------------------------------
  {
    id: "k-popcorn",
    categoryId: "kids",
    name: "Popcorn Chicken",
    variants: [
      { id: "kp-reg", name: "Regular", price: 399 },
      { id: "kp-lrg", name: "Large", price: 499 },
    ],
    modifierGroups: [DIPS],
    image: "kids-popcorn",
  },
  {
    id: "k-nuggets",
    categoryId: "kids",
    name: "Nuggets",
    variants: [
      { id: "kn-4", name: "4 pc", price: 399 },
      { id: "kn-8", name: "8 pc", price: 799 },
      { id: "kn-12", name: "12 pc", price: 999 },
      { id: "kn-16", name: "16 pc", price: 1199 },
    ],
    modifierGroups: [DIPS],
    image: "kids-nuggets",
  },
  {
    id: "k-mozzarella",
    categoryId: "kids",
    name: "Mozzarella Sticks",
    variants: [
      { id: "km-3", name: "3 pc", price: 399 },
      { id: "km-6", name: "6 pc", price: 599 },
      { id: "km-9", name: "9 pc", price: 799 },
    ],
    modifierGroups: [DIPS],
    image: "mozzarella-sticks",
  },

  // --- Dips (as standalone tubs) -------------------------------------------
  flat("d-ketchup", "dips", "Ketchup", 79),
  flat("d-mayo", "dips", "Mayo", 79),
  flat("d-garlic-mayo", "dips", "Garlic Mayo", 99),
  flat("d-bbq", "dips", "BBQ", 99),
  flat("d-burger", "dips", "Burger Sauce", 99),
  flat("d-chilli", "dips", "Chilli Sauce", 99),
  flat("d-peri", "dips", "Peri Peri Sauce", 99),
  flat("d-salsa", "dips", "Salsa Sauce", 99),
  flat("d-algerian", "dips", "Algerian Sauce", 99),

  // --- Drinks --------------------------------------------------------------
  // Serving-size labels ("(Can)" / "(500ml)" / "(330ml)") added on Imran's
  // instruction, 2026-07-31. These are RENAMES on the database side — see
  // rename_chick_shack_drinks_2026_07_31.py, which must run on production
  // BEFORE the next reseed, same reasoning as the item-name and dip-modifier
  // renames earlier this session (seed_chick_shack.py matches by name; a
  // blind rename here would duplicate the row rather than rename it).
  flat("dr-pepsi", "drinks", "Pepsi (Can)", 179, [], undefined, "pepsi"),
  flat("dr-pepsi-max", "drinks", "Pepsi Max (Can)", 179, [], undefined, "pepsi-max"),
  flat("dr-fanta-orange", "drinks", "Fanta Orange (Can)", 179, [], undefined, "fanta-orange"),
  flat("dr-7up", "drinks", "7up (Can)", 179, [], undefined, "7up"),
  // Fanta Pineapple Grapefruit removed and these two added on Imran's
  // instruction, 2026-07-27 — they are on neither the printed board nor
  // chick-shack.com.
  flat("dr-rubicon-passion", "drinks", "Rubicon Passionfruit (Can)", 179, [], undefined, "rubicon-passion"),
  flat("dr-levi-roots", "drinks", "Levi Roots Caribbean Crush (Can)", 179, [], undefined, "levi-roots"),
  flat("dr-irn-bru", "drinks", "Irn Bru (Can)", 179, [], undefined, "irn-bru"),
  flat("dr-irn-bru-diet", "drinks", "Diet Irn Bru (Can)", 179, [], undefined, "irn-bru-diet"),
  flat("dr-water", "drinks", "Water (500ml)", 149, [], undefined, "water"),
  {
    id: "dr-fruit-shoot",
    categoryId: "drinks",
    name: "Fruit Shoot (330ml)",
    variants: [
      { id: "fs-orange", name: "Orange", price: 149 },
      { id: "fs-blackcurrant", name: "Blackcurrant", price: 149 },
    ],
    modifierGroups: [],
    image: "fruit-shoot",
  },
];

/**
 * OI-45(b) — "make it a meal" as a real Meal product, not a flat +£3 tick.
 *
 * Settled model, from Imran's own EposNow screen recording (2026-07-29) and
 * re-confirmed by till photos (2026-07-31): Solo and Meal are SEPARATE
 * PRODUCTS in his till, not one product with a conditional toggle. Picking
 * the Meal item is what asks for a drink and a chips upgrade; picking Solo
 * never does. So each meal-eligible item gets a sibling `"<Name> Meal"` item
 * instead of a tickbox — same variants, +£3 each, with the drink + upgrade
 * groups attached in place of nothing (solo carries neither).
 */
function withMeal(item: MenuItem, drinkGroup: ModifierGroup): MenuItem {
  // Order matters here, and it isn't "whatever the solo item already had,
  // then the meal groups tacked on": Dips is an optional garnish and reads as
  // an afterthought, so it goes last regardless of where it sat on the solo
  // item. Heat (required, when present) leads, then the meal's own required
  // drink choice, then the optional chips upgrade, then Dips.
  const dips = item.modifierGroups.filter((g) => g.id === "dips");
  const rest = item.modifierGroups.filter((g) => g.id !== "dips");
  return {
    ...item,
    id: `${item.id}-meal`,
    name: `${item.name} Meal`,
    variants: item.variants.map((v) => ({
      id: `${v.id}-meal`,
      name: v.name,
      price: v.price + 300,
    })),
    modifierGroups: [...rest, drinkGroup, MEAL_UPGRADE, ...dips],
  };
}

/** Every item the board's "MAKE IT MEAL £3.00 EXTRA" badge used to apply to. */
const ADULT_MEAL_ITEM_IDS = new Set([
  "peri-wings",
  "peri-tenders",
  "fried-chicken",
  "fried-combo",
  "spicy-wings",
  "fried-tenders",
  "b-chicken-fillet",
  "b-double-chicken",
  "b-fillet-tower",
  "b-peri",
  "b-double-peri",
  "b-quarter-cheese",
  "b-half-cheese",
  "b-veggie",
  "b-fish",
  "b-big-shack",
  "w-chicken-fillet",
  "w-double-chicken",
  "w-peri",
  "w-double-peri",
  "w-veggie",
  "w-hot-chick",
]);

/** Kids items get the 2-flavour Kids Meal Deal Drink, never the adult list. */
const KIDS_MEAL_ITEM_IDS = new Set(["k-popcorn", "k-nuggets", "k-mozzarella"]);

const MEAL_ITEMS: MenuItem[] = BASE_ITEMS.filter(
  (item) => ADULT_MEAL_ITEM_IDS.has(item.id) || KIDS_MEAL_ITEM_IDS.has(item.id),
).map((item) =>
  withMeal(item, KIDS_MEAL_ITEM_IDS.has(item.id) ? KIDS_MEAL_DRINK : ADULT_MEAL_DRINK),
);

/**
 * Meal siblings are interleaved right after their solo item, not appended in
 * one block at the end of everything. `display_order` in the database is set
 * from this array's index (`seed_chick_shack.py`'s `enumerate(items)`), so a
 * flat append put every meal item after every solo item in a category —
 * ten solo burgers, then ten meal burgers below all of them. A customer
 * looking at a solo item never saw a meal version was one card away, and
 * had no reason to keep scrolling.
 */
export const MENU_ITEMS: MenuItem[] = BASE_ITEMS.flatMap((item) => {
  const meal = MEAL_ITEMS.find((m) => m.id === `${item.id}-meal`);
  return meal ? [item, meal] : [item];
});

// ---------------------------------------------------------------------------
// Shop configuration
// ---------------------------------------------------------------------------

export const SHOP: ShopConfig = {
  name: "Chick Shack",
  tagline: "Fried Chicken · Peri Peri",
  addressLines: ["Main Street", "Garelochhead", "Helensburgh"],
  postcode: "G84 0AN",
  phones: ["01436 653 143", "07719 566 889"],
  currency: "GBP",
  openTime: "16:00",
  closeTime: "22:00",
  // Pre-orders open two hours before service, matching Imran's own worked
  // example (placed 14:00, accepted 15:30, opens 16:00). INFERRED — confirm.
  orderFromTime: "14:00",
  // Imran, voice note 2026-08-02, re-confirmed by text 2026-08-03: last online
  // DELIVERY orders at 21:30 for every area except Garelochhead (21:45, see
  // its DeliveryArea.closeTime override below) -- there needs to be runway
  // before the shop shuts at 22:00. Collection is unaffected, stays open to
  // closeTime as normal ("You can collect till 22:00").
  deliveryCloseTime: "21:30",
  // Imran, WhatsApp 2026-08-03: delivery's own earliest window is 16:30, not
  // the shop's general 16:00 opening -- confirmed distinct from collection
  // ("Collections 16:00") after being asked directly. Collection is
  // unaffected and still uses openTime/orderFromTime as before.
  deliveryOpenTime: "16:30",
  // Orders are placed against POST /public/{tenant}/orders and appear on the
  // shop's tablet for accept/reject. Ordering additionally requires the menu to
  // have loaded from the API — see `canOrder` in store/menu.ts — so this flag
  // alone cannot produce an order the server would refuse.
  orderingEnabled: true,
  // Stripe Checkout + its signature-verified webhook are live in production
  // (proven with a real captured transaction, order 260801-004, 2026-08-02).
  // Imran approved going fully live in writing the same day.
  cardPaymentEnabled: true,
  services: ["collection", "delivery"],
  collectionMinutes: 20,
  deliveryMinutes: 45,
  // Imran, voice note 2026-08-02: flat 70p on every order, collection and
  // delivery alike, to offset Stripe's own ~£0.72 processing fee. Distinct
  // from the menu board's own "service fee may apply for long distance
  // deliveries" note above `deliveryAreas` below, which is a separate,
  // still-unconfirmed, distance-based idea — do not conflate the two.
  serviceFee: 70,

  /**
   * Exactly as printed on the menu board, cheapest first. The board also notes:
   * "A service fee may be applied for long distance deliveries" — clarify with
   * Imran whether that is on top of these, or already included.
   */
  deliveryAreas: [
    { id: "garelochhead", name: "Garelochhead", fee: 300, closeTime: "21:45" },
    { id: "greenfields", name: "Greenfields Camp", fee: 300 },
    { id: "southgate", name: "Southgate & Shanden", fee: 400 },
    { id: "mambeg", name: "Mambeg, Clynder & Rahane", fee: 400 },
    { id: "portincaple", name: "Portincaple", fee: 400 },
    { id: "rhu", name: "Rhu", fee: 450 },
    { id: "rosneath", name: "Rosneath", fee: 450 },
    { id: "caravan-park", name: "Caravan Park", fee: 600 },
    { id: "kilcreggan", name: "Kilcreggan & Cove", fee: 700 },
    { id: "helensburgh", name: "Helensburgh", fee: 1000 },
    { id: "arrochar", name: "Arrochar", fee: 1500 },
  ],

  /** £5.00. Confirmed by Imran 2026-07-27; not printed on the board. */
  deliveryMinimum: 500,

  allergenNotice:
    "Please inform a member of staff of any allergies or dietary requirements before placing your order. While we take care, we cannot guarantee the absence of allergens due to shared preparation areas.",
};

export function categoryById(id: string): Category | undefined {
  return CATEGORIES.find((c) => c.id === id);
}

export function itemsInCategory(categoryId: string): MenuItem[] {
  return MENU_ITEMS.filter((i) => i.categoryId === categoryId);
}

/**
 * Resolve which photo an item shows, or `null` for the branded fallback tile.
 *
 * Precedence: the item's own `image` wins, including an explicit `null` opt-out;
 * only `undefined` falls through to the category. `?? null` at the end covers
 * categories that have no image at all (Kids, Dips, Drinks).
 */
export function itemImage(item: MenuItem): ImageName | null {
  if (item.image !== undefined) return item.image;
  return categoryById(item.categoryId)?.image ?? null;
}

/** Cheapest variant, used for the "from £x.xx" label on cards. */
export function fromPrice(item: MenuItem): number {
  return Math.min(...item.variants.map((v) => v.price));
}

/**
 * Is this the "Meal" sibling of another item (see `withMeal` above), rather
 * than the solo product? Drives the "Meal Deal" badge.
 *
 * Matches on NAME, not id — when the menu comes from the API the id is a
 * database UUID, not the local `"<id>-meal"` this file generates, and names
 * are what survive the round trip through `seed_chick_shack.py` and back
 * (see `menuAdapter.ts`'s own header comment: "Names are the join key
 * throughout").
 */
export function isMealItem(item: MenuItem): boolean {
  return item.name.endsWith(" Meal");
}

/**
 * The other half of a Solo/Meal pair, if the current menu has one — a Meal
 * item's Solo, or a Solo item's Meal. Same name-matching reasoning as
 * `isMealItem`. Powers the cross-link in `ItemModal` so a customer looking at
 * one product can see the other exists without hunting for it in the list.
 */
export function siblingOf(item: MenuItem, items: MenuItem[]): MenuItem | undefined {
  const wantName = isMealItem(item)
    ? item.name.slice(0, -" Meal".length)
    : `${item.name} Meal`;
  return items.find((i) => i.categoryId === item.categoryId && i.name === wantName);
}

export function areaById(id: string) {
  return SHOP.deliveryAreas.find((a) => a.id === id);
}

/**
 * "Leave it out" ticks, offered on anything that is built with salad and sauce.
 *
 * Imran asked for these directly, 2026-07-29: *"a notes option whether if they
 * don't want any like no onion or lettuce, no salsa, no Algerian sauce, no
 * ketchup… They want just a plain, only with chicken and a wrap… And make our
 * life a lot easier if that was to happen."*
 *
 * These are deliberately **not** modifier rows in the database. They carry no
 * price, they change nothing the server has to validate, and modelling them as
 * modifiers would mean a schema-shaped change and a production re-seed to
 * deliver a tick-box. They travel instead on the line's `notes` field, which
 * the API already accepts and which `print_service` already prints **in bold**
 * on the kitchen ticket — which is exactly where a "no onion" needs to shout.
 *
 * A closed tick-list rather than free text, on purpose: a kitchen ticket is
 * read by a person at speed in a hot room, and free text invites "no unions"
 * and worse.
 */
export const EXCLUSIONS = [
  "No onion",
  "No lettuce",
  "No tomato",
  "No salad",
  "No mayo",
  "No ketchup",
  "No salsa",
  "No Algerian sauce",
] as const;

/**
 * Which categories get the ticks, by NAME rather than id.
 *
 * Burgers and wraps only — confirmed directly by Imran (2026-07-31, via
 * Malik): "This section [is] applicable to burgers and wraps." Salad and
 * sauce are built INTO those two, ingredient by ingredient, so "leave it out"
 * maps onto something real. The grilled/fried chicken plates just come with
 * a side of "salad & coleslaw" — not the same removable-ingredient shape —
 * so offering the same ticks there was noise, not a genuine option.
 *
 * By name, not id: `categoryId` is the local slug ("burgers") in the hardcoded
 * fallback menu but a database UUID once the live menu loads from the API, and
 * this Set was never updated for that second case. Result: this section has
 * never actually appeared on the live site — caught in UAT, Malik saw no
 * "leave it out" section at all on the real chickshackg84.com. Names survive
 * both paths (see `menuAdapter.ts`'s "Names are the join key throughout").
 */
const EXCLUDABLE_CATEGORY_NAMES = new Set(["Burgers", "Wraps"]);

export function exclusionsFor(categoryName: string): readonly string[] {
  return EXCLUDABLE_CATEGORY_NAMES.has(categoryName) ? EXCLUSIONS : [];
}
