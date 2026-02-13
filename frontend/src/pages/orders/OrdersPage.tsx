import { useCallback, useEffect, useRef, useState } from "react";
import { ClipboardList, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useOrderStore } from "@/stores/orderStore";
import { OrderCard } from "@/components/pos/OrderCard";
import type { OrderListItem } from "@/types/order";

/* -------------------------------------------------------------------------- */
/*  Filter definitions                                                        */
/* -------------------------------------------------------------------------- */

interface FilterTab {
  key: string;
  label: string;
  params: { status?: string; active_only?: boolean };
}

const FILTER_TABS: FilterTab[] = [
  { key: "all", label: "All", params: {} },
  { key: "active", label: "Active", params: { active_only: true } },
  { key: "in_kitchen", label: "In Kitchen", params: { status: "in_kitchen" } },
  { key: "ready", label: "Ready", params: { status: "ready" } },
  { key: "completed", label: "Completed", params: { status: "completed" } },
];

const AUTO_REFRESH_MS = 15_000;

/* -------------------------------------------------------------------------- */
/*  Component                                                                 */
/* -------------------------------------------------------------------------- */

function OrdersPage() {
  const orders = useOrderStore((s) => s.orders);
  const isLoading = useOrderStore((s) => s.isLoading);
  const error = useOrderStore((s) => s.error);
  const loadOrders = useOrderStore((s) => s.loadOrders);
  const transitionOrder = useOrderStore((s) => s.transitionOrder);
  const voidOrder = useOrderStore((s) => s.voidOrder);

  const [activeFilter, setActiveFilter] = useState("active");

  // Keep a ref to the active filter params so the interval callback
  // always reads the latest value without re-registering the timer.
  const filterParamsRef = useRef(FILTER_TABS[1]!.params);

  /* ----- Fetch on filter change ----- */

  const fetchWithFilter = useCallback(
    (filterKey: string) => {
      const tab = FILTER_TABS.find((t) => t.key === filterKey) ?? FILTER_TABS[0]!;
      filterParamsRef.current = tab.params;

      // Clear the debounce so loadOrders actually fires
      useOrderStore.setState({ lastFetched: null });
      loadOrders(tab.params);
    },
    [loadOrders]
  );

  function handleFilterChange(filterKey: string) {
    setActiveFilter(filterKey);
    fetchWithFilter(filterKey);
  }

  /* ----- Initial load + auto-refresh ----- */

  useEffect(() => {
    fetchWithFilter(activeFilter);

    const interval = setInterval(() => {
      // Reset debounce before each auto-refresh tick
      useOrderStore.setState({ lastFetched: null });
      loadOrders(filterParamsRef.current);
    }, AUTO_REFRESH_MS);

    return () => clearInterval(interval);
    // Only run on mount and when fetchWithFilter identity changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchWithFilter]);

  /* ----- Handlers ----- */

  const handleTransition = useCallback(
    async (id: string, status: string) => {
      try {
        await transitionOrder(id, status);
      } catch {
        // Error is surfaced via orderStore.error
      }
    },
    [transitionOrder]
  );

  const handleVoid = useCallback(
    async (id: string) => {
      const confirmed = window.confirm(
        "Are you sure you want to void this order? This action cannot be undone."
      );
      if (!confirmed) return;

      try {
        await voidOrder(id, "Voided from Orders page");
      } catch {
        // Error is surfaced via orderStore.error
      }
    },
    [voidOrder]
  );

  /* ----- Render ----- */

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-secondary-200 bg-white px-6 py-4">
        <div className="flex items-center gap-3">
          <ClipboardList className="h-6 w-6 text-primary-600" />
          <h1 className="text-xl font-bold text-secondary-900">Orders</h1>
          <Badge variant="secondary">{orders.length}</Badge>
        </div>

        {/* Status filter tabs */}
        <div className="flex items-center gap-1 rounded-lg bg-secondary-100 p-1">
          {FILTER_TABS.map((tab) => (
            <Button
              key={tab.key}
              variant="ghost"
              size="sm"
              onClick={() => handleFilterChange(tab.key)}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                activeFilter === tab.key
                  ? "bg-white text-secondary-900 shadow-sm"
                  : "text-secondary-500 hover:text-secondary-700"
              )}
            >
              {tab.label}
            </Button>
          ))}
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mx-6 mt-4 rounded-lg border border-danger-200 bg-danger-50 px-4 py-3 text-sm text-danger-700">
          {error}
        </div>
      )}

      {/* Content area */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading && orders.length === 0 ? (
          /* Loading state (only show spinner when there are no cached orders) */
          <div className="flex flex-col items-center justify-center gap-3 py-24">
            <Loader2 className="h-8 w-8 animate-spin text-primary-400" />
            <p className="text-sm text-secondary-400">Loading orders...</p>
          </div>
        ) : orders.length === 0 ? (
          /* Empty state */
          <div className="flex flex-col items-center justify-center gap-3 py-24">
            <ClipboardList className="h-12 w-12 text-secondary-200" />
            <p className="text-base font-medium text-secondary-400">
              No orders found
            </p>
            <p className="text-sm text-secondary-300">
              Orders will appear here once they are created
            </p>
          </div>
        ) : (
          /* Orders grid */
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {orders.map((order: OrderListItem) => (
              <OrderCard
                key={order.id}
                order={order}
                onTransition={handleTransition}
                onVoid={handleVoid}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default OrdersPage;
