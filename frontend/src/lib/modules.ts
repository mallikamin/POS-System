/**
 * Which parts of the interface this tenant should be shown.
 *
 * One backend serves several restaurants and they do not all buy, or want, the
 * same things. A bakery with no tables should not be offered "Dine-In" as its
 * most prominent action, and a client who has never heard of QuickBooks should
 * not find two QuickBooks entries in their sidebar. Both were found in UAT on
 * 2026-08-27.
 *
 * ⚠️ **THIS IS PRESENTATION, NOT ACCESS CONTROL, AND THE DIFFERENCE MATTERS.**
 *
 * Hiding a nav entry removes it from view. It does not stop anyone reaching the
 * route by typing it, and it does not stop the API answering, because every
 * admin endpoint in this system is gated by ROLE and nothing else. A filter is
 * not an invariant -- the same rule that OI-61 was opened for. The real
 * per-tenant module gate, enforced on the endpoints, is OI-93 and is not built.
 *
 * So: use this to make a client's screen match their business. Never cite it as
 * a reason something is secure.
 *
 * The empty string means hide nothing, which is what every existing tenant has
 * and therefore exactly today's behaviour. Adding a slug is opt-in per tenant.
 */

import type { RestaurantConfig } from "@/types";

/** Slugs understood today. Keep in step with the nav and dashboard call sites. */
export type UiModule =
  | "dine-in"
  | "takeaway"
  | "call-center"
  | "quickbooks-online"
  | "quickbooks-desktop";

function hiddenSet(config: RestaurantConfig | null): Set<string> {
  if (!config?.hidden_ui_modules) return new Set();
  return new Set(
    config.hidden_ui_modules
      .split(",")
      .map((part) => part.trim().toLowerCase())
      .filter(Boolean),
  );
}

/**
 * Should this module be hidden from this tenant?
 *
 * Defaults to visible whenever config has not loaded yet. Showing a module for a
 * moment and then hiding it is a cosmetic blink; hiding the whole sidebar while
 * config loads and then popping it in is a worse experience, and defaulting to
 * hidden would make a slow config request look like a broken installation.
 */
export function isModuleHidden(
  config: RestaurantConfig | null,
  module: UiModule,
): boolean {
  return hiddenSet(config).has(module);
}
