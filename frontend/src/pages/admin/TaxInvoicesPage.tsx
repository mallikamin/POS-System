import { useEffect, useMemo, useState } from "react";
import { FileText, Loader2, Printer, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { formatMoney } from "@/utils/currency";
import {
  fetchLocationOrders,
  fetchLocations,
  fetchTaxInvoice,
} from "@/services/locationsApi";
import type {
  Location,
  LocationOrderRow,
  TaxInvoiceData,
} from "@/types/location";

/**
 * A4 VAT tax invoices for a location's sales.
 *
 * The invoice itself is rendered on screen and printed from the browser rather
 * than generated as a PDF server-side. That keeps one template instead of two
 * that drift apart, and the print stylesheet below hides the whole application
 * chrome so what reaches the paper is only the document.
 */
function TaxInvoicesPage() {
  const { toast } = useToast();

  const [locations, setLocations] = useState<Location[]>([]);
  const [locationId, setLocationId] = useState<string>("");
  const [orders, setOrders] = useState<LocationOrderRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingOrders, setLoadingOrders] = useState(false);
  const [invoice, setInvoice] = useState<TaxInvoiceData | null>(null);
  const [loadingInvoice, setLoadingInvoice] = useState(false);

  useEffect(() => {
    void loadLocations();
  }, []);

  useEffect(() => {
    if (locationId) void loadOrders(locationId);
  }, [locationId]);

  async function loadLocations() {
    try {
      setLoading(true);
      const data = await fetchLocations(true);
      setLocations(data);
      // Default to a site that actually issues tax invoices, so the page opens
      // on something useful rather than an empty delivery kitchen.
      const preferred =
        data.find((l) => l.invoice_format === "a4_tax_invoice") ?? data[0];
      if (preferred) setLocationId(preferred.id);
    } catch {
      toast({ title: "Failed to load locations", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }

  async function loadOrders(id: string) {
    try {
      setLoadingOrders(true);
      setOrders(await fetchLocationOrders(id));
    } catch {
      toast({ title: "Failed to load sales", variant: "destructive" });
    } finally {
      setLoadingOrders(false);
    }
  }

  async function openInvoice(orderId: string) {
    try {
      setLoadingInvoice(true);
      setInvoice(await fetchTaxInvoice(orderId));
      // F36: the document renders below the sales table, well past the fold,
      // so clicking "Tax Invoice" looked like nothing had happened -- it was
      // reported as a dead button during UAT and only found by scrolling on a
      // hunch. Bring it into view so the click has a visible result.
      requestAnimationFrame(() => {
        document
          .getElementById("tax-invoice-document")
          ?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    } catch {
      toast({ title: "Failed to build the tax invoice", variant: "destructive" });
    } finally {
      setLoadingInvoice(false);
    }
  }

  const selected = useMemo(
    () => locations.find((l) => l.id === locationId) ?? null,
    [locations, locationId],
  );

  const currency = invoice?.currency ?? "AED";
  const money = (minor: number) => formatMoney(minor, currency);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Screen-only chrome. The print stylesheet at the end hides all of it. */}
      <div className="no-print space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Tax Invoices</h1>
          <p className="text-sm text-secondary-500">
            A4 VAT invoices for B2B and wholesale sales. Carries the location's
            registered legal name and TRN, with VAT shown as its own figure.
          </p>
        </div>

        <Card>
          <CardContent className="space-y-4 pt-6">
            <div className="max-w-md">
              <Label htmlFor="location">Location</Label>
              <Select
                id="location"
                value={locationId}
                onChange={(e) => setLocationId(e.target.value)}
              >
                {locations.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name} ({l.code})
                  </option>
                ))}
              </Select>
            </div>

            {/* F35: an amber banner used to appear here whenever the site's
                invoice_format was thermal_ticket, telling the reader to switch
                the format "so it carries a legal name and TRN". That was
                false. invoice_format only decides which document the site
                prints by DEFAULT; it has never gated the legal fields, and
                these invoices carry the TRN either way. The banner below is
                the real check: it fires on a site that genuinely has no TRN. */}

            {selected && !selected.tax_registration_number && (
              <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
                <strong>{selected.name}</strong> has no Tax Registration Number.
                An invoice without a TRN is not a valid tax invoice. Add one on
                the Locations screen before sending this to a customer.
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            {loadingOrders ? (
              <div className="flex h-32 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-primary-600" />
              </div>
            ) : orders.length === 0 ? (
              <div className="py-10 text-center">
                <FileText className="mx-auto h-10 w-10 text-secondary-300" />
                <p className="mt-3 font-medium text-secondary-700">
                  No sales at this location yet
                </p>
                <p className="text-sm text-secondary-500">
                  Completed sales recorded against this location will appear
                  here, ready to issue as a tax invoice.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-secondary-500">
                      <th className="py-2 pr-4 font-medium">Order</th>
                      <th className="py-2 pr-4 font-medium">Date</th>
                      <th className="py-2 pr-4 font-medium">Customer</th>
                      <th className="py-2 pr-4 font-medium">Channel</th>
                      <th className="py-2 pr-4 font-medium">Status</th>
                      <th className="py-2 pr-4 text-right font-medium">Total</th>
                      <th className="py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map((o) => (
                      <tr key={o.id} className="border-b last:border-0">
                        <td className="py-2 pr-4 font-mono">{o.order_number}</td>
                        <td className="py-2 pr-4">
                          {new Date(o.created_at).toLocaleDateString()}
                        </td>
                        <td className="py-2 pr-4">{o.customer_name ?? "-"}</td>
                        <td className="py-2 pr-4">{o.channel_name ?? "Direct"}</td>
                        <td className="py-2 pr-4">
                          <Badge
                            variant={
                              o.payment_status === "paid" ? "success" : "secondary"
                            }
                          >
                            {o.payment_status}
                          </Badge>
                        </td>
                        <td className="py-2 pr-4 text-right font-medium">
                          {formatMoney(o.total_minor, currency)}
                        </td>
                        <td className="py-2 text-right">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => void openInvoice(o.id)}
                            disabled={loadingInvoice}
                          >
                            Tax Invoice
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {invoice && (
        <>
          <div className="no-print flex items-center justify-end gap-2">
            <Button variant="outline" onClick={() => setInvoice(null)}>
              <X className="mr-2 h-4 w-4" />
              Close
            </Button>
            <Button onClick={() => window.print()}>
              <Printer className="mr-2 h-4 w-4" />
              Print
            </Button>
          </div>

          <div
            id="tax-invoice-document"
            className="mx-auto max-w-[210mm] bg-white p-10 text-secondary-900 shadow-sm print:shadow-none"
          >
            <div className="flex items-start justify-between border-b-2 border-secondary-900 pb-4">
              <div>
                <h2 className="text-2xl font-bold tracking-wide">
                  {invoice.document_title}
                </h2>
                <p className="mt-1 text-sm">
                  Invoice number:{" "}
                  <span className="font-mono font-semibold">
                    {invoice.invoice_number}
                  </span>
                </p>
                <p className="text-sm">
                  Order reference:{" "}
                  <span className="font-mono">{invoice.order_number}</span>
                </p>
              </div>
              <div className="text-right text-sm">
                <p>
                  Date of issue:{" "}
                  <span className="font-semibold">
                    {new Date(invoice.issue_date).toLocaleDateString()}
                  </span>
                </p>
                <p className="mt-1">Currency: {invoice.currency}</p>
              </div>
            </div>

            <div className="mt-6 grid grid-cols-2 gap-8 text-sm">
              <div>
                <p className="mb-1 font-semibold uppercase tracking-wide text-secondary-500">
                  Supplier
                </p>
                <p className="font-semibold">{invoice.supplier.name}</p>
                {invoice.supplier.trn && (
                  <p>
                    TRN: <span className="font-mono">{invoice.supplier.trn}</span>
                  </p>
                )}
                {invoice.supplier.address_line1 && (
                  <p>{invoice.supplier.address_line1}</p>
                )}
                {invoice.supplier.address_line2 && (
                  <p>{invoice.supplier.address_line2}</p>
                )}
                <p>
                  {[invoice.supplier.city, invoice.supplier.country]
                    .filter(Boolean)
                    .join(", ")}
                </p>
                {invoice.supplier.phone && <p>{invoice.supplier.phone}</p>}
                {invoice.supplier.email && <p>{invoice.supplier.email}</p>}
              </div>

              <div>
                <p className="mb-1 font-semibold uppercase tracking-wide text-secondary-500">
                  Bill to
                </p>
                {invoice.recipient ? (
                  <>
                    <p className="font-semibold">{invoice.recipient.name}</p>
                    {invoice.recipient.trn && (
                      <p>
                        TRN:{" "}
                        <span className="font-mono">{invoice.recipient.trn}</span>
                      </p>
                    )}
                    {invoice.recipient.address_line1 && (
                      <p>{invoice.recipient.address_line1}</p>
                    )}
                    {invoice.recipient.phone && <p>{invoice.recipient.phone}</p>}
                  </>
                ) : (
                  <p className="text-secondary-500">Cash sale</p>
                )}
              </div>
            </div>

            <table className="mt-8 w-full text-sm">
              <thead>
                <tr className="border-y bg-secondary-50 text-left">
                  <th className="py-2 pl-2 pr-4 font-semibold">Description</th>
                  <th className="py-2 pr-4 text-right font-semibold">Qty</th>
                  <th className="py-2 pr-4 text-right font-semibold">
                    Unit price
                  </th>
                  <th className="py-2 pr-4 text-right font-semibold">Net</th>
                  <th className="py-2 pr-4 text-right font-semibold">
                    VAT {(invoice.vat_rate_bps / 100).toFixed(0)}%
                  </th>
                  <th className="py-2 pr-2 text-right font-semibold">Total</th>
                </tr>
              </thead>
              <tbody>
                {invoice.lines.map((line, i) => (
                  <tr key={`${line.description}-${i}`} className="border-b">
                    <td className="py-2 pl-2 pr-4">{line.description}</td>
                    <td className="py-2 pr-4 text-right">{line.quantity}</td>
                    <td className="py-2 pr-4 text-right">
                      {money(line.unit_price_net_minor)}
                    </td>
                    <td className="py-2 pr-4 text-right">
                      {money(line.line_net_minor)}
                    </td>
                    <td className="py-2 pr-4 text-right">
                      {money(line.vat_amount_minor)}
                    </td>
                    <td className="py-2 pr-2 text-right font-medium">
                      {money(line.line_gross_minor)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="mt-6 flex justify-end">
              <div className="w-72 space-y-1 text-sm">
                <div className="flex justify-between">
                  <span>Subtotal (net)</span>
                  <span>{money(invoice.subtotal_net_minor)}</span>
                </div>
                {invoice.discount_minor > 0 && (
                  <div className="flex justify-between">
                    <span>Discount</span>
                    <span>-{money(invoice.discount_minor)}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span>VAT ({(invoice.vat_rate_bps / 100).toFixed(0)}%)</span>
                  <span>{money(invoice.vat_total_minor)}</span>
                </div>
                <div className="flex justify-between border-t-2 border-secondary-900 pt-2 text-base font-bold">
                  <span>Total payable</span>
                  <span>{money(invoice.total_gross_minor)}</span>
                </div>
              </div>
            </div>

            <div className="mt-8 border-t pt-4 text-xs text-secondary-500">
              {invoice.prices_include_vat && (
                <p>
                  Prices are VAT inclusive. The net and VAT figures above are
                  derived from the amount charged.
                </p>
              )}
              <p className="mt-1">
                Payment status: {invoice.payment_status}
                {invoice.location_name ? ` | Issued at: ${invoice.location_name}` : ""}
              </p>
              {invoice.notes && <p className="mt-1">Notes: {invoice.notes}</p>}
            </div>
          </div>
        </>
      )}

      {/*
        Printing must produce the document alone. Hiding the app chrome by
        class is more reliable than trying to re-lay-out the whole admin shell
        for paper.
      */}
      <style>{`
        @media print {
          .no-print { display: none !important; }
          body * { visibility: hidden; }
          #tax-invoice-document, #tax-invoice-document * { visibility: visible; }
          #tax-invoice-document {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
            padding: 0;
            box-shadow: none;
          }
          @page { size: A4; margin: 16mm; }
        }
      `}</style>
    </div>
  );
}

export default TaxInvoicesPage;
