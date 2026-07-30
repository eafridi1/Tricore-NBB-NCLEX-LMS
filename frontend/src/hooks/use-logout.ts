import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api-client";
import { clearAccessToken } from "@/lib/token-store";

export function useLogout() {
  const router = useRouter();
  const [isPending, setIsPending] = useState(false);

  async function run() {
    setIsPending(true);
    try {
      await apiClient.post("/auth/logout");
    } catch {
      // Even if the server call fails, log out client-side anyway.
    } finally {
      clearAccessToken();
      setIsPending(false);
      router.replace("/login");
    }
  }

  return { run, isPending };
}