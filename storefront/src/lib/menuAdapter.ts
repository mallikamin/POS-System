/**
 * Convert the POS public menu into the shapes this storefront renders.
 *
 * The two models do not line up, and this file is where that is reconciled.
 *
 * 1. **The POS has no variants.** A Chick Shack item like Fried Chicken is
 *    £4.99 for 2pc and £7.99 for 4pc, but `menu_items` holds one price. So the
 *    seeder (decision D-11) stores the CHEAPEST variant as the item price and
 *    turns the rest into a required single-select modifier group named
 *    "<item name> -- Choice", where each option's `price_adjustment` is the
 *    difference from that base. This file reverses that transformation, so the
 *    "Choose size" section keeps working and keeps showing absolute prices.
 *
 *    That group is then REMOVED from `modifierGroups`, or it would render twice
 *    — once as sizes and once as a modifier list.
 *
 * 2. **The POS has no food photography.** `image_url` is null on every seeded
 *    row. Photos, and the deliberate no-photo opt-outs, live in `data/menu.ts`
 *    and are matched back on by name. An item the local file has never heard of
 *    still renders, just with the branded fallback tile.
 *
 * Names are the join key throughout, because names are exactly what
 * `seed_chick_shack.py` matched on when it wrote the rows.
 */

import type {
  Category,
  ImageName,
  MenuItem,
  ModifierGroup,
  Variant,
} from "../types";
import { NO_VARIANT } from "../types";
import { CATEGORIES, MENU_ITEMS, itemImage } from "../data/menu";
import type { ApiCategory, ApiMenuItem, ApiModifierGroup } from "./api";

/**
 * Suffix the seeder appends to build a per-item variant group.
 *
 * ⚠️ Must stay in step with `VARIANT_GROUP_NAME` in
 * `backend/app/scripts/seed_chick_shack.py`, which builds the name as
 * `f"{item name} -- {VARIANT_GROUP_NAME}"`. Two ASCII hyphens, not a dash.
 */
const VARIANT_GROUP_SUFFIX = " -- Choice";

/** Match names tolerantly: casing and stray whitespace should not lose a photo. */
function nameKey(name: string): string {
  return name.trim().toLowerCase().replace(/\s+/g, " ");
}

/**
 * Photo for each locally-known item, with the item→category fallback already
 * resolved. `null` is a real value here: it means "deliberately no photo".
 */
const IMAGE_BY_ITEM_NAME: ReadonlyMap<string, ImageName | null> = new Map(
  MENU_ITEMS.map((item) => [nameKey(item.name), itemImage(item)] as const),
);

const CATEGORY_IMAGE_BY_NAME: ReadonlyMap<string, ImageName | undefined> = new Map(
  CATEGORIES.map((category) => [nameKey(category.name), category.image] as const),
);

/**
 * Slug for each shared modifier group, recovered by name.
 *
 * Derived from the items rather than from the group constants because those are
 * module-private in `data/menu.ts`. Every shared group is attached to at least
 * one item, so iterating items sees all of them.
 */
const GROUP_SLUG_BY_NAME: ReadonlyMap<string, string> = new Map(
  MENU_ITEMS.flatMap((item) =>
    item.modifierGroups.map((group) => [nameKey(group.name), group.id] as const),
  ),
);

function isVariantGroup(group: ApiModifierGroup, itemName: string): boolean {
  return nameKey(group.name) === nameKey(itemName + VARIANT_GROUP_SUFFIX);
}

function toModifierGroup(group: ApiModifierGroup): ModifierGroup {
  return {
    id: group.id,
    name: group.name,
    min: group.min_selections,
    // The API's 0 means unlimited; this UI treats `max` as a real ceiling and
    // uses it for `slice(-max)`, where 0 would be nonsense. Cap it at the
    // number of options, which is the true maximum anyway.
    max: group.max_selections === 0 ? group.modifiers.length : group.max_selections,
    options: group.modifiers.map((modifier) => ({
      id: modifier.id,
      name: modifier.name,
      priceDelta: modifier.price_adjustment,
    })),
    ...(GROUP_SLUG_BY_NAME.has(nameKey(group.name))
      ? { slug: GROUP_SLUG_BY_NAME.get(nameKey(group.name))! }
      : {}),
  };
}

/**
 * Rebuild the size list from the item's "Choice" group.
 *
 * Variant prices are ABSOLUTE in this UI and relative in the database, so each
 * option's price is `item.price + price_adjustment`. Returns a single unnamed
 * variant when the item has no Choice group, which is how flat-priced items
 * already work.
 */
function toVariants(item: ApiMenuItem, variantGroup: ApiModifierGroup | undefined): Variant[] {
  if (!variantGroup || variantGroup.modifiers.length === 0) {
    return [{ id: NO_VARIANT, name: "", price: item.price }];
  }
  return variantGroup.modifiers.map((modifier) => ({
    id: modifier.id,
    name: modifier.name,
    price: item.price + modifier.price_adjustment,
  }));
}

function toMenuItem(item: ApiMenuItem, categoryId: string): MenuItem | null {
  const variantGroup = item.modifier_groups.find((group) =>
    isVariantGroup(group, item.name),
  );

  // A required group with nothing available in it cannot be satisfied, so the
  // server would refuse the order with a 409 no matter what the customer picks.
  // Hiding the item is honest; offering it and failing at checkout is not.
  const unsatisfiable = item.modifier_groups.some(
    (group) => group.min_selections > 0 && group.modifiers.length < group.min_selections,
  );
  if (unsatisfiable) return null;

  return {
    id: item.id,
    categoryId,
    name: item.name,
    ...(item.description ? { description: item.description } : {}),
    variants: toVariants(item, variantGroup),
    modifierGroups: item.modifier_groups
      .filter((group) => group !== variantGroup)
      .map(toModifierGroup),
    // Always set, never left undefined: `itemImage` treats undefined as "fall
    // back to the category", and the category id here is a UUID the local
    // CATEGORIES list would not match. Resolving it now avoids that lookup.
    image: IMAGE_BY_ITEM_NAME.get(nameKey(item.name)) ?? null,
  };
}

export interface AdaptedMenu {
  categories: Category[];
  items: MenuItem[];
}

/** Flatten the API's nested menu into the flat lists this storefront renders. */
export function adaptMenu(apiCategories: ApiCategory[]): AdaptedMenu {
  const categories: Category[] = [];
  const items: MenuItem[] = [];

  for (const apiCategory of apiCategories) {
    const adapted = apiCategory.items
      .map((item) => toMenuItem(item, apiCategory.id))
      .filter((item): item is MenuItem => item !== null);

    // An empty category would render as a heading over nothing, and would still
    // take a slot on the sticky category rail.
    if (adapted.length === 0) continue;

    const image = CATEGORY_IMAGE_BY_NAME.get(nameKey(apiCategory.name));
    categories.push({
      id: apiCategory.id,
      name: apiCategory.name,
      sort: apiCategory.display_order,
      ...(image ? { image } : {}),
    });
    items.push(...adapted);
  }

  categories.sort((a, b) => a.sort - b.sort);
  return { categories, items };
}
