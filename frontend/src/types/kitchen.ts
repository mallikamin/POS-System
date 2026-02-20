export type KitchenStationFilter = "all" | string;

export type KitchenTicketColumn = "new" | "preparing" | "ready" | "served";

export type KitchenOrderStatus =
  | "draft"
  | "confirmed"
  | "in_kitchen"
  | "ready"
  | "served"
  | "completed"
  | "voided";

export interface KitchenTicket {
  id: string;
  ticket_id?: string;
  order_number: string;
  order_type: "dine_in" | "takeaway" | "call_center";
  raw_status: KitchenOrderStatus;
  column: KitchenTicketColumn;
  item_count: number;
  total: number;
  created_at: string;
  station_id?: string;
  station_name?: string;
  customer_name?: string;
  customer_phone?: string;
  table_id?: string;
}

export interface KitchenStation {
  id: string;
  name: string;
  display_order: number;
  is_active: boolean;
}

export interface KitchenTicketEvent {
  event: "kitchen.ticket.created" | "kitchen.ticket.updated";
  data: {
    ticket_id: string;
    order_id: string;
    station_id: string;
    station_name?: string | null;
    order_number?: string | null;
    order_type?: "dine_in" | "takeaway" | "call_center" | null;
    status: "new" | "preparing" | "ready" | "served";
    previous_status?: "new" | "preparing" | "ready" | "served" | null;
    priority?: number;
    items?: Array<{ order_item_id: string; name: string; quantity: number }>;
  };
}

export type KitchenConnectionStatus =
  | "disconnected"
  | "connecting"
  | "connected"
  | "degraded";
