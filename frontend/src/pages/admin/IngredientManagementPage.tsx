/**
 * Ingredient Management Page
 * Admin interface for managing BOM ingredients (CRUD)
 */

import { useCallback, useEffect, useState } from "react";
import { Package, Plus, Pencil, Trash2, Loader2, AlertTriangle } from "lucide-react";

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

import type { Ingredient, IngredientCreate, IngredientUpdate } from "@/types/inventory";
import * as inventoryApi from "@/services/inventoryApi";
import { formatPKR, paisaToRupees, rupeesToPaisa } from "@/utils/currency";

export default function IngredientManagementPage() {
  const { toast } = useToast();

  // Data state
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [loading, setLoading] = useState(true);

  // Filter state
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState<boolean | "all">("all");

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
  const [supplierName, setSupplierName] = useState("");
  const [supplierContact, setSupplierContact] = useState("");
  const [reorderPoint, setReorderPoint] = useState("");
  const [reorderQuantity, setReorderQuantity] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [notes, setNotes] = useState("");

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

      setIngredients(filtered);
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Failed to load ingredients",
      });
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, activeFilter, search, toast]);

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
    setSupplierName("");
    setSupplierContact("");
    setReorderPoint("");
    setReorderQuantity("");
    setIsActive(true);
    setNotes("");
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
    setSupplierName(ingredient.supplier_name || "");
    setSupplierContact(ingredient.supplier_contact || "");
    setReorderPoint(String(ingredient.reorder_point || ""));
    setReorderQuantity(String(ingredient.reorder_quantity || ""));
    setIsActive(ingredient.is_active);
    setNotes(ingredient.notes || "");
    setEditOpen(true);
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

    setSaving(true);
    try {
      const payload: IngredientCreate = {
        name: name.trim(),
        category: category.trim() || "General",
        unit: unit.trim(),
        cost_per_unit: costPerUnitRupees
          ? rupeesToPaisa(parseFloat(costPerUnitRupees))
          : 0,
        supplier_name: supplierName.trim() || null,
        supplier_contact: supplierContact.trim() || null,
        reorder_point: reorderPoint ? parseFloat(reorderPoint) : 0,
        reorder_quantity: reorderQuantity ? parseFloat(reorderQuantity) : 0,
        is_active: isActive,
        notes: notes.trim() || null,
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

    setSaving(true);
    try {
      const payload: IngredientUpdate = {
        name: name.trim(),
        category: category.trim() || "General",
        unit: unit.trim(),
        cost_per_unit: costPerUnitRupees
          ? rupeesToPaisa(parseFloat(costPerUnitRupees))
          : 0,
        supplier_name: supplierName.trim() || null,
        supplier_contact: supplierContact.trim() || null,
        reorder_point: reorderPoint ? parseFloat(reorderPoint) : 0,
        reorder_quantity: reorderQuantity ? parseFloat(reorderQuantity) : 0,
        is_active: isActive,
        notes: notes.trim() || null,
      };

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
                          {ingredient.name}
                          {isLowStock && (
                            <AlertTriangle className="ml-2 inline h-4 w-4 text-red-500" />
                          )}
                        </td>
                        <td className="py-3 text-secondary-600">
                          {ingredient.category}
                        </td>
                        <td className="py-3 text-secondary-600">
                          {ingredient.unit}
                        </td>
                        <td className="py-3 text-right text-secondary-900">
                          {formatPKR(ingredient.cost_per_unit)}
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

            {/* Unit */}
            <div className="space-y-2">
              <Label htmlFor="create-unit">Unit *</Label>
              <Input
                id="create-unit"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                placeholder="kg, L, pieces, etc."
                className="min-h-[48px]"
              />
            </div>

            {/* Cost per Unit */}
            <div className="space-y-2">
              <Label htmlFor="create-cost">Cost per Unit (PKR)</Label>
              <Input
                id="create-cost"
                type="number"
                min="0"
                step="0.01"
                value={costPerUnitRupees}
                onChange={(e) => setCostPerUnitRupees(e.target.value)}
                placeholder="800.00"
                className="min-h-[48px]"
              />
            </div>

            {/* Supplier */}
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
              <Label htmlFor="edit-unit">Unit *</Label>
              <Input
                id="edit-unit"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                className="min-h-[48px]"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-cost">Cost per Unit (PKR)</Label>
              <Input
                id="edit-cost"
                type="number"
                min="0"
                step="0.01"
                value={costPerUnitRupees}
                onChange={(e) => setCostPerUnitRupees(e.target.value)}
                className="min-h-[48px]"
              />
            </div>

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
