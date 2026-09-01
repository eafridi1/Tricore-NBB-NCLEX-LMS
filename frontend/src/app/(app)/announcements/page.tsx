"use client";

import { useAnnouncements } from "@/hooks/use-announcements";
import { Card, CardContent } from "@/components/ui/card";

export default function AnnouncementsPage() {
  const { data, isLoading, isError, error } = useAnnouncements();

  // Newest first, by published_at (falling back to created_at).
  const items = data?.items
    ? [...data.items].sort((a, b) => {
        const da = new Date(a.published_at ?? a.created_at).getTime();
        const db = new Date(b.published_at ?? b.created_at).getTime();
        return db - da;
      })
    : [];

  return (
    <main className="mx-auto max-w-2xl px-5 py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Announcements
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Updates and news from the NBB team.
        </p>
      </div>

      {isLoading && (
        <p className="text-sm text-muted-foreground">Loading announcements…</p>
      )}
      {isError && (
        <p className="text-sm text-destructive">
          {error instanceof Error
            ? error.message
            : "Failed to load announcements."}
        </p>
      )}
      {data && items.length === 0 && (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No announcements yet.
          </CardContent>
        </Card>
      )}

      {items.length > 0 && (
        <div className="grid gap-4">
          {items.map((a) => (
            <Card key={a.id}>
              <CardContent className="p-5">
                <h2 className="text-lg font-semibold text-foreground">
                  {a.title}
                </h2>
                <div className="mt-1 text-xs text-muted-foreground/70">
                  {new Date(a.published_at ?? a.created_at).toLocaleDateString(
                    undefined,
                    { year: "numeric", month: "long", day: "numeric" }
                  )}
                </div>
                <div className="mt-3 whitespace-pre-wrap leading-relaxed text-foreground/80">
                  {a.body}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </main>
  );
}