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
 * Is this order for now, or a pre-order for the next service?
 *
 * ⚠️ **We never refuse an order because of the time.** An earlier version did,
 * and it was wrong: a takeaway that answers "we're closed, come back later"
 * loses that customer to whoever is still taking orders. Every serious food
 * platform takes the order and schedules it. So do we.
 *
 * What the time DOES change is what everyone is told. An order placed at 03:00
 * cannot be confirmed at 03:00, and pretending otherwise is how a customer ends
 * up staring at a page that eventually tells them to ring a closed shop. So an
 * out-of-hours order is labelled a pre-order end to end: the button says so,
 * the confirmation page says the shop will confirm when it opens instead of
 * giving up, and the tablet shows it as a pre-order rather than as an order
 * that has been ignored for eleven hours.
 *
 * `orderFromTime` is the point from which an order counts as "for today's
 * service" rather than a pre-order. Imran's own worked example is an order
 * placed at 14:00 for a 16:00 opening, so pre-service ordering is normal here.
 * ⚠️ Inferred from that example, not stated. Confirm it.
 */
export type OrderTiming = {
  /** False only means "not for immediate service" — never "refused". */
  immediate: boolean;
  /** When the shop will next be answering, "HH:MM". */
  opensAt: string;
};

export function orderTiming(now: Date = new Date()): OrderTiming {
  const uk = new Date(now.toLocaleString("en-GB", { timeZone: "Europe/London" }));
  const minutes = uk.getHours() * 60 + uk.getMinutes();
  const [fh, fm] = (SHOP.orderFromTime || SHOP.openTime).split(":").map(Number);
  const [ch, cm] = SHOP.closeTime.split(":").map(Number);
  const immediate =
    minutes >= fh! * 60 + fm! && minutes < ch! * 60 + cm!;
  return { immediate, opensAt: SHOP.openTime };
}

export function deliveryOffered(): boolean {
  return SHOP.services.includes("delivery");
}

export function collectionOffered(): boolean {
  return SHOP.services.includes("collection");
}
