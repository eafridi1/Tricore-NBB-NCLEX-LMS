"use client";

import Link from "next/link";
import { isAxiosError } from "axios";
import { useParams } from "next/navigation";
import { useQuizResult } from "@/hooks/use-quiz-result";
import { QuizResults } from "@/components/quiz-results";

export default function QuizResultPage() {
  const params = useParams();
  const attemptId = Number(params.attemptId);

  const { data, isLoading, isError, error } = useQuizResult(attemptId);

  if (isLoading) return <Centered>Loading results…</Centered>;

  if (isError) {
    const notCompleted = isAxiosError(error) && error.response?.status === 403;
    return (
      <Centered>
        <div>
          <h2>{notCompleted ? "Not available yet" : "Couldn't load results"}</h2>
          <p style={{ color: "#666" }}>
            {notCompleted
              ? "This quiz attempt hasn't been completed."
              : error instanceof Error
              ? error.message
              : "Something went wrong."}
          </p>
          <p style={{ marginTop: 16 }}>
            <Link href="/dashboard" style={{ color: "#0B2540" }}>
              ← Back to dashboard
            </Link>
          </p>
        </div>
      </Centered>
    );
  }

  if (!data) return null;

  return <QuizResults result={data} />;
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ padding: 40, fontFamily: "system-ui", textAlign: "center" }}>
      {children}
    </div>
  );
}