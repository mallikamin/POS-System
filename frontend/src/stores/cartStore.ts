import { create } from "zustand";
import type { MenuItem } from "@/types/menu";
import type { SelectedModifier } from "@/types/cart";

/* ==========================================================================
   Cart line item — one entry per unique item+modifier combination
   ========================================================================== */

export interface CartLine {
  lineId: string;
  menuItem: MenuItem;
  quantity: number;
  modifiers: SelectedModifier[];
  notes: string;
  /** Unit price = item.price + sum(modifier.price_adjustment), in paisa */
  unitPrice: number;
}

export interface Cart {
  lines: CartLine[];
  createdAt: number;
}

/* ==========================================================================
   Store shape
   ========================================================================== */

interface CartState {
  /** All carts keyed by context id (table uuid for dine-in, "takeaway" for takeaway) */
  carts: Record<string, Cart>;
  /** Currently visible cart */
  activeCartId: string;
}

interface CartActions {
  setActiveCart: (id: string) => void;
  addItem: (menuItem: MenuItem, modifiers: SelectedModifier[]) => void;
  updateQuantity: (lineId: string, quantity: number) => void;
  removeItem: (lineId: string) => void;
  setLineNotes: (lineId: string, notes: string) => void;
  clearCart: (cartId?: string) => void;
  getActiveCart: () => Cart;
  getSubtotal: () => number;
  getItemCount: () => number;
}

type CartStore = CartState & CartActions;

/* ==========================================================================
   Helpers
   ========================================================================== */

function generateLineId(): string {
  return `line-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function calcUnitPrice(menuItem: MenuItem, modifiers: SelectedModifier[]): number {
  const base = menuItem.price;
  const adj = modifiers.reduce((sum, m) => sum + m.price_adjustment, 0);
  return Math.max(0, base + adj);
}

/** Check if two modifier arrays are identical (same options selected) */
function modifiersMatch(a: SelectedModifier[], b: SelectedModifier[]): boolean {
  if (a.length !== b.length) return false;
  const aIds = a.map((m) => m.modifier_option_id).sort();
  const bIds = b.map((m) => m.modifier_option_id).sort();
  return aIds.every((id, i) => id === bIds[i]);
}

/** Stable empty cart sentinel — prevents new object allocation on every selector call */
export const EMPTY_CART: Cart = Object.freeze({ lines: [], createdAt: 0 }) as Cart;

function newCart(): Cart {
  return { lines: [], createdAt: Date.now() };
}

/* ==========================================================================
   Store
   ========================================================================== */

export const useCartStore = create<CartStore>()((set, get) => ({
  carts: {},
  activeCartId: "takeaway",

  setActiveCart: (id: string) => {
    set((state) => {
      // Ensure the cart exists
      if (!state.carts[id]) {
        return { activeCartId: id, carts: { ...state.carts, [id]: newCart() } };
      }
      return { activeCartId: id };
    });
  },

  addItem: (menuItem: MenuItem, modifiers: SelectedModifier[]) => {
    set((state) => {
      const cartId = state.activeCartId;
      const cart = state.carts[cartId] || newCart();

      // Check if same item+modifiers already in cart — increment quantity
      const existingIndex = cart.lines.findIndex(
        (line) =>
          line.menuItem.id === menuItem.id && modifiersMatch(line.modifiers, modifiers)
      );

      let newLines: CartLine[];
      if (existingIndex >= 0) {
        newLines = cart.lines.map((line, i) =>
          i === existingIndex ? { ...line, quantity: line.quantity + 1 } : line
        );
      } else {
        const newLine: CartLine = {
          lineId: generateLineId(),
          menuItem,
          quantity: 1,
          modifiers,
          notes: "",
          unitPrice: calcUnitPrice(menuItem, modifiers),
        };
        newLines = [...cart.lines, newLine];
      }

      return {
        carts: {
          ...state.carts,
          [cartId]: { ...cart, lines: newLines },
        },
      };
    });
  },

  updateQuantity: (lineId: string, quantity: number) => {
    set((state) => {
      const cartId = state.activeCartId;
      const cart = state.carts[cartId];
      if (!cart) return state;

      const newLines =
        quantity <= 0
          ? cart.lines.filter((l) => l.lineId !== lineId)
          : cart.lines.map((l) => (l.lineId === lineId ? { ...l, quantity } : l));

      return {
        carts: {
          ...state.carts,
          [cartId]: { ...cart, lines: newLines },
        },
      };
    });
  },

  removeItem: (lineId: string) => {
    set((state) => {
      const cartId = state.activeCartId;
      const cart = state.carts[cartId];
      if (!cart) return state;

      return {
        carts: {
          ...state.carts,
          [cartId]: { ...cart, lines: cart.lines.filter((l) => l.lineId !== lineId) },
        },
      };
    });
  },

  setLineNotes: (lineId: string, notes: string) => {
    set((state) => {
      const cartId = state.activeCartId;
      const cart = state.carts[cartId];
      if (!cart) return state;

      return {
        carts: {
          ...state.carts,
          [cartId]: {
            ...cart,
            lines: cart.lines.map((l) => (l.lineId === lineId ? { ...l, notes } : l)),
          },
        },
      };
    });
  },

  clearCart: (cartId?: string) => {
    set((state) => {
      const id = cartId || state.activeCartId;
      return {
        carts: {
          ...state.carts,
          [id]: newCart(),
        },
      };
    });
  },

  getActiveCart: () => {
    const state = get();
    return state.carts[state.activeCartId] || EMPTY_CART;
  },

  getSubtotal: () => {
    const state = get();
    const cart = state.carts[state.activeCartId];
    if (!cart) return 0;
    return cart.lines.reduce((sum, line) => sum + line.unitPrice * line.quantity, 0);
  },

  getItemCount: () => {
    const state = get();
    const cart = state.carts[state.activeCartId];
    if (!cart) return 0;
    return cart.lines.reduce((sum, line) => sum + line.quantity, 0);
  },
}));
