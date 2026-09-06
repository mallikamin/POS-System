/**
 * Operating expenses (Martin M10).
 *
 * > "There is no expenses menu to attach the invoices of my expenses (not the
 * >  ones from suppliers which are already in the receiving of ingredients, but
 * >  other expenses such as rent, salaries etc...)"
 *
 * The boundary is his and it is the right one: an ingredient purchase already
 * lives in the purchase order, the goods receipt and the stock movement.
 * Nothing on this screen touches stock.
 *
 * 🔴 Money is entered in MAJOR units (8.50) and sent in MINOR units (850). The
 * conversion happens once, through `majorToMinor`, at the moment of sending.
 * The form holds the typed string so "2." survives while it is being typed.
 *
 * Built mobile-first (M12): filters wrap, the list is cards below `sm`, and
 * every control is at least 44px tall.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  FileText,
  Loader2,
  Paperclip,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  Upload,
  X,
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
import {
  formatMoney,
  getActiveCurrency,
  majorToMinor,
  minorToMajor,
} from "@/utils/currency";
import { fetchLocations } from "@/services/locationsApi";
import {
  createExpense,
  createExpenseCategory,
  deleteExpense,
  deleteExpenseAttachment,
  fetchExpenseCategories,
  fetchExpenseSummary,
  fetchExpenses,
  openExpenseAttachment,
  updateExpense,
  uploadExpenseAttachment,
} from "@/services/expensesApi";
import { cn } from "@/lib/utils";
import type {
  Expense,
  ExpenseCategory,
  ExpenseStatus,
  ExpenseSummary,
} from "@/types/expense";
import type { Location } from "@/types/location";

const STATUS_STYLES: Record<ExpenseStatus, string> = {
  draft: "bg-secondary-100 text-secondary-600",
  unpaid: "bg-warning-100 text-warning-800",
  paid: "bg-success-100 text-success-800",
};

/** First and last day of the current month, as `YYYY-MM-DD`. */
function currentMonth(): { from: string; to: string } {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth(), 1);
  const last = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  const iso = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
      d.getDate(),
    ).padStart(2, "0")}`;
  return { from: iso(first), to: iso(last) };
}

function toNumber(value: string | number | null | undefined): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function errorMessage(err: unknown, fallback: string): string {
  if (typeof err !== "object" || err === null || !("response" in err)) {
    return fallback;
  }
  const response = err.response;
  if (typeof response !== "object" || response === null || !("data" in response)) {
    return fallback;
  }
  const data = response.data;
  if (typeof data !== "object" || data === null || !("detail" in data)) {
    return fallback;
  }
  const detail = data.detail;
  return typeof detail === "string" && detail.length > 0 ? detail : fallback;
}

function ExpensesPage() {
  const { toast } = useToast();
  const currency = getActiveCurrency();
  const month = useMemo(currentMonth, []);

  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [categories, setCategories] = useState<ExpenseCategory[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [summary, setSummary] = useState<ExpenseSummary | null>(null);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);

  const [dateFrom, setDateFrom] = useState(month.from);
  const [dateTo, setDateTo] = useState(month.to);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");

  // Form. `editing` null means "create".
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Expense | null>(null);
  const [expenseDate, setExpenseDate] = useState(month.from);
  const [payee, setPayee] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [amount, setAmount] = useState("");
  const [tax, setTax] = useState("");
  const [reference, setReference] = useState("");
  const [description, setDescription] = useState("");
  const [statusValue, setStatusValue] = useState<ExpenseStatus>("unpaid");
  const [paymentMethod, setPaymentMethod] = useState("");
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);

  const [categoryDialogOpen, setCategoryDialogOpen] = useState(false);
  const [newCategory, setNewCategory] = useState("");

  const [deleteTarget, setDeleteTarget] = useState<Expense | null>(null);

  const load = useCallback(async () => {
    const params = {
      ...(dateFrom ? { date_from: dateFrom } : {}),
      ...(dateTo ? { date_to: dateTo } : {}),
      ...(categoryFilter ? { category_id: categoryFilter } : {}),
      ...(statusFilter ? { status: statusFilter } : {}),
      ...(search.trim() ? { search: search.trim() } : {}),
    };
    const [rows, totals] = await Promise.all([
      fetchExpenses(params),
      fetchExpenseSummary({
        ...(dateFrom ? { date_from: dateFrom } : {}),
        ...(dateTo ? { date_to: dateTo } : {}),
      }),
    ]);
    setExpenses(rows);
    setSummary(totals);
  }, [dateFrom, dateTo, categoryFilter, statusFilter, search]);

  useEffect(() => {
    void (async () => {
      try {
        const [cats, sites] = await Promise.all([
          fetchExpenseCategories(),
          fetchLocations().catch(() => [] as Location[]),
        ]);
        setCategories(cats);
        setLocations(sites);
        await load();
      } catch (err) {
        toast({
          title: "Could not load expenses",
          description: errorMessage(err, "The expenses screen is unavailable."),
          variant: "destructive",
        });
      } finally {
        setLoading(false);
      }
    })();
    // `load` is intentionally not a dependency here: this effect is the first
    // load only. Filter changes are handled by the effect below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [toast]);

  useEffect(() => {
    if (loading) return;
    const timer = setTimeout(() => {
      void load().catch((err) =>
        toast({
          title: "Could not filter",
          description: errorMessage(err, "The list could not be reloaded."),
          variant: "destructive",
        }),
      );
    }, 250);
    return () => clearTimeout(timer);
  }, [load, loading, toast]);

  function openCreate() {
    setEditing(null);
    setExpenseDate(new Date().toISOString().slice(0, 10));
    setPayee("");
    setCategoryId(categories[0]?.id ?? "");
    setLocationId("");
    setAmount("");
    setTax("");
    setReference("");
    setDescription("");
    setStatusValue("unpaid");
    setPaymentMethod("");
    setPendingFiles([]);
    setFormOpen(true);
  }

  function openEdit(expense: Expense) {
    setEditing(expense);
    setExpenseDate(expense.expense_date);
    setPayee(expense.payee);
    setCategoryId(expense.category_id ?? "");
    setLocationId(expense.location_id ?? "");
    setAmount(String(minorToMajor(expense.amount_minor, currency)));
    setTax(String(minorToMajor(expense.tax_minor, currency)));
    setReference(expense.reference_number ?? "");
    setDescription(expense.description ?? "");
    setStatusValue(expense.status);
    setPaymentMethod(expense.payment_method ?? "");
    setPendingFiles([]);
    setFormOpen(true);
  }

  const amountMinor = majorToMinor(toNumber(amount), currency);
  const taxMinor = majorToMinor(toNumber(tax), currency);
  const formValid =
    payee.trim().length > 0 &&
    expenseDate.length > 0 &&
    amountMinor >= 0 &&
    taxMinor >= 0 &&
    taxMinor <= amountMinor;

  async function handleSave() {
    if (!formValid || saving) return;
    setSaving(true);
    try {
      const body = {
        expense_date: expenseDate,
        payee: payee.trim(),
        amount_minor: amountMinor,
        tax_minor: taxMinor,
        category_id: categoryId || null,
        location_id: locationId || null,
        reference_number: reference.trim() || null,
        description: description.trim() || null,
        status: statusValue,
        payment_method: paymentMethod.trim() || null,
      };
      const saved = editing
        ? await updateExpense(editing.id, body)
        : await createExpense(body);

      // Attachments are uploaded after the expense exists, because the upload
      // route needs its id. Each failure is reported on its own: one bad file
      // must not discard the expense that was saved successfully.
      for (const file of pendingFiles) {
        try {
          await uploadExpenseAttachment(saved.id, file);
        } catch (err) {
          toast({
            title: `Could not attach ${file.name}`,
            description: errorMessage(err, "The expense itself was saved."),
            variant: "destructive",
          });
        }
      }

      toast({
        title: editing ? "Expense updated" : "Expense recorded",
        description: `${saved.payee} · ${formatMoney(saved.amount_minor, currency)}`,
        variant: "success",
      });
      setFormOpen(false);
      await load();
    } catch (err) {
      toast({
        title: "Not saved",
        description: errorMessage(err, "The expense was not recorded."),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleAddCategory() {
    const name = newCategory.trim();
    if (!name) return;
    try {
      const created = await createExpenseCategory(name);
      const refreshed = await fetchExpenseCategories();
      setCategories(refreshed);
      setCategoryId(created.id);
      setNewCategory("");
      setCategoryDialogOpen(false);
      toast({ title: `Category "${created.name}" added`, variant: "success" });
    } catch (err) {
      toast({
        title: "Category not added",
        description: errorMessage(err, "That category could not be created."),
        variant: "destructive",
      });
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await deleteExpense(deleteTarget.id);
      toast({ title: "Expense deleted", variant: "success" });
      setDeleteTarget(null);
      await load();
    } catch (err) {
      toast({
        title: "Not deleted",
        description: errorMessage(err, "The expense is still there."),
        variant: "destructive",
      });
    }
  }

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await load();
    } finally {
      setRefreshing(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-secondary-900 sm:text-2xl">
            Expenses
          </h1>
          <p className="mt-1 text-sm text-secondary-500">
            Rent, salaries, utilities and anything else that is not an
            ingredient purchase. Attach the invoice to each one.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => void handleRefresh()}
            disabled={refreshing}
            className="min-h-[44px] gap-2"
          >
            <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
          <Button onClick={openCreate} className="min-h-[44px] gap-2">
            <Plus className="h-4 w-4" />
            Add expense
          </Button>
        </div>
      </div>

      {/* ---- Totals ------------------------------------------------- */}
      {summary && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Card>
            <CardContent className="p-4">
              <p className="text-xs uppercase tracking-wide text-secondary-500">
                Total
              </p>
              <p className="mt-1 text-lg font-semibold text-secondary-900 sm:text-xl">
                {formatMoney(summary.total_minor, currency)}
              </p>
              <p className="mt-1 text-xs text-secondary-500">
                {summary.expense_count} expense
                {summary.expense_count === 1 ? "" : "s"}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-xs uppercase tracking-wide text-secondary-500">
                Net of VAT
              </p>
              <p className="mt-1 text-lg font-semibold text-secondary-900 sm:text-xl">
                {formatMoney(summary.net_minor, currency)}
              </p>
              <p className="mt-1 text-xs text-secondary-500">
                {formatMoney(summary.tax_total_minor, currency)} VAT
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-xs uppercase tracking-wide text-secondary-500">
                Still to pay
              </p>
              <p className="mt-1 text-lg font-semibold text-warning-700 sm:text-xl">
                {formatMoney(summary.unpaid_minor, currency)}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-xs uppercase tracking-wide text-secondary-500">
                Biggest category
              </p>
              <p className="mt-1 truncate text-lg font-semibold text-secondary-900 sm:text-xl">
                {summary.by_category[0]?.category_name ?? "—"}
              </p>
              <p className="mt-1 text-xs text-secondary-500">
                {summary.by_category[0]
                  ? formatMoney(summary.by_category[0].total_minor, currency)
                  : "Nothing yet"}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ---- Filters ------------------------------------------------- */}
      <Card>
        <CardContent className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-5">
          <div className="space-y-1">
            <Label htmlFor="exp-from" className="text-xs">
              From
            </Label>
            <Input
              id="exp-from"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="min-h-[44px]"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="exp-to" className="text-xs">
              To
            </Label>
            <Input
              id="exp-to"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="min-h-[44px]"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="exp-cat" className="text-xs">
              Category
            </Label>
            <Select
              id="exp-cat"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="min-h-[44px]"
            >
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="exp-status" className="text-xs">
              Status
            </Label>
            <Select
              id="exp-status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="min-h-[44px]"
            >
              <option value="">Any status</option>
              <option value="unpaid">Unpaid</option>
              <option value="paid">Paid</option>
              <option value="draft">Draft</option>
            </Select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="exp-search" className="text-xs">
              Search
            </Label>
            <Input
              id="exp-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Payee, invoice no."
              className="min-h-[44px]"
            />
          </div>
        </CardContent>
      </Card>

      {/* ---- The list ------------------------------------------------ */}
      {expenses.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <FileText className="mx-auto h-10 w-10 text-secondary-300" />
            <p className="mt-3 font-medium text-secondary-800">
              No expenses in this period
            </p>
            <p className="mt-1 text-sm text-secondary-500">
              Add the rent, the salaries, the electricity bill. Ingredient
              purchases stay on the purchase orders where they already are.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Phone: one card per expense. */}
          <div className="space-y-3 sm:hidden">
            {expenses.map((expense) => (
              <Card key={expense.id}>
                <CardContent className="space-y-2 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-secondary-900">
                        {expense.payee}
                      </p>
                      <p className="text-xs text-secondary-500">
                        {expense.expense_date} ·{" "}
                        {expense.category_name ?? "Uncategorised"}
                      </p>
                    </div>
                    <span className="shrink-0 tabular-nums font-semibold text-secondary-900">
                      {formatMoney(expense.amount_minor, currency)}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge className={STATUS_STYLES[expense.status]}>
                      {expense.status}
                    </Badge>
                    {expense.attachments.map((a) => (
                      <button
                        key={a.id}
                        type="button"
                        onClick={() => void openExpenseAttachment(a)}
                        className="inline-flex min-h-[32px] items-center gap-1 rounded-full bg-secondary-100 px-2 text-xs text-secondary-700"
                      >
                        <Paperclip className="h-3 w-3" />
                        {a.filename ?? "Invoice"}
                      </button>
                    ))}
                  </div>
                  <div className="flex gap-2 pt-1">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openEdit(expense)}
                      className="min-h-[40px] flex-1 gap-1"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                      Edit
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDeleteTarget(expense)}
                      className="min-h-[40px] text-danger-600"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Tablet and up: a table with a real minimum width, so its
              horizontal scroller works instead of crushing the columns. */}
          <Card className="hidden sm:block">
            <CardContent className="overflow-x-auto p-0">
              <table className="w-full min-w-[52rem] text-sm">
                <thead className="border-b border-secondary-200 bg-secondary-50 text-left text-xs uppercase tracking-wide text-secondary-500">
                  <tr>
                    <th className="px-4 py-3 font-medium">Date</th>
                    <th className="px-4 py-3 font-medium">Payee</th>
                    <th className="px-4 py-3 font-medium">Category</th>
                    <th className="px-4 py-3 font-medium">Invoice</th>
                    <th className="px-4 py-3 text-right font-medium">Net</th>
                    <th className="px-4 py-3 text-right font-medium">VAT</th>
                    <th className="px-4 py-3 text-right font-medium">Total</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Files</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-secondary-100">
                  {expenses.map((expense) => (
                    <tr key={expense.id} className="hover:bg-secondary-50">
                      <td className="whitespace-nowrap px-4 py-3 text-secondary-600">
                        {expense.expense_date}
                      </td>
                      <td className="px-4 py-3 font-medium text-secondary-900">
                        {expense.payee}
                        {expense.description && (
                          <span className="block text-xs font-normal text-secondary-500">
                            {expense.description}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-secondary-600">
                        {expense.category_name ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-secondary-500">
                        {expense.reference_number ?? "—"}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-secondary-600">
                        {formatMoney(expense.net_minor, currency)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-secondary-600">
                        {formatMoney(expense.tax_minor, currency)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums font-semibold text-secondary-900">
                        {formatMoney(expense.amount_minor, currency)}
                      </td>
                      <td className="px-4 py-3">
                        <Badge className={STATUS_STYLES[expense.status]}>
                          {expense.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        {expense.attachments.length === 0 ? (
                          <span className="text-secondary-400">—</span>
                        ) : (
                          <div className="flex flex-wrap gap-1">
                            {expense.attachments.map((a) => (
                              <button
                                key={a.id}
                                type="button"
                                onClick={() => void openExpenseAttachment(a)}
                                title={a.filename ?? "Invoice"}
                                className="inline-flex items-center gap-1 rounded bg-secondary-100 px-2 py-1 text-xs text-secondary-700 hover:bg-secondary-200"
                              >
                                <Paperclip className="h-3 w-3" />
                                View
                              </button>
                            ))}
                          </div>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEdit(expense)}
                          aria-label={`Edit ${expense.payee}`}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setDeleteTarget(expense)}
                          className="text-danger-600"
                          aria-label={`Delete ${expense.payee}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      )}

      {/* ---- Create / edit ------------------------------------------- */}
      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {editing ? "Edit expense" : "Add an expense"}
            </DialogTitle>
            <DialogDescription>
              The amount is the whole invoice. The VAT box is the part of it that
              is VAT, not an extra on top.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="f-date">Date *</Label>
                <Input
                  id="f-date"
                  type="date"
                  value={expenseDate}
                  onChange={(e) => setExpenseDate(e.target.value)}
                  className="min-h-[48px]"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="f-status">Status</Label>
                <Select
                  id="f-status"
                  value={statusValue}
                  onChange={(e) =>
                    setStatusValue(e.target.value as ExpenseStatus)
                  }
                  className="min-h-[48px]"
                >
                  <option value="unpaid">Unpaid</option>
                  <option value="paid">Paid</option>
                  <option value="draft">Draft (not counted in totals)</option>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="f-payee">Who was paid *</Label>
              <Input
                id="f-payee"
                value={payee}
                onChange={(e) => setPayee(e.target.value)}
                placeholder="Landlord, DEWA, staff payroll..."
                className="min-h-[48px]"
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="f-category">Category</Label>
                <button
                  type="button"
                  onClick={() => setCategoryDialogOpen(true)}
                  className="text-xs font-medium text-primary-600 hover:text-primary-700"
                >
                  + Add category
                </button>
              </div>
              <Select
                id="f-category"
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                className="min-h-[48px]"
              >
                <option value="">Uncategorised</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="f-amount">Invoice total ({currency}) *</Label>
                <Input
                  id="f-amount"
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="0.01"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="min-h-[48px]"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="f-tax">VAT inside it ({currency})</Label>
                <Input
                  id="f-tax"
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="0.01"
                  value={tax}
                  onChange={(e) => setTax(e.target.value)}
                  className="min-h-[48px]"
                />
              </div>
            </div>
            {amountMinor > 0 && (
              <p
                className={cn(
                  "text-xs",
                  taxMinor > amountMinor
                    ? "text-danger-600"
                    : "text-secondary-500",
                )}
              >
                {taxMinor > amountMinor
                  ? "The VAT cannot be more than the invoice total."
                  : `Net of VAT: ${formatMoney(amountMinor - taxMinor, currency)}`}
              </p>
            )}

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="f-ref">Their invoice number</Label>
                <Input
                  id="f-ref"
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                  className="min-h-[48px]"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="f-method">Paid by</Label>
                <Input
                  id="f-method"
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                  placeholder="Bank transfer, cash, cheque"
                  className="min-h-[48px]"
                />
              </div>
            </div>

            {locations.length > 1 && (
              <div className="space-y-2">
                <Label htmlFor="f-site">Site</Label>
                <Select
                  id="f-site"
                  value={locationId}
                  onChange={(e) => setLocationId(e.target.value)}
                  className="min-h-[48px]"
                >
                  <option value="">
                    The whole business (rent, licences)
                  </option>
                  {locations.map((site) => (
                    <option key={site.id} value={site.id}>
                      {site.name}
                    </option>
                  ))}
                </Select>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="f-desc">Notes</Label>
              <Textarea
                id="f-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
              />
            </div>

            {/* ---- Attachments ---- */}
            <div className="space-y-2">
              <Label htmlFor="f-files">Invoice (PDF or photo)</Label>
              <input
                id="f-files"
                type="file"
                multiple
                accept="application/pdf,image/*"
                onChange={(e) =>
                  setPendingFiles(Array.from(e.target.files ?? []))
                }
                className="block w-full text-sm text-secondary-600 file:mr-3 file:min-h-[44px] file:rounded-lg file:border-0 file:bg-primary-50 file:px-4 file:text-sm file:font-medium file:text-primary-700"
              />
              {pendingFiles.length > 0 && (
                <ul className="space-y-1 text-xs text-secondary-600">
                  {pendingFiles.map((f) => (
                    <li key={f.name} className="flex items-center gap-1">
                      <Upload className="h-3 w-3" />
                      {f.name}
                    </li>
                  ))}
                </ul>
              )}

              {editing && editing.attachments.length > 0 && (
                <ul className="space-y-1 pt-2">
                  {editing.attachments.map((a) => (
                    <li
                      key={a.id}
                      className="flex items-center justify-between gap-2 rounded bg-secondary-50 px-2 py-1.5 text-xs"
                    >
                      <button
                        type="button"
                        onClick={() => void openExpenseAttachment(a)}
                        className="flex min-w-0 items-center gap-1 text-primary-700"
                      >
                        <Paperclip className="h-3 w-3 shrink-0" />
                        <span className="truncate">
                          {a.filename ?? "Invoice"}
                        </span>
                      </button>
                      <button
                        type="button"
                        aria-label="Remove attachment"
                        onClick={() => {
                          void (async () => {
                            try {
                              await deleteExpenseAttachment(editing.id, a.id);
                              const refreshed = await fetchExpenses({
                                search: editing.payee,
                              });
                              const updated = refreshed.find(
                                (e) => e.id === editing.id,
                              );
                              if (updated) setEditing(updated);
                              await load();
                            } catch (err) {
                              toast({
                                title: "Not removed",
                                description: errorMessage(
                                  err,
                                  "The file is still attached.",
                                ),
                                variant: "destructive",
                              });
                            }
                          })();
                        }}
                        className="shrink-0 text-danger-600"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setFormOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => void handleSave()}
              disabled={!formValid || saving}
              className="min-h-[44px]"
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : editing ? (
                "Save changes"
              ) : (
                "Record expense"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---- Add a category ------------------------------------------ */}
      <Dialog open={categoryDialogOpen} onOpenChange={setCategoryDialogOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Add an expense category</DialogTitle>
            <DialogDescription>
              It appears in the dropdown straight away.
            </DialogDescription>
          </DialogHeader>
          <Input
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value)}
            placeholder="e.g. Staff accommodation"
            className="min-h-[48px]"
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCategoryDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={() => void handleAddCategory()}
              disabled={newCategory.trim().length === 0}
            >
              Add
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---- Delete confirm ------------------------------------------ */}
      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete this expense?</DialogTitle>
            <DialogDescription>
              {deleteTarget?.payee} ·{" "}
              {deleteTarget
                ? formatMoney(deleteTarget.amount_minor, currency)
                : ""}
              . The attached invoice is deleted with it. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => void handleDelete()}
              className="bg-danger-600 hover:bg-danger-700"
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default ExpensesPage;
