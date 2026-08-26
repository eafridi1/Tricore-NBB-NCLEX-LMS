import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type VideoWithProgress = components["schemas"]["VideoWithProgress"];

async function fetchVideo(id: number): Promise<VideoWithProgress> {
  const { data } = await apiClient.get<VideoWithProgress>(`/videos/${id}`);
  return data;
}

export function useVideo(id: number) {
  return useQuery({
    queryKey: ["video", id],
    queryFn: () => fetchVideo(id),
    enabled: Number.isFinite(id) && id > 0,
  });
}