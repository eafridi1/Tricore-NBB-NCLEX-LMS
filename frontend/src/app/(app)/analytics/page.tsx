"use client";

import { useState } from "react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { useMyAnalytics, type AnalyticsPeriod } from "@/hooks/use-my-analytics";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const NAVY = "#0B2540";

type TrendPoint = { date: string; score: number };
type WeakArea = { category_name: string; avg_score: number; attempt_count: number };

export default function AnalyticsPage() {
  const [period, setPeriod] = useState<AnalyticsPeriod>("all");
  const { data, isLoading, isError, error } = useMyAnalytics(period);

  const trend = (data?.score_trend ?? []) as TrendPoint[];
  const weakAreas = (data?.weak_areas ?? []) as WeakArea[];

  return (
    <main className="mx-auto max-w-4xl px-5 py-10">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Your Performance
        </h1>
        <div className="flex gap-1.5">
          {(["weekly", "monthly", "all"] as AnalyticsPeriod[]).map((p) => (
            <Button
              key={p}
              size="sm"
              variant={period === p ? "default" : "outline"}
              onClick={() => setPeriod(p)}
            >
              {p === "weekly" ? "Last week" : p === "monthly" ? "Last month" : "All time"}
            </Button>
          ))}
        </div>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading your analytics…</p>}
      {isError && (
        <p className="text-sm text-destructive">
          {error instanceof Error ? error.message : "Failed to load analytics."}
        </p>
      )}

      {data && (
        <>
          <div className="mb-7 grid grid-cols-3 gap-3">
            <StatCard label="Average Score" value={`${Math.round(data.avg_score)}%`} />
            <StatCard label="Quizzes Taken" value={String(data.total_attempts)} />
            <StatCard
              label="Status"
              value={data.is_at_risk ? "Needs focus" : "On track"}
              valueClass={data.is_at_risk ? "text-red-600" : "text-green-600"}
            />
          </div>

          <section className="mb-8">
            <h2 className="mb-3 text-lg font-semibold text-foreground">Score Over Time</h2>
            {trend.length === 0 ? (
              <Empty>No completed quizzes in this period yet.</Empty>
            ) : (
              <Card>
                <CardContent className="p-4">
                  <div className="h-64 w-full">
                    <ResponsiveContainer>
                      <LineChart data={trend} margin={{ top: 10, right: 20, bottom: 0, left: -10 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                        <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                        <Tooltip />
                        <Line type="monotone" dataKey="score" stroke={NAVY} strokeWidth={2} dot={{ r: 3 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            )}
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-foreground">Performance by Category</h2>
            {weakAreas.length === 0 ? (
              <Empty>Not enough data to show category performance yet.</Empty>
            ) : (
              <Card>
                <CardContent className="p-4">
                  <div className="h-72 w-full">
                    <ResponsiveContainer>
                      <BarChart data={weakAreas} margin={{ top: 10, right: 20, bottom: 40, left: -10 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                        <XAxis dataKey="category_name" tick={{ fontSize: 11 }} angle={-25} textAnchor="end" interval={0} />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                        <Tooltip
                          formatter={(value, _name, item) => [
                            `${Number(value)}% (${(item?.payload as WeakArea)?.attempt_count ?? 0} attempts)`,
                            "Avg score",
                          ]}
                        />
                        <Bar dataKey="avg_score" fill={NAVY} radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            )}
          </section>
        </>
      )}
    </main>
  );
}

function StatCard({
  label, value, valueClass = "text-primary",
}: {
  label: string; value: string; valueClass?: string;
}) {
  return (
    <Card className="bg-muted/40">
      <CardContent className="p-4 text-center">
        <div className={`text-3xl font-bold ${valueClass}`}>{value}</div>
        <div className="mt-1 text-sm text-muted-foreground">{label}</div>
      </CardContent>
    </Card>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <Card>
      <CardContent className="py-8 text-center text-sm text-muted-foreground">
        {children}
      </CardContent>
    </Card>
  );
}