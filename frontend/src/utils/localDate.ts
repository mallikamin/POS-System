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
