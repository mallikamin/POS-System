import { create } from "zustand";
import type { CategoryWithItems, FullMenu } from "@/types/menu";
import { fetchFullMenu } from "@/services/menuApi";

interface MenuState {
  categories: CategoryWithItems[];
  isLoading: boolean;
  error: string | null;
  lastFetched: number | null;
}

interface MenuActions {
  loadMenu: () => Promise<void>;
  clearMenu: () => void;
}

type MenuStore = MenuState & MenuActions;

export const useMenuStore = create<MenuStore>()((set, get) => ({
  categories: [],
  isLoading: false,
  error: null,
  lastFetched: null,

  loadMenu: async () => {
    // Debounce: don't re-fetch if loaded within last 30 seconds
    const { isLoading, lastFetched } = get();
    if (isLoading) return;
    if (lastFetched && Date.now() - lastFetched < 30_000) return;

    set({ isLoading: true, error: null });
    try {
      const data: FullMenu = await fetchFullMenu();
      set({
        categories: data.categories,
        isLoading: false,
        lastFetched: Date.now(),
      });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load menu";
      set({ error: message, isLoading: false });
    }
  },

  clearMenu: () => {
    set({ categories: [], lastFetched: null, error: null });
  },
}));
