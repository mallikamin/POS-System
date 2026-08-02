/**
 * Surviving the trip to Stripe and back.
 *
 * Paying by card means leaving this site entirely: the browser goes to Stripe's
 * hosted Checkout page and comes back as a **fresh page load**. This app keeps
 * its state in memory (`useState` in `App`), so without help the customer would
 * return to an empty menu having just paid — no order number, no confirmation,
 * nothing to suggest anything had happened. That is the single worst screen in
 * the whole flow, so it is worth a module of its own.
 *
 * Two halves, and both are needed:
 *
 *   the order      stashed here before the redirect, so the confirmation screen
 *                  can be rebuilt exactly as it would have appeared.
 *   the id in the  put on the return URL by the backend, so we know the page
 *   query string   load is a return from Stripe and which order it concerns —
 *                  and can tell a genuine return from a stale stash left by an
 *                  abandoned attempt days ago.
 *
 * Both must agree. Storage alone would resurrect an old order on an ordinary
 * visit; the query string alone cannot rebuild the screen. Requiring the pair
 * makes a wrong confirmation screen essentially impossible.
 */

import type { ApiOrderResponse } from "./api";
import type { OrderTiming } from "./delivery";

const STORAGE_KEY = "chickshack.pendingOrder";

/**
 * How long a stash stays usable.
 *
 * Long enough for a slow payment on a bad connection, short enough that a
 * forgotten tab reopened tomorrow does not present yesterday's order as if it
 * were new. Stripe Checkout sessions themselves expire in 24 hours, so an hour
 * is comfortably inside the window that can still be paid.
 */
const MAX_AGE_MS = 60 * 60 * 1000;

interface Stashed {
  order: ApiOrderResponse;
  // Computed once, at the moment of placing, from state (service/area) that
  // only exists on this page — Stripe's redirect is a fresh page load, so
  // this is the only way the confirmation screen can show the SAME pre-order
  // decision rather than a possibly-different one re-derived after the trip.
  timing: OrderTiming;
  savedAt: number;
}

/** Stash the placed order immediately before handing the browser to Stripe. */
export function savePendingOrder(
  order: ApiOrderResponse,
  timing: OrderTiming,
): void {
  try {
    const payload: Stashed = { order, timing, savedAt: Date.now() };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // Private browsing, a full quota, storage disabled. Not worth failing the
    // payment over — the customer still reaches Stripe and the order still
    // exists server-side; they just come back to the menu instead of their
    // confirmation. The shop sees the order either way, which is what matters.
  }
}

export function clearPendingOrder(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to do, and nothing that depends on it.
  }
}

/**
 * What the current URL says about a return from Stripe.
 *
 * `null` for an ordinary visit, which is the overwhelmingly common case.
 */
export function returnFromStripe(): { orderId: string; paid: boolean } | null {
  try {
    const params = new URLSearchParams(window.location.search);
    const orderId = params.get("order");
    if (!orderId) return null;
    return { orderId, paid: params.get("paid") === "1" };
  } catch {
    return null;
  }
}

/**
 * Rebuild the confirmation screen for a return from Stripe.
 *
 * Returns the stashed order only when it matches the id on the URL and is
 * recent. A mismatch means the stash belongs to some other attempt, and showing
 * it would tell the customer about an order they did not just pay for.
 */
export function takePendingOrder(
  orderId: string,
): { order: ApiOrderResponse; timing: OrderTiming } | null {
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
  if (!raw) return null;

  let stashed: Stashed;
  try {
    stashed = JSON.parse(raw) as Stashed;
  } catch {
    clearPendingOrder();
    return null;
  }

  const usable =
    stashed?.order?.id === orderId &&
    typeof stashed.savedAt === "number" &&
    Date.now() - stashed.savedAt < MAX_AGE_MS;

  // Consumed either way: a stash that did not match is stale by definition, and
  // leaving it would keep it eligible for some later page load.
  clearPendingOrder();
  return usable ? { order: stashed.order, timing: stashed.timing } : null;
}

/**
 * Drop the Stripe parameters from the address bar.
 *
 * Cosmetic but not pointless — it stops a refresh, a bookmark or a shared link
 * from re-triggering the return path, and stops the customer's order id sitting
 * in a URL they might paste somewhere.
 */
export function stripReturnParams(): void {
  try {
    const url = new URL(window.location.href);
    url.searchParams.delete("order");
    url.searchParams.delete("paid");
    window.history.replaceState({}, "", url.pathname + url.search + url.hash);
  } catch {
    // A browser without history.replaceState is not one we need to support.
  }
}
