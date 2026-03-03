import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MenuGrid } from "@/components/pos/MenuGrid";
import { CartPanel } from "@/components/pos/CartPanel";
import { FloorGrid } from "@/components/pos/FloorGrid";
import { useCartStore } from "@/stores/cartStore";
import { useFloorStore } from "@/stores/floorStore";
import { useUIStore } from "@/stores/uiStore";
import { OrderTicker } from "@/components/pos/OrderTicker";
import { Button } from "@/components/ui/button";
import { formatPKR } from "@/utils/currency";
import {
  getActiveSessionForTable,
  getSessionBillSummary,
  fetchWaiters,
  type TableSessionBillSummary,
} from "@/services/tableSessionApi";
import type { CartItem } from "@/types/cart";

function DineInPage() {
  const addItem = useCartStore((s) => s.addItem);
  const setActiveCart = useCartStore((s) => s.setActiveCart);
  const selectedTableId = useFloorStore((s) => s.selectedTableId);
  const setCurrentChannel = useUIStore((s) => s.setCurrentChannel);
  const navigate = useNavigate();
  const [sessionBill, setSessionBill] = useState<TableSessionBillSummary | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [waiters, setWaiters] = useState<{ id: string; name: string; role: string }[]>([]);
  const [selectedWaiterId, setSelectedWaiterId] = useState<string>("");
  const [sessionWaiterName, setSessionWaiterName] = useState<string | null>(null);

  useEffect(() => {
    setCurrentChannel("dine_in");
    fetchWaiters().then(setWaiters).catch(() => {});
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
      setActiveSessionId(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const session = await getActiveSessionForTable(selectedTableId);
        if (cancelled) return;
        if (session) {
          setActiveSessionId(session.id);
          setSessionWaiterName(session.assigned_waiter_name ?? null);
          if (session.order_count > 0) {
            const bill = await getSessionBillSummary(session.id);
            if (!cancelled) setSessionBill(bill);
          } else {
            setSessionBill(null);
          }
        } else {
          setActiveSessionId(null);
          setSessionBill(null);
          setSessionWaiterName(null);
        }
      } catch {
        if (!cancelled) {
          setSessionBill(null);
          setActiveSessionId(null);
        }
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

  // Refresh session data after an order is created (to show waiter name, update bill)
  const handleOrderCreated = useCallback(() => {
    if (!selectedTableId) return;
    void (async () => {
      try {
        const session = await getActiveSessionForTable(selectedTableId);
        if (session) {
          setActiveSessionId(session.id);
          setSessionWaiterName(session.assigned_waiter_name ?? null);
          if (session.order_count > 0) {
            const bill = await getSessionBillSummary(session.id);
            setSessionBill(bill);
          }
        }
      } catch { /* ignore */ }
    })();
  }, [selectedTableId]);

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
          {/* Waiter selector / display */}
          {tableSelected && (
            <div className="border-b border-secondary-200 bg-blue-50 px-4 py-2">
              {sessionWaiterName ? (
                <p className="text-xs text-blue-700">
                  <span className="font-semibold">Waiter:</span> {sessionWaiterName}
                </p>
              ) : (
                <div className="flex items-center gap-2">
                  <label className="text-xs font-semibold text-blue-700 whitespace-nowrap">Waiter:</label>
                  <select
                    className="flex-1 rounded border border-blue-200 bg-white px-2 py-1 text-xs"
                    value={selectedWaiterId}
                    onChange={(e) => setSelectedWaiterId(e.target.value)}
                  >
                    <option value="">No waiter</option>
                    {waiters.map((w) => (
                      <option key={w.id} value={w.id}>{w.name}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          )}
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
              {sessionBill.due_amount > 0 && activeSessionId && (
                <Button
                  size="sm"
                  className="mt-2 w-full"
                  onClick={() => navigate(`/payment/session/${activeSessionId}`)}
                >
                  Settle Table
                </Button>
              )}
            </div>
          )}
          <div className="flex-1 min-h-0">
            <CartPanel waiterId={selectedWaiterId || undefined} onOrderCreated={handleOrderCreated} />
          </div>
        </div>
      </div>

      {/* Bottom: Live order ticker */}
      <OrderTicker orderType="dine_in" />
    </div>
  );
}

export default DineInPage;
