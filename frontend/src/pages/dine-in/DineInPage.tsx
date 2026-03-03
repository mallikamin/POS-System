import { useCallback, useEffect, useState } from "react";
import { MenuGrid } from "@/components/pos/MenuGrid";
import { CartPanel } from "@/components/pos/CartPanel";
import { FloorGrid } from "@/components/pos/FloorGrid";
import { useCartStore } from "@/stores/cartStore";
import { useFloorStore } from "@/stores/floorStore";
import { useUIStore } from "@/stores/uiStore";
import { OrderTicker } from "@/components/pos/OrderTicker";
import { formatPKR } from "@/utils/currency";
import {
  getActiveSessionForTable,
  getSessionBillSummary,
  type TableSessionBillSummary,
} from "@/services/tableSessionApi";
import type { CartItem } from "@/types/cart";

function DineInPage() {
  const addItem = useCartStore((s) => s.addItem);
  const setActiveCart = useCartStore((s) => s.setActiveCart);
  const selectedTableId = useFloorStore((s) => s.selectedTableId);
  const setCurrentChannel = useUIStore((s) => s.setCurrentChannel);
  const [sessionBill, setSessionBill] = useState<TableSessionBillSummary | null>(null);

  useEffect(() => {
    setCurrentChannel("dine_in");
  }, [setCurrentChannel]);

  const tableSelected = Boolean(selectedTableId);

  // When table is selected, switch cart to that table's UUID
  function handleTableSelect(tableId: string) {
    setActiveCart(`table-${tableId}`);
  }

  // Keep the active cart in sync with floor selection, including persisted selection.
  useEffect(() => {
    if (selectedTableId) {
      setActiveCart(`table-${selectedTableId}`);
      return;
    }
    setActiveCart("dine-in-default");
  }, [selectedTableId, setActiveCart]);

  // Load active session bill when table changes
  useEffect(() => {
    if (!selectedTableId) {
      setSessionBill(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const session = await getActiveSessionForTable(selectedTableId);
        if (cancelled) return;
        if (session && session.order_count > 0) {
          const bill = await getSessionBillSummary(session.id);
          if (!cancelled) setSessionBill(bill);
        } else {
          setSessionBill(null);
        }
      } catch {
        if (!cancelled) setSessionBill(null);
      }
    })();
    return () => { cancelled = true; };
  }, [selectedTableId]);

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

        {/* Right: Cart panel + session bill */}
        <div className="w-80 shrink-0 border-l border-secondary-200 flex flex-col">
          {sessionBill && sessionBill.order_count > 0 && (
            <div className="border-b border-secondary-200 bg-amber-50 px-4 py-3 space-y-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">
                Table Session ({sessionBill.order_count} order{sessionBill.order_count !== 1 ? "s" : ""})
              </p>
              <div className="flex justify-between text-sm">
                <span className="text-amber-600">Running Total</span>
                <span className="font-semibold text-amber-800">{formatPKR(sessionBill.total)}</span>
              </div>
              {sessionBill.paid_amount > 0 && (
                <div className="flex justify-between text-sm">
                  <span className="text-amber-600">Paid</span>
                  <span className="text-amber-800">{formatPKR(sessionBill.paid_amount)}</span>
                </div>
              )}
              <div className="flex justify-between text-sm font-semibold">
                <span className="text-amber-700">Due</span>
                <span className="text-amber-900">{formatPKR(sessionBill.due_amount)}</span>
              </div>
            </div>
          )}
          <div className="flex-1 min-h-0">
            <CartPanel />
          </div>
        </div>
      </div>

      {/* Bottom: Live order ticker */}
      <OrderTicker orderType="dine_in" />
    </div>
  );
}

export default DineInPage;
