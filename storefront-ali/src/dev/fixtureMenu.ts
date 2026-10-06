/**
 * DEV-ONLY local preview of Ali's real menu, without a backend.
 *
 * Loaded only by `store/menu.ts` under `import.meta.env.DEV` and only when the
 * URL has `?fixture`, via a dynamic import, so it is dropped from production
 * builds entirely (verify: `grep -c Babaji dist/assets/*.js` must print 0).
 *
 * It reads the seeder's own input, `backend/app/scripts/data/ali_fish_chips_menu.json`,
 * and applies the same transformation `seed_ali_fish_chips.py` does, so the
 * adapter sees the shape `GET /public/{tenant}/menu` will return:
 *   - item price = cheapest variant
 *   - more than one variant -> required pick-one group "<name> -- Choice",
 *     each option's price_adjustment = variant price - base
 *   - modifier groups shared by exact name across items; max 0 = unlimited
 *
 * Ids are synthetic, not UUIDs. The checkout button still shows, but a
 * submitted order is refused by the API with a 422, so nothing can be placed
 * from the fixture. It is for looking at the menu and the item modal only.
 */

import raw from "../../../backend/app/scripts/data/ali_fish_chips_menu.json";
import type { ApiCategory, ApiMenuResponse, ApiModifierGroup } from "../lib/api";

interface FixtureGroup {
  id: string;
  name: string;
  min?: number;
  max?: number;
  options: { id: string; name: string; priceDelta?: number }[];
}

interface FixtureItem {
  id: string;
  categoryId: string;
  name: string;
  description?: string;
  variants: { id: string; name: string; price: number }[];
  modifierGroups?: FixtureGroup[];
}

interface FixtureFile {
  categories: { id: string; name: string; sort: number }[];
  items: FixtureItem[];
}

export function fixtureMenu(): ApiMenuResponse {
  const data = raw as unknown as FixtureFile;
  const shared = new Map<string, ApiModifierGroup>();

  const categories: ApiCategory[] = data.categories.map((c) => ({
    id: `cat-${c.id}`,
    name: c.name,
    description: null,
    display_order: c.sort,
    items: [],
  }));
  const byId = new Map(categories.map((c) => [c.id, c]));

  for (const item of data.items) {
    const base = Math.min(...item.variants.map((v) => v.price));
    const groups: ApiModifierGroup[] = [];

    if (item.variants.length > 1) {
      groups.push({
        id: `vg-${item.id}`,
        name: `${item.name} -- Choice`,
        required: true,
        min_selections: 1,
        max_selections: 1,
        modifiers: item.variants.map((v) => ({
          id: `vg-${item.id}-${v.id}`,
          name: v.name,
          price_adjustment: v.price - base,
        })),
      });
    }

    for (const g of item.modifierGroups ?? []) {
      let group = shared.get(g.name);
      if (!group) {
        const min = g.min ?? 0;
        group = {
          id: `g-${g.id}`,
          name: g.name,
          required: min > 0,
          min_selections: min,
          max_selections: g.max ?? 0,
          modifiers: g.options.map((o) => ({
            id: `g-${g.id}-${o.id}`,
            name: o.name,
            price_adjustment: o.priceDelta ?? 0,
          })),
        };
        shared.set(g.name, group);
      }
      groups.push(group);
    }

    byId.get(`cat-${item.categoryId}`)?.items.push({
      id: `item-${item.id}`,
      name: item.name,
      description: item.description ?? null,
      price: base,
      image_url: null,
      modifier_groups: groups,
    });
  }

  return { currency: "GBP", categories, ordering_paused: false };
}
