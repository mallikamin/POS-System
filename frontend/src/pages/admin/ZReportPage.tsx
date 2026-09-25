import { useEffect, useState } from "react";
import { toLocalISODate } from "@/utils/localDate";
import { currencyLocale } from "@/utils/currency";
import {
  FileText,
  Loader2,
  Printer,
  DollarSign,
  ShoppingCart,
  CreditCard,
  TrendingUp,
  RotateCcw,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { formatPKR } from "@/utils/currency";
import { useConfigStore } from "@/stores/configStore";
import api from "@/lib/axios";

/*
 * D-60 daily summary sections. Ingredient quantities and costs arrive as
 * JSON numbers; costs are MINOR units (possibly fractional), so they go
 * through formatPKR like every other amount on this page.
 */
interface InventoryUsedRow {
  ingredient_id: string;
  ingredient_name: string;
  unit: string;
  sold_quantity: number;
  sold_cost: number;
  production_quantity: number;
  production_cost: number;
  waste_quantity: number;
  waste_cost: number;
  adjustment_quantity: number;
  adjustment_cost: number;
  used_cost: number;
  costed_at_current_price: boolean;
}

interface InventoryUsed {
  rows: InventoryUsedRow[];
  total_sold_cost: number;
  total_production_cost: number;
  total_waste_cost: number;
  total_adjustment_cost: number;
  total_cost_of_goods_used: number;
}

interface StockLeftRow {
  location_id: string;
  location_name: string;
  ingredient_id: string;
  ingredient_name: string;
  unit: string;
  closing_quantity: number;
  reorder_point: number;
  is_low: boolean;
}

interface StockLeft {
  as_of: string;
  multiple_locations: boolean;
  low_count: number;
  rows: StockLeftRow[];
}

interface DrawerPosition {
  session_status: string;
  opened_at: string;
  closed_at: string | null;
  opening_float: number;
  cash_taken: number;
  cash_refunds: number;
  cash_paid_out: number;
  expected_in_drawer: number;
  counted_closing: number | null;
  over_short: number | null;
}

interface CashPosition {
  cash_taken: number;
  cash_refunds: number;
  cash_paid_out: number;
  cash_expenses: { payee: string; payment_method: string; amount: number }[];
  net_cash: number;
  drawer_opened: boolean;
  drawers: DrawerPosition[];
}

interface ZReport {
  date: string;
  generated_at: string;
  generated_by: string;
  total_orders: number;
  total_revenue: number;
  total_tax: number;
  total_discount: number;
  net_revenue: number;
  settled_orders: number;
  fully_refunded_orders: number;
  net_tax: number;
  by_channel: { channel: string; orders: number; revenue: number }[];
  by_payment_method: {
    method: string;
    count: number;
    total: number;
    payment_count: number;
    refund_count: number;
    gross_total: number;
    refund_total: number;
    net_total: number;
  }[];
  by_status: { status: string; count: number }[];
  top_items: { name: string; quantity: number; revenue: number }[];
  inventory_used: InventoryUsed;
  stock_left: StockLeft;
  cash_position: CashPosition;
}

function formatQty(qty: number): string {
  return qty.toLocaleString(currencyLocale(), { maximumFractionDigits: 3 });
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(currencyLocale(), {
    hour: "2-digit",
    minute: "2-digit",
  });
}

const sectionTitle =
  "font-semibold text-secondary-800 print:text-sm print:font-bold print:uppercase print:tracking-wide print:border-b print:border-gray-300 print:pb-1";
const printCard =
  "print:border print:border-gray-300 print:shadow-none print:rounded-none";

const channelLabels: Record<string, string> = {
  dine_in: "Dine-In",
  takeaway: "Takeaway",
  call_center: "Call Center",
};

/**
 * The tenant's own word for the walk-in channel wins.
 *
 * Martin renamed Takeaway to "Pick up" in round 1 and the till honours it, but
 * this report still printed "Takeaway" at close of day. Found in UAT on
 * 2026-09-06. `takeaway_label` is the same config field the POS header reads.
 */
function channelLabel(channel: string, takeawayLabel?: string | null): string {
  if (channel === "takeaway" && takeawayLabel) return takeawayLabel;
  return channelLabels[channel] ?? channel;
}

function getToday(): string {
  return toLocalISODate();
}

function ZReportPage() {
  const { toast } = useToast();
  const [selectedDate, setSelectedDate] = useState(getToday);
  const [report, setReport] = useState<ZReport | null>(null);
  const [loading, setLoading] = useState(false);

  // `formatPKR`/`formatMoney` read a currency that is set once, globally, by
  // configStore.fetchConfig() -- normally already done by POSLayout before
  // any page renders. A hard refresh or a bookmarked/WhatsApp-linked landing
  // directly on this route skips that mount (same gap OnlineReportsPage.tsx
  // already closed for itself), so amounts rendered on the FIRST paint here
  // used whatever currency was last set, defaulting to PKR for a session
  // that never went through POSLayout at all -- confirmed as the cause of
  // Imran's GBP tenant printing a Z-Report in PKR (voice note, 2026-08-03).
  // Subscribing to `config` guarantees a re-render once fetchConfig()
  // resolves, which is what actually picks up the corrected currency.
  const config = useConfigStore((s) => s.config);
  const fetchConfig = useConfigStore((s) => s.fetchConfig);

  useEffect(() => {
    if (!config) void fetchConfig();
  }, [config, fetchConfig]);

  useEffect(() => {
    if (selectedDate) fetchReport();
  }, [selectedDate]);

  async function fetchReport() {
    try {
      setLoading(true);
      const { data } = await api.get<ZReport>(
        `/reports/z-report?date=${selectedDate}`
      );
      setReport(data);
    } catch {
      toast({ title: "Failed to load Z-Report", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }

  function handlePrint() {
    window.print();
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div className="print-clean">
      {/* ===== SCREEN HEADER (hidden in print) ===== */}
      <div className="mb-6 flex items-center justify-between print:hidden">
        <div className="flex items-center gap-3">
          <FileText className="h-7 w-7 text-primary-600" />
          <h1 className="text-pos-2xl font-bold text-secondary-900">
            Z-Report / Daily Settlement
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="min-h-[48px] rounded-md border border-secondary-300 px-3 text-pos-sm"
          />
          <Button
            onClick={handlePrint}
            disabled={!report}
            className="min-h-[48px] gap-2"
          >
            <Printer className="h-4 w-4" />
            Print
          </Button>
        </div>
      </div>

      {/* ===== PRINT HEADER (hidden on screen) ===== */}
      <div className="hidden print:block print:mb-6">
        <div className="border-b-2 border-black pb-3 mb-4">
          <h1 className="text-xl font-bold text-center">Z-Report — Daily Settlement</h1>
          <p className="text-center text-sm mt-1">Date: {selectedDate}</p>
          {report && (
            <p className="text-center text-xs text-gray-500 mt-1">
              Generated by {report.generated_by} at{" "}
              {new Date(report.generated_at).toLocaleString(currencyLocale())}
            </p>
          )}
        </div>
      </div>

      {!report ? (
        <div className="py-12 text-center text-secondary-500">
          No data for this date.
        </div>
      ) : (
        <div className="space-y-6 print:space-y-4">
          {/* ===== KPI SUMMARY ===== */}
          {/* Screen: card grid */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-5 print:hidden">
            <KpiCard
              icon={<ShoppingCart className="h-5 w-5" />}
              label="Settled Orders"
              value={report.settled_orders.toString()}
            />
            <KpiCard
              icon={<RotateCcw className="h-5 w-5" />}
              label="Fully Refunded"
              value={report.fully_refunded_orders.toString()}
            />
            <KpiCard
              icon={<DollarSign className="h-5 w-5" />}
              label="Net Revenue"
              value={formatPKR(report.net_revenue)}
            />
            <KpiCard
              icon={<TrendingUp className="h-5 w-5" />}
              label="Net Tax Collected"
              value={formatPKR(report.net_tax)}
            />
            <KpiCard
              icon={<CreditCard className="h-5 w-5" />}
              label="Discounts"
              value={formatPKR(report.total_discount)}
            />
          </div>

          {/* Print: compact summary table */}
          <div className="hidden print:block print-section">
            <h2 className="text-sm font-bold uppercase tracking-wide border-b border-gray-300 pb-1 mb-2">Summary</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <tbody>
                  <tr><td className="py-1">Settled Orders</td><td className="py-1 text-right font-semibold">{report.settled_orders}</td></tr>
                  <tr><td className="py-1">Fully Refunded Orders</td><td className="py-1 text-right font-semibold">{report.fully_refunded_orders}</td></tr>
                  <tr><td className="py-1">Net Revenue</td><td className="py-1 text-right font-semibold">{formatPKR(report.net_revenue)}</td></tr>
                  <tr><td className="py-1">Net Tax Collected</td><td className="py-1 text-right font-semibold">{formatPKR(report.net_tax)}</td></tr>
                  <tr><td className="py-1">Discounts</td><td className="py-1 text-right font-semibold">{formatPKR(report.total_discount)}</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* ===== DETAIL SECTIONS ===== */}
          <div className="grid gap-6 lg:grid-cols-2 print:grid-cols-2 print:gap-4">
            {/* Cash Position (replaces the old Cash Drawer card, D-60) */}
            <CashPositionCard cash={report.cash_position} />

            {/* By Channel */}
            <Card className="print:border print:border-gray-300 print:shadow-none print:rounded-none">
              <CardContent className="space-y-3 pt-6 print:pt-3 print:px-3">
                <h2 className="font-semibold text-secondary-800 print:text-sm print:font-bold print:uppercase print:tracking-wide print:border-b print:border-gray-300 print:pb-1">
                  Sales by Channel
                </h2>
                {report.by_channel.length === 0 ? (
                  <p className="text-pos-sm text-secondary-500">No sales</p>
                ) : (
                  <div className="space-y-2 text-pos-sm print:space-y-0 print:text-xs">
                    {report.by_channel.map((ch) => (
                      <div
                        key={ch.channel}
                        className="flex items-center justify-between rounded-lg bg-secondary-50 px-3 py-2 print:rounded-none print:bg-transparent print:px-0 print:py-1 print:border-b print:border-gray-100"
                      >
                        <span className="font-medium">
                          {channelLabel(ch.channel, config?.takeaway_label)}
                        </span>
                        <span>
                          {ch.orders} orders — {formatPKR(ch.revenue)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* By Payment Method */}
            <Card className="print:border print:border-gray-300 print:shadow-none print:rounded-none">
              <CardContent className="space-y-3 pt-6 print:pt-3 print:px-3">
                <h2 className="font-semibold text-secondary-800 print:text-sm print:font-bold print:uppercase print:tracking-wide print:border-b print:border-gray-300 print:pb-1">
                  By Payment Method (Net)
                </h2>
                {report.by_payment_method.length === 0 ? (
                  <p className="text-pos-sm text-secondary-500">
                    No payments recorded
                  </p>
                ) : (
                  <div className="space-y-2 text-pos-sm print:space-y-0 print:text-xs">
                    {report.by_payment_method.map((pm) => (
                      <div
                        key={pm.method}
                        className="flex items-center justify-between rounded-lg bg-secondary-50 px-3 py-2 print:rounded-none print:bg-transparent print:px-0 print:py-1 print:border-b print:border-gray-100"
                      >
                        <div>
                          <div className="font-medium">{pm.method}</div>
                          <div className="text-xs text-secondary-500">
                            {pm.payment_count} payment{pm.payment_count === 1 ? "" : "s"}
                            {pm.refund_count > 0
                              ? ` | ${pm.refund_count} refund${pm.refund_count === 1 ? "" : "s"}`
                              : ""}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-semibold">
                            {formatPKR(pm.net_total)}
                          </div>
                          <div className="text-xs text-secondary-500">
                            Gross {formatPKR(pm.gross_total)}
                            {pm.refund_total > 0
                              ? ` | Refunds -${formatPKR(pm.refund_total)}`
                              : ""}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Order Status Breakdown */}
            <Card className="print:border print:border-gray-300 print:shadow-none print:rounded-none">
              <CardContent className="space-y-3 pt-6 print:pt-3 print:px-3">
                <h2 className="font-semibold text-secondary-800 print:text-sm print:font-bold print:uppercase print:tracking-wide print:border-b print:border-gray-300 print:pb-1">
                  Order Status
                </h2>
                <div className="flex flex-wrap gap-2 print:gap-1">
                  {report.by_status.map((s) => (
                    <Badge key={s.status} variant="outline" className="text-pos-sm print:text-xs print:rounded-none print:border-gray-400">
                      {s.status}: {s.count}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Top Items */}
          {report.top_items.length > 0 && (
            <Card className="print:border print:border-gray-300 print:shadow-none print:rounded-none print-section">
              <CardContent className="pt-6 print:pt-3 print:px-3">
                <h2 className="mb-3 font-semibold text-secondary-800 print:text-sm print:font-bold print:uppercase print:tracking-wide print:border-b print:border-gray-300 print:pb-1 print:mb-2">
                  Top 10 Items
                </h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-pos-sm print:text-xs">
                    <thead>
                      <tr className="border-b text-secondary-500 print:text-gray-600">
                        <th className="pb-2 font-medium print:pb-1">#</th>
                        <th className="pb-2 font-medium print:pb-1">Item</th>
                        <th className="pb-2 font-medium text-right print:pb-1">Qty</th>
                        <th className="pb-2 font-medium text-right print:pb-1">Revenue</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.top_items.map((item, i) => (
                        <tr key={i} className="border-b last:border-0">
                          <td className="py-2 text-secondary-500 print:py-1">{i + 1}</td>
                          <td className="py-2 font-medium print:py-1">{item.name}</td>
                          <td className="py-2 text-right print:py-1">{item.quantity}</td>
                          <td className="py-2 text-right print:py-1">
                            {formatPKR(item.revenue)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Inventory used + stock left (D-60) */}
          <InventoryUsedCard used={report.inventory_used} />
          <StockLeftCard left={report.stock_left} />

          {/* Print footer */}
          <div className="hidden print:block print:mt-6 print:pt-3 print:border-t print:border-gray-300 print:text-center print:text-xs print:text-gray-400">
            End of Z-Report — {selectedDate}
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------- D-60 daily summary sections ---------- */

function overShortVariant(v: number): "neutral" | "positive" | "negative" {
  if (v === 0) return "neutral";
  return v > 0 ? "positive" : "negative";
}

function CashPositionCard({ cash }: { cash: CashPosition }) {
  return (
    <Card className={printCard}>
      <CardContent className="space-y-3 pt-6 print:pt-3 print:px-3">
        <h2 className={sectionTitle}>Cash Position</h2>
        <div className="space-y-1 text-pos-sm print:text-xs">
          <Row label="Cash taken (sales)" value={formatPKR(cash.cash_taken)} />
          <Row label="Cash refunds" value={`-${formatPKR(cash.cash_refunds)}`} />
          <Row label="Cash paid out (expenses)" value={`-${formatPKR(cash.cash_paid_out)}`} />
          {cash.cash_expenses.map((e, i) => (
            <div
              key={i}
              className="flex justify-between pl-4 text-xs text-secondary-500 print:text-gray-600"
            >
              <span>
                {e.payee} ({e.payment_method})
              </span>
              <span>-{formatPKR(e.amount)}</span>
            </div>
          ))}
          <div className="border-t pt-1" />
          <Row label="Net cash for the day" value={formatPKR(cash.net_cash)} bold />
        </div>

        {!cash.drawer_opened ? (
          <p className="rounded-md bg-amber-50 px-3 py-2 text-pos-sm text-amber-800 print:bg-transparent print:px-0 print:text-xs print:text-black">
            No cash drawer was opened this day, so there is no opening float or
            counted amount to compare against.
          </p>
        ) : (
          cash.drawers.map((d, i) => (
            <div
              key={i}
              className="space-y-1 border-t pt-2 text-pos-sm print:text-xs"
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold">
                  Drawer {formatTime(d.opened_at)}
                  {d.closed_at ? ` to ${formatTime(d.closed_at)}` : ""}
                </span>
                <Badge
                  className={`print:hidden ${
                    d.session_status === "open"
                      ? "bg-green-100 text-green-800"
                      : "bg-secondary-100 text-secondary-600"
                  }`}
                >
                  {d.session_status}
                </Badge>
                <span className="hidden print:inline">({d.session_status})</span>
              </div>
              <Row label="Opening float" value={formatPKR(d.opening_float)} />
              <Row label="Cash taken" value={formatPKR(d.cash_taken)} />
              <Row label="Cash refunds" value={`-${formatPKR(d.cash_refunds)}`} />
              <Row label="Cash paid out" value={`-${formatPKR(d.cash_paid_out)}`} />
              <Row
                label="Should be in drawer"
                value={formatPKR(d.expected_in_drawer)}
                bold
              />
              {d.counted_closing != null && d.over_short != null ? (
                <>
                  <Row label="Counted at close" value={formatPKR(d.counted_closing)} />
                  <Row
                    label={d.over_short >= 0 ? "Over" : "Short"}
                    value={formatPKR(Math.abs(d.over_short))}
                    bold
                    variant={overShortVariant(d.over_short)}
                  />
                </>
              ) : (
                <p className="text-xs text-secondary-500">Not counted yet.</p>
              )}
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function InventoryUsedCard({ used }: { used: InventoryUsed }) {
  const showProduction = used.rows.some((r) => r.production_quantity !== 0);
  const showWaste = used.rows.some((r) => r.waste_quantity !== 0);
  const showAdjust = used.rows.some((r) => r.adjustment_quantity !== 0);
  const anyCurrentPrice = used.rows.some((r) => r.costed_at_current_price);

  return (
    <Card className={`${printCard} print-section`}>
      <CardContent className="pt-6 print:pt-3 print:px-3">
        <h2 className={`mb-3 print:mb-2 ${sectionTitle}`}>Inventory Used</h2>
        {used.rows.length === 0 ? (
          <p className="text-pos-sm text-secondary-500">
            No stock was used this day.
          </p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-pos-sm print:text-xs">
                <thead>
                  <tr className="border-b text-secondary-500 print:text-gray-600">
                    <th className="pb-2 font-medium print:pb-1">Ingredient</th>
                    <th className="pb-2 font-medium text-right print:pb-1">Sold</th>
                    {showProduction && (
                      <th className="pb-2 font-medium text-right print:pb-1">Production</th>
                    )}
                    {showWaste && (
                      <th className="pb-2 font-medium text-right print:pb-1">Waste</th>
                    )}
                    {showAdjust && (
                      <th className="pb-2 font-medium text-right print:pb-1">Adjusted</th>
                    )}
                    <th className="pb-2 font-medium text-right print:pb-1">Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {used.rows.map((r) => (
                    <tr key={r.ingredient_id} className="border-b last:border-0">
                      <td className="py-2 font-medium print:py-1">
                        {r.ingredient_name}
                        {r.costed_at_current_price ? " *" : ""}
                      </td>
                      <td className="py-2 text-right print:py-1">
                        {formatQty(r.sold_quantity)} {r.unit}
                      </td>
                      {showProduction && (
                        <td className="py-2 text-right print:py-1">
                          {formatQty(r.production_quantity)} {r.unit}
                        </td>
                      )}
                      {showWaste && (
                        <td className="py-2 text-right print:py-1">
                          {formatQty(r.waste_quantity)} {r.unit}
                        </td>
                      )}
                      {showAdjust && (
                        <td className="py-2 text-right print:py-1">
                          {r.adjustment_quantity > 0 ? "+" : ""}
                          {formatQty(r.adjustment_quantity)} {r.unit}
                        </td>
                      )}
                      <td className="py-2 text-right print:py-1">
                        {formatPKR(r.used_cost)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 space-y-1 border-t pt-2 text-pos-sm print:text-xs">
              <Row label="Cost of goods sold" value={formatPKR(used.total_sold_cost)} />
              {showWaste && (
                <Row label="Waste" value={formatPKR(used.total_waste_cost)} />
              )}
              <Row
                label="Total cost of goods used"
                value={formatPKR(used.total_cost_of_goods_used)}
                bold
              />
              {showProduction && (
                <Row
                  label="Used making in-house items (not in total)"
                  value={formatPKR(used.total_production_cost)}
                />
              )}
              {showAdjust && (
                <Row
                  label="Manual adjustments (not in total)"
                  value={formatPKR(used.total_adjustment_cost)}
                />
              )}
            </div>
            <p className="mt-2 text-xs text-secondary-500 print:text-gray-600">
              Sales are counted on the day the order completed.
              {showAdjust ? " Row cost excludes manual adjustments." : ""}
              {anyCurrentPrice
                ? " * No cost was recorded when this stock moved; priced at today's cost."
                : ""}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function StockLeftCard({ left }: { left: StockLeft }) {
  return (
    <Card className={`${printCard} print-section`}>
      <CardContent className="pt-6 print:pt-3 print:px-3">
        <h2 className={`mb-3 print:mb-2 ${sectionTitle}`}>
          Stock Left at Close
          {left.low_count > 0 && (
            <span className="ml-2 text-pos-sm font-normal text-red-600 print:text-xs print:text-black">
              ({left.low_count} at or below reorder point)
            </span>
          )}
        </h2>
        {left.rows.length === 0 ? (
          <p className="text-pos-sm text-secondary-500">No stock is tracked.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-pos-sm print:text-xs">
              <thead>
                <tr className="border-b text-secondary-500 print:text-gray-600">
                  {left.multiple_locations && (
                    <th className="pb-2 font-medium print:pb-1">Location</th>
                  )}
                  <th className="pb-2 font-medium print:pb-1">Ingredient</th>
                  <th className="pb-2 font-medium text-right print:pb-1">Left</th>
                  <th className="pb-2 font-medium text-right print:pb-1">Reorder at</th>
                  <th className="pb-2 font-medium text-right print:pb-1" />
                </tr>
              </thead>
              <tbody>
                {left.rows.map((r) => (
                  <tr
                    key={`${r.location_id}-${r.ingredient_id}`}
                    className={`border-b last:border-0 ${r.is_low ? "bg-red-50 print:bg-transparent" : ""}`}
                  >
                    {left.multiple_locations && (
                      <td className="py-2 print:py-1">{r.location_name}</td>
                    )}
                    <td className="py-2 font-medium print:py-1">{r.ingredient_name}</td>
                    <td className="py-2 text-right print:py-1">
                      {formatQty(r.closing_quantity)} {r.unit}
                    </td>
                    <td className="py-2 text-right text-secondary-500 print:py-1 print:text-gray-600">
                      {r.reorder_point > 0 ? `${formatQty(r.reorder_point)} ${r.unit}` : "-"}
                    </td>
                    <td className="py-2 text-right font-semibold text-red-600 print:py-1 print:text-black">
                      {r.is_low ? "LOW" : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ---------- helpers ---------- */

function KpiCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 pt-6">
        <div className="rounded-lg bg-primary-100 p-2 text-primary-600">
          {icon}
        </div>
        <div>
          <p className="text-pos-sm text-secondary-500">{label}</p>
          <p className="text-pos-lg font-bold text-secondary-900">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function Row({
  label,
  value,
  bold,
  variant,
}: {
  label: string;
  value: string;
  bold?: boolean;
  variant?: "neutral" | "positive" | "negative";
}) {
  const variantClass =
    variant === "positive"
      ? "text-green-600"
      : variant === "negative"
        ? "text-red-600"
        : "";

  return (
    <div className="flex justify-between">
      <span className={bold ? "font-semibold" : ""}>{label}</span>
      <span className={`${bold ? "font-semibold" : ""} ${variantClass}`}>
        {value}
      </span>
    </div>
  );
}

export default ZReportPage;
