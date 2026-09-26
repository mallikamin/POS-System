import { useEffect, useMemo, useState } from "react";
import { isAxiosError } from "axios";
import { Loader2, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { OpeningBalanceCard } from "@/components/admin/OpeningBalanceCard";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import {
  createIncomeCategory,
  createOtherIncome,
  deleteOtherIncome,
  fetchIncomeCategories,
  fetchOtherIncome,
  updateOtherIncome,
} from "@/services/otherIncomeApi";
import type { IncomeCategory, IncomeMethod, OtherIncome } from "@/types/otherIncome";
import { formatMoney, getActiveCurrency, paisaToRupees, rupeesToPaisa } from "@/utils/currency";
import { formatDate, toLocalISODate } from "@/utils/localDate";

/**
 * Other income (Danny's D-63): money in that is not a sale, such as a scrap
 * sale, rent received or an event deposit. Cash receipts are added to the
 * Z-Report day summary's cash position; bank receipts are recorded here and
 * never counted as cash in the till.
 */

function currentMonth(): { from: string; to: string } {
  const now = new Date();
  return {
    from: toLocalISODate(new Date(now.getFullYear(), now.getMonth(), 1)),
    to: toLocalISODate(new Date(now.getFullYear(), now.getMonth() + 1, 0)),
  };
}

function apiDetail(err: unknown, fallback: string): string {
  const detail = isAxiosError(err) ? err.response?.data?.detail : undefined;
  return typeof detail === "string" ? detail : fallback;
}

interface FormState {
  received_on: string;
  payer: string;
  amount: string;
  method: IncomeMethod;
  category_id: string;
  reference_number: string;
  description: string;
}

function emptyForm(): FormState {
  return {
    received_on: toLocalISODate(),
    payer: "",
    amount: "",
    method: "cash",
    category_id: "",
    reference_number: "",
    description: "",
  };
}

function OtherIncomePage() {
  const { toast } = useToast();
  const currency = getActiveCurrency();
  const month = useMemo(currentMonth, []);

  const [rows, setRows] = useState<OtherIncome[]>([]);
  const [categories, setCategories] = useState<IncomeCategory[]>([]);
  const [dateFrom, setDateFrom] = useState(month.from);
  const [dateTo, setDateTo] = useState(month.to);
  const [methodFilter, setMethodFilter] = useState<"" | IncomeMethod>("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);

  const [editing, setEditing] = useState<OtherIncome | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [newCategory, setNewCategory] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<OtherIncome | null>(null);

  async function load() {
    setRefreshing(true);
    try {
      const [list, cats] = await Promise.all([
        fetchOtherIncome({
          ...(dateFrom ? { date_from: dateFrom } : {}),
          ...(dateTo ? { date_to: dateTo } : {}),
          ...(methodFilter ? { method: methodFilter } : {}),
        }),
        fetchIncomeCategories(),
      ]);
      setRows(list);
      setCategories(cats);
    } catch (err) {
      toast({
        title: "Failed to load other income",
        description: apiDetail(err, "Please try again."),
        variant: "destructive",
      });
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [dateFrom, dateTo, methodFilter]);

  const cashTotal = rows.filter((r) => r.method === "cash").reduce((s, r) => s + r.amount_minor, 0);
  const bankTotal = rows.filter((r) => r.method === "bank").reduce((s, r) => s + r.amount_minor, 0);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm());
    setNewCategory("");
    setFormOpen(true);
  }

  function openEdit(row: OtherIncome) {
    setEditing(row);
    setForm({
      received_on: row.received_on,
      payer: row.payer,
      amount: String(paisaToRupees(row.amount_minor)),
      method: row.method,
      category_id: row.category_id ?? "",
      reference_number: row.reference_number ?? "",
      description: row.description ?? "",
    });
    setNewCategory("");
    setFormOpen(true);
  }

  const amountValue = Number(form.amount);
  const formValid =
    form.received_on !== "" &&
    form.payer.trim().length > 0 &&
    form.amount.trim() !== "" &&
    Number.isFinite(amountValue) &&
    rupeesToPaisa(amountValue) > 0;

  async function handleAddCategory() {
    const name = newCategory.trim();
    if (!name) return;
    try {
      const created = await createIncomeCategory(name);
      setCategories(await fetchIncomeCategories());
      setForm((f) => ({ ...f, category_id: created.id }));
      setNewCategory("");
    } catch (err) {
      toast({
        title: "Category not added",
        description: apiDetail(err, "Please try again."),
        variant: "destructive",
      });
    }
  }

  async function handleSave() {
    if (!formValid) return;
    setSaving(true);
    const body = {
      received_on: form.received_on,
      payer: form.payer.trim(),
      amount_minor: rupeesToPaisa(amountValue),
      method: form.method,
      category_id: form.category_id || null,
      reference_number: form.reference_number.trim() || null,
      description: form.description.trim() || null,
    };
    try {
      if (editing) {
        await updateOtherIncome(editing.id, body);
      } else {
        await createOtherIncome(body);
      }
      toast({
        title: editing ? "Income updated" : "Income recorded",
        description: `${body.payer}: ${formatMoney(body.amount_minor, currency)} (${body.method}).`,
        variant: "success",
      });
      setFormOpen(false);
      await load();
    } catch (err) {
      toast({
        title: "Income not saved",
        description: apiDetail(err, "Nothing was changed. Please try again."),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await deleteOtherIncome(deleteTarget.id);
      setDeleteTarget(null);
      await load();
    } catch (err) {
      toast({
        title: "Not deleted",
        description: apiDetail(err, "Please try again."),
        variant: "destructive",
      });
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-secondary-900 sm:text-2xl">Other Income</h1>
          <p className="mt-1 text-sm text-secondary-500">
            Money in that is not a sale: scrap sold, rent received, event deposits. Cash
            received is added to the Z-Report cash position for that day.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => void load()}
            disabled={refreshing}
            className="min-h-[44px] gap-2"
          >
            <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
          <Button onClick={openCreate} className="min-h-[44px] gap-2">
            <Plus className="h-4 w-4" />
            Add income
          </Button>
        </div>
      </div>

      <OpeningBalanceCard />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Card>
          <CardContent className="p-4">
            <p className="text-xs uppercase tracking-wide text-secondary-500">Total</p>
            <p className="mt-1 text-lg font-semibold text-secondary-900 sm:text-xl">
              {formatMoney(cashTotal + bankTotal, currency)}
            </p>
            <p className="mt-1 text-xs text-secondary-500">
              {rows.length} receipt{rows.length === 1 ? "" : "s"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs uppercase tracking-wide text-secondary-500">Cash</p>
            <p className="mt-1 text-lg font-semibold text-secondary-900 sm:text-xl">
              {formatMoney(cashTotal, currency)}
            </p>
            <p className="mt-1 text-xs text-secondary-500">Counted in the cash position</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs uppercase tracking-wide text-secondary-500">Bank</p>
            <p className="mt-1 text-lg font-semibold text-secondary-900 sm:text-xl">
              {formatMoney(bankTotal, currency)}
            </p>
            <p className="mt-1 text-xs text-secondary-500">Not cash in the till</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="grid gap-3 p-4 sm:grid-cols-3">
          <div className="space-y-1">
            <Label htmlFor="inc-from" className="text-xs">From</Label>
            <Input
              id="inc-from"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="min-h-[44px]"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="inc-to" className="text-xs">To</Label>
            <Input
              id="inc-to"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="min-h-[44px]"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="inc-method" className="text-xs">Received as</Label>
            <Select
              id="inc-method"
              value={methodFilter}
              onChange={(e) => setMethodFilter(e.target.value as "" | IncomeMethod)}
              className="min-h-[44px]"
            >
              <option value="">Cash and bank</option>
              <option value="cash">Cash</option>
              <option value="bank">Bank</option>
            </Select>
          </div>
        </CardContent>
      </Card>

      {rows.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-secondary-400">
            No other income recorded for these dates.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-secondary-200 text-left text-secondary-500">
                  <th className="px-4 py-3 font-medium">Date</th>
                  <th className="px-4 py-3 font-medium">From</th>
                  <th className="px-4 py-3 font-medium">Category</th>
                  <th className="px-4 py-3 font-medium">Received as</th>
                  <th className="px-4 py-3 text-right font-medium">Amount</th>
                  <th className="px-4 py-3 font-medium">Recorded by</th>
                  <th className="px-4 py-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-b border-secondary-100 last:border-0 align-top">
                    <td className="whitespace-nowrap px-4 py-3 text-secondary-700">
                      {formatDate(row.received_on)}
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-medium text-secondary-900">{row.payer}</p>
                      {(row.description || row.reference_number) && (
                        <p className="text-xs text-secondary-500">
                          {[row.reference_number, row.description].filter(Boolean).join(" · ")}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-secondary-700">{row.category_name ?? "None"}</td>
                    <td className="px-4 py-3">
                      <Badge variant={row.method === "cash" ? "success" : "secondary"}>
                        {row.method === "cash" ? "Cash" : "Bank"}
                      </Badge>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right font-semibold tabular-nums text-secondary-900">
                      {formatMoney(row.amount_minor, currency)}
                    </td>
                    <td className="px-4 py-3 text-secondary-600">{row.recorded_by_name ?? ""}</td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEdit(row)}
                          aria-label={`Edit ${row.payer}`}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setDeleteTarget(row)}
                          aria-label={`Delete ${row.payer}`}
                        >
                          <Trash2 className="h-4 w-4 text-danger-600" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* ---- Add / edit ----------------------------------------------- */}
      <Dialog open={formOpen} onOpenChange={(open) => !open && setFormOpen(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "Edit income" : "Add income"}</DialogTitle>
            <DialogDescription>
              Cash received counts in that day's cash position on the Z-Report.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="inc-date">Date received</Label>
              <Input
                id="inc-date"
                type="date"
                value={form.received_on}
                onChange={(e) => setForm((f) => ({ ...f, received_on: e.target.value }))}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="inc-amount">Amount (Rs)</Label>
              <Input
                id="inc-amount"
                type="number"
                inputMode="decimal"
                min={0}
                step="any"
                value={form.amount}
                onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
              />
            </div>
            <div className="space-y-1 sm:col-span-2">
              <Label htmlFor="inc-payer">Received from</Label>
              <Input
                id="inc-payer"
                value={form.payer}
                onChange={(e) => setForm((f) => ({ ...f, payer: e.target.value }))}
                placeholder="e.g. Scrap dealer, upstairs tenant, wedding party"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="inc-cat">Category</Label>
              <Select
                id="inc-cat"
                value={form.category_id}
                onChange={(e) => setForm((f) => ({ ...f, category_id: e.target.value }))}
              >
                <option value="">None</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
              <div className="flex gap-2 pt-1">
                <Input
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value)}
                  placeholder="New category"
                  aria-label="New category name"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void handleAddCategory()}
                  disabled={newCategory.trim().length === 0}
                >
                  Add
                </Button>
              </div>
            </div>
            <div className="space-y-1">
              <Label htmlFor="inc-method-form">Received as</Label>
              <Select
                id="inc-method-form"
                value={form.method}
                onChange={(e) => setForm((f) => ({ ...f, method: e.target.value as IncomeMethod }))}
              >
                <option value="cash">Cash</option>
                <option value="bank">Bank</option>
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="inc-ref">Reference (optional)</Label>
              <Input
                id="inc-ref"
                value={form.reference_number}
                onChange={(e) => setForm((f) => ({ ...f, reference_number: e.target.value }))}
                placeholder="Receipt or slip number"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="inc-desc">Note (optional)</Label>
              <Input
                id="inc-desc"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFormOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void handleSave()} disabled={saving || !formValid}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : editing ? "Save" : "Add income"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---- Delete confirm ------------------------------------------- */}
      <Dialog open={deleteTarget !== null} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete this income?</DialogTitle>
            <DialogDescription>
              {deleteTarget?.payer} ·{" "}
              {deleteTarget ? formatMoney(deleteTarget.amount_minor, currency) : ""}. This cannot
              be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button onClick={() => void handleDelete()} className="bg-danger-600 hover:bg-danger-700">
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default OtherIncomePage;
