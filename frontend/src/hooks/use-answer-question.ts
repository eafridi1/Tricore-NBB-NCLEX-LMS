import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type AnswerRequest = components["schemas"]["AnswerRequest"];
type AnswerResponse = components["schemas"]["AnswerResponse"];

async function submitAnswer(
  attemptId: number,
  payload: AnswerRequest
): Promise<AnswerResponse> {
  const { data } = await apiClient.post<AnswerResponse>(
    `/quizzes/${attemptId}/answer`,
    payload
  );
  return data;
}

export function useAnswerQuestion(attemptId: number) {
  return useMutation({
    mutationFn: (payload: AnswerRequest) => submitAnswer(attemptId, payload),
  });
}