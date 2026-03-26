/**
 * BOM & Inventory TypeScript types
 * Matches backend schemas/inventory.py
 * All monetary values in paisa (100 paisa = 1 PKR)
 */

// ==========================================================================
// INGREDIENT TYPES
// ==========================================================================

export interface Ingredient {
  id: string;
  tenant_id: string;
  name: string;
  category: string; // e.g., "Meat", "Grains", "Spices"
  unit: string; // e.g., "kg", "L", "pieces"
  cost_per_unit: number; // paisa
  supplier_name: string | null;
  supplier_contact: string | null;
  reorder_point: number;
  reorder_quantity: number;
  current_stock: number;
  is_active: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface IngredientCreate {
  name: string;
  category?: string;
  unit: string;
  cost_per_unit?: number; // paisa
  supplier_name?: string | null;
  supplier_contact?: string | null;
  reorder_point?: number;
  reorder_quantity?: number;
  is_active?: boolean;
  notes?: string | null;
}

export interface IngredientUpdate {
  name?: string;
  category?: string;
  unit?: string;
  cost_per_unit?: number; // paisa
  supplier_name?: string | null;
  supplier_contact?: string | null;
  reorder_point?: number;
  reorder_quantity?: number;
  is_active?: boolean;
  notes?: string | null;
}

// ==========================================================================
// RECIPE ITEM TYPES (sub-entity for recipes)
// ==========================================================================

export interface RecipeItem {
  id: string;
  recipe_id: string;
  ingredient_id: string;
  ingredient_name: string | null; // Populated from join
  quantity: number;
  unit: string;
  waste_factor: number; // 0-100 percentage
  cost_per_unit_snapshot: number; // paisa (historical cost)
  total_cost: number; // paisa (quantity × cost × (1 + waste_factor/100))
  notes: string | null;
}

export interface RecipeItemCreate {
  ingredient_id: string;
  quantity: number;
  unit: string;
  waste_factor?: number; // 0-100
  notes?: string | null;
}

export interface RecipeItemUpdate {
  quantity?: number;
  unit?: string;
  waste_factor?: number;
  notes?: string | null;
}

// ==========================================================================
// RECIPE TYPES (Bill of Materials)
// ==========================================================================

export interface Recipe {
  id: string;
  tenant_id: string;
  menu_item_id: string;
  menu_item_name: string | null; // Denormalized for display
  menu_item_price: number | null; // paisa (denormalized)
  yield_servings: number;
  prep_time_minutes: number | null;
  cook_time_minutes: number | null;
  instructions: string | null;
  notes: string | null;
  version: number; // Recipe versioning (1, 2, 3...)
  total_ingredient_cost: number; // paisa (sum of all recipe_items.total_cost)
  cost_per_serving: number; // paisa (total_cost / yield_servings)
  food_cost_percentage: number | null; // 0-100 (cost_per_serving / menu_price * 100)
  is_active: boolean; // Only one active recipe per menu item
  effective_date: string; // ISO date when this version became active
  created_by: string | null; // User ID
  created_at: string;
  updated_at: string | null;
  recipe_items: RecipeItem[];
}

export interface RecipeCreate {
  menu_item_id: string;
  yield_servings?: number;
  prep_time_minutes?: number | null;
  cook_time_minutes?: number | null;
  instructions?: string | null;
  notes?: string | null;
  recipe_items?: RecipeItemCreate[];
}

export interface RecipeUpdate {
  yield_servings?: number;
  prep_time_minutes?: number | null;
  cook_time_minutes?: number | null;
  instructions?: string | null;
  notes?: string | null;
  recipe_items?: RecipeItemCreate[]; // Full replacement → creates new version if provided
}

// ==========================================================================
// COST SIMULATION TYPES
// ==========================================================================

export interface RecipeCostSimulationRequest {
  ingredient_price_changes: Record<string, number>; // ingredient_id → new cost_per_unit (paisa)
}

export interface RecipeCostSimulationResult {
  current_total_cost: number; // paisa
  new_total_cost: number; // paisa
  cost_increase: number; // paisa (can be negative if costs decrease)
  cost_increase_percentage: number; // % change
  current_cost_per_serving: number; // paisa
  new_cost_per_serving: number; // paisa
  current_food_cost_percentage: number | null; // 0-100
  new_food_cost_percentage: number | null; // 0-100
  affected_items: Array<{
    ingredient_id: string;
    ingredient_name: string;
    old_cost: number; // paisa
    new_cost: number; // paisa
    quantity: number;
    cost_impact: number; // paisa (difference in item total cost)
  }>;
}

// ==========================================================================
// UTILITY TYPES
// ==========================================================================

/**
 * Ingredient with low stock indicator
 */
export interface IngredientWithStockStatus extends Ingredient {
  is_low_stock: boolean; // current_stock < reorder_point
}

/**
 * Recipe with status badge info
 */
export interface RecipeWithStatus extends Recipe {
  food_cost_status: "good" | "warning" | "high"; // <25%, 25-35%, >35%
}
