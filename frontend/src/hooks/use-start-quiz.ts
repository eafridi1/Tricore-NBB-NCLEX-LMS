import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type QuizStartRequest = components["schemas"]["QuizStartRequest"];
type QuizStartResponse = components["schemas"]["QuizStartResponse"];

async function startQuiz(payload: QuizStartRequest): Promise<QuizStartResponse> {
  const { data } = await apiClient.post<QuizStartResponse>("/quizzes", payload);
  return data;
}

export function useStartQuiz() {
  return useMutation({
    mutationFn: startQuiz,
  });
}