import { useEffect, useState } from "react";
import { isAxiosError } from "axios";
import { Loader2, PiggyBank } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { fetchOpeningBalance, saveOpeningBalance } from "@/services/otherIncomeApi";
import type { OpeningBalance } from "@/types/otherIncome";
import { formatMoney, getActiveCurrency, paisaToRupees, rupeesToPaisa } from "@/utils/currency";
import { formatDate, toLocalISODate } from "@/utils/localDate";

/**
 * Opening cash in hand (Danny's D-62): the cash the business held on the day
 * it started using the system. The Z-Report rolls it forward day by day into
 * "cash in hand at the start and end of the day". Cash only: nothing here
 * knows when card takings reach the bank, so a bank figure would drift.
 */
export function OpeningBalanceCard() {
  const { toast } = useToast();
  const currency = getActiveCurrency();
  const [balance, setBalance] = useState<OpeningBalance | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [open, setOpen] = useState(false);
  const [asOf, setAsOf] = useState(toLocalISODate());
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchOpeningBalance()
      .then(setBalance)
      .catch(() => setBalance(null))
      .finally(() => setLoaded(true));
  }, []);

  function openEditor() {
    setAsOf(balance?.as_of ?? toLocalISODate());
    setAmount(balance ? String(paisaToRupees(balance.cash_minor)) : "");
    setNotes(balance?.notes ?? "");
    setOpen(true);
  }

  const amountValue = Number(amount);
  const valid = asOf !== "" && amount.trim() !== "" && Number.isFinite(amountValue) && amountValue >= 0;

  async function handleSave() {
    if (!valid) return;
    setSaving(true);
    try {
      const saved = await saveOpeningBalance({
        as_of: asOf,
        cash_minor: rupeesToPaisa(amountValue),
        notes: notes.trim() || null,
      });
      setBalance(saved);
      setOpen(false);
      toast({
        title: "Opening cash saved",
        description: `${formatMoney(saved.cash_minor, currency)} at the start of ${formatDate(saved.as_of)}.`,
        variant: "success",
      });
    } catch (err) {
      const detail = isAxiosError(err) ? err.response?.data?.detail : undefined;
      toast({
        title: "Opening cash not saved",
        description: typeof detail === "string" ? detail : "Please try again.",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  if (!loaded) return null;

  return (
    <>
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
          <div className="flex items-center gap-3">
            <PiggyBank className="h-6 w-6 text-primary-600" aria-hidden="true" />
            {balance ? (
              <div>
                <p className="font-semibold text-secondary-900">
                  Opening cash in hand: {formatMoney(balance.cash_minor, currency)}
                </p>
                <p className="text-xs text-secondary-500">
                  At the start of {formatDate(balance.as_of)}
                  {balance.recorded_by_name ? `, set by ${balance.recorded_by_name}` : ""}. The
                  Z-Report carries it forward as cash in hand.
                </p>
              </div>
            ) : (
              <div>
                <p className="font-semibold text-secondary-900">Opening cash in hand not set</p>
                <p className="text-xs text-secondary-500">
                  Enter the cash held on your first day, and the Z-Report shows cash in hand for
                  every day after it.
                </p>
              </div>
            )}
          </div>
          <Button variant="outline" onClick={openEditor} className="min-h-[44px]">
            {balance ? "Edit" : "Set opening cash"}
          </Button>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={(next) => !next && setOpen(false)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Opening cash in hand</DialogTitle>
            <DialogDescription>
              All the cash the business held at the start of the day you began using the system:
              the till, the safe and any petty cash. Bank balances are not included.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="ob-date">At the start of</Label>
              <Input id="ob-date" type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="ob-amount">Cash (Rs)</Label>
              <Input
                id="ob-amount"
                type="number"
                inputMode="decimal"
                min={0}
                step="any"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="ob-notes">Note (optional)</Label>
              <Input id="ob-notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void handleSave()} disabled={saving || !valid}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
