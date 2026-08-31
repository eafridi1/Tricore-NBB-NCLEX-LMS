"use client";

import Link from "next/link";
import { useVideos } from "@/hooks/use-videos";
import { useCategories } from "@/hooks/use-categories";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

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
    <main className="mx-auto max-w-2xl px-5 py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Video Lessons
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Watch lessons to reinforce key NCLEX topics.
        </p>
      </div>

      {isLoading && (
        <p className="text-sm text-muted-foreground">Loading videos…</p>
      )}
      {isError && (
        <p className="text-sm text-destructive">
          {error instanceof Error ? error.message : "Failed to load videos."}
        </p>
      )}
      {data && data.items.length === 0 && (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No video lessons available yet.
          </CardContent>
        </Card>
      )}

      {data && data.items.length > 0 && (
        <ul className="grid gap-3">
          {data.items.map((video) => (
            <li key={video.id}>
              <Card className="transition-shadow hover:shadow-md">
                <CardContent className="flex items-start justify-between gap-3 p-4">
                  <div>
                    <div className="font-medium text-foreground">
                      {video.title}
                    </div>
                    {video.description && (
                      <div className="mt-1 text-sm text-muted-foreground">
                        {video.description}
                      </div>
                    )}
                    <div className="mt-1.5 text-xs text-muted-foreground/70">
                      {categoryName(video.category_id)}
                      {video.duration_secs
                        ? ` · ${formatDuration(video.duration_secs)}`
                        : ""}
                    </div>
                  </div>
                  <Button asChild size="sm">
                    <Link href={`/videos/${video.id}`}>Watch</Link>
                  </Button>
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}