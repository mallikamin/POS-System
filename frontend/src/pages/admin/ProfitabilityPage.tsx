import { useEffect, useState } from "react";
import { Loader2, RefreshCw, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { formatMoney } from "@/utils/currency";
import { useConfigStore } from "@/stores/configStore";
import { fetchProfitability } from "@/services/locationsApi";
import type { ProfitabilityReport, ProfitBucket } from "@/types/location";

/** Local calendar date as YYYY-MM-DD. toISOString() would shift by timezone. */
function toDateInput(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function startOfThisMonth(): string {
  const now = new Date();
  return toDateInput(new Date(now.getFullYear(), now.getMonth(), 1));
}

function formatPct(pct: number): string {
  return `${pct.toFixed(1)}%`;
}

function profitClass(minor: number): string {
  if (minor > 0) return "text-success-600";
  if (minor < 0) return "text-danger-600";
  return "text-secondary-900";
}

function ProfitabilityPage() {
  const { toast } = useToast();
  const config = useConfigStore((s) => s.config);
  const currency = config?.currency ?? "AED";

  const [dateFrom, setDateFrom] = useState(startOfThisMonth());
  const [dateTo, setDateTo] = useState(toDateInput(new Date()));
  const [report, setReport] = useState<ProfitabilityReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void loadReport(startOfThisMonth(), toDateInput(new Date()));
  }, []);

  const rangeInvalid = dateFrom !== "" && dateTo !== "" && dateFrom > dateTo;

  async function loadReport(from: string, to: string) {
    try {
      setLoading(true);
      const data = await fetchProfitability({ date_from: from, date_to: to });
      setReport(data);
    } catch {
      toast({
        title: "Failed to load profitability report",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }

  function handleRefresh() {
    if (rangeInvalid) return;
    void loadReport(dateFrom, dateTo);
  }

  const totals: ProfitBucket | null = report?.totals ?? null;
  const totalRevenue = totals?.revenue_minor ?? 0;

  function renderBreakdown(title: string, rows: ProfitBucket[]) {
    return (
      <Card>
        <CardContent className="p-0">
          <div className="border-b border-secondary-200 px-4 py-3">
            <h2 className="font-semibold text-secondary-900">{title}</h2>
          </div>
          {rows.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-secondary-400">
              Nothing recorded in this date range.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-secondary-200 text-left text-secondary-500">
                    <th className="px-4 py-3 font-medium">Name</th>
                    <th className="px-4 py-3 font-medium text-right">Orders</th>
                    <th className="px-4 py-3 font-medium text-right">Revenue</th>
                    <th className="px-4 py-3 font-medium text-right">
                      Product Cost
                    </th>
                    <th className="px-4 py-3 font-medium text-right">
                      Commission
                    </th>
                    <th className="px-4 py-3 font-medium text-right">
                      Net Profit
                    </th>
                    <th className="px-4 py-3 font-medium text-right">
                      Net Margin
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {/* Order comes from the API already sorted by revenue desc. */}
                  {rows.map((row) => {
                    const share =
                      totalRevenue > 0
                        ? (row.revenue_minor / totalRevenue) * 100
                        : 0;
                    return (
                      <tr
                        key={row.name}
                        className="border-b border-secondary-100 last:border-0"
                      >
                        <td className="px-4 py-3">
                          <p className="font-medium text-secondary-900">
                            {row.name}
                          </p>
                          <div className="mt-1 h-1.5 w-32 rounded-full bg-secondary-100">
                            <div
                              className="h-1.5 rounded-full bg-primary-500"
                              style={{ width: `${Math.min(share, 100)}%` }}
                            />
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-secondary-700">
                          {row.orders}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-secondary-900">
                          {formatMoney(row.revenue_minor, currency)}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-secondary-700">
                          {formatMoney(row.product_cost_minor, currency)}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-secondary-700">
                          {formatMoney(row.commission_minor, currency)}
                        </td>
                        <td
                          className={`px-4 py-3 text-right tabular-nums font-semibold ${profitClass(
                            row.net_profit_minor,
                          )}`}
                        >
                          {formatMoney(row.net_profit_minor, currency)}
                        </td>
                        <td
                          className={`px-4 py-3 text-right tabular-nums ${profitClass(
                            row.net_profit_minor,
                          )}`}
                        >
                          {formatPct(row.net_margin_pct)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <TrendingUp className="h-7 w-7 text-primary-600" />
        <div>
          <h1 className="text-pos-2xl font-bold text-secondary-900">
            Profitability
          </h1>
          <p className="text-sm text-secondary-500">
            What each channel and location actually earned, after the channel
            takes its cut.
          </p>
        </div>
      </div>

      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-wrap items-end gap-4">
            <div className="space-y-2">
              <Label>From</Label>
              <Input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-44"
              />
            </div>
            <div className="space-y-2">
              <Label>To</Label>
              <Input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-44"
              />
            </div>
            <Button
              onClick={handleRefresh}
              disabled={loading || rangeInvalid}
              className="gap-2 min-h-[48px]"
            >
              <RefreshCw
                className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
              />
              Refresh
            </Button>
          </div>
          {rangeInvalid && (
            <p className="mt-3 text-xs text-danger-600">
              The start date is after the end date.
            </p>
          )}
          <p className="mt-4 rounded-lg bg-secondary-50 px-3 py-2 text-sm text-secondary-600">
            Net Profit = Revenue - Product Cost - Channel Commission. A delivery
            app order and a direct order for the same basket do not earn the
            same money, because the app keeps a commission on its own.
          </p>
        </CardContent>
      </Card>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
        </div>
      ) : !totals || totals.orders === 0 ? (
        <Card>
          <CardContent className="py-12 text-center space-y-2">
            <p className="font-semibold text-secondary-900">
              No orders between {dateFrom} and {dateTo}
            </p>
            <p className="mx-auto max-w-xl text-sm text-secondary-500">
              Pick a wider date range, or check that orders in this period have
              been completed. Commission is only counted once an order is
              attributed to a sales channel.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Card>
              <CardContent className="pt-4">
                <p className="text-sm text-secondary-500">Revenue</p>
                <p className="mt-1 text-xl font-bold tabular-nums text-secondary-900">
                  {formatMoney(totals.revenue_minor, currency)}
                </p>
                <p className="mt-1 text-xs text-secondary-400">
                  {totals.orders} orders
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <p className="text-sm text-secondary-500">Product Cost</p>
                <p className="mt-1 text-xl font-bold tabular-nums text-secondary-900">
                  {formatMoney(totals.product_cost_minor, currency)}
                </p>
                <p className="mt-1 text-xs text-secondary-400">
                  Ingredients used
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <p className="text-sm text-secondary-500">Channel Commission</p>
                <p className="mt-1 text-xl font-bold tabular-nums text-warning-700">
                  {formatMoney(totals.commission_minor, currency)}
                </p>
                <p className="mt-1 text-xs text-secondary-400">
                  Kept by the channels
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <p className="text-sm text-secondary-500">Net Profit</p>
                <p
                  className={`mt-1 text-xl font-bold tabular-nums ${profitClass(
                    totals.net_profit_minor,
                  )}`}
                >
                  {formatMoney(totals.net_profit_minor, currency)}
                </p>
                <p className="mt-1 text-xs text-secondary-400">
                  After cost and commission
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <p className="text-sm text-secondary-500">Net Margin</p>
                <p
                  className={`mt-1 text-xl font-bold tabular-nums ${profitClass(
                    totals.net_profit_minor,
                  )}`}
                >
                  {formatPct(totals.net_margin_pct)}
                </p>
                <p className="mt-1 text-xs text-secondary-400">
                  Share of revenue kept
                </p>
              </CardContent>
            </Card>
          </div>

          {renderBreakdown("By Sales Channel", report?.by_channel ?? [])}
          {renderBreakdown("By Location", report?.by_location ?? [])}
        </>
      )}
    </div>
  );
}

export default ProfitabilityPage;
