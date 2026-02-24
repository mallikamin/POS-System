import axios from "axios";
import { toast } from "@/hooks/use-toast";

const envBase = import.meta.env.VITE_API_URL || "/api";
// Ensure the base always ends with /v1 regardless of what the env var contains
const baseURL = envBase.replace(/\/+$/, "").endsWith("/v1")
  ? envBase
  : `${envBase.replace(/\/+$/, "")}/v1`;

const api = axios.create({
  baseURL,
  headers: {
    "Content-Type": "application/json",
  },
});

/** Read access token from persisted auth store */
export function getAccessToken(): string | null {
  try {
    const stored = localStorage.getItem("auth-storage");
    if (!stored) return null;
    const parsed = JSON.parse(stored) as {
      state?: { tokens?: { access_token?: string } };
    };
    return parsed?.state?.tokens?.access_token ?? null;
  } catch {
    return null;
  }
}

/** Attach access token to every outgoing request */
api.interceptors.request.use(
  (config) => {
    const token = getAccessToken();
    if (token) {
      config.headers.set("Authorization", `Bearer ${token}`);
    }
    return config;
  },
  (error) => Promise.reject(error)
);

/** Track whether we are already refreshing to avoid infinite loops */
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null) {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else if (token) {
      prom.resolve(token);
    }
  });
  failedQueue = [];
}

/** On 401 attempt a token refresh; on refresh failure redirect to /login */
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/login") &&
      !originalRequest.url?.includes("/auth/refresh")
    ) {
      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.set("Authorization", `Bearer ${token}`);
          return api(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const stored = localStorage.getItem("auth-storage");
        if (!stored) throw new Error("No stored auth");

        const parsed = JSON.parse(stored) as {
          state?: { tokens?: { refresh_token?: string } };
        };
        const refreshToken = parsed?.state?.tokens?.refresh_token;
        if (!refreshToken) throw new Error("No refresh token");

        const { data } = await axios.post<{
          access_token: string;
          refresh_token: string;
          token_type: string;
        }>(`${api.defaults.baseURL}/auth/refresh`, {
          refresh_token: refreshToken,
        });

        // Update stored tokens — re-read in case Zustand wrote between await
        const freshStored = localStorage.getItem("auth-storage") ?? stored;
        const current = JSON.parse(freshStored);
        current.state.tokens = data;
        localStorage.setItem("auth-storage", JSON.stringify(current));

        processQueue(null, data.access_token);

        originalRequest.headers.set("Authorization", `Bearer ${data.access_token}`);
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        localStorage.removeItem("auth-storage");
        window.location.href = "/login";
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // Show toast for non-401 server errors (401 handled by refresh logic above)
    if (error.response && error.response.status !== 401) {
      const status = error.response.status as number;
      const detail =
        (error.response.data as { detail?: string })?.detail ??
        error.response.statusText ??
        "Something went wrong";

      if (status >= 500) {
        toast({
          variant: "destructive",
          title: "Server Error",
          description: detail,
        });
      } else if (status === 403) {
        toast({
          variant: "destructive",
          title: "Access Denied",
          description: "You don't have permission for this action.",
        });
      }
      // 400/404/409 etc. — let individual pages handle with specific messages
    } else if (!error.response && error.message !== "canceled") {
      // Network error
      toast({
        variant: "destructive",
        title: "Network Error",
        description: "Unable to reach the server. Check your connection.",
      });
    }

    return Promise.reject(error);
  }
);

export default api;
