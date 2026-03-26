/**
 * BOM & Inventory API Service Layer
 * All API calls for ingredients, recipes, and cost simulation
 */

import api from "@/lib/axios";
import type {
  Ingredient,
  IngredientCreate,
  IngredientUpdate,
  Recipe,
  RecipeCreate,
  RecipeUpdate,
  RecipeCostSimulationRequest,
  RecipeCostSimulationResult,
} from "@/types/inventory";

// ==========================================================================
// INGREDIENT API
// ==========================================================================

export async function fetchIngredients(params?: {
  category?: string;
  is_active?: boolean;
  skip?: number;
  limit?: number;
}): Promise<Ingredient[]> {
  const { data } = await api.get<Ingredient[]>("/inventory/ingredients", {
    params,
  });
  return data;
}

export async function getIngredient(id: string): Promise<Ingredient> {
  const { data } = await api.get<Ingredient>(`/inventory/ingredients/${id}`);
  return data;
}

export async function createIngredient(
  body: IngredientCreate
): Promise<Ingredient> {
  const { data } = await api.post<Ingredient>("/inventory/ingredients", body);
  return data;
}

export async function updateIngredient(
  id: string,
  body: IngredientUpdate
): Promise<Ingredient> {
  const { data } = await api.patch<Ingredient>(
    `/inventory/ingredients/${id}`,
    body
  );
  return data;
}

export async function deleteIngredient(id: string): Promise<void> {
  await api.delete(`/inventory/ingredients/${id}`);
}

// ==========================================================================
// RECIPE API
// ==========================================================================

export async function fetchRecipes(params?: {
  is_active?: boolean;
  skip?: number;
  limit?: number;
}): Promise<Recipe[]> {
  const { data } = await api.get<Recipe[]>("/inventory/recipes", { params });
  return data;
}

export async function getRecipe(id: string): Promise<Recipe> {
  const { data } = await api.get<Recipe>(`/inventory/recipes/${id}`);
  return data;
}

export async function getRecipeByMenuItem(
  menuItemId: string
): Promise<Recipe | null> {
  try {
    const { data } = await api.get<Recipe>(
      `/inventory/recipes/by-menu-item/${menuItemId}`
    );
    return data;
  } catch (err: any) {
    // 404 = no recipe exists for this menu item
    if (err.response?.status === 404) {
      return null;
    }
    throw err;
  }
}

export async function createRecipe(body: RecipeCreate): Promise<Recipe> {
  const { data } = await api.post<Recipe>("/inventory/recipes", body);
  return data;
}

export async function updateRecipe(
  id: string,
  body: RecipeUpdate
): Promise<Recipe> {
  const { data } = await api.patch<Recipe>(`/inventory/recipes/${id}`, body);
  return data;
}

export async function deleteRecipe(id: string): Promise<void> {
  await api.delete(`/inventory/recipes/${id}`);
}

// ==========================================================================
// COST SIMULATION API
// ==========================================================================

export async function simulateRecipeCost(
  recipeId: string,
  priceChanges: Record<string, number>
): Promise<RecipeCostSimulationResult> {
  const body: RecipeCostSimulationRequest = {
    ingredient_price_changes: priceChanges,
  };

  const { data } = await api.post<RecipeCostSimulationResult>(
    `/inventory/recipes/${recipeId}/simulate-cost`,
    body
  );

  return data;
}
