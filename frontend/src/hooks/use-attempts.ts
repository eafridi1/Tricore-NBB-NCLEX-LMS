import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type AttemptListResponse = components["schemas"]["AttemptListResponse"];

async function fetchAttempts(): Promise<AttemptListResponse> {
  const { data } = await apiClient.get<AttemptListResponse>("/quizzes");
  return data;
}

export function useAttempts() {
  return useQuery({
    queryKey: ["attempts"],
    queryFn: fetchAttempts,
  });
}