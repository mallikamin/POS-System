import { useEffect, useState } from "react";
import { isAxiosError } from "axios";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import * as paymentsApi from "@/services/paymentsApi";
import type { CashDrawerSessionResponse, CashDrawerSummary } from "@/types/payment";
import { formatMoney, getCurrencyDef, majorToMinor } from "@/utils/currency";
import { formatDateTime } from "@/utils/localDate";

/**
 * The cash drawer (Danny's D-73): open with a counted float, close with a
 * counted amount against what should be there.
 *
 * Until 2026-09-26 the only drawer controls were a card on the single-order
 * payment page that opened with a float of 0 and closed with a count of 0,
 * without asking either figure, and dine-in never showed it at all. This
 * dialog is reached from the POS header, so every channel has it.
 *
 * "Expected" comes from the server and is the same figure the Z-Report shows
 * for this drawer (D-68): float + cash sales - cash refunds - cash paid out
 * + other cash in, the last two being today's cash expenses and cash income.
 */
interface CashDrawerDialogProps {
  open: boolean;
  onClose: () => void;
  /** Called after a drawer is opened or closed, so the header can refresh. */
  onChanged: () => void;
}

type View =
  | { kind: "loading" }
  | { kind: "closed" }
  | { kind: "open"; summary: CashDrawerSummary }
  | { kind: "result"; session: CashDrawerSessionResponse; attached: number };

function errorDetail(err: unknown): string {
  const detail = isAxiosError(err) ? err.response?.data?.detail : undefined;
  return typeof detail === "string" ? detail : "Please try again.";
}

function parseAmount(text: string): number | null {
  if (text.trim() === "") return null;
  const value = Number(text);
  return Number.isFinite(value) && value >= 0 ? value : null;
}

function Line({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div
      className={`flex justify-between gap-4 py-1 ${
        strong ? "border-t border-secondary-200 pt-2 font-semibold text-secondary-900" : "text-secondary-700"
      }`}
    >
      <span>{label}</span>
      <span className="tabular-nums">{value}</span>
    </div>
  );
}

function Difference({ diff }: { diff: number }) {
  if (diff === 0) {
    return <p className="font-semibold text-success-700">Exact: the drawer matches.</p>;
  }
  return diff > 0 ? (
    <p className="font-semibold text-success-700">Over by {formatMoney(diff)}</p>
  ) : (
    <p className="font-semibold text-danger-600">Short by {formatMoney(-diff)}</p>
  );
}

export function CashDrawerDialog({ open, onClose, onChanged }: CashDrawerDialogProps) {
  const { toast } = useToast();
  const symbol = getCurrencyDef().symbol.trim();
  const [view, setView] = useState<View>({ kind: "loading" });
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setView({ kind: "loading" });
    setAmount("");
    setNote("");
    setFiles([]);
    setConfirming(false);
    paymentsApi
      .fetchDrawerSummary()
      .then((summary) => setView(summary ? { kind: "open", summary } : { kind: "closed" }))
      .catch((err) => {
        toast({ title: "Drawer not loaded", description: errorDetail(err), variant: "destructive" });
        onClose();
      });
  }, [open, toast, onClose]);

  const value = parseAmount(amount);

  async function handleOpen() {
    if (value === null) return;
    setBusy(true);
    try {
      const session = await paymentsApi.openDrawer({ opening_float: majorToMinor(value) });
      toast({
        title: "Drawer opened",
        description: `Float ${formatMoney(session.opening_float)}.`,
        variant: "success",
      });
      onChanged();
      onClose();
    } catch (err) {
      toast({ title: "Drawer not opened", description: errorDetail(err), variant: "destructive" });
    } finally {
      setBusy(false);
    }
  }

  async function handleClose() {
    if (value === null) return;
    setBusy(true);
    try {
      const session = await paymentsApi.closeDrawer({
        closing_balance_counted: majorToMinor(value),
        note: note.trim() || undefined,
      });
      // Files go up after the close, against the session id. Each failure is
      // reported on its own: one bad file must not undo a drawer that closed.
      let attached = 0;
      for (const file of files) {
        try {
          await paymentsApi.uploadDrawerAttachment(session.id, file);
          attached += 1;
        } catch (err) {
          toast({
            title: `${file.name} not attached`,
            description: errorDetail(err),
            variant: "destructive",
          });
        }
      }
      setView({ kind: "result", session, attached });
      onChanged();
    } catch (err) {
      setConfirming(false);
      toast({ title: "Drawer not closed", description: errorDetail(err), variant: "destructive" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && !busy && onClose()}>
      <DialogContent className="sm:max-w-md">
        {view.kind === "loading" && (
          <div className="flex justify-center py-10">
            <Loader2 className="h-6 w-6 animate-spin text-primary-600" />
          </div>
        )}

        {view.kind === "closed" && (
          <>
            <DialogHeader>
              <DialogTitle>Open the cash drawer</DialogTitle>
              <DialogDescription>
                Count the cash you are starting with (the float) and enter it.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-1">
              <Label htmlFor="drawer-float">Opening float ({symbol})</Label>
              <Input
                id="drawer-float"
                type="number"
                inputMode="decimal"
                min={0}
                step="any"
                autoFocus
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={onClose} className="min-h-[48px]">
                Cancel
              </Button>
              <Button
                onClick={() => void handleOpen()}
                disabled={busy || value === null}
                className="min-h-[48px]"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Open drawer"}
              </Button>
            </DialogFooter>
          </>
        )}

        {view.kind === "open" && (
          <>
            <DialogHeader>
              <DialogTitle>Close the cash drawer</DialogTitle>
              <DialogDescription>
                Opened {formatDateTime(view.summary.opened_at)}
                {view.summary.opened_by_name ? ` by ${view.summary.opened_by_name}` : ""}.
              </DialogDescription>
            </DialogHeader>
            <div className="text-sm">
              <Line label="Opening float" value={formatMoney(view.summary.opening_float)} />
              <Line label="+ Cash sales" value={formatMoney(view.summary.cash_taken)} />
              <Line label="- Cash refunds" value={formatMoney(view.summary.cash_refunds)} />
              <Line label="- Cash expenses today" value={formatMoney(view.summary.cash_paid_out)} />
              <Line label="+ Other cash income today" value={formatMoney(view.summary.other_cash_in)} />
              <Line
                label="Should be in the drawer"
                value={formatMoney(view.summary.expected_in_drawer)}
                strong
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="drawer-count">Cash counted ({symbol})</Label>
              <Input
                id="drawer-count"
                type="number"
                inputMode="decimal"
                min={0}
                step="any"
                autoFocus
                value={amount}
                onChange={(e) => {
                  setAmount(e.target.value);
                  setConfirming(false);
                }}
              />
            </div>
            {value !== null && (
              <Difference diff={majorToMinor(value) - view.summary.expected_in_drawer} />
            )}
            <div className="space-y-1">
              <Label htmlFor="drawer-note">Note or reason (optional)</Label>
              <Textarea
                id="drawer-note"
                rows={2}
                maxLength={500}
                placeholder="e.g. Rs 50 short: change given to a regular"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="drawer-files">Attach a photo or PDF (optional)</Label>
              <Input
                id="drawer-files"
                type="file"
                multiple
                accept="image/*,application/pdf"
                className="min-h-[48px] py-2"
                onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
              />
              {files.length > 0 && (
                <p className="text-xs text-secondary-500">
                  {files.length === 1 ? "1 file" : `${files.length} files`} will be attached when
                  the drawer closes.
                </p>
              )}
            </div>
            {confirming && (
              <p className="text-sm text-secondary-600">
                Closing cannot be undone. Close with {formatMoney(majorToMinor(value ?? 0))} counted?
              </p>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={onClose} disabled={busy} className="min-h-[48px]">
                Cancel
              </Button>
              {confirming ? (
                <Button
                  onClick={() => void handleClose()}
                  disabled={busy || value === null}
                  className="min-h-[48px]"
                >
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Yes, close drawer"}
                </Button>
              ) : (
                <Button
                  onClick={() => setConfirming(true)}
                  disabled={value === null}
                  className="min-h-[48px]"
                >
                  Close drawer
                </Button>
              )}
            </DialogFooter>
          </>
        )}

        {view.kind === "result" && (
          <>
            <DialogHeader>
              <DialogTitle>Drawer closed</DialogTitle>
              <DialogDescription>
                The figures below also appear on today's Z-Report.
              </DialogDescription>
            </DialogHeader>
            <div className="text-sm">
              <Line
                label="Should have been in the drawer"
                value={formatMoney(view.session.closing_balance_expected ?? 0)}
              />
              <Line label="Counted" value={formatMoney(view.session.closing_balance_counted ?? 0)} />
            </div>
            <Difference
              diff={
                (view.session.closing_balance_counted ?? 0) -
                (view.session.closing_balance_expected ?? 0)
              }
            />
            {view.session.note && (
              <p className="whitespace-pre-wrap break-words text-sm text-secondary-700">
                <span className="font-medium">Note: </span>
                {view.session.note}
              </p>
            )}
            {view.attached > 0 && (
              <p className="text-sm text-secondary-600">
                {view.attached === 1 ? "1 file" : `${view.attached} files`} attached.
              </p>
            )}
            <DialogFooter>
              <Button onClick={onClose} className="min-h-[48px]">
                Done
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
