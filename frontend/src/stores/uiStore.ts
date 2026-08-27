import { create } from "zustand";
import type { OrderType } from "@/types";

type Theme = "light" | "dark" | "system";

interface UIState {
  sidebarOpen: boolean;
  /**
   * F10: the admin nav shrunk to an icon rail. A per-device preference (a
   * tablet in landscape wants it, a wide monitor may not), so it lives in
   * localStorage rather than in the tenant config, and survives logout.
   */
  adminSidebarCollapsed: boolean;
  currentChannel: OrderType | null;
  theme: Theme;
}

interface UIActions {
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  setAdminSidebarCollapsed: (collapsed: boolean) => void;
  setCurrentChannel: (channel: OrderType | null) => void;
  setTheme: (theme: Theme) => void;
  resetUi: () => void;
}

type UIStore = UIState & UIActions;

const ADMIN_SIDEBAR_KEY = "pos.admin.sidebarCollapsed";

function readAdminSidebarCollapsed(): boolean {
  try {
    return window.localStorage.getItem(ADMIN_SIDEBAR_KEY) === "1";
  } catch {
    return false;
  }
}

function writeAdminSidebarCollapsed(collapsed: boolean): void {
  try {
    window.localStorage.setItem(ADMIN_SIDEBAR_KEY, collapsed ? "1" : "0");
  } catch {
    // Private browsing can refuse localStorage; the choice then lasts one page.
  }
}

export const useUIStore = create<UIStore>()((set) => ({
  /* ---- State ---- */
  sidebarOpen: false,
  adminSidebarCollapsed: readAdminSidebarCollapsed(),
  currentChannel: null,
  theme: "light",

  /* ---- Actions ---- */
  setSidebarOpen: (open: boolean) => set({ sidebarOpen: open }),

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  setAdminSidebarCollapsed: (collapsed: boolean) => {
    writeAdminSidebarCollapsed(collapsed);
    set({ adminSidebarCollapsed: collapsed });
  },

  setCurrentChannel: (channel: OrderType | null) => set({ currentChannel: channel }),

  setTheme: (theme: Theme) => set({ theme }),

  resetUi: () => set({ sidebarOpen: false, currentChannel: null }),
}));
