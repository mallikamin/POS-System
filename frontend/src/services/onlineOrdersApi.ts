import api from "@/lib/axios";

/**
 * The shop's own view of its online orders — what the order-queue tablet polls.
 *
 * Every route here is authenticated and the tenant comes from the caller's
 * token, never from the URL. That is the opposite of the customer-facing
 * storefront routes, which must name their tenant because nobody is logged in.
 */

export type OnlineOrderState = "pending" | "active" | "all";

export interface OnlineOrderLine {
  name: string;
  quantity: number;
  unit_price: number;
  total: number;
  modifiers: string[];
}

export interface OnlineOrder {
  id: string;
  order_number: string;
  status: string;
  payment_status: string;
  service_type: "collection" | "delivery";
  placed_at: string;

  customer_name: string;
  customer_phone: string | null;
  delivery_address: string | null;
  delivery_area: string | null;
  notes: string | null;

  lines: OnlineOrderLine[];
  subtotal: number;
  tax_amount: number;
  delivery_fee: number;
  total: number;
  currency: string;

  accepted_at: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  eta_minutes: number | null;
}

interface QueueResponse {
  state: OnlineOrderState;
  count: number;
  orders: OnlineOrder[];
}

export async function listOnlineOrders(
  state: OnlineOrderState = "pending",
): Promise<OnlineOrder[]> {
  const { data } = await api.get<QueueResponse>("/public/manage/orders", {
    params: { state },
  });
  return data.orders;
}

export async function acceptOnlineOrder(
  orderId: string,
  etaMinutes: number,
): Promise<OnlineOrder> {
  const { data } = await api.post(`/public/manage/orders/${orderId}/accept`, {
    eta_minutes: etaMinutes,
  });
  return data;
}

export async function rejectOnlineOrder(
  orderId: string,
  reason: string,
): Promise<OnlineOrder> {
  const { data } = await api.post(`/public/manage/orders/${orderId}/reject`, {
    reason,
  });
  return data;
}

/**
 * The food is made: out for delivery, or waiting on the counter.
 *
 * One call for both meanings. The server decides what the customer is told
 * from the order's own `service_type`, so the shop taps the same thing either
 * way and cannot pick the wrong one.
 */
export async function markOnlineOrderReady(orderId: string): Promise<OnlineOrder> {
  const { data } = await api.post(`/public/manage/orders/${orderId}/ready`, {});
  return data;
}

/**
 * Handed over. The order is done and leaves the Active tab.
 *
 * `markPaid` settles the balance in the same call, because for a cash takeaway
 * the money and the food change hands at the same instant. It is passed
 * explicitly rather than inferred here — the caller knows whether the order was
 * already paid, and a button that silently took payment would be dishonest.
 */
export async function completeOnlineOrder(
  orderId: string,
  markPaid = false,
): Promise<OnlineOrder> {
  const { data } = await api.post(`/public/manage/orders/${orderId}/complete`, {
    mark_paid: markPaid,
  });
  return data;
}

/**
 * Record payment separately, for when a driver comes back with the cash later.
 *
 * Writes a real payment row server-side, not a status flag, so the money shows
 * up in the Z-report and the sales reports.
 */
export async function markOnlineOrderPaid(
  orderId: string,
  methodCode = "cash",
): Promise<OnlineOrder> {
  const { data } = await api.post(`/public/manage/orders/${orderId}/paid`, {
    method_code: methodCode,
  });
  return data;
}

/**
 * Fetch the kitchen ticket as a `rawbt:` URL and hand it to the printer.
 *
 * ⚠️ **The server does not print.** It cannot: our API is on a box in
 * Singapore and the printer sits on the shop's LAN in Scotland. What the
 * server does is build the ESC/POS bytes; this function hands them to the
 * RawBT app on the tablet, which opens TCP:9100 to the printer's local IP.
 *
 * That is the whole reason printing rides on the Accept tap — the tablet is
 * awake and in the foreground at exactly that moment, so nothing has to
 * survive Android's Doze in the background.
 *
 * Returns false if the ticket could not be built. A failed print must never
 * undo an accepted order: the order is accepted either way and the ticket can
 * be printed again from the Active tab.
 */
export async function printTicket(orderId: string): Promise<boolean> {
  try {
    const { data } = await api.get<{ url: string; bytes: number }>(
      `/public/manage/orders/${orderId}/ticket`,
      { params: { format: "rawbt" } },
    );
    if (!data?.url) return false;

    // Navigating rather than window.open: a popup blocker will silently eat
    // window.open on Android Chrome, and this is a custom scheme handoff, not
    // a page we ever come back from.
    window.location.href = data.url;
    return true;
  } catch {
    return false;
  }
}
