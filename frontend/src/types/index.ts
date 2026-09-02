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
  /**
   * The shop's display name, from the tenant record.
   *
   * 🔴 This field was declared as `name` here while the API has always returned
   * `restaurant_name`, so `config.name` was permanently `undefined` and every
   * screen that tried to show the shop's name silently showed nothing. That is
   * what put "Restaurant not loaded" on the switch-account screen. Found in UAT
   * on 2026-08-27. Same failure as the missing `is_produced` in
   * `types/inventory.ts`: a response field with no matching TS type, silent in
   * both directions until somebody needs it.
   *
   * Nullable because a tenant row could in principle have no name; render a
   * fallback rather than an empty gap.
   */
  restaurant_name: string | null;
  /**
   * The slug of the tenant this session actually belongs to.
   *
   * The authoritative answer to "which shop am I signed in to". Unlike the
   * remembered slug in localStorage, this arrives with the session and cannot be
   * contradicted by a query string, which is what made the old inference wrong.
   */
  tenant_slug: string | null;
  payment_flow: "order_first" | "pay_first";
  currency: string;
  /**
   * Optional visual identity for this tenant, e.g. `desert-salt`.
   *
   * Null for every existing tenant, which is what keeps them looking exactly as
   * they do today: `setActiveTheme` stamps nothing and the `:root` defaults in
   * `index.css` apply. Declared here because a response field with no TS type
   * is silent in both directions (see the `restaurant_name` note above).
   */
  theme: string | null;
  timezone: string;
  tax_inclusive: boolean;
  default_tax_rate: number;
  receipt_header: string | null;
  receipt_footer: string | null;
  /** How the browser receipt prints: `thermal` (80mm roll) or `a4`. */
  receipt_format: "thermal" | "a4";
  /**
   * Display name for the walk-in channel ("Pick up" for FZ LLC). Null means
   * "Takeaway". The order_type underneath is always `takeaway`.
   */
  takeaway_label: string | null;
  /**
   * True for a shop that takes orders only from its website (Chick Shack):
   * the POS lands on the online-orders queue instead of the channel selector.
   */
  online_ordering_only: boolean;
  /**
   * Comma-separated UI module slugs this tenant should not be shown, e.g.
   * `"dine-in,quickbooks-online"`. Read it through `isModuleHidden()` in
   * `lib/modules.ts` rather than splitting it at each call site.
   *
   * ⚠️ Presentation only. It hides navigation and dashboard cards so a client is
   * not shown modules they do not use. It does NOT gate the endpoints behind
   * them, because every admin route is gated by role and nothing else. The real
   * per-tenant module gate is OI-93 and does not exist yet. Do not describe this
   * to anyone as access control.
   */
  hidden_ui_modules: string;
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
