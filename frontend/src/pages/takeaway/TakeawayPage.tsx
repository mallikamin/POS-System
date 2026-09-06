import { useCallback, useEffect, useLayoutEffect } from "react";
import { MenuGrid } from "@/components/pos/MenuGrid";
import { CartPanel } from "@/components/pos/CartPanel";
import { MobileCartSheet } from "@/components/pos/MobileCartSheet";
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
        {/* Left: Menu grid.
            The bottom padding below `lg` clears the fixed "View order" bar
            (M12); without it the last row of menu tiles sits under it. */}
        <div className="min-w-0 flex-1 p-3 pb-24 sm:p-4 lg:pb-4">
          <MenuGrid onAddToCart={handleAddToCart} />
        </div>

        {/* Right: the cart. A column at `lg` and up, a bottom sheet below it.
            This page is the one Martin photographed: a fixed `w-80` column
            beside the menu left a 360px phone with no usable menu at all. */}
        <MobileCartSheet>
          <CartPanel />
        </MobileCartSheet>
      </div>

      {/* Bottom: Live order ticker */}
      <OrderTicker orderType="takeaway" />
    </div>
  );
}

export default TakeawayPage;
