import { currencyLocale } from "@/utils/currency";
/**
 * Pure display helpers for the online-order queue card.
 *
 * They live here rather than inside `OnlineOrdersPage.tsx` for one reason:
 * this project has no frontend test runner, so the only way to verify a
 * function is to bundle it and run it for real. A module with no React, no
 * store and no browser API can be bundled standalone and exercised against
 * real cases; a helper buried in a page component cannot.
 */

/**
 * Every clock time on the queue is the SHOP's local time, never the viewer's.
 *
 * These stamps are read by two people in two countries: the shop in
 * Garelochhead, and Malik in Pakistan five hours ahead. Before OI-70 this
 * called `toLocaleString` with no `timeZone` at all, so it rendered in
 * whatever zone the browser happened to be in — right on the tablet by pure
 * accident, and silently five hours wrong anywhere else. There is one time
 * that means anything for an order: the one on the wall of the shop that
 * cooked it, which is also the one the customer was quoted.
 *
 * `Intl` throws on an unknown zone rather than falling back, and a bad config
 * value must not blank out the whole queue, so the call is guarded.
 */
export function shopTime(iso: string, tz?: string): string {
  try {
    return new Date(iso).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      ...(tz ? { timeZone: tz } : {}),
    });
  } catch {
    return new Date(iso).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }
}

/** "23:14, 28 Jul" — for a pre-order, the date matters as much as the time. */
export function placedAt(iso: string, tz?: string): string {
  try {
    return new Date(iso).toLocaleString(currencyLocale(), {
      hour: "2-digit",
      minute: "2-digit",
      day: "2-digit",
      month: "short",
      ...(tz ? { timeZone: tz } : {}),
    });
  } catch {
    return new Date(iso).toLocaleString(currencyLocale(), {
      hour: "2-digit",
      minute: "2-digit",
      day: "2-digit",
      month: "short",
    });
  }
}
