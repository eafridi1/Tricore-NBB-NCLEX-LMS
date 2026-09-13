"use client";

import { useAdminQuestions } from "@/hooks/use-admin-questions";
import { useQuestionStatus } from "@/hooks/use-question-status";
import { Card, CardContent } from "@/components/ui/card";

const STATUSES = ["draft", "in_review", "published", "archived"];

export default function AdminQuestionsPage() {
  const { data, isLoading, isError } = useAdminQuestions();
  const statusM = useQuestionStatus();

  return (
    <main className="mx-auto max-w-3xl px-5 py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Questions
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Manage the question bank and publishing status.
        </p>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {isError && <p className="text-sm text-destructive">Failed to load.</p>}
      {data && data.items.length === 0 && (
        <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">No questions yet.</CardContent></Card>
      )}

      {data && data.items.length > 0 && (
        <div className="grid gap-3">
          {data.items.map((q) => (
            <Card key={q.id}>
              <CardContent className="flex items-start justify-between gap-3 p-4">
                <div className="min-w-0">
                  <div className="truncate font-medium text-foreground">{q.stem}</div>
                  <div className="mt-1 text-xs text-muted-foreground/70">
                    {q.difficulty}
                  </div>
                </div>
                                <select
                  value={q.status}
                  disabled={statusM.isPending}
                  onChange={(e) => statusM.mutate({ id: q.id, status: e.target.value })}
                  className="h-8 shrink-0 rounded-md border border-input bg-background text-foreground px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {STATUSES.map((s) => (
                    <option key={s} value={s} className="bg-background text-foreground">{s}</option>
                  ))}
                </select>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </main>
  );
}