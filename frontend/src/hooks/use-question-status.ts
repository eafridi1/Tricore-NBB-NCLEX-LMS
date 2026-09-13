import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

async function setStatus(vars: { id: number; status: string }): Promise<void> {
  await apiClient.patch(`/questions/${vars.id}/status`, { status: vars.status });
}

export function useQuestionStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: setStatus,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-questions"] }),
  });
}