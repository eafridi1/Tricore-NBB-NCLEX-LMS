import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type DashboardStatsResponse = components["schemas"]["DashboardStatsResponse"];

async function fetchAdminStats(): Promise<DashboardStatsResponse> {
  const { data } = await apiClient.get<DashboardStatsResponse>("/admin/stats");
  return data;
}

export function useAdminStats() {
  return useQuery({
    queryKey: ["admin-stats"],
    queryFn: fetchAdminStats,
  });
}