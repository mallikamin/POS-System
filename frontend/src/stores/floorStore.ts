import { create } from "zustand";
import type { FloorWithTables, TableResponse } from "@/types/floor";
import { fetchStatusBoard, updateTableStatus } from "@/services/floorApi";

interface FloorState {
  floors: FloorWithTables[];
  selectedFloorId: string | null;
  selectedTableId: string | null;
  isLoading: boolean;
  error: string | null;
  lastFetched: number | null;
}

interface FloorActions {
  loadFloors: () => Promise<void>;
  setSelectedFloor: (id: string | null) => void;
  setSelectedTable: (id: string | null) => void;
  setTableStatus: (
    tableId: string,
    status: TableResponse["status"]
  ) => Promise<void>;
  getSelectedFloor: () => FloorWithTables | null;
  getSelectedTable: () => TableResponse | null;
  updateTableInStore: (tableId: string, updates: Partial<TableResponse>) => void;
}

type FloorStore = FloorState & FloorActions;

export const useFloorStore = create<FloorStore>()((set, get) => ({
  floors: [],
  selectedFloorId: null,
  selectedTableId: null,
  isLoading: false,
  error: null,
  lastFetched: null,

  loadFloors: async () => {
    const { isLoading, lastFetched } = get();
    if (isLoading) return;
    if (lastFetched && Date.now() - lastFetched < 15_000) return;

    set({ isLoading: true, error: null });
    try {
      const data = await fetchStatusBoard();
      const floors = data.floors;
      const state = get();

      // Auto-select first floor if none selected
      const selectedFloorId =
        state.selectedFloorId && floors.some((f) => f.id === state.selectedFloorId)
          ? state.selectedFloorId
          : floors[0]?.id ?? null;

      set({
        floors,
        selectedFloorId,
        isLoading: false,
        lastFetched: Date.now(),
      });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load floor plan";
      set({ error: message, isLoading: false });
    }
  },

  setSelectedFloor: (id) => {
    set({ selectedFloorId: id, selectedTableId: null });
  },

  setSelectedTable: (id) => {
    set({ selectedTableId: id });
  },

  setTableStatus: async (tableId, status) => {
    try {
      const updated = await updateTableStatus(tableId, status);
      set((state) => ({
        floors: state.floors.map((floor) => ({
          ...floor,
          tables: floor.tables.map((table) =>
            table.id === tableId ? updated : table
          ),
        })),
        error: null,
      }));
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to update table status";
      set({ error: message });
      throw err;
    }
  },

  getSelectedFloor: () => {
    const { floors, selectedFloorId } = get();
    return floors.find((f) => f.id === selectedFloorId) ?? null;
  },

  getSelectedTable: () => {
    const { floors, selectedTableId } = get();
    if (!selectedTableId) return null;
    for (const floor of floors) {
      const table = floor.tables.find((t) => t.id === selectedTableId);
      if (table) return table;
    }
    return null;
  },

  updateTableInStore: (tableId, updates) => {
    set((state) => ({
      floors: state.floors.map((floor) => ({
        ...floor,
        tables: floor.tables.map((t) =>
          t.id === tableId ? { ...t, ...updates } : t
        ),
      })),
    }));
  },
}));
