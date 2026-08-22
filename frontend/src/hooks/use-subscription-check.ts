import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type SubscriptionCheckResponse =
  components["schemas"]["SubscriptionCheckResponse"];

async function fetchCheck(): Promise<SubscriptionCheckResponse> {
  const { data } = await apiClient.get<SubscriptionCheckResponse>(
    "/subscriptions/check"
  );
  return data;
}

export function useSubscriptionCheck(options?: {
  refetchInterval?: number | false;
  enabled?: boolean;
}) {
  return useQuery({
    queryKey: ["subscription-check"],
    queryFn: fetchCheck,
    refetchInterval: options?.refetchInterval ?? false,
    enabled: options?.enabled ?? true,
  });
}