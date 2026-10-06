import { create } from "zustand";
import type { Category, MenuItem } from "../types";
import { CATEGORIES, MENU_ITEMS, SHOP } from "../data/menu";
import { ApiError, fetchMenu } from "../lib/api";
import { adaptMenu } from "../lib/menuAdapter";

/**
 * Where the menu on screen came from. This is not a diagnostic: it decides
 * whether an order can be placed at all.
 *
 *   loading   first fetch in flight
 *   api       live rows from the POS. Ids are UUIDs, so orders are placeable
 *   fallback  the fetch failed. Ali's copy has no hardcoded menu (see
 *             `data/menu.ts`), so the page shows the shop's phone number
 *             instead, and ordering is off
 */
export type MenuSource = "loading" | "api" | "fallback";

/**
 * Why the last fetch failed, so the page can say something true.
 *
 *   offline      the browser could not reach the API at all (status 0):
 *                bad signal, timeout. "Check your signal and retry."
 *   unavailable  the API answered but there is no orderable menu for this
 *                shop (404 before the tenant is seeded, 5xx, or an empty
 *                menu). The customer's connection is fine; telling them it
 *                dropped would be untrue. "Ring us to order."
 */
export type MenuFailure = "offline" | "unavailable";

interface MenuState {
  source: MenuSource;
  failure: MenuFailure | null;
  categories: Category[];
  items: MenuItem[];
  currency: string;
  /**
   * The shop has pressed its own "we're busy" button.
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
  source: "loading",
  failure: null,
  // Empty for Ali (no hardcoded menu). The page shows a loading state until
  // the API answers.
  categories: CATEGORIES,
  items: MENU_ITEMS,
  currency: SHOP.currency,
  orderingPaused: false,
  pausedMessage: null,

  load: async () => {
    // Mark the fetch in flight. On a retry this matters, because `canOrder`
    // must be false while we are asking again.
    set({ source: "loading" });
    try {
      // DEV ONLY: `?fixture` renders Ali's real menu JSON with no backend.
      // `import.meta.env.DEV` is a build-time constant, so production builds
      // drop this branch and the fixture module with it.
      const response =
        import.meta.env.DEV && new URLSearchParams(window.location.search).has("fixture")
          ? (await import("../dev/fixtureMenu")).fixtureMenu()
          : await fetchMenu();
      const { categories, items } = adaptMenu(response.categories);

      // An empty menu is a misconfigured tenant, not a valid state to order
      // from.
      if (items.length === 0) {
        set({ source: "fallback", failure: "unavailable" });
        return;
      }

      set({
        source: "api",
        failure: null,
        categories,
        items,
        currency: response.currency,
        orderingPaused: response.ordering_paused ?? false,
        pausedMessage: response.ordering_paused_message ?? null,
      });
    } catch (cause) {
      const offline = cause instanceof ApiError && cause.status === 0;
      set({ source: "fallback", failure: offline ? "offline" : "unavailable" });
    }
  },
}));

/**
 * Whether a real order can be placed right now.
 *
 * Three independent gates, and all must hold:
 *   1. `SHOP.orderingEnabled`, the deliberate master switch.
 *   2. The menu came from the API.
 *   3. The shop has not paused ordering during a rush.
 */
export function canOrder(source: MenuSource, paused = false): boolean {
  return SHOP.orderingEnabled && source === "api" && !paused;
}

/** The message to show when the shop has paused ordering, with a safe default. */
export const DEFAULT_PAUSED_MESSAGE =
  "We're very busy at the moment, so we've paused online orders for a little " +
  `while. Please call us on ${SHOP.phones[0] ?? ""} to place your order. ` +
  "Thanks for your patience.";
