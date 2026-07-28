import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { CartLine, MenuItem, ModifierOption, Pence, Variant } from "../types";

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
): string {
  const mods = modifiers.map((m) => m.id).sort().join("+");
  return `${itemId}|${variantId}|${mods}`;
}

export function unitPriceOf(variant: Variant, modifiers: ModifierOption[]): Pence {
  return variant.price + modifiers.reduce((sum, m) => sum + m.priceDelta, 0);
}

interface CartState {
  lines: CartLine[];
  add: (item: MenuItem, variant: Variant, modifiers: ModifierOption[], quantity?: number) => void;
  setQuantity: (key: string, quantity: number) => void;
  remove: (key: string) => void;
  clear: () => void;
}

export const useCart = create<CartState>()(
  persist(
    (set) => ({
      lines: [],

      add: (item, variant, modifiers, quantity = 1) =>
        set((state) => {
          const key = lineKey(item.id, variant.id, modifiers);
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
          };
          return { lines: [...state.lines, line] };
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

      clear: () => set({ lines: [] }),
    }),
    { name: "chick-shack-cart" },
  ),
);

/** Goods total, excluding any delivery fee. */
export function subtotalOf(lines: CartLine[]): Pence {
  return lines.reduce((sum, l) => sum + l.unitPrice * l.quantity, 0);
}

export function itemCountOf(lines: CartLine[]): number {
  return lines.reduce((sum, l) => sum + l.quantity, 0);
}
