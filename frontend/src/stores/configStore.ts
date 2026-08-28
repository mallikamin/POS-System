import { create } from "zustand";
import api from "@/lib/axios";
import { setActiveCurrency } from "@/utils/currency";
import { setActiveTheme } from "@/utils/theme";
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
      // Drive display formatting from the tenant's configured currency before
      // any component renders a price.
      setActiveCurrency(data.currency);
      // Same idea for the look: a tenant may carry its own palette. Tenants
      // without one get no attribute and render exactly as before.
      setActiveTheme(data.theme);
      set({ config: data, isLoading: false });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load restaurant config";
      set({ error: message, isLoading: false });
    }
  },

  clearConfig: () => {
    setActiveTheme(null);
    set({ config: null, error: null });
  },
}));
