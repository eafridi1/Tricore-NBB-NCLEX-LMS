"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { useQuizQuestion } from "@/hooks/use-quiz-question";
import { useAnswerQuestion } from "@/hooks/use-answer-question";

export default function QuizPage() {
  const params = useParams();
  const attemptId = Number(params.attemptId);

  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [finished, setFinished] = useState(false);

  const { data: q, isLoading, isError, error } = useQuizQuestion(attemptId, index);
  const answer = useAnswerQuestion(attemptId);

  // When a new question loads, reflect any previously-saved answer.
  useEffect(() => {
    if (q) {
      setSelected(q.already_answered ?? null);
    }
  }, [q]);

  if (finished) {
    return (
      <Centered>
        <div>
          <h2>Quiz complete</h2>
          <p style={{ color: "#666" }}>
            Your answers are saved. Results and scoring come in the next step.
          </p>
        </div>
      </Centered>
    );
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
    if (!q) return;
    if (selected === null) return; // require a selection to advance

    answer.mutate(
      { question_id: q.question_id, chosen_index: selected },
      {
        onSuccess: () => {
          if (isLast) {
            setFinished(true);
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
          disabled={selected === null || answer.isPending}
          style={{ padding: 10 }}
        >
          {answer.isPending ? "Saving…" : isLast ? "Finish" : "Next"}
        </button>
      </div>

      {answer.isError && (
        <p style={{ color: "crimson", marginTop: 12 }}>
          {answer.error instanceof Error
            ? answer.error.message
            : "Could not save answer."}
        </p>
      )}
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