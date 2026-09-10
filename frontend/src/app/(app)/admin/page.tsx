"use client";

import { useAdminStats } from "@/hooks/use-admin-stats";
import { Card, CardContent } from "@/components/ui/card";

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="p-5 text-center">
        <div className="text-3xl font-bold text-primary">{value}</div>
        <div className="mt-1 text-sm text-muted-foreground">{label}</div>
      </CardContent>
    </Card>
  );
}

export default function AdminOverviewPage() {
  const { data, isLoading, isError, error } = useAdminStats();

  function money(cents: number): string {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: "USD",
    }).format(cents / 100);
  }

  return (
    <main className="mx-auto max-w-5xl px-5 py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Overview
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Platform stats at a glance.
        </p>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading stats…</p>}
      {isError && (
        <p className="text-sm text-destructive">
          {error instanceof Error ? error.message : "Failed to load stats."}
        </p>
      )}

      {data && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          <StatCard label="Total Students" value={String(data.total_students)} />
          <StatCard label="Active Subscribers" value={String(data.active_subscribers)} />
          <StatCard label="Revenue This Month" value={money(data.revenue_this_month_cents)} />
          <StatCard label="Total Questions" value={String(data.total_questions)} />
          <StatCard label="Published Questions" value={String(data.published_questions)} />
          <StatCard label="Attempts Today" value={String(data.total_attempts_today)} />
        </div>
      )}
    </main>
  );
}