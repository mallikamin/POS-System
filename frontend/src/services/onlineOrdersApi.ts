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
/**
 * Imran wants three slips per accepted order (OI-51). The repeat rides INSIDE
 * the ESC/POS payload — three cut slips, one `rawbt:` navigation — because
 * navigating three times is three chances for Chrome to drop or coalesce the
 * handoff, which is exactly the class of bug fixed on 2026-07-29.
 */
const KITCHEN_TICKET_COPIES = 3;

export async function fetchTicketUrl(orderId: string): Promise<string | null> {
  try {
    const { data } = await api.get<{ url: string; bytes: number }>(
      `/public/manage/orders/${orderId}/ticket`,
      { params: { format: "rawbt", copies: KITCHEN_TICKET_COPIES } },
    );
    return data?.url ?? null;
  } catch {
    return null;
  }
}

/**
 * Hand an already-fetched job to RawBT. **Synchronous, and it must stay that
 * way.**
 *
 * ⚠️ **This is the bug that stopped the first live ticket printing.** Chrome on
 * Android refuses to navigate to a custom scheme unless the navigation happens
 * inside a genuine user gesture — and `await`ing anything first ends that
 * gesture. The old code fetched the ticket and *then* navigated, so by the time
 * it set `location.href` the tap was over and Chrome dropped it **silently**:
 * no error, no dialog, no print, and a 200 in the server log to say the ticket
 * had been built. It looked for all the world like a printer problem.
 *
 * So the URL must already be in hand before the tap. Do not "tidy" this by
 * moving the fetch back in here.
 *
 * The `intent:` form is tried first because it names the RawBT package
 * explicitly, which newer Chrome handles more reliably than a bare scheme; the
 * plain `rawbt:` URL stays as the fallback for older builds and other browsers.
 */
export function sendToPrinter(url: string): void {
  const base64 = url.startsWith("rawbt:base64,")
    ? url.slice("rawbt:base64,".length)
    : null;

  if (base64) {
    window.location.href =
      `intent:base64,${base64}` +
      "#Intent;scheme=rawbt;package=ru.a402d.rawbtprinter;end;";
    return;
  }
  window.location.href = url;
}

/**
 * Fetch and print in one go.
 *
 * Only safe when NOT inside a user gesture that matters — i.e. the automatic
 * attempt straight after Accept, which may well be dropped by Chrome. The
 * visible Print button uses the prefetched URL instead, and that is the path
 * that actually has to work.
 */
export async function printTicket(orderId: string): Promise<boolean> {
  const url = await fetchTicketUrl(orderId);
  if (!url) return false;
  sendToPrinter(url);
  return true;
}
