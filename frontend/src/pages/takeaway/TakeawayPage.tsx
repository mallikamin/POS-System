import { useCallback, useEffect, useLayoutEffect } from "react";
import { MenuGrid } from "@/components/pos/MenuGrid";
import { CartPanel } from "@/components/pos/CartPanel";
import { useCartStore } from "@/stores/cartStore";
import { useUIStore } from "@/stores/uiStore";
import { OrderTicker } from "@/components/pos/OrderTicker";
import type { CartItem } from "@/types/cart";

function TakeawayPage() {
  const addItem = useCartStore((s) => s.addItem);
  const setActiveCart = useCartStore((s) => s.setActiveCart);
  const setCurrentChannel = useUIStore((s) => s.setCurrentChannel);

  useEffect(() => {
    setCurrentChannel("takeaway");
  }, [setCurrentChannel]);

  useLayoutEffect(() => {
    setActiveCart("takeaway");
  }, [setActiveCart]);

  const handleAddToCart = useCallback(
    (item: CartItem) => {
      addItem(item.menuItem, item.modifiers);
    },
    [addItem]
  );

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-1 min-h-0">
        {/* Left: Menu grid */}
        <div className="flex-1 min-w-0 p-4">
          <MenuGrid onAddToCart={handleAddToCart} />
        </div>

        {/* Right: Cart panel */}
        <div className="w-80 shrink-0 border-l border-secondary-200">
          <CartPanel />
        </div>
      </div>

      {/* Bottom: Live order ticker */}
      <OrderTicker />
    </div>
  );
}

export default TakeawayPage;
