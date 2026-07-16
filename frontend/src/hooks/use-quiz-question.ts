import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type QuizQuestionResponse = components["schemas"]["QuizQuestionResponse"];

async function fetchQuestion(
  attemptId: number,
  index: number
): Promise<QuizQuestionResponse> {
  const { data } = await apiClient.get<QuizQuestionResponse>(
    `/quizzes/${attemptId}/question/${index}`
  );
  return data;
}

export function useQuizQuestion(attemptId: number, index: number) {
  return useQuery({
    queryKey: ["quiz-question", attemptId, index],
    queryFn: () => fetchQuestion(attemptId, index),
  });
}