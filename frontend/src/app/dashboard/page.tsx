"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSession } from "@/components/session-provider";
import { useAttempts } from "@/hooks/use-attempts";

export default function DashboardPage() {
  const session = useSession();
  const router = useRouter();

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
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 24,
        }}
      >
        <h1 style={{ margin: 0 }}>Your Quiz Attempts</h1>
        <Link
          href="/quiz/start"
          style={{
            padding: "10px 16px",
            background: "#0B2540",
            color: "white",
            borderRadius: 8,
            textDecoration: "none",
            fontSize: 14,
          }}
        >
          Start Quiz
        </Link>
      </div>

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
          {data.items.map((a) => {
            const inProgress = a.status === "in_progress";
            return (
              <li
                key={a.attempt_id}
                style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12 }}
              >
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>{a.category_name ?? "General"}</span>
                  <span
                    style={{
                      fontSize: 12,
                      padding: "2px 8px",
                      borderRadius: 999,
                      background: inProgress ? "#fff4e5" : "#e8f5e9",
                      color: inProgress ? "#b26a00" : "#2e7d32",
                    }}
                  >
                    {inProgress ? "In progress" : "Completed"}
                  </span>
                </div>

                <div style={{ fontSize: 14, color: "#666", marginTop: 4 }}>
                  {inProgress ? (
                    <>{a.total_questions} questions</>
                  ) : (
                    <>
                      Score: {a.score ?? "—"}% · {a.correct_count ?? 0}/
                      {a.total_questions} correct
                    </>
                  )}
                </div>

                <div style={{ fontSize: 12, color: "#999", marginTop: 4 }}>
                  Started: {new Date(a.started_at).toLocaleString()}
                </div>

                {inProgress && (
                  <div style={{ marginTop: 8 }}>
                    <Link
                      href={`/quiz/${a.attempt_id}`}
                      style={{ fontSize: 13, color: "#0B2540" }}
                    >
                      Resume →
                    </Link>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}