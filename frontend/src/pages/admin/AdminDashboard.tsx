import { useEffect, useState, useCallback } from "react";
import {
  fetchDashboardKpis,
  fetchLiveOperations,
} from "@/services/dashboardApi";
import {
  fetchHourlyBreakdown,
  fetchItemPerformance,
} from "@/services/reportsApi";
import type {
  DashboardKpis,
  LiveOperations,
  LiveOrderItem,
  HourlyBreakdown,
  ItemPerformance,
} from "@/types/order";
import { formatPKR } from "@/utils/currency";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DollarSign,
  ShoppingCart,
  TrendingUp,
  TrendingDown,
  BarChart3,
  UtensilsCrossed,
  Package,
  Phone,
  Clock,
  RefreshCw,
} from "lucide-react";

/* ---------- helpers ---------- */

function elapsed(createdAt: string): string {
  const diff = Math.floor(
    (Date.now() - new Date(createdAt).getTime()) / 60000
  );
  if (diff < 1) return "just now";
  if (diff < 60) return `${diff}m ago`;
  return `${Math.floor(diff / 60)}h ${diff % 60}m`;
}

const STATUS_STYLES: Record<string, string> = {
  in_kitchen: "bg-warning-100 text-warning-700",
  ready: "bg-success-100 text-success-700",
  served: "bg-primary-100 text-primary-700",
  confirmed: "bg-secondary-100 text-secondary-700",
};

function statusBadge(status: string) {
  const style = STATUS_STYLES[status] ?? "bg-secondary-100 text-secondary-600";
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-pos-xs font-medium capitalize ${style}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

/* ---------- sub-components ---------- */

function KpiCard({
  title,
  value,
  subtitle,
  icon: Icon,
  iconBg,
  iconColor,
  trend,
}: {
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ElementType;
  iconBg: string;
  iconColor: string;
  trend?: { direction: "up" | "down" | "flat"; label: string };
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-pos-sm font-medium text-secondary-600">
          {title}
        </CardTitle>
        <div className={`rounded-lg p-2 ${iconBg}`}>
          <Icon className={`h-5 w-5 ${iconColor}`} />
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-pos-2xl font-bold text-secondary-800">{value}</p>
        {trend && (
          <p className="mt-1 flex items-center gap-1 text-pos-xs">
            {trend.direction === "up" && (
              <TrendingUp className="h-4 w-4 text-success-500" />
            )}
            {trend.direction === "down" && (
              <TrendingDown className="h-4 w-4 text-danger-500" />
            )}
            <span
              className={
                trend.direction === "up"
                  ? "text-success-600"
                  : trend.direction === "down"
                    ? "text-danger-600"
                    : "text-secondary-400"
              }
            >
              {trend.label}
            </span>
          </p>
        )}
        {subtitle && (
          <p className="mt-1 text-pos-xs text-secondary-400">{subtitle}</p>
        )}
      </CardContent>
    </Card>
  );
}

function LiveOrderRow({ order }: { order: LiveOrderItem }) {
  return (
    <div className="flex items-center justify-between border-b border-secondary-100 px-4 py-3 last:border-0">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-secondary-800">
            {order.order_number}
          </span>
          {order.table_number != null && (
            <span className="text-pos-xs text-secondary-400">
              Table {order.table_number}
            </span>
          )}
          {order.customer_name && (
            <span className="truncate text-pos-xs text-secondary-400">
              {order.customer_name}
            </span>
          )}
        </div>
        <div className="mt-0.5 flex items-center gap-2 text-pos-xs text-secondary-400">
          <Clock className="h-3.5 w-3.5" />
          <span>{elapsed(order.created_at)}</span>
          <span>{order.item_count} item{order.item_count !== 1 ? "s" : ""}</span>
        </div>
      </div>
      <div className="flex flex-col items-end gap-1">
        {statusBadge(order.status)}
        <span className="text-pos-xs font-medium text-secondary-700">
          {formatPKR(order.total)}
        </span>
      </div>
    </div>
  );
}

function LiveColumn({
  title,
  icon: Icon,
  iconColor,
  orders,
}: {
  title: string;
  icon: React.ElementType;
  iconColor: string;
  orders: LiveOrderItem[];
}) {
  return (
    <Card className="flex flex-col">
      <CardHeader className="flex flex-row items-center gap-2 pb-3">
        <Icon className={`h-5 w-5 ${iconColor}`} />
        <CardTitle className="text-pos-sm font-semibold text-secondary-700">
          {title}
        </CardTitle>
        <span className="ml-auto rounded-full bg-secondary-100 px-2 py-0.5 text-pos-xs font-medium text-secondary-600">
          {orders.length}
        </span>
      </CardHeader>
      <CardContent className="flex-1 p-0">
        {orders.length === 0 ? (
          <p className="px-4 py-8 text-center text-pos-xs text-secondary-400">
            No active orders
          </p>
        ) : (
          <div className="max-h-80 overflow-y-auto">
            {orders.map((o) => (
              <LiveOrderRow key={o.id} order={o} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function HourlyChart({ data }: { data: HourlyBreakdown | null }) {
  if (!data) return null;

  const buckets = data.buckets;
  const maxRevenue = Math.max(...buckets.map((b) => b.revenue), 1);
  const currentHour = new Date().getHours();

  return (
    <Card>
      <CardHeader className="flex flex-row items-center gap-2 pb-3">
        <BarChart3 className="h-5 w-5 text-primary-500" />
        <CardTitle className="text-pos-sm font-semibold text-secondary-700">
          Hourly Sales
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex h-48 items-end gap-1">
          {buckets.map((bucket) => {
            const pct = (bucket.revenue / maxRevenue) * 100;
            const isCurrent = bucket.hour === currentHour;
            return (
              <div
                key={bucket.hour}
                className="group relative flex flex-1 flex-col items-center"
              >
                {/* tooltip on hover */}
                <div className="pointer-events-none absolute -top-10 z-10 hidden whitespace-nowrap rounded bg-secondary-800 px-2 py-1 text-pos-xs text-white shadow group-hover:block">
                  {bucket.hour}:00 &mdash; {formatPKR(bucket.revenue)} (
                  {bucket.order_count} orders)
                </div>
                <div
                  className={`w-full rounded-t transition-all ${
                    isCurrent ? "bg-primary-500" : "bg-primary-200"
                  }`}
                  style={{
                    height: `${pct > 0 ? Math.max(pct, 1) : 0.5}%`,
                    minHeight: "2px",
                  }}
                />
              </div>
            );
          })}
        </div>
        {/* hour labels every 3 hours */}
        <div className="mt-1 flex">
          {buckets.map((bucket) => (
            <div key={bucket.hour} className="flex-1 text-center">
              {bucket.hour % 3 === 0 ? (
                <span className="text-[0.65rem] text-secondary-400">
                  {bucket.hour}:00
                </span>
              ) : null}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function TopItemsChart({ data }: { data: ItemPerformance | null }) {
  if (!data || data.top_items.length === 0) return null;

  const items = data.top_items.slice(0, 5);
  const maxItemRevenue = Math.max(...items.map((i) => i.revenue), 1);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center gap-2 pb-3">
        <TrendingUp className="h-5 w-5 text-success-500" />
        <CardTitle className="text-pos-sm font-semibold text-secondary-700">
          Top 5 Items
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {items.map((item, idx) => (
            <div key={item.menu_item_id}>
              <div className="mb-1 flex items-center justify-between">
                <span className="text-pos-xs font-medium text-secondary-700">
                  {idx + 1}. {item.name}
                </span>
                <span className="text-pos-xs text-secondary-500">
                  {formatPKR(item.revenue)} ({item.quantity_sold} sold)
                </span>
              </div>
              <div className="h-2.5 w-full rounded-full bg-secondary-100">
                <div
                  className="h-2.5 rounded-full bg-success-400 transition-all"
                  style={{
                    width: `${(item.revenue / maxItemRevenue) * 100}%`,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

/* ---------- main component ---------- */

function AdminDashboard() {
  const [kpis, setKpis] = useState<DashboardKpis | null>(null);
  const [live, setLive] = useState<LiveOperations | null>(null);
  const [hourly, setHourly] = useState<HourlyBreakdown | null>(null);
  const [topItems, setTopItems] = useState<ItemPerformance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const loadData = useCallback(async () => {
    try {
      const today = new Date().toISOString().split("T")[0] ?? "";
      const [kpiData, liveData, hourlyData, itemData] = await Promise.all([
        fetchDashboardKpis(),
        fetchLiveOperations(),
        fetchHourlyBreakdown(today),
        fetchItemPerformance(today, today),
      ]);
      setKpis(kpiData);
      setLive(liveData);
      setHourly(hourlyData);
      setTopItems(itemData);
      setError(null);
    } catch (err) {
      console.error("Dashboard data fetch failed:", err);
      setError("Failed to load dashboard data. Retrying...");
    } finally {
      setLoading(false);
      setLastRefresh(new Date());
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30_000);
    return () => clearInterval(interval);
  }, [loadData]);

  /* Revenue trend calculation */
  const revenueTrend = (() => {
    if (!kpis) return undefined;
    if (kpis.yesterday_revenue === 0) {
      if (kpis.today_revenue === 0) return { direction: "flat" as const, label: "No sales yet" };
      return { direction: "up" as const, label: "First sales today" };
    }
    const pctChange =
      ((kpis.today_revenue - kpis.yesterday_revenue) / kpis.yesterday_revenue) *
      100;
    const direction: "up" | "down" | "flat" =
      pctChange > 0 ? "up" : pctChange < 0 ? "down" : "flat";
    return {
      direction,
      label: `${Math.abs(pctChange).toFixed(1)}% vs yesterday`,
    };
  })();

  /* utilization progress bar width */
  const utilPct = kpis ? Math.min(kpis.table_utilization, 100) : 0;

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-primary-400" />
        <span className="ml-3 text-pos-base text-secondary-500">
          Loading dashboard...
        </span>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BarChart3 className="h-6 w-6 text-secondary-600" />
          <h1 className="text-pos-2xl font-bold text-secondary-800">
            Dashboard
          </h1>
        </div>
        <div className="flex items-center gap-3">
          {error && (
            <span className="text-pos-xs text-danger-500">{error}</span>
          )}
          <span className="text-pos-xs text-secondary-400">
            Updated {lastRefresh.toLocaleTimeString()}
          </span>
          <button
            onClick={loadData}
            className="rounded-lg p-2 text-secondary-400 transition-colors hover:bg-secondary-100 hover:text-secondary-600"
            aria-label="Refresh dashboard"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          title="Today's Revenue"
          value={kpis ? formatPKR(kpis.today_revenue) : "--"}
          icon={DollarSign}
          iconBg="bg-success-50"
          iconColor="text-success-500"
          trend={revenueTrend}
        />
        <KpiCard
          title="Orders Today"
          value={kpis ? String(kpis.today_orders) : "--"}
          icon={ShoppingCart}
          iconBg="bg-primary-50"
          iconColor="text-primary-500"
          subtitle={
            kpis
              ? `${kpis.active_orders} active, ${kpis.pending_kitchen} in kitchen`
              : undefined
          }
        />
        <KpiCard
          title="Avg Order Value"
          value={kpis ? formatPKR(kpis.avg_order_value) : "--"}
          icon={TrendingUp}
          iconBg="bg-accent-50"
          iconColor="text-accent-500"
        />
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-pos-sm font-medium text-secondary-600">
              Table Utilization
            </CardTitle>
            <div className="rounded-lg bg-warning-50 p-2">
              <BarChart3 className="h-5 w-5 text-warning-500" />
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-pos-2xl font-bold text-secondary-800">
              {kpis ? `${Math.round(kpis.table_utilization)}%` : "--"}
            </p>
            <div className="mt-2 h-2 w-full rounded-full bg-secondary-100">
              <div
                className="h-2 rounded-full bg-warning-400 transition-all"
                style={{ width: `${utilPct}%` }}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Live Operations */}
      <div className="mb-6">
        <h2 className="mb-3 text-pos-lg font-semibold text-secondary-700">
          Live Operations
        </h2>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <LiveColumn
            title="Dine-In"
            icon={UtensilsCrossed}
            iconColor="text-primary-500"
            orders={live?.dine_in ?? []}
          />
          <LiveColumn
            title="Takeaway"
            icon={Package}
            iconColor="text-accent-500"
            orders={live?.takeaway ?? []}
          />
          <LiveColumn
            title="Call Center"
            icon={Phone}
            iconColor="text-warning-500"
            orders={live?.call_center ?? []}
          />
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <HourlyChart data={hourly} />
        <TopItemsChart data={topItems} />
      </div>
    </div>
  );
}

export default AdminDashboard;
