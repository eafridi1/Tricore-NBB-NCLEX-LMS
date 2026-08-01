import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type StudentAnalyticsResponse = components["schemas"]["StudentAnalyticsResponse"];

export type AnalyticsPeriod = "weekly" | "monthly" | "all";

async function fetchMyAnalytics(
  period: AnalyticsPeriod
): Promise<StudentAnalyticsResponse> {
  const { data } = await apiClient.get<StudentAnalyticsResponse>(
    "/admin/analytics/me",
    { params: { period } }
  );
  return data;
}

export function useMyAnalytics(period: AnalyticsPeriod) {
  return useQuery({
    queryKey: ["my-analytics", period],
    queryFn: () => fetchMyAnalytics(period),
  });
}