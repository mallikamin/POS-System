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
  | "burger-double"
  | "burger-big-shack"
  | "wraps"
  | "wrap-hot-chick"
  | "peri-tenders"
  | "sides-chips"
  | "kids-popcorn"
  | "kids-nuggets"
  | "boneless-breast"
  | "peri-burger"
  | "chicken-fillet-burger"
  | "fish-burger"
  | "veggie-burger"
  | "veggie-wrap"
  | "chicken-wrap"
  | "peri-wrap"
  | "onion-rings"
  | "peri-wedges"
  | "corn-cob"
  | "mozzarella-sticks"
  | "hash-brown"
  | "irn-bru"
  | "irn-bru-diet"
  | "rubicon-passion"
  | "levi-roots"
  | "water"
  | "chilli-cheese-bites"
  | "pepsi"
  | "pepsi-max"
  | "fanta-orange"
  | "7up"
  | "gravy"
  | "coleslaw"
  | "spicy-rice"
  | "beans"
  | "salad-box"
  | "fruit-shoot";

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
  /**
   * "Leave it out" ticks — "No onion", "No Algerian sauce".
   *
   * Free of charge and invisible to pricing. They travel to the server on the
   * line's `notes` field and print in bold on the kitchen ticket. Part of the
   * line's identity: a plain wrap and a no-onion wrap are two different things
   * to whoever is making them, so they must not merge into one line of two.
   */
  exclusions: string[];
  /**
   * Free-text instruction for this item — "extra crispy", "cut in half".
   *
   * Same treatment as `exclusions`: joins the line's `notes` field to the
   * server and prints bold on the kitchen ticket, and is part of the line's
   * identity so two units of the same item with different notes stay on
   * separate lines rather than silently merging.
   */
  note?: string;
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
  /**
   * Override for `ShopConfig.deliveryCloseTime`, 24h "HH:MM". Garelochhead
   * gets extra minutes over every other area (closest to the shop). Falls
   * back to the shop-wide delivery cut-off when unset.
   */
  closeTime?: string;
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
   * Earliest an order may be PLACED, 24h "HH:MM". Pre-orders are allowed from
   * here until `closeTime`; outside that window checkout is refused.
   *
   * Not the same as `openTime`: the client accepts pre-orders before service
   * (his own example is a 14:00 order for a 16:00 opening). What this stops is
   * a 3am order landing on a tablet nobody is watching.
   */
  orderFromTime: string;
  /**
   * Last time an online DELIVERY order is taken, 24h "HH:MM" — deliberately
   * earlier than `closeTime`, so there is runway before the shop actually
   * shuts. Collection is unaffected and stays open until `closeTime`.
   * Per-area override: `DeliveryArea.closeTime`.
   */
  deliveryCloseTime: string;
  /**
   * Earliest time an online DELIVERY order is taken, 24h "HH:MM" —
   * deliberately later than `openTime`/`orderFromTime`. Confirmed directly by
   * Imran (WhatsApp, 2026-08-03): collection starts at `openTime` (16:00) as
   * before, delivery starts later at 16:30. Collection is unaffected.
   */
  deliveryOpenTime: string;
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
  /**
   * Flat service fee in pence, added to every order regardless of service
   * type or payment method (Imran, voice note 2026-08-02 — offsets Stripe's
   * own processing fee). 0 = disabled. This is a client-side display value
   * only; the server computes and charges the authoritative figure from the
   * tenant's own config, same as every other amount on this page — see
   * `PublicOrderCreate`'s "browser never sends prices" rule.
   */
  serviceFee: Pence;
  /** Printed on the menu; must appear at checkout. */
  allergenNotice: string;
}
