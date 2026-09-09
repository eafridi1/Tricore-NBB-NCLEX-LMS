import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type BookmarkReviewResponse = components["schemas"]["BookmarkReviewResponse"];

async function fetchBookmarksReview(): Promise<BookmarkReviewResponse> {
  const { data } = await apiClient.get<BookmarkReviewResponse>("/bookmarks/review");
  return data;
}

export function useBookmarksReview() {
  return useQuery({
    queryKey: ["bookmarks-review"],
    queryFn: fetchBookmarksReview,
  });
}