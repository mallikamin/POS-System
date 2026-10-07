import type { Category, ImageName, MenuItem, ShopConfig } from "../types";

/**
 * Ali Fish & Chips & Curry House, Garelochhead.
 *
 * Source for every fact in this file: the client's printed A3 menu dated
 * March 2025 (`_context/clients/ali-fish-chips-uk/refs/2025-03_ali-fish-chips-official-menu-A3.pdf`)
 * and the client README in the same folder. All prices are integer pence.
 *
 * ---------------------------------------------------------------------------
 * THE MENU ITSELF LIVES IN THE DATABASE, NOT HERE.
 * ---------------------------------------------------------------------------
 * The storefront fetches `GET /public/ali-fish-chips/menu` on load
 * (`store/menu.ts`). Unlike the Chick Shack copy this was forked from, there is
 * NO hardcoded fallback menu: Ali's menu is ~195 numbered items with sizes,
 * protein choices and set-meal picks, and a second hand-maintained copy of it
 * in the bundle would drift from the database on the first price change. If the
 * API cannot be reached the page says so and gives the shop's phone number
 * instead of showing a menu that cannot be ordered from.
 *
 * `CATEGORIES` and `MENU_ITEMS` are only the photo lookup used by
 * `menuAdapter.ts`, matched to the API by `name` (so names must match the
 * seeded category names). Every item in a section shows the section's photo
 * unless `MENU_ITEMS` gives it its own (or `image: null` to opt out). The
 * photos are placeholder stock; see `ImageName` in types.ts.
 */
const section = (id: ImageName, name: string, sort: number): Category => ({ id, name, sort, image: id });

export const CATEGORIES: Category[] = [
  section("chip-shop", "Traditional Chip Shop", 1),
  section("burgers", "American Burgers", 2),
  section("snacks", "Snacks", 3),
  section("starters", "Starters", 4),
  section("tandoori-starters", "Tandoori Starters", 5),
  section("sizzlers", "Tandoori Sizzlers", 6),
  section("vegetable", "Vegetable Dishes", 7),
  section("korma", "Korma Dishes", 8),
  section("biryani", "Biryani Dishes", 9),
  section("traditional", "Traditional Dishes", 10),
  section("chefs", "Chef's Specialities", 11),
  section("breads", "Indian Breads", 12),
  section("rice", "Rice", 13),
  section("sauces", "Sauces", 14),
  section("accompaniments", "Accompaniments", 15),
  section("kebabs", "Turkish Kebabs", 16),
  section("hoggies", "Hoggies", 17),
  section("wraps", "Wraps", 18),
  section("pizzas", "Fresh Italian Pizzas", 19),
  section("special-pizzas", "Italian Special Pizzas", 20),
  section("calzones", "Italian Calzones", 21),
  section("set-meals", "Set Meals", 22),
  section("boxes", "Boxes & Specials", 23),
  section("kids", "Kids Corner", 24),
  section("dips", "Dips", 25),
];
export const MENU_ITEMS: MenuItem[] = [];

// ---------------------------------------------------------------------------
// Shop configuration
// ---------------------------------------------------------------------------

export const SHOP: ShopConfig = {
  name: "Ali Fish & Chips & Curry House",
  tagline: "Fish & Chips, Curries, Pizzas & Kebabs",
  addressLines: ["281 Main Road", "Garelochhead"],
  postcode: "G84 0AH",
  phones: ["01436 811329"],
  currency: "GBP",
  // Printed: "OPEN 7 DAYS FROM 4.30PM - 11.00PM".
  openTime: "16:30",
  closeTime: "23:00",
  // TODO-confirm with the client: whether online pre-orders before opening
  // count as "for today's service". Set equal to opening time for now, so any
  // order placed before 16:30 is labelled a pre-order end to end.
  orderFromTime: "16:30",
  // TODO-confirm with the client: last online DELIVERY order. ASSUMED 22:30,
  // giving 30 minutes of runway before the 23:00 close. Not on the menu.
  deliveryCloseTime: "22:30",
  // TODO-confirm with the client: last online COLLECTION order. ASSUMED 22:45.
  // Not on the menu.
  collectionCloseTime: "22:45",
  // Delivery starts when the shop opens. Printed menu gives no separate time.
  deliveryOpenTime: "16:30",
  orderingEnabled: true,
  // Stripe Checkout redirect. The client's Stripe account ("Ali Fish and
  // Chips", acct_1UNbi33iesgNCG6G) was submitted for activation 2026-10-06;
  // Stripe's review outcome is unknown. If the backend cannot create a
  // checkout session the order still stands as an unpaid order, see
  // `Checkout.tsx`, so this cannot lose an order, only fail to take a card.
  cardPaymentEnabled: true,
  services: ["collection", "delivery"],
  // TODO-confirm with the client: typical collection and delivery times.
  // Copied from the Chick Shack defaults; the shop's own ETA on Accept wins.
  collectionMinutes: 20,
  deliveryMinutes: 45,
  // No service / platform fee for Ali. The printed menu has none and the
  // client has not asked for one. Server-side tenant config must agree.
  serviceFee: 0,

  /**
   * Exactly as printed under "DELIVERY CHARGES", spellings corrected (the
   * artwork has "Mambag, Cryinder & Rhana", "Potiancapl", "Rosneth",
   * "Helensbrough"). No Arrochar: Ali does not list it.
   *
   * The `id` values are the area CODES the server looks the fee up by
   * (`delivery_areas.code`). They deliberately match the codes used for Chick
   * Shack so one seeder shape fits both tenants; Ali's own rows must still be
   * seeded under the `ali-fish-chips` tenant with these fees, or every
   * delivery order is refused with "We do not deliver to that area."
   */
  deliveryAreas: [
    { id: "garelochhead", name: "Garelochhead", fee: 295 },
    { id: "greenfields", name: "Greenfields Camp", fee: 295 },
    { id: "southgate", name: "Southgate & Shanden", fee: 395 },
    { id: "mambeg", name: "Mambeg, Clynder & Rahane", fee: 395 },
    { id: "portincaple", name: "Portincaple", fee: 395 },
    { id: "rhu", name: "Rhu", fee: 450 },
    { id: "rosneath", name: "Rosneath", fee: 450 },
    { id: "caravan-park", name: "Caravan Park", fee: 595 },
    { id: "kilcreggan", name: "Kilcreggan & Cove", fee: 695 },
    { id: "helensburgh", name: "Helensburgh", fee: 995 },
  ],

  // TODO-confirm with the client: delivery minimum. NOT printed on the menu.
  // 0 = no minimum. The server enforces its own figure from tenant config.
  deliveryMinimum: 0,

  // The printed "Allergy Awareness" box, lightly cleaned up. The only change
  // of substance: online customers cannot "let staff know" in person, so it
  // points them at the phone.
  allergenNotice:
    "A few of our dishes may contain nuts or dairy products. If you have an allergy or dietary requirement, please call us on 01436 811329 before ordering and we will give you full details of the ingredients.",
};

// TODO-confirm with the client: the printed menu advertises "10% DISCOUNT ON
// ORDER OVER £20 FROM OUR OWN WEBSITE". Deliberately NOT implemented. Every
// price is recomputed server-side, so a discount shown here and not applied by
// the backend would make the checkout total disagree with what is charged. If
// he still wants it, it has to be built as a server-side pricing rule first.

export function categoryById(id: string): Category | undefined {
  return CATEGORIES.find((c) => c.id === id);
}

/**
 * Resolve which photo an item shows, or `null` for none.
 *
 * Precedence: the item's own `image` wins, including an explicit `null` opt-out;
 * only `undefined` falls through to the category.
 */
export function itemImage(item: MenuItem): ImageName | null {
  if (item.image !== undefined) return item.image;
  return categoryById(item.categoryId)?.image ?? null;
}

/** Cheapest variant, used for the "from £x.xx" label on rows. */
export function fromPrice(item: MenuItem): number {
  return Math.min(...item.variants.map((v) => v.price));
}

/**
 * Split the printed menu number off an item name.
 *
 * Ali's menu items are numbered ("95. Tikka Masala") and phone customers and
 * the kitchen both refer to dishes by number, so the number is kept in the
 * database name and shown in its own column here. Names without a leading
 * number (set meals, boxes, dips) return `number: null`.
 */
export function splitItemNumber(name: string): { number: string | null; title: string } {
  const match = /^\s*(\d{1,3})\.\s+(.+)$/.exec(name);
  if (!match) return { number: null, title: name };
  return { number: match[1] ?? null, title: match[2] ?? name };
}

/**
 * One-line opening hours and online last-order times, shown on the menu page
 * and at checkout. Built from SHOP so the two can never disagree.
 */
export function hoursSummary(): string {
  const collectionUntil = SHOP.collectionCloseTime ?? SHOP.closeTime;
  return (
    `Open 7 days, ${SHOP.openTime} to ${SHOP.closeTime}. ` +
    `Online orders: collection until ${collectionUntil}, ` +
    `delivery ${SHOP.deliveryOpenTime} to ${SHOP.deliveryCloseTime}.`
  );
}

export function areaById(id: string) {
  return SHOP.deliveryAreas.find((a) => a.id === id);
}

/**
 * "Leave it out" ticks. Free of charge; they travel on the line's `notes`
 * field and print in bold on the kitchen ticket.
 *
 * TODO-confirm with the client: which ticks he wants, and on which sections.
 * This starting set covers what a kebab, wrap or burger is built with on his
 * menu ("Served with salad or appropriate sauce", "with chips, Cheese, Sauce
 * and Salad wrapped in a chapati"). Customers can always use the free-text
 * note as well.
 */
export const EXCLUSIONS = ["No salad", "No onion", "No sauce", "No cheese"] as const;

/**
 * Which categories get the ticks. Matched by keyword in the category NAME,
 * because ids are database UUIDs and the exact category titles in Ali's
 * database are not settled yet ("Turkish Kebabs", "Hoggies", "Wraps",
 * "American Burgers" on the print).
 */
const EXCLUDABLE_CATEGORY_KEYWORDS = ["kebab", "hoggie", "wrap", "burger"];

export function exclusionsFor(categoryName: string): readonly string[] {
  const name = categoryName.toLowerCase();
  return EXCLUDABLE_CATEGORY_KEYWORDS.some((k) => name.includes(k)) ? EXCLUSIONS : [];
}
