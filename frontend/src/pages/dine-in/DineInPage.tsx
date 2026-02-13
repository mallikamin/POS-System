import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { MenuGrid } from "@/components/pos/MenuGrid";
import { CartPanel } from "@/components/pos/CartPanel";
import { FloorGrid } from "@/components/pos/FloorGrid";
import { useCartStore } from "@/stores/cartStore";
import { useFloorStore } from "@/stores/floorStore";
import { useUIStore } from "@/stores/uiStore";
import { OrderTicker } from "@/components/pos/OrderTicker";
import type { CartItem } from "@/types/cart";

function DineInPage() {
  const addItem = useCartStore((s) => s.addItem);
  const setActiveCart = useCartStore((s) => s.setActiveCart);
  const selectedTableId = useFloorStore((s) => s.selectedTableId);
  const setCurrentChannel = useUIStore((s) => s.setCurrentChannel);

  useEffect(() => {
    setCurrentChannel("dine_in");
  }, [setCurrentChannel]);

  // Track whether a table is selected (show menu or prompt)
  const [tableSelected, setTableSelected] = useState(false);

  // When table is selected, switch cart to that table's UUID
  function handleTableSelect(tableId: string) {
    setActiveCart(`table-${tableId}`);
    setTableSelected(true);
  }

  // Fallback: if no table selected, use a default cart for browsing
  useLayoutEffect(() => {
    if (!selectedTableId) {
      setActiveCart("dine-in-default");
    }
  }, [selectedTableId, setActiveCart]);

  const handleAddToCart = useCallback(
    (item: CartItem) => {
      addItem(item.menuItem, item.modifiers);
    },
    [addItem]
  );

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-1 min-h-0">
        {/* Left: Floor plan with table selection */}
        <div className="w-64 shrink-0 border-r border-secondary-200 bg-secondary-50">
          <FloorGrid onTableSelect={handleTableSelect} />
        </div>

        {/* Center: Menu grid */}
        <div className="flex-1 min-w-0 p-4">
          {tableSelected ? (
            <MenuGrid onAddToCart={handleAddToCart} />
          ) : (
            <div className="flex flex-col items-center justify-center h-full gap-3">
              <p className="text-lg font-medium text-secondary-400">
                Select a table to start ordering
              </p>
              <p className="text-sm text-secondary-300">
                Choose a table from the floor plan on the left
              </p>
            </div>
          )}
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

export default DineInPage;
