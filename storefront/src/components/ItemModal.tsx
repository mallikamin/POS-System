import { useMemo, useState } from "react";
import type { MenuItem, ModifierOption, Variant } from "../types";
import { imageHero } from "../types";
import { exclusionsFor, isMealItem, itemImage } from "../data/menu";
import { formatGBP } from "../lib/money";
import { unitPriceOf, useCart } from "../store/cart";

interface Props {
  item: MenuItem;
  /** Display name of item's category, resolved by the caller — see `exclusionsFor`. */
  categoryName: string;
  onClose: () => void;
  /** The Meal/Solo counterpart of `item`, if the menu has one. */
  sibling?: MenuItem;
  /** Swap the modal to show `sibling` instead, without closing it. */
  onSwitch: (item: MenuItem) => void;
}

/**
 * Configure one item: pick a size/base variant, then any modifiers.
 *
 * Variant prices are absolute (2pc £4.99 / 4pc £7.99), so selecting a variant
 * REPLACES the base price. Modifier deltas are then added on top.
 */
export default function ItemModal({ item, categoryName, onClose, sibling, onSwitch }: Props) {
  const add = useCart((s) => s.add);

  const [variant, setVariant] = useState<Variant>(item.variants[0]!);
  const [selected, setSelected] = useState<Record<string, string[]>>({});
  const [quantity, setQuantity] = useState(1);

  /** "Leave it out" ticks. Free, and only offered where salad and sauce exist. */
  const [excluded, setExcluded] = useState<string[]>([]);
  const excludable = exclusionsFor(categoryName);

  /** null for items that deliberately have no photo — the modal just omits it. */
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

  /** Groups with min>0 must have at least min selections before adding. */
  const unmet = item.modifierGroups.filter(
    (g) => g.min > 0 && (selected[g.id]?.length ?? 0) < g.min,
  );

  const unitPrice = unitPriceOf(variant, chosenOptions);

  function toggle(groupId: string, optionId: string, max: number) {
    setSelected((prev) => {
      const current = prev[groupId] ?? [];
      if (current.includes(optionId)) {
        return { ...prev, [groupId]: current.filter((id) => id !== optionId) };
      }
      // Single-select groups replace; multi-select append up to max.
      const next = max === 1 ? [optionId] : [...current, optionId].slice(-max);
      return { ...prev, [groupId]: next };
    });
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/70 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full sm:max-w-lg max-h-[92vh] flex flex-col bg-ink-soft border border-ink-line
                   rounded-t-3xl sm:rounded-3xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={item.name}
      >
        {/* Hero. Decorative (alt=""): the name is announced by the heading
            below, so alt text here would just repeat it. Only fetched when a
            modal actually opens, which is why heroes are a separate size from
            the list thumbnails. */}
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

        <header className="flex items-start gap-3 p-5 border-b border-ink-line">
          <div className="flex-1">
            <h2 className="font-display text-xl leading-tight">{item.name}</h2>
            {item.description && (
              <p className="text-sm text-cream/60 mt-1">{item.description}</p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="w-9 h-9 rounded-full border border-ink-line text-cream/60 hover:text-cream shrink-0"
          >
            ✕
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {/* Cross-link to the other half of a Solo/Meal pair. Solo items list
              first in every category, so without this a customer looking at
              one has no reason to suspect a Meal version is further down. */}
          {sibling && (
            <button
              type="button"
              onClick={() => onSwitch(sibling)}
              className="w-full flex items-center justify-between gap-3 rounded-xl border border-ember/40
                         bg-ember/10 px-4 py-3 text-left hover:border-ember/70 transition-colors"
            >
              <span className="text-sm font-semibold text-ember">
                {isMealItem(item)
                  ? "Prefer it on its own? See the Solo version"
                  : "Make it a meal — adds a drink & chips upgrade"}
              </span>
              <span className="text-sm font-semibold text-ember shrink-0">
                {isMealItem(item) ? "View Solo ›" : "View Meal ›"}
              </span>
            </button>
          )}

          {/* Variants — only shown when there is a real choice. */}
          {item.variants.length > 1 && (
            <section>
              <h3 className="label">Choose size</h3>
              <div className="space-y-2">
                {item.variants.map((v) => (
                  <button
                    key={v.id}
                    onClick={() => setVariant(v)}
                    className={`w-full flex items-center justify-between rounded-xl border px-4 py-3 text-left
                      ${
                        variant.id === v.id
                          ? "border-flame bg-flame/10"
                          : "border-ink-line hover:border-cream/25"
                      }`}
                  >
                    <span className="font-medium">{v.name}</span>
                    <span className="text-cream/75">{formatGBP(v.price)}</span>
                  </button>
                ))}
              </div>
            </section>
          )}

          {item.modifierGroups.map((group) => (
            <section key={group.id}>
              <h3 className="label">
                {group.name}
                {group.min > 0 && <span className="text-flame ml-1">*</span>}
              </h3>
              <div className="space-y-2">
                {group.options.map((opt) => {
                  const on = (selected[group.id] ?? []).includes(opt.id);
                  return (
                    <button
                      key={opt.id}
                      onClick={() => toggle(group.id, opt.id, group.max)}
                      className={`w-full flex items-center justify-between rounded-xl border px-4 py-3 text-left
                        ${on ? "border-flame bg-flame/10" : "border-ink-line hover:border-cream/25"}`}
                    >
                      <span className="font-medium">{opt.name}</span>
                      {opt.priceDelta > 0 && (
                        <span className="text-cream/75">
                          +{formatGBP(opt.priceDelta)}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </section>
          ))}

          {excludable.length > 0 && (
            <section>
              <h3 className="label">Anything to leave out?</h3>
              <p className="text-sm text-cream/50 mb-2">
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
                          prev.includes(what)
                            ? prev.filter((x) => x !== what)
                            : [...prev, what],
                        )
                      }
                      className={`rounded-xl border px-3 py-3 text-left text-sm font-medium
                        ${on ? "border-flame bg-flame/10" : "border-ink-line hover:border-cream/25"}`}
                    >
                      {what}
                    </button>
                  );
                })}
              </div>
            </section>
          )}
        </div>

        <footer className="p-5 border-t border-ink-line space-y-3">
          <div className="flex items-center gap-3">
            <div className="flex items-center rounded-xl border border-ink-line">
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
            <button
              disabled={unmet.length > 0}
              onClick={() => {
                add(item, variant, chosenOptions, quantity, excluded);
                onClose();
              }}
              className="btn-primary tap flex-1 h-12"
            >
              {unmet.length > 0
                ? `Choose ${unmet[0]!.name.toLowerCase()}`
                : `Add · ${formatGBP(unitPrice * quantity)}`}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
