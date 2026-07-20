"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useResumeQuiz, interpretResume } from "@/hooks/use-resume-quiz";
import { useQuizQuestion } from "@/hooks/use-quiz-question";
import { useAnswerQuestion } from "@/hooks/use-answer-question";
import { useFinishQuiz } from "@/hooks/use-finish-quiz";
import type { components } from "@/types/api";
import { QuizResults } from "@/components/quiz-results";

type QuizResultResponse = components["schemas"]["QuizResultResponse"];

export default function QuizPage() {
  const params = useParams();
  const attemptId = Number(params.attemptId);

  const resumeQuery = useResumeQuiz(attemptId);
  const resume = interpretResume(
    resumeQuery.isLoading,
    resumeQuery.isError,
    resumeQuery.error,
    resumeQuery.data
  );

  // ── Gate on resume state ──────────────────────────────────────
  if (resume.kind === "loading") return <Centered>Loading quiz…</Centered>;

  if (resume.kind === "error")
    return (
      <Centered>
        <span style={{ color: "crimson" }}>{resume.message}</span>
      </Centered>
    );

  if (resume.kind === "ended")
    return (
      <Centered>
        <div>
          <h2>This attempt has ended</h2>
          <p style={{ color: "#666" }}>
            {resume.reason === "session_expired"
              ? "The time limit for this quiz has passed."
              : "This quiz is no longer in progress."}
          </p>
          <p style={{ marginTop: 16 }}>
            <Link href="/dashboard" style={{ color: "#0B2540" }}>
              ← Back to dashboard
            </Link>
          </p>
        </div>
      </Centered>
    );

  // resume.kind === "resumable" — hand off to the live quiz UI,
  // starting at the first unanswered question.
  return (
    <ActiveQuiz
      attemptId={attemptId}
      startIndex={Math.min(
        resume.data.answered_count,
        Math.max(0, resume.data.total_questions - 1)
      )}
    />
  );
}

function ActiveQuiz({
  attemptId,
  startIndex,
}: {
  attemptId: number;
  startIndex: number;
}) {
  const [index, setIndex] = useState(startIndex);
  const [selected, setSelected] = useState<number | null>(null);
  const [result, setResult] = useState<QuizResultResponse | null>(null);

  const { data: q, isLoading, isError, error } = useQuizQuestion(attemptId, index);
  const answer = useAnswerQuestion(attemptId);
  const finish = useFinishQuiz(attemptId);

  useEffect(() => {
    if (q) setSelected(q.already_answered ?? null);
  }, [q]);

  if (result) return <QuizResults result={result} />;

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
            finish.mutate(undefined, { onSuccess: (res) => setResult(res) });
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
          Could not save. This attempt may have expired —{" "}
          <Link href="/dashboard" style={{ color: "#0B2540" }}>
            back to dashboard
          </Link>
          .
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