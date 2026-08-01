"use client";

import { useState } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useMyAnalytics, type AnalyticsPeriod } from "@/hooks/use-my-analytics";

const NAVY = "#0B2540";

type TrendPoint = { date: string; score: number };
type WeakArea = {
  category_name: string;
  avg_score: number;
  attempt_count: number;
};

export default function AnalyticsPage() {
  const [period, setPeriod] = useState<AnalyticsPeriod>("all");
  const { data, isLoading, isError, error } = useMyAnalytics(period);

  const trend = (data?.score_trend ?? []) as TrendPoint[];
  const weakAreas = (data?.weak_areas ?? []) as WeakArea[];

  return (
    <main style={{ maxWidth: 820, margin: "40px auto", fontFamily: "system-ui", padding: "0 20px" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 24,
        }}
      >
        <h1 style={{ margin: 0 }}>Your Performance</h1>
        <div style={{ display: "flex", gap: 6 }}>
          {(["weekly", "monthly", "all"] as AnalyticsPeriod[]).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              style={{
                padding: "6px 12px",
                fontSize: 13,
                borderRadius: 6,
                border: "1px solid #ddd",
                background: period === p ? NAVY : "white",
                color: period === p ? "white" : "#666",
                cursor: "pointer",
              }}
            >
              {p === "weekly" ? "Last week" : p === "monthly" ? "Last month" : "All time"}
            </button>
          ))}
        </div>
      </div>

      {isLoading && <p>Loading your analytics…</p>}

      {isError && (
        <p style={{ color: "crimson" }}>
          {error instanceof Error ? error.message : "Failed to load analytics."}
        </p>
      )}

      {data && (
        <>
          {/* Summary cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 28 }}>
            <Card label="Average Score" value={`${Math.round(data.avg_score)}%`} />
            <Card label="Quizzes Taken" value={String(data.total_attempts)} />
            <Card
              label="Status"
              value={data.is_at_risk ? "Needs focus" : "On track"}
              valueColor={data.is_at_risk ? "#c62828" : "#2e7d32"}
            />
          </div>

          {/* Score trend */}
          <section style={{ marginBottom: 32 }}>
            <h2 style={{ fontSize: 18, marginBottom: 12 }}>Score Over Time</h2>
            {trend.length === 0 ? (
              <Empty>No completed quizzes in this period yet.</Empty>
            ) : (
              <div style={{ width: "100%", height: 260 }}>
                <ResponsiveContainer>
                  <LineChart data={trend} margin={{ top: 10, right: 20, bottom: 0, left: -10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                    <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="score"
                      stroke={NAVY}
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </section>

          {/* Weak areas */}
          <section>
            <h2 style={{ fontSize: 18, marginBottom: 12 }}>Performance by Category</h2>
            {weakAreas.length === 0 ? (
              <Empty>Not enough data to show category performance yet.</Empty>
            ) : (
              <div style={{ width: "100%", height: 280 }}>
                <ResponsiveContainer>
                  <BarChart
                    data={weakAreas}
                    margin={{ top: 10, right: 20, bottom: 40, left: -10 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                    <XAxis
                      dataKey="category_name"
                      tick={{ fontSize: 11 }}
                      angle={-25}
                      textAnchor="end"
                      interval={0}
                    />
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
            )}
          </section>
        </>
      )}
    </main>
  );
}

function Card({
  label,
  value,
  valueColor = NAVY,
}: {
  label: string;
  value: string;
  valueColor?: string;
}) {
  return (
    <div style={{ background: "#f5f8fb", borderRadius: 10, padding: 16, textAlign: "center" }}>
      <div style={{ fontSize: 28, fontWeight: 700, color: valueColor }}>{value}</div>
      <div style={{ fontSize: 13, color: "#666", marginTop: 4 }}>{label}</div>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ padding: 24, background: "#fafafa", borderRadius: 8, color: "#999", fontSize: 14 }}>
      {children}
    </div>
  );
}