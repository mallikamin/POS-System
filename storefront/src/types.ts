/**
 * Storefront domain types.
 *
 * MONEY IS ALWAYS INTEGER PENCE. £4.99 is 499. Never a float, never a string.
 * The POS backend uses the same convention (integer minor units), so amounts
 * cross the wire unchanged.
 */

/** Integer pence. */
export type Pence = number;

export type ServiceType = "collection" | "delivery";

export interface Category {
  id: string;
  name: string;
  /** Display order, ascending. */
  sort: number;
  /**
   * Image basename used as the fallback for every item in this category.
   * See `MenuItem.image` for what a basename is and why some are absent.
   */
  image?: ImageName;
}

/**
 * Basename of a self-hosted food photo, WITHOUT directory or extension.
 *
 * Each name resolves to two files, both committed under `public/img/`:
 *   /img/thumb/<name>.webp   240x180, ~10-20KB, lazy-loaded in the menu list
 *   /img/hero/<name>.webp    720x480, ~45-130KB, loaded only when a modal opens
 *
 * Self-hosted rather than hotlinked so the site has no third-party runtime
 * dependency and everything is served from the same Cloudflare edge.
 *
 * ⚠️ THESE ARE STOCK PHOTOS, NOT CHICK SHACK'S FOOD. They are placeholders
 * chosen to depict the right dish, pending real photography from the client.
 * Swapping one in later is a one-line change: drop the new files in and keep
 * the same basename. Do not add a name here without looking at the image.
 */
export type ImageName =
  | "peri-grilled"
  | "peri-wings"
  | "fried-chicken"
  | "fried-tenders"
  | "wings-spicy"
  | "burger-chicken"
  | "burger-beef"
  | "wraps"
  | "sides-chips";

export const imageThumb = (n: ImageName) => `/img/thumb/${n}.webp`;
export const imageHero = (n: ImageName) => `/img/hero/${n}.webp`;

/**
 * A purchasable size/base of an item.
 *
 * IMPORTANT: `price` is the ABSOLUTE price of that variant, not an increment.
 * Chick Shack's menu prices sizes outright — Fried Chicken is £4.99 for 2pc and
 * £7.99 for 4pc, which is not £4.99 + something. Treating these as additive
 * would produce wrong totals.
 */
export interface Variant {
  id: string;
  /** e.g. "2pc", "Half — Rice", "Reg". Empty string for single-price items. */
  name: string;
  price: Pence;
}

/**
 * A variant id that means "this item has only one price, so there is nothing to
 * choose". Used when the menu comes from the API: the POS has no variant
 * concept, so a real variant's id is the UUID of a modifier in that item's
 * required "Choice" group, and an item without such a group gets this instead.
 *
 * It must never be sent to the server as a modifier id — see `orderLinesOf`.
 */
export const NO_VARIANT = "";

/** A choice within a modifier group. Price here IS an increment on the line. */
export interface ModifierOption {
  id: string;
  name: string;
  /** Added to the line price. 0 for free choices like Mild/Hot. */
  priceDelta: Pence;
}

export interface ModifierGroup {
  id: string;
  name: string;
  /** Minimum selections. >0 makes the group required. */
  min: number;
  /** Maximum selections. 1 = radio, >1 = checkboxes. */
  max: number;
  options: ModifierOption[];
  /**
   * Stable slug identifying a well-known group across both menu sources.
   *
   * When the menu is hardcoded, `id` IS the slug ("meal", "heat", "dips"). When
   * it comes from the API, `id` is a UUID and the slug is recovered by name.
   * Presentation code that needs to recognise one specific group must match on
   * this rather than on `id` — see `hasMealUpgrade`.
   */
  slug?: string;
}

export interface MenuItem {
  id: string;
  categoryId: string;
  name: string;
  description?: string;
  /** Always at least one. Single unnamed variant for flat-priced items. */
  variants: Variant[];
  modifierGroups: ModifierGroup[];
  /**
   * Per-item photo. Three distinct states, and the difference matters:
   *
   *   undefined  -> inherit the category image
   *   ImageName  -> use this photo instead of the category's
   *   null       -> deliberately NO photo; render the branded fallback tile
   *
   * `null` exists so an item can opt OUT of an otherwise-correct category
   * image. The Fish and Veggie burgers are the reason: inheriting the Burgers
   * category photo would show a fried chicken burger to someone ordering fish,
   * which is worse than showing no picture at all.
   */
  image?: ImageName | null;
}

/** One configured line in the basket. */
export interface CartLine {
  /** Stable key derived from item + variant + chosen modifiers. */
  key: string;
  itemId: string;
  itemName: string;
  variantId: string;
  variantName: string;
  /** Chosen modifier options, flattened for display and pricing. */
  modifiers: ModifierOption[];
  quantity: number;
  /** Variant price + sum of modifier deltas. Per single unit. */
  unitPrice: Pence;
}

/**
 * A delivery destination as the shop actually prices it: by settlement name,
 * not by postcode.
 *
 * Their printed menu lists Garelochhead £3.00 … Arrochar £15.00. Nearly all of
 * these sit inside the SAME G84 outward code, so postcode-prefix matching would
 * quote £3 for a £15 run. The customer picks their area instead — which is also
 * how the shop and its drivers already think about it.
 */
export interface DeliveryArea {
  id: string;
  /** As printed on the menu, e.g. "Kilcreggan & Cove". */
  name: string;
  fee: Pence;
}

export interface ShopConfig {
  name: string;
  tagline: string;
  addressLines: string[];
  postcode: string;
  phones: string[];
  currency: string;
  /** Local opening hours, 24h "HH:MM". */
  openTime: string;
  closeTime: string;
  /**
   * Master switch for taking orders online.
   *
   * FALSE until the public order endpoint and Stripe webhook are live. While
   * false the site is a full menu and price list, and checkout ends by asking
   * the customer to phone — it never claims an order was placed. The printed
   * menus already advertise this domain, so a browsable menu beats a 404, but
   * a fake confirmation would be worse than either.
   */
  orderingEnabled: boolean;
  /**
   * Whether to offer paying by card on the website.
   *
   * Separate from `orderingEnabled` because the two arrived separately: orders
   * can be taken and settled in the shop long before Stripe exists. The order
   * endpoint creates every order `unpaid` and nothing behind it takes money, so
   * while this is false the checkout must not offer to charge a card.
   *
   * Flip only once Stripe Checkout AND its signature-verified webhook are live.
   */
  cardPaymentEnabled: boolean;
  /** Which service types the shop currently offers. */
  services: ServiceType[];
  collectionMinutes: number;
  deliveryMinutes: number;
  deliveryAreas: DeliveryArea[];
  /**
   * Shop-wide minimum basket for delivery, in pence. 0 = no minimum.
   * NOT STATED on their printed menu — confirm with Imran before go-live.
   */
  deliveryMinimum: Pence;
  /** Printed on the menu; must appear at checkout. */
  allergenNotice: string;
}
