import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type CategoryOut = components["schemas"]["CategoryOut"];

async function fetchCategories(): Promise<CategoryOut[]> {
  const { data } = await apiClient.get<CategoryOut[]>("/categories");
  return data;
}

export function useCategories() {
  return useQuery({
    queryKey: ["categories"],
    queryFn: fetchCategories,
  });
}