import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type UserOut = components["schemas"]["UserOut"];

async function fetchMe(): Promise<UserOut> {
  const { data } = await apiClient.get<UserOut>("/users/me");
  return data;
}

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: fetchMe,
    staleTime: 5 * 60 * 1000, // 5 min — role rarely changes
  });
}