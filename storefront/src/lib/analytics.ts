/**
 * Google Ads conversion reporting.
 *
 * One conversion, "Purchase", fired when a customer reaches the confirmation
 * screen. Everything here is fire-and-forget: it is called from an effect, it
 * returns void, and it swallows its own errors. Nothing in this file may ever
 * be able to block, delay or fail an order.
 */

import type { ApiOrderResponse } from "./api";

const SEND_TO = "AW-18408520125/xy0DCPb1kOccEL3z7slE";

/** Orders already reported, so a re-render or refresh cannot double count. */
const FIRED_KEY = "cs_conv_fired_v1";

function alreadyFired(orderId: string): boolean {
  try {
    const raw = localStorage.getItem(FIRED_KEY);
    return raw ? (JSON.parse(raw) as string[]).includes(orderId) : false;
  } catch {
    return false;
  }
}

function markFired(orderId: string): void {
  try {
    const raw = localStorage.getItem(FIRED_KEY);
    const seen = raw ? (JSON.parse(raw) as string[]) : [];
    // Keep the list short. A customer's last 20 orders is far more history
    // than the double-fire window needs, and it stops this growing forever.
    const next = [...seen.filter((id) => id !== orderId), orderId].slice(-20);
    localStorage.setItem(FIRED_KEY, JSON.stringify(next));
  } catch {
    /* worst case we report the same order twice; never worth throwing over */
  }
}

/**
 * Report a placed order.
 *
 * Value is the FOOD subtotal, not the total the customer paid. Delivery fee
 * largely passes through to the driver and the tip is not ours at all, so
 * bidding on the total would systematically overvalue delivery orders and
 * teach Google to chase the wrong basket. Subtotal is the revenue the shop
 * actually keeps, which is what we want optimised for.
 *
 * `transaction_id` is the human order number, so a conversion in the Google
 * Ads report can be tied back to a real ticket without guesswork.
 *
 * Called on BOTH routes to the confirmation screen — a fresh order and a
 * return from Stripe — hence the per-order guard. It is safe to call twice,
 * and under React StrictMode in dev it will be.
 */
export function trackPurchase(order: ApiOrderResponse): void {
  if (alreadyFired(order.id)) return;

  const w = window as unknown as { gtag?: (...a: unknown[]) => void };

  // `index.html` declares `gtag` inline before gtag.js loads, so this is
  // normally present. It can still be missing if the inline block was blocked
  // outright. Return WITHOUT marking: nothing was sent, so the order must stay
  // eligible to report on a later visit rather than being retired silently.
  if (typeof w.gtag !== "function") return;

  try {
    w.gtag("event", "conversion", {
      send_to: SEND_TO,
      value: order.subtotal / 100,
      currency: "GBP",
      transaction_id: order.order_number,
    });
    markFired(order.id);
  } catch {
    /* measurement is never allowed to break the shop */
  }
}
