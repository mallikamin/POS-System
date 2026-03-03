/* ==========================================================================
   Core TypeScript interfaces for the POS System
   ========================================================================== */

// ---------------------------------------------------------------------------
// Base
// ---------------------------------------------------------------------------
export interface BaseEntity {
  id: string;
  tenant_id: string;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------
export interface User extends BaseEntity {
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  avatar_url?: string;
}

export interface Permission {
  code: string;
  description: string | null;
}

export interface Role {
  id: string;
  name: string;
  permissions: Permission[];
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// ---------------------------------------------------------------------------
// Restaurant Config
// ---------------------------------------------------------------------------
export interface RestaurantConfig extends BaseEntity {
  name: string;
  payment_flow: "order_first" | "pay_first";
  currency: string;
  timezone: string;
  tax_inclusive: boolean;
  default_tax_rate: number;
  receipt_header: string | null;
  receipt_footer: string | null;
}

// ---------------------------------------------------------------------------
// Order Enums
// ---------------------------------------------------------------------------
export type OrderType = "dine_in" | "takeaway" | "call_center";

export type OrderStatus =
  | "draft"
  | "confirmed"
  | "in_kitchen"
  | "ready"
  | "served"
  | "completed"
  | "voided";

export type PaymentStatus = "unpaid" | "partial" | "paid" | "refunded";

export type TableStatus =
  | "available"
  | "occupied"
  | "reserved"
  | "dirty"
  | "blocked"
  | "ready_to_serve";

// ---------------------------------------------------------------------------
// Menu
// ---------------------------------------------------------------------------
export interface Category extends BaseEntity {
  name: string;
  display_order: number;
  is_active: boolean;
  icon?: string;
}

export interface MenuItem extends BaseEntity {
  name: string;
  description?: string;
  price: number;
  category_id: string;
  image_url?: string;
  is_available: boolean;
  preparation_time_minutes?: number;
  modifiers?: ModifierGroup[];
}

export interface ModifierGroup {
  id: string;
  name: string;
  required: boolean;
  min_selections: number;
  max_selections: number;
  options: ModifierOption[];
}

export interface ModifierOption {
  id: string;
  name: string;
  price_adjustment: number;
}

// ---------------------------------------------------------------------------
// Order
// ---------------------------------------------------------------------------
export interface Order extends BaseEntity {
  order_number: string;
  order_type: OrderType;
  status: OrderStatus;
  payment_status: PaymentStatus;
  table_id?: string;
  customer_name?: string;
  customer_phone?: string;
  delivery_address?: string;
  items: OrderItem[];
  subtotal: number;
  tax_amount: number;
  discount_amount: number;
  total: number;
  notes?: string;
  created_by: string;
}

export interface OrderItem {
  id: string;
  menu_item_id: string;
  name: string;
  quantity: number;
  unit_price: number;
  modifiers: SelectedModifier[];
  notes?: string;
  status: "pending" | "sent" | "preparing" | "ready" | "served";
  total: number;
}

export interface SelectedModifier {
  modifier_option_id: string;
  name: string;
  price_adjustment: number;
  quantity: number;
}

// ---------------------------------------------------------------------------
// Table / Floor
// ---------------------------------------------------------------------------
export interface Table extends BaseEntity {
  number: string;
  capacity: number;
  status: TableStatus;
  floor_id: string;
  position_x: number;
  position_y: number;
  width: number;
  height: number;
  shape: "rectangle" | "circle" | "square";
  current_order_id?: string;
}

export interface Floor extends BaseEntity {
  name: string;
  display_order: number;
  tables: Table[];
}

// ---------------------------------------------------------------------------
// Payment
// ---------------------------------------------------------------------------
export type PaymentMethod = "cash" | "card" | "mobile" | "split";

export interface Payment extends BaseEntity {
  order_id: string;
  amount: number;
  method: PaymentMethod;
  reference?: string;
  status: "pending" | "completed" | "failed" | "refunded";
}
