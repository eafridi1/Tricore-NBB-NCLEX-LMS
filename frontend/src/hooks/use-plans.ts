import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type PlanOut = components["schemas"]["PlanOut"];

async function fetchPlans(): Promise<PlanOut[]> {
  const { data } = await apiClient.get<PlanOut[]>("/subscriptions/plans");
  return data;
}

export function usePlans() {
  return useQuery({
    queryKey: ["plans"],
    queryFn: fetchPlans,
  });
}