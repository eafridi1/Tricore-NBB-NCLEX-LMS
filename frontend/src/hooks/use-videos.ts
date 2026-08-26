import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type VideoListResponse = components["schemas"]["VideoListResponse"];

async function fetchVideos(): Promise<VideoListResponse> {
  const { data } = await apiClient.get<VideoListResponse>("/videos");
  return data;
}

export function useVideos() {
  return useQuery({
    queryKey: ["videos"],
    queryFn: fetchVideos,
  });
}