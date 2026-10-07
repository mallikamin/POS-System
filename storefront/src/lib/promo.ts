import type { Pence } from "../types";
import type { ApiPromotion } from "./api";

/**
 * The discount the server will apply, so the basket can show it before the
 * order is placed. Mirrors `backend/app/services/promotions.discount_for`
 * exactly (same minimum, same round-half-up). The server recomputes it and
 * its figure is the one charged.
 */
export function promoDiscount(promo: ApiPromotion | null, subtotal: Pence): Pence {
  if (!promo || subtotal < promo.min_subtotal) return 0;
  if (Date.now() >= Date.parse(promo.ends_at)) return 0;
  return Math.floor((subtotal * promo.percent_bps + 5000) / 10000);
}

export function promoPercent(promo: ApiPromotion): number {
  return promo.percent_bps / 100;
}
