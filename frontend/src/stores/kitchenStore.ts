import { create } from "zustand";
import * as kitchenApi from "@/services/kitchenApi";
import { getAccessToken } from "@/lib/axios";
import type {
  KitchenConnectionStatus,
  KitchenStation,
  KitchenStationFilter,
  KitchenTicket,
  KitchenTicketEvent,
} from "@/types/kitchen";

interface KitchenState {
  tickets: KitchenTicket[];
  stations: KitchenStation[];
  selectedStation: KitchenStationFilter;
  isLoading: boolean;
  error: string | null;
  audioEnabled: boolean;
  recalledTicketIds: string[];
  lastLoadedAt: number | null;
  wsStatus: KitchenConnectionStatus;
  wsEnabled: boolean;
}

interface KitchenActions {
  setStation: (station: KitchenStationFilter) => void;
  setAudioEnabled: (enabled: boolean) => void;
  initialize: () => Promise<void>;
  connectRealtime: () => void;
  disconnectRealtime: () => void;
  toggleRecall: (ticketId: string) => void;
  loadTickets: (force?: boolean) => Promise<KitchenTicket[]>;
  applyTicketEvent: (evt: KitchenTicketEvent) => void;
  bumpTicket: (ticket: KitchenTicket) => Promise<void>;
  updateTicketStatus: (
    ticketId: string,
    status: "new" | "preparing" | "ready" | "served"
  ) => Promise<void>;
}

type KitchenStore = KitchenState & KitchenActions;

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let reconnectAttempt = 0;
let joinedStationRoom: string | null = null;
let manualDisconnect = false;

function buildWsUrl(): string {
  const configured = import.meta.env.VITE_WS_URL || "/ws";
  if (configured.startsWith("ws://") || configured.startsWith("wss://")) {
    return configured;
  }
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}${configured}`;
}

function sendWsMessage(payload: Record<string, unknown>) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify(payload));
}

function mapEventStatusToRaw(
  status: "new" | "preparing" | "ready" | "served"
): KitchenTicket["raw_status"] {
  if (status === "new") return "confirmed";
  if (status === "preparing") return "in_kitchen";
  if (status === "ready") return "ready";
  return "served";
}

function toTicketFromEvent(
  evt: KitchenTicketEvent,
  existing?: KitchenTicket
): KitchenTicket {
  const itemCount =
    evt.data.items?.reduce((sum, item) => sum + item.quantity, 0) ?? existing?.item_count ?? 0;

  return {
    id: evt.data.order_id,
    ticket_id: evt.data.ticket_id,
    order_number: evt.data.order_number || existing?.order_number || "N/A",
    order_type: evt.data.order_type || existing?.order_type || "dine_in",
    raw_status: mapEventStatusToRaw(evt.data.status),
    column: evt.data.status,
    item_count: itemCount,
    total: existing?.total ?? 0,
    created_at: existing?.created_at || new Date().toISOString(),
    station_id: evt.data.station_id,
    station_name: evt.data.station_name || existing?.station_name || undefined,
    customer_name: existing?.customer_name,
    customer_phone: existing?.customer_phone,
    table_id: existing?.table_id,
    items: evt.data.items?.map((item) => ({
      id: item.order_item_id,
      order_item_id: item.order_item_id,
      quantity: item.quantity,
      item_name: item.name,
    })) ?? existing?.items ?? [],
  };
}

function isKitchenTicketEvent(payload: unknown): payload is KitchenTicketEvent {
  if (!payload || typeof payload !== "object") return false;
  const value = payload as { event?: unknown; data?: unknown };

  if (
    value.event !== "kitchen.ticket.created" &&
    value.event !== "kitchen.ticket.updated"
  ) {
    return false;
  }
  const data = value.data as Record<string, unknown> | undefined;
  return Boolean(data && typeof data.order_id === "string" && typeof data.station_id === "string");
}

function subscribeRooms(selectedStation: KitchenStationFilter) {
  sendWsMessage({ type: "join", room: "kitchen:all" });

  if (joinedStationRoom) {
    sendWsMessage({ type: "leave", room: joinedStationRoom });
    joinedStationRoom = null;
  }

  if (selectedStation !== "all") {
    joinedStationRoom = `kitchen:${selectedStation}`;
    sendWsMessage({ type: "join", room: joinedStationRoom });
  }
}

export const useKitchenStore = create<KitchenStore>()((set, get) => ({
  tickets: [],
  stations: [],
  selectedStation: "all",
  isLoading: false,
  error: null,
  audioEnabled: false,
  recalledTicketIds: [],
  lastLoadedAt: null,
  wsStatus: "disconnected",
  wsEnabled: false,

  setStation: (station) => {
    set({ selectedStation: station });
    if (get().wsStatus === "connected") {
      subscribeRooms(station);
    }
  },

  setAudioEnabled: (enabled) => set({ audioEnabled: enabled }),

  initialize: async () => {
    const stations = await kitchenApi.fetchKitchenStations();
    set({ stations });
    await get().loadTickets(true);
  },

  connectRealtime: () => {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const token = getAccessToken();
    if (!token) {
      set({ wsStatus: "degraded", wsEnabled: false });
      return;
    }

    manualDisconnect = false;
    set({ wsStatus: "connecting" });
    ws = new WebSocket(buildWsUrl());

    ws.onopen = () => {
      reconnectAttempt = 0;
      set({ wsEnabled: true });
      sendWsMessage({ type: "auth", token });
    };

    ws.onmessage = (message) => {
      try {
        const payload = JSON.parse(message.data) as unknown;

        if (
          payload &&
          typeof payload === "object" &&
          "type" in payload &&
          (payload as { type?: unknown }).type === "auth_ok"
        ) {
          set({ wsStatus: "connected", wsEnabled: true, error: null });
          subscribeRooms(get().selectedStation);
          return;
        }

        if (isKitchenTicketEvent(payload)) {
          get().applyTicketEvent(payload);
        }
      } catch {
        // Ignore malformed payloads
      }
    };

    ws.onclose = () => {
      ws = null;
      set({ wsStatus: "degraded", wsEnabled: false });
      if (manualDisconnect) {
        set({ wsStatus: "disconnected", wsEnabled: false });
        return;
      }

      if (reconnectTimer) clearTimeout(reconnectTimer);
      reconnectAttempt += 1;
      const delay = Math.min(30_000, 1000 * 2 ** reconnectAttempt);
      reconnectTimer = setTimeout(() => {
        get().connectRealtime();
      }, delay);
    };

    ws.onerror = () => {
      set({ wsStatus: "degraded", wsEnabled: false });
    };
  },

  disconnectRealtime: () => {
    manualDisconnect = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (ws) {
      ws.close();
      ws = null;
    }
    joinedStationRoom = null;
    set({ wsStatus: "disconnected", wsEnabled: false });
  },

  toggleRecall: (ticketId) =>
    set((state) => {
      const exists = state.recalledTicketIds.includes(ticketId);
      return {
        recalledTicketIds: exists
          ? state.recalledTicketIds.filter((id) => id !== ticketId)
          : [ticketId, ...state.recalledTicketIds],
      };
    }),

  loadTickets: async (force = false) => {
    const state = get();
    if (!force && state.lastLoadedAt && Date.now() - state.lastLoadedAt < 2000) {
      return state.tickets;
    }

    set({ isLoading: true, error: null });
    try {
      const stations = state.stations.length > 0 ? state.stations : await kitchenApi.fetchKitchenStations();
      const tickets = await kitchenApi.fetchKitchenTickets(state.selectedStation, stations);
      set({
        tickets,
        stations,
        isLoading: false,
        lastLoadedAt: Date.now(),
      });
      return tickets;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load kitchen tickets";
      set({ error: message, isLoading: false });
      return [];
    }
  },

  applyTicketEvent: (evt) => {
    set((state) => {
      const selected = state.selectedStation;
      const belongsToSelected =
        selected === "all" || evt.data.station_id === selected;

      const existing = state.tickets.find((ticket) => ticket.id === evt.data.order_id);
      if (!belongsToSelected && !existing) {
        return state;
      }

      const nextTicket = toTicketFromEvent(evt, existing);
      const nextTickets = state.tickets.filter((ticket) => ticket.id !== evt.data.order_id);

      if (belongsToSelected) {
        nextTickets.unshift(nextTicket);
      }

      return { tickets: nextTickets, lastLoadedAt: Date.now() };
    });
  },

  bumpTicket: async (ticket) => {
    try {
      await kitchenApi.bumpKitchenTicket(ticket);
      await get().loadTickets(true);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to bump ticket";
      set({ error: message });
      throw err;
    }
  },

  updateTicketStatus: async (ticketId, status) => {
    try {
      await kitchenApi.setKitchenTicketStatus(ticketId, status);
      await get().loadTickets(true);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to update ticket status";
      set({ error: message });
      throw err;
    }
  },
}));
