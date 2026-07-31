import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { CartLine, MenuItem, ModifierOption, Pence, Variant } from "../types";
import { NO_VARIANT } from "../types";
import type { ApiOrderLineRequest } from "../lib/api";

/**
 * Basket state, persisted to localStorage so a customer who reloads or comes
 * back later does not lose their order.
 *
 * Prices held here are for DISPLAY ONLY. The server recalculates every total
 * from its own menu when the order is submitted — the browser is never trusted
 * on price. If they disagree, the server wins.
 */

/**
 * Identity of a configured line. Two lines merge only if the item, the variant
 * and the exact set of modifiers all match. Modifier ids are sorted so that
 * picking BBQ-then-Mayo and Mayo-then-BBQ produce the same line.
 */
function lineKey(
  itemId: string,
  variantId: string,
  modifiers: ModifierOption[],
  exclusions: string[] = [],
  note = "",
): string {
  const mods = modifiers.map((m) => m.id).sort().join("+");
  // Exclusions are part of identity, not decoration. A plain wrap and a
  // no-onion wrap are two different jobs in the kitchen and must stay two
  // lines, however identical their price. Same reasoning for the free-text
  // note: "extra crispy" and "well done" are different instructions and must
  // not collapse into a single line that can only show one of them.
  const without = [...exclusions].sort().join("+");
  return `${itemId}|${variantId}|${mods}|${without}|${note}`;
}

export function unitPriceOf(variant: Variant, modifiers: ModifierOption[]): Pence {
  return variant.price + modifiers.reduce((sum, m) => sum + m.priceDelta, 0);
}

interface CartState {
  lines: CartLine[];
  /**
   * The Checkout page's "Notes for the kitchen" textarea, lifted up here
   * (rather than local state in Checkout) so it survives Checkout
   * unmounting when the customer goes back to the menu, and so `add()` can
   * append a per-item note into it directly. Single source of truth: once
   * appended, the text is just text — the customer can edit or delete any
   * of it, including the auto-inserted part, from the Checkout box.
   */
  orderNotes: string;
  add: (
    item: MenuItem,
    variant: Variant,
    modifiers: ModifierOption[],
    quantity?: number,
    exclusions?: string[],
    note?: string,
  ) => void;
  setQuantity: (key: string, quantity: number) => void;
  remove: (key: string) => void;
  clear: () => void;
  setOrderNotes: (text: string) => void;
  /**
   * Re-check every basket line against the live menu. Returns how many lines
   * were dropped, so the customer can be told rather than quietly short-changed.
   */
  reconcile: (menuItems: MenuItem[]) => number;
}

export const useCart = create<CartState>()(
  persist(
    (set, get) => ({
      lines: [],
      orderNotes: "",

      add: (item, variant, modifiers, quantity = 1, exclusions = [], note) =>
        set((state) => {
          const trimmedNote = note?.trim() || "";
          const key = lineKey(item.id, variant.id, modifiers, exclusions, trimmedNote);
          const existing = state.lines.find((l) => l.key === key);
          if (existing) {
            return {
              lines: state.lines.map((l) =>
                l.key === key ? { ...l, quantity: l.quantity + quantity } : l,
              ),
            };
          }
          const line: CartLine = {
            key,
            itemId: item.id,
            itemName: item.name,
            variantId: variant.id,
            variantName: variant.name,
            modifiers,
            quantity,
            unitPrice: unitPriceOf(variant, modifiers),
            exclusions,
            ...(trimmedNote ? { note: trimmedNote } : {}),
          };
          // Append into the shared order-notes text, once, at the moment this
          // becomes a genuinely new line — not on a quantity-merge above,
          // which would otherwise re-insert the same note every extra unit.
          const orderNotes = trimmedNote
            ? [state.orderNotes, `${item.name}: ${trimmedNote}`]
                .filter(Boolean)
                .join("\n")
            : state.orderNotes;
          return { lines: [...state.lines, line], orderNotes };
        }),

      setQuantity: (key, quantity) =>
        set((state) => ({
          lines:
            quantity <= 0
              ? state.lines.filter((l) => l.key !== key)
              : state.lines.map((l) => (l.key === key ? { ...l, quantity } : l)),
        })),

      remove: (key) =>
        set((state) => ({ lines: state.lines.filter((l) => l.key !== key) })),

      clear: () => set({ lines: [], orderNotes: "" }),

      setOrderNotes: (text) => set({ orderNotes: text }),

      /**
       * Reconcile the basket against the menu currently on screen.
       *
       * This is not housekeeping, it is a correctness requirement. The basket
       * is persisted to localStorage and outlives the page, so it can hold:
       *
       *   - slug ids ("peri-half") saved before the menu came from the API,
       *     which `POST /orders` rejects with a 422 because it wants UUIDs;
       *   - UUIDs from a different environment, since local and production are
       *     separately seeded and share no ids;
       *   - options or items the shop has since turned off, which the server
       *     refuses with a 409.
       *
       * Every one of those fails at the last step of checkout, after the
       * customer has typed their address. Dropping them here means the basket
       * on screen is always one the server would accept.
       *
       * Surviving lines also have their prices and names refreshed from the
       * live menu, so a price Imran edits in the admin screen is reflected in
       * an already-open basket instead of disagreeing with the server's total.
       */
      reconcile: (menuItems) => {
        const itemsById = new Map(
          menuItems.map((item) => [item.id, item] as const),
        );
        const kept: CartLine[] = [];
        let dropped = 0;
        let changed = false;

        for (const line of get().lines) {
          const item = itemsById.get(line.itemId);
          if (!item) {
            dropped++;
            continue;
          }

          const variant = item.variants.find((v) => v.id === line.variantId);
          if (!variant) {
            dropped++;
            continue;
          }

          const optionsById = new Map(
            item.modifierGroups.flatMap((group) =>
              group.options.map((option) => [option.id, option] as const),
            ),
          );
          const modifiers: ModifierOption[] = [];
          for (const chosen of line.modifiers) {
            const live = optionsById.get(chosen.id);
            if (live) modifiers.push(live);
          }
          if (modifiers.length !== line.modifiers.length) {
            dropped++;
            continue;
          }

          const unitPrice = unitPriceOf(variant, modifiers);
          if (
            unitPrice !== line.unitPrice ||
            item.name !== line.itemName ||
            variant.name !== line.variantName
          ) {
            changed = true;
          }
          kept.push({
            ...line,
            itemName: item.name,
            variantName: variant.name,
            modifiers,
            unitPrice,
          });
        }

        if (dropped > 0 || changed) set({ lines: kept });
        return dropped;
      },
    }),
    {
      name: "chick-shack-cart",
      // v2: basket ids moved from menu.ts slugs to database UUIDs.
      // v3: lines gained `exclusions`, which is part of the line key. A basket
      //     persisted under v2 has neither the field nor the key format, and
      //     `reconcile` would keep it happily. Discarding once at the version
      //     boundary is deterministic and needs no menu to be loaded.
      // v4: lines gained `note` (also part of the key), and the store gained
      //     `orderNotes`. Same reasoning as v3 — discard rather than carry a
      //     basket whose keys were built without it.
      version: 4,
      partialize: (state) => ({ lines: state.lines, orderNotes: state.orderNotes }),
      migrate: () => ({ lines: [], orderNotes: "" }),
    },
  ),
);

/**
 * Translate the basket into the order endpoint's line format.
 *
 * IDs and quantities. No prices, no names, no totals — see the header of
 * `lib/api.ts` and `backend/app/schemas/public_order.py`.
 *
 * The chosen variant is sent as just another modifier id, because in the
 * database that is exactly what it is: an option in the item's required
 * "Choice" group. Items with a single price carry `NO_VARIANT`, which is a
 * marker rather than a real id and is dropped here — sending it would be a 422.
 */
export function orderLinesOf(lines: CartLine[]): ApiOrderLineRequest[] {
  return lines.map((line) => {
    // One per line: `print_service` splits notes on newlines and prints each
    // in bold, so the kitchen gets "** No onion" / "** extra crispy" each on
    // its own row rather than a sentence to parse. The free-text note is
    // deliberately given the same bold treatment as an exclusion tick — both
    // are "read this" instructions to whoever is making the item. Omitted
    // entirely when there's nothing, so an untouched order carries no empty
    // notes field.
    const noteLines = [...line.exclusions, ...(line.note ? [line.note] : [])];
    return {
      menu_item_id: line.itemId,
      quantity: line.quantity,
      modifier_ids: [
        ...(line.variantId === NO_VARIANT ? [] : [line.variantId]),
        ...line.modifiers.map((modifier) => modifier.id),
      ],
      ...(noteLines.length ? { notes: noteLines.join("\n") } : {}),
    };
  });
}

/** Goods total, excluding any delivery fee. */
export function subtotalOf(lines: CartLine[]): Pence {
  return lines.reduce((sum, l) => sum + l.unitPrice * l.quantity, 0);
}

export function itemCountOf(lines: CartLine[]): number {
  return lines.reduce((sum, l) => sum + l.quantity, 0);
}
