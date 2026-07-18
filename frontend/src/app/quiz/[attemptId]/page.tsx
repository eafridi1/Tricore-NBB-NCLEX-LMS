"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { useQuizQuestion } from "@/hooks/use-quiz-question";
import { useAnswerQuestion } from "@/hooks/use-answer-question";
import { useFinishQuiz } from "@/hooks/use-finish-quiz";
import type { components } from "@/types/api";

type QuizResultResponse = components["schemas"]["QuizResultResponse"];

export default function QuizPage() {
  const params = useParams();
  const attemptId = Number(params.attemptId);

  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [result, setResult] = useState<QuizResultResponse | null>(null);

  const { data: q, isLoading, isError, error } = useQuizQuestion(attemptId, index);
  const answer = useAnswerQuestion(attemptId);
  const finish = useFinishQuiz(attemptId);

  useEffect(() => {
    if (q) setSelected(q.already_answered ?? null);
  }, [q]);

  // ── Results view ──────────────────────────────────────────────
  if (result) {
    return <QuizResults result={result} />;
  }

  if (isLoading) return <Centered>Loading question…</Centered>;
  if (isError)
    return (
      <Centered>
        <span style={{ color: "crimson" }}>
          {error instanceof Error ? error.message : "Failed to load question."}
        </span>
      </Centered>
    );
  if (!q) return null;

  const isLast = q.question_index + 1 >= q.total_questions;

  function handleNext() {
    if (!q || selected === null) return;

    answer.mutate(
      { question_id: q.question_id, chosen_index: selected },
      {
        onSuccess: () => {
          if (isLast) {
            // All answered — finish and capture the result.
            finish.mutate(undefined, {
              onSuccess: (res) => setResult(res),
            });
          } else {
            setIndex((i) => i + 1);
          }
        },
      }
    );
  }

  function handlePrev() {
    if (index > 0) setIndex((i) => i - 1);
  }

  const busy = answer.isPending || finish.isPending;

  return (
    <main style={{ maxWidth: 640, margin: "40px auto", fontFamily: "system-ui" }}>
      <div style={{ fontSize: 13, color: "#666", marginBottom: 8 }}>
        Question {q.question_index + 1} of {q.total_questions} · {q.category_name} ·{" "}
        {q.difficulty}
      </div>

      <h2 style={{ marginBottom: 20, lineHeight: 1.4 }}>{q.stem}</h2>

      <ul style={{ display: "grid", gap: 10, padding: 0, listStyle: "none" }}>
        {q.options.map((opt, i) => {
          const isSelected = selected === i;
          return (
            <li key={i}>
              <button
                onClick={() => setSelected(i)}
                style={{
                  width: "100%",
                  textAlign: "left",
                  border: isSelected ? "2px solid #0B2540" : "1px solid #ddd",
                  background: isSelected ? "#eef2f7" : "white",
                  borderRadius: 8,
                  padding: 12,
                  cursor: "pointer",
                }}
              >
                <strong style={{ marginRight: 8 }}>
                  {String.fromCharCode(65 + i)}.
                </strong>
                {opt.text}
              </button>
            </li>
          );
        })}
      </ul>

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24 }}>
        <button onClick={handlePrev} disabled={index === 0} style={{ padding: 10 }}>
          Previous
        </button>
        <button
          onClick={handleNext}
          disabled={selected === null || busy}
          style={{ padding: 10 }}
        >
          {busy ? "Saving…" : isLast ? "Finish" : "Next"}
        </button>
      </div>

      {(answer.isError || finish.isError) && (
        <p style={{ color: "crimson", marginTop: 12 }}>
          Could not save. Please try again.
        </p>
      )}
    </main>
  );
}

// ── Results component ───────────────────────────────────────────
function QuizResults({ result }: { result: QuizResultResponse }) {
  return (
    <main style={{ maxWidth: 720, margin: "40px auto", fontFamily: "system-ui" }}>
      <div
        style={{
          padding: 20,
          borderRadius: 10,
          background: result.passed ? "#e8f5e9" : "#fdecea",
          border: `1px solid ${result.passed ? "#a5d6a7" : "#f5c6c2"}`,
          marginBottom: 28,
        }}
      >
        <h1 style={{ margin: "0 0 8px" }}>
          {result.passed ? "Passed" : "Not passed"}
        </h1>
        <div style={{ fontSize: 15 }}>
          Score: <strong>{result.score}%</strong> · {result.correct_count}/
          {result.total_questions} correct
          {result.time_taken_secs != null && (
            <> · {Math.round(result.time_taken_secs / 60)} min</>
          )}
        </div>
      </div>

      <h2 style={{ marginBottom: 16 }}>Review</h2>

      <div style={{ display: "grid", gap: 20 }}>
        {result.questions.map((qr, qi) => (
          <div
            key={qr.question_id}
            style={{ border: "1px solid #e0e0e0", borderRadius: 10, padding: 16 }}
          >
            <div style={{ fontSize: 12, color: "#888", marginBottom: 6 }}>
              Q{qi + 1} · {qr.category_name} · {qr.difficulty} ·{" "}
              <span style={{ color: qr.is_correct ? "#2e7d32" : "#c62828" }}>
                {qr.is_correct ? "Correct" : "Incorrect"}
              </span>
            </div>

            <div style={{ marginBottom: 12, lineHeight: 1.4 }}>{qr.stem}</div>

            <ul style={{ display: "grid", gap: 6, padding: 0, listStyle: "none" }}>
              {qr.options.map((opt, i) => {
                const isCorrect = i === qr.correct_answer;
                const isChosen = i === qr.chosen_answer;
                let bg = "white";
                let border = "1px solid #ddd";
                if (isCorrect) {
                  bg = "#e8f5e9";
                  border = "1px solid #a5d6a7";
                } else if (isChosen && !isCorrect) {
                  bg = "#fdecea";
                  border = "1px solid #f5c6c2";
                }
                return (
                  <li
                    key={i}
                    style={{ background: bg, border, borderRadius: 6, padding: 8 }}
                  >
                    <strong style={{ marginRight: 6 }}>
                      {String.fromCharCode(65 + i)}.
                    </strong>
                    {opt.text}
                    {isCorrect && (
                      <span style={{ color: "#2e7d32", marginLeft: 8, fontSize: 12 }}>
                        ✓ correct
                      </span>
                    )}
                    {isChosen && !isCorrect && (
                      <span style={{ color: "#c62828", marginLeft: 8, fontSize: 12 }}>
                        your answer
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>

            <div
              style={{
                marginTop: 12,
                padding: 12,
                background: "#f7f7f7",
                borderRadius: 6,
                fontSize: 14,
                lineHeight: 1.5,
              }}
            >
              <strong>Rationale:</strong> {qr.rationale}
            </div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 28 }}>
        <a href="/dashboard" style={{ color: "#0B2540" }}>
          ← Back to dashboard
        </a>
      </div>
    </main>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ padding: 40, fontFamily: "system-ui", textAlign: "center" }}>
      {children}
    </div>
  );
}