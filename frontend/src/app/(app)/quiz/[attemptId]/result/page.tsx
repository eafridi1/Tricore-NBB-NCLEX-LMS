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
          <h2 className="text-lg font-semibold text-foreground">
            {notCompleted ? "Not available yet" : "Couldn't load results"}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {notCompleted
              ? "This quiz attempt hasn't been completed."
              : error instanceof Error
              ? error.message
              : "Something went wrong."}
          </p>
          <p className="mt-4">
            <Link href="/dashboard" className="text-sm text-primary hover:underline">
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
  return <div className="p-10 text-center">{children}</div>;
}