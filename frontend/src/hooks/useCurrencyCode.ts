import { useConfigStore } from "@/stores/configStore";
import { getActiveCurrency } from "@/utils/currency";

/**
 * The signed-in tenant's currency code, for use in LABELS ("Amount (AED)").
 *
 * Why a hook rather than `getActiveCurrency()` directly: `activeCode` in
 * `utils/currency` is a module-level global set as a side effect of the config
 * fetch. It is fine for formatting inside a render that is already reacting to
 * something else, but it is invisible to React, so a component that reads it
 * once will happily keep displaying a stale code forever. Reading `config`
 * from the store makes the label re-render the moment the real currency lands.
 *
 * Found in UAT on 2026-08-28 (F17): seventeen labels across seven files said
 * "(PKR)" as literal text — on the payment screens, the menu editor, the
 * ingredient editor and Settings' discount thresholds. A UAE client was being
 * asked to type a price in Pakistani rupees, and a UK one had been for months.
 *
 * Falls back to the module global so a component outside a loaded config (a
 * deep-linked screen mid-fetch) still renders something sane rather than
 * an empty pair of brackets.
 */
export function useCurrencyCode(): string {
  const config = useConfigStore((s) => s.config);
  return config?.currency ?? getActiveCurrency();
}
