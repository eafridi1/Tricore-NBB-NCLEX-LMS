"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useResumeQuiz, interpretResume } from "@/hooks/use-resume-quiz";
import { useQuizQuestion } from "@/hooks/use-quiz-question";
import { useAnswerQuestion } from "@/hooks/use-answer-question";
import { useFinishQuiz } from "@/hooks/use-finish-quiz";
import { useBookmark } from "@/hooks/use-bookmark";
import { QuizResults } from "@/components/quiz-results";
import { isAxiosError } from "axios";
import type { components } from "@/types/api";
import { Button } from "@/components/ui/button";

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
        <span className="text-destructive">{resume.message}</span>
      </Centered>
    );

  if (resume.kind === "ended")
    return (
      <Centered>
        <div>
          <h2 className="text-lg font-semibold text-foreground">
            This attempt has ended
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {resume.reason === "session_expired"
              ? "The time limit for this quiz has passed."
              : "This quiz is no longer in progress."}
          </p>
          <p className="mt-4">
            <Link href="/dashboard" className="text-sm text-primary hover:underline">
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
  const [bookmarked, setBookmarked] = useState(false);

  const [remaining, setRemaining] = useState<number | null>(null);
  const autoFinishedRef = useRef(false);

  const { data: q, isLoading, isError, error } = useQuizQuestion(attemptId, index);
  const answer = useAnswerQuestion(attemptId);
  const finish = useFinishQuiz(attemptId);
  const bookmark = useBookmark();

  useEffect(() => {
    if (q) {
      setSelected(q.already_answered ?? null);
      setBookmarked(q.is_bookmarked);
      if (q.time_remaining_secs != null) {
        setRemaining(q.time_remaining_secs);
      }
    }
  }, [q]);

  function autoFinish() {
    if (autoFinishedRef.current) return;
    autoFinishedRef.current = true;
    finish.mutate(undefined, {
      onSuccess: (res) => setResult(res),
    });
  }

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

  function toggleBookmark() {
    if (!q || bookmark.isPending) return;
    const next = !bookmarked;
    setBookmarked(next); // optimistic
    const mutation = next ? bookmark.add : bookmark.remove;
    mutation.mutate(q.question_id, {
      onError: () => setBookmarked(!next), // revert on failure
    });
  }

  if (result) return <QuizResults result={result} />;

  if (isLoading) return <Centered>Loading question…</Centered>;
  if (isError)
    return (
      <Centered>
        <span className="text-destructive">
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
    <main className="mx-auto max-w-2xl px-5 py-10">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-xs text-muted-foreground">
          Question {q.question_index + 1} of {q.total_questions} · {q.category_name} · {q.difficulty}
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={toggleBookmark}
            disabled={bookmark.isPending}
            title={bookmarked ? "Remove bookmark" : "Bookmark this question"}
            className={`text-lg leading-none ${
              bookmarked ? "text-amber-500" : "text-muted-foreground/50"
            } ${bookmark.isPending ? "cursor-default" : "cursor-pointer"}`}
          >
            {bookmarked ? "★" : "☆"}
          </button>
          {remaining != null && (
            <div
              className={`text-sm font-semibold tabular-nums ${
                remaining <= 30 ? "text-red-600" : "text-primary"
              }`}
            >
              {formatTime(remaining)}
            </div>
          )}
        </div>
      </div>

      <h2 className="mb-5 text-lg font-medium leading-relaxed text-foreground">
        {q.stem}
      </h2>

      <ul className="grid list-none gap-2.5 p-0">
        {q.options.map((opt, i) => {
          const isSelected = selected === i;
          return (
            <li key={i}>
              <button
                onClick={() => setSelected(i)}
                className={`w-full rounded-lg border p-3 text-left transition-colors ${
                  isSelected
                    ? "border-primary bg-primary/5 ring-1 ring-primary/20"
                    : "border-border bg-card hover:bg-muted/50"
                }`}
              >
                <strong className="mr-2 text-primary">
                  {String.fromCharCode(65 + i)}.
                </strong>
                {opt.text}
              </button>
            </li>
          );
        })}
      </ul>

      <div className="mt-6 flex justify-between">
        <Button variant="outline" onClick={handlePrev} disabled={index === 0}>
          Previous
        </Button>
        <Button onClick={handleNext} disabled={selected === null || busy}>
          {busy ? "Loading…" : isLast ? "Finish" : "Next"}
        </Button>
      </div>
    </main>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center">{children}</div>
    </div>
  );
}

function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  return `${m}:${s.toString().padStart(2, "0")}`;
}