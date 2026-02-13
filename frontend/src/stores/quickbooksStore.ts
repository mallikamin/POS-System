/**
 * QuickBooks integration Zustand store (Attempt 2 — client-centric).
 *
 * No templates. POS declares needs, fuzzy-matches against partner's QB accounts.
 */

import { create } from "zustand";
import type {
  QBConnectionStatus,
  QBAccountMapping,
  QBSyncStats,
  QBMatchResult,
} from "@/types/quickbooks";
import * as qbApi from "@/services/quickbooksApi";

interface QBState {
  connectionStatus: QBConnectionStatus | null;
  isLoadingConnection: boolean;

  matchResult: QBMatchResult | null;
  isMatching: boolean;

  mappings: QBAccountMapping[];
  isLoadingMappings: boolean;

  syncStats: QBSyncStats | null;
  isLoadingSyncStats: boolean;

  error: string | null;
}

interface QBActions {
  loadConnectionStatus: () => Promise<void>;
  runMatching: () => Promise<QBMatchResult | null>;
  setMatchResult: (result: QBMatchResult | null) => void;
  loadMappings: (mappingType?: string) => Promise<void>;
  loadSyncStats: () => Promise<void>;
  clearError: () => void;
}

export const useQuickBooksStore = create<QBState & QBActions>()((set) => ({
  connectionStatus: null,
  isLoadingConnection: false,
  matchResult: null,
  isMatching: false,
  mappings: [],
  isLoadingMappings: false,
  syncStats: null,
  isLoadingSyncStats: false,
  error: null,

  loadConnectionStatus: async () => {
    set({ isLoadingConnection: true, error: null });
    try {
      const status = await qbApi.fetchConnectionStatus();
      set({ connectionStatus: status, isLoadingConnection: false });
    } catch {
      set({
        connectionStatus: { is_connected: false },
        isLoadingConnection: false,
      });
    }
  },

  runMatching: async () => {
    set({ isMatching: true, error: null });
    try {
      const result = await qbApi.runAccountMatching();
      set({ matchResult: result, isMatching: false });
      return result;
    } catch {
      set({ error: "Failed to run account matching", isMatching: false });
      return null;
    }
  },

  setMatchResult: (result) => set({ matchResult: result }),

  loadMappings: async (mappingType?) => {
    set({ isLoadingMappings: true, error: null });
    try {
      const mappings = await qbApi.fetchMappings(mappingType);
      set({ mappings, isLoadingMappings: false });
    } catch {
      set({ error: "Failed to load mappings", isLoadingMappings: false });
    }
  },

  loadSyncStats: async () => {
    set({ isLoadingSyncStats: true });
    try {
      const stats = await qbApi.fetchSyncStats();
      set({ syncStats: stats, isLoadingSyncStats: false });
    } catch {
      set({ isLoadingSyncStats: false });
    }
  },

  clearError: () => set({ error: null }),
}));
