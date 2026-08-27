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
  // "AED 28.00" — the dirham has 100 fils and UAE retail quotes both decimals.
  // Added explicitly in UAT (F16): AED was previously reaching `fallbackFor()`,
  // which happened to produce the right string. That is luck, not a decision —
  // the fallback exists to stop an unknown code throwing mid-render, and a
  // live tenant's currency should never depend on it.
  AED: { symbol: "AED ", locale: "en-AE", minorExponent: 2, displayDecimals: 2 },
};

/**
 * What this jurisdiction calls its consumption tax.
 *
 * UAT F18: the cart said "Tax (5% GST)" to a UAE client. The Emirates levy
 * **VAT**; GST is India, Australia, Singapore, New Zealand and Canada. Pakistan
 * is the one place in this system's history where "GST" was right, which is why
 * it was hardcoded. Getting the name wrong on a screen a customer is paying
 * against is not a typo — it is the wrong tax named on a financial document.
 *
 * Keyed by currency because that is what the tenant config actually carries; if
 * a tenant ever needs to override the label independently it becomes a config
 * field, not a longer switch here.
 */
const TAX_NAMES: Record<string, string> = {
  PKR: "GST",
  GBP: "VAT",
  AED: "VAT",
};

/** e.g. "VAT" for AED, "GST" for PKR, plain "Tax" for anything unmapped. */
export function taxName(code: string = activeCode): string {
  return TAX_NAMES[code.toUpperCase()] ?? "Tax";
}

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
 * The locale to format DATES and TIMES in for this tenant.
 *
 * F27: seven screens hardcoded a locale — `en-PK` on the printed receipt, the
 * Z-report and the staff list, `en-GB` on the order lists. So a UAE client's
 * own tax receipt carried a Pakistani date format, and the same build showed
 * two different date conventions on adjacent screens.
 *
 * Derived from the currency because that is the only jurisdiction signal the
 * tenant config carries, and it is already paired with a locale in the table
 * above. If a tenant ever needs a locale independent of its currency, that
 * becomes a config field rather than a second hardcoded constant.
 */
export function currencyLocale(code: string = activeCode): string {
  return getCurrencyDef(code).locale;
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
