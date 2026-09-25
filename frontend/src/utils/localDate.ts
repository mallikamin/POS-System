/**
 * A date as YYYY-MM-DD on the device's own calendar.
 *
 * `toISOString()` converts to UTC first, so in Pakistan every date picked
 * between midnight and 5 am was yesterday's, and "start of this month" was the
 * last day of the previous one (Danny's UAT D-30, 2026-09-25).
 */
export function toLocalISODate(d: Date = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/**
 * A bare "YYYY-MM-DD" is a calendar date, not an instant: `new Date()` reads it
 * as UTC midnight, which is the previous day anywhere west of Greenwich.
 */
function toDate(value: string | Date): Date {
  if (value instanceof Date) return value;
  const bare = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (bare) return new Date(Number(bare[1]), Number(bare[2]) - 1, Number(bare[3]));
  return new Date(value);
}

/**
 * "24 Sep 2026". Never the browser default: an en-US browser printed 9/24/2026,
 * which a Pakistani reader takes as the 9th of the 24th month, and 5/9 is
 * ambiguous everywhere (Danny's UAT D-47). Same form as the printed PO.
 */
export function formatDate(value: string | Date): string {
  return toDate(value).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** "24 Sep 2026, 14:05" (24-hour clock, same as the order screens). */
export function formatDateTime(value: string | Date): string {
  const d = toDate(value);
  return `${formatDate(d)}, ${d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`;
}
