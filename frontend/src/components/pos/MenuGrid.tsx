import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatPKR } from "@/utils/currency";
import { useMenuStore } from "@/stores/menuStore";
import { ModifierModal } from "./ModifierModal";
import type { MenuItem } from "@/types/menu";
import type { SelectedModifier, CartItem } from "@/types/cart";

interface MenuGridProps {
  onAddToCart: (item: CartItem) => void;
}

export function MenuGrid({ onAddToCart }: MenuGridProps) {
  const { categories, isLoading, error, loadMenu } = useMenuStore();
  const [activeCategoryIndex, setActiveCategoryIndex] = useState(0);
  const [modifierItem, setModifierItem] = useState<MenuItem | null>(null);

  useEffect(() => {
    loadMenu();
  }, [loadMenu]);

  function handleItemClick(item: MenuItem) {
    if (item.modifier_groups && item.modifier_groups.length > 0) {
      setModifierItem(item);
    } else {
      onAddToCart({
        menuItem: item,
        quantity: 1,
        modifiers: [],
      });
    }
  }

  function handleModifierConfirm(selectedModifiers: SelectedModifier[]) {
    if (!modifierItem) return;
    onAddToCart({
      menuItem: modifierItem,
      quantity: 1,
      modifiers: selectedModifiers,
    });
    setModifierItem(null);
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-20">
        <p className="text-danger-600">{error}</p>
        <button
          onClick={() => loadMenu()}
          className="text-sm text-primary-600 underline"
        >
          Retry
        </button>
      </div>
    );
  }

  if (categories.length === 0) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-secondary-400">No menu items available</p>
      </div>
    );
  }

  const activeCategory = categories[activeCategoryIndex];
  const availableItems = activeCategory?.items?.filter((i) => i.is_available) || [];

  return (
    <div className="flex h-full flex-col">
      {/* Category tabs - horizontal scrollable */}
      <div className="flex gap-2 overflow-x-auto border-b border-secondary-200 pb-2 scrollbar-hide">
        {categories.map((cat, idx) => (
          <button
            key={cat.id}
            onClick={() => setActiveCategoryIndex(idx)}
            className={cn(
              "flex-shrink-0 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors min-h-touch-lg",
              idx === activeCategoryIndex
                ? "bg-primary-600 text-white shadow-sm"
                : "bg-secondary-100 text-secondary-600 hover:bg-secondary-200"
            )}
          >
            {cat.icon && <span className="mr-1.5">{cat.icon}</span>}
            {cat.name}
          </button>
        ))}
      </div>

      {/* Items grid */}
      <div className="flex-1 overflow-y-auto pt-3">
        {availableItems.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <p className="text-secondary-400">
              No items available in this category
            </p>
          </div>
        ) : (
          /*
            Auto-fill columns of ~150-200 px with a 4:3 photograph on each card,
            the layout from the approved storefront mockup. The previous fixed
            2/3/4-column grid gave a 370 px wide card a 96 px photo strip, which
            showed only a band through the middle of a square image.
          */
          <div className="grid gap-2 grid-cols-[repeat(auto-fill,minmax(150px,1fr))]">
            {availableItems.map((item) => (
              <button
                key={item.id}
                onClick={() => handleItemClick(item)}
                className="flex flex-col rounded-xl border border-secondary-200 bg-white overflow-hidden text-center transition-all hover:border-primary-300 hover:shadow-md active:scale-[0.97]"
              >
                <div className="relative w-full aspect-[4/3] bg-secondary-100">
                  {item.image_url ? (
                    <img
                      src={item.image_url}
                      alt={item.name}
                      className="h-full w-full object-cover"
                      loading="lazy"
                      onError={(e) => {
                        const img = e.target as HTMLImageElement;
                        img.style.display = "none";
                        img.parentElement!.classList.add("flex", "items-center", "justify-center");
                        const span = document.createElement("span");
                        span.className = "text-3xl";
                        span.textContent = "\uD83C\uDF7D\uFE0F";
                        img.parentElement!.appendChild(span);
                      }}
                    />
                  ) : (
                    <span className="flex h-full w-full items-center justify-center text-3xl">🍽️</span>
                  )}
                </div>
                <div className="flex flex-col items-center gap-1 p-2.5">
                  <span className="text-sm font-medium text-secondary-900 line-clamp-2 leading-tight">
                    {item.name}
                  </span>
                  <span className="text-sm font-bold text-primary-600">
                    {formatPKR(item.price)}
                  </span>
                  {item.modifier_groups && item.modifier_groups.length > 0 && (
                    <span className="text-[10px] text-secondary-400">
                      + options
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Modifier Modal */}
      <ModifierModal
        item={modifierItem}
        open={!!modifierItem}
        onClose={() => setModifierItem(null)}
        onConfirm={handleModifierConfirm}
      />
    </div>
  );
}
