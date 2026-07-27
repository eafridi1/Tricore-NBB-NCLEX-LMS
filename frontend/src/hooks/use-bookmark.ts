import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

async function addBookmark(questionId: number): Promise<void> {
  await apiClient.post(`/questions/${questionId}/bookmark`);
}

async function removeBookmark(questionId: number): Promise<void> {
  await apiClient.delete(`/questions/${questionId}/bookmark`);
}

export function useBookmark() {
  const add = useMutation({ mutationFn: addBookmark });
  const remove = useMutation({ mutationFn: removeBookmark });

  return {
    add,
    remove,
    isPending: add.isPending || remove.isPending,
  };
}