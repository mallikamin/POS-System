import { useEffect, useState, useCallback } from "react";
import {
  fetchSalesSummary,
  fetchItemPerformance,
  fetchHourlyBreakdown,
  fetchVoidReport,
  fetchPaymentMethodReport,
  fetchWaiterPerformance,
  downloadSalesCsv,
} from "@/services/reportsApi";
import type {
  SalesSummary,
  ItemPerformance,
  HourlyBreakdown,
  VoidReport,
  PaymentMethodReport,
  WaiterPerformanceReport,
} from "@/types/order";
import { formatPKR } from "@/utils/currency";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  BarChart3,
  Download,
  DollarSign,
  ShoppingCart,
  Receipt,
  Calendar,
  Loader2,
  AlertCircle,
  TrendingDown,
  Percent,
  Tag,
  Ban,
  CreditCard,
  Banknote,
  Wallet,
  UserCircle,
} from "lucide-react";

/* ---------- date helpers ---------- */

const today = new Date().toISOString().split("T")[0] ?? "";
const yesterday = new Date(Date.now() - 86400000).toISOString().split("T")[0] ?? "";
const weekStart = (() => {
  const d = new Date();
  d.setDate(d.getDate() - d.getDay());
  return d.toISOString().split("T")[0] ?? "";
})();
const monthStart = new Date(
  new Date().getFullYear(),
  new Date().getMonth(),
  1
)
  .toISOString()
  .split("T")[0] ?? "";

interface DatePreset {
  label: string;
  from: string;
  to: string;
}

const presets: DatePreset[] = [
  { label: "Today", from: today, to: today },
  { label: "Yesterday", from: yesterday, to: yesterday },
  { label: "This Week", from: weekStart, to: today },
  { label: "This Month", from: monthStart, to: today },
];

/* ---------- channel config ---------- */

interface ChannelInfo {
  key: "dine_in" | "takeaway" | "call_center";
  label: string;
  color: string;
  bgColor: string;
}

const channels: ChannelInfo[] = [
  {
    key: "dine_in",
    label: "Dine-In",
    color: "bg-primary-500",
    bgColor: "bg-primary-50",
  },
  {
    key: "takeaway",
    label: "Takeaway",
    color: "bg-success-500",
    bgColor: "bg-success-50",
  },
  {
    key: "call_center",
    label: "Call Center",
    color: "bg-accent-500",
    bgColor: "bg-accent-50",
  },
];

/* ---------- component ---------- */

function ReportsPage() {
  const [dateFrom, setDateFrom] = useState(today);
  const [dateTo, setDateTo] = useState(today);

  const [summary, setSummary] = useState<SalesSummary | null>(null);
  const [itemPerf, setItemPerf] = useState<ItemPerformance | null>(null);
  const [hourly, setHourly] = useState<HourlyBreakdown | null>(null);
  const [voidReport, setVoidReport] = useState<VoidReport | null>(null);
  const [pmReport, setPmReport] = useState<PaymentMethodReport | null>(null);
  const [waiterReport, setWaiterReport] = useState<WaiterPerformanceReport | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [hoveredHour, setHoveredHour] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryData, itemData, hourlyData, voidData, pmData, waiterData] = await Promise.all([
        fetchSalesSummary(dateFrom, dateTo),
        fetchItemPerformance(dateFrom, dateTo),
        fetchHourlyBreakdown(dateFrom),
        fetchVoidReport(dateFrom, dateTo),
        fetchPaymentMethodReport(dateFrom, dateTo),
        fetchWaiterPerformance(dateFrom, dateTo),
      ]);
      setSummary(summaryData);
      setItemPerf(itemData);
      setHourly(hourlyData);
      setVoidReport(voidData);
      setPmReport(pmData);
      setWaiterReport(waiterData);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load report data";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo]);

  useEffect(() => {
    if (dateFrom && dateTo) {
      loadData();
    }
  }, [dateFrom, dateTo, loadData]);

  const handleExport = async () => {
    setExporting(true);
    try {
      await downloadSalesCsv(dateFrom, dateTo);
    } catch {
      /* download error is visible to user via browser */
    } finally {
      setExporting(false);
    }
  };

  const applyPreset = (preset: DatePreset) => {
    setDateFrom(preset.from);
    setDateTo(preset.to);
  };

  const isActivePreset = (preset: DatePreset) =>
    dateFrom === preset.from && dateTo === preset.to;

  /* hourly chart helpers */
  const maxHourlyRevenue =
    hourly?.buckets.reduce((max, b) => Math.max(max, b.revenue), 0) ?? 0;

  const getBarHeight = (revenue: number) => {
    if (maxHourlyRevenue === 0) return 0;
    return Math.max((revenue / maxHourlyRevenue) * 100, revenue > 0 ? 4 : 0);
  };

  /* channel breakdown helpers */
  const getChannelRevenue = (ch: ChannelInfo): number => {
    if (!summary) return 0;
    return summary[`${ch.key}_revenue` as keyof SalesSummary] as number;
  };

  const getChannelOrders = (ch: ChannelInfo): number => {
    if (!summary) return 0;
    return summary[`${ch.key}_orders` as keyof SalesSummary] as number;
  };

  const maxChannelRevenue = Math.max(
    ...channels.map((ch) => getChannelRevenue(ch)),
    1
  );

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* ---------- header ---------- */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <BarChart3 className="h-7 w-7 text-primary-600" />
          <h1 className="text-pos-2xl font-bold text-secondary-800">
            Sales Reports
          </h1>
        </div>

        <Button
          onClick={handleExport}
          variant="outline"
          disabled={exporting || loading || !summary}
          className="w-full sm:w-auto"
        >
          {exporting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          Export CSV
        </Button>
      </div>

      {/* ---------- date range picker ---------- */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-secondary-500" />
              <span className="text-sm font-medium text-secondary-700">
                Date Range
              </span>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                max={dateTo}
                className="rounded-lg border border-secondary-300 px-3 py-2 text-sm text-secondary-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200"
                aria-label="From date"
              />
              <span className="text-sm text-secondary-400">to</span>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                min={dateFrom}
                max={today}
                className="rounded-lg border border-secondary-300 px-3 py-2 text-sm text-secondary-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200"
                aria-label="To date"
              />
            </div>

            <div className="flex flex-wrap gap-2">
              {presets.map((preset) => (
                <Button
                  key={preset.label}
                  variant={isActivePreset(preset) ? "default" : "secondary"}
                  size="sm"
                  onClick={() => applyPreset(preset)}
                >
                  {preset.label}
                </Button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ---------- loading / error ---------- */}
      {loading && (
        <div className="flex items-center justify-center gap-3 py-12">
          <Loader2 className="h-6 w-6 animate-spin text-primary-500" />
          <span className="text-secondary-500">Loading report data...</span>
        </div>
      )}

      {error && !loading && (
        <div className="flex items-center gap-3 rounded-lg border border-danger-200 bg-danger-50 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-danger-600" />
          <div>
            <p className="font-medium text-danger-800">
              Failed to load reports
            </p>
            <p className="text-sm text-danger-600">{error}</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={loadData}
            className="ml-auto"
          >
            Retry
          </Button>
        </div>
      )}

      {/* ---------- data sections ---------- */}
      {!loading && summary && (
        <>
          {/* summary cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-secondary-600">
                  Total Revenue
                </CardTitle>
                <DollarSign className="h-5 w-5 text-success-500" />
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-secondary-900">
                  {formatPKR(summary.total_revenue)}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-secondary-600">
                  Total Orders
                </CardTitle>
                <ShoppingCart className="h-5 w-5 text-primary-500" />
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-secondary-900">
                  {summary.total_orders.toLocaleString()}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-secondary-600">
                  Avg Order Value
                </CardTitle>
                <BarChart3 className="h-5 w-5 text-accent-500" />
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-secondary-900">
                  {formatPKR(summary.avg_order_value)}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-secondary-600">
                  Tax Collected
                </CardTitle>
                <Receipt className="h-5 w-5 text-warning-500" />
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-secondary-900">
                  {formatPKR(summary.total_tax)}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* discount & net revenue row */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-secondary-600">
                  Total Discount
                </CardTitle>
                <Tag className="h-5 w-5 text-danger-500" />
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-danger-600">
                  {formatPKR(summary.total_discount)}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-secondary-600">
                  Net Revenue
                </CardTitle>
                <DollarSign className="h-5 w-5 text-success-600" />
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-success-700">
                  {formatPKR(summary.net_revenue)}
                </p>
              </CardContent>
            </Card>

            {/* discount breakdown by type */}
            {summary.discount_breakdown.length > 0 && (
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-secondary-600">
                    Discount Breakdown
                  </CardTitle>
                  <Percent className="h-5 w-5 text-accent-500" />
                </CardHeader>
                <CardContent>
                  <div className="flex flex-col gap-2">
                    {summary.discount_breakdown.map((entry) => (
                      <div
                        key={entry.source_type}
                        className="flex items-center justify-between text-sm"
                      >
                        <span className="text-secondary-600">
                          {entry.label}{" "}
                          <span className="text-xs text-secondary-400">
                            ({entry.count}x)
                          </span>
                        </span>
                        <span className="font-medium text-secondary-800">
                          {formatPKR(entry.total)}
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* cash / card / other revenue split */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-secondary-600">
                  Cash Revenue
                </CardTitle>
                <Banknote className="h-5 w-5 text-success-500" />
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-secondary-900">
                  {formatPKR(summary.cash_revenue)}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-secondary-600">
                  Card Revenue
                </CardTitle>
                <CreditCard className="h-5 w-5 text-primary-500" />
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-secondary-900">
                  {formatPKR(summary.card_revenue)}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-secondary-600">
                  Other Revenue
                </CardTitle>
                <Wallet className="h-5 w-5 text-accent-500" />
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-secondary-900">
                  {formatPKR(summary.other_revenue)}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* payment-method breakdown + void report */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* payment-method breakdown */}
            {pmReport && pmReport.entries.length > 0 && (
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <CreditCard className="h-4 w-4 text-primary-500" />
                    <CardTitle className="text-base text-secondary-800">
                      Payment Method Breakdown
                    </CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="overflow-hidden rounded-lg border border-secondary-200">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-secondary-200 bg-secondary-50">
                          <th className="px-4 py-2.5 text-left font-medium text-secondary-600">
                            Method
                          </th>
                          <th className="px-4 py-2.5 text-right font-medium text-secondary-600">
                            Payments
                          </th>
                          <th className="px-4 py-2.5 text-right font-medium text-secondary-600">
                            Total
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-secondary-100">
                        {pmReport.entries.map((entry) => (
                          <tr key={entry.method_code} className="hover:bg-secondary-50">
                            <td className="px-4 py-2.5 text-secondary-700">
                              {entry.method}
                            </td>
                            <td className="px-4 py-2.5 text-right text-secondary-800">
                              {entry.count}
                            </td>
                            <td className="px-4 py-2.5 text-right font-medium text-secondary-900">
                              {formatPKR(entry.total)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="border-t border-secondary-200 bg-secondary-50">
                          <td className="px-4 py-2.5 font-medium text-secondary-700">
                            Total Collected
                          </td>
                          <td />
                          <td className="px-4 py-2.5 text-right font-bold text-secondary-900">
                            {formatPKR(pmReport.total_collected)}
                          </td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* void report */}
            {voidReport && (
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Ban className="h-4 w-4 text-danger-500" />
                    <CardTitle className="text-base text-secondary-800">
                      Void Report
                    </CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="mb-4 grid grid-cols-2 gap-4">
                    <div className="rounded-lg bg-danger-50 p-3">
                      <p className="text-xs font-medium text-danger-600">
                        Total Voids
                      </p>
                      <p className="text-xl font-bold text-danger-700">
                        {voidReport.total_voids}
                      </p>
                    </div>
                    <div className="rounded-lg bg-danger-50 p-3">
                      <p className="text-xs font-medium text-danger-600">
                        Voided Value
                      </p>
                      <p className="text-xl font-bold text-danger-700">
                        {formatPKR(voidReport.total_voided_value)}
                      </p>
                    </div>
                  </div>

                  {voidReport.by_reason.length > 0 && (
                    <div className="mb-4">
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-secondary-500">
                        By Reason
                      </p>
                      <div className="flex flex-col gap-1.5">
                        {voidReport.by_reason.map((entry) => (
                          <div
                            key={entry.reason}
                            className="flex items-center justify-between text-sm"
                          >
                            <span className="text-secondary-600">
                              {entry.reason}{" "}
                              <span className="text-xs text-secondary-400">
                                ({entry.count}x)
                              </span>
                            </span>
                            <span className="font-medium text-secondary-800">
                              {formatPKR(entry.total_value)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {voidReport.by_user.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-secondary-500">
                        By User
                      </p>
                      <div className="flex flex-col gap-1.5">
                        {voidReport.by_user.map((entry) => (
                          <div
                            key={entry.user_id}
                            className="flex items-center justify-between text-sm"
                          >
                            <span className="flex items-center gap-1.5 text-secondary-600">
                              <UserCircle className="h-3.5 w-3.5" />
                              {entry.user_name}{" "}
                              <span className="text-xs text-secondary-400">
                                ({entry.count}x)
                              </span>
                            </span>
                            <span className="font-medium text-secondary-800">
                              {formatPKR(entry.total_value)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {voidReport.total_voids === 0 && (
                    <p className="py-4 text-center text-sm text-secondary-400">
                      No voided orders in this period
                    </p>
                  )}
                </CardContent>
              </Card>
            )}
          </div>

          {/* waiter performance */}
          {waiterReport && (
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <UserCircle className="h-4 w-4 text-primary-500" />
                  <CardTitle className="text-base text-secondary-800">
                    Waiter Performance
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                {waiterReport.entries.length > 0 ? (
                  <div className="overflow-hidden rounded-lg border border-secondary-200">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-secondary-200 bg-secondary-50">
                          <th className="px-4 py-2.5 text-left font-medium text-secondary-600">
                            Waiter
                          </th>
                          <th className="px-4 py-2.5 text-right font-medium text-secondary-600">
                            Orders
                          </th>
                          <th className="px-4 py-2.5 text-right font-medium text-secondary-600">
                            Revenue
                          </th>
                          <th className="px-4 py-2.5 text-right font-medium text-secondary-600">
                            Avg Order
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-secondary-100">
                        {waiterReport.entries.map((entry) => (
                          <tr key={entry.waiter_id} className="hover:bg-secondary-50">
                            <td className="px-4 py-2.5 text-secondary-700">
                              <div className="flex items-center gap-1.5">
                                <UserCircle className="h-3.5 w-3.5 text-secondary-400" />
                                {entry.waiter_name}
                              </div>
                            </td>
                            <td className="px-4 py-2.5 text-right text-secondary-800">
                              {entry.order_count}
                            </td>
                            <td className="px-4 py-2.5 text-right font-medium text-secondary-900">
                              {formatPKR(entry.total_revenue)}
                            </td>
                            <td className="px-4 py-2.5 text-right text-secondary-700">
                              {formatPKR(entry.avg_order_value)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="border-t border-secondary-200 bg-secondary-50">
                          <td className="px-4 py-2.5 font-medium text-secondary-700">
                            Total (with waiter)
                          </td>
                          <td className="px-4 py-2.5 text-right font-bold text-secondary-900">
                            {waiterReport.total_orders_with_waiter}
                          </td>
                          <td className="px-4 py-2.5 text-right font-bold text-secondary-900">
                            {formatPKR(waiterReport.entries.reduce((s, e) => s + e.total_revenue, 0))}
                          </td>
                          <td />
                        </tr>
                        {waiterReport.total_orders_without_waiter > 0 && (
                          <tr className="bg-secondary-50">
                            <td className="px-4 py-2.5 text-secondary-500" colSpan={2}>
                              Orders without waiter
                            </td>
                            <td className="px-4 py-2.5 text-right text-secondary-500" colSpan={2}>
                              {waiterReport.total_orders_without_waiter}
                            </td>
                          </tr>
                        )}
                      </tfoot>
                    </table>
                  </div>
                ) : (
                  <p className="text-center text-sm text-secondary-500 py-4">
                    No waiter-assigned orders in this period
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {/* channel breakdown + hourly chart */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* channel breakdown */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base text-secondary-800">
                  Channel Breakdown
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col gap-5">
                  {channels.map((ch) => {
                    const revenue = getChannelRevenue(ch);
                    const orders = getChannelOrders(ch);
                    const pct =
                      maxChannelRevenue > 0
                        ? (revenue / maxChannelRevenue) * 100
                        : 0;

                    return (
                      <div key={ch.key} className="flex flex-col gap-2">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-secondary-700">
                            {ch.label}
                          </span>
                          <div className="flex items-center gap-4">
                            <span className="text-xs text-secondary-500">
                              {orders} order{orders !== 1 ? "s" : ""}
                            </span>
                            <span className="text-sm font-semibold text-secondary-800">
                              {formatPKR(revenue)}
                            </span>
                          </div>
                        </div>
                        <div className="h-3 w-full overflow-hidden rounded-full bg-secondary-100">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${ch.color}`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* channel summary table */}
                <div className="mt-6 overflow-hidden rounded-lg border border-secondary-200">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-secondary-200 bg-secondary-50">
                        <th className="px-4 py-2.5 text-left font-medium text-secondary-600">
                          Channel
                        </th>
                        <th className="px-4 py-2.5 text-right font-medium text-secondary-600">
                          Orders
                        </th>
                        <th className="px-4 py-2.5 text-right font-medium text-secondary-600">
                          Revenue
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-secondary-100">
                      {channels.map((ch) => (
                        <tr key={ch.key} className="hover:bg-secondary-50">
                          <td className="px-4 py-2.5 text-secondary-700">
                            <div className="flex items-center gap-2">
                              <div
                                className={`h-2.5 w-2.5 rounded-full ${ch.color}`}
                              />
                              {ch.label}
                            </div>
                          </td>
                          <td className="px-4 py-2.5 text-right text-secondary-800">
                            {getChannelOrders(ch).toLocaleString()}
                          </td>
                          <td className="px-4 py-2.5 text-right font-medium text-secondary-900">
                            {formatPKR(getChannelRevenue(ch))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>

            {/* hourly breakdown chart */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base text-secondary-800">
                  Hourly Revenue ({hourly?.date ?? dateFrom})
                </CardTitle>
              </CardHeader>
              <CardContent>
                {hourly && hourly.buckets.length > 0 ? (
                  <div className="flex flex-col gap-2">
                    {/* chart area */}
                    <div className="relative flex h-48 items-end gap-[2px]">
                      {hourly.buckets.map((bucket) => {
                        const height = getBarHeight(bucket.revenue);
                        const isHovered = hoveredHour === bucket.hour;

                        return (
                          <div
                            key={bucket.hour}
                            className="group relative flex flex-1 flex-col items-center justify-end"
                            onMouseEnter={() => setHoveredHour(bucket.hour)}
                            onMouseLeave={() => setHoveredHour(null)}
                          >
                            {/* tooltip */}
                            {isHovered && bucket.revenue > 0 && (
                              <div className="absolute -top-14 left-1/2 z-10 -translate-x-1/2 whitespace-nowrap rounded-lg bg-secondary-800 px-3 py-1.5 text-xs text-white shadow-lg">
                                <div className="font-medium">
                                  {formatPKR(bucket.revenue)}
                                </div>
                                <div className="text-secondary-300">
                                  {bucket.order_count} order
                                  {bucket.order_count !== 1 ? "s" : ""}
                                </div>
                                <div className="absolute -bottom-1 left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 bg-secondary-800" />
                              </div>
                            )}

                            {/* bar */}
                            <div
                              className={`w-full rounded-t transition-all duration-300 ${
                                isHovered
                                  ? "bg-primary-500"
                                  : "bg-primary-400"
                              } ${
                                bucket.revenue === 0
                                  ? "bg-secondary-200"
                                  : ""
                              }`}
                              style={{
                                height: `${height}%`,
                                minHeight: bucket.revenue > 0 ? "4px" : "2px",
                              }}
                            />
                          </div>
                        );
                      })}
                    </div>

                    {/* hour labels */}
                    <div className="flex gap-[2px]">
                      {hourly.buckets.map((bucket) => (
                        <div
                          key={bucket.hour}
                          className="flex-1 text-center text-[10px] text-secondary-400"
                        >
                          {bucket.hour % 3 === 0
                            ? `${bucket.hour.toString().padStart(2, "0")}:00`
                            : ""}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="flex h-48 items-center justify-center text-sm text-secondary-400">
                    No hourly data available
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* item performance tables */}
          {itemPerf && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              {/* top 10 items */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base text-secondary-800">
                    Top 10 Items
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {itemPerf.top_items.length > 0 ? (
                    <div className="overflow-hidden rounded-lg border border-secondary-200">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-secondary-200 bg-secondary-50">
                            <th className="w-12 px-4 py-2.5 text-center font-medium text-secondary-600">
                              #
                            </th>
                            <th className="px-4 py-2.5 text-left font-medium text-secondary-600">
                              Item Name
                            </th>
                            <th className="px-4 py-2.5 text-right font-medium text-secondary-600">
                              Qty Sold
                            </th>
                            <th className="px-4 py-2.5 text-right font-medium text-secondary-600">
                              Revenue
                            </th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-secondary-100">
                          {itemPerf.top_items
                            .slice(0, 10)
                            .map((item, index) => (
                              <tr
                                key={item.menu_item_id}
                                className="hover:bg-secondary-50"
                              >
                                <td className="px-4 py-2.5 text-center">
                                  <span
                                    className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                                      index === 0
                                        ? "bg-warning-100 text-warning-700"
                                        : index === 1
                                          ? "bg-secondary-200 text-secondary-600"
                                          : index === 2
                                            ? "bg-amber-100 text-amber-700"
                                            : "text-secondary-500"
                                    }`}
                                  >
                                    {index + 1}
                                  </span>
                                </td>
                                <td className="px-4 py-2.5 font-medium text-secondary-800">
                                  {item.name}
                                </td>
                                <td className="px-4 py-2.5 text-right text-secondary-700">
                                  {item.quantity_sold.toLocaleString()}
                                </td>
                                <td className="px-4 py-2.5 text-right font-medium text-secondary-900">
                                  {formatPKR(item.revenue)}
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="py-8 text-center text-sm text-secondary-400">
                      No item data for this period
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* bottom 5 performers */}
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <TrendingDown className="h-4 w-4 text-danger-500" />
                    <CardTitle className="text-base text-secondary-800">
                      Bottom 5 Performers
                    </CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  {itemPerf.bottom_items.length > 0 ? (
                    <div className="overflow-hidden rounded-lg border border-secondary-200">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-secondary-200 bg-secondary-50">
                            <th className="w-12 px-4 py-2.5 text-center font-medium text-secondary-600">
                              #
                            </th>
                            <th className="px-4 py-2.5 text-left font-medium text-secondary-600">
                              Item Name
                            </th>
                            <th className="px-4 py-2.5 text-right font-medium text-secondary-600">
                              Qty Sold
                            </th>
                            <th className="px-4 py-2.5 text-right font-medium text-secondary-600">
                              Revenue
                            </th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-secondary-100">
                          {itemPerf.bottom_items
                            .slice(0, 5)
                            .map((item, index) => (
                              <tr
                                key={item.menu_item_id}
                                className="hover:bg-secondary-50"
                              >
                                <td className="px-4 py-2.5 text-center text-secondary-500">
                                  {index + 1}
                                </td>
                                <td className="px-4 py-2.5 font-medium text-secondary-800">
                                  {item.name}
                                </td>
                                <td className="px-4 py-2.5 text-right text-secondary-700">
                                  {item.quantity_sold.toLocaleString()}
                                </td>
                                <td className="px-4 py-2.5 text-right font-medium text-secondary-900">
                                  {formatPKR(item.revenue)}
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="py-8 text-center text-sm text-secondary-400">
                      No underperforming items to show
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </>
      )}

      {/* empty state when loaded but no orders */}
      {!loading && !error && summary && summary.total_orders === 0 && (
        <div className="flex flex-col items-center justify-center gap-3 py-12">
          <BarChart3 className="h-12 w-12 text-secondary-300" />
          <p className="text-secondary-500">
            No orders found for the selected date range.
          </p>
        </div>
      )}
    </div>
  );
}

export default ReportsPage;
