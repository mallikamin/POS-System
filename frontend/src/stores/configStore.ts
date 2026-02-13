import { create } from "zustand";
import api from "@/lib/axios";
import type { RestaurantConfig } from "@/types";

interface ConfigState {
  config: RestaurantConfig | null;
  isLoading: boolean;
  error: string | null;
  fetchConfig: () => Promise<void>;
  clearConfig: () => void;
}

export const useConfigStore = create<ConfigState>()((set, get) => ({
  config: null,
  isLoading: false,
  error: null,

  fetchConfig: async () => {
    // Avoid duplicate fetches
    if (get().isLoading) return;

    set({ isLoading: true, error: null });
    try {
      const { data } = await api.get<RestaurantConfig>("/config/restaurant");
      set({ config: data, isLoading: false });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load restaurant config";
      set({ error: message, isLoading: false });
    }
  },

  clearConfig: () => set({ config: null, error: null }),
}));
