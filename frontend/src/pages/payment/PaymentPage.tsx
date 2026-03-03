import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { CreditCard, Loader2, Printer, RefreshCw } from "lucide-react";
import { isAxiosError } from "axios";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatPKR, rupeesToPaisa, paisaToRupees } from "@/utils/currency";
import * as paymentsApi from "@/services/paymentsApi";
import { fetchOrder, fetchPaymentPreview } from "@/services/ordersApi";
import type { PaymentPreview } from "@/services/ordersApi";
import type {
  CashDrawerSessionResponse,
  PaymentMethodCode,
  PaymentSummary,
  SplitPaymentAllocation,
} from "@/types/payment";
import type { OrderResponse } from "@/types/order";

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

function PaymentPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const [mode, setMode] = useState<Mode>("cash");
  const [summary, setSummary] = useState<PaymentSummary | null>(null);
  const [orderDetail, setOrderDetail] = useState<OrderResponse | null>(null);
  const [preview, setPreview] = useState<PaymentPreview | null>(null);
  const [drawerSession, setDrawerSession] = useState<CashDrawerSessionResponse | null>(null);
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
    if (!orderId) return;
    void loadData(orderId);
  }, [orderId]);

  async function loadData(currentOrderId: string) {
    setLoading(true);
    setError(null);
    try {
      const [nextSummary, nextDrawer, nextOrder, nextPreview] = await Promise.all([
        paymentsApi.fetchOrderPaymentSummary(currentOrderId),
        paymentsApi.fetchDrawerSession(),
        fetchOrder(currentOrderId),
        fetchPaymentPreview(currentOrderId),
      ]);
      setSummary(nextSummary);
      setDrawerSession(nextDrawer);
      setOrderDetail(nextOrder);
      setPreview(nextPreview);
      // Auto-fill amount fields with due amount
      if (nextSummary.due_amount > 0) {
        const dueRupees = String(paisaToRupees(nextSummary.due_amount));
        setCashAmount(dueRupees);
        setCardAmount(dueRupees);
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to load payment data"));
    } finally {
      setLoading(false);
    }
  }

  async function handleCashPayment() {
    if (!orderId) return;
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const next = await paymentsApi.createPayment({
        order_id: orderId,
        method_code: "cash",
        amount: parseRupees(cashAmount),
        tendered_amount: parseRupees(cashTendered) || undefined,
      });
      setSummary(next);
      // Show change in success message if tendered > amount
      const tenderedPaisa = parseRupees(cashTendered);
      const amountPaisa = parseRupees(cashAmount);
      if (tenderedPaisa > amountPaisa) {
        setSuccess(`Cash payment recorded. Change due: ${formatPKR(tenderedPaisa - amountPaisa)}`);
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
    if (!orderId) return;
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const next = await paymentsApi.createPayment({
        order_id: orderId,
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
    if (!orderId) return;
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

      const next = await paymentsApi.splitPayment({
        order_id: orderId,
        allocations,
      });
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

  async function handleOpenDrawer() {
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const next = await paymentsApi.openDrawer({ opening_float: 0 });
      setDrawerSession(next);
      setSuccess("Cash drawer session opened.");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to open drawer"));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCloseDrawer() {
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const next = await paymentsApi.closeDrawer({ closing_balance_counted: 0 });
      setDrawerSession(next.status === "open" ? next : null);
      setSuccess("Cash drawer session closed.");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to close drawer"));
    } finally {
      setSubmitting(false);
    }
  }

  function handlePrintBill() {
    if (!summary) return;
    window.print();
  }

  if (!orderId) {
    return <div className="p-6 text-danger-700">Missing order id.</div>;
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
      <div className="flex items-center justify-between rounded-xl border border-secondary-200 bg-white px-4 py-3">
        <div className="flex items-center gap-3">
          <CreditCard className="h-5 w-5 text-primary-600" />
          <div>
            <h2 className="text-lg font-semibold text-secondary-900">Payment</h2>
            <p className="text-xs text-secondary-500">Order #{summary?.order_number ?? orderId}</p>
            {(orderDetail?.table_label || orderDetail?.table_number) && (
              <p className="text-xs text-secondary-500">
                {orderDetail.table_label ?? `Table ${orderDetail.table_number}`}
              </p>
            )}
          </div>
        </div>
        <div className="text-right">
          <p className="text-xs text-secondary-500">Due</p>
          <p className="text-lg font-semibold text-secondary-900">{dueDisplay}</p>
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 print:hidden">
        <Button
          variant="outline"
          size="sm"
          disabled={submitting}
          onClick={() => void loadData(orderId)}
        >
          <RefreshCw className="mr-1 h-4 w-4" />
          Refresh
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={!summary}
          onClick={handlePrintBill}
        >
          <Printer className="mr-1 h-4 w-4" />
          Print Bill
        </Button>
      </div>

      {error && <div className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{error}</div>}
      {success && <div className="rounded-lg bg-success-50 px-3 py-2 text-sm text-success-700">{success}</div>}

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

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Cash Drawer</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-between gap-3">
          <p className="text-sm text-secondary-600">
            {drawerSession ? "Session is open." : "Session is closed."}
          </p>
          {drawerSession ? (
            <Button variant="outline" onClick={handleCloseDrawer} disabled={submitting}>
              Close Session
            </Button>
          ) : (
            <Button variant="outline" onClick={handleOpenDrawer} disabled={submitting}>
              Open Session
            </Button>
          )}
        </CardContent>
      </Card>

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
                <p className="mt-1 text-xs text-secondary-400">Cash received from customer. Change will be calculated automatically.</p>
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
                    onChange={(e) =>
                      setSplitRows((prev) =>
                        prev.map((item, i) => (i === idx ? { ...item, method: e.target.value as PaymentMethodCode } : item))
                      )
                    }
                    className="h-10 rounded-lg border border-secondary-300 px-3 text-sm"
                  >
                    <option value="cash">Cash</option>
                    <option value="card">Card</option>
                    <option value="mobile_wallet">Mobile Wallet</option>
                    <option value="bank_transfer">Bank Transfer</option>
                  </select>
                  <Input
                    value={row.amount}
                    onChange={(e) =>
                      setSplitRows((prev) =>
                        prev.map((item, i) => (i === idx ? { ...item, amount: e.target.value } : item))
                      )
                    }
                    placeholder="Amount (PKR)"
                    type="number"
                    min="0"
                  />
                  <Input
                    value={row.reference}
                    onChange={(e) =>
                      setSplitRows((prev) =>
                        prev.map((item, i) => (i === idx ? { ...item, reference: e.target.value } : item))
                      )
                    }
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

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Payment Summary</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-base">
          <div className="flex justify-between"><span className="text-secondary-500">Order Total</span><span className="font-medium">{summary ? formatPKR(summary.order_total) : "--"}</span></div>
          {(() => {
            const totalTendered = summary?.payments.reduce((sum, p) => sum + (p.tendered_amount ?? p.amount), 0) ?? 0;
            const totalChange = summary ? totalTendered - summary.paid_amount : 0;
            return totalTendered > (summary?.paid_amount ?? 0) ? (
              <>
                <div className="flex justify-between"><span className="text-secondary-500">Received</span><span className="font-medium">{formatPKR(totalTendered)}</span></div>
                <div className="flex justify-between"><span className="text-secondary-500">Change</span><span className="text-success-600 font-semibold">{formatPKR(totalChange)}</span></div>
              </>
            ) : null;
          })()}
          {!!summary && summary.refunded_amount > 0 && (
            <div className="flex justify-between"><span className="text-secondary-500">Refunded</span><span className="font-medium">{formatPKR(summary.refunded_amount)}</span></div>
          )}
          <div className="flex justify-between border-t border-secondary-200 pt-3 text-lg font-bold"><span>Due</span><span>{summary ? formatPKR(summary.due_amount) : "--"}</span></div>
          {!!summary && summary.payments.length > 0 && (
            <div className="mt-4 border-t border-secondary-200 pt-3">
              <p className="mb-2 text-sm font-semibold uppercase tracking-wide text-secondary-500">Transactions</p>
              <div className="space-y-2">
                {summary.payments.map((payment) => (
                  <div key={payment.id} className="flex items-center justify-between text-sm">
                    <span className="text-secondary-600">
                      {(payment.method?.display_name ?? payment.method_id)} ({payment.kind})
                    </span>
                    <span className="font-medium text-secondary-900">{formatPKR(payment.tendered_amount ?? payment.amount)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default PaymentPage;
