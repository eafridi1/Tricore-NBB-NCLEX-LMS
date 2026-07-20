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
            const badge = statusBadge(a.status);
            const isCompleted = a.status === "completed";
            const isInProgress = a.status === "in_progress";

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
                      background: badge.bg,
                      color: badge.color,
                    }}
                  >
                    {badge.label}
                  </span>
                </div>

                <div style={{ fontSize: 14, color: "#666", marginTop: 4 }}>
                  {isCompleted ? (
                    <>
                      Score: {a.score ?? "—"}% · {a.correct_count ?? 0}/
                      {a.total_questions} correct
                    </>
                  ) : (
                    <>{a.total_questions} questions</>
                  )}
                </div>

                <div style={{ fontSize: 12, color: "#999", marginTop: 4 }}>
                  Started: {new Date(a.started_at).toLocaleString()}
                </div>

                {(isInProgress || isCompleted) && (
                  <div style={{ marginTop: 8 }}>
                    {isInProgress ? (
                      <Link
                        href={`/quiz/${a.attempt_id}`}
                        style={{ fontSize: 13, color: "#0B2540" }}
                      >
                        Resume →
                      </Link>
                    ) : (
                      <Link
                        href={`/quiz/${a.attempt_id}/result`}
                        style={{ fontSize: 13, color: "#0B2540" }}
                      >
                        View results →
                      </Link>
                    )}
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

function statusBadge(status: string): {
  label: string;
  bg: string;
  color: string;
} {
  switch (status) {
    case "in_progress":
      return { label: "In progress", bg: "#fff4e5", color: "#b26a00" };
    case "completed":
      return { label: "Completed", bg: "#e8f5e9", color: "#2e7d32" };
    case "timed_out":
      return { label: "Timed out", bg: "#fdecea", color: "#c62828" };
    case "abandoned":
      return { label: "Abandoned", bg: "#f0f0f0", color: "#777" };
    default:
      return { label: status, bg: "#f0f0f0", color: "#777" };
  }
}