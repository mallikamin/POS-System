import { useMemo, useState } from "react";
import type { MenuItem, ModifierGroup, ModifierOption, Variant } from "../types";
import { imageHero } from "../types";
import { exclusionsFor, itemImage, splitItemNumber } from "../data/menu";
import { formatGBP } from "../lib/money";
import { unitPriceOf, useCart } from "../store/cart";

interface Props {
  item: MenuItem;
  /** Display name of item's category, resolved by the caller. See `exclusionsFor`. */
  categoryName: string;
  onClose: () => void;
}

/**
 * A pick-one group with more options than this renders as a native picker
 * instead of a list of buttons.
 */
const LONG_LIST = 8;

/**
 * The instruction shown under a modifier group's name.
 *
 * Ali's menu leans on these: "choose 3 curries" on a set meal is a group with
 * min = max = 3, a protein pick is min = max = 1, extra toppings are 0..N.
 */
function groupHint(group: ModifierGroup): string {
  const { min, max } = group;
  if (min > 0 && min === max) return max === 1 ? "Choose 1" : `Choose ${max}`;
  if (min > 0) return `Choose ${min} to ${max}`;
  return max === 1 ? "Optional, choose 1" : `Optional, up to ${max}`;
}

/**
 * Configure one item: pick a variant (size / protein), then any modifiers.
 *
 * Variant prices are absolute (Single £8.50 / Supper £12.95), so selecting a
 * variant REPLACES the base price. Modifier deltas are then added on top.
 */
export default function ItemModal({ item, categoryName, onClose }: Props) {
  const add = useCart((s) => s.add);
  const { number, title } = splitItemNumber(item.name);

  const [variant, setVariant] = useState<Variant>(item.variants[0]!);
  const [selected, setSelected] = useState<Record<string, string[]>>({});
  const [quantity, setQuantity] = useState(1);

  /** "Leave it out" ticks. Free, and only offered where salad and sauce exist. */
  const [excluded, setExcluded] = useState<string[]>([]);
  const excludable = exclusionsFor(categoryName);

  /**
   * Free-text instruction for this item. Capped well under the 300-char
   * per-line limit the server enforces so it can never fail at submit time.
   */
  const [note, setNote] = useState("");
  const NOTE_MAX = 120;

  /** null for items with no photo (all of them, until photos arrive). */
  const hero = itemImage(item);

  const chosenOptions = useMemo<ModifierOption[]>(() => {
    const out: ModifierOption[] = [];
    for (const group of item.modifierGroups) {
      const ids = selected[group.id] ?? [];
      for (const id of ids) {
        const opt = group.options.find((o) => o.id === id);
        if (opt) out.push(opt);
      }
    }
    return out;
  }, [item.modifierGroups, selected]);

  /** Groups with min > 0 must have at least min selections before adding. */
  const requiredGroups = item.modifierGroups.filter((g) => g.min > 0);
  const unmet = requiredGroups.filter((g) => (selected[g.id]?.length ?? 0) < g.min);
  const firstUnmet = unmet[0];

  /** Set once the customer taps Add with choices missing; highlights them. */
  const [attempted, setAttempted] = useState(false);

  /** Take the customer to the first required group they have not finished. */
  function showFirstUnmet() {
    setAttempted(true);
    if (!firstUnmet) return;
    document
      .getElementById(`grp-${firstUnmet.id}`)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
    // Focus a picker directly so the phone opens its list straight away.
    document.getElementById(`sel-${firstUnmet.id}`)?.focus({ preventScroll: true });
  }

  const unitPrice = unitPriceOf(variant, chosenOptions);

  function toggle(group: ModifierGroup, optionId: string) {
    setSelected((prev) => {
      const current = prev[group.id] ?? [];
      if (current.includes(optionId)) {
        return { ...prev, [group.id]: current.filter((id) => id !== optionId) };
      }
      // Single-select: tapping another option replaces the choice (radio).
      if (group.max === 1) return { ...prev, [group.id]: [optionId] };
      // Multi-select at its limit: refuse rather than silently dropping an
      // earlier pick. Someone choosing 3 curries for a set meal must never
      // lose their first curry without noticing. The option is also shown
      // disabled, so this branch is a guard, not the UX.
      if (current.length >= group.max) return prev;
      return { ...prev, [group.id]: [...current, optionId] };
    });
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full sm:max-w-lg max-h-[92vh] flex flex-col bg-paper-soft border border-paper-line
                   rounded-t-3xl sm:rounded-3xl overflow-hidden shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={item.name}
      >
        {hero && (
          <img
            src={imageHero(hero)}
            alt=""
            width={720}
            height={480}
            decoding="async"
            className="w-full h-40 sm:h-48 object-cover shrink-0"
          />
        )}

        <header className="flex items-start gap-3 p-5 border-b border-paper-line">
          <div className="flex-1">
            {number && (
              <span className="inline-block mb-1 rounded-md bg-saffron-soft border border-saffron/50 px-2 py-0.5 text-xs font-bold tabular-nums">
                No. {number}
              </span>
            )}
            <h2 className="font-display text-xl leading-tight uppercase">{title}</h2>
            {item.description && (
              <p className="text-sm text-fg/70 mt-1">{item.description}</p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="w-10 h-10 rounded-full border border-paper-line text-fg/70 hover:text-fg shrink-0"
          >
            ✕
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {/* Variants: only shown when there is a real choice. On Ali's menu
              this is a size (Single / Supper, 10" / 12" / 14") or a priced
              protein column (Chicken or Lamb / King Prawn / Mix Veg). */}
          {item.variants.length > 1 && (
            <section>
              <h3 className="label">Choose an option</h3>
              <div className="space-y-2" role="radiogroup" aria-label="Choose an option">
                {item.variants.map((v) => (
                  <button
                    key={v.id}
                    role="radio"
                    aria-checked={variant.id === v.id}
                    onClick={() => setVariant(v)}
                    className={`w-full flex items-center justify-between rounded-xl border px-4 py-3 text-left
                      ${
                        variant.id === v.id
                          ? "border-flame bg-flame/10"
                          : "border-paper-line hover:border-fg/30"
                      }`}
                  >
                    <span className="font-medium">{v.name}</span>
                    <span className="text-fg/75 tabular-nums">{formatGBP(v.price)}</span>
                  </button>
                ))}
              </div>
            </section>
          )}

          {requiredGroups.length > 1 && (
            <p
              className={`rounded-xl px-4 py-2.5 text-sm font-semibold ${
                unmet.length === 0
                  ? "bg-emerald-600/10 text-emerald-800"
                  : "bg-saffron-soft text-fg"
              }`}
              aria-live="polite"
            >
              Required choices: {requiredGroups.length - unmet.length} of{" "}
              {requiredGroups.length} done
            </p>
          )}

          {item.modifierGroups.map((group) => {
            const picks = selected[group.id] ?? [];
            const full = group.max > 1 && picks.length >= group.max;
            const required = group.min > 0;
            const satisfied = picks.length >= group.min;
            const flagged = attempted && required && !satisfied;

            // One pick from a long list (a set meal's "choose dish" has ~40
            // curries): a native picker. Compact, uses the phone's own wheel or
            // list, and keeps a 12-group set meal to 12 rows instead of ~480
            // buttons.
            if (group.max === 1 && group.options.length > LONG_LIST) {
              const value = picks[0] ?? "";
              return (
                <section key={group.id} id={`grp-${group.id}`} style={{ scrollMarginTop: 16 }}>
                  <label htmlFor={`sel-${group.id}`} className="label">
                    {group.name}
                    {required ? (
                      <span className="text-flame ml-1">*</span>
                    ) : (
                      <span className="ml-1 normal-case tracking-normal font-normal">(optional)</span>
                    )}
                  </label>
                  <select
                    id={`sel-${group.id}`}
                    value={value}
                    onChange={(e) =>
                      setSelected((prev) => ({
                        ...prev,
                        [group.id]: e.target.value ? [e.target.value] : [],
                      }))
                    }
                    aria-invalid={flagged}
                    className={`field ${
                      flagged ? "border-flame ring-2 ring-flame/30" : value ? "border-flame/60" : ""
                    }`}
                  >
                    <option value="">{required ? "Choose…" : "None"}</option>
                    {group.options.map((opt) => (
                      <option key={opt.id} value={opt.id}>
                        {opt.name}
                        {opt.priceDelta > 0 ? ` (+${formatGBP(opt.priceDelta)})` : ""}
                      </option>
                    ))}
                  </select>
                </section>
              );
            }

            return (
              <section key={group.id} id={`grp-${group.id}`} style={{ scrollMarginTop: 16 }}>
                <div className="flex items-baseline justify-between gap-3 mb-1.5">
                  <h3 className="label mb-0">
                    {group.name}
                    {required && <span className="text-flame ml-1">*</span>}
                  </h3>
                  {group.max > 1 && (
                    <span
                      className={`text-xs font-semibold tabular-nums ${
                        required && !satisfied ? "text-flame" : "text-fg/70"
                      }`}
                      aria-live="polite"
                    >
                      {picks.length} of {group.max}
                    </span>
                  )}
                </div>
                <p className={`text-xs mb-2 ${flagged ? "text-flame font-semibold" : "text-fg/70"}`}>
                  {groupHint(group)}
                </p>
                <div className="space-y-2">
                  {group.options.map((opt) => {
                    const on = picks.includes(opt.id);
                    const locked = full && !on;
                    return (
                      <button
                        key={opt.id}
                        onClick={() => toggle(group, opt.id)}
                        disabled={locked}
                        aria-pressed={on}
                        className={`w-full flex items-center justify-between gap-3 rounded-xl border px-4 py-3 text-left
                          disabled:opacity-40 disabled:cursor-not-allowed
                          ${on ? "border-flame bg-flame/10" : "border-paper-line hover:border-fg/30"}`}
                      >
                        <span className="flex items-center gap-3">
                          <span
                            aria-hidden
                            className={`grid place-items-center w-5 h-5 shrink-0 border-2 text-[11px] font-bold
                              ${group.max === 1 ? "rounded-full" : "rounded"}
                              ${on ? "border-flame bg-flame text-white" : "border-fg/30"}`}
                          >
                            {on ? "✓" : ""}
                          </span>
                          <span className="font-medium">{opt.name}</span>
                        </span>
                        {opt.priceDelta > 0 && (
                          <span className="text-fg/75 tabular-nums">
                            +{formatGBP(opt.priceDelta)}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </section>
            );
          })}

          {excludable.length > 0 && (
            <section>
              <h3 className="label">Anything to leave out?</h3>
              <p className="text-sm text-fg/70 mb-2">
                Optional. Tick anything you don't want and we'll make it without.
              </p>
              <div className="grid grid-cols-2 gap-2">
                {excludable.map((what) => {
                  const on = excluded.includes(what);
                  return (
                    <button
                      key={what}
                      type="button"
                      aria-pressed={on}
                      onClick={() =>
                        setExcluded((prev) =>
                          prev.includes(what) ? prev.filter((x) => x !== what) : [...prev, what],
                        )
                      }
                      className={`rounded-xl border px-3 py-3 text-left text-sm font-medium
                        ${on ? "border-flame bg-flame/10" : "border-paper-line hover:border-fg/30"}`}
                    >
                      {what}
                    </button>
                  );
                })}
              </div>
            </section>
          )}

          <section>
            <h3 className="label">Anything else?</h3>
            <p className="text-sm text-fg/70 mb-2">Optional, e.g. extra spicy, well done.</p>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={NOTE_MAX}
              rows={2}
              placeholder="A note for the kitchen about this item…"
              className="field resize-none"
            />
          </section>
        </div>

        <footer className="p-5 border-t border-paper-line space-y-3">
          <div className="flex items-center gap-3">
            <div className="flex items-center rounded-xl border border-paper-line">
              <button
                onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                className="w-12 h-12 text-xl"
                aria-label="Decrease quantity"
              >
                −
              </button>
              <span className="w-10 text-center font-semibold" aria-live="polite">
                {quantity}
              </span>
              <button
                onClick={() => setQuantity((q) => q + 1)}
                className="w-12 h-12 text-xl"
                aria-label="Increase quantity"
              >
                +
              </button>
            </div>
            {/* With choices missing this never adds. It is not `disabled`,
                because a dead button on a 12-choice set meal leaves the
                customer hunting for what they missed; instead it takes them
                straight to it. */}
            <button
              aria-disabled={firstUnmet !== undefined}
              onClick={() => {
                if (firstUnmet) {
                  showFirstUnmet();
                  return;
                }
                add(item, variant, chosenOptions, quantity, excluded, note);
                onClose();
              }}
              className={`btn-primary tap flex-1 h-12 min-w-0 ${
                firstUnmet ? "opacity-60" : ""
              }`}
            >
              <span className="truncate">
                {firstUnmet
                  ? unmet.length === 1
                    ? `Choose: ${firstUnmet.name}`
                    : `${unmet.length} choices left`
                  : `Add · ${formatGBP(unitPrice * quantity)}`}
              </span>
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
