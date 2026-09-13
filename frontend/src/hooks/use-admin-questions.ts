import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type QuestionListResponse = components["schemas"]["QuestionListResponse"];

async function fetchQuestions(): Promise<QuestionListResponse> {
  const { data } = await apiClient.get<QuestionListResponse>("/questions", {
    params: { per_page: 100 },
  });
  return data;
}

export function useAdminQuestions() {
  return useQuery({ queryKey: ["admin-questions"], queryFn: fetchQuestions });
}