/**
 * Tax arithmetic, mirroring `order_service.compute_tax` on the server.
 *
 * One module because the rule was previously written out by hand at every call
 * site, and they drifted: F19 fixed the cart and the previews, and a FOURTH
 * copy inside the payment-transaction list kept computing the old way, so the
 * same screen showed "Order Total tax AED 1.29" above "Tax @ 5% AED 1.35". A
 * customer-facing document contradicting itself is worse than either figure
 * being wrong on its own.
 *
 * All amounts are integer minor units (fils / paisa / pence). Never floats.
 */

export interface TaxSplit {
  /** The tax portion, in minor units. */
  tax: number;
  /** What the customer actually pays, in minor units. */
  total: number;
}

/**
 * Split a subtotal into its tax portion and the payable total.
 *
 * When prices INCLUDE tax the tax is already inside `subtotal`, so the total is
 * the subtotal and the tax is derived by SUBTRACTION -- never as `net * rate`.
 * Two independent roundings would leave a remainder that either vanishes or
 * appears from nowhere, and on a tax document a stray minor unit is a
 * reconciliation failure.
 */
export function splitTax(
  subtotal: number,
  rateBps: number,
  pricesIncludeTax: boolean
): TaxSplit {
  if (rateBps <= 0) return { tax: 0, total: subtotal };

  if (pricesIncludeTax) {
    const net = Math.round((subtotal * 10_000) / (10_000 + rateBps));
    return { tax: subtotal - net, total: subtotal };
  }

  const tax = Math.round((subtotal * rateBps) / 10_000);
  return { tax, total: subtotal + tax };
}

/** The tax contained in (or due on) an amount. */
export function taxPortion(
  amount: number,
  rateBps: number,
  pricesIncludeTax: boolean
): number {
  return splitTax(amount, rateBps, pricesIncludeTax).tax;
}

/** What is payable on a base amount. */
export function payableTotal(
  base: number,
  rateBps: number,
  pricesIncludeTax: boolean
): number {
  return splitTax(base, rateBps, pricesIncludeTax).total;
}
