"use client";

import Link from "next/link";
import { useVideos } from "@/hooks/use-videos";
import { useCategories } from "@/hooks/use-categories";

function formatDuration(secs: number | null | undefined): string {
  if (!secs) return "";
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function VideosPage() {
  const { data, isLoading, isError, error } = useVideos();
  const { data: categories } = useCategories();

  const categoryName = (id: number) =>
    categories?.find((c) => c.id === id)?.name ?? "General";

  return (
    <main style={{ maxWidth: 640, margin: "40px auto", fontFamily: "system-ui", padding: "0 20px" }}>
      <h1 style={{ marginBottom: 24 }}>Video Lessons</h1>

      {isLoading && <p>Loading videos…</p>}
      {isError && (
        <p style={{ color: "crimson" }}>
          {error instanceof Error ? error.message : "Failed to load videos."}
        </p>
      )}
      {data && data.items.length === 0 && <p>No video lessons available yet.</p>}

      {data && data.items.length > 0 && (
        <ul style={{ display: "grid", gap: 12, padding: 0, listStyle: "none" }}>
          {data.items.map((video) => (
            <li
              key={video.id}
              style={{ border: "1px solid #ddd", borderRadius: 8, padding: 14 }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: 12,
                }}
              >
                <div>
                  <div style={{ fontWeight: 600 }}>{video.title}</div>
                  {video.description && (
                    <div style={{ fontSize: 14, color: "#666", marginTop: 4 }}>
                      {video.description}
                    </div>
                  )}
                  <div style={{ fontSize: 12, color: "#999", marginTop: 6 }}>
                    {categoryName(video.category_id)}
                    {video.duration_secs
                      ? ` · ${formatDuration(video.duration_secs)}`
                      : ""}
                  </div>
                </div>
                <Link
                  href={`/videos/${video.id}`}
                  style={{
                    padding: "8px 14px",
                    background: "#0B2540",
                    color: "white",
                    borderRadius: 8,
                    textDecoration: "none",
                    whiteSpace: "nowrap",
                    fontSize: 14,
                  }}
                >
                  Watch
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}