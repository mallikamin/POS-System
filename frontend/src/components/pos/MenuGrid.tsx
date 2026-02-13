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
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            {availableItems.map((item) => (
              <button
                key={item.id}
                onClick={() => handleItemClick(item)}
                className="flex flex-col rounded-xl border border-secondary-200 bg-white overflow-hidden text-center transition-all hover:border-primary-300 hover:shadow-md active:scale-[0.97]"
              >
                {item.image_url ? (
                  <div className="relative w-full h-24 bg-secondary-100">
                    <img
                      src={item.image_url}
                      alt={item.name}
                      className="h-full w-full object-cover"
                      loading="lazy"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = "none";
                      }}
                    />
                  </div>
                ) : (
                  <div className="flex h-16 w-full items-center justify-center bg-secondary-50 text-2xl">
                    🍽️
                  </div>
                )}
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
