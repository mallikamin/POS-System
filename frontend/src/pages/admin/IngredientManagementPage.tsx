/**
 * Ingredient Management Page
 * Admin interface for managing BOM ingredients (CRUD)
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Package,
  Plus,
  Pencil,
  Trash2,
  Loader2,
  AlertTriangle,
  ChefHat,
  ShoppingBag,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { ImageField } from "@/components/admin/ImageField";
import { Thumb } from "@/components/admin/Thumb";

import type { Ingredient, IngredientCreate, IngredientUpdate } from "@/types/inventory";
import * as inventoryApi from "@/services/inventoryApi";
import { formatPKR, paisaToRupees, rupeesToPaisa } from "@/utils/currency";
import { useCurrencyCode } from "@/hooks/useCurrencyCode";

export default function IngredientManagementPage() {
  const currency = useCurrencyCode();
  const { toast } = useToast();

  // Data state
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [loading, setLoading] = useState(true);

  // Filter state
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState<boolean | "all">("all");
  /*
   * Martin (FZ LLC, 2026-09-02): "there is no difference between bought items
   * (flour, coca cola cans, fruits) which have a price and ingredients
   * manufactured by us, where the price needs to be calculated by the
   * system". The distinction always existed in the data (`is_produced`); this
   * screen simply never showed it, and let a calculated cost be typed over.
   */
  const [sourceFilter, setSourceFilter] = useState<"all" | "bought" | "produced">("all");

  // Dialog state
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Ingredient | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Ingredient | null>(null);
  const [saving, setSaving] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [category, setCategory] = useState("General");
  const [unit, setUnit] = useState("kg");
  const [costPerUnitRupees, setCostPerUnitRupees] = useState(""); // Display in PKR
  /**
   * Martin (FZ LLC, 2026-09-04, M8): "2 units and a conversion. The unit you
   * buy, the unit you store) use in recipes ... I buy tomato cans..so in the
   * purchase order I will request 2 cans. But in my recipes I use grams".
   *
   * Off by default, and the whole block stays hidden until it is switched on,
   * because most ingredients are bought in the unit they are stocked in and
   * three extra boxes on every create form would be a tax on the simple case.
   */
  const [hasPurchaseUnit, setHasPurchaseUnit] = useState(false);
  const [purchaseUnit, setPurchaseUnit] = useState("");
  const [unitsPerPurchaseUnit, setUnitsPerPurchaseUnit] = useState("");
  const [purchaseCostRupees, setPurchaseCostRupees] = useState("");
  const [supplierName, setSupplierName] = useState("");
  const [supplierContact, setSupplierContact] = useState("");
  const [reorderPoint, setReorderPoint] = useState("");
  const [reorderQuantity, setReorderQuantity] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [isProduced, setIsProduced] = useState(false);
  const [notes, setNotes] = useState("");
  const [imageUrl, setImageUrl] = useState<string | null>(null);

  // Fetch ingredients with filters
  const fetchIngredients = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (categoryFilter) params.category = categoryFilter;
      if (activeFilter !== "all") params.is_active = activeFilter;

      const data = await inventoryApi.fetchIngredients(params);

      // Client-side search filter
      let filtered = data;
      if (search) {
        const searchLower = search.toLowerCase();
        filtered = data.filter((ing) =>
          ing.name.toLowerCase().includes(searchLower)
        );
      }
      if (sourceFilter !== "all") {
        filtered = filtered.filter((ing) =>
          sourceFilter === "produced" ? ing.is_produced : !ing.is_produced
        );
      }

      setIngredients(filtered);
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Failed to load ingredients",
      });
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, activeFilter, sourceFilter, search, toast]);

  useEffect(() => {
    fetchIngredients();
  }, [fetchIngredients]);

  // Extract unique categories for filter dropdown
  const categories = Array.from(
    new Set(ingredients.map((ing) => ing.category))
  ).sort();

  // Reset form
  function resetForm() {
    setName("");
    setCategory("General");
    setUnit("kg");
    setCostPerUnitRupees("");
    setHasPurchaseUnit(false);
    setPurchaseUnit("");
    setUnitsPerPurchaseUnit("");
    setPurchaseCostRupees("");
    setSupplierName("");
    setSupplierContact("");
    setReorderPoint("");
    setReorderQuantity("");
    setIsActive(true);
    setIsProduced(false);
    setNotes("");
    setImageUrl(null);
  }

  // Open create dialog
  function openCreate() {
    resetForm();
    setCreateOpen(true);
  }

  // Open edit dialog
  function openEdit(ingredient: Ingredient) {
    setEditTarget(ingredient);
    setName(ingredient.name);
    setCategory(ingredient.category);
    setUnit(ingredient.unit);
    setCostPerUnitRupees(String(paisaToRupees(ingredient.cost_per_unit)));
    setHasPurchaseUnit(Boolean(ingredient.purchase_unit));
    setPurchaseUnit(ingredient.purchase_unit || "");
    setUnitsPerPurchaseUnit(
      ingredient.purchase_unit ? String(ingredient.units_per_purchase_unit) : ""
    );
    setPurchaseCostRupees(
      ingredient.purchase_unit
        ? String(paisaToRupees(ingredient.purchase_cost_minor))
        : ""
    );
    setSupplierName(ingredient.supplier_name || "");
    setSupplierContact(ingredient.supplier_contact || "");
    setReorderPoint(String(ingredient.reorder_point || ""));
    setReorderQuantity(String(ingredient.reorder_quantity || ""));
    setIsActive(ingredient.is_active);
    setIsProduced(ingredient.is_produced);
    setNotes(ingredient.notes || "");
    setImageUrl(ingredient.image_url ?? null);
    setEditOpen(true);
  }

  /**
   * The purchase-unit trio for a payload, or the "no conversion" trio.
   *
   * Returned as one object rather than three loose values so the unit, the
   * conversion and the price it belongs to can never be assembled from
   * different places and end up describing different things. A produced
   * ingredient never gets one: it is made, not bought.
   */
  function purchaseFields() {
    if (isProduced || !hasPurchaseUnit || !purchaseUnit.trim()) {
      return {
        purchase_unit: null,
        units_per_purchase_unit: 1,
        purchase_cost_minor: 0,
      };
    }
    return {
      purchase_unit: purchaseUnit.trim(),
      units_per_purchase_unit: parseFloat(unitsPerPurchaseUnit),
      purchase_cost_minor: purchaseCostRupees
        ? rupeesToPaisa(parseFloat(purchaseCostRupees))
        : 0,
    };
  }

  /** Null when the form is fine, otherwise the sentence to show. */
  function purchaseUnitProblem(): string | null {
    if (isProduced || !hasPurchaseUnit) return null;
    if (!purchaseUnit.trim()) {
      return "Say what you buy it in, for example a can or a case.";
    }
    const conversion = parseFloat(unitsPerPurchaseUnit);
    if (!Number.isFinite(conversion) || conversion <= 0) {
      return `Say how many ${unit.trim() || "units"} are in one ${purchaseUnit.trim()}.`;
    }
    return null;
  }

  // Create ingredient
  async function handleCreate() {
    if (!name.trim() || !unit.trim()) {
      toast({
        variant: "destructive",
        title: "Name and unit are required",
      });
      return;
    }

    const problem = purchaseUnitProblem();
    if (problem) {
      toast({ variant: "destructive", title: problem });
      return;
    }

    setSaving(true);
    try {
      const payload: IngredientCreate = {
        name: name.trim(),
        category: category.trim() || "General",
        unit: unit.trim(),
        // A made-in-house ingredient has no typed cost: the recipe that
        // produces it writes the cost. The server ignores one anyway.
        cost_per_unit:
          !isProduced && costPerUnitRupees
            ? rupeesToPaisa(parseFloat(costPerUnitRupees))
            : 0,
        // M8. When a purchase unit is set the server derives the cost above
        // from these three and ignores what was sent, so the two never drift.
        ...purchaseFields(),
        supplier_name: isProduced ? null : supplierName.trim() || null,
        supplier_contact: isProduced ? null : supplierContact.trim() || null,
        reorder_point: reorderPoint ? parseFloat(reorderPoint) : 0,
        reorder_quantity: reorderQuantity ? parseFloat(reorderQuantity) : 0,
        is_active: isActive,
        is_produced: isProduced,
        notes: notes.trim() || null,
        image_url: imageUrl,
      };

      await inventoryApi.createIngredient(payload);

      toast({
        variant: "success",
        title: "Ingredient created",
      });

      setCreateOpen(false);
      await fetchIngredients();
    } catch (err: any) {
      const msg =
        err.response?.data?.detail || "Failed to create ingredient";
      toast({
        variant: "destructive",
        title: msg,
      });
    } finally {
      setSaving(false);
    }
  }

  // Update ingredient
  async function handleUpdate() {
    if (!editTarget) return;

    if (!name.trim() || !unit.trim()) {
      toast({
        variant: "destructive",
        title: "Name and unit are required",
      });
      return;
    }

    const problem = purchaseUnitProblem();
    if (problem) {
      toast({ variant: "destructive", title: problem });
      return;
    }

    setSaving(true);
    try {
      const payload: IngredientUpdate = {
        name: name.trim(),
        category: category.trim() || "General",
        unit: unit.trim(),
        ...purchaseFields(),
        supplier_name: isProduced ? null : supplierName.trim() || null,
        supplier_contact: isProduced ? null : supplierContact.trim() || null,
        reorder_point: reorderPoint ? parseFloat(reorderPoint) : 0,
        reorder_quantity: reorderQuantity ? parseFloat(reorderQuantity) : 0,
        is_active: isActive,
        is_produced: isProduced,
        notes: notes.trim() || null,
        image_url: imageUrl,
      };
      // Only a bought ingredient's cost is ours to send. A produced one's is
      // calculated by its recipe and the server drops any value sent.
      if (!isProduced) {
        payload.cost_per_unit = costPerUnitRupees
          ? rupeesToPaisa(parseFloat(costPerUnitRupees))
          : 0;
      }

      await inventoryApi.updateIngredient(editTarget.id, payload);

      toast({
        variant: "success",
        title: "Ingredient updated",
      });

      setEditOpen(false);
      setEditTarget(null);
      await fetchIngredients();
    } catch (err: any) {
      const msg =
        err.response?.data?.detail || "Failed to update ingredient";
      toast({
        variant: "destructive",
        title: msg,
      });
    } finally {
      setSaving(false);
    }
  }

  // Delete ingredient (soft delete - sets is_active=false)
  async function handleDelete() {
    if (!deleteTarget) return;

    try {
      await inventoryApi.deleteIngredient(deleteTarget.id);

      toast({
        variant: "success",
        title: "Ingredient deleted",
      });

      setDeleteTarget(null);
      await fetchIngredients();
    } catch (err: any) {
      const msg =
        err.response?.data?.detail || "Failed to delete ingredient";
      toast({
        variant: "destructive",
        title: msg,
      });
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Package className="h-7 w-7 text-primary-600" />
          <h1 className="text-pos-2xl font-bold text-secondary-900">
            Ingredient Management
          </h1>
        </div>
        <Button onClick={openCreate} className="min-h-[48px] gap-2">
          <Plus className="h-4 w-4" />
          Add Ingredient
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Search */}
        <Input
          placeholder="Search by name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="min-h-[48px] max-w-md"
        />

        {/* Category filter */}
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="min-h-[48px] rounded-md border border-secondary-300 px-3 text-pos-sm"
        >
          <option value="">All Categories</option>
          {categories.map((cat) => (
            <option key={cat} value={cat}>
              {cat}
            </option>
          ))}
        </select>

        {/* Source filter: bought vs made in-house */}
        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value as typeof sourceFilter)}
          className="min-h-[48px] rounded-md border border-secondary-300 px-3 text-pos-sm"
          aria-label="Filter by source"
        >
          <option value="all">Bought and made in-house</option>
          <option value="bought">Bought only</option>
          <option value="produced">Made in-house only</option>
        </select>

        {/* Active filter */}
        <select
          value={String(activeFilter)}
          onChange={(e) => {
            const val = e.target.value;
            setActiveFilter(val === "all" ? "all" : val === "true");
          }}
          className="min-h-[48px] rounded-md border border-secondary-300 px-3 text-pos-sm"
        >
          <option value="all">All Status</option>
          <option value="true">Active Only</option>
          <option value="false">Inactive Only</option>
        </select>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="pt-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
            </div>
          ) : ingredients.length === 0 ? (
            <div className="py-12 text-center text-secondary-500">
              No ingredients found.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-pos-sm">
                <thead>
                  <tr className="border-b text-secondary-500">
                    <th className="pb-3 font-medium">Name</th>
                    <th className="pb-3 font-medium">Source</th>
                    <th className="pb-3 font-medium">Category</th>
                    <th className="pb-3 font-medium">Unit</th>
                    <th className="pb-3 font-medium text-right">Cost/Unit</th>
                    <th className="pb-3 font-medium text-right">
                      Current Stock
                    </th>
                    <th className="pb-3 font-medium text-right">
                      Reorder Point
                    </th>
                    <th className="pb-3 font-medium">Status</th>
                    <th className="pb-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {ingredients.map((ingredient) => {
                    const isLowStock =
                      ingredient.current_stock < ingredient.reorder_point;

                    return (
                      <tr
                        key={ingredient.id}
                        className="border-b last:border-0 hover:bg-secondary-50"
                      >
                        <td className="py-3 font-medium text-secondary-900">
                          <div className="flex items-center gap-3">
                            <Thumb src={ingredient.image_url} alt={ingredient.name} size="lg" />
                            <span>
                              {ingredient.name}
                              {isLowStock && (
                                <AlertTriangle className="ml-2 inline h-4 w-4 text-red-500" />
                              )}
                            </span>
                          </div>
                        </td>
                        <td className="py-3">
                          {ingredient.is_produced ? (
                            <div className="flex flex-col gap-0.5">
                              <Badge variant="secondary" className="w-fit gap-1 text-xs">
                                <ChefHat className="h-3 w-3" />
                                Made in-house
                              </Badge>
                              {ingredient.production_recipe_id ? (
                                <Link
                                  to="/admin/recipes"
                                  className="text-[11px] text-primary-600 hover:underline"
                                >
                                  Recipe: {ingredient.production_recipe_name}
                                </Link>
                              ) : (
                                <Link
                                  to="/admin/recipes"
                                  className="text-[11px] text-amber-700 hover:underline"
                                >
                                  No recipe yet. Build one
                                </Link>
                              )}
                            </div>
                          ) : (
                            <Badge variant="outline" className="w-fit gap-1 text-xs">
                              <ShoppingBag className="h-3 w-3" />
                              Bought
                            </Badge>
                          )}
                        </td>
                        <td className="py-3 text-secondary-600">
                          {ingredient.category}
                        </td>
                        <td className="py-3 text-secondary-600">
                          {ingredient.unit}
                          {/* M8: the second unit, when there is one, so the two
                              are visible on the row rather than only in the
                              dialog that set them. */}
                          {ingredient.purchase_unit && (
                            <div className="text-[10px] font-normal text-secondary-400">
                              buy: 1 {ingredient.purchase_unit} ={" "}
                              {ingredient.units_per_purchase_unit} {ingredient.unit}
                            </div>
                          )}
                        </td>
                        <td className="py-3 text-right text-secondary-900">
                          {formatPKR(ingredient.cost_per_unit)}
                          {ingredient.is_produced && (
                            <div className="text-[10px] font-normal text-secondary-400">
                              {ingredient.production_recipe_id
                                ? "calculated from recipe"
                                : "awaiting recipe"}
                            </div>
                          )}
                          {!ingredient.is_produced && ingredient.purchase_unit && (
                            <div className="text-[10px] font-normal text-secondary-400">
                              {formatPKR(ingredient.purchase_cost_minor)} per{" "}
                              {ingredient.purchase_unit}
                            </div>
                          )}
                        </td>
                        <td className="py-3 text-right text-secondary-600">
                          {ingredient.current_stock.toFixed(2)}
                        </td>
                        <td className="py-3 text-right text-secondary-600">
                          {ingredient.reorder_point > 0
                            ? ingredient.reorder_point.toFixed(2)
                            : "—"}
                        </td>
                        <td className="py-3">
                          <div className="flex items-center gap-2">
                            <Badge
                              variant={
                                ingredient.is_active ? "success" : "secondary"
                              }
                              className="text-xs"
                            >
                              {ingredient.is_active ? "Active" : "Inactive"}
                            </Badge>
                            {isLowStock && (
                              <Badge
                                variant="destructive"
                                className="text-xs"
                              >
                                Low Stock
                              </Badge>
                            )}
                          </div>
                        </td>
                        <td className="py-3">
                          <div className="flex items-center justify-end gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="min-h-[40px]"
                              onClick={() => openEdit(ingredient)}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="min-h-[40px] text-danger-600 hover:text-danger-700"
                              onClick={() => setDeleteTarget(ingredient)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Create Ingredient</DialogTitle>
            <DialogDescription>
              Add a new ingredient to the inventory.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Name */}
            <div className="space-y-2">
              <Label htmlFor="create-name">Name *</Label>
              <Input
                id="create-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Chicken (with bone)"
                className="min-h-[48px]"
              />
            </div>

            <ImageField
              value={imageUrl}
              onChange={setImageUrl}
              idPrefix="create-image"
            />

            {/* Category */}
            <div className="space-y-2">
              <Label htmlFor="create-category">Category</Label>
              <Input
                id="create-category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="e.g., Meat, Grains, Spices"
                className="min-h-[48px]"
              />
            </div>

            {/* Unit. Relabelled with M8: it is the STOCKING unit, and calling
                it that here is the only place the distinction can be taught. */}
            <div className="space-y-2">
              <Label htmlFor="create-unit">Unit I store and cook in *</Label>
              <Input
                id="create-unit"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                placeholder="kg, g, L, pieces, etc."
                className="min-h-[48px]"
              />
              <p className="text-xs text-secondary-500">
                Recipes and stock on hand are both counted in this.
              </p>
            </div>

            {/* Bought or made in-house */}
            <SourceSwitch
              idPrefix="create"
              isProduced={isProduced}
              onChange={setIsProduced}
            />

            {/* Cost per Unit: typed for a bought item, calculated for a
                made-in-house one */}
            {isProduced ? (
              <p className="rounded-md border border-dashed border-secondary-300 bg-secondary-50 px-3 py-2 text-pos-sm text-secondary-600">
                The cost per {unit.trim() || "unit"} will be calculated from this
                ingredient's recipe. After saving, build the recipe under{" "}
                <span className="font-medium">Recipes</span> and choose
                &ldquo;Sub-recipe&rdquo; as the target.
              </p>
            ) : (
              <PurchaseUnitFields
                idPrefix="create"
                currency={currency}
                stockUnit={unit}
                enabled={hasPurchaseUnit}
                onEnabledChange={setHasPurchaseUnit}
                purchaseUnit={purchaseUnit}
                onPurchaseUnitChange={setPurchaseUnit}
                unitsPerPurchaseUnit={unitsPerPurchaseUnit}
                onUnitsPerPurchaseUnitChange={setUnitsPerPurchaseUnit}
                purchaseCostRupees={purchaseCostRupees}
                onPurchaseCostChange={setPurchaseCostRupees}
                costPerUnitRupees={costPerUnitRupees}
                onCostPerUnitChange={setCostPerUnitRupees}
              />
            )}

            {/* Supplier (bought items only) */}
            {!isProduced && (
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="create-supplier-name">Supplier Name</Label>
                <Input
                  id="create-supplier-name"
                  value={supplierName}
                  onChange={(e) => setSupplierName(e.target.value)}
                  placeholder="Optional"
                  className="min-h-[48px]"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="create-supplier-contact">
                  Supplier Contact
                </Label>
                <Input
                  id="create-supplier-contact"
                  value={supplierContact}
                  onChange={(e) => setSupplierContact(e.target.value)}
                  placeholder="Phone or email"
                  className="min-h-[48px]"
                />
              </div>
            </div>
            )}

            {/* Reorder points */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="create-reorder-point">Reorder Point</Label>
                <Input
                  id="create-reorder-point"
                  type="number"
                  min="0"
                  step="0.01"
                  value={reorderPoint}
                  onChange={(e) => setReorderPoint(e.target.value)}
                  placeholder="20.00"
                  className="min-h-[48px]"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="create-reorder-qty">Reorder Quantity</Label>
                <Input
                  id="create-reorder-qty"
                  type="number"
                  min="0"
                  step="0.01"
                  value={reorderQuantity}
                  onChange={(e) => setReorderQuantity(e.target.value)}
                  placeholder="50.00"
                  className="min-h-[48px]"
                />
              </div>
            </div>

            {/* Active toggle */}
            <div className="flex items-center gap-2">
              <input
                id="create-active"
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="h-4 w-4 rounded border-secondary-300"
              />
              <Label htmlFor="create-active" className="cursor-pointer">
                Active
              </Label>
            </div>

            {/* Notes */}
            <div className="space-y-2">
              <Label htmlFor="create-notes">Notes</Label>
              <Textarea
                id="create-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Additional information..."
                rows={3}
                className="resize-none"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCreateOpen(false)}
              className="min-h-touch"
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!name.trim() || !unit.trim() || saving}
              className="min-h-touch gap-2"
            >
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Ingredient</DialogTitle>
            <DialogDescription>
              Update ingredient details.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Same form fields as Create */}
            <div className="space-y-2">
              <Label htmlFor="edit-name">Name *</Label>
              <Input
                id="edit-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="min-h-[48px]"
              />
            </div>

            <ImageField
              value={imageUrl}
              onChange={setImageUrl}
              idPrefix="edit-image"
            />

            <div className="space-y-2">
              <Label htmlFor="edit-category">Category</Label>
              <Input
                id="edit-category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="min-h-[48px]"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-unit">Unit I store and cook in *</Label>
              <Input
                id="edit-unit"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                className="min-h-[48px]"
              />
              <p className="text-xs text-secondary-500">
                Recipes and stock on hand are both counted in this.
              </p>
            </div>

            <SourceSwitch
              idPrefix="edit"
              isProduced={isProduced}
              onChange={setIsProduced}
              lockedByRecipe={!!editTarget?.production_recipe_id}
            />

            {isProduced ? (
              <div className="space-y-2">
                <Label>Cost per Unit ({currency})</Label>
                <div className="flex min-h-[48px] items-center justify-between rounded-md border border-dashed border-secondary-300 bg-secondary-50 px-3 text-pos-sm">
                  <span className="font-medium text-secondary-900">
                    {formatPKR(editTarget?.cost_per_unit ?? 0)}
                  </span>
                  {editTarget?.production_recipe_id ? (
                    <Link
                      to="/admin/recipes"
                      className="text-primary-600 hover:underline"
                    >
                      Calculated from recipe. Edit the recipe to change it.
                    </Link>
                  ) : (
                    <Link to="/admin/recipes" className="text-amber-700 hover:underline">
                      No recipe yet. Build one to calculate the cost.
                    </Link>
                  )}
                </div>
              </div>
            ) : (
              <PurchaseUnitFields
                idPrefix="edit"
                currency={currency}
                stockUnit={unit}
                enabled={hasPurchaseUnit}
                onEnabledChange={setHasPurchaseUnit}
                purchaseUnit={purchaseUnit}
                onPurchaseUnitChange={setPurchaseUnit}
                unitsPerPurchaseUnit={unitsPerPurchaseUnit}
                onUnitsPerPurchaseUnitChange={setUnitsPerPurchaseUnit}
                purchaseCostRupees={purchaseCostRupees}
                onPurchaseCostChange={setPurchaseCostRupees}
                costPerUnitRupees={costPerUnitRupees}
                onCostPerUnitChange={setCostPerUnitRupees}
              />
            )}

            {!isProduced && (
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="edit-supplier-name">Supplier Name</Label>
                <Input
                  id="edit-supplier-name"
                  value={supplierName}
                  onChange={(e) => setSupplierName(e.target.value)}
                  className="min-h-[48px]"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-supplier-contact">
                  Supplier Contact
                </Label>
                <Input
                  id="edit-supplier-contact"
                  value={supplierContact}
                  onChange={(e) => setSupplierContact(e.target.value)}
                  className="min-h-[48px]"
                />
              </div>
            </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="edit-reorder-point">Reorder Point</Label>
                <Input
                  id="edit-reorder-point"
                  type="number"
                  min="0"
                  step="0.01"
                  value={reorderPoint}
                  onChange={(e) => setReorderPoint(e.target.value)}
                  className="min-h-[48px]"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-reorder-qty">Reorder Quantity</Label>
                <Input
                  id="edit-reorder-qty"
                  type="number"
                  min="0"
                  step="0.01"
                  value={reorderQuantity}
                  onChange={(e) => setReorderQuantity(e.target.value)}
                  className="min-h-[48px]"
                />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <input
                id="edit-active"
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="h-4 w-4 rounded border-secondary-300"
              />
              <Label htmlFor="edit-active" className="cursor-pointer">
                Active
              </Label>
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-notes">Notes</Label>
              <Textarea
                id="edit-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                className="resize-none"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEditOpen(false)}
              className="min-h-touch"
            >
              Cancel
            </Button>
            <Button
              onClick={handleUpdate}
              disabled={!name.trim() || !unit.trim() || saving}
              className="min-h-touch gap-2"
            >
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Update
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Ingredient</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete "{deleteTarget?.name}"? This will
              deactivate the ingredient (soft delete).
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteTarget(null)}
              className="min-h-touch"
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              className="min-h-touch"
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ==========================================================================
   Bought / made in-house switch
   ========================================================================== */

interface SourceSwitchProps {
  idPrefix: string;
  isProduced: boolean;
  onChange: (produced: boolean) => void;
  /** An active recipe makes this ingredient; the server refuses to flip it. */
  lockedByRecipe?: boolean;
}

function SourceSwitch({ idPrefix, isProduced, onChange, lockedByRecipe }: SourceSwitchProps) {
  const base =
    "flex flex-1 items-start gap-2 rounded-lg border-2 p-3 text-left transition-colors min-h-[64px]";
  const on = "border-primary-500 bg-primary-50";
  const off = "border-secondary-200 hover:border-secondary-300";
  return (
    <div className="space-y-2">
      <Label>Source</Label>
      <div className="flex gap-3">
        <button
          type="button"
          id={`${idPrefix}-source-bought`}
          onClick={() => !lockedByRecipe && onChange(false)}
          disabled={lockedByRecipe}
          className={`${base} ${!isProduced ? on : off} disabled:cursor-not-allowed disabled:opacity-60`}
          aria-pressed={!isProduced}
        >
          <ShoppingBag className="mt-0.5 h-4 w-4 shrink-0 text-secondary-500" />
          <span>
            <span className="block font-medium text-secondary-900">Bought</span>
            <span className="block text-xs text-secondary-500">
              Flour, cans, fruit. You enter the price you pay.
            </span>
          </span>
        </button>
        <button
          type="button"
          id={`${idPrefix}-source-produced`}
          onClick={() => onChange(true)}
          className={`${base} ${isProduced ? on : off}`}
          aria-pressed={isProduced}
        >
          <ChefHat className="mt-0.5 h-4 w-4 shrink-0 text-secondary-500" />
          <span>
            <span className="block font-medium text-secondary-900">Made in-house</span>
            <span className="block text-xs text-secondary-500">
              Dough, sauces, fillings. The cost is calculated from its recipe.
            </span>
          </span>
        </button>
      </div>
      {lockedByRecipe && (
        <p className="text-xs text-secondary-500">
          An active recipe makes this ingredient. Delete that recipe first to mark it as bought.
        </p>
      )}
    </div>
  );
}

interface PurchaseUnitFieldsProps {
  idPrefix: string;
  currency: string;
  /** The stocking unit typed above, used verbatim in every label here. */
  stockUnit: string;
  enabled: boolean;
  onEnabledChange: (value: boolean) => void;
  purchaseUnit: string;
  onPurchaseUnitChange: (value: string) => void;
  unitsPerPurchaseUnit: string;
  onUnitsPerPurchaseUnitChange: (value: string) => void;
  purchaseCostRupees: string;
  onPurchaseCostChange: (value: string) => void;
  costPerUnitRupees: string;
  onCostPerUnitChange: (value: string) => void;
}

/**
 * Cost for a bought ingredient, in one unit or in two.
 *
 * Martin (FZ LLC, 2026-09-04, M8): "I buy tomato cans..so in the purchase
 * order I will request 2 cans. But in my recipes I use grams."
 *
 * The switch is off by default and the whole two-unit block is hidden behind
 * it, so the common case (buy kilos, cook kilos) is the same single cost box
 * it has always been. Switched on, the typed cost box disappears entirely and
 * is replaced by a computed line, because a screen that shows both an editable
 * cost per gram and a price per can invites someone to make them disagree.
 */
function PurchaseUnitFields({
  idPrefix,
  currency,
  stockUnit,
  enabled,
  onEnabledChange,
  purchaseUnit,
  onPurchaseUnitChange,
  unitsPerPurchaseUnit,
  onUnitsPerPurchaseUnitChange,
  purchaseCostRupees,
  onPurchaseCostChange,
  costPerUnitRupees,
  onCostPerUnitChange,
}: PurchaseUnitFieldsProps) {
  const storeUnit = stockUnit.trim() || "unit";
  const buyUnit = purchaseUnit.trim() || "purchase unit";
  const conversion = parseFloat(unitsPerPurchaseUnit);
  const price = parseFloat(purchaseCostRupees);
  const derived =
    Number.isFinite(conversion) && conversion > 0 && Number.isFinite(price)
      ? price / conversion
      : null;

  return (
    <div className="space-y-3">
      <label
        htmlFor={`${idPrefix}-two-units`}
        className="flex cursor-pointer items-start gap-3 rounded-lg border-2 border-secondary-200 p-3 transition-colors hover:border-secondary-300"
      >
        <input
          id={`${idPrefix}-two-units`}
          type="checkbox"
          checked={enabled}
          onChange={(e) => onEnabledChange(e.target.checked)}
          className="mt-1 h-5 w-5 shrink-0 accent-primary-600"
        />
        <span>
          <span className="block font-medium text-secondary-900">
            I buy this in a different unit from the one I cook with
          </span>
          <span className="block text-xs text-secondary-500">
            For example, bought by the can and used by the gram.
          </span>
        </span>
      </label>

      {!enabled ? (
        <div className="space-y-2">
          <Label htmlFor={`${idPrefix}-cost`}>
            Cost per {storeUnit} ({currency})
          </Label>
          <Input
            id={`${idPrefix}-cost`}
            type="number"
            min="0"
            step="0.01"
            value={costPerUnitRupees}
            onChange={(e) => onCostPerUnitChange(e.target.value)}
            placeholder="800.00"
            className="min-h-[48px]"
          />
        </div>
      ) : (
        <div className="space-y-3 rounded-lg border border-secondary-200 bg-secondary-50 p-3">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor={`${idPrefix}-purchase-unit`}>I buy it in *</Label>
              <Input
                id={`${idPrefix}-purchase-unit`}
                value={purchaseUnit}
                onChange={(e) => onPurchaseUnitChange(e.target.value)}
                placeholder="can, case, sack"
                className="min-h-[48px]"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor={`${idPrefix}-conversion`}>
                {storeUnit} in one {buyUnit} *
              </Label>
              <Input
                id={`${idPrefix}-conversion`}
                type="number"
                min="0"
                step="any"
                value={unitsPerPurchaseUnit}
                onChange={(e) => onUnitsPerPurchaseUnitChange(e.target.value)}
                placeholder="400"
                className="min-h-[48px]"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor={`${idPrefix}-purchase-cost`}>
              Cost per {buyUnit} ({currency})
            </Label>
            <Input
              id={`${idPrefix}-purchase-cost`}
              type="number"
              min="0"
              step="0.01"
              value={purchaseCostRupees}
              onChange={(e) => onPurchaseCostChange(e.target.value)}
              placeholder="8.50"
              className="min-h-[48px]"
            />
          </div>

          {/* Read-only on purpose. This is the number recipes are costed at,
              and it is arithmetic, not an opinion. */}
          <p className="text-pos-sm text-secondary-600">
            {derived === null ? (
              <>
                Fill in the three boxes above and the cost per {storeUnit} will
                be worked out here.
              </>
            ) : (
              <>
                Cost per {storeUnit}:{" "}
                <span className="font-medium text-secondary-900">
                  {currency} {derived.toFixed(4)}
                </span>
                . Purchase orders are placed in {buyUnit}s; recipes and stock
                stay in {storeUnit}.
              </>
            )}
          </p>
        </div>
      )}
    </div>
  );
}
