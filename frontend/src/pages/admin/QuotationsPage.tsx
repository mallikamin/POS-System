/**
 * Back-office quotations: offer a price, send it, win or lose the business.
 *
 * 🔴 Prices on this screen INCLUDE VAT, like everywhere else on the sales
 * side. The tax shown is the tax contained in the total, not added to it. The
 * price inputs take major units and convert ONCE, on submit.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  FileText,
  Loader2,
  Mail,
  Plus,
  Printer,
  Send,
  ShoppingCart,
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
import { useConfigStore } from "@/stores/configStore";
import { formatMoney } from "@/utils/currency";
import {
  convertQuotation,
  createQuotation,
  decideQuotation,
  fetchQuotationDocument,
  fetchQuotations,
  sendQuotation,
} from "@/services/quotationsApi";
import { fetchLocations } from "@/services/locationsApi";
import { fetchFullMenu } from "@/services/menuApi";
import type {
  Quotation,
  QuotationDisplayStatus,
} from "@/types/quotation";
import type { Location } from "@/types/location";

type StatusFilter = "all" | QuotationDisplayStatus;

const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "draft", label: "Draft" },
  { value: "sent", label: "Sent" },
  { value: "expired", label: "Expired" },
  { value: "accepted", label: "Accepted" },
  { value: "declined", label: "Declined" },
  { value: "converted", label: "Converted" },
];

const STATUS_BADGE: Record<
  QuotationDisplayStatus,
  { label: string; variant: "secondary" | "warning" | "success" | "destructive" }
> = {
  draft: { label: "Draft", variant: "secondary" },
  sent: { label: "Sent", variant: "warning" },
  expired: { label: "Expired", variant: "destructive" },
  accepted: { label: "Accepted", variant: "success" },
  declined: { label: "Declined", variant: "destructive" },
  converted: { label: "Ordered", variant: "success" },
};

interface MenuOption {
  id: string;
  name: string;
  price: number;
}

interface DraftLine {
  uid: string;
  menu_item_id: string;
  name: string;
  quantity: string;
  price: string;
}

let lineCounter = 0;
function newLine(): DraftLine {
  lineCounter += 1;
  return {
    uid: `quote-line-${lineCounter}`,
    menu_item_id: "",
    name: "",
    quantity: "1",
    price: "",
  };
}

function errorDetail(error: unknown, fallback = "Please try again."): string {
  return (
    (error as { response?: { data?: { detail?: string } } })?.response?.data
      ?.detail ?? fallback
  );
}

function inDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function QuotationsPage() {
  const { toast } = useToast();
  const config = useConfigStore((s) => s.config);
  const currency = config?.currency ?? "AED";
  const defaultTaxBps = config?.default_tax_rate ?? 0;

  const [quotations, setQuotations] = useState<Quotation[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [menuItems, setMenuItems] = useState<MenuOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [expanded, setExpanded] = useState<string | null>(null);

  // Create
  const [showCreate, setShowCreate] = useState(false);
  const [customerName, setCustomerName] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerTrn, setCustomerTrn] = useState("");
  const [customerAddress, setCustomerAddress] = useState("");
  const [locationId, setLocationId] = useState("");
  const [validUntil, setValidUntil] = useState(inDays(30));
  const [terms, setTerms] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([newLine()]);

  // Send / decline
  const [sendFor, setSendFor] = useState<Quotation | null>(null);
  const [sendTo, setSendTo] = useState("");
  const [sendMessage, setSendMessage] = useState("");
  const [declineFor, setDeclineFor] = useState<Quotation | null>(null);
  const [declineReason, setDeclineReason] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [rows, locs, menu] = await Promise.all([
        fetchQuotations(filter === "all" ? undefined : filter),
        fetchLocations(),
        fetchFullMenu(),
      ]);
      setQuotations(rows);
      setLocations(locs);
      setMenuItems(
        menu.categories.flatMap((category) =>
          (category.items ?? []).map((item) => ({
            id: item.id,
            name: item.name,
            price: item.price,
          })),
        ),
      );
      setLocationId(
        (prev) => prev || locs.find((l) => l.is_default)?.id || locs[0]?.id || "",
      );
    } catch {
      toast({ title: "Could not load quotations", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [filter, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const menuById = useMemo(() => {
    const map = new Map<string, MenuOption>();
    menuItems.forEach((item) => map.set(item.id, item));
    return map;
  }, [menuItems]);

  const draftTotal = useMemo(
    () =>
      lines.reduce((sum, line) => {
        const quantity = Number(line.quantity);
        if (!Number.isFinite(quantity) || quantity <= 0) return sum;
        const typed = Number(line.price);
        const priceMinor =
          line.price.trim() !== "" && Number.isFinite(typed)
            ? Math.round(typed * 100)
            : (menuById.get(line.menu_item_id)?.price ?? 0);
        return sum + quantity * priceMinor;
      }, 0),
    [lines, menuById],
  );

  function openCreate() {
    setCustomerName("");
    setCustomerEmail("");
    setCustomerPhone("");
    setCustomerTrn("");
    setCustomerAddress("");
    setValidUntil(inDays(30));
    setTerms("");
    setNotes("");
    setLines([newLine()]);
    setShowCreate(true);
  }

  async function submitCreate() {
    const usable = lines.filter(
      (line) =>
        Number(line.quantity) > 0 &&
        (line.menu_item_id || line.name.trim()),
    );
    if (!customerName.trim() || usable.length === 0) {
      toast({
        title: "Incomplete quotation",
        description: "It needs a customer and at least one priced line.",
        variant: "destructive",
      });
      return;
    }
    setSaving(true);
    try {
      const quote = await createQuotation({
        customer_name: customerName.trim(),
        customer_email: customerEmail.trim() || null,
        customer_phone: customerPhone.trim() || null,
        customer_trn: customerTrn.trim() || null,
        customer_address: customerAddress.trim() || null,
        location_id: locationId || null,
        valid_until: validUntil || null,
        tax_rate_bps: defaultTaxBps,
        terms: terms.trim() || null,
        notes: notes.trim() || null,
        lines: usable.map((line) => ({
          menu_item_id: line.menu_item_id || null,
          name: line.menu_item_id ? null : line.name.trim(),
          quantity: Number(line.quantity),
          // Blank on a menu line means "use the menu price", decided on the
          // server. A free-text line must carry its own.
          unit_price_minor:
            line.price.trim() === ""
              ? null
              : Math.round(Number(line.price) * 100),
        })),
      });
      toast({ title: `${quote.quote_number} created` });
      setShowCreate(false);
      await load();
    } catch (error) {
      toast({
        title: "Could not create the quotation",
        description: errorDetail(error),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  async function openDocument(quote: Quotation) {
    try {
      const html = await fetchQuotationDocument(quote.id);
      const url = URL.createObjectURL(new Blob([html], { type: "text/html" }));
      const win = window.open(url, "_blank");
      if (!win) {
        toast({
          title: "Pop-up blocked",
          description: "Allow pop-ups to preview the quotation.",
          variant: "destructive",
        });
      }
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
      toast({
        title: "Could not open the document",
        description: errorDetail(error),
        variant: "destructive",
      });
    }
  }

  async function submitSend(skipEmail: boolean) {
    if (!sendFor) return;
    setSaving(true);
    try {
      const result = await sendQuotation(sendFor.id, {
        to: skipEmail ? null : sendTo.trim() || null,
        message: skipEmail ? null : sendMessage.trim() || null,
        skip_email: skipEmail,
      });
      if (skipEmail) {
        toast({ title: `${result.quotation.quote_number} marked as sent` });
      } else if (result.email_sent) {
        toast({
          title: "Quotation emailed",
          description: `Sent to ${result.sent_to}.`,
        });
      } else {
        toast({
          title: "Recorded as sent, but the email did NOT go out",
          description: result.error ?? "Print it and send it another way.",
          variant: "destructive",
        });
      }
      setSendFor(null);
      await load();
    } catch (error) {
      toast({
        title: "Could not send it",
        description: errorDetail(error),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  async function accept(quote: Quotation) {
    setSaving(true);
    try {
      await decideQuotation(quote.id, true);
      toast({ title: `${quote.quote_number} accepted` });
      await load();
    } catch (error) {
      toast({
        title: "Could not record the acceptance",
        description: errorDetail(error),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  async function submitDecline() {
    if (!declineFor) return;
    setSaving(true);
    try {
      await decideQuotation(declineFor.id, false, declineReason.trim() || null);
      toast({ title: `${declineFor.quote_number} declined` });
      setDeclineFor(null);
      setDeclineReason("");
      await load();
    } catch (error) {
      toast({
        title: "Could not record it",
        description: errorDetail(error),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  async function convert(quote: Quotation) {
    setSaving(true);
    try {
      const result = await convertQuotation(quote.id);
      toast({
        title: `Order ${result.order_number} created`,
        description: "At the quoted prices, not today's menu prices.",
      });
      await load();
    } catch (error) {
      toast({
        title: "Could not turn it into an order",
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
          <h1 className="text-2xl font-bold text-secondary-900">Quotations</h1>
          <p className="text-sm text-secondary-500">
            Price offered before there is an order. Send it, then record whether
            it was won.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select
            className="w-44"
            value={filter}
            onChange={(e) => setFilter(e.target.value as StatusFilter)}
          >
            {STATUS_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </Select>
          <Button onClick={openCreate}>
            <Plus className="mr-2 h-4 w-4" />
            New quotation
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-secondary-500">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          Loading
        </div>
      ) : quotations.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
            <FileText className="h-10 w-10 text-secondary-300" />
            <p className="text-secondary-600">No quotations yet.</p>
            <p className="max-w-md text-sm text-secondary-500">
              Raise one when a customer asks what something would cost. An
              accepted quotation turns into an order at the price you quoted.
            </p>
            <Button onClick={openCreate}>
              <Plus className="mr-2 h-4 w-4" />
              Raise the first one
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {quotations.map((quote) => {
            const badge = STATUS_BADGE[quote.display_status];
            const isOpen = expanded === quote.id;
            const decided =
              quote.display_status === "accepted" ||
              quote.display_status === "declined" ||
              quote.display_status === "converted";
            return (
              <Card key={quote.id}>
                <CardContent className="p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <button
                      type="button"
                      className="text-left"
                      onClick={() => setExpanded(isOpen ? null : quote.id)}
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-secondary-900">
                          {quote.quote_number}
                        </span>
                        <Badge variant={badge.variant}>{badge.label}</Badge>
                      </div>
                      <div className="mt-1 text-sm text-secondary-600">
                        {quote.customer_name}
                        {quote.location_name && ` · ${quote.location_name}`}
                      </div>
                      <div className="text-xs text-secondary-500">
                        Issued{" "}
                        {new Date(quote.issue_date).toLocaleDateString()} ·
                        valid until{" "}
                        {new Date(quote.valid_until).toLocaleDateString()}
                      </div>
                    </button>

                    <div className="flex flex-wrap items-center gap-2">
                      <div className="mr-2 text-right">
                        <div className="text-lg font-semibold text-secondary-900">
                          {formatMoney(quote.total_minor, currency)}
                        </div>
                        {quote.tax_rate_bps > 0 && (
                          <div className="text-xs text-secondary-500">
                            incl. {formatMoney(quote.tax_minor, currency)} VAT
                          </div>
                        )}
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => void openDocument(quote)}
                      >
                        <Printer className="mr-1 h-4 w-4" />
                        Print
                      </Button>
                      {(quote.status === "draft" ||
                        quote.status === "sent") && (
                        <Button
                          size="sm"
                          variant={quote.status === "draft" ? "default" : "outline"}
                          onClick={() => {
                            setSendFor(quote);
                            setSendTo(quote.customer_email ?? "");
                            setSendMessage("");
                          }}
                        >
                          {quote.status === "draft" ? (
                            <Send className="mr-1 h-4 w-4" />
                          ) : (
                            <Mail className="mr-1 h-4 w-4" />
                          )}
                          {quote.status === "draft" ? "Send" : "Resend"}
                        </Button>
                      )}
                      {quote.status === "sent" && (
                        <>
                          <Button
                            size="sm"
                            disabled={saving}
                            onClick={() => void accept(quote)}
                          >
                            <CheckCircle2 className="mr-1 h-4 w-4" />
                            Won
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setDeclineFor(quote)}
                          >
                            <XCircle className="h-4 w-4 text-danger-600" />
                          </Button>
                        </>
                      )}
                      {quote.status === "accepted" && (
                        <Button
                          size="sm"
                          disabled={saving}
                          onClick={() => void convert(quote)}
                        >
                          <ShoppingCart className="mr-1 h-4 w-4" />
                          Make it an order
                        </Button>
                      )}
                    </div>
                  </div>

                  {isOpen && (
                    <div className="mt-4 space-y-3 border-t border-secondary-100 pt-4">
                      <table className="w-full text-sm">
                        <thead className="text-left text-xs uppercase tracking-wide text-secondary-500">
                          <tr>
                            <th className="py-1">Item</th>
                            <th className="py-1 text-right">Qty</th>
                            <th className="py-1 text-right">Price</th>
                            <th className="py-1 text-right">Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {quote.items.map((item) => (
                            <tr
                              key={item.id}
                              className="border-t border-secondary-100"
                            >
                              <td className="py-2">
                                {item.name}
                                {item.description && (
                                  <div className="text-xs text-secondary-500">
                                    {item.description}
                                  </div>
                                )}
                              </td>
                              <td className="py-2 text-right">
                                {item.quantity}
                              </td>
                              <td className="py-2 text-right">
                                {formatMoney(item.unit_price_minor, currency)}
                              </td>
                              <td className="py-2 text-right">
                                {formatMoney(item.line_total_minor, currency)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                        <tfoot className="border-t border-secondary-200">
                          <tr>
                            <td colSpan={3} className="py-1 text-right">
                              Subtotal
                            </td>
                            <td className="py-1 text-right">
                              {formatMoney(quote.subtotal_minor, currency)}
                            </td>
                          </tr>
                          {quote.discount_minor > 0 && (
                            <tr>
                              <td colSpan={3} className="py-1 text-right">
                                Discount
                              </td>
                              <td className="py-1 text-right">
                                -{formatMoney(quote.discount_minor, currency)}
                              </td>
                            </tr>
                          )}
                          {quote.tax_rate_bps > 0 && (
                            <tr className="text-secondary-500">
                              <td colSpan={3} className="py-1 text-right">
                                of which VAT {quote.tax_rate_bps / 100}%
                              </td>
                              <td className="py-1 text-right">
                                {formatMoney(quote.tax_minor, currency)}
                              </td>
                            </tr>
                          )}
                          <tr className="font-semibold">
                            <td colSpan={3} className="py-1 text-right">
                              Total
                            </td>
                            <td className="py-1 text-right">
                              {formatMoney(quote.total_minor, currency)}
                            </td>
                          </tr>
                        </tfoot>
                      </table>

                      {quote.terms && (
                        <p className="rounded bg-secondary-50 p-3 text-sm text-secondary-600">
                          {quote.terms}
                        </p>
                      )}
                      {quote.decline_reason && (
                        <p className="rounded bg-danger-50 p-3 text-sm text-danger-700">
                          Declined: {quote.decline_reason}
                        </p>
                      )}
                      {quote.last_email_error && (
                        <p className="rounded bg-danger-50 p-3 text-sm text-danger-700">
                          The last email attempt failed: {quote.last_email_error}
                        </p>
                      )}
                      {decided && quote.decided_at && (
                        <p className="text-xs text-secondary-500">
                          Decided {new Date(quote.decided_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* -------------------------------------------------------- create */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>New quotation</DialogTitle>
            <DialogDescription>
              Prices include VAT, as on the rest of the system.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label>Customer</Label>
              <Input
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                placeholder="Emirates Catering Co"
              />
            </div>
            <div>
              <Label>Email</Label>
              <Input
                type="email"
                value={customerEmail}
                onChange={(e) => setCustomerEmail(e.target.value)}
              />
            </div>
            <div>
              <Label>Phone</Label>
              <Input
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
              />
            </div>
            <div>
              <Label>Their TRN (for a B2B customer)</Label>
              <Input
                value={customerTrn}
                onChange={(e) => setCustomerTrn(e.target.value)}
              />
            </div>
            <div className="md:col-span-2">
              <Label>Address</Label>
              <Input
                value={customerAddress}
                onChange={(e) => setCustomerAddress(e.target.value)}
              />
            </div>
            <div>
              <Label>Quoting from</Label>
              <Select
                value={locationId}
                onChange={(e) => setLocationId(e.target.value)}
              >
                {locations.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label>Valid until</Label>
              <Input
                type="date"
                value={validUntil}
                onChange={(e) => setValidUntil(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Lines</Label>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setLines([...lines, newLine()])}
              >
                <Plus className="mr-1 h-4 w-4" />
                Add line
              </Button>
            </div>
            {lines.map((line, index) => (
              <div key={line.uid} className="grid gap-2 md:grid-cols-12">
                <div className="md:col-span-6">
                  <Select
                    value={line.menu_item_id}
                    onChange={(e) => {
                      const next = [...lines];
                      next[index] = { ...line, menu_item_id: e.target.value };
                      setLines(next);
                    }}
                  >
                    <option value="">Something else (type it below)</option>
                    {menuItems.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name} · {formatMoney(item.price, currency)}
                      </option>
                    ))}
                  </Select>
                  {!line.menu_item_id && (
                    <Input
                      className="mt-1"
                      placeholder="Delivery to Abu Dhabi"
                      value={line.name}
                      onChange={(e) => {
                        const next = [...lines];
                        next[index] = { ...line, name: e.target.value };
                        setLines(next);
                      }}
                    />
                  )}
                </div>
                <div className="md:col-span-2">
                  <Input
                    type="number"
                    min={1}
                    placeholder="Qty"
                    value={line.quantity}
                    onChange={(e) => {
                      const next = [...lines];
                      next[index] = { ...line, quantity: e.target.value };
                      setLines(next);
                    }}
                  />
                </div>
                <div className="md:col-span-3">
                  <Input
                    type="number"
                    step="0.01"
                    min={0}
                    placeholder={
                      line.menu_item_id
                        ? `Price (${currency}), optional`
                        : `Price (${currency})`
                    }
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
            ))}
            <p className="text-xs text-secondary-500">
              Leave the price blank on a menu line to quote today&rsquo;s menu
              price. Whatever is used is fixed onto the quotation, so the offer
              does not change if the menu does.
            </p>
          </div>

          <div className="rounded-lg bg-secondary-50 p-3 text-sm">
            <div className="flex justify-between font-semibold">
              <span>Total (VAT included)</span>
              <span>{formatMoney(draftTotal, currency)}</span>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <Label>Terms</Label>
              <Textarea
                rows={2}
                value={terms}
                onChange={(e) => setTerms(e.target.value)}
                placeholder="50% deposit on acceptance."
              />
            </div>
            <div>
              <Label>Notes</Label>
              <Textarea
                rows={2}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>
              Cancel
            </Button>
            <Button disabled={saving} onClick={() => void submitCreate()}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create quotation
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---------------------------------------------------------- send */}
      <Dialog
        open={!!sendFor}
        onOpenChange={(open) => !open && setSendFor(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Send {sendFor?.quote_number}</DialogTitle>
            <DialogDescription>
              The customer receives the full quotation as an email.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>To</Label>
              <Input
                type="email"
                value={sendTo}
                onChange={(e) => setSendTo(e.target.value)}
              />
            </div>
            <div>
              <Label>Message (optional)</Label>
              <Textarea
                rows={3}
                value={sendMessage}
                onChange={(e) => setSendMessage(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter className="flex-col gap-2 sm:flex-row">
            <Button
              variant="outline"
              disabled={saving}
              onClick={() => void submitSend(true)}
            >
              Mark sent without emailing
            </Button>
            <Button disabled={saving} onClick={() => void submitSend(false)}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              <Send className="mr-2 h-4 w-4" />
              Send by email
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ------------------------------------------------------- decline */}
      <Dialog
        open={!!declineFor}
        onOpenChange={(open) => !open && setDeclineFor(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {declineFor?.quote_number} was not taken up
            </DialogTitle>
            <DialogDescription>
              Worth recording why. Lost quotations are the cheapest market
              research a business gets.
            </DialogDescription>
          </DialogHeader>
          <div>
            <Label>Reason</Label>
            <Textarea
              rows={3}
              value={declineReason}
              onChange={(e) => setDeclineReason(e.target.value)}
              placeholder="Went with another supplier on price"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeclineFor(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={saving}
              onClick={() => void submitDecline()}
            >
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Record as declined
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default QuotationsPage;
