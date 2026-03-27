import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, CreditCard, Loader2, Printer, RefreshCw, ShieldCheck, Tag, X } from "lucide-react";
import { isAxiosError } from "axios";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatPKR, rupeesToPaisa, paisaToRupees } from "@/utils/currency";
import * as paymentsApi from "@/services/paymentsApi";
import { fetchOrder, fetchPaymentPreview, verifyPassword } from "@/services/ordersApi";
import {
  fetchDiscountTypes,
  fetchOrderDiscounts,
  applyDiscount,
  removeDiscount,
  type DiscountType,
  type DiscountBreakdown,
} from "@/services/discountsApi";
import type { PaymentPreview } from "@/services/ordersApi";
import { useAuthStore } from "@/stores/authStore";
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

function taxInclusive(basePaisa: number, rateBps: number): number {
  return basePaisa + Math.round(basePaisa * rateBps / 10_000);
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
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const [mode, setMode] = useState<Mode>("cash");
  const [summary, setSummary] = useState<PaymentSummary | null>(null);
  const [orderDetail, setOrderDetail] = useState<OrderResponse | null>(null);
  const [preview, setPreview] = useState<PaymentPreview | null>(null);
  const [drawerSession, setDrawerSession] = useState<CashDrawerSessionResponse | null>(null);
  const [discountTypes, setDiscountTypes] = useState<DiscountType[]>([]);
  const [discountBreakdown, setDiscountBreakdown] = useState<DiscountBreakdown | null>(null);
  const [selectedDiscountTypeId, setSelectedDiscountTypeId] = useState("");
  const [manualDiscountAmount, setManualDiscountAmount] = useState("");
  const [manualDiscountNote, setManualDiscountNote] = useState("");
  const [showManagerApproval, setShowManagerApproval] = useState(false);
  const [managerPassword, setManagerPassword] = useState("");
  const [managerApprovalError, setManagerApprovalError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [cashAmount, setCashAmount] = useState("");
  const [cashTendered, setCashTendered] = useState("");
  const [cardAmount, setCardAmount] = useState("");
  const [cardReference, setCardReference] = useState("");
  const [splitCashBase, setSplitCashBase] = useState("");
  const [splitCardReference, setSplitCardReference] = useState("");
  const [splitRows, setSplitRows] = useState<Array<{ method: PaymentMethodCode; amount: string; reference: string }>>([
    { method: "cash", amount: "", reference: "" },
    { method: "card", amount: "", reference: "" },
  ]);
  const [refundingPaymentId, setRefundingPaymentId] = useState<string | null>(null);
  const [refundAmount, setRefundAmount] = useState("");
  const [refundNote, setRefundNote] = useState("");

  const splitCalcEnabled = useMemo(
    () => !!preview && !!summary && summary.paid_amount === 0,
    [preview, summary]
  );
  const splitSubtotal = (preview?.subtotal ?? 0) - (discountBreakdown?.total_discount ?? 0);
  const splitCashBasePaisa = useMemo(() => {
    if (!splitCalcEnabled) return 0;
    return Math.min(parseRupees(splitCashBase), splitSubtotal);
  }, [splitCalcEnabled, splitCashBase, splitSubtotal]);
  const splitCardBasePaisa = useMemo(() => {
    if (!splitCalcEnabled) return 0;
    return Math.max(splitSubtotal - splitCashBasePaisa, 0);
  }, [splitCalcEnabled, splitSubtotal, splitCashBasePaisa]);
  const splitCashPayable = useMemo(() => {
    if (!splitCalcEnabled || !preview) return 0;
    return taxInclusive(splitCashBasePaisa, preview.cash_tax_rate_bps);
  }, [splitCalcEnabled, preview, splitCashBasePaisa]);
  const splitCardPayable = useMemo(() => {
    if (!splitCalcEnabled || !preview) return 0;
    return taxInclusive(splitCardBasePaisa, preview.card_tax_rate_bps);
  }, [splitCalcEnabled, preview, splitCardBasePaisa]);
  const splitTotalPayable = useMemo(
    () => splitCashPayable + splitCardPayable,
    [splitCashPayable, splitCardPayable]
  );
  const refundableAmounts = useMemo(() => {
    if (!summary) return {};

    const refundedByParent = summary.payments.reduce<Record<string, number>>((acc, payment) => {
      if (payment.kind === "refund" && payment.parent_payment_id) {
        acc[payment.parent_payment_id] = (acc[payment.parent_payment_id] ?? 0) + payment.amount;
      }
      return acc;
    }, {});

    return summary.payments.reduce<Record<string, number>>((acc, payment) => {
      if (payment.kind === "payment" && payment.status === "completed") {
        acc[payment.id] = Math.max(payment.amount - (refundedByParent[payment.id] ?? 0), 0);
      }
      return acc;
    }, {});
  }, [summary]);
  const canIssueRefund = useMemo(
    () =>
      user?.role.permissions.some(
        (permission) => permission.code === "payment.refund"
      ) ?? false,
    [user]
  );

  const dueDisplay = useMemo(() => {
    if (!summary) return "--";
    if (mode === "split" && splitCalcEnabled) return formatPKR(splitTotalPayable);
    return formatPKR(summary.due_amount);
  }, [summary, mode, splitCalcEnabled, splitTotalPayable]);

  useEffect(() => {
    if (!orderId) return;
    void loadData(orderId);
  }, [orderId]);

  async function loadData(currentOrderId: string) {
    setLoading(true);
    setError(null);
    try {
      const [nextSummary, nextDrawer, nextOrder, nextPreview, nextDiscTypes, nextDiscBreakdown] = await Promise.all([
        paymentsApi.fetchOrderPaymentSummary(currentOrderId),
        paymentsApi.fetchDrawerSession(),
        fetchOrder(currentOrderId),
        fetchPaymentPreview(currentOrderId),
        fetchDiscountTypes(true),
        fetchOrderDiscounts(currentOrderId),
      ]);
      setSummary(nextSummary);
      setDrawerSession(nextDrawer);
      setOrderDetail(nextOrder);
      setPreview(nextPreview);
      setDiscountTypes(nextDiscTypes);
      setDiscountBreakdown(nextDiscBreakdown);
      // Auto-fill amount fields with due amount
      if (nextSummary.due_amount > 0) {
        const dueRupees = String(paisaToRupees(nextSummary.due_amount));
        setCashAmount(dueRupees);
        setCardAmount(dueRupees);
        const postDiscountSubtotal = nextPreview.subtotal - (nextDiscBreakdown?.total_discount ?? 0);
        const halfSubtotal = Math.round(postDiscountSubtotal / 2);
        setSplitCashBase(String(paisaToRupees(halfSubtotal)));
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
      const allocations: SplitPaymentAllocation[] = splitCalcEnabled
        ? [
            ...(splitCashPayable > 0
              ? [{ method_code: "cash" as const, amount: splitCashPayable }]
              : []),
            ...(splitCardPayable > 0
              ? [{
                  method_code: "card" as const,
                  amount: splitCardPayable,
                  reference: splitCardReference || undefined,
                }]
              : []),
          ]
        : splitRows
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
      setSplitCardReference("");
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

  async function handleRefund(paymentId: string) {
    const amount = parseRupees(refundAmount);
    if (!amount) {
      setError("Enter a refund amount greater than zero.");
      return;
    }

    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const next = await paymentsApi.refundPayment({
        payment_id: paymentId,
        amount,
        note: refundNote || undefined,
      });
      setSummary(next);
      setSuccess("Refund recorded.");
      setRefundingPaymentId(null);
      setRefundAmount("");
      setRefundNote("");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to record refund"));
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
          <Button
            variant="ghost"
            size="sm"
            className="h-9 w-9 p-0 text-secondary-500 hover:text-secondary-700"
            onClick={() => navigate(-1)}
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
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

      {/* Discounts */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Tag className="h-4 w-4" />
            Discounts
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {/* Applied discounts */}
          {discountBreakdown && discountBreakdown.discounts.length > 0 && (
            <div className="space-y-2">
              {discountBreakdown.discounts.map((d) => (
                <div key={d.id} className="flex items-center justify-between rounded-lg bg-amber-50 px-3 py-2">
                  <div>
                    <p className="text-sm font-medium text-amber-800">{d.label}</p>
                    {d.note && <p className="text-xs text-amber-600">{d.note}</p>}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-amber-900">-{formatPKR(d.amount)}</span>
                    <button
                      onClick={async () => {
                        try {
                          await removeDiscount(d.id);
                          if (orderId) await loadData(orderId);
                        } catch (err: unknown) {
                          setError(getErrorMessage(err, "Failed to remove discount"));
                        }
                      }}
                      className="rounded p-1 text-amber-500 hover:bg-amber-100"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))}
              <div className="flex justify-between text-sm font-semibold border-t border-secondary-100 pt-2">
                <span>Total Discount</span>
                <span className="text-amber-700">-{formatPKR(discountBreakdown.total_discount)}</span>
              </div>
            </div>
          )}
          {/* Apply new discount */}
          <div className="space-y-2">
            <div className="grid gap-2 md:grid-cols-3">
              <div>
                <Label className="text-xs">Discount Type</Label>
                <select
                  value={selectedDiscountTypeId}
                  onChange={(e) => setSelectedDiscountTypeId(e.target.value)}
                  className="h-10 w-full rounded-lg border border-secondary-300 px-3 text-sm"
                >
                  <option value="">Manual</option>
                  {discountTypes.map((dt) => (
                    <option key={dt.id} value={dt.id}>
                      {dt.name} ({dt.kind === "percent" ? `${dt.value / 100}%` : formatPKR(dt.value)})
                    </option>
                  ))}
                </select>
              </div>
              {!selectedDiscountTypeId && (
                <div>
                  <Label className="text-xs">Amount (PKR)</Label>
                  <Input
                    value={manualDiscountAmount}
                    onChange={(e) => setManualDiscountAmount(e.target.value)}
                    placeholder="0"
                    type="number"
                    min="0"
                  />
                </div>
              )}
              <div>
                <Label className="text-xs">Note</Label>
                <Input
                  value={manualDiscountNote}
                  onChange={(e) => setManualDiscountNote(e.target.value)}
                  placeholder="Optional"
                />
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              disabled={submitting}
              onClick={async () => {
                if (!orderId) return;
                setSubmitting(true);
                setError(null);
                try {
                  await applyDiscount({
                    order_id: orderId,
                    discount_type_id: selectedDiscountTypeId || undefined,
                    amount: !selectedDiscountTypeId && manualDiscountAmount
                      ? rupeesToPaisa(Number(manualDiscountAmount))
                      : undefined,
                    label: !selectedDiscountTypeId ? "Manual Discount" : undefined,
                    source_type: !selectedDiscountTypeId ? "manual" : undefined,
                    note: manualDiscountNote || undefined,
                  });
                  setManualDiscountAmount("");
                  setManualDiscountNote("");
                  setSelectedDiscountTypeId("");
                  await loadData(orderId);
                  setSuccess("Discount applied.");
                } catch (err: unknown) {
                  const msg = getErrorMessage(err, "Failed to apply discount");
                  if (msg === "approval_required") {
                    setShowManagerApproval(true);
                    setManagerApprovalError("");
                    setManagerPassword("");
                  } else {
                    setError(msg);
                  }
                } finally {
                  setSubmitting(false);
                }
              }}
            >
              Apply Discount
            </Button>

            {/* Manager approval dialog */}
            {showManagerApproval && (
              <div className="mt-3 rounded-lg border border-amber-300 bg-amber-50 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <ShieldCheck className="h-5 w-5 text-amber-600" />
                  <span className="text-sm font-semibold text-amber-800">
                    Manager Approval Required
                  </span>
                </div>
                <p className="text-xs text-amber-700 mb-3">
                  This discount exceeds the approval threshold. Enter manager password to authorize.
                </p>
                <div className="flex gap-2">
                  <Input
                    type="password"
                    placeholder="Manager password"
                    value={managerPassword}
                    onChange={(e) => setManagerPassword(e.target.value)}
                    onKeyDown={async (e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        (e.target as HTMLInputElement).closest("div")?.querySelector<HTMLButtonElement>("button")?.click();
                      }
                    }}
                    className="flex-1"
                  />
                  <Button
                    size="sm"
                    disabled={submitting || !managerPassword}
                    onClick={async () => {
                      if (!orderId) return;
                      setSubmitting(true);
                      setManagerApprovalError("");
                      try {
                        const { auth_token } = await verifyPassword(managerPassword);
                        await applyDiscount({
                          order_id: orderId,
                          discount_type_id: selectedDiscountTypeId || undefined,
                          amount: !selectedDiscountTypeId && manualDiscountAmount
                            ? rupeesToPaisa(Number(manualDiscountAmount))
                            : undefined,
                          label: !selectedDiscountTypeId ? "Manual Discount" : undefined,
                          source_type: !selectedDiscountTypeId ? "manual" : undefined,
                          note: manualDiscountNote || undefined,
                          manager_verify_token: auth_token,
                        });
                        setShowManagerApproval(false);
                        setManagerPassword("");
                        setManualDiscountAmount("");
                        setManualDiscountNote("");
                        setSelectedDiscountTypeId("");
                        await loadData(orderId);
                        setSuccess("Discount approved and applied.");
                      } catch (err: unknown) {
                        setManagerApprovalError(
                          getErrorMessage(err, "Approval failed")
                        );
                      } finally {
                        setSubmitting(false);
                      }
                    }}
                  >
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setShowManagerApproval(false);
                      setManagerPassword("");
                    }}
                  >
                    Cancel
                  </Button>
                </div>
                {managerApprovalError && (
                  <p className="mt-2 text-xs text-danger-600">{managerApprovalError}</p>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

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
              {splitCalcEnabled ? (
                <>
                  <div className="grid gap-3 md:grid-cols-2">
                    <div>
                      <Label>Cash Base (PKR, pre-tax)</Label>
                      <Input
                        value={splitCashBase}
                        onChange={(e) => setSplitCashBase(e.target.value)}
                        placeholder="0"
                        type="number"
                        min="0"
                        max={String(paisaToRupees(splitSubtotal))}
                      />
                    </div>
                    <div>
                      <Label>Card Base (PKR, pre-tax)</Label>
                      <Input value={String(paisaToRupees(splitCardBasePaisa))} readOnly />
                    </div>
                  </div>
                  <div className="grid gap-2 rounded-lg border border-secondary-200 p-3 text-sm">
                    <div className="flex justify-between">
                      <span className="text-secondary-600">Cash Payable ({(preview?.cash_tax_rate_bps ?? 0) / 100}%)</span>
                      <span className="font-medium">{formatPKR(splitCashPayable)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-secondary-600">Card Payable ({(preview?.card_tax_rate_bps ?? 0) / 100}%)</span>
                      <span className="font-medium">{formatPKR(splitCardPayable)}</span>
                    </div>
                    <div className="flex justify-between border-t border-secondary-200 pt-2 font-semibold">
                      <span>Split Total Due</span>
                      <span>{formatPKR(splitTotalPayable)}</span>
                    </div>
                  </div>
                  <div>
                    <Label>Card Reference</Label>
                    <Input
                      value={splitCardReference}
                      onChange={(e) => setSplitCardReference(e.target.value)}
                      placeholder="Last 4 / txn id"
                    />
                  </div>
                </>
              ) : (
                <>
                  <p className="text-xs text-amber-700">
                    Smart split calculator is available before first payment only. Use manual split below.
                  </p>
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
                </>
              )}
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
          {orderDetail && (
            <>
              <div className="flex justify-between"><span className="text-secondary-500">Subtotal</span><span className="font-medium">{formatPKR(orderDetail.subtotal)}</span></div>
              <div className="flex justify-between"><span className="text-secondary-500">Tax ({orderDetail.tax_amount > 0 ? `${((orderDetail.tax_amount / orderDetail.subtotal) * 100).toFixed(0)}%` : "0%"})</span><span className="font-medium">{formatPKR(orderDetail.tax_amount)}</span></div>
            </>
          )}
          {discountBreakdown && discountBreakdown.total_discount > 0 && (
            <div className="flex justify-between"><span className="text-amber-600">Discount</span><span className="font-medium text-amber-700">-{formatPKR(discountBreakdown.total_discount)}</span></div>
          )}
          <div className="flex justify-between border-t border-secondary-200 pt-2 font-semibold"><span className="text-secondary-700">Order Total</span><span>{summary ? formatPKR(summary.order_total) : "--"}</span></div>
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
              <div className="space-y-3">
                {summary.payments.map((payment) => {
                  const methodName = payment.method?.display_name ?? payment.method_id;
                  const isCash = methodName.toLowerCase().includes("cash");
                  const taxRateBps = preview ? (isCash ? preview.cash_tax_rate_bps : preview.card_tax_rate_bps) : 0;
                  const taxPct = taxRateBps / 100;
                  const paymentTax = Math.round(payment.amount * taxRateBps / 10000);
                  const refundableAmount = refundableAmounts[payment.id] ?? 0;
                  const isRefund = payment.kind === "refund";
                  return (
                    <div key={payment.id}>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-secondary-600">
                          {methodName} ({payment.kind})
                        </span>
                        <span className={`font-medium ${isRefund ? "text-danger-700" : "text-secondary-900"}`}>
                          {isRefund ? "-" : ""}
                          {formatPKR(payment.amount)}
                        </span>
                      </div>
                      {(payment.reference || payment.note) && (
                        <div className="mt-1 space-y-0.5 pl-2 text-xs text-secondary-400">
                          {payment.reference && <div>Ref: {payment.reference}</div>}
                          {payment.note && <div>Note: {payment.note}</div>}
                        </div>
                      )}
                      {!isRefund && taxRateBps > 0 && (
                        <div className="flex items-center justify-between text-xs text-secondary-400 pl-2">
                          <span>Tax @ {taxPct}%</span>
                          <span>{formatPKR(paymentTax)}</span>
                        </div>
                      )}
                      {!isRefund && canIssueRefund && refundableAmount > 0 && (
                        <div className="mt-2 rounded-lg border border-secondary-200 bg-secondary-50 p-2">
                          <div className="flex items-center justify-between gap-2">
                            <div className="text-xs text-secondary-500">
                              Refundable balance: <span className="font-medium text-secondary-700">{formatPKR(refundableAmount)}</span>
                            </div>
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={submitting}
                              onClick={() => {
                                if (refundingPaymentId === payment.id) {
                                  setRefundingPaymentId(null);
                                  setRefundAmount("");
                                  setRefundNote("");
                                  return;
                                }
                                setRefundingPaymentId(payment.id);
                                setRefundAmount(String(paisaToRupees(refundableAmount)));
                                setRefundNote("");
                              }}
                            >
                              {refundingPaymentId === payment.id ? "Cancel" : "Refund"}
                            </Button>
                          </div>
                          {refundingPaymentId === payment.id && (
                            <div className="mt-3 grid gap-2 md:grid-cols-[1fr_1fr_auto]">
                              <Input
                                value={refundAmount}
                                onChange={(e) => setRefundAmount(e.target.value)}
                                placeholder="Amount (PKR)"
                                type="number"
                                min="0"
                                max={String(paisaToRupees(refundableAmount))}
                              />
                              <Input
                                value={refundNote}
                                onChange={(e) => setRefundNote(e.target.value)}
                                placeholder="Reason / note"
                              />
                              <Button
                                disabled={submitting}
                                onClick={() => void handleRefund(payment.id)}
                              >
                                Post Refund
                              </Button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default PaymentPage;



