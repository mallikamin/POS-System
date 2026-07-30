import { useState } from "react";
import { fromPrice, isMealItem, itemImage, siblingOf } from "../data/menu";
import type { MenuItem } from "../types";
import { imageThumb } from "../types";
import { formatGBP } from "../lib/money";
import { useMenu } from "../store/menu";
import ItemModal from "./ItemModal";

/**
 * Square media tile on the left of each card.
 *
 * Items with no photo are a deliberate state, not a missing asset, so this
 * renders a branded monogram tile rather than a broken-image icon or an empty
 * gap. Keeping the same footprint either way stops the list jumping around.
 */
function ItemThumb({ item }: { item: MenuItem }) {
  const img = itemImage(item);

  if (!img) {
    return (
      <div
        aria-hidden
        className="w-20 h-20 shrink-0 rounded-lg bg-gradient-to-br from-flame/25 to-ember/10
                   border border-ink-line grid place-items-center"
      >
        <span className="font-display text-xl text-flame-light/70">
          {item.name.charAt(0)}
        </span>
      </div>
    );
  }

  return (
    <img
      src={imageThumb(img)}
      alt=""
      width={80}
      height={80}
      loading="lazy"
      decoding="async"
      className="w-20 h-20 shrink-0 rounded-lg object-cover border border-ink-line"
    />
  );
}

export default function MenuBrowser() {
  const [open, setOpen] = useState<MenuItem | null>(null);
  const [active, setActive] = useState<string | null>(null);

  const categories = useMenu((s) => s.categories);
  const items = useMenu((s) => s.items);

  // Category ids change identity when the live menu replaces the hardcoded one
  // (slugs become UUIDs), so a remembered selection can stop existing. Derive
  // the highlighted rail button instead of storing it, and fall back to the
  // first category whenever the stored one is no longer on the menu.
  const activeId =
    (active && categories.some((c) => c.id === active) ? active : categories[0]?.id) ??
    "";

  function jumpTo(id: string) {
    setActive(id);
    document.getElementById(`cat-${id}`)?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  return (
    <>
      {/* Sticky category rail. Horizontally scrollable on phones. */}
      <nav className="sticky top-[57px] z-30 bg-ink/95 backdrop-blur border-b border-ink-line">
        <div className="flex gap-2 overflow-x-auto px-4 py-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {categories.map((c) => (
            <button
              key={c.id}
              onClick={() => jumpTo(c.id)}
              className={`whitespace-nowrap rounded-full px-4 py-2 text-sm font-semibold transition-colors
                ${
                  activeId === c.id
                    ? "bg-flame text-white"
                    : "border border-ink-line text-cream/70 hover:text-cream"
                }`}
            >
              {c.name}
            </button>
          ))}
        </div>
      </nav>

      <div className="px-4 pb-32 max-w-3xl mx-auto">
        {categories.map((cat) => {
          const inCategory = items.filter((i) => i.categoryId === cat.id);
          if (inCategory.length === 0) return null;
          return (
            <section key={cat.id} id={`cat-${cat.id}`} className="pt-8 scroll-mt-32">
              <h2 className="font-display text-2xl mb-4">{cat.name}</h2>
              <div className="grid gap-3">
                {inCategory.map((item) => {
                  const multi = item.variants.length > 1;
                  return (
                    <button
                      key={item.id}
                      onClick={() => setOpen(item)}
                      className="card p-4 text-left hover:border-flame/50 transition-colors"
                    >
                      <div className="flex items-start gap-3">
                        <ItemThumb item={item} />
                        <div className="flex-1 min-w-0 flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <h3 className="font-semibold leading-snug">{item.name}</h3>
                          {item.description && (
                            <p className="text-sm text-cream/55 mt-1 line-clamp-2">
                              {item.description}
                            </p>
                          )}
                          {isMealItem(item) && (
                            <span className="inline-block mt-2 text-[11px] font-semibold uppercase tracking-wide text-ember">
                              Meal Deal · includes a drink &amp; chips
                            </span>
                          )}
                        </div>
                        <div className="text-right shrink-0">
                          {multi && (
                            <span className="block text-[11px] uppercase tracking-wide text-cream/40">
                              from
                            </span>
                          )}
                          <span className="font-semibold text-flame-light">
                            {formatGBP(fromPrice(item))}
                          </span>
                        </div>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </section>
          );
        })}
      </div>

      {open && (
        <ItemModal
          key={open.id}
          item={open}
          sibling={siblingOf(open, items)}
          onSwitch={setOpen}
          onClose={() => setOpen(null)}
        />
      )}
    </>
  );
}
