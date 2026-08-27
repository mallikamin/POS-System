/**
 * Supplier master: who we buy from, what each of them sells, and what we have
 * bought from them.
 *
 * 🔴 Prices here are MINOR UNITS. The API sends `last_price_minor` as a string
 * already in minor units ("450.00" = 4.50 AED) and `formatMoney` divides by
 * 100 itself, so the input field asks for major units and converts ONCE on the
 * way in. There is no other multiplication by 100 on this screen.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Building2,
  History,
  Loader2,
  Package,
  Pencil,
  Plus,
  Star,
  Trash2,
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
  createSupplier,
  deactivateSupplier,
  fetchCatalogue,
  fetchSupplierHistory,
  fetchSuppliers,
  removeCatalogueItem,
  updateSupplier,
  upsertCatalogueItem,
} from "@/services/procurementApi";
import { fetchIngredients } from "@/services/inventoryApi";
import type {
  Supplier,
  SupplierItemRow,
  SupplierPurchaseRow,
} from "@/types/procurement";
import type { Ingredient } from "@/types/inventory";

/** Money arrives as a decimal string in minor units. */
function minor(value: string | null | undefined): number {
  const n = Number(value ?? 0);
  return Number.isFinite(n) ? n : 0;
}

function formatQty(value: string | null | undefined): string {
  const n = Number(value ?? 0);
  return Number.isFinite(n) ? String(n) : "-";
}

interface SupplierForm {
  name: string;
  code: string;
  contact_name: string;
  email: string;
  phone: string;
  address_line1: string;
  city: string;
  country: string;
  payment_terms: string;
  tax_registration_number: string;
  lead_time_days: string;
  notes: string;
}

const EMPTY_FORM: SupplierForm = {
  name: "",
  code: "",
  contact_name: "",
  email: "",
  phone: "",
  address_line1: "",
  city: "",
  country: "",
  payment_terms: "",
  tax_registration_number: "",
  lead_time_days: "0",
  notes: "",
};

/** F37: the supplier "Code" is an internal short handle the client never asked
 *  for, and it was a REQUIRED field, so the form looked complete and then
 *  refused to save. Derive it from the name instead. It stays visible and
 *  editable for anyone with their own coding scheme. */
function deriveCode(name: string): string {
  // Word boundaries matter: without them "CO" matches inside "COFFEE",
  // so "Coffee Co" would derive as "FFEE" instead of "COFFEE".
  const cleaned = name
    .toUpperCase()
    .replace(/\b(LLC|L\.L\.C|FZE|FZCO|TRADING|COMPANY|CO|LTD|LIMITED|INC)\b/g, " ")
    .replace(/[^A-Z0-9]/g, "");
  return cleaned.slice(0, 12) || name.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 12);
}

function SuppliersPage() {
  const { toast } = useToast();
  const config = useConfigStore((s) => s.config);
  const currency = config?.currency ?? "AED";

  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showInactive, setShowInactive] = useState(false);

  // Supplier create/edit
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Supplier | null>(null);
  // Once the user types their own code, stop overwriting it from the name.
  const [codeTouched, setCodeTouched] = useState(false);
  const [form, setForm] = useState<SupplierForm>(EMPTY_FORM);

  // Catalogue
  const [catalogueFor, setCatalogueFor] = useState<Supplier | null>(null);
  const [catalogue, setCatalogue] = useState<SupplierItemRow[]>([]);
  const [catalogueLoading, setCatalogueLoading] = useState(false);
  const [newItemIngredient, setNewItemIngredient] = useState("");
  const [newItemSku, setNewItemSku] = useState("");
  const [newItemPrice, setNewItemPrice] = useState("");
  const [newItemPack, setNewItemPack] = useState("");
  const [newItemPreferred, setNewItemPreferred] = useState(false);

  // History
  const [historyFor, setHistoryFor] = useState<Supplier | null>(null);
  const [history, setHistory] = useState<SupplierPurchaseRow[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [rows, ings] = await Promise.all([
        fetchSuppliers(showInactive),
        fetchIngredients(),
      ]);
      setSuppliers(rows);
      setIngredients(ings);
    } catch {
      toast({
        title: "Could not load suppliers",
        description: "Check the connection and try again.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [showInactive, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  // Only purchased ingredients can be bought; a produced one is made in-house
  // and the backend refuses it, so it must not be offered here either.
  const purchasable = useMemo(
    () => ingredients.filter((i) => !i.is_produced),
    [ingredients],
  );

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setCodeTouched(false);
    setShowForm(true);
  }

  function openEdit(supplier: Supplier) {
    setEditing(supplier);
    setCodeTouched(true);
    setForm({
      name: supplier.name,
      code: supplier.code,
      contact_name: supplier.contact_name ?? "",
      email: supplier.email ?? "",
      phone: supplier.phone ?? "",
      address_line1: supplier.address_line1 ?? "",
      city: supplier.city ?? "",
      country: supplier.country ?? "",
      payment_terms: supplier.payment_terms ?? "",
      tax_registration_number: supplier.tax_registration_number ?? "",
      lead_time_days: String(supplier.lead_time_days ?? 0),
      notes: supplier.notes ?? "",
    });
    setShowForm(true);
  }

  async function saveSupplier() {
    if (!form.name.trim()) {
      toast({
        title: "A supplier name is required",
        variant: "destructive",
      });
      return;
    }
    // F37: never block the save on the internal code. If the field is empty,
    // derive one from the name.
    const code = form.code.trim() || deriveCode(form.name);
    setSaving(true);
    try {
      const body = {
        name: form.name.trim(),
        contact_name: form.contact_name.trim() || null,
        email: form.email.trim() || null,
        phone: form.phone.trim() || null,
        address_line1: form.address_line1.trim() || null,
        city: form.city.trim() || null,
        country: form.country.trim() || null,
        payment_terms: form.payment_terms.trim() || null,
        tax_registration_number: form.tax_registration_number.trim() || null,
        lead_time_days: Number(form.lead_time_days) || 0,
        notes: form.notes.trim() || null,
      };
      if (editing) {
        await updateSupplier(editing.id, body);
      } else {
        await createSupplier({ ...body, code });
      }
      toast({ title: editing ? "Supplier updated" : "Supplier added" });
      setShowForm(false);
      await load();
    } catch (error) {
      const detail =
        (error as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Please try again.";
      toast({
        title: "Could not save the supplier",
        description: detail,
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  async function deactivate(supplier: Supplier) {
    setSaving(true);
    try {
      await deactivateSupplier(supplier.id);
      toast({
        title: `${supplier.name} deactivated`,
        description: "The purchase history is kept.",
      });
      await load();
    } catch {
      toast({ title: "Could not deactivate", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  }

  async function openCatalogue(supplier: Supplier) {
    setCatalogueFor(supplier);
    setCatalogueLoading(true);
    setNewItemIngredient("");
    setNewItemSku("");
    setNewItemPrice("");
    setNewItemPack("");
    setNewItemPreferred(false);
    try {
      setCatalogue(await fetchCatalogue({ supplierId: supplier.id }));
    } catch {
      toast({ title: "Could not load the catalogue", variant: "destructive" });
    } finally {
      setCatalogueLoading(false);
    }
  }

  async function addCatalogueItem() {
    if (!catalogueFor || !newItemIngredient) return;
    setSaving(true);
    try {
      // The box asks for major units; convert ONCE, here.
      const priceMajor = Number(newItemPrice);
      await upsertCatalogueItem(catalogueFor.id, {
        ingredient_id: newItemIngredient,
        supplier_sku: newItemSku.trim() || null,
        last_price_minor: Number.isFinite(priceMajor)
          ? Math.round(priceMajor * 100)
          : 0,
        pack_size: Number(newItemPack) || 0,
        is_preferred: newItemPreferred,
      });
      setCatalogue(await fetchCatalogue({ supplierId: catalogueFor.id }));
      setNewItemIngredient("");
      setNewItemSku("");
      setNewItemPrice("");
      setNewItemPack("");
      setNewItemPreferred(false);
      toast({ title: "Catalogue updated" });
    } catch (error) {
      const detail =
        (error as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Please try again.";
      toast({
        title: "Could not update the catalogue",
        description: detail,
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  async function removeItem(item: SupplierItemRow) {
    if (!catalogueFor) return;
    setSaving(true);
    try {
      await removeCatalogueItem(item.id);
      setCatalogue(await fetchCatalogue({ supplierId: catalogueFor.id }));
    } catch {
      toast({ title: "Could not remove the item", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  }

  async function openHistory(supplier: Supplier) {
    setHistoryFor(supplier);
    setHistoryLoading(true);
    try {
      setHistory(await fetchSupplierHistory(supplier.id));
    } catch {
      toast({ title: "Could not load the history", variant: "destructive" });
    } finally {
      setHistoryLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Suppliers</h1>
          <p className="text-sm text-secondary-500">
            Who you buy from, what they sell, and what you have bought.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-secondary-600">
            <input
              type="checkbox"
              className="h-4 w-4"
              checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)}
            />
            Show inactive
          </label>
          <Button onClick={openCreate}>
            <Plus className="mr-2 h-4 w-4" />
            New supplier
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-secondary-500">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          Loading suppliers
        </div>
      ) : suppliers.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
            <Building2 className="h-10 w-10 text-secondary-300" />
            <p className="text-secondary-600">No suppliers yet.</p>
            <p className="max-w-md text-sm text-secondary-500">
              Add the companies you buy ingredients from. Once a supplier has a
              catalogue, raising a purchase order fills in the prices for you.
            </p>
            <Button onClick={openCreate}>
              <Plus className="mr-2 h-4 w-4" />
              Add the first supplier
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <table className="w-full text-sm">
              <thead className="border-b border-secondary-200 bg-secondary-50 text-left text-xs uppercase tracking-wide text-secondary-500">
                <tr>
                  <th className="px-4 py-3">Supplier</th>
                  <th className="px-4 py-3">Contact</th>
                  <th className="px-4 py-3">Terms</th>
                  <th className="px-4 py-3 text-right">Lead time</th>
                  <th className="px-4 py-3 text-right">Orders</th>
                  <th className="px-4 py-3 text-right">Spend</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {suppliers.map((supplier) => (
                  <tr
                    key={supplier.id}
                    className="border-b border-secondary-100 last:border-0"
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-secondary-900">
                        {supplier.name}
                        {!supplier.is_active && (
                          <Badge variant="secondary" className="ml-2">
                            Inactive
                          </Badge>
                        )}
                      </div>
                      <div className="text-xs text-secondary-500">
                        {supplier.code}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div>{supplier.contact_name || "-"}</div>
                      <div className="text-xs text-secondary-500">
                        {supplier.email || "no email on file"}
                      </div>
                    </td>
                    <td className="px-4 py-3">{supplier.payment_terms || "-"}</td>
                    <td className="px-4 py-3 text-right">
                      {supplier.lead_time_days
                        ? `${supplier.lead_time_days} days`
                        : "-"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {supplier.order_count}
                    </td>
                    <td className="px-4 py-3 text-right font-medium">
                      {formatMoney(minor(supplier.total_spend_minor), currency)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => void openCatalogue(supplier)}
                          title="Items this supplier sells"
                        >
                          <Package className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => void openHistory(supplier)}
                          title="Purchase history"
                        >
                          <History className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => openEdit(supplier)}
                          title="Edit"
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        {supplier.is_active && (
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={saving}
                            onClick={() => void deactivate(supplier)}
                            title="Deactivate"
                          >
                            <Trash2 className="h-4 w-4 text-danger-600" />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* ---------------------------------------------------- supplier form */}
      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {editing ? `Edit ${editing.name}` : "New supplier"}
            </DialogTitle>
            <DialogDescription>
              The email address is where purchase orders are sent.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label>Name</Label>
              <Input
                value={form.name}
                onChange={(e) =>
                  setForm({
                    ...form,
                    name: e.target.value,
                    code:
                      editing || codeTouched
                        ? form.code
                        : deriveCode(e.target.value),
                  })
                }
                placeholder="Al Maya Trading LLC"
              />
            </div>
            <div>
              <Label>Code</Label>
              <Input
                value={form.code}
                disabled={!!editing}
                onChange={(e) => {
                  setCodeTouched(true);
                  setForm({ ...form, code: e.target.value });
                }}
                placeholder="ALMAYA"
              />
              {!editing && (
                <p className="mt-1 text-xs text-secondary-500">
                  Filled in from the name. Change it if you use your own codes.
                </p>
              )}
              {editing && (
                <p className="mt-1 text-xs text-secondary-500">
                  The code cannot change; it appears on orders already placed.
                </p>
              )}
            </div>
            <div>
              <Label>Contact name</Label>
              <Input
                value={form.contact_name}
                onChange={(e) =>
                  setForm({ ...form, contact_name: e.target.value })
                }
              />
            </div>
            <div>
              <Label>Email</Label>
              <Input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="orders@supplier.com"
              />
            </div>
            <div>
              <Label>Phone</Label>
              <Input
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </div>
            <div>
              <Label>Tax registration number</Label>
              <Input
                value={form.tax_registration_number}
                onChange={(e) =>
                  setForm({
                    ...form,
                    tax_registration_number: e.target.value,
                  })
                }
              />
            </div>
            <div className="md:col-span-2">
              <Label>Address</Label>
              <Input
                value={form.address_line1}
                onChange={(e) =>
                  setForm({ ...form, address_line1: e.target.value })
                }
              />
            </div>
            <div>
              <Label>City</Label>
              <Input
                value={form.city}
                onChange={(e) => setForm({ ...form, city: e.target.value })}
              />
            </div>
            <div>
              <Label>Country</Label>
              <Input
                value={form.country}
                onChange={(e) => setForm({ ...form, country: e.target.value })}
              />
            </div>
            <div>
              <Label>Payment terms</Label>
              <Input
                value={form.payment_terms}
                onChange={(e) =>
                  setForm({ ...form, payment_terms: e.target.value })
                }
                placeholder="30 days"
              />
            </div>
            <div>
              <Label>Lead time (days)</Label>
              <Input
                type="number"
                min={0}
                value={form.lead_time_days}
                onChange={(e) =>
                  setForm({ ...form, lead_time_days: e.target.value })
                }
              />
            </div>
            <div className="md:col-span-2">
              <Label>Notes</Label>
              <Textarea
                rows={2}
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowForm(false)}>
              Cancel
            </Button>
            <Button disabled={saving} onClick={() => void saveSupplier()}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {editing ? "Save changes" : "Add supplier"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ------------------------------------------------------- catalogue */}
      <Dialog
        open={!!catalogueFor}
        onOpenChange={(open) => !open && setCatalogueFor(null)}
      >
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>{catalogueFor?.name} catalogue</DialogTitle>
            <DialogDescription>
              What this supplier sells, and what you last paid. Prices fill in
              automatically when you raise a purchase order.
            </DialogDescription>
          </DialogHeader>

          {catalogueLoading ? (
            <div className="flex items-center justify-center py-10 text-secondary-500">
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Loading
            </div>
          ) : (
            <div className="space-y-4">
              <div className="max-h-72 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 border-b border-secondary-200 bg-secondary-50 text-left text-xs uppercase tracking-wide text-secondary-500">
                    <tr>
                      <th className="px-3 py-2">Ingredient</th>
                      {/* F38: the supplier SKU column is hidden. The field and
                          the purchase-order document logic are intact -- see
                          purchase_order_document.py, which prints "Flour [SKU]"
                          when one is set. It was built speculatively, before
                          the client had shared a single real supplier invoice,
                          so it is not shown until his paperwork proves his
                          suppliers actually quote codes. */}
                      <th className="px-3 py-2 text-right">Last price</th>
                      <th className="px-3 py-2 text-right">Pack</th>
                      <th className="px-3 py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {catalogue.length === 0 && (
                      <tr>
                        <td
                          colSpan={4}
                          className="px-3 py-6 text-center text-secondary-500"
                        >
                          Nothing listed for this supplier yet.
                        </td>
                      </tr>
                    )}
                    {catalogue.map((item) => (
                      <tr
                        key={item.id}
                        className="border-b border-secondary-100 last:border-0"
                      >
                        <td className="px-3 py-2">
                          <span className="font-medium text-secondary-900">
                            {item.ingredient_name}
                          </span>
                          {item.is_preferred && (
                            <Star className="ml-1 inline h-3 w-3 fill-warning-500 text-warning-500" />
                          )}
                          <span className="ml-1 text-xs text-secondary-500">
                            per {item.unit}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right">
                          {formatMoney(minor(item.last_price_minor), currency)}
                        </td>
                        <td className="px-3 py-2 text-right">
                          {Number(item.pack_size) > 0
                            ? `${formatQty(item.pack_size)} ${item.unit}`
                            : "-"}
                        </td>
                        <td className="px-3 py-2 text-right">
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={saving}
                            onClick={() => void removeItem(item)}
                          >
                            <Trash2 className="h-4 w-4 text-danger-600" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="rounded-lg border border-secondary-200 p-4">
                <p className="mb-3 text-sm font-medium text-secondary-900">
                  Add or update an item
                </p>
                <div className="grid gap-3 md:grid-cols-4">
                  <div className="md:col-span-2">
                    <Label>Ingredient</Label>
                    <Select
                      value={newItemIngredient}
                      onChange={(e) => setNewItemIngredient(e.target.value)}
                    >
                      <option value="">Select</option>
                      {purchasable.map((i) => (
                        <option key={i.id} value={i.id}>
                          {i.name} ({i.unit})
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Label>Price per unit ({currency})</Label>
                    <Input
                      type="number"
                      step="0.01"
                      min={0}
                      value={newItemPrice}
                      onChange={(e) => setNewItemPrice(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label>Pack size</Label>
                    <Input
                      type="number"
                      step="0.001"
                      min={0}
                      value={newItemPack}
                      onChange={(e) => setNewItemPack(e.target.value)}
                    />
                  </div>
                </div>
                <div className="mt-3 flex items-center justify-between">
                  <label className="flex items-center gap-2 text-sm text-secondary-600">
                    <input
                      type="checkbox"
                      className="h-4 w-4"
                      checked={newItemPreferred}
                      onChange={(e) => setNewItemPreferred(e.target.checked)}
                    />
                    Preferred supplier for this ingredient
                  </label>
                  <Button
                    size="sm"
                    disabled={saving || !newItemIngredient}
                    onClick={() => void addCatalogueItem()}
                  >
                    {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Save item
                  </Button>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* --------------------------------------------------------- history */}
      <Dialog
        open={!!historyFor}
        onOpenChange={(open) => !open && setHistoryFor(null)}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{historyFor?.name} purchase history</DialogTitle>
          </DialogHeader>
          {historyLoading ? (
            <div className="flex items-center justify-center py-10 text-secondary-500">
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Loading
            </div>
          ) : history.length === 0 ? (
            <p className="py-8 text-center text-secondary-500">
              Nothing has been ordered from this supplier yet.
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b border-secondary-200 text-left text-xs uppercase tracking-wide text-secondary-500">
                <tr>
                  <th className="px-3 py-2">Order</th>
                  <th className="px-3 py-2">Location</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2 text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {history.map((row) => (
                  <tr
                    key={row.id}
                    className="border-b border-secondary-100 last:border-0"
                  >
                    <td className="px-3 py-2">
                      <div className="font-medium">{row.po_number}</div>
                      <div className="text-xs text-secondary-500">
                        {new Date(row.created_at).toLocaleDateString()}
                      </div>
                    </td>
                    <td className="px-3 py-2">{row.location_name}</td>
                    <td className="px-3 py-2 capitalize">
                      {row.status.replace("_", " ")}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {formatMoney(minor(row.total_minor), currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default SuppliersPage;
