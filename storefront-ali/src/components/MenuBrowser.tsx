import { useEffect, useMemo, useRef, useState } from "react";
import { fromPrice, itemImage, splitItemNumber } from "../data/menu";
import type { Category, MenuItem } from "../types";
import { imageThumb } from "../types";
import { formatGBP } from "../lib/money";
import { useMenu } from "../store/menu";
import ItemModal from "./ItemModal";

/**
 * The menu, built for Ali's ~195 numbered items on a phone.
 *
 * Compact rows with a small photo of the dish rather than big photo cards: at
 * this size a list you can scan beats cards you have to scroll past. The
 * printed item number gets its own column, because that is how phone
 * customers and the kitchen already refer to dishes ("two number 95s").
 *
 * Navigation, in order of how people actually find things:
 *   1. search: by name, or by the printed number
 *   2. a sticky category rail that follows the scroll (scroll-spy) and keeps
 *      the current category's chip in view
 *   3. plain scrolling
 */

/** Height of the sticky header (h-14) plus the rail, for scroll offsets. */
const SPY_TOP_OFFSET_PX = 130;

function matchesQuery(item: MenuItem, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const { number, title } = splitItemNumber(item.name);
  // A bare number is a lookup by printed menu number: "95" finds item 95 only.
  if (/^\d{1,3}$/.test(q)) return number === q;
  return (
    title.toLowerCase().includes(q) ||
    (item.description?.toLowerCase().includes(q) ?? false)
  );
}

function ItemRow({ item, onOpen }: { item: MenuItem; onOpen: () => void }) {
  const { number, title } = splitItemNumber(item.name);
  const multi = item.variants.length > 1;
  const img = itemImage(item);

  return (
    <li>
      <button
        onClick={onOpen}
        className="w-full flex items-start gap-3 px-3 py-3 text-left hover:bg-saffron-soft/60
                   focus-visible:outline focus-visible:outline-2 focus-visible:outline-flame
                   transition-colors"
      >
        <span
          className={`w-9 shrink-0 mt-0.5 rounded-md py-0.5 text-center text-xs font-bold tabular-nums
            ${number ? "bg-saffron-soft text-fg border border-saffron/50" : ""}`}
          aria-hidden={!number}
        >
          {number ?? ""}
        </span>

        <span className="flex-1 min-w-0">
          <span className="block font-semibold leading-snug">
            {number && <span className="sr-only">Number {number}, </span>}
            {title}
          </span>
          {item.description && (
            <span className="block text-sm text-fg/65 mt-0.5 line-clamp-2">
              {item.description}
            </span>
          )}
          {/* Sizes and their prices on the row itself (Single / Supper,
              10" / 12" / 14"), so nobody has to open an item to compare. */}
          {multi && (
            <span className="block text-xs text-fg/70 mt-1">
              {item.variants.map((v) => `${v.name} ${formatGBP(v.price)}`).join(" · ")}
            </span>
          )}
        </span>

        {img && (
          <img
            src={imageThumb(img)}
            alt=""
            width={56}
            height={56}
            loading="lazy"
            decoding="async"
            className="w-14 h-14 shrink-0 rounded-lg object-cover border border-paper-line"
          />
        )}

        <span className="shrink-0 text-right">
          {multi && (
            <span className="block text-[11px] uppercase tracking-wide text-fg/65">from</span>
          )}
          <span className="font-semibold text-flame tabular-nums">
            {formatGBP(fromPrice(item))}
          </span>
        </span>
      </button>
    </li>
  );
}

function CategorySection({
  category,
  items,
  onOpen,
}: {
  category: Category;
  items: MenuItem[];
  onOpen: (item: MenuItem) => void;
}) {
  return (
    <section
      id={`cat-${category.id}`}
      data-cat={category.id}
      className="pt-6"
      style={{ scrollMarginTop: SPY_TOP_OFFSET_PX }}
    >
      <h2 className="font-display text-xl uppercase tracking-wide text-flame mb-2">
        {category.name}
      </h2>
      <ul className="card divide-y divide-paper-line overflow-hidden">
        {items.map((item) => (
          <ItemRow key={item.id} item={item} onOpen={() => onOpen(item)} />
        ))}
      </ul>
    </section>
  );
}

function LoadingRows() {
  return (
    <div className="px-4 max-w-3xl mx-auto pt-6" aria-busy="true" aria-label="Loading menu">
      <div className="h-6 w-40 rounded bg-paper-line animate-pulse mb-3" />
      <div className="card divide-y divide-paper-line">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="flex items-center gap-3 px-3 py-4">
            <div className="w-9 h-5 rounded bg-paper-line animate-pulse" />
            <div className="flex-1 h-4 rounded bg-paper-line animate-pulse" />
            <div className="w-12 h-4 rounded bg-paper-line animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function MenuBrowser() {
  const [open, setOpen] = useState<MenuItem | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const categories = useMenu((s) => s.categories);
  const items = useMenu((s) => s.items);
  const source = useMenu((s) => s.source);

  const railRef = useRef<HTMLDivElement>(null);
  // While a tapped category is smooth-scrolling into place, the spy would
  // otherwise light up every category the page passes on the way.
  const spyPausedUntil = useRef(0);

  const searching = query.trim().length > 0;

  const byCategory = useMemo(() => {
    const map = new Map<string, MenuItem[]>();
    for (const item of items) {
      if (searching && !matchesQuery(item, query)) continue;
      const list = map.get(item.categoryId);
      if (list) list.push(item);
      else map.set(item.categoryId, [item]);
    }
    return map;
  }, [items, query, searching]);

  const visibleCategories = categories.filter((c) => (byCategory.get(c.id)?.length ?? 0) > 0);
  const matchCount = searching
    ? visibleCategories.reduce((n, c) => n + (byCategory.get(c.id)?.length ?? 0), 0)
    : 0;

  // Ids change identity when the live menu loads, so derive the highlighted
  // chip rather than trusting a stored one.
  const activeId =
    (active && categories.some((c) => c.id === active) ? active : categories[0]?.id) ?? "";

  // Scroll-spy: highlight the category whose heading is nearest the top.
  useEffect(() => {
    if (searching || categories.length === 0) return;
    const sections = Array.from(document.querySelectorAll<HTMLElement>("section[data-cat]"));
    if (sections.length === 0 || typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (Date.now() < spyPausedUntil.current) return;
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        const id = visible[0]?.target.getAttribute("data-cat");
        if (id) setActive(id);
      },
      { rootMargin: `-${SPY_TOP_OFFSET_PX}px 0px -60% 0px` },
    );
    sections.forEach((s) => observer.observe(s));
    return () => observer.disconnect();
  }, [categories, searching]);

  // Keep the active chip visible in the horizontally scrolling rail.
  useEffect(() => {
    const rail = railRef.current;
    const chip = rail?.querySelector<HTMLElement>(`[data-chip="${activeId}"]`);
    if (!rail || !chip) return;
    rail.scrollTo({
      left: chip.offsetLeft - rail.clientWidth / 2 + chip.clientWidth / 2,
      behavior: "smooth",
    });
  }, [activeId]);

  function jumpTo(id: string) {
    setActive(id);
    spyPausedUntil.current = Date.now() + 900;
    document.getElementById(`cat-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  if (items.length === 0) {
    // Still fetching: show the shape of a menu. Failed: the notice above the
    // menu (App.tsx) already explains and gives the phone number.
    return source === "loading" ? <LoadingRows /> : null;
  }

  return (
    <>
      <div className="px-4 pt-4 max-w-3xl mx-auto">
        <label className="sr-only" htmlFor="menu-search">
          Search the menu
        </label>
        <input
          id="menu-search"
          type="search"
          inputMode="search"
          enterKeyHint="search"
          autoComplete="off"
          placeholder="Search dishes, or type a menu number"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="field"
        />
      </div>

      {/* Sticky category rail. Horizontally scrollable on phones. Hidden
          while searching: results are already filtered to what matches. */}
      {!searching && (
        <nav
          aria-label="Menu sections"
          className="sticky top-14 z-30 mt-3 bg-paper/95 backdrop-blur border-b border-paper-line"
        >
          <div
            ref={railRef}
            className="flex gap-2 overflow-x-auto px-4 py-2.5 max-w-3xl mx-auto
                       [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          >
            {visibleCategories.map((c) => (
              <button
                key={c.id}
                data-chip={c.id}
                onClick={() => jumpTo(c.id)}
                aria-current={activeId === c.id ? "true" : undefined}
                className={`whitespace-nowrap rounded-full px-4 min-h-[40px] text-sm font-semibold transition-colors
                  ${
                    activeId === c.id
                      ? "bg-flame text-white"
                      : "bg-paper-soft border border-paper-line text-fg/80 hover:text-fg"
                  }`}
              >
                {c.name}
              </button>
            ))}
          </div>
        </nav>
      )}

      <div className="px-4 pb-32 max-w-3xl mx-auto">
        {searching && (
          <p className="pt-4 text-sm text-fg/70" aria-live="polite">
            {matchCount === 0
              ? `Nothing matches "${query.trim()}".`
              : `${matchCount} ${matchCount === 1 ? "dish" : "dishes"} found.`}{" "}
            <button onClick={() => setQuery("")} className="font-semibold text-flame underline">
              Clear search
            </button>
          </p>
        )}

        {visibleCategories.map((cat) => (
          <CategorySection
            key={cat.id}
            category={cat}
            items={byCategory.get(cat.id) ?? []}
            onOpen={setOpen}
          />
        ))}
      </div>

      {open && (
        <ItemModal
          key={open.id}
          item={open}
          // `categories` and `items` come from the same source, so this
          // resolves even though ids are database UUIDs.
          categoryName={categories.find((c) => c.id === open.categoryId)?.name ?? ""}
          onClose={() => setOpen(null)}
        />
      )}
    </>
  );
}
