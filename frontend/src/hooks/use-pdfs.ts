import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type PDFListResponse = components["schemas"]["PDFListResponse"];

async function fetchPdfs(): Promise<PDFListResponse> {
  const { data } = await apiClient.get<PDFListResponse>("/pdfs");
  return data;
}

export function usePdfs() {
  return useQuery({
    queryKey: ["pdfs"],
    queryFn: fetchPdfs,
  });
}