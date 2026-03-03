import { create } from "zustand";
import type { OrderListItem, OrderResponse, PaginatedOrders } from "@/types/order";
import { createOrder, fetchOrders, transitionOrder, voidOrder } from "@/services/ordersApi";
import { useCartStore } from "@/stores/cartStore";
import { useUIStore } from "@/stores/uiStore";
import { useFloorStore } from "@/stores/floorStore";
import type { OrderCreateRequest, OrderItemCreate, OrderItemModifierCreate } from "@/types/order";

interface OrderState {
  orders: OrderListItem[];
  total: number;
  isLoading: boolean;
  error: string | null;
  lastFetched: number | null;
  isSending: boolean;
  lastOrderNumber: string | null;
}

interface OrderActions {
  loadOrders: (params?: {
    status?: string;
    type?: string;
    active_only?: boolean;
  }) => Promise<void>;
  createOrderFromCart: (
    orderType?: string,
    tableId?: string,
    customerName?: string,
    customerPhone?: string,
    waiterId?: string
  ) => Promise<OrderResponse>;
  transitionOrder: (id: string, status: string) => Promise<void>;
  voidOrder: (id: string, reason: string, authToken?: string) => Promise<void>;
  clearOrders: () => void;
}

type OrderStore = OrderState & OrderActions;

export const useOrderStore = create<OrderStore>()((set, get) => ({
  orders: [],
  total: 0,
  isLoading: false,
  error: null,
  lastFetched: null,
  isSending: false,
  lastOrderNumber: null,

  loadOrders: async (params) => {
    const state = get();
    if (state.isLoading) return;
    // 10-second debounce
    if (state.lastFetched && Date.now() - state.lastFetched < 10_000) return;

    set({ isLoading: true, error: null });
    try {
      const data: PaginatedOrders = await fetchOrders({
        ...params,
        page_size: 100,
      });
      set({
        orders: data.items,
        total: data.total,
        isLoading: false,
        lastFetched: Date.now(),
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load orders";
      set({ error: message, isLoading: false });
    }
  },

  createOrderFromCart: async (
    orderType?: string,
    tableId?: string,
    customerName?: string,
    customerPhone?: string,
    waiterId?: string
  ) => {
    set({ isSending: true, error: null });
    try {
      const cartState = useCartStore.getState();
      const cart = cartState.carts[cartState.activeCartId];
      if (!cart || cart.lines.length === 0) {
        throw new Error("Cart is empty");
      }

      const channel = orderType || useUIStore.getState().currentChannel || "takeaway";

      const items: OrderItemCreate[] = cart.lines.map((line) => ({
        menu_item_id: line.menuItem.id,
        name: line.menuItem.name,
        quantity: line.quantity,
        unit_price: line.unitPrice,
        modifiers: line.modifiers.map(
          (m): OrderItemModifierCreate => ({
            modifier_id: m.modifier_option_id,
            name: m.name,
            price_adjustment: m.price_adjustment,
          })
        ),
        notes: line.notes || undefined,
      }));

      const payload: OrderCreateRequest = {
        order_type: channel as OrderCreateRequest["order_type"],
        table_id: tableId || undefined,
        waiter_id: waiterId || undefined,
        customer_name: customerName || undefined,
        customer_phone: customerPhone || undefined,
        items,
      };

      const order = await createOrder(payload);

      // Clear the cart after successful order
      useCartStore.getState().clearCart();

      // Update table status to occupied if dine-in
      if (channel === "dine_in" && tableId) {
        useFloorStore.getState().updateTableInStore(tableId, { status: "occupied" });
      }

      set({
        isSending: false,
        lastOrderNumber: order.order_number,
        // Force refresh order list
        lastFetched: null,
      });

      return order;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to create order";
      set({ error: message, isSending: false });
      throw err;
    }
  },

  transitionOrder: async (id, status) => {
    try {
      await transitionOrder(id, status);
      // Force refresh
      set({ lastFetched: null });
      await get().loadOrders();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to update order";
      set({ error: message });
      throw err;
    }
  },

  voidOrder: async (id, reason, authToken) => {
    try {
      await voidOrder(id, reason, authToken);
      set({ lastFetched: null });
      await get().loadOrders();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to void order";
      set({ error: message });
      throw err;
    }
  },

  clearOrders: () => {
    set({ orders: [], total: 0, lastFetched: null, error: null });
  },
}));
