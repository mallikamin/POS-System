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
  /** The STOCKING unit: what recipes spend and stock on hand counts. "g", "kg", "L". */
  unit: string;
  /**
   * Minor units per one STOCKING unit. Read-only on screen whenever
   * `purchase_unit` is set: the server derives it and ignores what is sent.
   */
  cost_per_unit: number;
  /**
   * Martin (FZ LLC, 2026-09-04, M8): "2 units and a conversion. The unit you
   * buy, the unit you store) use in recipes". What the supplier sells, e.g.
   * "can". Null means bought in the unit it is stocked in, which is every
   * ingredient that existed before this and stays the simple case on screen.
   */
  purchase_unit: string | null;
  /** Stocking units in one purchase unit, e.g. 400 g per can. 1 when there is no conversion. */
  units_per_purchase_unit: number;
  /** Minor units per PURCHASE unit, e.g. 850 = 8.50 AED a can. The price actually typed. */
  purchase_cost_minor: number;
  supplier_name: string | null;
  supplier_contact: string | null;
  reorder_point: number;
  reorder_quantity: number;
  current_stock: number;
  is_active: boolean;
  notes: string | null;
  /**
   * True when this ingredient is MADE in-house by a recipe rather than bought.
   * The API has returned it since the sub-recipe work landed; it was missing
   * from this type, so every screen was blind to the distinction. It matters:
   * a produced ingredient cannot be put on a purchase order, and its
   * `cost_per_unit` is a rollup owned by the recipe engine, not a price
   * anybody pays.
   */
  is_produced: boolean;
  /**
   * The active recipe that makes a produced ingredient, when one exists.
   * Null on a produced ingredient means "no recipe yet", which the
   * Ingredients screen signposts rather than hides.
   */
  production_recipe_id: string | null;
  production_recipe_name: string | null;
  /** Photograph, uploaded via /media/images. Follows the ingredient onto every screen that names it. */
  image_url: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface IngredientCreate {
  name: string;
  category?: string;
  /** The stocking unit. Recipes are written in this. */
  unit: string;
  /** Ignored by the server when `purchase_unit` is set. Send the can price instead. */
  cost_per_unit?: number; // paisa
  /** M8: what the supplier sells. Omit for an ingredient bought in its stocking unit. */
  purchase_unit?: string | null;
  units_per_purchase_unit?: number;
  purchase_cost_minor?: number;
  supplier_name?: string | null;
  supplier_contact?: string | null;
  reorder_point?: number;
  reorder_quantity?: number;
  is_active?: boolean;
  /** Made in-house from a recipe. The cost is then calculated, never typed. */
  is_produced?: boolean;
  notes?: string | null;
  image_url?: string | null;
}

export interface IngredientUpdate {
  name?: string;
  category?: string;
  unit?: string;
  cost_per_unit?: number; // paisa
  purchase_unit?: string | null;
  units_per_purchase_unit?: number;
  purchase_cost_minor?: number;
  supplier_name?: string | null;
  supplier_contact?: string | null;
  reorder_point?: number;
  reorder_quantity?: number;
  is_active?: boolean;
  is_produced?: boolean;
  notes?: string | null;
  image_url?: string | null;
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
  /**
   * A recipe is attached to exactly one of three targets, never two and never
   * none (the database enforces it):
   *
   *  - a sellable menu item;
   *  - an ingredient it produces, which makes it a sub-recipe (dough, a sauce,
   *    a stuffing) that other recipes then consume, and is what makes
   *    multi-layer production chains possible;
   *  - a modifier, meaning a paid add-on chosen at the till, which is consumed
   *    and costed on top of the line it is added to.
   */
  menu_item_id: string | null;
  produces_ingredient_id: string | null;
  produces_ingredient_name: string | null;
  modifier_id: string | null;
  modifier_name: string | null;
  modifier_group_name: string | null;
  modifier_price: number | null; // minor units, the add-on's price adjustment
  menu_item_name: string | null; // Denormalized for display
  menu_item_price: number | null; // minor units, as on the menu board
  // Menu price with the tenant's tax backed out when prices are tax-inclusive
  // (F13). This is the divisor of food_cost_percentage.
  menu_item_net_price: number | null;
  yield_servings: number;
  prep_time_minutes: number | null;
  cook_time_minutes: number | null;
  instructions: string | null;
  notes: string | null;
  version: number; // Recipe versioning (1, 2, 3...)
  total_ingredient_cost: number; // paisa (sum of all recipe_items.total_cost)
  cost_per_serving: number; // paisa (total_cost / yield_servings)
  food_cost_percentage: number | null; // 0-100 (cost_per_serving / menu_item_net_price * 100)
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
