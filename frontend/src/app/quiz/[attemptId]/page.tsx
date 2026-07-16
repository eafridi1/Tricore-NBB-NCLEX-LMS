"use client";

import { useParams } from "next/navigation";
import { useQuizQuestion } from "@/hooks/use-quiz-question";

export default function QuizPage() {
  const params = useParams();
  const attemptId = Number(params.attemptId);

  const { data: q, isLoading, isError, error } = useQuizQuestion(attemptId, 0);

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

  return (
    <main style={{ maxWidth: 640, margin: "40px auto", fontFamily: "system-ui" }}>
      <div style={{ fontSize: 13, color: "#666", marginBottom: 8 }}>
        Question {q.question_index + 1} of {q.total_questions} · {q.category_name} ·{" "}
        {q.difficulty}
      </div>

      <h2 style={{ marginBottom: 20, lineHeight: 1.4 }}>{q.stem}</h2>

      <ul style={{ display: "grid", gap: 10, padding: 0, listStyle: "none" }}>
        {q.options.map((opt, i) => (
          <li
            key={i}
            style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12 }}
          >
            <strong style={{ marginRight: 8 }}>
              {String.fromCharCode(65 + i)}.
            </strong>
            {opt.text}
          </li>
        ))}
      </ul>

      <p style={{ marginTop: 24, fontSize: 13, color: "#999" }}>
        (Answering comes in the next step — this is read-only for now.)
      </p>
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