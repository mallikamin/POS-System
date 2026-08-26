/**
 * Recipe Builder Page
 * Two-panel interface: target list (menu items or ingredients) -> Recipe Editor
 *
 * A recipe produces EITHER a sellable menu item OR an ingredient. The second
 * kind is a sub-recipe: dough, a sauce, a stuffing, which other recipes then
 * consume as an ordinary ingredient line. That is what makes multi-layer
 * production chains work (raw -> sub-recipe -> intermediate -> final item).
 * Auto-calculates food cost % with real-time updates.
 */

import { useCallback, useEffect, useState } from "react";
import {
  ChefHat,
  Layers,
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
import { Select } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";

import type { MenuItem, Category } from "@/types/menu";
import type {
  Ingredient,
  Recipe,
  RecipeCreate,
  RecipeItemCreate,
} from "@/types/inventory";
import * as menuApi from "@/services/menuApi";
import * as inventoryApi from "@/services/inventoryApi";
import { formatPKR } from "@/utils/currency";

type TargetMode = "menu_item" | "sub_recipe";

/**
 * The backend 422s on both targets or neither (a DB CHECK constraint plus a
 * Pydantic validator), so the two keys are modelled as a union rather than two
 * loose optional fields that could both be filled in by mistake.
 */
type RecipeTarget =
  | { menu_item_id: string; produces_ingredient_id?: never }
  | { produces_ingredient_id: string; menu_item_id?: never };

type RecipeSavePayload = RecipeTarget & {
  yield_servings?: number;
  prep_time_minutes?: number | null;
  cook_time_minutes?: number | null;
  instructions?: string | null;
  notes?: string | null;
  recipe_items?: RecipeItemCreate[];
};

/**
 * IngredientResponse carries is_produced, but the shared Ingredient type has
 * not caught up and widening it here would touch a type other pages depend on.
 */
function isProducedIngredient(ingredient: Ingredient): boolean {
  return Reflect.get(ingredient, "is_produced") === true;
}

export default function RecipeBuilderPage() {
  const { toast } = useToast();

  // What this recipe produces: a sellable menu item, or an ingredient
  const [targetMode, setTargetMode] = useState<TargetMode>("menu_item");
  const isSubRecipe = targetMode === "sub_recipe";

  // Menu items + categories
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [loading, setLoading] = useState(true);

  // Ingredients (dropdown + sub-recipe target list)
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [ingredientsLoading, setIngredientsLoading] = useState(true);
  const [ingredientFilter, setIngredientFilter] = useState("");

  // Active recipes: labels which targets already have one, and is how a
  // sub-recipe is looked up (there is no by-ingredient endpoint)
  const [activeRecipes, setActiveRecipes] = useState<Recipe[]>([]);

  // Selected target + recipe (exactly one of the two selections is ever set)
  const [selectedMenuItem, setSelectedMenuItem] = useState<MenuItem | null>(
    null
  );
  const [selectedIngredientTarget, setSelectedIngredientTarget] =
    useState<Ingredient | null>(null);
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
  const [addIngredientError, setAddIngredientError] = useState("");

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

  // Fetch ingredients (dropdown + sub-recipe target list)
  const fetchIngredients = useCallback(async () => {
    setIngredientsLoading(true);
    try {
      const data = await inventoryApi.fetchIngredients({ is_active: true });
      setIngredients(data);
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Failed to load ingredients",
      });
    } finally {
      setIngredientsLoading(false);
    }
  }, [toast]);

  // Fetch active recipes (target badges + sub-recipe lookup)
  const fetchActiveRecipes = useCallback(async (): Promise<Recipe[]> => {
    try {
      const data = await inventoryApi.fetchRecipes({
        is_active: true,
        limit: 500,
      });
      setActiveRecipes(data);
      return data;
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Failed to load recipes",
      });
      return [];
    }
  }, [toast]);

  useEffect(() => {
    fetchMenuData();
    fetchIngredients();
    fetchActiveRecipes();
  }, [fetchMenuData, fetchIngredients, fetchActiveRecipes]);

  // Fill the editor from a saved recipe
  const applyRecipeToEditor = useCallback((recipeData: Recipe) => {
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
  }, []);

  const resetEditor = useCallback(() => {
    setRecipe(null);
    setYieldServings(1);
    setPrepTime(null);
    setCookTime(null);
    setInstructions("");
    setNotes("");
    setRecipeItems([]);
  }, []);

  // Load recipe when menu item is selected
  const loadRecipe = useCallback(
    async (menuItem: MenuItem) => {
      setSelectedIngredientTarget(null);
      setSelectedMenuItem(menuItem);
      setRecipeLoading(true);

      try {
        const recipeData = await inventoryApi.getRecipeByMenuItem(menuItem.id);

        if (recipeData) {
          applyRecipeToEditor(recipeData);
        } else {
          resetEditor();
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
    [toast, applyRecipeToEditor, resetEditor]
  );

  // Load the sub-recipe that produces the selected ingredient.
  // getRecipeByMenuItem cannot serve this: a sub-recipe has no menu_item_id,
  // so the active recipe is found in the list by produces_ingredient_id.
  const loadRecipeForIngredient = useCallback(
    async (ingredient: Ingredient) => {
      setSelectedMenuItem(null);
      setSelectedIngredientTarget(ingredient);
      setRecipeLoading(true);

      try {
        const recipes = await inventoryApi.fetchRecipes({
          is_active: true,
          limit: 500,
        });
        setActiveRecipes(recipes);

        const recipeData = recipes.find(
          (r) => r.produces_ingredient_id === ingredient.id
        );

        if (recipeData) {
          applyRecipeToEditor(recipeData);
        } else {
          resetEditor();
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
    [toast, applyRecipeToEditor, resetEditor]
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

  const hasTarget = selectedMenuItem !== null || selectedIngredientTarget !== null;

  // Yield is servings for a menu item, but a quantity in the produced
  // ingredient's own unit for a sub-recipe (5 meaning 5 kg of dough)
  const producedUnit = selectedIngredientTarget?.unit ?? "unit";

  // Dough cannot be made from dough. A sub-recipe that lists its own output as
  // an input would loop forever when costs are rolled up.
  const selfReferencingItem =
    selectedIngredientTarget !== null &&
    recipeItems.some(
      (item) => item.ingredient_id === selectedIngredientTarget.id
    );

  const ingredientCategories = Array.from(
    new Set(ingredients.map((ing) => ing.category).filter((c) => c.length > 0))
  ).sort();

  // Produced ingredients first, because they are the usual sub-recipe target,
  // but any ingredient stays pickable: creating its recipe is exactly what
  // marks it as produced.
  const ingredientTargets = ingredients
    .filter((ing) => !ingredientFilter || ing.category === ingredientFilter)
    .sort((a, b) => {
      const aRank = isProducedIngredient(a) ? 0 : 1;
      const bRank = isProducedIngredient(b) ? 0 : 1;
      if (aRank !== bRank) return aRank - bRank;
      return a.name.localeCompare(b.name);
    });

  // Switch between the two recipe targets
  function handleModeChange(mode: TargetMode) {
    if (mode === targetMode) return;

    // The modes select from different lists, so no selection can carry over
    setTargetMode(mode);
    setSelectedMenuItem(null);
    setSelectedIngredientTarget(null);
    resetEditor();
  }

  // Reload whichever target is currently selected
  function handleReloadTarget() {
    if (selectedIngredientTarget) {
      loadRecipeForIngredient(selectedIngredientTarget);
    } else if (selectedMenuItem) {
      loadRecipe(selectedMenuItem);
    }
  }

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

    // A sub-recipe cannot consume the ingredient it produces
    if (
      selectedIngredientTarget &&
      newIngredientId === selectedIngredientTarget.id
    ) {
      setAddIngredientError(
        `${selectedIngredientTarget.name} is what this sub-recipe produces, so it cannot also be one of its inputs.`
      );
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
    setAddIngredientError("");
    setAddIngredientOpen(false);
  }

  // Clear the inline error whenever the dialog opens or closes
  function handleAddIngredientOpenChange(open: boolean) {
    setAddIngredientError("");
    setAddIngredientOpen(open);
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
    if (!hasTarget) return;

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
        title: isSubRecipe
          ? "Yield quantity must be greater than 0"
          : "Yield servings must be greater than 0",
      });
      return;
    }

    if (selfReferencingItem && selectedIngredientTarget) {
      toast({
        variant: "destructive",
        title: `Remove ${selectedIngredientTarget.name} from its own inputs before saving`,
      });
      return;
    }

    // Sending recipe_items is what makes the backend cut a new version, so a
    // metadata-only edit deliberately leaves the key off the request
    const itemsChanged = !recipe || hasItemsChanged();
    const base = {
      yield_servings: yieldServings,
      prep_time_minutes: prepTime || null,
      cook_time_minutes: cookTime || null,
      instructions: instructions.trim() || null,
      notes: notes.trim() || null,
      recipe_items: itemsChanged ? recipeItems : undefined,
    };

    // Exactly one target key, never both, never neither: the other combination
    // is a 422 from the backend validator
    let payload: RecipeSavePayload;
    if (selectedIngredientTarget) {
      payload = {
        produces_ingredient_id: selectedIngredientTarget.id,
        ...base,
      };
    } else if (selectedMenuItem) {
      payload = { menu_item_id: selectedMenuItem.id, ...base };
    } else {
      return;
    }

    setSaving(true);
    try {
      if (recipe) {
        await inventoryApi.updateRecipe(recipe.id, payload);
        toast({
          variant: "success",
          title: itemsChanged
            ? "Recipe updated (new version created)"
            : "Recipe metadata updated",
        });
      } else {
        // RecipeCreate in the shared types still models the menu-item-only
        // backend; the sub-recipe payload is widened at this call alone
        await inventoryApi.createRecipe(payload as RecipeCreate);
        toast({
          variant: "success",
          title: "Recipe created (Version 1)",
        });
      }

      // Reload the target and refresh the "has a recipe" badges
      if (selectedIngredientTarget) {
        await loadRecipeForIngredient(selectedIngredientTarget);
      } else if (selectedMenuItem) {
        await loadRecipe(selectedMenuItem);
        await fetchActiveRecipes();
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
      resetEditor();
      await fetchActiveRecipes();
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
    const hasRecipe = activeRecipes.some((r) => r.menu_item_id === menuItem.id);
    if (!hasRecipe) return null;

    return (
      <Badge variant="secondary" className="text-pos-xs">
        Recipe
      </Badge>
    );
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

      {/* Target mode switch: what this recipe produces */}
      <Card>
        <CardContent className="flex flex-col gap-3 pt-6 sm:flex-row sm:items-center">
          <span className="text-pos-sm font-medium text-secondary-700">
            This recipe produces:
          </span>
          <div className="flex flex-wrap gap-2">
            <Button
              variant={isSubRecipe ? "outline" : "default"}
              onClick={() => handleModeChange("menu_item")}
              className="min-h-[48px] gap-2"
            >
              <ChefHat className="h-4 w-4" />
              Menu item recipe
            </Button>
            <Button
              variant={isSubRecipe ? "default" : "outline"}
              onClick={() => handleModeChange("sub_recipe")}
              className="min-h-[48px] gap-2"
            >
              <Layers className="h-4 w-4" />
              Sub-recipe (produces an ingredient)
            </Button>
          </div>
          <p className="text-pos-xs text-secondary-500 sm:ml-auto sm:max-w-xs">
            {isSubRecipe
              ? "An in-house ingredient such as dough, a sauce, or a stuffing, which other recipes then use as an input line."
              : "A sellable item on the menu, priced and ordered by customers."}
          </p>
        </CardContent>
      </Card>

      {/* Two-panel layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* LEFT PANEL: Target list (menu items or ingredients) */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-pos-lg">
              {isSubRecipe ? "Ingredients" : "Menu Items"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Category filter */}
            {isSubRecipe ? (
              <Select
                value={ingredientFilter}
                onChange={(e) => setIngredientFilter(e.target.value)}
                className="min-h-[48px]"
              >
                <option value="">All Ingredient Categories</option>
                {ingredientCategories.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </Select>
            ) : (
              <Select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="min-h-[48px]"
              >
                <option value="">All Categories</option>
                {categories.map((cat) => (
                  <option key={cat.id} value={cat.id}>
                    {cat.name}
                  </option>
                ))}
              </Select>
            )}

            {/* Target list */}
            {isSubRecipe ? (
              ingredientsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-primary-600" />
                </div>
              ) : ingredientTargets.length === 0 ? (
                <div className="py-8 text-center text-pos-sm text-secondary-500">
                  No ingredients found.
                </div>
              ) : (
                <div className="space-y-2">
                  {ingredientTargets.map((ing) => {
                    const isSelected = selectedIngredientTarget?.id === ing.id;
                    const hasSubRecipe = activeRecipes.some(
                      (r) => r.produces_ingredient_id === ing.id
                    );

                    return (
                      <button
                        key={ing.id}
                        onClick={() => loadRecipeForIngredient(ing)}
                        className={`w-full rounded-lg border p-3 text-left transition-colors ${
                          isSelected
                            ? "border-primary-500 bg-primary-50"
                            : "border-secondary-200 hover:bg-secondary-50"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1">
                            <div className="text-pos-sm font-medium text-secondary-900">
                              {ing.name}
                            </div>
                            <div className="text-pos-xs text-secondary-500">
                              {formatPKR(ing.cost_per_unit)} per {ing.unit}
                            </div>
                          </div>
                          {hasSubRecipe ? (
                            <Badge variant="secondary" className="text-pos-xs">
                              Sub-recipe
                            </Badge>
                          ) : isProducedIngredient(ing) ? (
                            <Badge variant="secondary" className="text-pos-xs">
                              Produced
                            </Badge>
                          ) : null}
                        </div>
                      </button>
                    );
                  })}
                </div>
              )
            ) : loading ? (
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
            {!hasTarget ? (
              <div className="py-12 text-center text-secondary-500">
                {isSubRecipe
                  ? "Select an ingredient to create or edit the sub-recipe that produces it."
                  : "Select a menu item to create or edit its recipe."}
              </div>
            ) : recipeLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
              </div>
            ) : (
              <div className="space-y-6">
                {/* Header: Target Info */}
                <div className="rounded-lg border border-secondary-200 bg-secondary-50 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-pos-base font-semibold text-secondary-900">
                        {selectedIngredientTarget
                          ? selectedIngredientTarget.name
                          : selectedMenuItem?.name}
                      </div>
                      <div className="text-pos-sm text-secondary-600">
                        {selectedIngredientTarget
                          ? `Sub-recipe, measured in ${selectedIngredientTarget.unit}`
                          : selectedMenuItem
                            ? `Price: ${formatPKR(selectedMenuItem.price)}`
                            : ""}
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
                    <Label htmlFor="yield">
                      {isSubRecipe
                        ? `Yield Quantity (${producedUnit}) *`
                        : "Yield Servings *"}
                    </Label>
                    <Input
                      id="yield"
                      type="number"
                      min={isSubRecipe ? "0.01" : "1"}
                      step={isSubRecipe ? "0.01" : "1"}
                      value={yieldServings}
                      onChange={(e) =>
                        setYieldServings(
                          (isSubRecipe
                            ? parseFloat(e.target.value)
                            : parseInt(e.target.value)) || 1
                        )
                      }
                      className="min-h-[48px]"
                    />
                    <p className="text-pos-xs text-secondary-500">
                      {isSubRecipe
                        ? `How much one batch makes, in ${producedUnit}. Enter 5 for a batch yielding 5 ${producedUnit}.`
                        : "Servings produced by one batch of this recipe."}
                    </p>
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

                  {selfReferencingItem && selectedIngredientTarget && (
                    <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-pos-sm text-red-700">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                      <span>
                        {selectedIngredientTarget.name} is listed as one of its
                        own inputs. An ingredient cannot be made from itself.
                        Remove that line before saving.
                      </span>
                    </div>
                  )}

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
                            {isSubRecipe
                              ? `Cost per ${producedUnit} (÷ ${yieldServings}):`
                              : `Cost per Serving (÷ ${yieldServings}):`}
                          </span>
                          <span className="font-semibold text-secondary-900">
                            {formatPKR(costPerServing)}
                          </span>
                        </div>

                        {/* Food cost % needs a selling price. A sub-recipe has
                            none, so it reports cost per produced unit instead. */}
                        {selectedIngredientTarget ? (
                          <div className="border-t border-primary-200 pt-3">
                            <div className="flex items-center justify-between">
                              <span className="text-pos-base font-semibold text-secondary-900">
                                Cost per {producedUnit}:
                              </span>
                              <Badge className="bg-primary-100 text-pos-base font-bold text-primary-700">
                                {formatPKR(costPerServing)}
                              </Badge>
                            </div>
                            <div className="mt-2 text-pos-xs text-secondary-600">
                              This is the unit cost that flows into every recipe
                              using {selectedIngredientTarget.name}. A sub-recipe
                              is not sold on its own, so food cost % does not
                              apply here.
                            </div>
                          </div>
                        ) : selectedMenuItem ? (
                          <>
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
                          </>
                        ) : null}
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
                      onClick={handleReloadTarget}
                      className="min-h-[48px]"
                    >
                      Discard Changes
                    </Button>
                    <Button
                      onClick={handleSave}
                      disabled={
                        recipeItems.length === 0 ||
                        yieldServings <= 0 ||
                        selfReferencingItem ||
                        saving
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
      <Dialog
        open={addIngredientOpen}
        onOpenChange={handleAddIngredientOpenChange}
      >
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
              <Select
                id="ingredient"
                value={newIngredientId}
                onChange={(e) => {
                  setAddIngredientError("");
                  setNewIngredientId(e.target.value);
                }}
                className="min-h-[48px]"
              >
                <option value="">Select ingredient...</option>
                {ingredients
                  .filter(
                    (ing) =>
                      !recipeItems.some(
                        (item) => item.ingredient_id === ing.id
                      )
                  )
                  // A sub-recipe cannot consume what it produces
                  .filter((ing) => ing.id !== selectedIngredientTarget?.id)
                  .map((ing) => (
                    <option key={ing.id} value={ing.id}>
                      {ing.name} ({ing.unit}) - {formatPKR(ing.cost_per_unit)}
                    </option>
                  ))}
              </Select>
              {addIngredientError && (
                <p className="flex items-start gap-1 text-pos-xs text-red-600">
                  <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                  {addIngredientError}
                </p>
              )}
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
              onClick={() => handleAddIngredientOpenChange(false)}
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
