import { useEffect, useState } from "react";
import {
  ArrowRight,
  Loader2,
  PackageCheck,
  Plus,
  Send,
  Trash2,
  Truck,
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
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import {
  fetchTransfers,
  createTransfer,
  sendTransfer,
  receiveTransfer,
  cancelTransfer,
  fetchLocations,
} from "@/services/locationsApi";
import { fetchIngredients } from "@/services/inventoryApi";
import type {
  Location,
  Transfer,
  TransferItem,
  TransferStatus,
} from "@/types/location";
import type { Ingredient } from "@/types/inventory";

type StatusFilter = "all" | TransferStatus;

interface DraftLine {
  uid: string;
  ingredient_id: string;
  quantity: string;
}

const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All statuses" },
  { value: "draft", label: "Draft" },
  { value: "in_transit", label: "In transit" },
  { value: "received", label: "Received" },
  { value: "cancelled", label: "Cancelled" },
];

const STATUS_BADGE: Record<
  TransferStatus,
  { label: string; variant: "secondary" | "warning" | "success" | "destructive" }
> = {
  draft: { label: "Draft", variant: "secondary" },
  in_transit: { label: "In Transit", variant: "warning" },
  received: { label: "Received", variant: "success" },
  cancelled: { label: "Cancelled", variant: "destructive" },
};

let lineCounter = 0;
function newLine(): DraftLine {
  lineCounter += 1;
  return { uid: `line-${lineCounter}`, ingredient_id: "", quantity: "" };
}

/**
 * NaN means "not a usable number".
 *
 * Decimals arrive from the API as JSON **numbers** (`Num` in
 * `schemas/location.py`), while the draft-line and receive-quantity inputs on
 * this page are form strings. Both land here. Calling `.trim()` on the number
 * case is what crashed this whole page to the error boundary with
 * `n.trim is not a function` (F51), so the type is narrowed before any string
 * method is touched.
 */
function toNum(value: string | number | null | undefined): number {
  if (value === null || value === undefined) return NaN;
  if (typeof value === "number") return Number.isFinite(value) ? value : NaN;
  if (value.trim() === "") return NaN;
  const n = Number(value);
  return Number.isFinite(n) ? n : NaN;
}

function formatQty(value: string | number | null | undefined): string {
  const n = toNum(value);
  return Number.isNaN(n) ? "-" : String(n);
}

function formatTimestamp(value: string | null): string | null {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString();
}

function isShort(item: TransferItem): boolean {
  const sent = toNum(item.quantity_sent);
  const received = toNum(item.quantity_received);
  if (Number.isNaN(sent) || Number.isNaN(received)) return false;
  return received < sent;
}

function TransfersPage() {
  const { toast } = useToast();

  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [actingId, setActingId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [fromLocationId, setFromLocationId] = useState("");
  const [toLocationId, setToLocationId] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([newLine()]);

  // Receive form
  const [receiveTarget, setReceiveTarget] = useState<Transfer | null>(null);
  const [receiveQty, setReceiveQty] = useState<Record<string, string>>({});

  useEffect(() => {
    void loadReferenceData();
  }, []);

  useEffect(() => {
    void loadTransfers();
  }, [statusFilter]);

  async function loadTransfers() {
    try {
      setLoading(true);
      const data = await fetchTransfers(
        statusFilter === "all" ? undefined : { status: statusFilter },
      );
      const sorted = [...data].sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      );
      setTransfers(sorted);
    } catch {
      toast({ title: "Failed to load transfers", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }

  async function loadReferenceData() {
    try {
      const [locs, ings] = await Promise.all([
        fetchLocations(),
        fetchIngredients({ is_active: true }),
      ]);
      setLocations(locs);
      setIngredients(ings);
    } catch {
      toast({
        title: "Failed to load locations and ingredients",
        variant: "destructive",
      });
    }
  }

  // ------------------------------------------------------------------
  // Create
  // ------------------------------------------------------------------

  function resetCreateForm() {
    setFromLocationId("");
    setToLocationId("");
    setNotes("");
    setLines([newLine()]);
  }

  function openCreate() {
    resetCreateForm();
    setShowCreate(true);
  }

  function updateLine(uid: string, patch: Partial<Omit<DraftLine, "uid">>) {
    setLines((prev) =>
      prev.map((l) => (l.uid === uid ? { ...l, ...patch } : l)),
    );
  }

  function addLine() {
    setLines((prev) => [...prev, newLine()]);
  }

  function removeLine(uid: string) {
    setLines((prev) => prev.filter((l) => l.uid !== uid));
  }

  const sameLocation =
    fromLocationId !== "" && fromLocationId === toLocationId;

  const validLines = lines.filter((l) => {
    const qty = toNum(l.quantity);
    return l.ingredient_id !== "" && !Number.isNaN(qty) && qty > 0;
  });

  const hasBadLine = lines.some((l) => {
    const qty = toNum(l.quantity);
    const touched = l.ingredient_id !== "" || l.quantity.trim() !== "";
    return touched && (l.ingredient_id === "" || Number.isNaN(qty) || qty <= 0);
  });

  const canCreate =
    fromLocationId !== "" &&
    toLocationId !== "" &&
    !sameLocation &&
    validLines.length > 0 &&
    !hasBadLine;

  async function handleCreate() {
    if (!canCreate) return;
    setSaving(true);
    try {
      await createTransfer({
        from_location_id: fromLocationId,
        to_location_id: toLocationId,
        notes: notes.trim() === "" ? null : notes.trim(),
        lines: validLines.map((l) => ({
          ingredient_id: l.ingredient_id,
          quantity: Number(l.quantity),
        })),
      });
      toast({ title: "Transfer created as draft", variant: "success" });
      setShowCreate(false);
      resetCreateForm();
      await loadTransfers();
    } catch {
      toast({ title: "Failed to create transfer", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  }

  // ------------------------------------------------------------------
  // Send / Cancel
  // ------------------------------------------------------------------

  async function handleSend(transfer: Transfer) {
    setActingId(transfer.id);
    try {
      await sendTransfer(transfer.id);
      toast({
        title: `${transfer.transfer_number} sent`,
        description: "Stock has left the source location.",
        variant: "success",
      });
      await loadTransfers();
    } catch {
      toast({ title: "Failed to send transfer", variant: "destructive" });
    } finally {
      setActingId(null);
    }
  }

  async function handleCancel(transfer: Transfer) {
    if (!confirm(`Cancel transfer ${transfer.transfer_number}?`)) return;
    setActingId(transfer.id);
    try {
      await cancelTransfer(transfer.id);
      toast({ title: `${transfer.transfer_number} cancelled`, variant: "success" });
      await loadTransfers();
    } catch {
      toast({ title: "Failed to cancel transfer", variant: "destructive" });
    } finally {
      setActingId(null);
    }
  }

  // ------------------------------------------------------------------
  // Receive
  // ------------------------------------------------------------------

  function openReceive(transfer: Transfer) {
    const prefilled: Record<string, string> = {};
    for (const item of transfer.items) {
      const sent = toNum(item.quantity_sent);
      prefilled[item.id] = Number.isNaN(sent) ? "" : String(sent);
    }
    setReceiveQty(prefilled);
    setReceiveTarget(transfer);
  }

  function receiveLineError(item: TransferItem): string | null {
    const sent = toNum(item.quantity_sent);
    const entered = toNum(receiveQty[item.id]);
    if (Number.isNaN(entered)) return "Enter a number";
    if (entered < 0) return "Cannot be negative";
    if (!Number.isNaN(sent) && entered > sent)
      return `Cannot exceed ${sent} sent`;
    return null;
  }

  const receiveHasError =
    receiveTarget !== null &&
    receiveTarget.items.some((item) => receiveLineError(item) !== null);

  async function handleReceive() {
    const transfer = receiveTarget;
    if (!transfer || receiveHasError) return;
    setSaving(true);
    try {
      // Unchanged lines mean "receive everything in full", which the backend
      // does for an empty payload.
      const changed = transfer.items.some((item) => {
        const sent = toNum(item.quantity_sent);
        const entered = toNum(receiveQty[item.id]);
        return Number.isNaN(sent) || entered !== sent;
      });

      const payload = changed
        ? transfer.items.map((item) => ({
            item_id: item.id,
            quantity_received: Number(receiveQty[item.id]),
          }))
        : [];

      await receiveTransfer(transfer.id, payload);
      toast({
        title: `${transfer.transfer_number} received`,
        description: "Stock has arrived at the destination.",
        variant: "success",
      });
      setReceiveTarget(null);
      setReceiveQty({});
      await loadTransfers();
    } catch {
      toast({ title: "Failed to receive transfer", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  }

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Truck className="h-7 w-7 text-primary-600" />
          <div>
            <h1 className="text-pos-2xl font-bold text-secondary-900">
              Stock Transfers
            </h1>
            <p className="text-sm text-secondary-500">
              Stock leaves the source when sent and only arrives when received.
              In transit it belongs to neither site.
            </p>
          </div>
        </div>
        <Button onClick={openCreate} className="gap-2 min-h-[48px]">
          <Plus className="h-4 w-4" />
          New Transfer
        </Button>
      </div>

      <div className="flex items-center gap-3">
        <Label className="text-sm text-secondary-600">Status</Label>
        <Select
          className="w-56"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
        >
          {STATUS_FILTERS.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </Select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
        </div>
      ) : transfers.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-secondary-400">
            {statusFilter === "all"
              ? "No transfers yet. Create one to move stock between locations."
              : `No transfers with status "${statusFilter}".`}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {transfers.map((t) => {
            const badge = STATUS_BADGE[t.status];
            const createdAt = formatTimestamp(t.created_at);
            const sentAt = formatTimestamp(t.sent_at);
            const receivedAt = formatTimestamp(t.received_at);
            const busy = actingId === t.id;

            return (
              <Card key={t.id}>
                <CardContent className="pt-4 space-y-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-3">
                        <p className="font-semibold text-secondary-900">
                          {t.transfer_number}
                        </p>
                        <Badge variant={badge.variant}>{badge.label}</Badge>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-secondary-600">
                        <span>{t.from_location_name}</span>
                        <ArrowRight className="h-4 w-4 text-secondary-400" />
                        <span>{t.to_location_name}</span>
                      </div>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-secondary-500">
                        {createdAt && <span>Created: {createdAt}</span>}
                        {sentAt && <span>Sent: {sentAt}</span>}
                        {receivedAt && <span>Received: {receivedAt}</span>}
                      </div>
                      {t.notes && (
                        <p className="text-sm text-secondary-500">{t.notes}</p>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      {t.status === "draft" && (
                        <>
                          <Button
                            size="sm"
                            className="gap-2"
                            disabled={busy}
                            onClick={() => void handleSend(t)}
                          >
                            {busy ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Send className="h-4 w-4" />
                            )}
                            Send
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="gap-2 text-danger-600"
                            disabled={busy}
                            onClick={() => void handleCancel(t)}
                          >
                            <XCircle className="h-4 w-4" />
                            Cancel
                          </Button>
                        </>
                      )}
                      {t.status === "in_transit" && (
                        <>
                          <Button
                            size="sm"
                            className="gap-2"
                            disabled={busy}
                            onClick={() => openReceive(t)}
                          >
                            <PackageCheck className="h-4 w-4" />
                            Receive
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="gap-2 text-danger-600"
                            disabled={busy}
                            onClick={() => void handleCancel(t)}
                          >
                            <XCircle className="h-4 w-4" />
                            Cancel
                          </Button>
                        </>
                      )}
                    </div>
                  </div>

                  {t.items.length === 0 ? (
                    <p className="text-sm text-secondary-400">
                      This transfer has no lines.
                    </p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-secondary-200 text-left text-xs uppercase tracking-wide text-secondary-500">
                            <th className="py-2 pr-4 font-medium">Ingredient</th>
                            <th className="py-2 pr-4 font-medium">Sent</th>
                            <th className="py-2 pr-4 font-medium">Received</th>
                            <th className="py-2 pr-4 font-medium">Unit</th>
                            <th className="py-2 font-medium" />
                          </tr>
                        </thead>
                        <tbody>
                          {t.items.map((item) => (
                            <tr
                              key={item.id}
                              className="border-b border-secondary-100 last:border-0"
                            >
                              <td className="py-2 pr-4 text-secondary-900">
                                {item.ingredient_name}
                              </td>
                              <td className="py-2 pr-4 text-secondary-700">
                                {formatQty(item.quantity_sent)}
                              </td>
                              <td className="py-2 pr-4 text-secondary-700">
                                {item.quantity_received === null
                                  ? "-"
                                  : formatQty(item.quantity_received)}
                              </td>
                              <td className="py-2 pr-4 text-secondary-500">
                                {item.unit}
                              </td>
                              <td className="py-2">
                                {isShort(item) && (
                                  <Badge variant="destructive">Short</Badge>
                                )}
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
          })}
        </div>
      )}

      {/* Create Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>New Transfer</DialogTitle>
            <DialogDescription>
              Creates a draft. Nothing moves until you send it.
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>From location</Label>
                <Select
                  value={fromLocationId}
                  onChange={(e) => setFromLocationId(e.target.value)}
                >
                  <option value="">Select source</option>
                  {locations.map((loc) => (
                    <option key={loc.id} value={loc.id}>
                      {loc.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-2">
                <Label>To location</Label>
                <Select
                  value={toLocationId}
                  onChange={(e) => setToLocationId(e.target.value)}
                >
                  <option value="">Select destination</option>
                  {locations.map((loc) => (
                    <option key={loc.id} value={loc.id}>
                      {loc.name}
                    </option>
                  ))}
                </Select>
              </div>
            </div>

            {sameLocation && (
              <p className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">
                Source and destination must be different locations.
              </p>
            )}

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Lines</Label>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="gap-2"
                  onClick={addLine}
                >
                  <Plus className="h-4 w-4" />
                  Add line
                </Button>
              </div>

              {lines.length === 0 ? (
                <p className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">
                  Add at least one line to transfer.
                </p>
              ) : (
                <div className="space-y-2">
                  {lines.map((line) => {
                    const ingredient = ingredients.find(
                      (i) => i.id === line.ingredient_id,
                    );
                    const qty = toNum(line.quantity);
                    const qtyInvalid =
                      line.quantity.trim() !== "" &&
                      (Number.isNaN(qty) || qty <= 0);

                    return (
                      <div key={line.uid} className="flex items-start gap-2">
                        <div className="flex-1">
                          <Select
                            value={line.ingredient_id}
                            onChange={(e) =>
                              updateLine(line.uid, {
                                ingredient_id: e.target.value,
                              })
                            }
                          >
                            <option value="">Select ingredient</option>
                            {ingredients.map((ing) => (
                              <option key={ing.id} value={ing.id}>
                                {ing.name} ({ing.unit})
                              </option>
                            ))}
                          </Select>
                        </div>
                        <div className="w-32">
                          <Input
                            type="number"
                            min={0}
                            step="any"
                            placeholder="Qty"
                            value={line.quantity}
                            onChange={(e) =>
                              updateLine(line.uid, { quantity: e.target.value })
                            }
                          />
                          {qtyInvalid && (
                            <p className="mt-1 text-xs text-danger-600">
                              Must be greater than 0
                            </p>
                          )}
                        </div>
                        <div className="w-14 pt-2 text-sm text-secondary-500">
                          {ingredient?.unit ?? ""}
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="text-danger-500 hover:text-danger-700"
                          onClick={() => removeLine(line.uid)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label>Notes</Label>
              <Textarea
                rows={2}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Optional note for the receiving site"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>
              Cancel
            </Button>
            <Button onClick={() => void handleCreate()} disabled={saving || !canCreate}>
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Create Draft"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Receive Dialog */}
      <Dialog
        open={receiveTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setReceiveTarget(null);
            setReceiveQty({});
          }
        }}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              Receive {receiveTarget?.transfer_number ?? ""}
            </DialogTitle>
            <DialogDescription>
              Reduce a quantity if less arrived than was sent. The shortfall
              stays on record.
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-[60vh] space-y-3 overflow-y-auto pr-1">
            {receiveTarget?.items.map((item) => {
              const sent = toNum(item.quantity_sent);
              const error = receiveLineError(item);
              return (
                <div
                  key={item.id}
                  className="flex items-start justify-between gap-3 border-b border-secondary-100 pb-3 last:border-0"
                >
                  <div>
                    <p className="text-sm font-medium text-secondary-900">
                      {item.ingredient_name}
                    </p>
                    <p className="text-xs text-secondary-500">
                      Sent: {formatQty(item.quantity_sent)} {item.unit}
                    </p>
                  </div>
                  <div className="w-40">
                    <Input
                      type="number"
                      min={0}
                      max={Number.isNaN(sent) ? undefined : sent}
                      step="any"
                      value={receiveQty[item.id] ?? ""}
                      onChange={(e) =>
                        setReceiveQty((prev) => ({
                          ...prev,
                          [item.id]: e.target.value,
                        }))
                      }
                    />
                    {error && (
                      <p className="mt-1 text-xs text-danger-600">{error}</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setReceiveTarget(null);
                setReceiveQty({});
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={() => void handleReceive()}
              disabled={saving || receiveHasError}
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Confirm Receipt"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default TransfersPage;
