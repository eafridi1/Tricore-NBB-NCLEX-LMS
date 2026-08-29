"use client";

import Link from "next/link";
import { useAttempts } from "@/hooks/use-attempts";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function DashboardPage() {
  const { data, isLoading, isError, error } = useAttempts();

  return (
    <main className="mx-auto max-w-2xl px-5 py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Your Quiz Attempts
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Review your progress and pick up where you left off.
        </p>
      </div>

      {isLoading && (
        <p className="text-sm text-muted-foreground">Loading attempts…</p>
      )}
      {isError && (
        <p className="text-sm text-destructive">
          {error instanceof Error ? error.message : "Failed to load attempts."}
        </p>
      )}
      {data && data.items.length === 0 && (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            You haven&apos;t taken any quizzes yet.
          </CardContent>
        </Card>
      )}

      {data && data.items.length > 0 && (
        <ul className="grid gap-3">
          {data.items.map((a) => {
            const isCompleted = a.status === "completed";
            const isInProgress = a.status === "in_progress";
            return (
              <li key={a.attempt_id}>
                <Card className="transition-shadow hover:shadow-md">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <span className="font-medium text-foreground">
                        {a.category_name ?? "General"}
                      </span>
                      <StatusBadge status={a.status} />
                    </div>

                    <div className="mt-1.5 text-sm text-muted-foreground">
                      {isCompleted ? (
                        <>
                          Score: {a.score ?? "—"}% · {a.correct_count ?? 0}/
                          {a.total_questions} correct
                        </>
                      ) : (
                        <>{a.total_questions} questions</>
                      )}
                    </div>

                    <div className="mt-1 text-xs text-muted-foreground/70">
                      Started: {new Date(a.started_at).toLocaleString()}
                    </div>

                    {(isInProgress || isCompleted) && (
                      <div className="mt-3">
                        {isInProgress ? (
                          <Link
                            href={`/quiz/${a.attempt_id}`}
                            className="text-sm font-medium text-primary hover:underline"
                          >
                            Resume →
                          </Link>
                        ) : (
                          <Link
                            href={`/quiz/${a.attempt_id}/result`}
                            className="text-sm font-medium text-primary hover:underline"
                          >
                            View results →
                          </Link>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; className: string }> = {
    in_progress: {
      label: "In progress",
      className: "bg-amber-100 text-amber-800 hover:bg-amber-100",
    },
    completed: {
      label: "Completed",
      className: "bg-green-100 text-green-800 hover:bg-green-100",
    },
    timed_out: {
      label: "Timed out",
      className: "bg-red-100 text-red-800 hover:bg-red-100",
    },
    abandoned: {
      label: "Abandoned",
      className: "bg-muted text-muted-foreground hover:bg-muted",
    },
  };
  const cfg = map[status] ?? {
    label: status,
    className: "bg-muted text-muted-foreground hover:bg-muted",
  };
  return (
    <Badge variant="secondary" className={cfg.className}>
      {cfg.label}
    </Badge>
  );
}