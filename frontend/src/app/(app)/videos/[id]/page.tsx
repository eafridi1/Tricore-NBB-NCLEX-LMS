"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useVideo } from "@/hooks/use-video";

export default function VideoPlayerPage() {
  const params = useParams();
  const id = Number(params?.id);
  const { data: video, isLoading, isError, error } = useVideo(id);

  return (
    <main className="mx-auto max-w-3xl px-5 py-10">
      <Link
        href="/videos"
        className="text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        ← Back to Video Lessons
      </Link>

      {isLoading && (
        <p className="mt-5 text-sm text-muted-foreground">Loading video…</p>
      )}
      {isError && (
        <p className="mt-5 text-sm text-destructive">
          {error instanceof Error ? error.message : "Failed to load video."}
        </p>
      )}

      {video && (
        <>
          <h1 className="mt-4 mb-3 text-2xl font-semibold tracking-tight text-foreground">
            {video.title}
          </h1>

          <div className="mb-4 aspect-video overflow-hidden rounded-lg bg-black">
            <video
              key={video.stream_url}
              controls
              poster={video.thumbnail_url ?? undefined}
              className="h-full w-full"
            >
              <source src={video.stream_url} />
              Your browser does not support the video tag.
            </video>
          </div>

          {video.description && (
            <p className="leading-relaxed text-foreground/80">
              {video.description}
            </p>
          )}

          {typeof video.percent_watched === "number" &&
            video.percent_watched > 0 && (
              <div className="mt-2 text-sm text-muted-foreground/70">
                {Math.round(video.percent_watched)}% watched
              </div>
            )}
        </>
      )}
    </main>
  );
}