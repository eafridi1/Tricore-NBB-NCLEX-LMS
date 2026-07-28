"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSession } from "@/components/session-provider";
import { useAnnouncements } from "@/hooks/use-announcements";

export default function AnnouncementsPage() {
  const session = useSession();
  const router = useRouter();

  useEffect(() => {
    if (session === "unauthenticated") {
      router.replace("/login");
    }
  }, [session, router]);

  const { data, isLoading, isError, error } = useAnnouncements();

  if (session === "unauthenticated") return null;

  // Newest first, by published_at (falling back to created_at).
  const items = data?.items
    ? [...data.items].sort((a, b) => {
        const da = new Date(a.published_at ?? a.created_at).getTime();
        const db = new Date(b.published_at ?? b.created_at).getTime();
        return db - da;
      })
    : [];

  return (
    <main style={{ maxWidth: 640, margin: "60px auto", fontFamily: "system-ui" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 24,
        }}
      >
        <h1 style={{ margin: 0 }}>Announcements</h1>
        <Link href="/dashboard" style={{ fontSize: 14, color: "#0B2540" }}>
          ← Dashboard
        </Link>
      </div>

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