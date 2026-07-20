import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type QuizResultResponse = components["schemas"]["QuizResultResponse"];

async function fetchResult(attemptId: number): Promise<QuizResultResponse> {
  const { data } = await apiClient.get<QuizResultResponse>(
    `/quizzes/${attemptId}/result`
  );
  return data;
}

export function useQuizResult(attemptId: number) {
  return useQuery({
    queryKey: ["quiz-result", attemptId],
    queryFn: () => fetchResult(attemptId),
    retry: false,
  });
}