/* ==========================================================================
   Menu domain types (matches backend schemas/menu.py)
   All prices are in paisa (100 paisa = 1 PKR)
   ========================================================================== */

// ---------------------------------------------------------------------------
// Response types (from API)
// ---------------------------------------------------------------------------

export interface Category {
  id: string;
  name: string;
  description: string | null;
  display_order: number;
  is_active: boolean;
  icon: string | null;
}

export interface ModifierOption {
  id: string;
  name: string;
  price_adjustment: number;
  display_order: number;
  is_available: boolean;
  group_id: string;
}

export interface ModifierGroup {
  id: string;
  name: string;
  display_order: number;
  required: boolean;
  min_selections: number;
  max_selections: number;
  is_active: boolean;
  modifiers: ModifierOption[];
}

export interface MenuItem {
  id: string;
  name: string;
  description: string | null;
  price: number;
  category_id: string;
  image_url: string | null;
  is_available: boolean;
  display_order: number;
  preparation_time_minutes: number | null;
  modifier_groups: ModifierGroup[];
}

export interface CategoryWithItems extends Category {
  items: MenuItem[];
}

export interface FullMenu {
  categories: CategoryWithItems[];
}

// ---------------------------------------------------------------------------
// Create / Update request types (for admin CRUD)
// ---------------------------------------------------------------------------

export interface CategoryCreate {
  name: string;
  description?: string | null;
  display_order?: number;
  is_active?: boolean;
  icon?: string | null;
}

export interface CategoryUpdate {
  name?: string;
  description?: string | null;
  display_order?: number;
  is_active?: boolean;
  icon?: string | null;
}

export interface MenuItemCreate {
  name: string;
  description?: string | null;
  price: number;
  category_id: string;
  image_url?: string | null;
  is_available?: boolean;
  display_order?: number;
  preparation_time_minutes?: number | null;
  modifier_group_ids?: string[];
}

export interface MenuItemUpdate {
  name?: string;
  description?: string | null;
  price?: number;
  category_id?: string;
  image_url?: string | null;
  is_available?: boolean;
  display_order?: number;
  preparation_time_minutes?: number | null;
  modifier_group_ids?: string[];
}

export interface ModifierCreate {
  name: string;
  price_adjustment?: number;
  display_order?: number;
  is_available?: boolean;
}

export interface ModifierUpdate {
  name?: string;
  price_adjustment?: number;
  display_order?: number;
  is_available?: boolean;
}

export interface ModifierGroupCreate {
  name: string;
  display_order?: number;
  required?: boolean;
  min_selections?: number;
  max_selections?: number;
  is_active?: boolean;
  modifiers?: ModifierCreate[];
}

export interface ModifierGroupUpdate {
  name?: string;
  display_order?: number;
  required?: boolean;
  min_selections?: number;
  max_selections?: number;
  is_active?: boolean;
}
