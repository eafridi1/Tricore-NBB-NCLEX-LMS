import { useEffect, useState } from "react";
import { isAxiosError } from "axios";
import { apiClient } from "@/lib/api-client";
import { setAccessToken, clearAccessToken } from "@/lib/token-store";
import type { components } from "@/types/api";

type RefreshResponse = components["schemas"]["RefreshResponse"];

export type SessionStatus = "loading" | "authenticated" | "unauthenticated";

export function useRefreshSession(): SessionStatus {
  const [status, setStatus] = useState<SessionStatus>("loading");

  useEffect(() => {
    let cancelled = false;

    async function attemptRefresh() {
      try {
        const { data } = await apiClient.post<RefreshResponse>("/auth/refresh");
        if (cancelled) return;
        setAccessToken(data.access_token);
        setStatus("authenticated");
      } catch (error) {
        if (cancelled) return;
        clearAccessToken();
        // A 401 here just means "no valid session" — the normal
        // logged-out case, not an error worth surfacing.
        if (isAxiosError(error) && error.response?.status === 401) {
          setStatus("unauthenticated");
        } else {
          // Network failure / backend down — also treat as unauthenticated
          // for routing purposes, but this is the branch to expand later
          // if we want a distinct "server unreachable" state.
          setStatus("unauthenticated");
        }
      }
    }

    attemptRefresh();

    return () => {
      cancelled = true;
    };
  }, []);

  return status;
}