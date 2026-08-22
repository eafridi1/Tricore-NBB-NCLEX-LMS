import axios, {
  isAxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from "axios";
import { getAccessToken, setAccessToken, clearAccessToken } from "@/lib/token-store";
import { emitLogout } from "@/lib/auth-events";
import type { components } from "@/types/api";

type RefreshResponse = components["schemas"]["RefreshResponse"];

export const apiClient = axios.create({
  baseURL: "/api",
  withCredentials: true,
});

// Endpoints that must NOT receive a bearer token and must NOT trigger
// the 401 refresh-retry cycle (they either establish the session or are
// the refresh call itself — intercepting them causes infinite loops).
const AUTH_FREE_PATHS = [
  "/auth/login",
  "/auth/2fa-verify",
  "/auth/register",
  "/auth/refresh",
];

function isAuthFreePath(url: string | undefined): boolean {
  if (!url) return false;
  return AUTH_FREE_PATHS.some((p) => url.startsWith(p));
}

// ── Request interceptor: attach bearer token ──────────────────────────
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (!isAuthFreePath(config.url)) {
    const token = getAccessToken();
    if (token) {
      config.headers.set("Authorization", `Bearer ${token}`);
    }
  }
  return config;
});

// ── Response interceptor: single-flight refresh + retry ───────────────
// Shared promise so concurrent 401s wait on ONE refresh, not N.
let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  try {
    // Bare axios (not apiClient) so this call skips the interceptors
    // entirely — belt-and-suspenders against loops.
    const { data } = await axios.post<RefreshResponse>(
      "/api/auth/refresh",
      null,
      { withCredentials: true }
    );
    setAccessToken(data.access_token);
    return data.access_token;
  } catch {
    clearAccessToken();
    return null;
  }
}

interface RetriableConfig extends AxiosRequestConfig {
  _retried?: boolean;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (!isAxiosError(error) || !error.response) {
      return Promise.reject(error);
    }

    const original = error.config as RetriableConfig | undefined;
    const status = error.response.status;

        // 402 = authenticated but no active subscription (gated content).
    // Send the user to the subscribe page rather than surfacing a raw error.
    // Guard against a loop if somehow already heading there.
    if (status === 402) {
      if (
        typeof window !== "undefined" &&
        !window.location.pathname.startsWith("/subscribe")
      ) {
        window.location.href = "/subscribe";
      }
      return Promise.reject(error);
    }

    // Only act on 401s, never on the auth-free paths, and only once.
    if (
      status !== 401 ||
      !original ||
      original._retried ||
      isAuthFreePath(original.url)
    ) {
      return Promise.reject(error);
    }

    original._retried = true;

    // Single-flight: first 401 kicks off the refresh; others await it.
    if (!refreshPromise) {
      refreshPromise = refreshAccessToken().finally(() => {
        refreshPromise = null;
      });
    }
    const newToken = await refreshPromise;

    if (!newToken) {
      // Session is genuinely dead — tell React to redirect.
      emitLogout();
      return Promise.reject(error);
    }

    // Retry the original request with the fresh token.
    original.headers = original.headers ?? {};
    (original.headers as Record<string, string>)["Authorization"] =
      `Bearer ${newToken}`;
    return apiClient(original);
  }
);