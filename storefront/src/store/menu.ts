import { create } from "zustand";
import type { Category, MenuItem } from "../types";
import { CATEGORIES, MENU_ITEMS, SHOP } from "../data/menu";
import { fetchMenu } from "../lib/api";
import { adaptMenu } from "../lib/menuAdapter";

/**
 * Where the menu on screen came from. This is not a diagnostic — it decides
 * whether an order can be placed at all.
 *
 *   loading   first fetch in flight
 *   api       live rows from the POS. Ids are UUIDs, so orders are placeable
 *   fallback  the hardcoded menu in `data/menu.ts`. Ids are slugs like
 *             "peri-half", which `POST /public/{tenant}/orders` rejects with a
 *             422 because it validates UUIDs
 *
 * The fallback exists because the printed menus already advertise this domain,
 * so a readable menu beats an error page if the API is unreachable. But
 * ordering MUST be off in that state: a checkout that cannot succeed is worse
 * than one that openly says "ring us".
 */
export type MenuSource = "loading" | "api" | "fallback";

interface MenuState {
  source: MenuSource;
  categories: Category[];
  items: MenuItem[];
  currency: string;
  /**
   * The shop has pressed its own "we're slammed" button (Imran, 2026-08-04).
   *
   * Distinct from every other reason ordering can be off: this one is
   * temporary, deliberate, and comes with a specific instruction to phone the
   * shop. It is re-read on every menu load, and the server refuses orders
   * while it is set regardless of what this copy of the app believes.
   */
  orderingPaused: boolean;
  pausedMessage: string | null;
  load: () => Promise<void>;
}

export const useMenu = create<MenuState>()((set) => ({
  // Render the hardcoded menu immediately rather than a spinner. The fetch
  // usually replaces it within a few hundred milliseconds, and a customer on a
  // slow phone sees food rather than a loading state.
  source: "loading",
  categories: CATEGORIES,
  items: MENU_ITEMS,
  currency: SHOP.currency,
  orderingPaused: false,
  pausedMessage: null,

  load: async () => {
    try {
      const response = await fetchMenu();
      const { categories, items } = adaptMenu(response.categories);

      // An empty menu is a misconfigured tenant, not a valid state to order
      // from. Keep the hardcoded list on screen and leave ordering off.
      if (items.length === 0) {
        set({ source: "fallback" });
        return;
      }

      set({
        source: "api",
        categories,
        items,
        currency: response.currency,
        orderingPaused: response.ordering_paused ?? false,
        pausedMessage: response.ordering_paused_message ?? null,
      });
    } catch {
      // `api.ts` has already turned this into something loggable. Here the only
      // decision that matters is that the ids on screen are not orderable.
      set({ source: "fallback" });
    }
  },
}));

/**
 * Whether a real order can be placed right now.
 *
 * Three independent gates, and all must hold:
 *   1. `SHOP.orderingEnabled` — the deliberate master switch.
 *   2. The menu came from the API — otherwise the basket holds slug ids that
 *      the order endpoint will reject.
 *   3. The shop has not paused ordering during a rush (Imran, 2026-08-04).
 *
 * `paused` is passed in rather than read from the store here so this stays a
 * pure function, like it already was for `source`.
 */
export function canOrder(source: MenuSource, paused = false): boolean {
  return SHOP.orderingEnabled && source === "api" && !paused;
}

/** The message to show when the shop has paused ordering, with a safe default. */
export const DEFAULT_PAUSED_MESSAGE =
  "We are facing high demand at the moment, please directly call the " +
  "restaurant 07719 566 889 to place your order. We appreciate your " +
  "patience in this regard.";
