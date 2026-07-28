import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type AnnouncementListResponse = components["schemas"]["AnnouncementListResponse"];

async function fetchAnnouncements(): Promise<AnnouncementListResponse> {
  const { data } = await apiClient.get<AnnouncementListResponse>("/announcements");
  return data;
}

export function useAnnouncements() {
  return useQuery({
    queryKey: ["announcements"],
    queryFn: fetchAnnouncements,
  });
}