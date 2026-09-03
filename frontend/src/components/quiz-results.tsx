import Link from "next/link";
import type { components } from "@/types/api";
import { Card, CardContent } from "@/components/ui/card";

type QuizResultResponse = components["schemas"]["QuizResultResponse"];

export function QuizResults({ result }: { result: QuizResultResponse }) {
  return (
    <main className="mx-auto max-w-3xl px-5 py-10">
      <div
        className={`mb-7 rounded-lg border p-5 ${
          result.passed
            ? "border-green-200 bg-green-50"
            : "border-red-200 bg-red-50"
        }`}
      >
        <h1 className="mb-2 text-2xl font-semibold text-foreground">
          {result.passed ? "Passed" : "Not passed"}
        </h1>
        <div className="text-sm text-foreground/80">
          Score: <strong>{result.score}%</strong> · {result.correct_count}/
          {result.total_questions} correct
          {result.time_taken_secs != null && (
            <> · {Math.round(result.time_taken_secs / 60)} min</>
          )}
        </div>
      </div>

      <h2 className="mb-4 text-lg font-semibold text-foreground">Review</h2>

      <div className="grid gap-5">
        {result.questions.map((qr, qi) => (
          <Card key={qr.question_id}>
            <CardContent className="p-4">
              <div className="mb-1.5 text-xs text-muted-foreground">
                Q{qi + 1} · {qr.category_name} · {qr.difficulty} ·{" "}
                <span className={qr.is_correct ? "text-green-700" : "text-red-700"}>
                  {qr.is_correct ? "Correct" : "Incorrect"}
                </span>
              </div>
              <div className="mb-3 leading-relaxed text-foreground">{qr.stem}</div>

              <ul className="grid list-none gap-1.5 p-0">
                {qr.options.map((opt, i) => {
                  const isCorrect = i === qr.correct_answer;
                  const isChosen = i === qr.chosen_answer;
                  let cls = "border-border bg-card";
                  if (isCorrect) {
                    cls = "border-green-200 bg-green-50";
                  } else if (isChosen && !isCorrect) {
                    cls = "border-red-200 bg-red-50";
                  }
                  return (
                    <li key={i} className={`rounded-md border p-2 text-sm ${cls}`}>
                      <strong className="mr-1.5">
                        {String.fromCharCode(65 + i)}.
                      </strong>
                      {opt.text}
                      {isCorrect && (
                        <span className="ml-2 text-xs text-green-700">✓ correct</span>
                      )}
                      {isChosen && !isCorrect && (
                        <span className="ml-2 text-xs text-red-700">your answer</span>
                      )}
                    </li>
                  );
                })}
              </ul>

              <div className="mt-3 rounded-md bg-muted/60 p-3 text-sm leading-relaxed text-foreground/80">
                <strong>Rationale:</strong> {qr.rationale}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mt-7">
        <Link href="/dashboard" className="text-sm text-primary hover:underline">
          ← Back to dashboard
        </Link>
      </div>
    </main>
  );
}