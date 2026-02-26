import api from "@/lib/axios";
import type {
  KitchenOrderStatus,
  KitchenStation,
  KitchenStationFilter,
  KitchenTicket,
} from "@/types/kitchen";

type KitchenQueueItemResponse = {
  id?: string;
  order_item_id: string;
  quantity: number;
  item_name?: string;
  item_notes?: string;
};

type KitchenQueueTicketResponse = {
  id: string;
  order_id: string;
  station_id: string;
  status: "new" | "preparing" | "ready" | "served";
  created_at: string;
  order_number?: string;
  order_type?: "dine_in" | "takeaway" | "call_center";
  order_total?: number;
  customer_name?: string;
  table_id?: string;
  items: KitchenQueueItemResponse[];
};

function mapKitchenStatusToOrderStatus(status: KitchenQueueTicketResponse["status"]): KitchenOrderStatus {
  if (status === "new") return "confirmed";
  if (status === "preparing") return "in_kitchen";
  if (status === "ready") return "ready";
  return "served";
}

function toTicket(
  ticket: KitchenQueueTicketResponse,
  station: KitchenStation
): KitchenTicket {
  const raw = mapKitchenStatusToOrderStatus(ticket.status);
  return {
    id: ticket.order_id,
    ticket_id: ticket.id,
    order_number: ticket.order_number || "N/A",
    order_type: ticket.order_type || "dine_in",
    raw_status: raw,
    column: ticket.status,
    item_count: ticket.items.reduce((sum, item) => sum + item.quantity, 0),
    total: ticket.order_total ?? 0,
    created_at: ticket.created_at,
    station_id: ticket.station_id,
    station_name: station.name,
    customer_name: ticket.customer_name,
    table_id: ticket.table_id,
    items: ticket.items.map((item) => ({
      id: item.id ?? item.order_item_id,
      order_item_id: item.order_item_id,
      quantity: item.quantity,
      item_name: item.item_name,
      item_notes: item.item_notes,
    })),
  };
}

export async function fetchKitchenStations(): Promise<KitchenStation[]> {
  const { data } = await api.get<KitchenStation[]>("/kitchen/stations", {
    params: { active_only: true },
  });
  return data;
}

async function fetchStationQueue(stationId: string): Promise<KitchenQueueTicketResponse[]> {
  const { data } = await api.get<KitchenQueueTicketResponse[]>(
    `/kitchen/stations/${stationId}/queue`,
    { params: { active_only: false } }
  );
  return data;
}

export async function fetchKitchenTickets(
  stationFilter: KitchenStationFilter,
  stations: KitchenStation[]
): Promise<KitchenTicket[]> {
  const effectiveStations =
    stationFilter === "all"
      ? stations
      : stations.filter((station) => station.id === stationFilter);

  const queueResults = await Promise.all(
    effectiveStations.map(async (station) => ({
      station,
      tickets: await fetchStationQueue(station.id),
    }))
  );

  return queueResults.flatMap((result) =>
    result.tickets.map((ticket) => toTicket(ticket, result.station))
  );
}

/**
 * Map kitchen ticket column to the kitchen ticket API status values.
 * Kitchen ticket statuses: new → preparing → ready → served
 */
const TICKET_BUMP_MAP: Record<string, string | null> = {
  new: "preparing",
  preparing: "ready",
  ready: "served",
  served: null,
};

export async function bumpKitchenTicket(ticket: KitchenTicket): Promise<void> {
  const next = TICKET_BUMP_MAP[ticket.column];
  if (!next) {
    throw new Error("Ticket is already at terminal state.");
  }

  await api.patch(`/kitchen/tickets/${ticket.ticket_id}/status`, {
    status: next,
  });
}

export async function setKitchenTicketStatus(
  ticketId: string,
  status: "new" | "preparing" | "ready" | "served"
): Promise<void> {
  await api.patch(`/kitchen/tickets/${ticketId}/status`, {
    status,
  });
}
