"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCategories } from "@/hooks/use-categories";
import { useStartQuiz } from "@/hooks/use-start-quiz";

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
      {
        onSuccess: (res) => {
          router.push(`/quiz/${res.attempt_id}`);
        },
      }
    );
  }

  return (
    <main style={{ maxWidth: 480, margin: "60px auto", fontFamily: "system-ui" }}>
      <h1 style={{ marginBottom: 24 }}>Start a Quiz</h1>

      <div style={{ display: "grid", gap: 16 }}>
        <label style={{ display: "grid", gap: 4 }}>
          Category
          <select
            value={categoryId ?? ""}
            onChange={(e) =>
              setCategoryId(e.target.value ? Number(e.target.value) : null)
            }
            style={{ padding: 8 }}
          >
            <option value="">All categories</option>
            {categories?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>

        <label style={{ display: "grid", gap: 4 }}>
          Number of questions
          <input
            type="number"
            min={1}
            max={100}
            value={questionCount}
            onChange={(e) => setQuestionCount(Number(e.target.value))}
            style={{ padding: 8 }}
          />
        </label>

        <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            type="checkbox"
            checked={timed}
            onChange={(e) => setTimed(e.target.checked)}
          />
          Timed quiz
        </label>

        {timed && (
          <label style={{ display: "grid", gap: 4 }}>
            Time limit (minutes)
            <input
              type="number"
              min={1}
              value={timeLimitMins}
              onChange={(e) => setTimeLimitMins(Number(e.target.value))}
              style={{ padding: 8 }}
            />
          </label>
        )}

        <button
          onClick={handleStart}
          disabled={startQuiz.isPending || questionCount < 1}
          style={{ padding: 12 }}
        >
          {startQuiz.isPending ? "Starting…" : "Start Quiz"}
        </button>

        {startQuiz.isError && (
          <p style={{ color: "crimson" }}>
            {startQuiz.error instanceof Error
              ? startQuiz.error.message
              : "Could not start quiz."}
          </p>
        )}
      </div>
    </main>
  );
}