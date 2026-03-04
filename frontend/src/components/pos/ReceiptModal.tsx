import { useEffect, useState, useRef } from "react";
import { Printer, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import api from "@/lib/axios";

interface ReceiptItem {
  modifiers: Array<{
    name: string;
    price_adjustment: number;
  }>;
  name: string;
  quantity: number;
  unit_price: number;
  total: number;
  order_label?: string | null;
}

interface ReceiptPayment {
  method: string;
  amount: number;
  tendered: number | null;
  change: number | null;
}

interface ReceiptData {
  restaurant_name: string;
  receipt_header: string | null;
  receipt_footer: string | null;
  order_number: string;
  order_type: string;
  date: string;
  table_label: string | null;
  customer_name: string | null;
  customer_phone: string | null;
  cashier_name: string;
  waiter_name: string | null;
  items: ReceiptItem[];
  subtotal: number;
  tax_label: string;
  tax_rate_display: string;
  tax_amount: number;
  discount_amount: number;
  total: number;
  payments: ReceiptPayment[];
  payment_status: string;
  cash_tax_rate_bps: number;
  card_tax_rate_bps: number;
  currency: string;
}

function formatAmount(paisa: number): string {
  return `Rs. ${(paisa / 100).toLocaleString("en-PK", { minimumFractionDigits: 0 })}`;
}

function formatSignedAmount(paisa: number): string {
  const abs = Math.abs(paisa);
  const sign = paisa >= 0 ? "+" : "-";
  return `${sign}${formatAmount(abs)}`;
}

interface Props {
  orderId?: string;
  sessionId?: string;
  open: boolean;
  onClose: () => void;
}

export function ReceiptModal({ orderId, sessionId, open, onClose }: Props) {
  const [receipt, setReceipt] = useState<ReceiptData | null>(null);
  const [loading, setLoading] = useState(false);
  const printRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && (orderId || sessionId)) {
      fetchReceipt();
    }
  }, [open, orderId, sessionId]);

  async function fetchReceipt() {
    try {
      setLoading(true);
      const url = sessionId
        ? `/receipts/sessions/${sessionId}`
        : `/receipts/orders/${orderId}`;
      const { data } = await api.get<ReceiptData>(url);
      setReceipt(data);
    } catch {
      setReceipt(null);
    } finally {
      setLoading(false);
    }
  }

  function handlePrint() {
    if (!printRef.current) return;
    const printWindow = window.open("", "_blank", "width=320,height=600");
    if (!printWindow) return;

    // Set title safely via DOM API (no string interpolation into HTML)
    printWindow.document.title = `Receipt - ${receipt?.order_number ?? ""}`;

    // Inject styles via DOM (no document.write)
    const style = printWindow.document.createElement("style");
    style.textContent = [
      "* { margin: 0; padding: 0; box-sizing: border-box; }",
      "body { font-family: 'Courier New', monospace; font-size: 12px; width: 80mm; padding: 4mm; color: #000; }",
      ".center { text-align: center; }",
      ".right { text-align: right; }",
      ".bold { font-weight: bold; }",
      ".divider { border-top: 1px dashed #000; margin: 4px 0; }",
      ".row { display: flex; justify-content: space-between; }",
      ".modifier { padding-left: 8px; font-size: 10px; color: #666; }",
      ".total-row { font-size: 14px; font-weight: bold; }",
      "@media print { body { width: 80mm; } }",
    ].join("\n");
    printWindow.document.head.appendChild(style);

    // Clone content into print window (safe — no innerHTML injection)
    const clone = printRef.current.cloneNode(true);
    printWindow.document.body.appendChild(clone);

    printWindow.focus();
    printWindow.print();
    printWindow.close();
  }

  const orderTypeLabel: Record<string, string> = {
    dine_in: "Dine-In",
    takeaway: "Takeaway",
    call_center: "Call Center",
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between">
            <span>Receipt Preview</span>
            <Button
              variant="outline"
              size="sm"
              onClick={handlePrint}
              disabled={!receipt}
              className="gap-2"
            >
              <Printer className="h-4 w-4" />
              Print
            </Button>
          </DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-primary-600" />
          </div>
        ) : !receipt ? (
          <div className="py-8 text-center text-secondary-500">
            Failed to load receipt.
          </div>
        ) : (
          <div
            ref={printRef}
            className="mx-auto max-w-[300px] rounded border bg-white p-4 font-mono text-xs leading-relaxed text-secondary-900"
          >
            {/* Header */}
            <div className="center text-center">
              <div className="bold text-sm font-bold">
                {receipt.restaurant_name}
              </div>
              {receipt.receipt_header && (
                <div className="mt-1 whitespace-pre-wrap text-[10px]">
                  {receipt.receipt_header}
                </div>
              )}
            </div>

            <div className="divider my-2 border-t border-dashed border-secondary-400" />

            {/* Order info */}
            <div className="row flex justify-between">
              <span>Order: {receipt.order_number}</span>
              <span>{orderTypeLabel[receipt.order_type] ?? receipt.order_type}</span>
            </div>
            <div>
              {new Date(receipt.date).toLocaleString("en-PK", {
                dateStyle: "short",
                timeStyle: "short",
              })}
            </div>
            {receipt.table_label && <div>{receipt.table_label}</div>}
            {receipt.customer_name && (
              <div>Customer: {receipt.customer_name}</div>
            )}
            {receipt.customer_phone && <div>Phone: {receipt.customer_phone}</div>}
            <div>Cashier: {receipt.cashier_name}</div>
            {receipt.waiter_name && <div>Waiter: {receipt.waiter_name}</div>}

            <div className="divider my-2 border-t border-dashed border-secondary-400" />

            {/* Items — grouped by order when session receipt */}
            {(() => {
              const hasOrderLabels = receipt.items.some((it) => it.order_label);
              // Group items by order_label (preserving order)
              const groups: Array<{ label: string | null; items: typeof receipt.items }> = [];
              for (const item of receipt.items) {
                const label = item.order_label ?? null;
                const last = groups[groups.length - 1];
                if (last && last.label === label) {
                  last.items.push(item);
                } else {
                  groups.push({ label, items: [item] });
                }
              }

              return groups.map((group, gi) => (
                <div key={gi}>
                  {hasOrderLabels && group.label && (
                    <div className="mb-1 mt-1 text-center text-[10px] font-bold text-secondary-600">
                      — Order #{group.label} —
                    </div>
                  )}
                  {group.items.map((item, i) => {
                    const hasModifiers = item.modifiers.length > 0;
                    const groupedMods: Array<{ name: string; price_adjustment: number; qty: number }> = [];
                    for (const mod of item.modifiers) {
                      const existing = groupedMods.find((g) => g.name === mod.name && g.price_adjustment === mod.price_adjustment);
                      if (existing) { existing.qty += 1; } else { groupedMods.push({ name: mod.name, price_adjustment: mod.price_adjustment, qty: 1 }); }
                    }
                    const modTotal = item.modifiers.reduce((s, m) => s + m.price_adjustment, 0);
                    const basePrice = item.unit_price - modTotal;
                    const basePriceTotal = basePrice * item.quantity;
                    return (
                      <div key={i} className="mb-1">
                        <div className="row flex justify-between">
                          <span>
                            {item.quantity}x {item.name}
                          </span>
                          <span>{formatAmount(basePriceTotal)}</span>
                        </div>
                        {groupedMods.map((mod, j) => (
                          <div key={j} className="modifier pl-2 text-[10px] text-secondary-500">
                            + {mod.qty > 1 ? `${mod.qty}x ` : ""}{mod.name}
                            {mod.price_adjustment !== 0 ? ` (${formatSignedAmount(mod.price_adjustment * mod.qty)})` : ""}
                          </div>
                        ))}
                        {hasModifiers && modTotal !== 0 && (
                          <div className="row flex justify-between pl-2 text-[10px] font-medium text-secondary-700">
                            <span>Line Total</span>
                            <span>{formatAmount(item.total)}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ));
            })()}

            <div className="divider my-2 border-t border-dashed border-secondary-400" />

            {/* Totals */}
            <div className="row flex justify-between">
              <span>Subtotal</span>
              <span>{formatAmount(receipt.subtotal)}</span>
            </div>
            {(() => {
              const cashRate = receipt.cash_tax_rate_bps || 0;
              const cardRate = receipt.card_tax_rate_bps || 0;
              const hasDiffRates = cashRate !== cardRate && cashRate > 0 && cardRate > 0;
              const isSplit = receipt.payments.length > 1;

              if (isSplit && hasDiffRates) {
                // Split payment with different tax rates — extract tax from
                // tax-inclusive payment amounts: base = amount * 10000 / (10000 + rate)
                const lines = receipt.payments.map((p) => {
                  const isCash = p.method.toLowerCase().includes("cash");
                  const rateBps = isCash ? cashRate : cardRate;
                  const ratePct = rateBps / 100;
                  const base = Math.round(p.amount * 10000 / (10000 + rateBps));
                  const tax = p.amount - base;
                  return { method: p.method, ratePct, base, tax };
                });
                const totalTax = lines.reduce((s, ln) => s + ln.tax, 0);
                return (
                  <>
                    {lines.map((ln, idx) => (
                      <div key={idx} className="row flex justify-between">
                        <span>{ln.method} Tax ({ln.ratePct}%)</span>
                        <span>{formatAmount(ln.tax)}</span>
                      </div>
                    ))}
                    <div className="row flex justify-between font-medium">
                      <span>Total Tax</span>
                      <span>{formatAmount(totalTax)}</span>
                    </div>
                  </>
                );
              }

              // Single payment — show rate for the method used
              if (receipt.payments.length === 1 && hasDiffRates) {
                const p = receipt.payments[0]!;
                const isCash = p.method.toLowerCase().includes("cash");
                const rateBps = isCash ? cashRate : cardRate;
                const ratePct = rateBps / 100;
                return (
                  <div className="row flex justify-between">
                    <span>{p.method} Tax ({ratePct}%)</span>
                    <span>{formatAmount(receipt.tax_amount)}</span>
                  </div>
                );
              }

              return (
                <div className="row flex justify-between">
                  <span>{receipt.tax_label} ({receipt.tax_rate_display})</span>
                  <span>{formatAmount(receipt.tax_amount)}</span>
                </div>
              );
            })()}
            {receipt.discount_amount > 0 && (
              <div className="row flex justify-between">
                <span>Discount</span>
                <span>-{formatAmount(receipt.discount_amount)}</span>
              </div>
            )}

            <div className="divider my-2 border-t border-dashed border-secondary-400" />

            <div className="total-row row flex justify-between text-sm font-bold">
              <span>TOTAL</span>
              <span>{formatAmount(receipt.total)}</span>
            </div>

            {/* Payments */}
            {receipt.payments.length > 0 && (() => {
              const cashRate = receipt.cash_tax_rate_bps || 0;
              const cardRate = receipt.card_tax_rate_bps || 0;
              const hasDiffRates = cashRate !== cardRate && cashRate > 0 && cardRate > 0;
              return (
                <>
                  <div className="divider my-2 border-t border-dashed border-secondary-400" />
                  {receipt.payments.map((p, i) => {
                    const isCash = p.method.toLowerCase().includes("cash");
                    const rateBps = isCash ? cashRate : cardRate;
                    const ratePct = rateBps / 100;
                    const base = hasDiffRates
                      ? Math.round(p.amount * 10000 / (10000 + rateBps))
                      : 0;
                    const tax = hasDiffRates ? p.amount - base : 0;
                    return (
                      <div key={i} className="mb-1">
                        <div className="row flex justify-between font-medium">
                          <span>{p.method}</span>
                          <span>{formatAmount(p.amount)}</span>
                        </div>
                        {hasDiffRates && (
                          <>
                            <div className="row flex justify-between text-[10px] text-secondary-500">
                              <span>Pre-tax</span>
                              <span>{formatAmount(base)}</span>
                            </div>
                            <div className="row flex justify-between text-[10px] text-secondary-500">
                              <span>Tax @ {ratePct}%</span>
                              <span>{formatAmount(tax)}</span>
                            </div>
                          </>
                        )}
                        {p.tendered != null && p.tendered > p.amount && (
                          <>
                            <div className="row flex justify-between text-[10px]">
                              <span>Tendered</span>
                              <span>{formatAmount(p.tendered)}</span>
                            </div>
                            <div className="row flex justify-between text-[10px]">
                              <span>Change</span>
                              <span>{formatAmount(p.change ?? 0)}</span>
                            </div>
                          </>
                        )}
                      </div>
                    );
                  })}
                </>
              );
            })()}

            {/* Footer */}
            <div className="divider my-2 border-t border-dashed border-secondary-400" />
            <div className="center text-center">
              {receipt.receipt_footer && (
                <div className="whitespace-pre-wrap">
                  {receipt.receipt_footer}
                </div>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
