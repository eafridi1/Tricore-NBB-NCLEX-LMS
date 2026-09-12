import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type AtRiskStudent = components["schemas"]["AtRiskStudent"];

async function fetchAtRisk(): Promise<AtRiskStudent[]> {
  const { data } = await apiClient.get<AtRiskStudent[]>("/admin/analytics/students");
  return data;
}

export function useAtRiskStudents() {
  return useQuery({
    queryKey: ["at-risk-students"],
    queryFn: fetchAtRisk,
  });
}