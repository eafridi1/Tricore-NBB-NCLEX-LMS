"use client";

import { useAnnouncements } from "@/hooks/use-announcements";

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
    <main style={{ maxWidth: 640, margin: "40px auto", fontFamily: "system-ui", padding: "0 20px" }}>
      <h1 style={{ marginBottom: 24 }}>Announcements</h1>

      {isLoading && <p>Loading announcements…</p>}

      {isError && (
        <p style={{ color: "crimson" }}>
          {error instanceof Error ? error.message : "Failed to load announcements."}
        </p>
      )}

      {data && items.length === 0 && <p>No announcements yet.</p>}

      {items.length > 0 && (
        <div style={{ display: "grid", gap: 16 }}>
          {items.map((a) => (
            <article
              key={a.id}
              style={{ border: "1px solid #ddd", borderRadius: 10, padding: 16 }}
            >
              <h2 style={{ margin: "0 0 6px", fontSize: 18 }}>{a.title}</h2>
              <div style={{ fontSize: 12, color: "#999", marginBottom: 10 }}>
                {new Date(a.published_at ?? a.created_at).toLocaleDateString(
                  undefined,
                  { year: "numeric", month: "long", day: "numeric" }
                )}
              </div>
              <div style={{ fontSize: 15, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                {a.body}
              </div>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}