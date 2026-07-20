import { useQuery } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type QuizResumeResponse = components["schemas"]["QuizResumeResponse"];

export type ResumeState =
  | { kind: "resumable"; data: QuizResumeResponse }
  | { kind: "ended"; reason: string }
  | { kind: "loading" }
  | { kind: "error"; message: string };

async function fetchResume(attemptId: number): Promise<QuizResumeResponse> {
  const { data } = await apiClient.get<QuizResumeResponse>(
    `/quizzes/${attemptId}/resume`
  );
  return data;
}

export function useResumeQuiz(attemptId: number) {
  return useQuery<QuizResumeResponse, unknown>({
    queryKey: ["resume", attemptId],
    queryFn: () => fetchResume(attemptId),
    retry: false, // a 409 is a definitive answer, not a transient failure
  });
}

// Helper: interpret the query result into a clear state.
export function interpretResume(
  isLoading: boolean,
  isError: boolean,
  error: unknown,
  data: QuizResumeResponse | undefined
): ResumeState {
  if (isLoading) return { kind: "loading" };
  if (isError) {
    if (isAxiosError(error) && error.response?.status === 409) {
      const detail = error.response.data?.detail;
      const reason =
        typeof detail === "object" && detail?.detail
          ? detail.detail
          : typeof detail === "string"
          ? detail
          : "attempt_not_in_progress";
      return { kind: "ended", reason };
    }
    return {
      kind: "error",
      message: error instanceof Error ? error.message : "Failed to load attempt.",
    };
  }
  if (data) return { kind: "resumable", data };
  return { kind: "loading" };
}