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

/** Required on all peri peri items. The board prints "MILD OR HOT". Free. */
const HEAT: ModifierGroup = {
  id: "heat",
  name: "Mild or Hot",
  min: 1,
  max: 1,
  options: [
    { id: "heat-mild", name: "Mild", priceDelta: 0 },
    { id: "heat-hot", name: "Hot", priceDelta: 0 },
  ],
};

/** The board's "MAKE IT MEAL £3.00 EXTRA" badge. */
const MEAL: ModifierGroup = {
  id: "meal",
  name: "Make it a meal",
  min: 0,
  max: 1,
  options: [{ id: "meal-yes", name: "Make it a meal", priceDelta: 300 }],
};

/** Dips priced as per the DIPS TUBS (2oz) section. */
const DIPS: ModifierGroup = {
  id: "dips",
  name: "Add a dip (2oz tub)",
  min: 0,
  max: 6,
  options: [
    { id: "dip-ketchup", name: "Ketchup", priceDelta: 79 },
    { id: "dip-mayo", name: "Mayo", priceDelta: 79 },
    { id: "dip-garlic-mayo", name: "Garlic Mayo", priceDelta: 99 },
    { id: "dip-bbq", name: "BBQ", priceDelta: 99 },
    { id: "dip-burger", name: "Burger Sauce", priceDelta: 99 },
    { id: "dip-chilli", name: "Chilli Sauce", priceDelta: 99 },
    { id: "dip-peri", name: "Peri Peri Sauce", priceDelta: 99 },
    { id: "dip-salsa", name: "Salsa Sauce", priceDelta: 99 },
    { id: "dip-algerian", name: "Algerian Sauce", priceDelta: 99 },
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

export const MENU_ITEMS: MenuItem[] = [
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
    modifierGroups: [HEAT, MEAL, DIPS],
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
    modifierGroups: [HEAT, MEAL, DIPS],
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
    modifierGroups: [MEAL, DIPS],
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
    modifierGroups: [MEAL, DIPS],
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
    modifierGroups: [MEAL, DIPS],
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
    modifierGroups: [MEAL, DIPS],
  },

  // --- Burgers -------------------------------------------------------------
  flat("b-chicken-fillet", "burgers", "Chicken Fillet", 699, [MEAL, DIPS],
    "Fried chicken fillet in a seeded bun with crisp lettuce, red onion and creamy mayonnaise."),
  flat("b-double-chicken", "burgers", "Double Chicken", 899, [MEAL, DIPS],
    "Double fried chicken fillet in a seeded bun with crisp lettuce, red onion and creamy mayonnaise."),
  flat("b-fillet-tower", "burgers", "Chick Shack Fillet Tower", 799, [MEAL, DIPS],
    "Fried chicken fillet and hashbrown in a seeded bun with crisp lettuce, red onion and creamy mayonnaise."),
  flat("b-peri", "burgers", "Peri Peri", 799, [HEAT, MEAL, DIPS],
    "Grilled peri chicken fillet, seeded bun, mayonnaise, lettuce, red onion."),
  flat("b-double-peri", "burgers", "Double Peri Peri", 1099, [HEAT, MEAL, DIPS],
    "Grilled double peri chicken fillet, seeded bun, mayonnaise, lettuce and red onion."),
  flat("b-quarter-cheese", "burgers", "¼ Cheese Burger", 599, [MEAL, DIPS],
    "Seeded bun, beef patty, burger sauce, lettuce, cheese, red onion & tomato.",
    "burger-beef"),
  flat("b-half-cheese", "burgers", "½ Cheese Burger", 799, [MEAL, DIPS],
    "Seeded bun, beef patty, burger sauce, lettuce, cheese, red onion & tomato.",
    "burger-beef"),
  // null, not undefined: inheriting the Burgers image would show a fried
  // chicken burger to someone ordering veggie or fish.
  flat("b-veggie", "burgers", "Veggie Burger", 599, [MEAL, DIPS],
    "Seeded bun with veggie patty, mayo, lettuce, red onion & cheese.", null),
  flat("b-fish", "burgers", "Fish Burger", 599, [MEAL, DIPS],
    "Seeded bun with fish patty, mayo, lettuce, red onion & cheese.", null),
  flat("b-big-shack", "burgers", "The Big Shack", 1099, [MEAL, DIPS],
    "Seeded bun, mayo, Algerian sauce, lettuce, cheese, ¼ beef patty, fried chicken fillet, hashbrown, tomato & red onion.",
    "burger-beef"),

  // --- Wraps ---------------------------------------------------------------
  flat("w-chicken-fillet", "wraps", "Chicken Fillet Wrap", 699, [MEAL, DIPS],
    "Tortilla wrap, fried chicken fillet, red onion, lettuce and salsa sauce."),
  flat("w-double-chicken", "wraps", "Double Chicken Fillet Wrap", 899, [MEAL, DIPS],
    "Double tortilla wrap, fried chicken fillet, red onion, lettuce and salsa sauce."),
  flat("w-peri", "wraps", "Peri Peri Wrap", 799, [HEAT, MEAL, DIPS],
    "Tortilla wrap, peri fillet, lettuce, mayonnaise, red onion and salsa sauce."),
  flat("w-double-peri", "wraps", "Double Peri Peri Wrap", 1099, [HEAT, MEAL, DIPS],
    "Double tortilla wrap, peri fillet, lettuce, mayonnaise, red onion and salsa sauce."),
  flat("w-veggie", "wraps", "Veggie Wrap", 599, [MEAL, DIPS],
    "Tortilla wrap with veggie patty, red onion, lettuce & salsa sauce.", null),
  flat("w-hot-chick", "wraps", "The Hot Chick", 699, [MEAL, DIPS],
    "Tortilla wrap, fried chicken fillet, lettuce and chilli sauce."),

  // --- Sides ---------------------------------------------------------------
  flat("s-chips-reg", "sides", "Regular Chips", 349),
  flat("s-chips-large", "sides", "Large Chips", 399),
  flat("s-peri-chips", "sides", "Peri Chips", 429),
  flat("s-onion-rings", "sides", "Onion Rings (12)", 599),
  flat("s-wedges-plain", "sides", "Plain Wedges", 429),
  flat("s-wedges-peri", "sides", "Peri Wedges", 479),
  flat("s-chilli-cheese-bites", "sides", "Chilli Cheese Bites (8)", 499),
  flat("s-corn-cob", "sides", "Corn Cob", 299),
  flat("s-beans", "sides", "Beans (8oz)", 249),
  flat("s-gravy", "sides", "Gravy (8oz)", 249),
  flat("s-coleslaw", "sides", "Coleslaw (8oz)", 249),
  flat("s-spicy-rice", "sides", "Spicy Rice", 399),
  flat("s-hash-brown", "sides", "Hash Brown", 299),
  flat("s-salad-box", "sides", "Salad Box", 299),

  // --- Kids ----------------------------------------------------------------
  {
    id: "k-popcorn",
    categoryId: "kids",
    name: "Popcorn Chicken",
    variants: [
      { id: "kp-reg", name: "Regular", price: 399 },
      { id: "kp-lrg", name: "Large", price: 499 },
    ],
    modifierGroups: [MEAL, DIPS],
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
    modifierGroups: [MEAL, DIPS],
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
    modifierGroups: [MEAL, DIPS],
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
  flat("dr-pepsi", "drinks", "Pepsi", 179),
  flat("dr-pepsi-max", "drinks", "Pepsi Max", 179),
  flat("dr-fanta-orange", "drinks", "Fanta Orange", 179),
  flat("dr-7up", "drinks", "7up", 179),
  // Fanta Pineapple Grapefruit removed and these two added on Imran's
  // instruction, 2026-07-27 — they are on neither the printed board nor
  // chick-shack.com.
  flat("dr-rubicon-passion", "drinks", "Rubicon Passionfruit", 179),
  flat("dr-levi-roots", "drinks", "Levi Roots Caribbean Crush", 179),
  flat("dr-irn-bru", "drinks", "Irn Bru", 179),
  flat("dr-irn-bru-diet", "drinks", "Diet Irn Bru", 179),
  flat("dr-water", "drinks", "Water", 149),
  {
    id: "dr-fruit-shoot",
    categoryId: "drinks",
    name: "Fruit Shoot",
    variants: [
      { id: "fs-orange", name: "Orange", price: 149 },
      { id: "fs-blackcurrant", name: "Blackcurrant", price: 149 },
    ],
    modifierGroups: [],
  },
];

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
  // Orders are placed against POST /public/{tenant}/orders and appear on the
  // shop's tablet for accept/reject. Ordering additionally requires the menu to
  // have loaded from the API — see `canOrder` in store/menu.ts — so this flag
  // alone cannot produce an order the server would refuse.
  orderingEnabled: true,
  // ⚠️ Stays false until Stripe Checkout and its signature-verified webhook are
  // live. Orders are created unpaid and settled in the shop. Flipping this
  // without Stripe means telling a customer they have paid when they have not.
  cardPaymentEnabled: false,
  services: ["collection", "delivery"],
  collectionMinutes: 20,
  deliveryMinutes: 45,

  /**
   * Exactly as printed on the menu board, cheapest first. The board also notes:
   * "A service fee may be applied for long distance deliveries" — clarify with
   * Imran whether that is on top of these, or already included.
   */
  deliveryAreas: [
    { id: "garelochhead", name: "Garelochhead", fee: 300 },
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
 * Does this item offer the board's "MAKE IT MEAL £3.00 EXTRA" upgrade?
 *
 * Matches on `slug`, falling back to `id`, so it works for both menu sources:
 * in this file the id IS the slug, while a menu from the API has UUID ids and
 * carries the slug separately. Matching on `id` alone silently stopped finding
 * anything the moment the menu started coming from the database.
 */
export function hasMealUpgrade(item: MenuItem): boolean {
  return item.modifierGroups.some((group) => (group.slug ?? group.id) === "meal");
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
 * Which categories get the ticks.
 *
 * Salad and sauce only exist on the things you build: burgers, wraps and the
 * chicken plates. Offering "no lettuce" on a can of Irn Bru is noise, and noise
 * on an ordering screen costs conversions.
 *
 * ⚠️ The category list is **our** inference from his wording ("only with chicken
 * and a wrap"), not something he enumerated. Confirm it with him.
 */
const EXCLUDABLE_CATEGORIES = new Set([
  "burgers",
  "wraps",
  "peri-grilled",
  "fried-chicken",
]);

export function exclusionsFor(item: MenuItem): readonly string[] {
  return EXCLUDABLE_CATEGORIES.has(item.categoryId) ? EXCLUSIONS : [];
}
