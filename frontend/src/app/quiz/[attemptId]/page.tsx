"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useResumeQuiz, interpretResume } from "@/hooks/use-resume-quiz";
import { useQuizQuestion } from "@/hooks/use-quiz-question";
import { useAnswerQuestion } from "@/hooks/use-answer-question";
import { useFinishQuiz } from "@/hooks/use-finish-quiz";
import { QuizResults } from "@/components/quiz-results";
import { isAxiosError } from "axios";
import type { components } from "@/types/api";

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

  // Timer state: seconds remaining, or null if this quiz isn't timed.
  const [remaining, setRemaining] = useState<number | null>(null);
  const autoFinishedRef = useRef(false);

  const { data: q, isLoading, isError, error } = useQuizQuestion(attemptId, index);
  const answer = useAnswerQuestion(attemptId);
  const finish = useFinishQuiz(attemptId);

  // On each question load: reflect prior answer, and re-sync the timer to
  // the server's authoritative time_remaining_secs (drift/pause-proof).
  useEffect(() => {
    if (q) {
      setSelected(q.already_answered ?? null);
      if (q.time_remaining_secs != null) {
        setRemaining(q.time_remaining_secs);
      }
    }
  }, [q]);

  // Auto-finish helper (used by both the countdown hitting 0 and a 409).
  function autoFinish() {
    if (autoFinishedRef.current) return;
    autoFinishedRef.current = true;
    finish.mutate(undefined, {
      onSuccess: (res) => setResult(res),
    });
  }

  // Countdown tick. Only runs for timed quizzes (remaining != null).
  useEffect(() => {
    if (remaining == null || result) return;
    if (remaining <= 0) {
      autoFinish();
      return;
    }
    const t = setInterval(() => {
      setRemaining((r) => (r == null ? r : r - 1));
    }, 1000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remaining, result]);

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
        onError: (err) => {
          // Time ran out at the moment of answering — finish and score.
          if (
            isAxiosError(err) &&
            err.response?.status === 409 &&
            !autoFinishedRef.current
          ) {
            autoFinish();
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
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <div style={{ fontSize: 13, color: "#666" }}>
          Question {q.question_index + 1} of {q.total_questions} · {q.category_name}{" "}
          · {q.difficulty}
        </div>
        {remaining != null && (
          <div
            style={{
              fontSize: 14,
              fontWeight: 600,
              fontVariantNumeric: "tabular-nums",
              color: remaining <= 30 ? "#c62828" : "#0B2540",
            }}
          >
            {formatTime(remaining)}
          </div>
        )}
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

      {(answer.isError || finish.isError) && !autoFinishedRef.current && (
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

function formatTime(secs: number): string {
  const s = Math.max(0, secs);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, "0")}`;
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ padding: 40, fontFamily: "system-ui", textAlign: "center" }}>
      {children}
    </div>
  );
}