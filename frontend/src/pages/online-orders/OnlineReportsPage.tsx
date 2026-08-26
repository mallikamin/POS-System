import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Download } from "lucide-react";
import { useConfigStore } from "@/stores/configStore";
import { fetchSalesSummary, downloadSalesCsv } from "@/services/reportsApi";
import {
  fetchPrepaidVsCod,
  downloadPrepaidVsCodCsv,
  fetchRejectedOrders,
  downloadRejectedOrdersCsv,
  fetchStripeReconciliation,
  downloadStripeReconciliationCsv,
  type PrepaidVsCodReport,
  type RejectedOrdersReport,
  type StripeReconciliationReport,
} from "@/services/onlineReportsApi";
import type { SalesSummary } from "@/types/order";
import { formatMoney } from "@/utils/currency";

/**
 * OI-58 -- a lean, branded reports view for online-ordering-only tenants.
 *
 * Deliberately NOT the general `/admin/reports` page: that page's channel
 * breakdown, waiter performance and dine-in charts are all dead weight for a
 * shop with no tables and no waiters. This is four focused tiles instead:
 * Daily Sales, Prepaid vs Cash-on-Delivery, Rejected Orders, and a Stripe
 * reconciliation (last, and collapsible -- Malik flagged it "maybe").
 *
 * Styled with the ink/flame/ember palette already used for this tenant's
 * branded emails, but the shop NAME comes from `useConfigStore` rather than
 * a hardcoded string -- the next `online_ordering_only` tenant should get
 * this page working for free, not a rewrite.
 */

function todayISO(): string {
  return new Date().toISOString().split("T")[0] ?? "";
}

function StatTile({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border border-ink-line bg-ink-soft p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-secondary-400">
        {label}
      </p>
      <p className="mt-1 text-2xl font-bold text-cream">{value}</p>
      {sub ? <p className="mt-0.5 text-xs text-secondary-400">{sub}</p> : null}
    </div>
  );
}

function DownloadButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex h-11 items-center gap-2 rounded-lg border border-ink-line bg-ink-soft px-4 text-sm font-semibold text-cream hover:border-flame"
    >
      <Download className="h-4 w-4" />
      CSV
    </button>
  );
}

export default function OnlineReportsPage() {
  const config = useConfigStore((s) => s.config);
  const fetchConfig = useConfigStore((s) => s.fetchConfig);
  // Was `config?.name`, a field the API never returns, so this had always
  // silently fallen through to the generic label. Corrected 2026-08-27 with the
  // rest of that type mismatch; the fallback stays for the pre-load frame.
  const shopName = config?.restaurant_name ?? "Online Orders";
  const currency = config?.currency ?? "GBP";

  const [dateFrom, setDateFrom] = useState(todayISO());
  const [dateTo, setDateTo] = useState(todayISO());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [sales, setSales] = useState<SalesSummary | null>(null);
  const [prepaidVsCod, setPrepaidVsCod] = useState<PrepaidVsCodReport | null>(null);
  const [rejected, setRejected] = useState<RejectedOrdersReport | null>(null);
  const [stripe, setStripe] = useState<StripeReconciliationReport | null>(null);
  const [showStripe, setShowStripe] = useState(false);

  useEffect(() => {
    // A hard refresh landing directly on this route (bookmarked, or a link
    // sent over WhatsApp) skips POSLayout's own fetchConfig() call, since
    // this page -- like /online-orders itself -- is mounted outside it.
    if (!config) void fetchConfig();
  }, [config, fetchConfig]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([
      fetchSalesSummary(dateFrom, dateTo),
      fetchPrepaidVsCod(dateFrom, dateTo),
      fetchRejectedOrders(dateFrom, dateTo),
    ])
      .then(([s, p, r]) => {
        if (cancelled) return;
        setSales(s);
        setPrepaidVsCod(p);
        setRejected(r);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load reports for this date range.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [dateFrom, dateTo]);

  // Stripe reconciliation calls Stripe once per matching order -- fetched
  // only when the section is actually opened, not on every date change.
  useEffect(() => {
    if (!showStripe) return;
    let cancelled = false;
    fetchStripeReconciliation(dateFrom, dateTo).then((data) => {
      if (!cancelled) setStripe(data);
    });
    return () => {
      cancelled = true;
    };
  }, [showStripe, dateFrom, dateTo]);

  return (
    <div className="min-h-screen bg-ink p-4 text-cream">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <Link
            to="/online-orders"
            className="mb-1 inline-flex items-center gap-1 text-sm text-secondary-400 hover:text-cream"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to orders
          </Link>
          <h1 className="text-2xl font-bold text-cream">{shopName} Reports</h1>
        </div>

        <div className="flex items-center gap-2 rounded-xl border border-ink-line bg-ink-soft p-2">
          <label className="text-sm font-medium text-secondary-400">From</label>
          <input
            type="date"
            value={dateFrom}
            max={dateTo}
            onChange={(e) => setDateFrom(e.target.value)}
            className="h-9 rounded-lg border border-ink-line bg-ink px-2 text-sm text-cream"
          />
          <label className="text-sm font-medium text-secondary-400">To</label>
          <input
            type="date"
            value={dateTo}
            min={dateFrom}
            max={todayISO()}
            onChange={(e) => setDateTo(e.target.value)}
            className="h-9 rounded-lg border border-ink-line bg-ink px-2 text-sm text-cream"
          />
        </div>
      </header>

      {error ? (
        <p className="rounded-lg border border-flame bg-ink-soft p-4 text-flame-light">
          {error}
        </p>
      ) : loading ? (
        <p className="p-8 text-center text-secondary-400">Loading…</p>
      ) : (
        <div className="flex flex-col gap-6">
          {/* Daily Sales */}
          <section>
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-cream">Daily Sales</h2>
              <DownloadButton onClick={() => void downloadSalesCsv(dateFrom, dateTo)} />
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile
                label="Online Revenue"
                value={formatMoney(sales?.online_revenue ?? 0, currency)}
              />
              <StatTile label="Online Orders" value={String(sales?.online_orders ?? 0)} />
              <StatTile
                label="Total Revenue"
                value={formatMoney(sales?.total_revenue ?? 0, currency)}
                sub="all channels"
              />
              <StatTile
                label="Avg Order Value"
                value={formatMoney(sales?.avg_order_value ?? 0, currency)}
              />
            </div>
          </section>

          {/* Prepaid vs Cash on Delivery */}
          <section>
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-cream">
                Prepaid vs Cash on Delivery
              </h2>
              <DownloadButton
                onClick={() => void downloadPrepaidVsCodCsv(dateFrom, dateTo)}
              />
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile
                label="Prepaid Revenue"
                value={formatMoney(prepaidVsCod?.prepaid_revenue ?? 0, currency)}
              />
              <StatTile
                label="Prepaid Orders"
                value={String(prepaidVsCod?.prepaid_orders ?? 0)}
              />
              <StatTile
                label="Cash on Delivery Revenue"
                value={formatMoney(prepaidVsCod?.cod_revenue ?? 0, currency)}
              />
              <StatTile
                label="Cash on Delivery Orders"
                value={String(prepaidVsCod?.cod_orders ?? 0)}
              />
            </div>
          </section>

          {/* Tips (OI-81) -- same endpoint as Prepaid vs COD, so the split
              follows the same money-actually-taken rule as revenue. */}
          <section>
            <h2 className="mb-2 text-lg font-semibold text-cream">Tips</h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile
                label="Total Tips"
                value={formatMoney(
                  (prepaidVsCod?.prepaid_tips ?? 0) + (prepaidVsCod?.cod_tips ?? 0),
                  currency,
                )}
              />
              <StatTile
                label="Card Tips"
                value={formatMoney(prepaidVsCod?.prepaid_tips ?? 0, currency)}
                sub="charged with the order"
              />
              <StatTile
                label="Cash Tips"
                value={formatMoney(prepaidVsCod?.cod_tips ?? 0, currency)}
                sub="collected with the bill"
              />
            </div>
          </section>

          {/* Rejected Orders */}
          <section>
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-cream">Rejected Orders</h2>
              <DownloadButton
                onClick={() => void downloadRejectedOrdersCsv(dateFrom, dateTo)}
              />
            </div>
            <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile label="Rejected" value={String(rejected?.count ?? 0)} />
              <StatTile
                label="Value Lost"
                value={formatMoney(rejected?.total_value ?? 0, currency)}
              />
            </div>
            {rejected && rejected.orders.length > 0 ? (
              <div className="overflow-x-auto rounded-xl border border-ink-line">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-ink-soft text-left text-secondary-400">
                      <th className="px-3 py-2">Order</th>
                      <th className="px-3 py-2">Customer</th>
                      <th className="px-3 py-2">Rejected At</th>
                      <th className="px-3 py-2">Reason</th>
                      <th className="px-3 py-2 text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-line">
                    {rejected.orders.map((o) => (
                      <tr key={o.order_number}>
                        <td className="px-3 py-2 font-semibold text-cream">
                          {o.order_number}
                        </td>
                        <td className="px-3 py-2 text-secondary-300">
                          {o.customer_name ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-secondary-300">
                          {new Date(o.rejected_at).toLocaleString("en-GB", {
                            day: "2-digit",
                            month: "short",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </td>
                        <td className="px-3 py-2 text-secondary-300">
                          {o.rejection_reason}
                        </td>
                        <td className="px-3 py-2 text-right text-cream">
                          {formatMoney(o.total, currency)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="rounded-xl border border-dashed border-ink-line p-6 text-center text-secondary-400">
                No rejected orders in this range.
              </p>
            )}
          </section>

          {/* Stripe reconciliation -- lower priority, collapsed by default */}
          <section>
            <button
              onClick={() => setShowStripe((v) => !v)}
              className="flex w-full items-center justify-between rounded-xl border border-ink-line bg-ink-soft px-4 py-3 text-left"
            >
              <span className="text-lg font-semibold text-cream">
                Stripe Reconciliation
              </span>
              <span className="text-sm text-secondary-400">
                {showStripe ? "Hide" : "Check against Stripe"}
              </span>
            </button>

            {showStripe ? (
              stripe ? (
                <div className="mt-3">
                  <div className="mb-3 flex items-center justify-between">
                    <div className="flex gap-3">
                      <StatTile label="Checked" value={String(stripe.checked)} />
                      <StatTile
                        label="Mismatches"
                        value={String(stripe.mismatches)}
                      />
                    </div>
                    <DownloadButton
                      onClick={() =>
                        void downloadStripeReconciliationCsv(dateFrom, dateTo)
                      }
                    />
                  </div>
                  {stripe.rows.length > 0 ? (
                    <div className="overflow-x-auto rounded-xl border border-ink-line">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="bg-ink-soft text-left text-secondary-400">
                            <th className="px-3 py-2">Order</th>
                            <th className="px-3 py-2">DB Status</th>
                            <th className="px-3 py-2 text-right">DB Captured</th>
                            <th className="px-3 py-2">Stripe Status</th>
                            <th className="px-3 py-2 text-right">Stripe Received</th>
                            <th className="px-3 py-2 text-center">Match</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-ink-line">
                          {stripe.rows.map((r) => (
                            <tr key={r.order_number}>
                              <td className="px-3 py-2 font-semibold text-cream">
                                {r.order_number}
                              </td>
                              <td className="px-3 py-2 text-secondary-300">
                                {r.db_payment_status}
                              </td>
                              <td className="px-3 py-2 text-right text-secondary-300">
                                {formatMoney(r.db_captured_amount, currency)}
                              </td>
                              <td className="px-3 py-2 text-secondary-300">
                                {r.error ? (
                                  <span className="text-flame-light">{r.error}</span>
                                ) : (
                                  r.stripe_status
                                )}
                              </td>
                              <td className="px-3 py-2 text-right text-secondary-300">
                                {r.stripe_amount_received != null
                                  ? formatMoney(r.stripe_amount_received, currency)
                                  : "—"}
                              </td>
                              <td className="px-3 py-2 text-center">
                                {r.matches ? (
                                  <span className="text-success-400">✓</span>
                                ) : (
                                  <span className="text-flame-light">✕</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="rounded-xl border border-dashed border-ink-line p-6 text-center text-secondary-400">
                      No card-paid online orders in this range.
                    </p>
                  )}
                </div>
              ) : (
                <p className="p-4 text-center text-secondary-400">
                  Checking against Stripe…
                </p>
              )
            ) : null}
          </section>
        </div>
      )}
    </div>
  );
}
