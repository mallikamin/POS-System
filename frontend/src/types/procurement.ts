/**
 * Suppliers, purchase orders and goods receipts.
 *
 * 🔴 Every `*_minor` field arrives from the API as a STRING holding a decimal
 * in MINOR UNITS ("4600.00" means 46.00 AED). Two things follow, and both
 * matter:
 *
 *   1. It is a string because it is a `Numeric` on the wire, not a JS number.
 *      Parse it with `Number(...)` before doing arithmetic on it.
 *   2. It is already minor units. `formatMoney()` divides by 100 itself, so
 *      passing it a value you have already divided prints 100x too small.
 *      A `* 100` "conversion" of an already-minor value is the exact bug that
 *      produced a -1790% margin on 2026-08-26.
 *
 * Quantities are also strings, for the same `Numeric` reason.
 */

export type PurchaseOrderStatus =
  | "draft"
  | "sent"
  | "partially_received"
  | "received"
  | "cancelled";

export type ReceiptSource = "manual" | "ocr";

// ==========================================================================
// SUPPLIERS
// ==========================================================================

export interface Supplier {
  id: string;
  tenant_id: string;
  name: string;
  code: string;
  contact_name: string | null;
  email: string | null;
  phone: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  country: string | null;
  payment_terms: string | null;
  tax_registration_number: string | null;
  lead_time_days: number;
  is_active: boolean;
  notes: string | null;
  created_at: string;
  order_count: number;
  total_spend_minor: string;
}

export interface SupplierCreate {
  name: string;
  code: string;
  contact_name?: string | null;
  email?: string | null;
  phone?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  country?: string | null;
  payment_terms?: string | null;
  tax_registration_number?: string | null;
  lead_time_days?: number;
  is_active?: boolean;
  notes?: string | null;
}

export type SupplierUpdate = Partial<Omit<SupplierCreate, "code">>;

export interface SupplierItemRow {
  id: string;
  supplier_id: string;
  supplier_name: string;
  ingredient_id: string;
  ingredient_name: string;
  ingredient_image_url: string | null;
  unit: string;
  supplier_sku: string | null;
  supplier_item_name: string | null;
  last_price_minor: string;
  last_purchased_at: string | null;
  pack_size: string;
  minimum_order_quantity: string;
  lead_time_days: number | null;
  is_preferred: boolean;
  is_active: boolean;
  notes: string | null;
}

export interface SupplierItemUpsert {
  ingredient_id: string;
  supplier_sku?: string | null;
  supplier_item_name?: string | null;
  last_price_minor?: string | number;
  pack_size?: string | number;
  minimum_order_quantity?: string | number;
  lead_time_days?: number | null;
  is_preferred?: boolean;
  is_active?: boolean;
  notes?: string | null;
}

export interface SupplierPurchaseRow {
  id: string;
  po_number: string;
  status: PurchaseOrderStatus;
  location_id: string;
  location_name: string;
  expected_date: string | null;
  total_minor: string;
  sent_at: string | null;
  fully_received_at: string | null;
  created_at: string;
}

// ==========================================================================
// PURCHASE ORDERS
// ==========================================================================

export interface PurchaseOrderItem {
  id: string;
  ingredient_id: string;
  ingredient_name: string;
  ingredient_image_url: string | null;
  quantity_ordered: string;
  quantity_received: string;
  quantity_outstanding: string;
  unit: string;
  unit_price_minor: string;
  line_total_minor: string;
  supplier_sku: string | null;
  notes: string | null;
}

export interface GoodsReceiptLine {
  id: string;
  purchase_order_item_id: string;
  ingredient_id: string;
  quantity_received: string;
  unit: string;
  unit_price_minor: string;
}

export interface GoodsReceipt {
  id: string;
  receipt_number: string;
  purchase_order_id: string;
  source: ReceiptSource;
  document_reference: string | null;
  received_at: string;
  notes: string | null;
  lines: GoodsReceiptLine[];
}

export interface PurchaseOrder {
  id: string;
  po_number: string;
  supplier_id: string;
  supplier_name: string;
  supplier_email: string | null;
  location_id: string;
  location_name: string;
  status: PurchaseOrderStatus;
  expected_date: string | null;
  tax_bps: number;
  subtotal_minor: string;
  tax_minor: string;
  total_minor: string;
  notes: string | null;
  delivery_instructions: string | null;
  sent_at: string | null;
  sent_to_email: string | null;
  email_send_count: number;
  last_email_error: string | null;
  fully_received_at: string | null;
  cancelled_at: string | null;
  created_at: string;
  items: PurchaseOrderItem[];
  receipts: GoodsReceipt[];
}

export interface PurchaseOrderLineCreate {
  ingredient_id: string;
  quantity_ordered: string | number;
  unit_price_minor?: string | number | null;
  supplier_sku?: string | null;
  notes?: string | null;
}

export interface PurchaseOrderCreate {
  supplier_id: string;
  location_id: string;
  lines: PurchaseOrderLineCreate[];
  tax_bps?: number;
  expected_date?: string | null;
  notes?: string | null;
  delivery_instructions?: string | null;
}

export interface PurchaseOrderUpdate {
  expected_date?: string | null;
  tax_bps?: number;
  notes?: string | null;
  delivery_instructions?: string | null;
  lines?: PurchaseOrderLineCreate[];
}

export interface PurchaseOrderSendRequest {
  to?: string | null;
  cc_self?: boolean;
  message?: string | null;
  skip_email?: boolean;
}

export interface PurchaseOrderSendResult {
  purchase_order: PurchaseOrder;
  email_sent: boolean;
  sent_to: string | null;
  error: string | null;
}

export interface GoodsReceiptLineRequest {
  purchase_order_item_id: string;
  quantity_received: string | number;
  unit_price_minor?: string | number | null;
}

export interface GoodsReceiptRequest {
  lines: GoodsReceiptLineRequest[];
  document_reference?: string | null;
  source?: ReceiptSource;
  notes?: string | null;
}

export interface GoodsReceiptResult {
  purchase_order: PurchaseOrder;
  receipt: GoodsReceipt;
}

// ==========================================================================
// ORDERING SUGGESTION
//
// 🔴 Every quantity below is COMPUTED on the server from the recipe tree,
// stock and open orders. Only `advice` is model-written, and it is prose.
// ==========================================================================

export interface ProductionTarget {
  recipe_id: string;
  batches: string | number;
}

export interface SuggestionRequest {
  location_id?: string | null;
  targets: ProductionTarget[];
  days_until_production?: number | null;
  include_advice?: boolean;
}

export interface SuggestionTargetRow {
  recipe_id: string;
  recipe_name: string;
  batches: string;
  yield_servings: string;
  produces: string;
}

export interface ProductionPlanRow {
  ingredient_id: string;
  ingredient_name: string;
  unit: string;
  quantity_to_make: string;
}

export interface SuggestionLine {
  ingredient_id: string;
  ingredient_name: string;
  unit: string;
  required: string;
  on_hand: string;
  on_order: string;
  shortfall: string;
  suggested_quantity: string;
  unit_price_minor: string;
  estimated_cost_minor: string;
  supplier_id: string | null;
  supplier_name: string | null;
  lead_time_days: number | null;
  pack_size: string;
  has_supplier: boolean;
}

export interface SuggestionBasket {
  supplier_id: string;
  supplier_name: string;
  lead_time_days: number | null;
  lines: SuggestionLine[];
  estimated_total_minor: string;
}

export interface PlanAdvice {
  summary: string;
  risks: string[];
  order_first: string[];
}

export interface SuggestionResponse {
  location_id: string;
  location_name: string;
  targets: SuggestionTargetRow[];
  production_plan: ProductionPlanRow[];
  lines: SuggestionLine[];
  baskets: SuggestionBasket[];
  unsourced: SuggestionLine[];
  estimated_total_minor: string;
  advice: PlanAdvice | null;
  /** Why the commentary is missing. The plan itself is complete regardless. */
  advice_error: string | null;
}

// ==========================================================================
// OCR GOODS RECEIVING
// ==========================================================================

export interface ScannedLine {
  purchase_order_item_id: string;
  ingredient_name: string;
  unit: string;
  quantity_received: string;
  unit_price_minor: string | null;
  ordered_quantity: string;
  outstanding_quantity: string;
  document_text: string;
  confidence: string;
}

export interface UnmatchedLine {
  document_text: string;
  quantity: string | null;
  confidence: string;
}

export interface ScanResult {
  document_reference: string | null;
  supplier_name: string | null;
  lines: ScannedLine[];
  unmatched: UnmatchedLine[];
  duplicate_line_ids: string[];
  notes: string | null;
}

export interface ReceivingHistoryRow {
  id: string;
  receipt_number: string;
  purchase_order_id: string;
  po_number: string;
  source: ReceiptSource;
  document_reference: string | null;
  received_at: string;
  line_count: number;
  total_minor: string;
  notes: string | null;
}
