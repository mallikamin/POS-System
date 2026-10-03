import { create } from "zustand";
import { persist } from "zustand/middleware";
import api from "@/lib/axios";
import { getTenantSlug } from "@/lib/tenant";
import type { User, AuthTokens } from "@/types";
import { useMenuStore } from "@/stores/menuStore";
import { useConfigStore } from "@/stores/configStore";
import { useUIStore } from "@/stores/uiStore";

interface AuthState {
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

interface AuthActions {
  loginWithPin: (pin: string) => Promise<void>;
  loginWithPassword: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  refreshUser: () => Promise<void>;
  setLoading: (loading: boolean) => void;
}

type AuthStore = AuthState & AuthActions;

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      /* ---- State ---- */
      user: null,
      tokens: null,
      isAuthenticated: false,
      isLoading: false,

      /* ---- Actions ---- */
      loginWithPin: async (pin: string) => {
        set({ isLoading: true });
        try {
          // A PIN is only unique within one restaurant, so the server refuses
          // to guess when it hosts more than one. Undefined is fine and is the
          // normal case for a single-restaurant deployment. See lib/tenant.ts.
          const { data } = await api.post<{ user: User; tokens: AuthTokens }>(
            "/auth/login/pin",
            { pin, tenant_slug: getTenantSlug() }
          );
          set({
            user: data.user,
            tokens: data.tokens,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      loginWithPassword: async (email: string, password: string) => {
        set({ isLoading: true });
        try {
          const { data } = await api.post<{ user: User; tokens: AuthTokens }>(
            "/auth/login",
            { email, password, tenant_slug: getTenantSlug() }
          );
          set({
            user: data.user,
            tokens: data.tokens,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      logout: () => {
        const tokens = get().tokens;
        if (tokens) {
          // Fire-and-forget logout call
          api.post("/auth/logout", { refresh_token: tokens.refresh_token }).catch(() => {
            // Ignore errors during logout
          });
        }
        set({
          user: null,
          tokens: null,
          isAuthenticated: false,
          isLoading: false,
        });
        // Clear all other stores on logout
        useMenuStore.getState().clearMenu();
        useConfigStore.getState().clearConfig();
        useUIStore.getState().resetUi();
      },

      refreshToken: async () => {
        const tokens = get().tokens;
        if (!tokens?.refresh_token) {
          get().logout();
          return;
        }
        try {
          const { data } = await api.post<AuthTokens>("/auth/refresh", {
            refresh_token: tokens.refresh_token,
          });
          set({ tokens: data });
        } catch {
          get().logout();
        }
      },

      /**
       * Re-read the signed-in user from the server. `user` is persisted from
       * login, so without this a rename or role change made in Admin > Staff
       * stayed invisible until the next login. Errors are ignored: a dead
       * session is handled by the axios 401 path.
       */
      refreshUser: async () => {
        if (!get().isAuthenticated) return;
        try {
          const { data } = await api.get<User>("/auth/me");
          set({ user: data });
        } catch {
          // keep the cached user
        }
      },

      setLoading: (loading: boolean) => {
        set({ isLoading: loading });
      },
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({
        user: state.user,
        tokens: state.tokens,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
