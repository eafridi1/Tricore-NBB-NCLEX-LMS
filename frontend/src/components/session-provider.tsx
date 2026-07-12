"use client";

import { createContext, useContext, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useRefreshSession, type SessionStatus } from "@/hooks/use-refresh-session";
import { onLogout } from "@/lib/auth-events";
import { clearAccessToken } from "@/lib/token-store";

const SessionContext = createContext<SessionStatus>("loading");

export function useSession(): SessionStatus {
  return useContext(SessionContext);
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const status = useRefreshSession();
  const router = useRouter();

  useEffect(() => {
    const unsubscribe = onLogout(() => {
      clearAccessToken();
      router.push("/login");
    });
    return unsubscribe;
  }, [router]);

  if (status === "loading") {
    return <div style={{ padding: 40, fontFamily: "system-ui" }}>Loading…</div>;
  }

  return (
    <SessionContext.Provider value={status}>{children}</SessionContext.Provider>
  );
}