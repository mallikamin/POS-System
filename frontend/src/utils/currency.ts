/**
 * Currency formatting.
 *
 * All monetary amounts are stored and transported as INTEGER MINOR UNITS
 * (paisa for PKR, pence for GBP). Never floats.
 *
 * Two distinct concepts, deliberately kept separate — conflating them is a
 * money bug:
 *
 *   minorExponent   how many minor units make one major unit (10^n).
 *                   PKR = 2 (100 paisa = 1 rupee). Drives ARITHMETIC.
 *   displayDecimals how many decimal places to SHOW.
 *                   PKR = 0 by local convention, even though it has paisa.
 *
 * For PKR these differ (store paisa, display whole rupees). For GBP they do
 * not (store pence, display pence). Using one for the other would render
 * £8.50 as £9 — which is what this module previously did.
 */

export interface CurrencyDef {
  /** Prefix as displayed. Trailing space is intentional where the locale uses one. */
  symbol: string;
  locale: string;
  /** 10^n minor units per major unit. Arithmetic only. */
  minorExponent: number;
  /** Decimal places shown to the user. Presentation only. */
  displayDecimals: number;
}

const CURRENCIES: Record<string, CurrencyDef> = {
  // "Rs. 1,800" — matches the long-standing PKR output exactly. Do not change.
  PKR: { symbol: "Rs. ", locale: "en-PK", minorExponent: 2, displayDecimals: 0 },
  // "£8.50" — pence must always show, this is a checkout-facing currency.
  GBP: { symbol: "£", locale: "en-GB", minorExponent: 2, displayDecimals: 2 },
};

/** Unknown codes fall back to this rather than throwing mid-render. */
function fallbackFor(code: string): CurrencyDef {
  return {
    symbol: `${code} `,
    locale: "en-US",
    minorExponent: 2,
    displayDecimals: 2,
  };
}

/**
 * Default stays PKR so existing tenants are unaffected until their config
 * loads. `setActiveCurrency` is called by configStore on fetch.
 */
let activeCode = "PKR";

export function setActiveCurrency(code: string | null | undefined): void {
  if (!code) return;
  activeCode = code.toUpperCase();
}

export function getActiveCurrency(): string {
  return activeCode;
}

export function getCurrencyDef(code: string = activeCode): CurrencyDef {
  return CURRENCIES[code.toUpperCase()] ?? fallbackFor(code.toUpperCase());
}

/**
 * Format an integer minor-unit amount for display.
 * @param minor Integer amount in minor units (paisa / pence / fils).
 */
export function formatMoney(minor: number, code: string = activeCode): string {
  const def = getCurrencyDef(code);
  const major = minor / 10 ** def.minorExponent;
  return `${def.symbol}${major.toLocaleString(def.locale, {
    minimumFractionDigits: def.displayDecimals,
    maximumFractionDigits: def.displayDecimals,
  })}`;
}

/**
 * @deprecated Use `formatMoney`. Retained so the ~140 existing call sites keep
 * working; it is currency-aware, so it is no longer PKR-specific despite the
 * name. New code should not use it.
 */
export function formatPKR(paisa: number): string {
  return formatMoney(paisa);
}

/** Major units (user input, e.g. 8.50) to integer minor units (850). */
export function majorToMinor(major: number, code: string = activeCode): number {
  return Math.round(major * 10 ** getCurrencyDef(code).minorExponent);
}

/** Integer minor units to major units, for populating number inputs. */
export function minorToMajor(minor: number, code: string = activeCode): number {
  return minor / 10 ** getCurrencyDef(code).minorExponent;
}

/** @deprecated Use `majorToMinor`. */
export function rupeesToPaisa(rupees: number): number {
  return majorToMinor(rupees);
}

/** @deprecated Use `minorToMajor`. */
export function paisaToRupees(paisa: number): number {
  return minorToMajor(paisa);
}
