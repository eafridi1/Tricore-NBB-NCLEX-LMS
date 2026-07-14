"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/components/session-provider";
import { useAttempts } from "@/hooks/use-attempts";


export default function DashboardPage() {
  const session = useSession();
  const router = useRouter();

  // Route guard: bounce unauthenticated users to /login.
  useEffect(() => {
    if (session === "unauthenticated") {
      router.replace("/login");
    }
  }, [session, router]);

  const { data, isLoading, isError, error } = useAttempts();

  if (session === "unauthenticated") {
    return null; // redirect is in flight
  }

  return (
    <main style={{ maxWidth: 640, margin: "60px auto", fontFamily: "system-ui" }}>
      <h1 style={{ marginBottom: 24 }}>Your Quiz Attempts</h1>
     

      {isLoading && <p>Loading attempts…</p>}

      {isError && (
        <p style={{ color: "crimson" }}>
          {error instanceof Error ? error.message : "Failed to load attempts."}
        </p>
      )}

      {data && data.items.length === 0 && (
        <p>You haven&apos;t taken any quizzes yet.</p>
      )}

      {data && data.items.length > 0 && (
        <ul style={{ display: "grid", gap: 12, padding: 0, listStyle: "none" }}>
          {data.items.map((a) => (
            <li
              key={a.attempt_id}
              style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12 }}
            >
              <div>{a.category_name ?? "General"}</div>
              <div style={{ fontSize: 14, color: "#666" }}>
                Status: {a.status} · Score:{" "}
                {a.score ?? "—"} · {a.correct_count ?? 0}/{a.total_questions} correct
              </div>
              <div style={{ fontSize: 12, color: "#999" }}>
                Started: {new Date(a.started_at).toLocaleString()}
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}