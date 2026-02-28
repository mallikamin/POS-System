import { useEffect, useMemo } from "react";
import { useOrderStore } from "@/stores/orderStore";
import { Clock, ChefHat } from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  confirmed: "bg-secondary-100 text-secondary-700",
  in_kitchen: "bg-warning-100 text-warning-700",
  ready: "bg-success-100 text-success-700",
  served: "bg-primary-100 text-primary-700",
};

const STATUS_LABELS: Record<string, string> = {
  confirmed: "Confirmed",
  in_kitchen: "Kitchen",
  ready: "Ready",
  served: "Served",
};

function elapsed(createdAt: string): string {
  const diff = Math.floor((Date.now() - new Date(createdAt).getTime()) / 60000);
  if (diff < 1) return "<1m";
  if (diff < 60) return `${diff}m`;
  return `${Math.floor(diff / 60)}h${diff % 60}m`;
}

interface OrderTickerProps {
  orderType?: "dine_in" | "takeaway" | "call_center";
}

export function OrderTicker({ orderType }: OrderTickerProps) {
  const orders = useOrderStore((s) => s.orders);
  const loadOrders = useOrderStore((s) => s.loadOrders);

  useEffect(() => {
    loadOrders({ active_only: true });
    const interval = setInterval(() => {
      useOrderStore.setState({ lastFetched: null });
      loadOrders({ active_only: true });
    }, 15_000);
    return () => clearInterval(interval);
  }, [loadOrders]);

  const activeOrders = useMemo(
    () => orders.filter((o) =>
      !["completed", "voided"].includes(o.status) &&
      (!orderType || o.order_type === orderType)
    ),
    [orders, orderType]
  );

  if (activeOrders.length === 0) return null;

  return (
    <div className="flex items-center gap-2 overflow-x-auto border-t border-secondary-200 bg-secondary-50 px-3 py-1.5 scrollbar-thin">
      <div className="flex shrink-0 items-center gap-1.5 text-xs font-semibold text-secondary-500">
        <ChefHat className="h-3.5 w-3.5" />
        <span>{activeOrders.length}</span>
      </div>
      <div className="h-4 w-px bg-secondary-200" />
      {activeOrders.slice(0, 8).map((order) => (
        <div
          key={order.id}
          className="flex shrink-0 items-center gap-1.5 rounded-full bg-white px-2.5 py-1 text-[11px] shadow-sm border border-secondary-100"
        >
          <span className="font-semibold text-secondary-700">
            #{order.order_number.split("-")[1]}
          </span>
          <span
            className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none ${
              STATUS_COLORS[order.status] || "bg-secondary-100 text-secondary-600"
            }`}
          >
            {STATUS_LABELS[order.status] || order.status}
          </span>
          <span className="text-secondary-400 flex items-center gap-0.5">
            <Clock className="h-2.5 w-2.5" />
            {elapsed(order.created_at)}
          </span>
        </div>
      ))}
      {activeOrders.length > 8 && (
        <span className="shrink-0 text-[11px] text-secondary-400">
          +{activeOrders.length - 8} more
        </span>
      )}
    </div>
  );
}
