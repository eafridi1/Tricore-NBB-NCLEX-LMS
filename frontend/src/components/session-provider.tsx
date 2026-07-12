"use client";

import { createContext, useContext } from "react";
import { useRefreshSession, type SessionStatus } from "@/hooks/use-refresh-session";

const SessionContext = createContext<SessionStatus>("loading");

export function useSession(): SessionStatus {
  return useContext(SessionContext);
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const status = useRefreshSession();

  if (status === "loading") {
    return (
      <div style={{ padding: 40, fontFamily: "system-ui" }}>Loading…</div>
    );
  }

  return (
    <SessionContext.Provider value={status}>{children}</SessionContext.Provider>
  );
}