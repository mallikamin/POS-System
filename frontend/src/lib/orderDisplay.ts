/**
 * Pure display helpers for the online-order queue card.
 *
 * They live here rather than inside `OnlineOrdersPage.tsx` for one reason:
 * this project has no frontend test runner, so the only way to verify a
 * function is to bundle it and run it for real. A module with no React, no
 * store and no browser API can be bundled standalone and exercised against
 * real cases; a helper buried in a page component cannot.
 */

/** Modifier-name suffix that marks a dip tub. Mirrors `print_service.py`. */
export const DIP_TUB_SUFFIX = " (Dip Tub)";

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
    return new Date(iso).toLocaleString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      day: "2-digit",
      month: "short",
      ...(tz ? { timeZone: tz } : {}),
    });
  } catch {
    return new Date(iso).toLocaleString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      day: "2-digit",
      month: "short",
    });
  }
}

export function isDipTub(modifier: string): boolean {
  return modifier.endsWith(DIP_TUB_SUFFIX);
}

/** The tub name without its suffix — the block's own heading already says it. */
export function dipTubLabel(modifier: string): string {
  return modifier.endsWith(DIP_TUB_SUFFIX)
    ? modifier.slice(0, -DIP_TUB_SUFFIX.length)
    : modifier;
}

/** The shape `dipTubTotals` needs — deliberately narrower than `OnlineOrder`. */
export interface DipTubSource {
  lines: { quantity: number; modifiers: string[] }[];
}

/**
 * Dip tubs rolled up across the whole order — the screen saying what the paper
 * says (OI-71).
 *
 * The printed ticket has grouped these into one DIP TUBS block since OI-64
 * (`print_service.py`, same suffix rule) because a tub buried as a sub-line
 * under whichever item it was attached to is easy for a busy packer to miss.
 * The tablet card kept printing them inline, so screen and paper disagreed —
 * and either one may be what the person packing is looking at.
 *
 * Counts by line QUANTITY, not by occurrence, exactly as the ticket does:
 * 3 × a meal carrying one dip is three tubs to count out, not one. Standalone
 * Dips-category items sold on their own carry no suffix and are deliberately
 * untouched, again matching the ticket.
 */
export function dipTubTotals(order: DipTubSource): [string, number][] {
  const counts = new Map<string, number>();
  for (const line of order.lines) {
    for (const modifier of line.modifiers) {
      if (!isDipTub(modifier)) continue;
      counts.set(modifier, (counts.get(modifier) ?? 0) + line.quantity);
    }
  }
  return [...counts.entries()].sort(([a], [b]) => a.localeCompare(b));
}
