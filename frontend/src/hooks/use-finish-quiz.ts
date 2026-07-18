import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type QuizResultResponse = components["schemas"]["QuizResultResponse"];

async function finishQuiz(attemptId: number): Promise<QuizResultResponse> {
  const { data } = await apiClient.post<QuizResultResponse>(
    `/quizzes/${attemptId}/finish`
  );
  return data;
}

export function useFinishQuiz(attemptId: number) {
  return useMutation({
    mutationFn: () => finishQuiz(attemptId),
  });
}