/**
 * QuickBooks integration Zustand store.
 */

import { create } from "zustand";
import type {
  QBConnectionStatus,
  QBTemplateInfo,
  QBAccountMapping,
  QBSyncStats,
  QBDiagnosticReport,
  QBTestFixture,
} from "@/types/quickbooks";
import * as qbApi from "@/services/quickbooksApi";

interface QBState {
  connectionStatus: QBConnectionStatus | null;
  isLoadingConnection: boolean;

  templates: QBTemplateInfo[];
  isLoadingTemplates: boolean;
  selectedTemplate: string | null;

  mappings: QBAccountMapping[];
  isLoadingMappings: boolean;

  syncStats: QBSyncStats | null;
  isLoadingSyncStats: boolean;

  // Diagnostic
  diagnosticReport: QBDiagnosticReport | null;
  isRunningDiagnostic: boolean;
  fixtures: QBTestFixture[];

  error: string | null;
}

interface QBActions {
  loadConnectionStatus: () => Promise<void>;
  loadTemplates: () => Promise<void>;
  selectTemplate: (name: string | null) => void;
  loadMappings: (mappingType?: string) => Promise<void>;
  loadSyncStats: () => Promise<void>;
  loadFixtures: () => Promise<void>;
  setDiagnosticReport: (report: QBDiagnosticReport | null) => void;
  setIsRunningDiagnostic: (v: boolean) => void;
  clearError: () => void;
}

export const useQuickBooksStore = create<QBState & QBActions>()((set, get) => ({
  connectionStatus: null,
  isLoadingConnection: false,
  templates: [],
  isLoadingTemplates: false,
  selectedTemplate: null,
  mappings: [],
  isLoadingMappings: false,
  syncStats: null,
  isLoadingSyncStats: false,
  diagnosticReport: null,
  isRunningDiagnostic: false,
  fixtures: [],
  error: null,

  loadConnectionStatus: async () => {
    set({ isLoadingConnection: true, error: null });
    try {
      const status = await qbApi.fetchConnectionStatus();
      set({ connectionStatus: status, isLoadingConnection: false });
    } catch {
      // 404 = no connection — that's fine for simulation mode
      set({
        connectionStatus: { is_connected: false },
        isLoadingConnection: false,
      });
    }
  },

  loadTemplates: async () => {
    if (get().isLoadingTemplates) return;
    set({ isLoadingTemplates: true, error: null });
    try {
      const templates = await qbApi.fetchTemplates();
      set({ templates, isLoadingTemplates: false });
    } catch {
      set({ error: "Failed to load templates", isLoadingTemplates: false });
    }
  },

  selectTemplate: (name) => set({ selectedTemplate: name }),

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

  loadFixtures: async () => {
    try {
      const fixtures = await qbApi.fetchTestFixtures();
      set({ fixtures });
    } catch {
      // Non-critical
    }
  },

  setDiagnosticReport: (report) => set({ diagnosticReport: report }),
  setIsRunningDiagnostic: (v) => set({ isRunningDiagnostic: v }),

  clearError: () => set({ error: null }),
}));
