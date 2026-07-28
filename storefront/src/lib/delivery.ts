import type { DeliveryArea, Pence } from "../types";
import { SHOP, areaById } from "../data/menu";

/**
 * Delivery eligibility and pricing.
 *
 * The shop prices delivery BY SETTLEMENT, not by postcode — Garelochhead £3.00
 * through to Arrochar £15.00, straight off their printed menu. Most of those
 * villages share the G84 outward code, so a postcode-prefix lookup would quote
 * £3 for a £15 run. The customer picks their area instead, which also matches
 * how the shop and its drivers already talk about deliveries.
 */

export type DeliveryCheck =
  | { ok: true; area: DeliveryArea; fee: Pence }
  | { ok: false; reason: "no_area_selected" }
  | { ok: false; reason: "unknown_area" }
  | { ok: false; reason: "below_minimum"; shortfall: Pence };

/**
 * Whether this basket can be delivered to the chosen area, and for how much.
 * `subtotal` is the goods total in pence, before any delivery fee.
 */
export function checkDelivery(areaId: string, subtotal: Pence): DeliveryCheck {
  if (!areaId) return { ok: false, reason: "no_area_selected" };

  const area = areaById(areaId);
  if (!area) return { ok: false, reason: "unknown_area" };

  if (SHOP.deliveryMinimum > 0 && subtotal < SHOP.deliveryMinimum) {
    return {
      ok: false,
      reason: "below_minimum",
      shortfall: SHOP.deliveryMinimum - subtotal,
    };
  }

  return { ok: true, area, fee: area.fee };
}

/** Is the shop currently within its opening hours, in UK local time? */
export function isOpenNow(now: Date = new Date()): boolean {
  // Compute against Europe/London explicitly — the customer may be on a phone
  // set to another timezone, and the shop's hours are local.
  const uk = new Date(now.toLocaleString("en-GB", { timeZone: "Europe/London" }));
  const minutes = uk.getHours() * 60 + uk.getMinutes();
  const [oh, om] = SHOP.openTime.split(":").map(Number);
  const [ch, cm] = SHOP.closeTime.split(":").map(Number);
  return minutes >= oh! * 60 + om! && minutes < ch! * 60 + cm!;
}

/**
 * May an order be PLACED right now?
 *
 * Distinct from `isOpenNow`, and the difference is the whole point. The shop
 * opens at 16:00, but Imran's own worked example is an order **placed at
 * 14:00** and accepted at 15:30 — so he takes pre-orders before service, and
 * refusing them would remove behaviour he already relies on.
 *
 * What must NOT happen is an order at 03:00. Nobody is at the tablet, the
 * customer's confirmation screen gives up after twenty minutes, and the shop
 * opens to stale orders it never agreed to. Before this existed, `isOpenNow`
 * only drew a banner and checkout was reachable around the clock.
 *
 * ⚠️ `orderFromTime` is inferred from that 14:00 example, not stated by the
 * client. Confirm it before relying on it commercially.
 */
export function canOrderNow(now: Date = new Date()): boolean {
  const uk = new Date(now.toLocaleString("en-GB", { timeZone: "Europe/London" }));
  const minutes = uk.getHours() * 60 + uk.getMinutes();
  const [fh, fm] = (SHOP.orderFromTime || SHOP.openTime).split(":").map(Number);
  const [ch, cm] = SHOP.closeTime.split(":").map(Number);
  return minutes >= fh! * 60 + fm! && minutes < ch! * 60 + cm!;
}

export function deliveryOffered(): boolean {
  return SHOP.services.includes("delivery");
}

export function collectionOffered(): boolean {
  return SHOP.services.includes("collection");
}
