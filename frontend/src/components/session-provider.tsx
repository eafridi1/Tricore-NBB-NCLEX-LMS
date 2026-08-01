"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useRefreshSession, type SessionStatus } from "@/hooks/use-refresh-session";
import { onLogout, onLogin } from "@/lib/auth-events";
import { clearAccessToken } from "@/lib/token-store";

const SessionContext = createContext<SessionStatus>("loading");

export function useSession(): SessionStatus {
  return useContext(SessionContext);
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const bootStatus = useRefreshSession();
  const router = useRouter();

  // Local status seeded by the boot refresh, but overridable by
  // login/logout events that happen after boot.
  const [status, setStatus] = useState<SessionStatus>("loading");

  // Sync from the boot refresh once it resolves.
  useEffect(() => {
    setStatus(bootStatus);
  }, [bootStatus]);

  // React to login/logout that occur after boot.
  useEffect(() => {
    const offLogin = onLogin(() => setStatus("authenticated"));
    const offLogout = onLogout(() => {
      clearAccessToken();
      setStatus("unauthenticated");
      router.push("/login");
    });
    return () => {
      offLogin();
      offLogout();
    };
  }, [router]);

  if (status === "loading") {
    return <div style={{ padding: 40, fontFamily: "system-ui" }}>Loading…</div>;
  }

  return (
    <SessionContext.Provider value={status}>{children}</SessionContext.Provider>
  );
}