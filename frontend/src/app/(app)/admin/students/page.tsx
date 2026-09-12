"use client";

import { useAtRiskStudents } from "@/hooks/use-at-risk-students";
import { Card, CardContent } from "@/components/ui/card";

export default function AtRiskStudentsPage() {
  const { data, isLoading, isError } = useAtRiskStudents();

  return (
    <main className="mx-auto max-w-3xl px-5 py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          At-Risk Students
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Students with low average scores who may need support.
        </p>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {isError && <p className="text-sm text-destructive">Failed to load.</p>}
      {data && data.length === 0 && (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No at-risk students right now.
          </CardContent>
        </Card>
      )}

      {data && data.length > 0 && (
        <div className="grid gap-3">
          {data.map((s) => (
            <Card key={s.user_id}>
              <CardContent className="flex items-center justify-between gap-3 p-4">
                <div>
                  <div className="font-medium text-foreground">{s.name}</div>
                  <div className="text-sm text-muted-foreground">{s.email}</div>
                  <div className="mt-1 text-xs text-muted-foreground/70">
                    Last attempt: {new Date(s.last_attempt).toLocaleDateString()}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xl font-bold text-red-600">
                    {Math.round(s.avg_score)}%
                  </div>
                  <div className="text-xs text-muted-foreground">avg score</div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </main>
  );
}