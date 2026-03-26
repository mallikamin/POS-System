/**
 * Recipe Builder Page
 * Two-panel interface: Menu Items ← → Recipe Editor
 * Auto-calculates food cost % with real-time updates
 */

import { useCallback, useEffect, useState } from "react";
import {
  ChefHat,
  Plus,
  Save,
  Trash2,
  Loader2,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";

import type { MenuItem, Category } from "@/types/menu";
import type {
  Ingredient,
  Recipe,
  RecipeItemCreate,
} from "@/types/inventory";
import * as menuApi from "@/services/menuApi";
import * as inventoryApi from "@/services/inventoryApi";
import { formatPKR, paisaToRupees } from "@/utils/currency";

export default function RecipeBuilderPage() {
  const { toast } = useToast();

  // Menu items + categories
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [loading, setLoading] = useState(true);

  // Ingredients (for dropdown)
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);

  // Selected menu item + recipe
  const [selectedMenuItem, setSelectedMenuItem] = useState<MenuItem | null>(
    null
  );
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [recipeLoading, setRecipeLoading] = useState(false);

  // Recipe editor state
  const [recipeItems, setRecipeItems] = useState<RecipeItemCreate[]>([]);
  const [yieldServings, setYieldServings] = useState(1);
  const [prepTime, setPrepTime] = useState<number | null>(null);
  const [cookTime, setCookTime] = useState<number | null>(null);
  const [instructions, setInstructions] = useState("");
  const [notes, setNotes] = useState("");

  // Ingredient add dialog
  const [addIngredientOpen, setAddIngredientOpen] = useState(false);
  const [newIngredientId, setNewIngredientId] = useState("");
  const [newQuantity, setNewQuantity] = useState("");
  const [newWaste, setNewWaste] = useState("");

  // Delete confirmation
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  // Saving state
  const [saving, setSaving] = useState(false);

  // Fetch menu items + categories
  const fetchMenuData = useCallback(async () => {
    setLoading(true);
    try {
      const [itemsData, catsData] = await Promise.all([
        menuApi.fetchMenuItems({
          category_id: categoryFilter || undefined,
          available_only: false,
        }),
        menuApi.fetchCategories(false),
      ]);

      setMenuItems(itemsData);
      setCategories(catsData);
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Failed to load menu items",
      });
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, toast]);

  // Fetch ingredients (for dropdown)
  const fetchIngredients = useCallback(async () => {
    try {
      const data = await inventoryApi.fetchIngredients({ is_active: true });
      setIngredients(data);
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Failed to load ingredients",
      });
    }
  }, [toast]);

  useEffect(() => {
    fetchMenuData();
    fetchIngredients();
  }, [fetchMenuData, fetchIngredients]);

  // Load recipe when menu item is selected
  const loadRecipe = useCallback(
    async (menuItem: MenuItem) => {
      setSelectedMenuItem(menuItem);
      setRecipeLoading(true);

      try {
        const recipeData = await inventoryApi.getRecipeByMenuItem(menuItem.id);

        if (recipeData) {
          // Recipe exists - load it
          setRecipe(recipeData);
          setYieldServings(recipeData.yield_servings);
          setPrepTime(recipeData.prep_time_minutes);
          setCookTime(recipeData.cook_time_minutes);
          setInstructions(recipeData.instructions || "");
          setNotes(recipeData.notes || "");

          // Convert recipe_items to RecipeItemCreate format
          setRecipeItems(
            recipeData.recipe_items.map((item) => ({
              ingredient_id: item.ingredient_id,
              quantity: item.quantity,
              unit: item.unit,
              waste_factor: item.waste_factor,
              notes: item.notes || undefined,
            }))
          );
        } else {
          // No recipe - reset to defaults
          setRecipe(null);
          setYieldServings(1);
          setPrepTime(null);
          setCookTime(null);
          setInstructions("");
          setNotes("");
          setRecipeItems([]);
        }
      } catch (err) {
        toast({
          variant: "destructive",
          title: "Failed to load recipe",
        });
      } finally {
        setRecipeLoading(false);
      }
    },
    [toast]
  );

  // Real-time cost calculation
  const calculateCosts = useCallback(() => {
    let totalCost = 0;

    recipeItems.forEach((item) => {
      const ingredient = ingredients.find((i) => i.id === item.ingredient_id);
      if (ingredient) {
        const wasteFactor = item.waste_factor || 0;
        const adjustedQty = item.quantity * (1 + wasteFactor / 100);
        const itemCost = adjustedQty * ingredient.cost_per_unit;
        totalCost += itemCost;
      }
    });

    const costPerServing = yieldServings > 0 ? totalCost / yieldServings : 0;
    const foodCostPct =
      selectedMenuItem && selectedMenuItem.price > 0
        ? (costPerServing / selectedMenuItem.price) * 100
        : 0;

    return { totalCost, costPerServing, foodCostPct };
  }, [recipeItems, ingredients, yieldServings, selectedMenuItem]);

  const { totalCost, costPerServing, foodCostPct } = calculateCosts();

  // Check if recipe items changed (for versioning)
  const hasItemsChanged = useCallback(() => {
    if (!recipe || !recipe.recipe_items) return true;

    // Compare arrays
    if (recipeItems.length !== recipe.recipe_items.length) return true;

    // Compare each item
    return recipeItems.some((newItem) => {
      const oldItem = recipe.recipe_items.find(
        (old) => old.ingredient_id === newItem.ingredient_id
      );
      if (!oldItem) return true;

      return (
        oldItem.quantity !== newItem.quantity ||
        oldItem.unit !== newItem.unit ||
        oldItem.waste_factor !== (newItem.waste_factor || 0)
      );
    });
  }, [recipe, recipeItems]);

  // Add ingredient to recipe
  function handleAddIngredient() {
    if (!newIngredientId || !newQuantity) {
      toast({
        variant: "destructive",
        title: "Ingredient and quantity are required",
      });
      return;
    }

    // Check if already added
    if (recipeItems.some((item) => item.ingredient_id === newIngredientId)) {
      toast({
        variant: "destructive",
        title: "Ingredient already added to recipe",
      });
      return;
    }

    const ingredient = ingredients.find((i) => i.id === newIngredientId);
    if (!ingredient) return;

    setRecipeItems([
      ...recipeItems,
      {
        ingredient_id: newIngredientId,
        quantity: parseFloat(newQuantity),
        unit: ingredient.unit, // Copy unit from ingredient
        waste_factor: newWaste ? parseFloat(newWaste) : 0,
      },
    ]);

    // Reset form
    setNewIngredientId("");
    setNewQuantity("");
    setNewWaste("");
    setAddIngredientOpen(false);
  }

  // Remove ingredient from recipe
  function handleRemoveIngredient(ingredientId: string) {
    setRecipeItems(recipeItems.filter((item) => item.ingredient_id !== ingredientId));
  }

  // Update ingredient quantity/waste in recipe
  function handleUpdateRecipeItem(
    ingredientId: string,
    field: "quantity" | "waste_factor",
    value: number
  ) {
    setRecipeItems(
      recipeItems.map((item) =>
        item.ingredient_id === ingredientId ? { ...item, [field]: value } : item
      )
    );
  }

  // Save recipe
  async function handleSave() {
    if (!selectedMenuItem) return;

    if (recipeItems.length === 0) {
      toast({
        variant: "destructive",
        title: "Add at least one ingredient to the recipe",
      });
      return;
    }

    if (yieldServings <= 0) {
      toast({
        variant: "destructive",
        title: "Yield servings must be greater than 0",
      });
      return;
    }

    setSaving(true);
    try {
      const payload: any = {
        menu_item_id: selectedMenuItem.id,
        yield_servings: yieldServings,
        prep_time_minutes: prepTime || null,
        cook_time_minutes: cookTime || null,
        instructions: instructions.trim() || null,
        notes: notes.trim() || null,
      };

      if (recipe) {
        // Existing recipe - check if items changed
        const itemsChanged = hasItemsChanged();

        if (itemsChanged) {
          // Create new version
          payload.recipe_items = recipeItems;
          const updated = await inventoryApi.updateRecipe(recipe.id, payload);
          toast({
            variant: "success",
            title: `Recipe updated (Version ${updated.version})`,
          });
        } else {
          // Update metadata only (no new version)
          const updated = await inventoryApi.updateRecipe(recipe.id, payload);
          toast({
            variant: "success",
            title: "Recipe metadata updated",
          });
        }

        // Reload recipe
        await loadRecipe(selectedMenuItem);
      } else {
        // New recipe
        payload.recipe_items = recipeItems;
        await inventoryApi.createRecipe(payload);

        toast({
          variant: "success",
          title: "Recipe created (Version 1)",
        });

        // Reload recipe
        await loadRecipe(selectedMenuItem);
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Failed to save recipe";
      toast({
        variant: "destructive",
        title: msg,
      });
    } finally {
      setSaving(false);
    }
  }

  // Delete recipe
  async function handleDelete() {
    if (!recipe) return;

    try {
      await inventoryApi.deleteRecipe(recipe.id);

      toast({
        variant: "success",
        title: "Recipe deleted",
      });

      setDeleteConfirmOpen(false);

      // Reset editor
      setRecipe(null);
      setRecipeItems([]);
      setYieldServings(1);
      setPrepTime(null);
      setCookTime(null);
      setInstructions("");
      setNotes("");
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Failed to delete recipe";
      toast({
        variant: "destructive",
        title: msg,
      });
    }
  }

  // Get food cost color class
  function getFoodCostColorClass(pct: number) {
    if (pct < 25) return "text-green-600 bg-green-50";
    if (pct < 35) return "text-yellow-600 bg-yellow-50";
    return "text-red-600 bg-red-50";
  }

  // Get menu item badge
  function getMenuItemBadge(menuItem: MenuItem) {
    // Check if recipe exists (would need to fetch all recipes or add to menu item)
    // For now, simplified version
    return null;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <ChefHat className="h-7 w-7 text-primary-600" />
        <h1 className="text-pos-2xl font-bold text-secondary-900">
          Recipe Builder
        </h1>
      </div>

      {/* Two-panel layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* LEFT PANEL: Menu Items List */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-pos-lg">Menu Items</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Category filter */}
            <Select value={categoryFilter} onValueChange={setCategoryFilter}>
              <SelectTrigger className="min-h-[48px]">
                <SelectValue placeholder="All Categories" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All Categories</SelectItem>
                {categories.map((cat) => (
                  <SelectItem key={cat.id} value={cat.id}>
                    {cat.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Menu items list */}
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-primary-600" />
              </div>
            ) : menuItems.length === 0 ? (
              <div className="py-8 text-center text-pos-sm text-secondary-500">
                No menu items found.
              </div>
            ) : (
              <div className="space-y-2">
                {menuItems.map((item) => {
                  const isSelected = selectedMenuItem?.id === item.id;

                  return (
                    <button
                      key={item.id}
                      onClick={() => loadRecipe(item)}
                      className={`w-full rounded-lg border p-3 text-left transition-colors ${
                        isSelected
                          ? "border-primary-500 bg-primary-50"
                          : "border-secondary-200 hover:bg-secondary-50"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="text-pos-sm font-medium text-secondary-900">
                            {item.name}
                          </div>
                          <div className="text-pos-xs text-secondary-500">
                            {formatPKR(item.price)}
                          </div>
                        </div>
                        {getMenuItemBadge(item)}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* RIGHT PANEL: Recipe Editor */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-pos-lg">Recipe Editor</CardTitle>
          </CardHeader>
          <CardContent>
            {!selectedMenuItem ? (
              <div className="py-12 text-center text-secondary-500">
                Select a menu item to create or edit its recipe.
              </div>
            ) : recipeLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
              </div>
            ) : (
              <div className="space-y-6">
                {/* Header: Menu Item Info */}
                <div className="rounded-lg border border-secondary-200 bg-secondary-50 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-pos-base font-semibold text-secondary-900">
                        {selectedMenuItem.name}
                      </div>
                      <div className="text-pos-sm text-secondary-600">
                        Price: {formatPKR(selectedMenuItem.price)}
                      </div>
                    </div>
                    {recipe && (
                      <Badge variant="secondary" className="text-pos-xs">
                        Version {recipe.version}
                      </Badge>
                    )}
                  </div>
                </div>

                {/* Metadata fields */}
                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="yield">Yield Servings *</Label>
                    <Input
                      id="yield"
                      type="number"
                      min="1"
                      step="1"
                      value={yieldServings}
                      onChange={(e) =>
                        setYieldServings(parseInt(e.target.value) || 1)
                      }
                      className="min-h-[48px]"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="prep">Prep Time (min)</Label>
                    <Input
                      id="prep"
                      type="number"
                      min="0"
                      step="1"
                      value={prepTime || ""}
                      onChange={(e) =>
                        setPrepTime(
                          e.target.value ? parseInt(e.target.value) : null
                        )
                      }
                      placeholder="Optional"
                      className="min-h-[48px]"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="cook">Cook Time (min)</Label>
                    <Input
                      id="cook"
                      type="number"
                      min="0"
                      step="1"
                      value={cookTime || ""}
                      onChange={(e) =>
                        setCookTime(
                          e.target.value ? parseInt(e.target.value) : null
                        )
                      }
                      placeholder="Optional"
                      className="min-h-[48px]"
                    />
                  </div>
                </div>

                {/* Ingredients table */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Label className="text-pos-base">Ingredients</Label>
                    <Button
                      size="sm"
                      onClick={() => setAddIngredientOpen(true)}
                      className="min-h-[40px] gap-2"
                    >
                      <Plus className="h-4 w-4" />
                      Add Ingredient
                    </Button>
                  </div>

                  {recipeItems.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-secondary-300 bg-secondary-50 py-8 text-center text-pos-sm text-secondary-500">
                      No ingredients added yet. Click "Add Ingredient" to start.
                    </div>
                  ) : (
                    <div className="overflow-x-auto rounded-lg border border-secondary-200">
                      <table className="w-full text-left text-pos-sm">
                        <thead className="bg-secondary-50">
                          <tr>
                            <th className="p-3 font-medium text-secondary-700">
                              Ingredient
                            </th>
                            <th className="p-3 font-medium text-secondary-700">
                              Quantity
                            </th>
                            <th className="p-3 font-medium text-secondary-700">
                              Unit
                            </th>
                            <th className="p-3 font-medium text-secondary-700">
                              Waste %
                            </th>
                            <th className="p-3 font-medium text-right text-secondary-700">
                              Item Cost
                            </th>
                            <th className="p-3 font-medium text-secondary-700"></th>
                          </tr>
                        </thead>
                        <tbody>
                          {recipeItems.map((item) => {
                            const ingredient = ingredients.find(
                              (i) => i.id === item.ingredient_id
                            );
                            if (!ingredient) return null;

                            const wasteFactor = item.waste_factor || 0;
                            const adjustedQty =
                              item.quantity * (1 + wasteFactor / 100);
                            const itemCost =
                              adjustedQty * ingredient.cost_per_unit;

                            return (
                              <tr
                                key={item.ingredient_id}
                                className="border-t border-secondary-200"
                              >
                                <td className="p-3 font-medium text-secondary-900">
                                  {ingredient.name}
                                </td>
                                <td className="p-3">
                                  <Input
                                    type="number"
                                    min="0"
                                    step="0.01"
                                    value={item.quantity}
                                    onChange={(e) =>
                                      handleUpdateRecipeItem(
                                        item.ingredient_id,
                                        "quantity",
                                        parseFloat(e.target.value) || 0
                                      )
                                    }
                                    className="w-24 min-h-[40px]"
                                  />
                                </td>
                                <td className="p-3 text-secondary-600">
                                  {item.unit}
                                </td>
                                <td className="p-3">
                                  <Input
                                    type="number"
                                    min="0"
                                    max="100"
                                    step="0.1"
                                    value={item.waste_factor || 0}
                                    onChange={(e) =>
                                      handleUpdateRecipeItem(
                                        item.ingredient_id,
                                        "waste_factor",
                                        parseFloat(e.target.value) || 0
                                      )
                                    }
                                    className="w-20 min-h-[40px]"
                                  />
                                </td>
                                <td className="p-3 text-right text-secondary-900">
                                  {formatPKR(itemCost)}
                                </td>
                                <td className="p-3">
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() =>
                                      handleRemoveIngredient(item.ingredient_id)
                                    }
                                    className="min-h-[40px] text-danger-600 hover:text-danger-700"
                                  >
                                    <X className="h-4 w-4" />
                                  </Button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                {/* Cost Summary */}
                {recipeItems.length > 0 && (
                  <Card className="border-2 border-primary-200 bg-primary-50/50">
                    <CardContent className="pt-6">
                      <div className="space-y-3">
                        <div className="flex items-center justify-between text-pos-sm">
                          <span className="text-secondary-700">
                            Total Ingredient Cost:
                          </span>
                          <span className="font-semibold text-secondary-900">
                            {formatPKR(totalCost)}
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-pos-sm">
                          <span className="text-secondary-700">
                            Cost per Serving (÷ {yieldServings}):
                          </span>
                          <span className="font-semibold text-secondary-900">
                            {formatPKR(costPerServing)}
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-pos-sm">
                          <span className="text-secondary-700">
                            Menu Item Price:
                          </span>
                          <span className="font-semibold text-secondary-900">
                            {formatPKR(selectedMenuItem.price)}
                          </span>
                        </div>
                        <div className="border-t border-primary-200 pt-3">
                          <div className="flex items-center justify-between">
                            <span className="text-pos-base font-semibold text-secondary-900">
                              Food Cost %:
                            </span>
                            <Badge
                              className={`text-pos-base font-bold ${getFoodCostColorClass(
                                foodCostPct
                              )}`}
                            >
                              {foodCostPct.toFixed(2)}%
                            </Badge>
                          </div>
                          <div className="mt-2 text-pos-xs text-secondary-600">
                            {foodCostPct < 25 && (
                              <span className="flex items-center gap-1 text-green-600">
                                <CheckCircle className="h-3 w-3" />
                                Excellent - within target (&lt;25%)
                              </span>
                            )}
                            {foodCostPct >= 25 && foodCostPct < 35 && (
                              <span className="flex items-center gap-1 text-yellow-600">
                                <AlertCircle className="h-3 w-3" />
                                Acceptable - monitor closely (25-35%)
                              </span>
                            )}
                            {foodCostPct >= 35 && (
                              <span className="flex items-center gap-1 text-red-600">
                                <AlertTriangle className="h-3 w-3" />
                                High - consider price adjustment (&gt;35%)
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Instructions & Notes */}
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="instructions">Cooking Instructions</Label>
                    <Textarea
                      id="instructions"
                      value={instructions}
                      onChange={(e) => setInstructions(e.target.value)}
                      placeholder="Step-by-step instructions..."
                      rows={4}
                      className="resize-none"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="notes">Notes</Label>
                    <Textarea
                      id="notes"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      placeholder="Additional notes, tips, etc."
                      rows={4}
                      className="resize-none"
                    />
                  </div>
                </div>

                {/* Action buttons */}
                <div className="flex items-center justify-between border-t border-secondary-200 pt-6">
                  <div>
                    {recipe && (
                      <Button
                        variant="destructive"
                        onClick={() => setDeleteConfirmOpen(true)}
                        className="min-h-[48px] gap-2"
                      >
                        <Trash2 className="h-4 w-4" />
                        Delete Recipe
                      </Button>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <Button
                      variant="outline"
                      onClick={() => loadRecipe(selectedMenuItem)}
                      className="min-h-[48px]"
                    >
                      Discard Changes
                    </Button>
                    <Button
                      onClick={handleSave}
                      disabled={
                        recipeItems.length === 0 || yieldServings <= 0 || saving
                      }
                      className="min-h-[48px] gap-2"
                    >
                      {saving && <Loader2 className="h-4 w-4 animate-spin" />}
                      <Save className="h-4 w-4" />
                      {recipe ? "Update Recipe" : "Create Recipe"}
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Add Ingredient Dialog */}
      <Dialog open={addIngredientOpen} onOpenChange={setAddIngredientOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Ingredient to Recipe</DialogTitle>
            <DialogDescription>
              Select an ingredient and specify the quantity needed.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Ingredient dropdown */}
            <div className="space-y-2">
              <Label htmlFor="ingredient">Ingredient *</Label>
              <Select value={newIngredientId} onValueChange={setNewIngredientId}>
                <SelectTrigger id="ingredient" className="min-h-[48px]">
                  <SelectValue placeholder="Select ingredient..." />
                </SelectTrigger>
                <SelectContent>
                  {ingredients
                    .filter(
                      (ing) =>
                        !recipeItems.some(
                          (item) => item.ingredient_id === ing.id
                        )
                    )
                    .map((ing) => (
                      <SelectItem key={ing.id} value={ing.id}>
                        {ing.name} ({ing.unit}) - {formatPKR(ing.cost_per_unit)}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>

            {/* Quantity */}
            <div className="space-y-2">
              <Label htmlFor="quantity">Quantity *</Label>
              <Input
                id="quantity"
                type="number"
                min="0"
                step="0.01"
                value={newQuantity}
                onChange={(e) => setNewQuantity(e.target.value)}
                placeholder="e.g., 2.5"
                className="min-h-[48px]"
              />
            </div>

            {/* Waste factor */}
            <div className="space-y-2">
              <Label htmlFor="waste">Waste Factor (%)</Label>
              <Input
                id="waste"
                type="number"
                min="0"
                max="100"
                step="0.1"
                value={newWaste}
                onChange={(e) => setNewWaste(e.target.value)}
                placeholder="e.g., 5 (optional)"
                className="min-h-[48px]"
              />
              <p className="text-pos-xs text-secondary-500">
                Accounts for trimming, peeling, spillage, etc.
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setAddIngredientOpen(false)}
              className="min-h-touch"
            >
              Cancel
            </Button>
            <Button
              onClick={handleAddIngredient}
              disabled={!newIngredientId || !newQuantity}
              className="min-h-touch"
            >
              Add to Recipe
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Recipe</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this recipe? This action will
              deactivate the recipe (soft delete).
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteConfirmOpen(false)}
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
