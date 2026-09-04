/**
 * Purchase orders: raise, send, receive, and see what is still owed.
 *
 *     Location -> Supplier -> Items -> Create -> Send -> Receive -> Stock
 *
 * 🔴 Money on this screen is MINOR UNITS end to end. Price inputs ask for
 * major units and convert ONCE, at the point of sending. `formatMoney` takes
 * minor units and divides by 100 itself. Nothing else multiplies or divides.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ClipboardList,
  Loader2,
  PackageCheck,
  Plus,
  Printer,
  ScanLine,
  Send,
  Trash2,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { Thumb } from "@/components/admin/Thumb";
import { useConfigStore } from "@/stores/configStore";
import { formatMoney } from "@/utils/currency";
import {
  cancelPurchaseOrder,
  createPurchaseOrder,
  fetchCatalogue,
  fetchPurchaseOrderDocument,
  fetchPurchaseOrders,
  fetchSuppliers,
  receiveGoods,
  scanDeliveryNote,
  sendPurchaseOrder,
} from "@/services/procurementApi";
import { fetchLocations } from "@/services/locationsApi";
import { fetchIngredients } from "@/services/inventoryApi";
import type {
  PurchaseOrder,
  PurchaseOrderStatus,
  ReceiptSource,
  ScanResult,
  Supplier,
  SupplierItemRow,
} from "@/types/procurement";
import type { Location } from "@/types/location";
import type { Ingredient } from "@/types/inventory";

type StatusFilter = "all" | PurchaseOrderStatus;

const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All statuses" },
  { value: "draft", label: "Draft" },
  { value: "sent", label: "Sent" },
  { value: "partially_received", label: "Partially received" },
  { value: "received", label: "Received" },
  { value: "cancelled", label: "Cancelled" },
];

const STATUS_BADGE: Record<
  PurchaseOrderStatus,
  { label: string; variant: "secondary" | "warning" | "success" | "destructive" }
> = {
  draft: { label: "Draft", variant: "secondary" },
  sent: { label: "Sent", variant: "warning" },
  partially_received: { label: "Part received", variant: "warning" },
  received: { label: "Received", variant: "success" },
  cancelled: { label: "Cancelled", variant: "destructive" },
};

interface DraftLine {
  uid: string;
  ingredient_id: string;
  quantity: string;
  price: string;
}

let lineCounter = 0;
function newLine(): DraftLine {
  lineCounter += 1;
  return { uid: `po-line-${lineCounter}`, ingredient_id: "", quantity: "", price: "" };
}

function minor(value: string | null | undefined): number {
  const n = Number(value ?? 0);
  return Number.isFinite(n) ? n : 0;
}

function qty(value: string | null | undefined): number {
  const n = Number(value ?? 0);
  return Number.isFinite(n) ? n : 0;
}

function errorDetail(error: unknown, fallback = "Please try again."): string {
  return (
    (error as { response?: { data?: { detail?: string } } })?.response?.data
      ?.detail ?? fallback
  );
}

function PurchaseOrdersPage() {
  const { toast } = useToast();
  const config = useConfigStore((s) => s.config);
  const currency = config?.currency ?? "AED";
  const defaultTaxBps = config?.default_tax_rate ?? 0;

  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [expanded, setExpanded] = useState<string | null>(null);

  // Create
  const [showCreate, setShowCreate] = useState(false);
  const [supplierId, setSupplierId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [expectedDate, setExpectedDate] = useState("");
  const [taxPercent, setTaxPercent] = useState(String(defaultTaxBps / 100));
  const [deliveryInstructions, setDeliveryInstructions] = useState("");
  // Martin (FZ LLC, 2026-09-02): "needs to have a section with 'additional
  // comments' same as there is delivery instructions". Stored as the PO's
  // `notes`, which existed but was never on the form nor on the document.
  const [additionalComments, setAdditionalComments] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([newLine()]);
  const [catalogue, setCatalogue] = useState<SupplierItemRow[]>([]);

  // Send
  const [sendFor, setSendFor] = useState<PurchaseOrder | null>(null);

  // Receive
  const [receiveFor, setReceiveFor] = useState<PurchaseOrder | null>(null);
  const [receiveQty, setReceiveQty] = useState<Record<string, string>>({});
  const [receivePrice, setReceivePrice] = useState<Record<string, string>>({});
  const [deliveryNote, setDeliveryNote] = useState("");
  const [receiveNotes, setReceiveNotes] = useState("");
  // Scanning fills the same form in. It never books stock on its own.
  const [scanning, setScanning] = useState(false);
  const [scan, setScan] = useState<ScanResult | null>(null);
  const [scanSource, setScanSource] = useState<ReceiptSource>("manual");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [po, sup, locs, ings] = await Promise.all([
        fetchPurchaseOrders(
          statusFilter === "all" ? {} : { status: statusFilter },
        ),
        fetchSuppliers(),
        fetchLocations(),
        fetchIngredients(),
      ]);
      setOrders(po);
      setSuppliers(sup);
      setLocations(locs);
      setIngredients(ings);
    } catch {
      toast({
        title: "Could not load purchase orders",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [statusFilter, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  // A produced ingredient is made in-house; the backend refuses to buy it, so
  // it is not offered here either.
  const purchasable = useMemo(
    () => ingredients.filter((i) => !i.is_produced),
    [ingredients],
  );

  // When the supplier changes, load their catalogue so the buyer can see the
  // last paid price before committing to a quantity.
  useEffect(() => {
    if (!supplierId) {
      setCatalogue([]);
      return;
    }
    let cancelled = false;
    void fetchCatalogue({ supplierId })
      .then((rows) => {
        if (!cancelled) setCatalogue(rows);
      })
      .catch(() => {
        if (!cancelled) setCatalogue([]);
      });
    return () => {
      cancelled = true;
    };
  }, [supplierId]);

  const catalogueByIngredient = useMemo(() => {
    const map = new Map<string, SupplierItemRow>();
    catalogue.forEach((row) => map.set(row.ingredient_id, row));
    return map;
  }, [catalogue]);

  const draftTotal = useMemo(() => {
    const subtotal = lines.reduce((sum, line) => {
      const quantity = Number(line.quantity);
      if (!Number.isFinite(quantity) || quantity <= 0) return sum;
      const typed = Number(line.price);
      const priceMinor = Number.isFinite(typed) && line.price.trim() !== ""
        ? typed * 100
        : minor(catalogueByIngredient.get(line.ingredient_id)?.last_price_minor);
      return sum + quantity * priceMinor;
    }, 0);
    const bps = Math.round((Number(taxPercent) || 0) * 100);
    const tax = (subtotal * bps) / 10000;
    return { subtotal, tax, total: subtotal + tax };
  }, [lines, taxPercent, catalogueByIngredient]);

  function openCreate() {
    setSupplierId("");
    setLocationId(locations.find((l) => l.is_default)?.id ?? locations[0]?.id ?? "");
    setExpectedDate("");
    setTaxPercent(String(defaultTaxBps / 100));
    setDeliveryInstructions("");
    setAdditionalComments("");
    setLines([newLine()]);
    setShowCreate(true);
  }

  async function submitCreate() {
    const usable = lines.filter(
      (line) => line.ingredient_id && Number(line.quantity) > 0,
    );
    if (!supplierId || !locationId || usable.length === 0) {
      toast({
        title: "Incomplete order",
        description: "Pick a supplier, a delivery location and at least one item.",
        variant: "destructive",
      });
      return;
    }
    setSaving(true);
    try {
      await createPurchaseOrder({
        supplier_id: supplierId,
        location_id: locationId,
        expected_date: expectedDate || null,
        tax_bps: Math.round((Number(taxPercent) || 0) * 100),
        delivery_instructions: deliveryInstructions.trim() || null,
        notes: additionalComments.trim() || null,
        lines: usable.map((line) => ({
          ingredient_id: line.ingredient_id,
          quantity_ordered: line.quantity,
          // Blank means "use the supplier's last price, then the ingredient
          // cost" -- decided on the server, not guessed here.
          unit_price_minor:
            line.price.trim() === ""
              ? null
              : Math.round(Number(line.price) * 100),
        })),
      });
      toast({ title: "Purchase order created" });
      setShowCreate(false);
      await load();
    } catch (error) {
      toast({
        title: "Could not create the order",
        description: errorDetail(error),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  async function openDocument(order: PurchaseOrder) {
    try {
      const html = await fetchPurchaseOrderDocument(order.id);
      // Opened from a blob rather than linked directly: a plain link would not
      // carry the auth header and the endpoint would reject it.
      const blob = new Blob([html], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      const win = window.open(url, "_blank");
      if (!win) {
        toast({
          title: "Pop-up blocked",
          description: "Allow pop-ups to preview the order document.",
          variant: "destructive",
        });
      }
      // Revoke late enough for the new window to have loaded it.
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
      toast({
        title: "Could not open the document",
        description: errorDetail(error),
        variant: "destructive",
      });
    }
  }

  function openSend(order: PurchaseOrder) {
    setSendFor(order);
  }

  async function submitSend() {
    if (!sendFor) return;
    setSaving(true);
    try {
      // F39: always skip_email. The endpoint still records the transition and
      // the audit trail; only the outbound mail is gone.
      const skipEmail = true;
      const result = await sendPurchaseOrder(sendFor.id, {
        to: null,
        message: null,
        cc_self: false,
        skip_email: skipEmail,
      });
      if (skipEmail) {
        toast({
          title: `${result.purchase_order.po_number} marked as sent`,
          description: "No email was sent.",
        });
      } else if (result.email_sent) {
        toast({
          title: "Purchase order emailed",
          description: `Sent to ${result.sent_to}.`,
        });
      } else {
        // Deliberately not a silent success. The supplier does not know about
        // the order, and the buyer needs to be told that plainly.
        toast({
          title: "Order recorded, but the email did NOT go out",
          description:
            result.error ??
            "Print the order and send it to the supplier by hand.",
          variant: "destructive",
        });
      }
      setSendFor(null);
      await load();
    } catch (error) {
      toast({
        title: "Could not send the order",
        description: errorDetail(error),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleScan(file: File) {
    if (!receiveFor) return;
    setScanning(true);
    try {
      const result = await scanDeliveryNote(receiveFor.id, file);
      setScan(result);
      setScanSource("ocr");
      if (result.document_reference) setDeliveryNote(result.document_reference);

      // Fill the SAME form the buyer would have typed into. Nothing is
      // committed: they still read it, correct it, and press the button.
      const quantities = { ...receiveQty };
      const prices = { ...receivePrice };
      result.lines.forEach((line) => {
        quantities[line.purchase_order_item_id] = line.quantity_received;
        if (line.unit_price_minor !== null) {
          prices[line.purchase_order_item_id] = String(
            minor(line.unit_price_minor) / 100,
          );
        }
      });
      setReceiveQty(quantities);
      setReceivePrice(prices);

      const lowConfidence = result.lines.filter(
        (l) => l.confidence !== "high",
      ).length;
      toast({
        title: `Read ${result.lines.length} line${result.lines.length === 1 ? "" : "s"}`,
        description:
          lowConfidence > 0 || result.unmatched.length > 0
            ? "Check the highlighted rows before confirming."
            : "Check the figures against the paper, then confirm.",
      });
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response
        ?.status;
      toast({
        title:
          status === 503
            ? "Scanning is not available"
            : "Could not read that document",
        description: errorDetail(
          error,
          "Enter the delivery by hand instead.",
        ),
        variant: "destructive",
      });
    } finally {
      setScanning(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  function openReceive(order: PurchaseOrder) {
    setReceiveFor(order);
    setDeliveryNote("");
    setReceiveNotes("");
    setScan(null);
    setScanSource("manual");
    // Pre-fill with what is still outstanding: the common case is that the
    // rest of the order arrived.
    const quantities: Record<string, string> = {};
    const prices: Record<string, string> = {};
    order.items.forEach((item) => {
      const outstanding = qty(item.quantity_outstanding);
      quantities[item.id] = outstanding > 0 ? String(outstanding) : "";
      prices[item.id] = String(minor(item.unit_price_minor) / 100);
    });
    setReceiveQty(quantities);
    setReceivePrice(prices);
  }

  async function submitReceive() {
    if (!receiveFor) return;
    const payloadLines = receiveFor.items
      .filter((item) => Number(receiveQty[item.id]) > 0)
      .map((item) => {
        const typedPrice = Number(receivePrice[item.id]);
        return {
          purchase_order_item_id: item.id,
          quantity_received: receiveQty[item.id] as string,
          unit_price_minor: Number.isFinite(typedPrice)
            ? Math.round(typedPrice * 100)
            : null,
        };
      });

    if (payloadLines.length === 0) {
      toast({
        title: "Nothing to receive",
        description: "Enter the quantity that actually arrived.",
        variant: "destructive",
      });
      return;
    }

    setSaving(true);
    try {
      const result = await receiveGoods(receiveFor.id, {
        lines: payloadLines,
        document_reference: deliveryNote.trim() || null,
        notes: receiveNotes.trim() || null,
        // Records where the numbers came from, not who is accountable for
        // them. A person confirmed this either way.
        source: scanSource,
      });
      toast({
        title: `Received on ${result.receipt.receipt_number}`,
        description: `Stock updated at ${result.purchase_order.location_name}.`,
      });
      setReceiveFor(null);
      await load();
    } catch (error) {
      toast({
        title: "Could not record the delivery",
        description: errorDetail(error),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  async function cancel(order: PurchaseOrder) {
    setSaving(true);
    try {
      await cancelPurchaseOrder(order.id);
      toast({ title: `${order.po_number} cancelled` });
      await load();
    } catch (error) {
      toast({
        title: "Could not cancel the order",
        description: errorDetail(error),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">
            Purchase orders
          </h1>
          <p className="text-sm text-secondary-500">
            Order from a supplier, send it, and book the delivery into stock.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select
            className="w-52"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
          >
            {STATUS_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </Select>
          <Button onClick={openCreate}>
            <Plus className="mr-2 h-4 w-4" />
            New order
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-secondary-500">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          Loading purchase orders
        </div>
      ) : orders.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
            <ClipboardList className="h-10 w-10 text-secondary-300" />
            <p className="text-secondary-600">No purchase orders yet.</p>
            <p className="max-w-md text-sm text-secondary-500">
              Raise one to order stock from a supplier. When the delivery
              arrives, receiving it here updates the stock at that location
              automatically.
            </p>
            <Button onClick={openCreate}>
              <Plus className="mr-2 h-4 w-4" />
              Raise the first order
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {orders.map((order) => {
            const badge = STATUS_BADGE[order.status];
            const isOpen = expanded === order.id;
            // F46: this used to add the outstanding QUANTITIES across lines
            // ("55 still owed" for 30 kg of butter and 25 kg of flour), which
            // is a number with no unit. Count the lines still owed instead.
            const outstanding = order.items.filter(
              (item) => qty(item.quantity_outstanding) > 0,
            ).length;
            return (
              <Card key={order.id}>
                <CardContent className="p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <button
                      type="button"
                      className="text-left"
                      onClick={() => setExpanded(isOpen ? null : order.id)}
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-secondary-900">
                          {order.po_number}
                        </span>
                        <Badge variant={badge.variant}>{badge.label}</Badge>
                        {order.last_email_error && (
                          <Badge variant="destructive">
                            <AlertTriangle className="mr-1 h-3 w-3" />
                            Email failed
                          </Badge>
                        )}
                      </div>
                      <div className="mt-1 text-sm text-secondary-600">
                        {order.supplier_name} &rarr; {order.location_name}
                      </div>
                      <div className="text-xs text-secondary-500">
                        Raised {new Date(order.created_at).toLocaleDateString()}
                        {order.expected_date &&
                          ` · due ${new Date(order.expected_date).toLocaleDateString()}`}
                        {outstanding > 0 &&
                          order.status !== "cancelled" &&
                          ` · ${outstanding} ${outstanding === 1 ? "line" : "lines"} still owed`}
                      </div>
                    </button>

                    <div className="flex flex-wrap items-center gap-2">
                      <div className="mr-2 text-right">
                        <div className="text-lg font-semibold text-secondary-900">
                          {formatMoney(minor(order.total_minor), currency)}
                        </div>
                        <div className="text-xs text-secondary-500">
                          {order.items.length} item
                          {order.items.length === 1 ? "" : "s"}
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => void openDocument(order)}
                      >
                        <Printer className="mr-1 h-4 w-4" />
                        Print
                      </Button>
                      {order.status === "draft" && (
                        <Button size="sm" onClick={() => openSend(order)}>
                          <Send className="mr-1 h-4 w-4" />
                          Send
                        </Button>
                      )}
                      {/* F39: a "Resend" button used to sit here. Emailing was
                          removed from this flow -- the shared mail service runs
                          on another tenant's account and sending domain, and
                          this client never asked for supplier emailing. Print
                          the order and send it however he already does. */}
                      {(order.status === "sent" ||
                        order.status === "partially_received") && (
                        <Button size="sm" onClick={() => openReceive(order)}>
                          <PackageCheck className="mr-1 h-4 w-4" />
                          Receive
                        </Button>
                      )}
                      {order.status !== "received" &&
                        order.status !== "cancelled" && (
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={saving}
                            onClick={() => void cancel(order)}
                          >
                            <XCircle className="h-4 w-4 text-danger-600" />
                          </Button>
                        )}
                    </div>
                  </div>

                  {isOpen && (
                    <div className="mt-4 space-y-4 border-t border-secondary-100 pt-4">
                      <table className="w-full text-sm">
                        <thead className="text-left text-xs uppercase tracking-wide text-secondary-500">
                          <tr>
                            <th className="py-1">Item</th>
                            <th className="py-1 text-right">Ordered</th>
                            <th className="py-1 text-right">Received</th>
                            <th className="py-1 text-right">Unit price</th>
                            <th className="py-1 text-right">Line total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {order.items.map((item) => (
                            <tr
                              key={item.id}
                              className="border-t border-secondary-100"
                            >
                              <td className="py-2">
                                <div className="flex items-center gap-2">
                                  <Thumb
                                    src={item.ingredient_image_url}
                                    alt={item.ingredient_name}
                                  />
                                  <span>
                                    {item.ingredient_name}
                                    {item.supplier_sku && (
                                      <span className="ml-2 text-xs text-secondary-500">
                                        {item.supplier_sku}
                                      </span>
                                    )}
                                  </span>
                                </div>
                              </td>
                              <td className="py-2 text-right">
                                {qty(item.quantity_ordered)} {item.unit}
                                {/* M8: the same quantity in the unit the
                                    kitchen counts, when the two differ. The
                                    supplier is still asked for cans. */}
                                {qty(item.units_per_purchase_unit) !== 1 &&
                                  item.stock_unit && (
                                    <div className="text-[10px] text-secondary-400">
                                      ={" "}
                                      {qty(item.quantity_ordered) *
                                        qty(item.units_per_purchase_unit)}{" "}
                                      {item.stock_unit}
                                    </div>
                                  )}
                              </td>
                              <td className="py-2 text-right">
                                <span
                                  className={
                                    qty(item.quantity_received) >
                                    qty(item.quantity_ordered)
                                      ? "text-warning-600"
                                      : undefined
                                  }
                                >
                                  {qty(item.quantity_received)} {item.unit}
                                </span>
                              </td>
                              <td className="py-2 text-right">
                                {formatMoney(
                                  minor(item.unit_price_minor),
                                  currency,
                                )}
                              </td>
                              <td className="py-2 text-right">
                                {formatMoney(
                                  minor(item.line_total_minor),
                                  currency,
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                        <tfoot className="border-t border-secondary-200">
                          <tr>
                            <td colSpan={4} className="py-1 text-right">
                              Subtotal
                            </td>
                            <td className="py-1 text-right">
                              {formatMoney(minor(order.subtotal_minor), currency)}
                            </td>
                          </tr>
                          {order.tax_bps > 0 && (
                            <tr>
                              <td colSpan={4} className="py-1 text-right">
                                VAT {order.tax_bps / 100}%
                              </td>
                              <td className="py-1 text-right">
                                {formatMoney(minor(order.tax_minor), currency)}
                              </td>
                            </tr>
                          )}
                          <tr className="font-semibold">
                            <td colSpan={4} className="py-1 text-right">
                              Total
                            </td>
                            <td className="py-1 text-right">
                              {formatMoney(minor(order.total_minor), currency)}
                            </td>
                          </tr>
                        </tfoot>
                      </table>

                      {order.delivery_instructions && (
                        <div className="rounded bg-secondary-50 p-3 text-sm text-secondary-600">
                          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-secondary-500">
                            Delivery instructions
                          </p>
                          <p className="whitespace-pre-wrap">{order.delivery_instructions}</p>
                        </div>
                      )}

                      {order.notes && (
                        <div className="rounded bg-secondary-50 p-3 text-sm text-secondary-600">
                          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-secondary-500">
                            Additional comments
                          </p>
                          <p className="whitespace-pre-wrap">{order.notes}</p>
                        </div>
                      )}

                      {order.last_email_error && (
                        <p className="rounded bg-danger-50 p-3 text-sm text-danger-700">
                          The last email attempt failed: {order.last_email_error}
                        </p>
                      )}

                      {order.receipts.length > 0 && (
                        <div>
                          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-secondary-500">
                            Deliveries
                          </p>
                          <ul className="space-y-1 text-sm text-secondary-600">
                            {order.receipts.map((receipt) => (
                              <li key={receipt.id}>
                                {receipt.receipt_number} ·{" "}
                                {new Date(
                                  receipt.received_at,
                                ).toLocaleString()}
                                {receipt.document_reference &&
                                  ` · note ${receipt.document_reference}`}
                                {receipt.source === "ocr" && " · scanned"}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* ------------------------------------------------------- create */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>New purchase order</DialogTitle>
            <DialogDescription>
              Goods will be booked into the location you choose here.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label>Supplier</Label>
              <Select
                value={supplierId}
                onChange={(e) => setSupplierId(e.target.value)}
              >
                <option value="">Select a supplier</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label>Deliver to</Label>
              <Select
                value={locationId}
                onChange={(e) => setLocationId(e.target.value)}
              >
                <option value="">Select a location</option>
                {locations.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label>Required by</Label>
              <Input
                type="date"
                value={expectedDate}
                onChange={(e) => setExpectedDate(e.target.value)}
              />
            </div>
            <div>
              <Label>VAT %</Label>
              <Input
                type="number"
                step="0.01"
                min={0}
                max={100}
                value={taxPercent}
                onChange={(e) => setTaxPercent(e.target.value)}
              />
              <p className="mt-1 text-xs text-secondary-500">
                Added on top of the prices below, as a supplier quotes net.
              </p>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Items</Label>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setLines([...lines, newLine()])}
              >
                <Plus className="mr-1 h-4 w-4" />
                Add line
              </Button>
            </div>
            {lines.map((line, index) => {
              const known = catalogueByIngredient.get(line.ingredient_id);
              // M8. The quantity box counts what the supplier sells, so it has
              // to be labelled with that unit and not with the one recipes use.
              // Martin's whole point: he requests 2 cans, he cooks in grams.
              const chosen = purchasable.find((i) => i.id === line.ingredient_id);
              const orderUnit = chosen?.purchase_unit || chosen?.unit || "";
              const chosenQty = Number(line.quantity);
              return (
                <div key={line.uid} className="grid gap-2 md:grid-cols-12">
                  <div className="md:col-span-6">
                    <Select
                      value={line.ingredient_id}
                      onChange={(e) => {
                        const next = [...lines];
                        next[index] = {
                          ...line,
                          ingredient_id: e.target.value,
                        };
                        setLines(next);
                      }}
                    >
                      <option value="">Select an ingredient</option>
                      {purchasable.map((i) => (
                        <option key={i.id} value={i.id}>
                          {i.name} ({i.purchase_unit || i.unit})
                        </option>
                      ))}
                    </Select>
                    {known && (
                      <p className="mt-1 text-xs text-secondary-500">
                        Last paid{" "}
                        {formatMoney(minor(known.last_price_minor), currency)}
                        {known.supplier_sku && ` · ${known.supplier_sku}`}
                      </p>
                    )}
                  </div>
                  <div className="md:col-span-2">
                    <Input
                      type="number"
                      step="0.001"
                      min={0}
                      placeholder={orderUnit ? `Qty (${orderUnit})` : "Qty"}
                      value={line.quantity}
                      onChange={(e) => {
                        const next = [...lines];
                        next[index] = { ...line, quantity: e.target.value };
                        setLines(next);
                      }}
                    />
                    {chosen?.purchase_unit && chosenQty > 0 && (
                      <p className="mt-1 text-xs text-secondary-500">
                        = {chosenQty * chosen.units_per_purchase_unit}{" "}
                        {chosen.unit}
                      </p>
                    )}
                  </div>
                  <div className="md:col-span-3">
                    <Input
                      type="number"
                      step="0.01"
                      min={0}
                      placeholder={`Price (${currency}), optional`}
                      value={line.price}
                      onChange={(e) => {
                        const next = [...lines];
                        next[index] = { ...line, price: e.target.value };
                        setLines(next);
                      }}
                    />
                  </div>
                  <div className="md:col-span-1 flex items-center">
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={lines.length === 1}
                      onClick={() =>
                        setLines(lines.filter((l) => l.uid !== line.uid))
                      }
                    >
                      <Trash2 className="h-4 w-4 text-danger-600" />
                    </Button>
                  </div>
                </div>
              );
            })}
            <p className="text-xs text-secondary-500">
              Leave the price blank to use what you last paid this supplier, or
              the ingredient&rsquo;s recorded cost if you have never bought it
              from them.
            </p>
          </div>

          <div className="rounded-lg bg-secondary-50 p-3 text-sm">
            <div className="flex justify-between">
              <span>Subtotal</span>
              <span>{formatMoney(draftTotal.subtotal, currency)}</span>
            </div>
            <div className="flex justify-between text-secondary-600">
              <span>VAT</span>
              <span>{formatMoney(draftTotal.tax, currency)}</span>
            </div>
            <div className="mt-1 flex justify-between border-t border-secondary-200 pt-1 font-semibold">
              <span>Estimated total</span>
              <span>{formatMoney(draftTotal.total, currency)}</span>
            </div>
            <p className="mt-1 text-xs text-secondary-500">
              An estimate. The server recalculates from the prices it resolves.
            </p>
          </div>

          <div>
            <Label>Delivery instructions</Label>
            <Textarea
              rows={2}
              value={deliveryInstructions}
              onChange={(e) => setDeliveryInstructions(e.target.value)}
              placeholder="Printed on the order the supplier receives."
            />
          </div>

          <div>
            <Label>Additional comments</Label>
            <Textarea
              rows={2}
              value={additionalComments}
              onChange={(e) => setAdditionalComments(e.target.value)}
              placeholder="Anything else for the supplier. Printed under the delivery instructions."
            />
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>
              Cancel
            </Button>
            <Button disabled={saving} onClick={() => void submitCreate()}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create order
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* --------------------------------------------------------- send */}
      <Dialog
        open={!!sendFor}
        onOpenChange={(open) => !open && setSendFor(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Send {sendFor?.po_number}</DialogTitle>
            <DialogDescription>
              Marks the order as sent so it can be received against. Print it
              and pass it to the supplier however you normally do.
            </DialogDescription>
          </DialogHeader>

          {/* F39: this dialog used to collect a To address, a message and a
              BCC, and email the purchase order. The mail service it used runs
              on ANOTHER tenant's account and sending domain, so this client's
              paperwork would have gone out under someone else's identity.
              Emailing is removed; the status transition is kept. */}

          <DialogFooter className="flex-col gap-2 sm:flex-row">
            <Button
              variant="outline"
              disabled={saving}
              onClick={() => setSendFor(null)}
            >
              Cancel
            </Button>
            <Button disabled={saving} onClick={() => void submitSend()}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              <Send className="mr-2 h-4 w-4" />
              Mark as sent
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ------------------------------------------------------ receive */}
      <Dialog
        open={!!receiveFor}
        onOpenChange={(open) => !open && setReceiveFor(null)}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Receive {receiveFor?.po_number}</DialogTitle>
            <DialogDescription>
              Enter what actually arrived. Stock updates at{" "}
              {receiveFor?.location_name}.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            {/* Scan first, or skip it and type. Both end at the same button. */}
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-dashed border-secondary-300 p-3">
              <div>
                <p className="text-sm font-medium text-secondary-900">
                  Scan the delivery note
                </p>
                <p className="text-xs text-secondary-500">
                  Photograph or upload it and the quantities fill in below. You
                  still check them before anything is booked in.
                </p>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif,application/pdf"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void handleScan(file);
                }}
              />
              <Button
                size="sm"
                variant="outline"
                disabled={scanning}
                onClick={() => fileInputRef.current?.click()}
              >
                {scanning ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <ScanLine className="mr-2 h-4 w-4" />
                )}
                {scanning ? "Reading" : "Upload or photograph"}
              </Button>
            </div>

            {scan && (
              <div className="space-y-2 rounded-lg bg-secondary-50 p-3 text-sm">
                <p className="font-medium text-secondary-900">
                  Read from the document
                  {scan.supplier_name ? ` (${scan.supplier_name})` : ""}
                </p>
                {scan.notes && (
                  <p className="text-secondary-600">{scan.notes}</p>
                )}
                {scan.duplicate_line_ids.length > 0 && (
                  <p className="text-danger-700">
                    The same item was read twice. Check the quantities before
                    confirming, or the delivery will be counted double.
                  </p>
                )}
                {scan.unmatched.length > 0 && (
                  <div className="text-warning-700">
                    <p>
                      {scan.unmatched.length} row
                      {scan.unmatched.length === 1 ? "" : "s"} on the document
                      did not match this order:
                    </p>
                    <ul className="ml-4 list-disc">
                      {scan.unmatched.map((row, i) => (
                        <li key={i}>
                          {row.document_text}
                          {row.quantity ? ` (${row.quantity})` : ""}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <p className="text-xs text-secondary-500">
                  Nothing has been booked in yet. These are suggestions from the
                  document; the figures below are yours to correct.
                </p>
              </div>
            )}

            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-secondary-500">
                <tr>
                  <th className="py-1">Item</th>
                  <th className="w-20 py-1 pr-3 text-right">Still owed</th>
                  <th className="w-28 py-1 pr-3 text-right">Received now</th>
                  <th className="w-28 py-1 text-right">Price paid</th>
                </tr>
              </thead>
              <tbody>
                {receiveFor?.items.map((item) => {
                  const read = scan?.lines.find(
                    (l) => l.purchase_order_item_id === item.id,
                  );
                  return (
                  <tr key={item.id} className="border-t border-secondary-100">
                    <td className="py-2">
                      <div className="flex items-center gap-2">
                        <Thumb
                          src={item.ingredient_image_url}
                          alt={item.ingredient_name}
                          size="sm"
                        />
                        <span>
                          {item.ingredient_name}
                          <span className="ml-1 text-xs text-secondary-500">
                            ({item.unit})
                          </span>
                          {/* M8: what this many cans will put on the shelf.
                              Shown here because this is the moment stock
                              actually moves, and the number that moves is not
                              the number being typed. */}
                          {qty(item.units_per_purchase_unit) !== 1 &&
                            item.stock_unit &&
                            Number(receiveQty[item.id]) > 0 && (
                              <span className="ml-1 text-xs text-secondary-400">
                                → {Number(receiveQty[item.id]) *
                                  qty(item.units_per_purchase_unit)}{" "}
                                {item.stock_unit} into stock
                              </span>
                            )}
                        </span>
                      </div>
                      {read && (
                        <div
                          className={
                            read.confidence === "high"
                              ? "text-xs text-secondary-500"
                              : "text-xs text-warning-700"
                          }
                        >
                          read as &ldquo;{read.document_text}&rdquo;
                          {read.confidence !== "high" &&
                            ` · ${read.confidence} confidence, check this one`}
                        </div>
                      )}
                    </td>
                    <td className="py-2 pr-3 text-right tabular-nums">
                      {qty(item.quantity_outstanding)}
                    </td>
                    <td className="py-2 pr-3 text-right">
                      <Input
                        className="w-full text-right tabular-nums"
                        type="number"
                        step="0.001"
                        min={0}
                        value={receiveQty[item.id] ?? ""}
                        onChange={(e) =>
                          setReceiveQty({
                            ...receiveQty,
                            [item.id]: e.target.value,
                          })
                        }
                      />
                    </td>
                    <td className="py-2 text-right">
                      <Input
                        className="w-full text-right tabular-nums"
                        type="number"
                        step="0.01"
                        min={0}
                        value={receivePrice[item.id] ?? ""}
                        onChange={(e) =>
                          setReceivePrice({
                            ...receivePrice,
                            [item.id]: e.target.value,
                          })
                        }
                      />
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>

            <p className="text-xs text-secondary-500">
              Leave a quantity blank for anything that did not arrive; the
              balance stays owed. Changing a price records what was actually
              charged and updates that ingredient&rsquo;s cost.
            </p>

            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <Label>Delivery note number</Label>
                <Input
                  value={deliveryNote}
                  onChange={(e) => setDeliveryNote(e.target.value)}
                  placeholder="The supplier's own reference"
                />
              </div>
              <div>
                <Label>Notes</Label>
                <Input
                  value={receiveNotes}
                  onChange={(e) => setReceiveNotes(e.target.value)}
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setReceiveFor(null)}>
              Cancel
            </Button>
            <Button disabled={saving} onClick={() => void submitReceive()}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              <PackageCheck className="mr-2 h-4 w-4" />
              Book the delivery in
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default PurchaseOrdersPage;
