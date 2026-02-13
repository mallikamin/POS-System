import { create } from "zustand";
import type { OrderType } from "@/types";

type Theme = "light" | "dark" | "system";

interface UIState {
  sidebarOpen: boolean;
  currentChannel: OrderType | null;
  theme: Theme;
}

interface UIActions {
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  setCurrentChannel: (channel: OrderType | null) => void;
  setTheme: (theme: Theme) => void;
  resetUi: () => void;
}

type UIStore = UIState & UIActions;

export const useUIStore = create<UIStore>()((set) => ({
  /* ---- State ---- */
  sidebarOpen: false,
  currentChannel: null,
  theme: "light",

  /* ---- Actions ---- */
  setSidebarOpen: (open: boolean) => set({ sidebarOpen: open }),

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  setCurrentChannel: (channel: OrderType | null) => set({ currentChannel: channel }),

  setTheme: (theme: Theme) => set({ theme }),

  resetUi: () => set({ sidebarOpen: false, currentChannel: null }),
}));
