/**
 * Advertising / conversion measurement: switched OFF for Ali.
 *
 * The Chick Shack storefront this was copied from reports purchases to Chick
 * Shack's own Google Ads account. Ali is a different business and must never
 * report into another client's ad account (memory: tenant-scoped-integrations),
 * so every tag, conversion label and pixel has been removed, not just
 * disabled: `index.html` loads no third-party script at all.
 *
 * `ADS_TRACKING_ENABLED` is the single switch for the leftovers that depend on
 * it: the cookie bar (`ConsentBar`) and click-id capture (`clickId.ts`). With
 * no tag on the page there is nothing to consent to, so the bar is not shown.
 *
 * If Ali later gets his OWN Google Ads account: add his tag to `index.html`
 * (consent defaults first), put his conversion label in `trackPurchase`, and
 * flip this to true. Never reuse another tenant's ids.
 */

import type { ApiOrderResponse } from "./api";

export const ADS_TRACKING_ENABLED = false;

/** Orders already reported, so a re-render or refresh cannot double count. */
export const CONVERSION_FIRED_KEY = "ali_conv_fired_v1";

/**
 * Report a placed order. Currently a no-op: there is no ad account to report
 * to. Kept as the single hook `App.tsx` already calls, so wiring Ali's own
 * account later is a change to this file only.
 */
export function trackPurchase(_order: ApiOrderResponse): void {
  if (!ADS_TRACKING_ENABLED) return;
}
