import api from "@/lib/axios";
import { transitionOrder } from "@/services/ordersApi";
import type { OrderResponse } from "@/types/order";
import type {
  KitchenOrderStatus,
  KitchenStation,
  KitchenStationFilter,
  KitchenTicket,
} from "@/types/kitchen";

type KitchenQueueItemResponse = {
  id: string;
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
    total: 0,
    created_at: ticket.created_at,
    station_id: ticket.station_id,
    station_name: station.name,
    customer_name: undefined,
    customer_phone: undefined,
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
    { params: { active_only: true } }
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

export async function bumpKitchenTicket(ticket: KitchenTicket): Promise<OrderResponse> {
  const nextStatusByCurrent: Record<KitchenOrderStatus, string | null> = {
    draft: "confirmed",
    confirmed: "in_kitchen",
    in_kitchen: "ready",
    ready: "served",
    served: "completed",
    completed: null,
    voided: null,
  };

  const next = nextStatusByCurrent[ticket.raw_status];
  if (!next) {
    throw new Error("Ticket is already at terminal state.");
  }

  return transitionOrder(ticket.id, next);
}

export async function setKitchenTicketStatus(
  orderId: string,
  status: "confirmed" | "in_kitchen" | "ready" | "served" | "completed"
): Promise<OrderResponse> {
  return transitionOrder(orderId, status);
}
