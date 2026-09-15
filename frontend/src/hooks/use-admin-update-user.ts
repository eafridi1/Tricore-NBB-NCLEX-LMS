import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

async function updateUser(vars: {
  id: number;
  role?: string;
  is_active?: boolean;
}): Promise<void> {
  const { id, ...body } = vars;
  await apiClient.patch(`/users/${id}`, body);
}

export function useAdminUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: updateUser,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });
}