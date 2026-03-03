import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { CreditCard, Loader2, RefreshCw } from "lucide-react";
import { isAxiosError } from "axios";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatPKR, rupeesToPaisa, paisaToRupees } from "@/utils/currency";
import * as paymentsApi from "@/services/paymentsApi";
import type {
  PaymentMethodCode,
  SessionPaymentPreview,
  SessionPaymentSummary,
  SplitPaymentAllocation,
} from "@/types/payment";

type Mode = "cash" | "card" | "split";

function parseRupees(value: string): number {
  const numeric = Number(value || "0");
  return Number.isFinite(numeric) && numeric > 0 ? rupeesToPaisa(numeric) : 0;
}

function getErrorMessage(err: unknown, fallback: string): string {
  if (isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    return typeof detail === "string" ? detail : fallback;
  }
  return fallback;
}

function SessionPaymentPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("cash");
  const [summary, setSummary] = useState<SessionPaymentSummary | null>(null);
  const [preview, setPreview] = useState<SessionPaymentPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [cashAmount, setCashAmount] = useState("");
  const [cashTendered, setCashTendered] = useState("");
  const [cardAmount, setCardAmount] = useState("");
  const [cardReference, setCardReference] = useState("");
  const [splitRows, setSplitRows] = useState<Array<{ method: PaymentMethodCode; amount: string; reference: string }>>([
    { method: "cash", amount: "", reference: "" },
    { method: "card", amount: "", reference: "" },
  ]);

  const dueDisplay = useMemo(() => (summary ? formatPKR(summary.due_amount) : "--"), [summary]);

  useEffect(() => {
    if (!sessionId) return;
    void loadData(sessionId);
  }, [sessionId]);

  async function loadData(id: string) {
    setLoading(true);
    setError(null);
    try {
      const [s, p] = await Promise.all([
        paymentsApi.fetchSessionPaymentSummary(id),
        paymentsApi.fetchSessionPaymentPreview(id),
      ]);
      setSummary(s);
      setPreview(p);
      if (s.due_amount > 0) {
        const dueRupees = String(paisaToRupees(s.due_amount));
        setCashAmount(dueRupees);
        setCardAmount(dueRupees);
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to load session payment data"));
    } finally {
      setLoading(false);
    }
  }

  async function handleCashPayment() {
    if (!sessionId) return;
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const next = await paymentsApi.createSessionPayment(sessionId, {
        method_code: "cash",
        amount: parseRupees(cashAmount),
        tendered_amount: parseRupees(cashTendered) || undefined,
      });
      setSummary(next);
      const tenderedPaisa = parseRupees(cashTendered);
      const amountPaisa = parseRupees(cashAmount);
      if (tenderedPaisa > amountPaisa) {
        setSuccess(`Cash payment recorded. Change: ${formatPKR(tenderedPaisa - amountPaisa)}`);
      } else {
        setSuccess("Cash payment recorded.");
      }
      setCashAmount("");
      setCashTendered("");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to record cash payment"));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCardPayment() {
    if (!sessionId) return;
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const next = await paymentsApi.createSessionPayment(sessionId, {
        method_code: "card",
        amount: parseRupees(cardAmount),
        reference: cardReference || undefined,
      });
      setSummary(next);
      setSuccess("Card payment recorded.");
      setCardAmount("");
      setCardReference("");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to record card payment"));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSplitPayment() {
    if (!sessionId) return;
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const allocations: SplitPaymentAllocation[] = splitRows
        .map((row) => ({
          method_code: row.method,
          amount: parseRupees(row.amount),
          reference: row.reference || undefined,
        }))
        .filter((row) => row.amount > 0);

      const next = await paymentsApi.splitSessionPayment(sessionId, { allocations });
      setSummary(next);
      setSuccess("Split payment recorded.");
      setSplitRows([
        { method: "cash", amount: "", reference: "" },
        { method: "card", amount: "", reference: "" },
      ]);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to record split payment"));
    } finally {
      setSubmitting(false);
    }
  }

  if (!sessionId) {
    return <div className="p-6 text-danger-700">Missing session id.</div>;
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-4 p-4 md:p-6">
      {/* Header */}
      <div className="flex items-center justify-between rounded-xl border border-secondary-200 bg-white px-4 py-3">
        <div className="flex items-center gap-3">
          <CreditCard className="h-5 w-5 text-primary-600" />
          <div>
            <h2 className="text-lg font-semibold text-secondary-900">Settle Table Session</h2>
            <p className="text-xs text-secondary-500">
              {summary?.table_label ? `Table ${summary.table_label}` : "Table"} — {summary?.order_count ?? 0} order{(summary?.order_count ?? 0) !== 1 ? "s" : ""}
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-xs text-secondary-500">Due</p>
          <p className="text-lg font-semibold text-secondary-900">{dueDisplay}</p>
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 print:hidden">
        <Button variant="outline" size="sm" onClick={() => navigate(-1)}>
          Back
        </Button>
        <Button variant="outline" size="sm" disabled={submitting} onClick={() => void loadData(sessionId)}>
          <RefreshCw className="mr-1 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {error && <div className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{error}</div>}
      {success && <div className="rounded-lg bg-success-50 px-3 py-2 text-sm text-success-700">{success}</div>}

      {/* Per-order breakdown */}
      {summary && summary.orders.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Order Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-hidden rounded-lg border border-secondary-200">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-secondary-200 bg-secondary-50">
                    <th className="px-4 py-2.5 text-left font-medium text-secondary-600">Order #</th>
                    <th className="px-4 py-2.5 text-right font-medium text-secondary-600">Total</th>
                    <th className="px-4 py-2.5 text-right font-medium text-secondary-600">Paid</th>
                    <th className="px-4 py-2.5 text-right font-medium text-secondary-600">Due</th>
                    <th className="px-4 py-2.5 text-right font-medium text-secondary-600">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-secondary-100">
                  {summary.orders.map((o) => (
                    <tr key={o.order_id} className="hover:bg-secondary-50">
                      <td className="px-4 py-2.5 text-secondary-700">{o.order_number}</td>
                      <td className="px-4 py-2.5 text-right">{formatPKR(o.order_total)}</td>
                      <td className="px-4 py-2.5 text-right">{formatPKR(o.paid_amount)}</td>
                      <td className="px-4 py-2.5 text-right font-medium">{formatPKR(o.due_amount)}</td>
                      <td className="px-4 py-2.5 text-right">
                        <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                          o.payment_status === "paid" ? "bg-success-100 text-success-700"
                            : o.payment_status === "partial" ? "bg-amber-100 text-amber-700"
                            : "bg-secondary-100 text-secondary-600"
                        }`}>
                          {o.payment_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Bill totals by payment method */}
      {preview && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Bill Totals by Payment Method</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-lg border-2 border-green-200 bg-green-50 p-3 text-center">
                <p className="text-xs font-medium text-green-700">Cash ({preview.cash_tax_rate_bps / 100}% tax)</p>
                <p className="text-lg font-bold text-green-800">{formatPKR(preview.cash_total)}</p>
                <p className="text-xs text-green-600">Tax: {formatPKR(preview.cash_tax_amount)}</p>
              </div>
              <div className="rounded-lg border-2 border-blue-200 bg-blue-50 p-3 text-center">
                <p className="text-xs font-medium text-blue-700">Card ({preview.card_tax_rate_bps / 100}% tax)</p>
                <p className="text-lg font-bold text-blue-800">{formatPKR(preview.card_total)}</p>
                <p className="text-xs text-blue-600">Tax: {formatPKR(preview.card_tax_amount)}</p>
              </div>
            </div>
            <p className="mt-2 text-center text-xs text-secondary-400">Subtotal: {formatPKR(preview.subtotal)}</p>
          </CardContent>
        </Card>
      )}

      {/* Session summary totals */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Session Totals</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="flex justify-between"><span className="text-secondary-500">Subtotal</span><span>{summary ? formatPKR(summary.subtotal) : "--"}</span></div>
          {preview ? (
            <>
              <div className="flex justify-between"><span className="text-secondary-500">Cash Tax ({preview.cash_tax_rate_bps / 100}%)</span><span>{formatPKR(preview.cash_tax_amount)}</span></div>
              <div className="flex justify-between"><span className="text-secondary-500">Card Tax ({preview.card_tax_rate_bps / 100}%)</span><span>{formatPKR(preview.card_tax_amount)}</span></div>
            </>
          ) : (
            <div className="flex justify-between"><span className="text-secondary-500">Tax</span><span>{summary ? formatPKR(summary.tax_amount) : "--"}</span></div>
          )}
          {!!summary && summary.discount_amount > 0 && (
            <div className="flex justify-between"><span className="text-amber-600">Discount</span><span className="text-amber-700">-{formatPKR(summary.discount_amount)}</span></div>
          )}
          <div className="flex justify-between"><span className="text-secondary-500">Paid</span><span>{summary ? formatPKR(summary.paid_amount) : "--"}</span></div>
          <div className="flex justify-between border-t border-secondary-200 pt-2 text-base font-bold">
            <span>Due</span>
            <span>{dueDisplay}</span>
          </div>
        </CardContent>
      </Card>

      {/* Payment mode */}
      {summary && summary.due_amount > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Payment Mode</CardTitle>
            <div className="flex gap-2">
              <Button variant={mode === "cash" ? "default" : "outline"} size="sm" onClick={() => setMode("cash")}>Cash</Button>
              <Button variant={mode === "card" ? "default" : "outline"} size="sm" onClick={() => setMode("card")}>Card</Button>
              <Button variant={mode === "split" ? "default" : "outline"} size="sm" onClick={() => setMode("split")}>Split</Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {mode === "cash" && (
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <Label>Amount (PKR)</Label>
                  <Input value={cashAmount} onChange={(e) => setCashAmount(e.target.value)} placeholder="0" type="number" min="0" />
                </div>
                <div>
                  <Label>Tendered (PKR)</Label>
                  <Input value={cashTendered} onChange={(e) => setCashTendered(e.target.value)} placeholder="0" type="number" min="0" />
                </div>
                <div className="md:col-span-2">
                  <Button onClick={handleCashPayment} disabled={submitting}>Post Cash Payment</Button>
                </div>
              </div>
            )}

            {mode === "card" && (
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <Label>Amount (PKR)</Label>
                  <Input value={cardAmount} onChange={(e) => setCardAmount(e.target.value)} placeholder="0" type="number" min="0" />
                </div>
                <div>
                  <Label>Reference</Label>
                  <Input value={cardReference} onChange={(e) => setCardReference(e.target.value)} placeholder="Last 4 / txn id" />
                </div>
                <div className="md:col-span-2">
                  <Button onClick={handleCardPayment} disabled={submitting}>Post Card Payment</Button>
                </div>
              </div>
            )}

            {mode === "split" && (
              <div className="space-y-2">
                {splitRows.map((row, idx) => (
                  <div key={idx} className="grid gap-2 md:grid-cols-3">
                    <select
                      value={row.method}
                      onChange={(e) => setSplitRows((prev) => prev.map((item, i) => (i === idx ? { ...item, method: e.target.value as PaymentMethodCode } : item)))}
                      className="h-10 rounded-lg border border-secondary-300 px-3 text-sm"
                    >
                      <option value="cash">Cash</option>
                      <option value="card">Card</option>
                      <option value="mobile_wallet">Mobile Wallet</option>
                      <option value="bank_transfer">Bank Transfer</option>
                    </select>
                    <Input
                      value={row.amount}
                      onChange={(e) => setSplitRows((prev) => prev.map((item, i) => (i === idx ? { ...item, amount: e.target.value } : item)))}
                      placeholder="Amount (PKR)"
                      type="number"
                      min="0"
                    />
                    <Input
                      value={row.reference}
                      onChange={(e) => setSplitRows((prev) => prev.map((item, i) => (i === idx ? { ...item, reference: e.target.value } : item)))}
                      placeholder="Reference (optional)"
                    />
                  </div>
                ))}
                <Button variant="outline" onClick={() => setSplitRows((prev) => [...prev, { method: "card", amount: "", reference: "" }])}>
                  Add Split Row
                </Button>
                <div>
                  <Button onClick={handleSplitPayment} disabled={submitting}>Post Split Payment</Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Fully paid indicator */}
      {summary && summary.due_amount === 0 && summary.paid_amount > 0 && (
        <div className="rounded-lg bg-success-50 border border-success-200 p-4 text-center">
          <p className="text-lg font-semibold text-success-700">Session Fully Paid</p>
          <p className="text-sm text-success-600">All {summary.order_count} orders are settled.</p>
        </div>
      )}
    </div>
  );
}

export default SessionPaymentPage;
