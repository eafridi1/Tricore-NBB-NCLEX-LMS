"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCategories } from "@/hooks/use-categories";
import { useStartQuiz } from "@/hooks/use-start-quiz";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function QuizStartPage() {
  const router = useRouter();
  const { data: categories } = useCategories();
  const startQuiz = useStartQuiz();

  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [questionCount, setQuestionCount] = useState(10);
  const [timed, setTimed] = useState(false);
  const [timeLimitMins, setTimeLimitMins] = useState(45);

  function handleStart() {
    startQuiz.mutate(
      {
        category_id: categoryId,
        difficulty: null,
        question_count: questionCount,
        timed,
        time_limit_secs: timed ? timeLimitMins * 60 : null,
      },
      { onSuccess: (res) => router.push(`/quiz/${res.attempt_id}`) }
    );
  }

  return (
    <main className="mx-auto max-w-md px-5 py-14">
      <h1 className="mb-6 text-2xl font-semibold tracking-tight text-foreground">
        Start a Quiz
      </h1>

      <Card>
        <CardContent className="grid gap-5 p-6">
          <div className="grid gap-1.5">
            <Label htmlFor="category">Category</Label>
            <select
              id="category"
              value={categoryId ?? ""}
              onChange={(e) =>
                setCategoryId(e.target.value ? Number(e.target.value) : null)
              }
              className="h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="">All categories</option>
              {categories?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="count">Number of questions</Label>
            <Input
              id="count"
              type="number"
              min={1}
              max={100}
              value={questionCount}
              onChange={(e) => setQuestionCount(Number(e.target.value))}
            />
          </div>

          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={timed}
              onChange={(e) => setTimed(e.target.checked)}
              className="h-4 w-4 accent-primary"
            />
            Timed quiz
          </label>

          {timed && (
            <div className="grid gap-1.5">
              <Label htmlFor="limit">Time limit (minutes)</Label>
              <Input
                id="limit"
                type="number"
                min={1}
                value={timeLimitMins}
                onChange={(e) => setTimeLimitMins(Number(e.target.value))}
              />
            </div>
          )}

          <Button
            onClick={handleStart}
            disabled={startQuiz.isPending || questionCount < 1}
          >
            {startQuiz.isPending ? "Starting…" : "Start Quiz"}
          </Button>

          {startQuiz.isError && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {startQuiz.error instanceof Error
                ? startQuiz.error.message
                : "Could not start quiz."}
            </p>
          )}
        </CardContent>
      </Card>
    </main>
  );
}