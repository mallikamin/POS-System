/* Order types matching backend schemas */

export interface OrderItemModifierCreate {
  modifier_id: string;
  name: string;
  price_adjustment: number;
}

export interface OrderItemCreate {
  menu_item_id: string;
  name: string;
  quantity: number;
  unit_price: number; // paisa
  modifiers: OrderItemModifierCreate[];
  notes?: string;
}

export interface OrderCreateRequest {
  order_type: "dine_in" | "takeaway" | "call_center";
  table_id?: string;
  customer_name?: string;
  customer_phone?: string;
  items: OrderItemCreate[];
  notes?: string;
}

export interface OrderItemModifierResponse {
  id: string;
  modifier_id: string;
  name: string;
  price_adjustment: number;
}

export interface OrderItemResponse {
  id: string;
  menu_item_id: string;
  name: string;
  quantity: number;
  unit_price: number;
  total: number;
  notes?: string;
  status: string;
  modifiers: OrderItemModifierResponse[];
}

export interface OrderResponse {
  id: string;
  order_number: string;
  order_type: string;
  status: string;
  payment_status: string;
  table_id?: string;
  table_session_id?: string;
  table_number?: number;
  table_label?: string;
  customer_name?: string;
  customer_phone?: string;
  subtotal: number;
  tax_amount: number;
  discount_amount: number;
  total: number;
  notes?: string;
  created_by: string;
  created_at: string;
  updated_at?: string;
  items: OrderItemResponse[];
}

export interface OrderListItem {
  id: string;
  order_number: string;
  order_type: string;
  status: string;
  payment_status: string;
  table_id?: string;
  table_number?: number;
  table_label?: string;
  item_count: number;
  total: number;
  created_at: string;
  created_by: string;
}

export interface PaginatedOrders {
  items: OrderListItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/* Dashboard types */

export interface DashboardKpis {
  today_revenue: number;
  yesterday_revenue: number;
  today_orders: number;
  avg_order_value: number;
  table_utilization: number;
  active_orders: number;
  pending_kitchen: number;
}

export interface LiveOrderItem {
  id: string;
  order_number: string;
  order_type: string;
  status: string;
  table_id?: string;
  table_number?: number;
  customer_name?: string;
  customer_phone?: string;
  item_count: number;
  total: number;
  created_at: string;
}

export interface LiveOperations {
  dine_in: LiveOrderItem[];
  takeaway: LiveOrderItem[];
  call_center: LiveOrderItem[];
}

/* Report types */

export interface SalesSummary {
  total_revenue: number;
  total_orders: number;
  avg_order_value: number;
  total_tax: number;
  dine_in_revenue: number;
  dine_in_orders: number;
  takeaway_revenue: number;
  takeaway_orders: number;
  call_center_revenue: number;
  call_center_orders: number;
}

export interface ItemPerformanceEntry {
  menu_item_id: string;
  name: string;
  quantity_sold: number;
  revenue: number;
}

export interface CategoryBreakdown {
  category_name: string;
  revenue: number;
  order_count: number;
}

export interface ItemPerformance {
  top_items: ItemPerformanceEntry[];
  bottom_items: ItemPerformanceEntry[];
  categories: CategoryBreakdown[];
}

export interface HourlyBucket {
  hour: number;
  order_count: number;
  revenue: number;
}

export interface HourlyBreakdown {
  date: string;
  buckets: HourlyBucket[];
}
