import type { DeliveryArea, Pence, ServiceType } from "../types";
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

/**
 * Minutes past midnight, in the shop's own timezone.
 *
 * ⚠️ **Do not go back to `new Date(now.toLocaleString("en-GB", …))`.** That was
 * here, and it was broken in every browser:
 *
 *     new Date("29/07/2026, 17:16:39")   ->   Invalid Date
 *
 * `en-GB` formats day-first, and JavaScript's date parser cannot read
 * DD/MM/YYYY — it tries month 29 and gives up. Every subsequent `getHours()`
 * returned `NaN`, and because every comparison against `NaN` is false, the shop
 * read as **closed 24 hours a day** and **every order was labelled a
 * pre-order**, live, for real customers.
 *
 * It failed silently and looked completely reasonable, which is exactly why it
 * survived review. `formatToParts` reads the numbers directly and never goes
 * near the string parser.
 */
function shopMinutesNow(now: Date): number {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(now);

  const value = (type: string) =>
    Number(parts.find((part) => part.type === type)?.value ?? NaN);

  // `hour12: false` yields "24" for midnight in some engines rather than "00".
  const hour = value("hour") % 24;
  const minute = value("minute");

  return hour * 60 + minute;
}

/** "HH:MM" as minutes past midnight. */
function toMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return (h ?? 0) * 60 + (m ?? 0);
}

/** Is the shop currently within its opening hours, in UK local time? */
export function isOpenNow(now: Date = new Date()): boolean {
  // Computed against Europe/London explicitly — the customer may be on a phone
  // set to another timezone, and the shop's hours are local.
  const minutes = shopMinutesNow(now);
  return minutes >= toMinutes(SHOP.openTime) && minutes < toMinutes(SHOP.closeTime);
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
  /** Why `immediate` is false. Absent when `immediate` is true. */
  closedReason?: "shop_closed" | "delivery_cutoff";
};

/** This area's own last-delivery-order time, or the shop-wide default. */
function deliveryCloseTimeFor(areaId: string | undefined): string {
  return (areaId && areaById(areaId)?.closeTime) || SHOP.deliveryCloseTime;
}

/**
 * Same "never refuse, just say when we'll get to it" model as `isOpenNow`,
 * but delivery gets its own, earlier cut-off (Imran, voice note 2026-08-02):
 * the shop stays open for collection until `closeTime`, but online delivery
 * needs to stop sooner so there is runway before the kitchen actually shuts.
 * `service`/`areaId` are optional so existing shop-wide-only callers keep
 * working — omit them and this behaves exactly as it did before delivery had
 * its own cut-off.
 */
export function orderTiming(
  now: Date = new Date(),
  service?: ServiceType,
  areaId?: string,
): OrderTiming {
  const minutes = shopMinutesNow(now);
  const from = toMinutes(SHOP.orderFromTime || SHOP.openTime);
  const shopOpen = minutes >= from && minutes < toMinutes(SHOP.closeTime);

  if (!shopOpen) {
    return { immediate: false, opensAt: SHOP.openTime, closedReason: "shop_closed" };
  }

  if (service === "delivery" && minutes >= toMinutes(deliveryCloseTimeFor(areaId))) {
    return { immediate: false, opensAt: SHOP.openTime, closedReason: "delivery_cutoff" };
  }

  return { immediate: true, opensAt: SHOP.openTime };
}

export function deliveryOffered(): boolean {
  return SHOP.services.includes("delivery");
}

export function collectionOffered(): boolean {
  return SHOP.services.includes("collection");
}
