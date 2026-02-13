import axios from "axios";

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

/** Attach access token to every outgoing request */
api.interceptors.request.use(
  (config) => {
    const stored = localStorage.getItem("auth-storage");
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as {
          state?: { tokens?: { access_token?: string } };
        };
        const token = parsed?.state?.tokens?.access_token;
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      } catch {
        // Ignore malformed storage
      }
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
      !originalRequest.url?.includes("/auth/refresh")
    ) {
      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
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

        // Update stored tokens
        const current = JSON.parse(stored);
        current.state.tokens = data;
        localStorage.setItem("auth-storage", JSON.stringify(current));

        processQueue(null, data.access_token);

        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
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

    return Promise.reject(error);
  }
);

export default api;
