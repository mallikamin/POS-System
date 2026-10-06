import type { Pence } from "../types";

/**
 * All money in this app is integer pence. These helpers are the only place
 * pence become pounds. Nothing else should divide by 100.
 */

const GBP = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** 499 -> "£4.99". Always shows pence — this is a checkout. */
export function formatGBP(pence: Pence): string {
  return GBP.format(pence / 100);
}

/** "4.99" (user input, pounds) -> 499. Rounds to nearest penny. */
export function poundsToPence(pounds: number): Pence {
  return Math.round(pounds * 100);
}

/** Sum helper that keeps everything in integers. */
export function sum(values: Pence[]): Pence {
  return values.reduce((a, b) => a + b, 0);
}
