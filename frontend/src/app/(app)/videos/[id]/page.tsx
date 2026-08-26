"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useVideo } from "@/hooks/use-video";

export default function VideoPlayerPage() {
  const params = useParams();
  const id = Number(params?.id);
  const { data: video, isLoading, isError, error } = useVideo(id);

  return (
    <main style={{ maxWidth: 800, margin: "40px auto", fontFamily: "system-ui", padding: "0 20px" }}>
      <Link href="/videos" style={{ fontSize: 14, color: "#666", textDecoration: "none" }}>
        ← Back to Video Lessons
      </Link>

      {isLoading && <p style={{ marginTop: 20 }}>Loading video…</p>}
      {isError && (
        <p style={{ color: "crimson", marginTop: 20 }}>
          {error instanceof Error ? error.message : "Failed to load video."}
        </p>
      )}

      {video && (
        <>
          <h1 style={{ margin: "16px 0 12px" }}>{video.title}</h1>

          <div
            style={{
              background: "#000",
              borderRadius: 10,
              overflow: "hidden",
              aspectRatio: "16 / 9",
              marginBottom: 16,
            }}
          >
            <video
              key={video.stream_url}
              controls
              poster={video.thumbnail_url ?? undefined}
              style={{ width: "100%", height: "100%" }}
            >
              <source src={video.stream_url} />
              Your browser does not support the video tag.
            </video>
          </div>

          {video.description && (
            <p style={{ color: "#444", lineHeight: 1.6 }}>{video.description}</p>
          )}

          {typeof video.percent_watched === "number" && video.percent_watched > 0 && (
            <div style={{ fontSize: 13, color: "#999", marginTop: 8 }}>
              {Math.round(video.percent_watched)}% watched
            </div>
          )}
        </>
      )}
    </main>
  );
}