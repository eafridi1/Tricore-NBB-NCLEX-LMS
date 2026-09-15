import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type UserListResponse = components["schemas"]["UserListResponse"];

async function fetchUsers(): Promise<UserListResponse> {
  const { data } = await apiClient.get<UserListResponse>("/users", {
    params: { per_page: 100 },
  });
  return data;
}

export function useAdminUsers() {
  return useQuery({ queryKey: ["admin-users"], queryFn: fetchUsers });
}